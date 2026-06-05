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
from bpy.props import StringProperty

# ---------------------------------------------------------------------------
# Preview collection management
# ---------------------------------------------------------------------------

_preview_collections = {}


def get_gradient_preview_collection():
    return _preview_collections.get("gradient_presets")


def register_gradient_previews(addon_package=None):
    import bpy.utils.previews

    from ..utils.gradient_presets import (
        generate_preset_previews,
        generate_user_preset_previews,
        init_user_presets,
    )

    pcoll = bpy.utils.previews.new()
    generate_preset_previews(pcoll)

    if addon_package is not None:
        init_user_presets(addon_package)
        generate_user_preset_previews(pcoll)

    _preview_collections["gradient_presets"] = pcoll


def unregister_gradient_previews():
    import bpy.utils.previews

    for pcoll in _preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    _preview_collections.clear()


def _ensure_gradient_ownership_for_object(obj):
    from ..modifiers import get_modifier_class
    from ..utils.gradient import ensure_gradient_ownership

    mod_type = obj.get("nexus_modifier_type")
    if mod_type is None:
        return

    mod_cls = get_modifier_class(mod_type)
    if mod_cls is None:
        return

    ensure_gradient_ownership(obj, mod_cls.get_gradient_specs() or None)


def _resolve_gradient_node(gradient_id: str, object_name: str, slot_name: str):
    from ..utils.gradient import get_gradient_node_by_id, get_gradient_node_for_slot

    if object_name:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            return None, f"Object not found: {object_name}"
        _ensure_gradient_ownership_for_object(obj)
        node = get_gradient_node_for_slot(obj, slot_name)
        if node is not None:
            return node, None
        return None, f"Gradient slot not found on object '{object_name}': {slot_name}"

    if gradient_id:
        node = get_gradient_node_by_id(gradient_id, slot_name)
        if node is not None:
            return node, None

    return None, f"Gradient slot not found: {slot_name}"


def _resolve_gradient_id(gradient_id: str, object_name: str) -> str:
    from ..utils.gradient import _get_gradient_id

    if object_name:
        obj = bpy.data.objects.get(object_name)
        if obj is not None:
            resolved = _get_gradient_id(obj) or ""
            if resolved:
                return resolved

    return gradient_id or ""


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------


class NEXUS_OT_gradient_preset_apply(bpy.types.Operator):
    """Apply a gradient preset to the selected color ramp"""

    bl_idname = "nexus.gradient_preset_apply"
    bl_label = "Apply Gradient Preset"
    bl_description = "Replace the current gradient with this preset"
    bl_options = {"REGISTER", "UNDO"}

    preset_id: StringProperty(name="Preset ID", default="")
    gradient_id: StringProperty(name="Gradient ID", default="")
    object_name: StringProperty(name="Object Name", default="", options={"HIDDEN"})
    slot_name: StringProperty(name="Slot Name", default="")

    def execute(self, context):
        del context
        from ..utils.gradient_presets import get_preset

        preset = get_preset(self.preset_id)
        if preset is None:
            self.report({"ERROR"}, f"Unknown gradient preset: {self.preset_id}")
            return {"CANCELLED"}

        node, error = _resolve_gradient_node(self.gradient_id, self.object_name, self.slot_name)
        if node is None:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        color_ramp = node.color_ramp
        sorted_stops = sorted(preset.stops, key=lambda s: s[0])

        while len(color_ramp.elements) > 2:
            color_ramp.elements.remove(color_ramp.elements[-1])

        color_ramp.elements[0].position = sorted_stops[0][0]
        color_ramp.elements[0].color = sorted_stops[0][1]
        color_ramp.elements[1].position = sorted_stops[-1][0]
        color_ramp.elements[1].color = sorted_stops[-1][1]

        for position, color in sorted_stops[1:-1]:
            elem = color_ramp.elements.new(position)
            elem.color = color

        color_ramp.interpolation = preset.interpolation

        self.report({"INFO"}, f"Applied gradient preset: {preset.name}")
        return {"FINISHED"}


class NEXUS_OT_gradient_preset_save(bpy.types.Operator):
    """Save the current gradient as a user preset"""

    bl_idname = "nexus.gradient_preset_save"
    bl_label = "Save Gradient Preset"
    bl_description = "Save the current gradient as a reusable preset"
    bl_options = {"REGISTER", "INTERNAL"}

    gradient_id: StringProperty(name="Gradient ID", default="")
    object_name: StringProperty(name="Object Name", default="", options={"HIDDEN"})
    slot_name: StringProperty(name="Slot Name", default="")
    preset_name: StringProperty(name="Name", default="User Preset")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "preset_name")

    def execute(self, context):
        del context
        from ..utils.gradient_presets import (
            _generate_single_preview,
            add_user_preset,
        )

        node, error = _resolve_gradient_node(self.gradient_id, self.object_name, self.slot_name)
        if node is None:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        color_ramp = node.color_ramp
        stops = [(elem.position, tuple(elem.color)) for elem in color_ramp.elements]
        interpolation = color_ramp.interpolation

        preset_id = add_user_preset(self.preset_name, stops, interpolation)

        pcoll = get_gradient_preview_collection()
        if pcoll is not None:
            _generate_single_preview(pcoll, preset_id, stops)

        self.report({"INFO"}, f"Saved gradient preset: {self.preset_name}")
        return {"FINISHED"}


class NEXUS_OT_gradient_preset_rename(bpy.types.Operator):
    """Rename a user gradient preset"""

    bl_idname = "nexus.gradient_preset_rename"
    bl_label = "Rename Gradient Preset"
    bl_description = "Rename this user preset"
    bl_options = {"REGISTER", "INTERNAL"}

    preset_id: StringProperty(name="Preset ID", default="")
    new_name: StringProperty(name="Name", default="")

    def invoke(self, context, event):
        from ..utils.gradient_presets import get_preset

        preset = get_preset(self.preset_id)
        if preset is not None:
            self.new_name = preset.name
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "new_name")

    def execute(self, context):
        from ..utils.gradient_presets import rename_user_preset

        if not self.new_name.strip():
            self.report({"WARNING"}, "Preset name cannot be empty")
            return {"CANCELLED"}

        if rename_user_preset(self.preset_id, self.new_name):
            self.report({"INFO"}, f"Renamed preset to: {self.new_name}")
        else:
            self.report({"WARNING"}, "User preset not found")
        return {"FINISHED"}


class NEXUS_OT_gradient_preset_delete(bpy.types.Operator):
    """Delete a user gradient preset"""

    bl_idname = "nexus.gradient_preset_delete"
    bl_label = "Delete Gradient Preset"
    bl_description = "Permanently delete this user preset"
    bl_options = {"REGISTER", "INTERNAL"}

    preset_id: StringProperty(name="Preset ID", default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        from ..utils.gradient_presets import remove_user_preset

        if remove_user_preset(self.preset_id):
            self.report({"INFO"}, "Deleted user preset")
        else:
            self.report({"WARNING"}, "User preset not found")
        return {"FINISHED"}


class NEXUS_OT_gradient_preset_popup(bpy.types.Operator):
    """Browse and apply gradient presets"""

    bl_idname = "nexus.gradient_preset_popup"
    bl_label = "INSYDIUM Gradient Presets"
    bl_description = "Browse and apply gradient presets"
    bl_options = {"INTERNAL"}

    gradient_id: StringProperty(name="Gradient ID", default="")
    object_name: StringProperty(name="Object Name", default="", options={"HIDDEN"})
    slot_name: StringProperty(name="Slot Name", default="")

    def invoke(self, context, event):
        context.window_manager.invoke_popup(self, width=450)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        from ..utils.gradient_presets import (
            GRADIENT_PRESET_CATEGORIES,
            get_presets_by_category,
            get_user_presets,
        )

        layout = self.layout
        pcoll = get_gradient_preview_collection()
        presets_by_cat = get_presets_by_category()
        user_presets = get_user_presets()
        resolved_gradient_id = _resolve_gradient_id(self.gradient_id, self.object_name)

        from ..icons import get_icon

        insydium_icon = get_icon("insydium")
        if insydium_icon:
            layout.label(text="INSYDIUM Gradient Presets", icon_value=insydium_icon)
        else:
            layout.label(text="INSYDIUM Gradient Presets", icon="COLOR")
        layout.separator(type="LINE")

        if user_presets:
            layout.label(text="User")
            for preset in user_presets:
                icon_value = 0
                if pcoll and preset.preset_id in pcoll:
                    icon_value = pcoll[preset.preset_id].icon_id
                row = layout.row(align=True)
                op = row.operator(
                    "nexus.gradient_preset_apply",
                    text=preset.name,
                    icon_value=icon_value,
                )
                op.preset_id = preset.preset_id
                op.gradient_id = resolved_gradient_id
                op.object_name = self.object_name
                op.slot_name = self.slot_name
                op = row.operator(
                    "nexus.gradient_preset_rename",
                    text="",
                    icon="GREASEPENCIL",
                )
                op.preset_id = preset.preset_id
                op = row.operator(
                    "nexus.gradient_preset_delete",
                    text="",
                    icon="X",
                )
                op.preset_id = preset.preset_id
            layout.separator(type="LINE")

        first = True
        for cat_key, cat_label in GRADIENT_PRESET_CATEGORIES.items():
            presets = presets_by_cat.get(cat_key, [])
            if not presets:
                continue

            if not first:
                layout.separator(type="LINE")
            first = False

            layout.label(text=cat_label)
            grid = layout.grid_flow(
                row_major=True,
                columns=2,
                even_columns=True,
                even_rows=True,
                align=False,
            )
            for preset in presets:
                icon_value = 0
                if pcoll and preset.preset_id in pcoll:
                    icon_value = pcoll[preset.preset_id].icon_id
                op = grid.operator(
                    "nexus.gradient_preset_apply",
                    text=preset.name,
                    icon_value=icon_value,
                )
                op.preset_id = preset.preset_id
                op.gradient_id = resolved_gradient_id
                op.object_name = self.object_name
                op.slot_name = self.slot_name

        layout.separator(type="LINE")
        op = layout.operator(
            "nexus.gradient_preset_save",
            text="Save Current Gradient",
            icon="ADD",
        )
        op.gradient_id = resolved_gradient_id
        op.object_name = self.object_name
        op.slot_name = self.slot_name


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

gradient_preset_classes = [
    NEXUS_OT_gradient_preset_apply,
    NEXUS_OT_gradient_preset_save,
    NEXUS_OT_gradient_preset_rename,
    NEXUS_OT_gradient_preset_delete,
    NEXUS_OT_gradient_preset_popup,
]
