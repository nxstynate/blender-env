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

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
)

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..ui import NodeTreeDef, make_allowed_types_poll
from ..utils import XP_COLOR_MODS_BLUE

_MAX_FILTERED_EMITTERS = 32

_SCALE_SOURCE_ITEMS = [
    ("CUSTOM", "Custom", "Use the per-axis scale set on this layer"),
    ("MESH", "Mesh Scale", "Use the picked object's transform scale"),
    ("PARTICLE_RADIUS", "Particle Radius", "Use the per-particle radius (uniform on all axes)"),
    ("PARTICLE_SCALE", "Particle Scale", "Use the per-particle vec3 scale buffer"),
]

_COLOR_SOURCE_ITEMS = [
    ("CUSTOM", "Custom", "Use the colour set on this layer"),
    ("MESH", "Mesh", "Use the picked object's viewport colour"),
    ("PARTICLE", "Particle", "Use the per-particle colour from the simulation"),
]

_ROTATION_SOURCE_ITEMS = [
    ("CUSTOM", "Custom", "Use the per-axis rotation set on this layer"),
    ("MESH", "Mesh", "Use the picked object's transform rotation"),
    ("PARTICLE", "Particle", "Use the per-particle HPB from the simulation"),
]

_SHADING_MODE_ITEMS = [
    ("DEFAULT", "Default", "Use the source mesh's own per-polygon smooth/flat shading flags"),
    ("FLAT", "Flat", "Force flat shading for every face"),
    ("SMOOTH", "Smooth", "Force smooth shading by averaging vertex normals"),
]


# Recursion guard for the auto-balance: when one layer's update callback
# adjusts other layers, we must not re-fire the callback on each adjustment.
_LOCK_GUARD = False

# Per-generator layer-count snapshot, used by the index-update callback to
# detect add/remove (which the framework operators trigger via index changes).
# Keyed by ``obj.session_uid``.
_LAST_LAYER_COUNTS: dict[int, int] = {}


def _tag_redraw_3d_views(_self, context) -> None:
    """Force a 3D viewport redraw — used by layer-property update callbacks."""
    if context is None or context.screen is None:
        return
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


def _rebalance_unlocked_pool(props) -> None:
    """Rescale the unlocked-enabled layers proportionally so their sum plus the
    locked-enabled sum is 100%. Locked layers and disabled layers untouched.

    Caller need not set ``_LOCK_GUARD`` — this function manages it.
    """
    locked_sum = 0.0
    unlocked = []
    for layer in props.generator_layers:
        if not layer.enabled:
            continue
        if layer.locked:
            locked_sum += layer.spawn_chance
        else:
            unlocked.append(layer)

    if not unlocked:
        return

    target = max(0.0, 100.0 - locked_sum)
    unlocked_sum = sum(layer.spawn_chance for layer in unlocked)
    global _LOCK_GUARD
    _LOCK_GUARD = True
    try:
        if unlocked_sum <= 0.0:
            share = target / len(unlocked)
            for layer in unlocked:
                layer.spawn_chance = share
        else:
            scale = target / unlocked_sum
            for layer in unlocked:
                layer.spawn_chance = max(0.0, min(100.0, layer.spawn_chance * scale))
    finally:
        _LOCK_GUARD = False


def _on_enabled_change(self, context) -> None:
    """Layer enabled/disabled — rescale unlocked-enabled layers to sum to 100%."""
    _tag_redraw_3d_views(self, context)
    if _LOCK_GUARD:
        return
    obj = self.id_data
    if obj is None or obj.get("nexus_modifier_type") != "NX_GENERATOR":
        return
    _rebalance_unlocked_pool(obj.nexus_modifier)


def _on_layers_index_change(self, context) -> None:
    """Index changed — redraw, and if the layer COUNT changed (add/remove)
    rebalance the unlocked-enabled pool to sum to 100%."""
    _tag_redraw_3d_views(self, context)

    obj = self.id_data
    if obj is None or obj.get("nexus_modifier_type") != "NX_GENERATOR":
        return

    key = obj.session_uid
    current_count = len(self.generator_layers)
    last_count = _LAST_LAYER_COUNTS.get(key, current_count)
    _LAST_LAYER_COUNTS[key] = current_count

    if current_count == last_count:
        return  # plain click on a layer — leave values alone.

    if current_count > last_count:
        # Layer was added. Give it a fair share of the unlocked pool; the
        # spawn-change cascade then scales the rest down proportionally.
        layers = self.generator_layers
        new_idx = self.generator_layers_index
        if 0 <= new_idx < current_count:
            new_layer = layers[new_idx]
            if new_layer.enabled and not new_layer.locked:
                unlocked_count = sum(1 for layer in layers if layer.enabled and not layer.locked)
                if unlocked_count > 0:
                    locked_sum = sum(
                        layer.spawn_chance for layer in layers if layer.enabled and layer.locked
                    )
                    target_pool = max(0.0, 100.0 - locked_sum)
                    new_layer.spawn_chance = target_pool / unlocked_count
                    return  # _on_spawn_change cascade does the rest
    # Either it was a removal, or the new layer wasn't eligible — proportional
    # rebalance of the surviving / current pool.
    _rebalance_unlocked_pool(self)


def _on_spawn_change(self, context) -> None:
    """A layer's spawn_chance was changed — redistribute the surplus/deficit
    among the OTHER enabled, *unlocked* layers so the total stays at 100%.

    Locked layers keep their values; only unlocked others rescale. ``self``
    (the layer being dragged) keeps the value the user just set, even if it
    is itself locked — explicit user input always wins.
    """
    _tag_redraw_3d_views(self, context)

    global _LOCK_GUARD
    if _LOCK_GUARD:
        return

    obj = self.id_data
    if obj is None or obj.get("nexus_modifier_type") != "NX_GENERATOR":
        return
    props = obj.nexus_modifier
    if not self.enabled:
        return  # disabled layer leaves the pool; renderer handles normalisation

    layers = props.generator_layers
    self_ptr = self.as_pointer()

    locked_others_sum = 0.0
    unlocked_others = []
    for layer in layers:
        if layer.as_pointer() == self_ptr:
            continue
        if not layer.enabled:
            continue
        if layer.locked:
            locked_others_sum += layer.spawn_chance
        else:
            unlocked_others.append(layer)

    # Clamp self if locked-others already account for too much of the pool.
    cap = max(0.0, 100.0 - locked_others_sum)
    _LOCK_GUARD = True
    try:
        if self.spawn_chance > cap:
            self.spawn_chance = cap
    finally:
        _LOCK_GUARD = False

    if not unlocked_others:
        # Self is the only unlocked-enabled layer. If self is unlocked,
        # pin it to (100 - locked_sum) — there's no one else to absorb
        # under or overshoot, so the value is forced.
        if not self.locked:
            target_for_self = max(0.0, 100.0 - locked_others_sum)
            if abs(self.spawn_chance - target_for_self) > 1e-6:
                _LOCK_GUARD = True
                try:
                    self.spawn_chance = target_for_self
                finally:
                    _LOCK_GUARD = False
        return

    target = max(0.0, 100.0 - self.spawn_chance - locked_others_sum)
    unlocked_sum = sum(layer.spawn_chance for layer in unlocked_others)
    _LOCK_GUARD = True
    try:
        if unlocked_sum <= 0.0:
            share = target / len(unlocked_others)
            for layer in unlocked_others:
                layer.spawn_chance = share
        else:
            scale = target / unlocked_sum
            for layer in unlocked_others:
                layer.spawn_chance = max(0.0, min(100.0, layer.spawn_chance * scale))
    finally:
        _LOCK_GUARD = False


def _on_display_mode_change(self, context) -> None:
    _tag_redraw_3d_views(self, context)
    obj = self.id_data
    if obj is None or obj.get("nexus_modifier_type") != "NX_GENERATOR":
        return
    from ..modifiers.nx_generator_realgeo import (
        ensure_realgeo_setup,
        teardown_realgeo,
    )

    if self.display_mode == "GEOMETRY":
        ensure_realgeo_setup(obj, self)
    else:
        teardown_realgeo(obj, self)


def _on_freeze_toggle(self, context) -> None:
    _tag_redraw_3d_views(self, context)
    obj = self.id_data
    if obj is None or obj.get("nexus_modifier_type") != "NX_GENERATOR":
        return
    if not self.freeze_animation:
        return
    if context is None or self.obj is None:
        return
    scene = context.scene
    if scene is None:
        return
    self.frozen_frame = int(scene.frame_current)
    from ..viewport.generators.cache import capture_frozen_mesh

    depsgraph = context.evaluated_depsgraph_get()
    capture_frozen_mesh(self.obj, self.frozen_frame, depsgraph)


def _variation_prop(name: str, description: str) -> FloatProperty:
    return FloatProperty(
        name=name,
        description=description,
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_tag_redraw_3d_views,
    )


class NexusGeneratorLayerItem(bpy.types.PropertyGroup):
    """One layer in an NX_GENERATOR — its own mesh + sources + variations + spawn weight."""

    obj: PointerProperty(
        name="Mesh",
        description="Mesh to instance for particles assigned to this layer",
        type=bpy.types.Object,
        poll=make_allowed_types_poll(["MESH"]),
        update=_tag_redraw_3d_views,
    )
    enabled: BoolProperty(name="Enabled", default=True, update=_on_enabled_change)
    locked: BoolProperty(
        name="Lock",
        description=(
            "When on, this layer's spawn chance is preserved when other "
            "layers' sliders are dragged. The value can still be changed "
            "by dragging this layer's own slider"
        ),
        default=False,
        update=_tag_redraw_3d_views,
    )

    spawn_chance: FloatProperty(
        name="Spawn",
        description=(
            "Layer's share of particles. Dragging this redistributes the "
            "remainder among the other enabled, unlocked layers so the total "
            "stays at 100%"
        ),
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_spawn_change,
    )

    # --- Scale ---
    scale_source: EnumProperty(
        name="Scale Source",
        description="Where each instance's scale comes from",
        items=_SCALE_SOURCE_ITEMS,
        default="CUSTOM",
        update=_tag_redraw_3d_views,
    )
    custom_scale_per_axis: BoolProperty(
        name="Per-axis Scale",
        description="Use independent X / Y / Z scale values",
        default=False,
        update=_tag_redraw_3d_views,
    )
    custom_scale_uniform: FloatProperty(
        name="Scale",
        description="Per-layer uniform scale when Source is Custom",
        default=1.0,
        min=0.0,
        soft_max=10.0,
        update=_tag_redraw_3d_views,
    )
    custom_scale: FloatVectorProperty(
        name="Scale",
        description="Per-layer per-axis scale when Source is Custom",
        size=3,
        default=(1.0, 1.0, 1.0),
        subtype="XYZ",
        update=_tag_redraw_3d_views,
    )
    scale_variation_per_axis: BoolProperty(
        name="Per-axis Scale Variation",
        description="Use independent X / Y / Z variation amounts",
        default=False,
        update=_tag_redraw_3d_views,
    )
    scale_variation: _variation_prop(
        "Scale Variation",
        "Per-particle random scale jitter, ± of the base value",
    )
    scale_variation_x: _variation_prop("X", "Per-particle X-axis scale jitter")
    scale_variation_y: _variation_prop("Y", "Per-particle Y-axis scale jitter")
    scale_variation_z: _variation_prop("Z", "Per-particle Z-axis scale jitter")

    # --- Shading ---
    shading_mode: EnumProperty(
        name="Shading",
        description="How to shade the instanced mesh",
        items=_SHADING_MODE_ITEMS,
        default="DEFAULT",
        update=_tag_redraw_3d_views,
    )

    # --- Colour ---
    color_source: EnumProperty(
        name="Colour Source",
        description="Where each instance's colour comes from",
        items=_COLOR_SOURCE_ITEMS,
        default="CUSTOM",
        update=_tag_redraw_3d_views,
    )
    custom_color: FloatVectorProperty(
        name="Colour",
        description="Per-layer colour used when Source is Custom",
        subtype="COLOR",
        size=4,
        default=XP_COLOR_MODS_BLUE,
        min=0.0,
        max=1.0,
        update=_tag_redraw_3d_views,
    )
    color_variation_per_axis: BoolProperty(
        name="Per-channel Colour Variation",
        description="Use independent R / G / B variation amounts",
        default=False,
        update=_tag_redraw_3d_views,
    )
    color_variation: _variation_prop(
        "Colour Variation",
        "Per-particle random RGB jitter, ± of the base value",
    )
    color_variation_r: _variation_prop("R", "Per-particle red-channel jitter, ± of the base")
    color_variation_g: _variation_prop("G", "Per-particle green-channel jitter, ± of the base")
    color_variation_b: _variation_prop("B", "Per-particle blue-channel jitter, ± of the base")

    # --- Rotation ---
    rotation_source: EnumProperty(
        name="Rotation Source",
        description="Where each instance's rotation comes from",
        items=_ROTATION_SOURCE_ITEMS,
        default="CUSTOM",
        update=_tag_redraw_3d_views,
    )
    custom_rotation_per_axis: BoolProperty(
        name="Per-axis Rotation",
        description="Use independent X / Y / Z rotation values",
        default=False,
        update=_tag_redraw_3d_views,
    )
    custom_rotation_uniform: FloatProperty(
        name="Rotation",
        description="Per-layer uniform rotation (applied to X, Y, Z) when Source is Custom",
        default=0.0,
        subtype="ANGLE",
        unit="ROTATION",
        update=_tag_redraw_3d_views,
    )
    custom_rotation: FloatVectorProperty(
        name="Rotation",
        description="Per-layer per-axis Euler rotation when Source is Custom",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
        unit="ROTATION",
        update=_tag_redraw_3d_views,
    )
    rotation_variation_per_axis: BoolProperty(
        name="Per-axis Rotation Variation",
        description="Use independent X / Y / Z variation amounts",
        default=False,
        update=_tag_redraw_3d_views,
    )
    rotation_variation: _variation_prop(
        "Rotation Variation",
        "Per-particle random rotation jitter, in [0, 100]% of a full turn",
    )
    rotation_variation_x: _variation_prop("X", "Per-particle pitch (X-axis) jitter")
    rotation_variation_y: _variation_prop("Y", "Per-particle heading (Y-axis) jitter")
    rotation_variation_z: _variation_prop("Z", "Per-particle bank (Z-axis) jitter")

    # --- Real geometry ---
    instance_material: PointerProperty(
        name="Instance Material",
        description=(
            "Material applied to instances of this layer. Leave empty to use the "
            "source mesh's material as-is. Use the '+' button to spawn a starter "
            "material wired to per-instance attributes (nx_color etc.)"
        ),
        type=bpy.types.Material,
        update=_tag_redraw_3d_views,
    )

    # --- Animation ---
    freeze_animation: BoolProperty(
        name="Freeze Animation",
        description="Lock instances to the source mesh's pose at toggle time",
        default=False,
        update=_on_freeze_toggle,
    )
    frozen_frame: IntProperty(
        name="Frozen Frame",
        description="Scene frame captured by the freeze",
        default=1,
        min=0,
    )

    # --- UI fold state ---
    color_expanded: BoolProperty(name="Colour Expanded", default=True)
    scale_expanded: BoolProperty(name="Scale Expanded", default=False)
    rotation_expanded: BoolProperty(name="Rotation Expanded", default=False)
    animation_expanded: BoolProperty(name="Animation Expanded", default=False)


class NexusGeneratorSourceEmitterItem(bpy.types.PropertyGroup):
    obj: PointerProperty(
        name="Emitter",
        description="Restrict the generator to particles emitted by this emitter",
        type=bpy.types.Object,
        poll=make_allowed_types_poll(["NX_EMITTER"]),
        update=_tag_redraw_3d_views,
    )
    enabled: BoolProperty(name="Enabled", default=True, update=_tag_redraw_3d_views)


_SOURCE_EMITTERS = NodeTreeDef(
    "Source Emitters",
    item_type=NexusGeneratorSourceEmitterItem,
    allowed_types=["NX_EMITTER"],
)
_source_emitters_props = _SOURCE_EMITTERS.properties("source_emitters")


def _is_generator_excluded_on_emitter(emitter_obj, generator_obj) -> bool:
    """Return True if the emitter's Modifiers tab discludes the generator."""
    try:
        items = emitter_obj.nexus_modifier.emitter_modifier_objects
    except (AttributeError, ReferenceError):
        return False
    for item in items:
        try:
            if item.obj == generator_obj and not item.enabled:
                return True
        except ReferenceError:
            continue
    return False


def compute_emitter_filter_mask(scene, generator_obj) -> int:
    """Bitmask of emitter indices ``generator_obj`` instances on. 0 = none."""
    from ..handlers import pipeline as pipeline_manager

    try:
        props = generator_obj.nexus_modifier
    except (AttributeError, ReferenceError):
        return 0

    mask = 0
    for item in getattr(props, "source_emitters", ()):
        try:
            if not item.enabled or item.obj is None:
                continue
            if item.obj.get("nexus_modifier_type") != "NX_EMITTER":
                continue
        except ReferenceError:
            continue
        if _is_generator_excluded_on_emitter(item.obj, generator_obj):
            continue
        idx = pipeline_manager.get_emitter_index(scene, item.obj)
        if idx is None or idx < 0 or idx >= _MAX_FILTERED_EMITTERS:
            continue
        mask |= 1 << int(idx)
    return mask


class NEXUS_UL_generator_layers(bpy.types.UIList):
    """Layer-list row with an inline spawn-chance slider."""

    bl_idname = "NEXUS_UL_generator_layers"

    def draw_item(
        self,
        _context,
        layout,
        _data,
        item,
        _icon,
        _active_data,
        _active_propname,
        index,
    ):
        from ..icons import get_icon
        from ..modifiers import MODIFIER_REGISTRY
        from ..ui.nodetree.registry import (
            _get_enable_icons,
            _nodetree_data_paths,
            _nodetree_registry,
            _nodetree_tree_types,
        )

        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)

            # Object name + icon (mirrors NEXUS_UL_nodetree._draw_object_item).
            if item.obj:
                icon_value = layout.icon(item.obj)
                mod_type = item.obj.get("nexus_modifier_type")
                if mod_type:
                    mod_class = MODIFIER_REGISTRY.get(mod_type)
                    icon_name = getattr(mod_class, "icon_name", None) if mod_class else None
                    if icon_name:
                        nx_icon = get_icon(icon_name)
                        if nx_icon > 0:
                            icon_value = nx_icon
                row.prop(item.obj, "name", text="", emboss=False, icon_value=icon_value)
            else:
                row.label(text="<Empty>", icon="ERROR")

            slider = row.row(align=True)
            slider.ui_units_x = 5.0
            slider.prop(item, "spawn_chance", text="", slider=True)

            lock_sub = row.row(align=True)
            lock_sub.ui_units_x = 1.0
            lock_sub.prop(
                item,
                "locked",
                text="",
                icon="LOCKED" if item.locked else "UNLOCKED",
                emboss=False,
            )

            data_path = _nodetree_data_paths.get(self.list_id, "")
            registry_entry = _nodetree_registry.get(self.list_id)
            list_prop = registry_entry["list_prop"] if registry_entry else self.list_id

            enable_sub = row.row(align=True)
            enable_sub.ui_units_x = 1.0
            enabled_icon, disabled_icon = _get_enable_icons(
                _nodetree_tree_types.get(self.list_id, "regular")
            )
            op = enable_sub.operator(
                "nexus.nodetree_toggle_enable",
                text="",
                icon_value=get_icon(enabled_icon) if item.enabled else get_icon(disabled_icon),
                emboss=False,
            )
            op.data_path = data_path
            op.list_prop = list_prop
            op.index = index
            op.prop_name = "enabled"

        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            if item.obj:
                layout.label(text="", icon_value=layout.icon(item.obj))
            else:
                layout.label(text="", icon="ERROR")


SPEC = ModifierPropertySpec(
    modifier_type="NX_GENERATOR",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="generator_layers",
            prop=CollectionProperty(name="Generator Layers", type=NexusGeneratorLayerItem),
            preset=False,
        ),
        PropertyDescriptor(
            name="generator_layers_index",
            prop=IntProperty(
                name="Active Layer Index",
                default=0,
                min=0,
                update=_on_layers_index_change,
            ),
            preset=False,
        ),
        PropertyDescriptor(
            name="source_emitters",
            prop=_source_emitters_props["source_emitters"],
            preset=False,
        ),
        PropertyDescriptor(
            name="source_emitters_index",
            prop=_source_emitters_props["source_emitters_index"],
            preset=False,
        ),
        PropertyDescriptor(
            name="source_emitters_drop_target",
            prop=_source_emitters_props.get("source_emitters_drop_target"),
            preset=False,
        ),
        PropertyDescriptor(
            name="display_mode",
            prop=EnumProperty(
                name="Display Mode",
                description=(
                    "Switch between the fast GPU-only viewport preview and real "
                    "Blender geometry"
                ),
                items=[
                    (
                        "PREVIEW",
                        "Preview",
                        (
                            "GPU-only viewport preview — not visible to "
                            "colliders, modifiers or render engines"
                        ),
                    ),
                    (
                        "GEOMETRY",
                        "Geometry",
                        (
                            "Materialise instances as real Blender geometry "
                            "(Instance-on-Points). Visible to colliders, "
                            "modifiers, and render engines"
                        ),
                    ),
                ],
                default="PREVIEW",
                update=_on_display_mode_change,
            ),
            no_sync=True,
        ),
    ),
    item_classes=(NexusGeneratorLayerItem, NexusGeneratorSourceEmitterItem),
)
