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

"""Generic Mapping tab: source/dest pickers, layer picker, UIList row, and the
draw helpers used by NEXUS_PT_modifier_main.draw_mapping_section.

Public surface (imported elsewhere):
    - ``draw_mapping_section(layout, props)``
    - ``classes`` — UIList + Menu classes for register/unregister

Theron-side glue (sync, ABI wrappers) lives in libs/mapping_metadata.py and
handlers/pipeline.py — nothing UI-related leaks there.
"""

import bpy

from ..icons import get_icon

# Basic sources available to every modifier's Mapping tab, alongside each modifier's own
# _mapTo list
BASIC_MAPPING_SOURCES = [
    (11, "Age", "nx_datamap_age"),
    (6, "Color (Brightness)", "nx_datamap_color_brightness"),
    (67, "Color R", "nx_datamap_color_r"),
    (68, "Color G", "nx_datamap_color_g"),
    (69, "Color B", "nx_datamap_color_b"),
    (24, "Distance", "nx_datamap_distance"),
    (66, "Document Time", "nx_datamap_document_time"),
    (23, "Fluid Density", "nx_datamap_fluid_density"),
    (34, "Fuel", "nx_datamap_fuel"),
    (20, "Granular", "nx_datamap_granular"),
    (13, "Group", "nx_datamap_group"),
    (14, "ID", "nx_datamap_id"),
    (21, "Life", "nx_datamap_life"),
    (9, "Mass", "nx_datamap_mass"),
    (12, "Radius", "nx_datamap_radius"),
    (16, "Scale", "nx_datamap_scale"),
    (32, "Smoke", "nx_datamap_smoke"),
    (64, "Speed", "nx_datamap_speed"),
    (33, "Temperature", "nx_datamap_temperature"),
    (22, "Vertex Weight", "nx_datamap_vertex_weight"),
]

_SOURCE_ICON_KEYS = {sid: key for sid, _label, key in BASIC_MAPPING_SOURCES if key}


def source_icon_value(source_id: int) -> int:
    """Return a Blender icon_value for a particle-data source, or 0 if none is registered."""
    key = _SOURCE_ICON_KEYS.get(source_id)
    if not key:
        return 0
    return get_icon(key)


def _find_param_info(params, needle_id):
    for info in params:
        if info.param == needle_id:
            return info
    return None


def _find_source_info(metadata, source_id):
    # modifier-specific sources first so they can override a shared basic-source label
    info = _find_param_info(metadata.map_to, source_id)
    if info is not None:
        return info
    from ..libs.theron import MappingParamInfo

    for sid, label, _icon in BASIC_MAPPING_SOURCES:
        if sid == source_id:
            return MappingParamInfo(param=sid, group=0, name=label)
    return None


# mod_type -> layer CollectionProperty attr; same string is the nodetree registry's menu_id
MAPPING_LAYER_COLLECTIONS = {
    "NX_TURBULENCE": "turbulence_layers",
    "NX_SCALE": "scale_layers",
    "NX_SPEED": "speed_layers",
    "NX_SPIN": "spin_layers",
    "NX_DIRECTION": "direction_layers",
    "NX_LIMIT": "limit_layers",
    "NX_COLOR": "color_layers",
}


def _enum_display_label(item, prop_name: str) -> str:
    """Resolve an EnumProperty's current value to its display label, "" on failure."""
    try:
        rna_prop = item.bl_rna.properties.get(prop_name)
        if rna_prop is None:
            return ""
        key = getattr(item, prop_name, None)
        if key is None:
            return ""
        enum_item = rna_prop.enum_items.get(key)
        return enum_item.name if enum_item else ""
    except (AttributeError, KeyError, TypeError, RuntimeError):
        return ""


def blender_layer_icon(obj, layer_id: int) -> int:
    """Layer's `item_type` icon_value via the nodetree registry, 0 if unavailable.
    bl_rna's enum icon doesn't survive callback-driven enums, so we go through the registry."""
    if obj is None or layer_id < 0:
        return 0
    mod_type = obj.get("nexus_modifier_type")
    attr = MAPPING_LAYER_COLLECTIONS.get(mod_type)
    if attr is None:
        return 0
    coll = getattr(obj.nexus_modifier, attr, None)
    if coll is None or layer_id >= len(coll):
        return 0
    item_type = getattr(coll[layer_id], "item_type", None)
    if not item_type:
        return 0
    from ..ui.nodetree.registry import _lookup_type_info

    info = _lookup_type_info(item_type, attr)
    if not info:
        return 0
    _, icon = info
    return icon if isinstance(icon, int) and icon > 0 else 0


def blender_layer_labels(obj) -> list[str]:
    """One label per layer in tree order; waterfall: item.name -> item_type label -> "Layer N"."""
    if obj is None:
        return []
    mod_type = obj.get("nexus_modifier_type")
    attr = MAPPING_LAYER_COLLECTIONS.get(mod_type)
    if attr is None:
        return []
    coll = getattr(obj.nexus_modifier, attr, None)
    if coll is None:
        return []

    labels: list[str] = []
    for idx, item in enumerate(coll):
        name = getattr(item, "name", "") or ""
        if not name:
            name = _enum_display_label(item, "item_type")
        if not name:
            raw = getattr(item, "item_type", "")
            name = str(raw).replace("_", " ").title() if raw else ""
        if not name:
            name = f"Layer {idx + 1}"
        labels.append(name)
    return labels


class NEXUS_UL_mapping(bpy.types.UIList):
    """[✓] [src] Source → [layer_icon] Layer · Param   0–2s · 100% · clamp"""

    _CLAMP_GLYPHS = {"CLAMP": "│", "CYCLE": "↻", "CONTINUE": "↦"}

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        from ..handlers.pipeline import get_nexus_obj_handle
        from ..libs.mapping_metadata import get_mapping_metadata, resolve_label
        from ..libs.nexus_time import get_prop_time_mode
        from ..properties.mapping import is_time_source

        obj = context.object
        mod_type = obj.get("nexus_modifier_type") if obj else None
        scene = context.scene
        handle = get_nexus_obj_handle(scene, obj) if scene and mod_type else 0
        metadata = get_mapping_metadata(mod_type, handle or 0) if mod_type else None

        source_label = "(no source)"
        if metadata:
            source_info = _find_source_info(metadata, item.source_param)
            if source_info:
                source_label = resolve_label(source_info, metadata)
            elif item.source_param != 0:
                source_label = f"id_{item.source_param}"

        dest_label = "(select parameter)"
        if metadata and item.dest_param != 0:
            dest_info = _find_param_info(metadata.dest_params, item.dest_param)
            if dest_info:
                dest_label = resolve_label(dest_info, metadata)
            else:
                dest_label = f"id_{item.dest_param}"

        layer_labels = blender_layer_labels(obj)
        if layer_labels:
            if 0 <= item.layer_id < len(layer_labels):
                dest_label = f"{layer_labels[item.layer_id]} · {dest_label}"
            else:
                dest_label = f"? · {dest_label}"

        if is_time_source(item.source_param):
            min_mode = get_prop_time_mode(item, "range_min_time")
            max_mode = get_prop_time_mode(item, "range_max_time")
            min_unit = "f" if min_mode == "FRAMES" else "s"
            max_unit = "f" if max_mode == "FRAMES" else "s"
            if min_unit == max_unit:
                range_str = f"{item.range_min_time:g}–{item.range_max_time:g}{max_unit}"
            else:
                range_str = f"{item.range_min_time:g}{min_unit}–{item.range_max_time:g}{max_unit}"
        else:
            range_str = f"{item.range_min:g}–{item.range_max:g}"

        weight_str = f"{int(round(item.weight))}%"
        clamp_glyph = self._CLAMP_GLYPHS.get(item.clamp, "")

        row = layout.row(align=True)
        row.active = item.enabled

        toggle = row.row(align=True)
        toggle.ui_units_x = 1.0
        enable_icon = get_icon("nx_enable" if item.enabled else "nx_disable")
        op = toggle.operator(
            "nexus.nodetree_toggle_enable",
            text="",
            icon_value=enable_icon,
            emboss=False,
        )
        op.data_path = ""
        op.list_prop = "mappings"
        op.index = index
        op.prop_name = "enabled"

        # alignment="LEFT" packs source/dest tight (no auto-50/50 gap)
        body = row.row(align=True)
        body.alignment = "LEFT"

        src_icon = source_icon_value(item.source_param)
        if src_icon:
            body.label(text=f"{source_label}  →", icon_value=src_icon)
        else:
            body.label(text=f"{source_label}  →", icon="PARTICLE_DATA")

        layer_icon = blender_layer_icon(obj, item.layer_id) if layer_labels else 0
        tail_parts = [dest_label, "·", weight_str, "·", range_str]
        if clamp_glyph:
            tail_parts.append(clamp_glyph)
        tail = "  ".join(tail_parts)
        if layer_icon:
            body.label(text=tail, icon_value=layer_icon)
        else:
            body.label(text=tail)


def _draw_source_menu_items(layout, metadata, operator_id, param_attr="source_param"):
    """Shared body for the 'pick a source' popup. Used by Add and Set-source menus."""
    from ..libs.mapping_metadata import resolve_group_label, resolve_label

    layout.label(text="Particle Data")
    for sid, label, icon_key in BASIC_MAPPING_SOURCES:
        icon_value = get_icon(icon_key) if icon_key else 0
        if icon_value:
            op = layout.operator(operator_id, text=label, icon_value=icon_value)
        else:
            op = layout.operator(operator_id, text="    " + label)
        setattr(op, param_attr, sid)

    if not metadata or not metadata.map_to:
        return

    grouped: dict[int, list] = {}
    for p in metadata.map_to:
        grouped.setdefault(p.group, []).append(p)

    if metadata.map_to_groups:
        for g_idx, group_name in enumerate(metadata.map_to_groups):
            params = grouped.get(g_idx, [])
            if not params:
                continue
            layout.separator()
            layout.label(text=resolve_group_label(group_name, g_idx))
            for p in params:
                op = layout.operator(operator_id, text="    " + resolve_label(p, metadata))
                setattr(op, param_attr, p.param)
    else:
        layout.separator()
        for p in metadata.map_to:
            op = layout.operator(operator_id, text="    " + resolve_label(p, metadata))
            setattr(op, param_attr, p.param)


class NEXUS_MT_mapping_add(bpy.types.Menu):
    """Add a new mapping layer. Pick the particle-data source the layer is keyed by."""

    bl_idname = "NEXUS_MT_mapping_add"
    bl_label = "Add Mapping Layer"

    def draw(self, context):
        from ..handlers.pipeline import get_nexus_obj_handle
        from ..libs.mapping_metadata import get_mapping_metadata

        layout = self.layout
        obj = context.object
        if obj is None or not obj.get("nexus_modifier_type"):
            layout.label(text="No active modifier")
            return

        scene = context.scene
        mod_type = obj["nexus_modifier_type"]
        handle = get_nexus_obj_handle(scene, obj) if scene else 0
        metadata = get_mapping_metadata(mod_type, handle or 0)

        _draw_source_menu_items(
            layout, metadata, "nexus.mapping_add_entry", param_attr="source_param"
        )


class NEXUS_MT_mapping_set_source(bpy.types.Menu):
    """Change the particle-data source feeding the active mapping layer."""

    bl_idname = "NEXUS_MT_mapping_set_source"
    bl_label = "Source"

    def draw(self, context):
        from ..handlers.pipeline import get_nexus_obj_handle
        from ..libs.mapping_metadata import get_mapping_metadata

        layout = self.layout
        obj = context.object
        if obj is None or not obj.get("nexus_modifier_type"):
            layout.label(text="No active modifier")
            return

        scene = context.scene
        mod_type = obj["nexus_modifier_type"]
        handle = get_nexus_obj_handle(scene, obj) if scene else 0
        metadata = get_mapping_metadata(mod_type, handle or 0)

        _draw_source_menu_items(
            layout, metadata, "nexus.mapping_set_source", param_attr="source_param"
        )


class NEXUS_MT_mapping_set_layer(bpy.types.Menu):
    """Pick which runtime layer of a layered modifier this mapping applies to.

    Labels come from the Blender-side layer collection (item.name or its item_type enum
    display label), which mirrors the names the user sees in the modifier's own layer list.
    Layered modifiers always require a specific layer per entry -- there's no "all layers".
    """

    bl_idname = "NEXUS_MT_mapping_set_layer"
    bl_label = "Layer"

    def draw(self, context):
        layout = self.layout
        obj = context.object
        labels = blender_layer_labels(obj)
        if not labels:
            layout.label(text="No layers")
            return
        for i, label in enumerate(labels):
            icon_value = blender_layer_icon(obj, i)
            if icon_value:
                op = layout.operator("nexus.mapping_set_layer", text=label, icon_value=icon_value)
            else:
                op = layout.operator("nexus.mapping_set_layer", text=label)
            op.layer_id = i


class NEXUS_MT_mapping_set_dest(bpy.types.Menu):
    """Pick which modifier parameter this layer modulates. Uses _mapParams + _groupNames."""

    bl_idname = "NEXUS_MT_mapping_set_dest"
    bl_label = "Destination"

    def draw(self, context):
        from ..handlers.pipeline import get_nexus_obj_handle
        from ..libs.mapping_metadata import (
            get_mapping_metadata,
            resolve_group_label,
            resolve_label,
        )

        layout = self.layout
        obj = context.object
        if obj is None or not obj.get("nexus_modifier_type"):
            layout.label(text="No active modifier")
            return

        scene = context.scene
        mod_type = obj["nexus_modifier_type"]
        handle = get_nexus_obj_handle(scene, obj) if scene else 0
        metadata = get_mapping_metadata(mod_type, handle or 0)
        if not metadata.dest_params:
            layout.label(text="No mappable parameters")
            return

        grouped: dict[int, list] = {}
        for p in metadata.dest_params:
            grouped.setdefault(p.group, []).append(p)

        group_count = len(metadata.groups)
        ungrouped = []
        for idx, plist in grouped.items():
            if idx < 0 or idx >= group_count:
                ungrouped.extend(plist)

        for p in ungrouped:
            op = layout.operator("nexus.mapping_set_dest", text=resolve_label(p, metadata))
            op.dest_param = p.param

        for g_idx, group_name in enumerate(metadata.groups):
            params = grouped.get(g_idx, [])
            if not params:
                continue
            layout.separator()
            layout.label(text=resolve_group_label(group_name, g_idx))
            for p in params:
                op = layout.operator(
                    "nexus.mapping_set_dest", text="    " + resolve_label(p, metadata)
                )
                op.dest_param = p.param


def draw_mapping_section(layout, props):
    from ..handlers.pipeline import get_nexus_obj_handle
    from ..libs.mapping_metadata import get_mapping_metadata, resolve_label

    obj = bpy.context.object
    if obj is None or not obj.get("nexus_modifier_type"):
        layout.label(text="No active modifier", icon="ERROR")
        return

    mod_type = obj["nexus_modifier_type"]
    scene = bpy.context.scene
    handle = get_nexus_obj_handle(scene, obj) if scene is not None else None
    metadata = get_mapping_metadata(mod_type, handle or 0)

    if not metadata.dest_params:
        layout.label(text="No mappable parameters", icon="INFO")
        return

    header = layout.row(align=True)
    header.label(text="Mapping Layers", icon="DRIVER")
    header.menu("NEXUS_MT_mapping_add", text="", icon="ADD")

    body = layout.row()
    body.template_list(
        "NEXUS_UL_mapping",
        "",
        props,
        "mappings",
        props,
        "mappings_index",
        rows=4,
    )
    side = body.column(align=True)
    side.operator("nexus.mapping_remove_entry", text="", icon="REMOVE")
    side.separator()
    up = side.operator("nexus.mapping_move_entry", text="", icon="TRIA_UP")
    up.direction = "UP"
    dn = side.operator("nexus.mapping_move_entry", text="", icon="TRIA_DOWN")
    dn.direction = "DOWN"

    idx = props.mappings_index
    if not (0 <= idx < len(props.mappings)):
        return

    entry = props.mappings[idx]
    source_info = _find_source_info(metadata, entry.source_param)
    dest_info = _find_param_info(metadata.dest_params, entry.dest_param)
    layer_labels = blender_layer_labels(obj)

    layout.separator()
    detail = layout.box()

    title_src = resolve_label(source_info, metadata) if source_info else "?"
    title_dst = resolve_label(dest_info, metadata) if dest_info else "?"
    if layer_labels and 0 <= entry.layer_id < len(layer_labels):
        title_dst = f"{layer_labels[entry.layer_id]} · {title_dst}"
    title = detail.row(align=True)
    title.label(text=f"{title_src}  →  {title_dst}", icon="DRIVER")

    route = detail.column(align=True)
    route.use_property_split = True

    source_text = (
        resolve_label(source_info, metadata) if source_info else "Select Particle Data..."
    )
    detail_src_icon = source_icon_value(entry.source_param) if source_info else 0
    if detail_src_icon:
        route.menu("NEXUS_MT_mapping_set_source", text=source_text, icon_value=detail_src_icon)
    else:
        route.menu("NEXUS_MT_mapping_set_source", text=source_text, icon="PARTICLE_DATA")

    if layer_labels:
        if 0 <= entry.layer_id < len(layer_labels):
            layer_text = layer_labels[entry.layer_id]
            layer_btn_icon = blender_layer_icon(obj, entry.layer_id)
        else:
            layer_text = "Select Layer..."
            layer_btn_icon = 0
        if layer_btn_icon:
            route.menu("NEXUS_MT_mapping_set_layer", text=layer_text, icon_value=layer_btn_icon)
        else:
            route.menu("NEXUS_MT_mapping_set_layer", text=layer_text, icon="RENDERLAYERS")

    dest_text = (
        resolve_label(dest_info, metadata)
        if dest_info
        else ("Select Parameter..." if entry.dest_param == 0 else f"id_{entry.dest_param}")
    )
    route.menu("NEXUS_MT_mapping_set_dest", text=dest_text, icon="FORWARD")

    range_col = detail.column(align=True)
    range_col.use_property_split = True
    range_col.separator()

    from ..libs.nexus_time import draw_time_prop
    from ..properties.mapping import is_time_source

    if is_time_source(entry.source_param):
        draw_time_prop(range_col, entry, "range_min_time")
        draw_time_prop(range_col, entry, "range_max_time")
    else:
        range_col.prop(entry, "range_min")
        range_col.prop(entry, "range_max")
    range_col.prop(entry, "weight")

    shape = detail.column(align=True)
    shape.use_property_split = True
    shape.separator()
    shape.prop(entry, "clamp")
    if entry.curve_id:
        from ..utils.curve import NexusCurve

        slot = f"mapping_curve_{entry.curve_id}"
        NexusCurve(obj, slot).draw_ui(shape, "Mapping")


classes = [
    NEXUS_UL_mapping,
    NEXUS_MT_mapping_add,
    NEXUS_MT_mapping_set_source,
    NEXUS_MT_mapping_set_dest,
    NEXUS_MT_mapping_set_layer,
]
