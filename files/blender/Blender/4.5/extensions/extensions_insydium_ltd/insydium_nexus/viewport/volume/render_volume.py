# INSYDIUM NeXus Add-on for Blender
# Copyright (C) 2026 INSYDIUM LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Volume datablock manager for nxExplosiaFX render output.

We wish to populate grid data into a Volume object for the renderer to process.
As of Blender 5.1, the Python Volume API remains completely disk-mediated --
There is no way to attach an in-memory OpenVDB grid via the API.
The only viable approach at present is to write a transient VDB file and link it to the volume obj.
Note that the VDB files used here are mediators only, not designed to be a persistent cache.
This handler also creates the volume object itself as a child of the EFX object, and attaches
a material suitable for smoke and fire visualization
(only if volume / material do not initially exist).

Each VDB write first produces a unique never-reused filename.
This is done because it was discovered by experimentation that data
in Volume objects are internally cached with the cache keyed on the filename.
So we need to keep rotating filenames as new data is saved.  Using ``unload()`` alone on old data
is not sufficient to prevent stale data being displayed unless we also use unique filenames.

``prune_cache`` deletes VDB files older than the most recent ``_CACHE_KEEP_COUNT`` writes
so that the on-disk set per modifier stays within reasonable bounds.
We keep more than one file alive to avoid writing to files that are being read by the renderer.

The self-created Volume object is tagged with ``nexus_object_type = NX_EFX_RENDER_VOLUME``
so the orphan sweeper in ``handlers/cleanup.py`` removes it when the parent
ExplosiaFX modifier is deleted.
"""

from __future__ import annotations

import os

import bpy

VOLUME_OBJECT_TAG = "NX_EFX_RENDER_VOLUME"

# Monotonic write counter, one per modifier instance.
# This increments on every call to ``next_cache_filepath``
# so each write is made to a fresh filename. The
# renderer's filename-keyed grid cache must not see a re-used path name.
_next_slot: dict[str, int] = {}

# Number of recent cache files to keep on disk per modifier UID. Two is found to be enough.
# One is the file currently bound to the Volume object, and the second is the previous one,
# kept in case an in-flight render (e.g. F12 animation) is still reading it at next VDB write.
_CACHE_KEEP_COUNT = 2

# Zero-padded width of the counter portion of the filename. 8 digits =
# 100M writes before wraparound, unreachable in a single session.
_COUNTER_WIDTH = 8


def get_cache_dir(props) -> str:
    """Resolve the absolute directory for this modifier's temporary VDB files."""
    user_dir = (getattr(props, "explosiafx_render_cache_dir", "") or "").strip()
    if user_dir:
        return os.path.expanduser(bpy.path.abspath(user_dir))
    return os.path.join(bpy.app.tempdir, "nx_efx_cache")


def _file_pattern_prefix(mod_uid: str) -> str:
    return f"nx_efx_{mod_uid}_"


def next_cache_filepath(props, mod_uid: str) -> str:
    """Return the absolute path of the next VDB write target.

    Each call increments a monotonic per-modifier counter and returns a
    fresh filename. Older files are cleared by ``prune_cache``.
    """
    slot = _next_slot.get(mod_uid, 0)
    _next_slot[mod_uid] = slot + 1
    name = f"{_file_pattern_prefix(mod_uid)}{slot:0{_COUNTER_WIDTH}d}.vdb"
    return os.path.join(get_cache_dir(props), name)


def prune_cache(props, mod_uid: str, keep: int = _CACHE_KEEP_COUNT) -> None:
    """Delete cache files older than the most recent ``keep`` for this modifier.

    Exceptions: any ``OSError`` is passed so a file held open by an
    in-process render (e.g., Windows file lock) silently remains until
    the next prune attempt. A missing cache directory is also tolerated.
    """
    cache_dir = get_cache_dir(props)
    prefix = _file_pattern_prefix(mod_uid)
    try:
        entries = []
        for name in os.listdir(cache_dir):
            if not (name.startswith(prefix) and name.endswith(".vdb")):
                continue
            stem = name[len(prefix) : -4]
            try:
                tick = int(stem)
            except ValueError:
                continue
            entries.append((tick, name))
    except OSError:
        return

    entries.sort(reverse=True)
    for _, name in entries[keep:]:
        try:
            os.remove(os.path.join(cache_dir, name))
        except OSError:
            # File still held open by an in-flight render(?). Swallow and retry on next pass.
            pass


def _link_to_modifier_collections(
    volume_obj: bpy.types.Object, modifier_obj: bpy.types.Object
) -> None:
    for collection in modifier_obj.users_collection:
        try:
            collection.objects.link(volume_obj)
        except RuntimeError:
            pass
    if not volume_obj.users_collection:
        try:
            bpy.context.scene.collection.objects.link(volume_obj)
        except (AttributeError, RuntimeError):
            pass


def _build_smoke_node_group(name: str) -> bpy.types.NodeTree:
    """Create the smoke-handler node group with labeled sockets.

    Inputs:  Density, Extinction, Albedo, Anisotropy
    Outputs: Shader (Absorb + Scatter combined), Absorb Density (float)

    NOTE: The Absorb Density output is exposed because the parent material's emission
    path multiplies it into the blackbody term (Kirchhoff weighting on hot soot).
    """
    group = bpy.data.node_groups.new(name, "ShaderNodeTree")
    iface = group.interface
    iface.new_socket(name="Density", in_out="INPUT", socket_type="NodeSocketFloat")
    # Extinction coefficient
    extinction_socket = iface.new_socket(
        name="Extinction", in_out="INPUT", socket_type="NodeSocketFloat"
    )
    # ``subtype = "FACTOR"`` makes the socket render as a [min, max] slider in the UI.
    # ``min_value`` / ``max_value`` bound the slider drag and the numeric editor.
    # Note: these are UI bounds only — they do not limit values arriving from a linked
    # upstream node. That requires input limiting nodes internal to the group that pre-process
    # the socket incoming values (see below).
    try:
        extinction_socket.subtype = "FACTOR"
    except (AttributeError, TypeError):
        pass
    extinction_socket.default_value = 40.0
    extinction_socket.min_value = 0.0
    extinction_socket.max_value = 1000.0
    # Albedo
    albedo_socket = iface.new_socket(name="Albedo", in_out="INPUT", socket_type="NodeSocketFloat")
    try:
        albedo_socket.subtype = "FACTOR"
    except (AttributeError, TypeError):
        pass
    albedo_socket.default_value = 0.8
    albedo_socket.min_value = 0.0
    albedo_socket.max_value = 1.0
    # Anisotropy
    ani = iface.new_socket(name="Anisotropy", in_out="INPUT", socket_type="NodeSocketFloat")
    try:
        ani.subtype = "FACTOR"
    except (AttributeError, TypeError):
        pass
    ani.default_value = 0.4
    ani.min_value = -1.0
    ani.max_value = 1.0
    #
    iface.new_socket(name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
    iface.new_socket(name="Absorb Density", in_out="OUTPUT", socket_type="NodeSocketFloat")

    nodes = group.nodes
    links = group.links

    group_in = nodes.new("NodeGroupInput")
    group_in.location = (-1100, 100)
    group_out = nodes.new("NodeGroupOutput")
    group_out.location = (500, 100)

    # --- Input clamps: enforce valid ranges on incoming values ---
    # Extinction has no natural upper bound, so use MAXIMUM(value, 0) instead of Clamp.
    ext_clamp = nodes.new("ShaderNodeMath")
    ext_clamp.location = (-900, 250)
    ext_clamp.operation = "MAXIMUM"
    ext_clamp.label = "Extinction >= 0"
    ext_clamp.inputs[1].default_value = 0.0
    links.new(group_in.outputs["Extinction"], ext_clamp.inputs[0])

    albedo_clamp = nodes.new("ShaderNodeClamp")
    albedo_clamp.location = (-900, 100)
    albedo_clamp.label = "Albedo in [0, 1]"
    albedo_clamp.inputs["Min"].default_value = 0.0
    albedo_clamp.inputs["Max"].default_value = 1.0
    links.new(group_in.outputs["Albedo"], albedo_clamp.inputs["Value"])

    ani_clamp = nodes.new("ShaderNodeClamp")
    ani_clamp.location = (-900, -50)
    ani_clamp.label = "Anisotropy in [-1, 1]"
    ani_clamp.inputs["Min"].default_value = -1.0
    ani_clamp.inputs["Max"].default_value = 1.0
    links.new(group_in.outputs["Anisotropy"], ani_clamp.inputs["Value"])

    mul_density_ext = nodes.new("ShaderNodeMath")
    mul_density_ext.location = (-600, 200)
    mul_density_ext.operation = "MULTIPLY"
    mul_density_ext.label = "density x extinction"
    links.new(group_in.outputs["Density"], mul_density_ext.inputs[0])
    links.new(ext_clamp.outputs[0], mul_density_ext.inputs[1])

    one_minus_albedo = nodes.new("ShaderNodeMath")
    one_minus_albedo.location = (-600, 500)
    one_minus_albedo.operation = "SUBTRACT"
    one_minus_albedo.label = "1 - albedo"
    one_minus_albedo.inputs[0].default_value = 1.0
    links.new(albedo_clamp.outputs[0], one_minus_albedo.inputs[1])

    absorb_density = nodes.new("ShaderNodeMath")
    absorb_density.location = (-300, 400)
    absorb_density.operation = "MULTIPLY"
    absorb_density.label = "absorb density"
    links.new(one_minus_albedo.outputs[0], absorb_density.inputs[0])
    links.new(mul_density_ext.outputs[0], absorb_density.inputs[1])

    scatter_density = nodes.new("ShaderNodeMath")
    scatter_density.location = (-300, 200)
    scatter_density.operation = "MULTIPLY"
    scatter_density.label = "scatter density"
    links.new(albedo_clamp.outputs[0], scatter_density.inputs[0])
    links.new(mul_density_ext.outputs[0], scatter_density.inputs[1])

    absorb = nodes.new("ShaderNodeVolumeAbsorption")
    absorb.location = (0, 300)
    absorb.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    links.new(absorb_density.outputs[0], absorb.inputs["Density"])

    scatter = nodes.new("ShaderNodeVolumeScatter")
    scatter.location = (0, 100)
    if "Anisotropy" in scatter.inputs:
        links.new(ani_clamp.outputs[0], scatter.inputs["Anisotropy"])
    links.new(scatter_density.outputs[0], scatter.inputs["Density"])

    add_smoke = nodes.new("ShaderNodeAddShader")
    add_smoke.location = (250, 200)
    add_smoke.label = "Absorb + Scatter"
    links.new(absorb.outputs[0], add_smoke.inputs[0])
    links.new(scatter.outputs[0], add_smoke.inputs[1])

    links.new(add_smoke.outputs[0], group_out.inputs["Shader"])
    links.new(absorb_density.outputs[0], group_out.inputs["Absorb Density"])

    return group


def _build_flame_node_group(name: str) -> bpy.types.NodeTree:
    """Create the flame/emission node group with labeled sockets.

    Inputs:  Temperature (K), Absorb Density, Tmin (K),
             Hot Soot Emit Intensity, Direct Emit Intensity
    Output:  Shader (Blackbody Emission)

    Internals:
      filtered_T = (T > Tmin) * T                            # threshold discard
      Color      = Blackbody(filtered_T)
      Tn         = filtered_T / 2500
      Strength   = (Tn^4 * Absorb Density) * SootEmit        # Kirchhoff local equilibrium
                 + Tn^4 * DirectEmit                         # direct emission
    """
    group = bpy.data.node_groups.new(name, "ShaderNodeTree")
    iface = group.interface
    iface.new_socket(name="Temperature", in_out="INPUT", socket_type="NodeSocketFloat")
    iface.new_socket(name="Absorb Density", in_out="INPUT", socket_type="NodeSocketFloat")
    tmin_sock = iface.new_socket(name="Tmin", in_out="INPUT", socket_type="NodeSocketFloat")
    # See comments in smoke node group about the FACTOR subtype.
    try:
        tmin_sock.subtype = "FACTOR"
    except (AttributeError, TypeError):
        pass
    tmin_sock.default_value = 1100.0
    tmin_sock.min_value = 0.0
    tmin_sock.max_value = 10000.0
    sootemit_sock = iface.new_socket(
        name="Hot Soot Emit Intensity", in_out="INPUT", socket_type="NodeSocketFloat"
    )
    try:
        sootemit_sock.subtype = "FACTOR"
    except (AttributeError, TypeError):
        pass
    sootemit_sock.default_value = 0.5
    sootemit_sock.min_value = 0.0
    sootemit_sock.max_value = 10.0
    direct_sock = iface.new_socket(
        name="Direct Emit Intensity", in_out="INPUT", socket_type="NodeSocketFloat"
    )
    try:
        direct_sock.subtype = "FACTOR"
    except (AttributeError, TypeError):
        pass
    direct_sock.default_value = 0.25
    direct_sock.min_value = 0.0
    direct_sock.max_value = 10.0
    iface.new_socket(name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader")

    nodes = group.nodes
    links = group.links

    group_in = nodes.new("NodeGroupInput")
    group_in.location = (-1100, -150)
    group_out = nodes.new("NodeGroupOutput")
    group_out.location = (700, -150)

    # --- Input clamps: enforce non-negative values on user knobs.
    # Each uses MAXIMUM(value, 0) since there is no natural upper bound.
    tmin_clamp = nodes.new("ShaderNodeMath")
    tmin_clamp.location = (-900, -100)
    tmin_clamp.operation = "MAXIMUM"
    tmin_clamp.label = "Tmin >= 0"
    tmin_clamp.inputs[1].default_value = 0.0
    links.new(group_in.outputs["Tmin"], tmin_clamp.inputs[0])

    sootemit_clamp = nodes.new("ShaderNodeMath")
    sootemit_clamp.location = (-900, -250)
    sootemit_clamp.operation = "MAXIMUM"
    sootemit_clamp.label = "Hot Soot Emit >= 0"
    sootemit_clamp.inputs[1].default_value = 0.0
    links.new(group_in.outputs["Hot Soot Emit Intensity"], sootemit_clamp.inputs[0])

    directemit_clamp = nodes.new("ShaderNodeMath")
    directemit_clamp.location = (-900, -400)
    directemit_clamp.operation = "MAXIMUM"
    directemit_clamp.label = "Direct Emit >= 0"
    directemit_clamp.inputs[1].default_value = 0.0
    links.new(group_in.outputs["Direct Emit Intensity"], directemit_clamp.inputs[0])

    temp_gt = nodes.new("ShaderNodeMath")
    temp_gt.location = (-700, -150)
    temp_gt.operation = "GREATER_THAN"
    temp_gt.label = "T > Tmin"
    links.new(group_in.outputs["Temperature"], temp_gt.inputs[0])
    links.new(tmin_clamp.outputs[0], temp_gt.inputs[1])

    temp_filtered = nodes.new("ShaderNodeMath")
    temp_filtered.location = (-500, -150)
    temp_filtered.operation = "MULTIPLY"
    temp_filtered.label = "T (filtered)"
    links.new(temp_gt.outputs[0], temp_filtered.inputs[0])
    links.new(group_in.outputs["Temperature"], temp_filtered.inputs[1])

    bb = nodes.new("ShaderNodeBlackbody")
    bb.location = (-100, -150)
    links.new(temp_filtered.outputs[0], bb.inputs["Temperature"])

    tn = nodes.new("ShaderNodeMath")
    tn.location = (-500, -300)
    tn.operation = "DIVIDE"
    tn.inputs[1].default_value = 2500.0
    tn.label = "T / 2500"
    links.new(temp_filtered.outputs[0], tn.inputs[0])

    tn4 = nodes.new("ShaderNodeMath")
    tn4.location = (-300, -300)
    tn4.operation = "POWER"
    tn4.inputs[1].default_value = 4.0
    tn4.label = "Tn^4"
    links.new(tn.outputs[0], tn4.inputs[0])

    # Kirchhoff weighting on the hot-soot path: in LTE, emission \propto \mu_a \times B(T),
    # so multiply Tn^4 by the absorption density before the intensity gain.
    hot_soot_term = nodes.new("ShaderNodeMath")
    hot_soot_term.location = (-100, -250)
    hot_soot_term.operation = "MULTIPLY"
    hot_soot_term.label = "Tn^4 x absorb"
    links.new(tn4.outputs[0], hot_soot_term.inputs[0])
    links.new(group_in.outputs["Absorb Density"], hot_soot_term.inputs[1])

    hot_soot_intensity = nodes.new("ShaderNodeMath")
    hot_soot_intensity.location = (100, -200)
    hot_soot_intensity.operation = "MULTIPLY"
    hot_soot_intensity.label = "Hot Soot Emit Intensity"
    links.new(hot_soot_term.outputs[0], hot_soot_intensity.inputs[0])
    links.new(sootemit_clamp.outputs[0], hot_soot_intensity.inputs[1])

    direct_intensity = nodes.new("ShaderNodeMath")
    direct_intensity.location = (100, -400)
    direct_intensity.operation = "MULTIPLY"
    direct_intensity.label = "Direct Emit Intensity"
    links.new(tn4.outputs[0], direct_intensity.inputs[0])
    links.new(directemit_clamp.outputs[0], direct_intensity.inputs[1])

    intensity_sum = nodes.new("ShaderNodeMath")
    intensity_sum.location = (300, -300)
    intensity_sum.operation = "ADD"
    intensity_sum.label = "Total Emit Intensity"
    links.new(hot_soot_intensity.outputs[0], intensity_sum.inputs[0])
    links.new(direct_intensity.outputs[0], intensity_sum.inputs[1])

    emission = nodes.new("ShaderNodeEmission")
    emission.location = (500, -150)
    links.new(bb.outputs["Color"], emission.inputs["Color"])
    strength_socket = emission.inputs.get("Strength") or emission.inputs.get("Density")
    if strength_socket is not None:
        links.new(intensity_sum.outputs[0], strength_socket)

    links.new(emission.outputs[0], group_out.inputs["Shader"])

    return group


def _build_default_material(name: str) -> bpy.types.Material:
    """Create a volume material that mirrors the viewport raymarcher's look.

    Smoke = Volume Absorption + Volume Scatter, both driven by the ``density``
    attribute. Fire = Volume Emission with:

      Color    = Blackbody(clamp(temperature, 0, 6500))
      Strength = (temperature / 2500)^4  *  density  *  flame_gain

    The ``T^4`` factor mirrors the Stefan-Boltzmann intensity scaling in
    ``viewport/volume/basic.py``'s ``BlackBodyRGB`` (normalized at 2500 K),
    which is what makes fire read as "hot" rather than dim brown.

    The ``temperature`` grid is read directly in Kelvin.
    """
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    for node in list(nt.nodes):
        nt.nodes.remove(node)

    # --- Attribute reads ---
    attr_density = nt.nodes.new("ShaderNodeAttribute")
    attr_density.location = (-700, 250)
    attr_density.attribute_name = "density"
    attr_density.label = "density"

    attr_temp = nt.nodes.new("ShaderNodeAttribute")
    attr_temp.location = (-700, -200)
    attr_temp.attribute_name = "temperature"
    attr_temp.label = "temperature (K)"

    # --- Smoke shader graph (encapsulated as a node group) ---
    # Total extinction \mu_t = density \times extinction. Then split by albedo:
    #   absorb density \mu_a = \mu_t \times (1 − albedo)
    #   scatter density \mu_s = \mu_t \times albedo
    smoke_group = nt.nodes.new("ShaderNodeGroup")
    smoke_group.node_tree = _build_smoke_node_group("EFX_Smoke")
    smoke_group.location = (-400, 250)
    smoke_group.label = "Smoke"
    nt.links.new(attr_density.outputs["Fac"], smoke_group.inputs["Density"])

    # --- Flame / emission graph (encapsulated as a node group) ---
    # See _build_flame_node_group for the internal math.
    flame_group = nt.nodes.new("ShaderNodeGroup")
    flame_group.node_tree = _build_flame_node_group("EFX_Flame")
    flame_group.location = (-100, -200)
    flame_group.label = "Flame"
    nt.links.new(attr_temp.outputs["Fac"], flame_group.inputs["Temperature"])
    nt.links.new(smoke_group.outputs["Absorb Density"], flame_group.inputs["Absorb Density"])

    # --- Combine: Smoke (Absorb + Scatter) + Flame (Emission) ---
    add_total = nt.nodes.new("ShaderNodeAddShader")
    add_total.location = (200, 50)
    nt.links.new(smoke_group.outputs["Shader"], add_total.inputs[0])
    nt.links.new(flame_group.outputs["Shader"], add_total.inputs[1])

    output = nt.nodes.new("ShaderNodeOutputMaterial")
    output.location = (500, 100)
    nt.links.new(add_total.outputs[0], output.inputs["Volume"])
    return mat


def _ensure_default_material(volume_obj: bpy.types.Object) -> None:
    """Attach a default material to the Volume only if it has none.

    If material construction fails (e.g. shader node socket name mismatch on a future Blender),
    log the traceback and gracefully leave the Volume with no material. Do not raise.
    """
    if volume_obj.data is None:
        return
    if len(volume_obj.data.materials) > 0:
        return
    try:
        mat = _build_default_material(f"{volume_obj.name}_mat")
        volume_obj.data.materials.append(mat)
    except Exception as exc:
        import traceback

        print(f"[nx_explosiafx render_volume] default material build failed: {exc}")
        traceback.print_exc()


def _adopt_orphan_render_volume(modifier_obj: bpy.types.Object) -> bpy.types.Object | None:
    """If previous runs left tagged child Volume objects on this modifier,
    keep the first and remove the rest. This repeairs scenes where the pointer got detached
    but child Volume object(s) remain."""
    candidates = [
        c
        for c in modifier_obj.children
        if c.get("nexus_object_type") == VOLUME_OBJECT_TAG and c.type == "VOLUME"
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda c: c.name)
    keep, extras = candidates[0], candidates[1:]
    for extra in extras:
        try:
            extra_data = extra.data
            bpy.data.objects.remove(extra, do_unlink=True)
            if extra_data is not None and extra_data.users == 0:
                bpy.data.volumes.remove(extra_data)
        except (ReferenceError, RuntimeError):
            pass
    return keep


def ensure_render_volume(modifier_obj: bpy.types.Object) -> bpy.types.Object | None:
    """Return the Volume object linked to this modifier, creating and linking a new one if needed.

    NOTE: we store the pointer before attempting material creation. This is done so that any
    failure in building the material does not result in a stranded bad state with a tagged
    child Volume and no pointer -- that would mean another child Volume is created
    on the next render (and so on).
    """
    props = modifier_obj.nexus_modifier
    existing = getattr(props, "explosiafx_render_volume_obj", None)
    if existing is not None and existing.name in bpy.data.objects:
        return existing

    # Recover: adopt a tagged child if a prior run created one but didn't store the pointer.
    adopted = _adopt_orphan_render_volume(modifier_obj)
    if adopted is not None:
        props.explosiafx_render_volume_obj = adopted
        _ensure_default_material(adopted)
        return adopted

    volume_data = bpy.data.volumes.new(name=f"{modifier_obj.name}_volume")
    volume_obj = bpy.data.objects.new(volume_data.name, volume_data)
    volume_obj["nexus_object_type"] = VOLUME_OBJECT_TAG

    volume_obj.parent = modifier_obj
    volume_obj.matrix_parent_inverse.identity()
    volume_obj.matrix_local.identity()

    _link_to_modifier_collections(volume_obj, modifier_obj)
    # Pointer first before material, as discussed in docstring.
    props.explosiafx_render_volume_obj = volume_obj
    _ensure_default_material(volume_obj)
    return volume_obj


def update_render_volume(
    modifier_obj: bpy.types.Object, scene: bpy.types.Scene, frame_filepath: str
) -> bpy.types.Object | None:
    """Point the linked Volume datablock at the just-written single-frame VDB file."""
    del scene
    volume_obj = ensure_render_volume(modifier_obj)
    if volume_obj is None or volume_obj.data is None:
        return None

    volume = volume_obj.data
    if volume.is_sequence:
        volume.is_sequence = False
    if volume.filepath != frame_filepath:
        volume.filepath = frame_filepath
    return volume_obj


def reload_render_volume(modifier_obj: bpy.types.Object) -> None:
    """Discard the Volume datablock's in-RAM grids after a fresh write."""
    props = modifier_obj.nexus_modifier
    volume_obj = getattr(props, "explosiafx_render_volume_obj", None)
    if volume_obj is None or volume_obj.data is None:
        return
    try:
        if hasattr(volume_obj.data, "unload"):
            volume_obj.data.unload()
        volume_obj.data.update_tag()
        volume_obj.update_tag()
    except (AttributeError, RuntimeError) as exc:
        print(f"[nx_explosiafx render_volume] reload failed: {exc}")


def remove_render_volume(modifier_obj: bpy.types.Object) -> None:
    """Detach and remove the Volume object + datablock for this modifier."""
    props = modifier_obj.nexus_modifier
    volume_obj = getattr(props, "explosiafx_render_volume_obj", None)
    if volume_obj is None:
        return
    try:
        volume_data = volume_obj.data
        bpy.data.objects.remove(volume_obj, do_unlink=True)
        if volume_data is not None and volume_data.users == 0:
            bpy.data.volumes.remove(volume_data)
    except (ReferenceError, RuntimeError):
        pass
    props.explosiafx_render_volume_obj = None
