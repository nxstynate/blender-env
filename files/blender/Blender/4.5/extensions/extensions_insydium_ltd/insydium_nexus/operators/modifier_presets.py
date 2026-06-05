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
from bpy.props import EnumProperty, StringProperty


def _get_category_items(self, context):
    from ..utils.modifier_presets import get_categories_for_type

    items = [("__NONE__", "Uncategorized", "Save without a category", "NONE", 0)]

    if context and context.object:
        mod_type = context.object.get("nexus_modifier_type")
        if mod_type:
            for i, cat in enumerate(sorted(get_categories_for_type(mod_type)), start=1):
                items.append((cat, cat, "", "FILE_FOLDER", i))

    items.append(("__NEW__", "New Category...", "Create a new category", "ADD", len(items)))
    return items


# ---------------------------------------------------------------------------
# Core preset operators
# ---------------------------------------------------------------------------


class NEXUS_OT_modifier_preset_apply(bpy.types.Operator):
    """Apply a modifier preset to the active NeXus object"""

    bl_idname = "nexus.modifier_preset_apply"
    bl_label = "Apply Modifier Preset"
    bl_description = "Replace the current modifier settings with this preset"
    bl_options = {"REGISTER", "UNDO"}

    preset_id: StringProperty(name="Preset ID", default="")

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and "nexus_modifier_type" in obj

    def execute(self, context):
        from ..utils.modifier_presets import apply_preset_data, get_preset

        preset = get_preset(self.preset_id)
        if preset is None:
            self.report({"ERROR"}, "Unknown preset")
            return {"CANCELLED"}

        obj = context.object
        if obj.get("nexus_modifier_type") != preset.modifier_type:
            self.report({"ERROR"}, "Preset type mismatch")
            return {"CANCELLED"}

        apply_preset_data(obj, preset.data, context=context)

        context.view_layer.depsgraph.update()
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        self.report({"INFO"}, f"Applied preset: {preset.name}")
        return {"FINISHED"}


class NEXUS_OT_modifier_preset_apply_default(bpy.types.Operator):
    """Reset all properties, curves, and gradients to factory defaults"""

    bl_idname = "nexus.modifier_preset_apply_default"
    bl_label = "Restore INSYDIUM Defaults"
    bl_description = "Reset all properties, curves, and gradients to factory defaults"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and "nexus_modifier_type" in obj

    def execute(self, context):
        from ..utils.modifier_presets import reset_to_defaults

        reset_to_defaults(context.object, context=context)

        context.view_layer.depsgraph.update()
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        self.report({"INFO"}, "Restored INSYDIUM defaults")
        return {"FINISHED"}


class NEXUS_OT_modifier_preset_save(bpy.types.Operator):
    """Save the current modifier settings as a user preset"""

    bl_idname = "nexus.modifier_preset_save"
    bl_label = "Save Modifier Preset"
    bl_description = "Save the current modifier settings as a reusable preset"
    bl_options = {"REGISTER", "INTERNAL"}

    preset_name: StringProperty(name="Name", default="User Preset")
    preset_category_enum: EnumProperty(
        name="Category",
        items=_get_category_items,
        default=0,
    )
    preset_category_new: StringProperty(name="New Category", default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "preset_name")
        layout.prop(self, "preset_category_enum")
        if self.preset_category_enum == "__NEW__":
            layout.prop(self, "preset_category_new")

    def execute(self, context):
        from ..utils.modifier_presets import add_user_preset, snapshot_modifier

        obj = context.object
        data = snapshot_modifier(obj)
        if data is None:
            self.report({"ERROR"}, "Could not snapshot modifier")
            return {"CANCELLED"}

        if self.preset_category_enum == "__NEW__":
            category = self.preset_category_new.strip()
        elif self.preset_category_enum == "__NONE__":
            category = ""
        else:
            category = self.preset_category_enum

        mod_type = obj.get("nexus_modifier_type")
        add_user_preset(self.preset_name, mod_type, category, data)
        self.report({"INFO"}, f"Saved preset: {self.preset_name}")
        return {"FINISHED"}


class NEXUS_OT_modifier_preset_rename(bpy.types.Operator):
    """Rename a user modifier preset"""

    bl_idname = "nexus.modifier_preset_rename"
    bl_label = "Rename Modifier Preset"
    bl_description = "Rename this user preset"
    bl_options = {"REGISTER", "INTERNAL"}

    preset_id: StringProperty(name="Preset ID", default="")
    new_name: StringProperty(name="Name", default="")

    def invoke(self, context, event):
        from ..utils.modifier_presets import get_preset

        preset = get_preset(self.preset_id)
        if preset is not None:
            self.new_name = preset.name
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "new_name")

    def execute(self, context):
        from ..utils.modifier_presets import rename_user_preset

        if not self.new_name.strip():
            self.report({"WARNING"}, "Preset name cannot be empty")
            return {"CANCELLED"}

        if rename_user_preset(self.preset_id, self.new_name):
            self.report({"INFO"}, f"Renamed preset to: {self.new_name}")
        else:
            self.report({"WARNING"}, "User preset not found")
        return {"FINISHED"}


class NEXUS_OT_modifier_preset_delete(bpy.types.Operator):
    """Delete a user modifier preset"""

    bl_idname = "nexus.modifier_preset_delete"
    bl_label = "Delete Modifier Preset"
    bl_description = "Permanently delete this user preset"
    bl_options = {"REGISTER", "INTERNAL"}

    preset_id: StringProperty(name="Preset ID", default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        from ..utils.modifier_presets import remove_user_preset

        if remove_user_preset(self.preset_id):
            self.report({"INFO"}, "Deleted user preset")
        else:
            self.report({"WARNING"}, "User preset not found")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Category management
# ---------------------------------------------------------------------------


class NEXUS_OT_modifier_preset_set_category(bpy.types.Operator):
    """Move a preset to a different category"""

    bl_idname = "nexus.modifier_preset_set_category"
    bl_label = "Set Preset Category"
    bl_description = "Move this preset to a different category"
    bl_options = {"REGISTER", "INTERNAL"}

    preset_id: StringProperty(name="Preset ID", default="")
    new_category: StringProperty(name="Category", default="")

    def execute(self, context):
        from ..utils.modifier_presets import update_preset_category

        category = "" if self.new_category == "__NONE__" else self.new_category
        if update_preset_category(self.preset_id, category):
            label = category if category else "Uncategorized"
            self.report({"INFO"}, f"Moved preset to: {label}")
        else:
            self.report({"WARNING"}, "User preset not found")
        return {"FINISHED"}


class NEXUS_OT_modifier_preset_new_category_dialog(bpy.types.Operator):
    """Move a preset to a new category"""

    bl_idname = "nexus.modifier_preset_new_category_dialog"
    bl_label = "New Category"
    bl_description = "Move this preset to a new category"
    bl_options = {"REGISTER", "INTERNAL"}

    preset_id: StringProperty(name="Preset ID", default="")
    new_category: StringProperty(name="Category Name", default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "new_category")

    def execute(self, context):
        from ..utils.modifier_presets import update_preset_category

        name = self.new_category.strip()
        if not name:
            self.report({"WARNING"}, "Category name cannot be empty")
            return {"CANCELLED"}

        if update_preset_category(self.preset_id, name):
            self.report({"INFO"}, f"Moved preset to: {name}")
        else:
            self.report({"WARNING"}, "User preset not found")
        return {"FINISHED"}


class NEXUS_OT_modifier_preset_rename_category(bpy.types.Operator):
    """Rename a category across all presets"""

    bl_idname = "nexus.modifier_preset_rename_category"
    bl_label = "Rename Category"
    bl_description = "Rename this category for all presets that use it"
    bl_options = {"REGISTER", "INTERNAL"}

    modifier_type: StringProperty(default="")
    old_category: StringProperty(default="")
    new_category: StringProperty(name="Name", default="")

    def invoke(self, context, event):
        self.new_category = self.old_category
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "new_category")

    def execute(self, context):
        from ..utils.modifier_presets import get_categories_for_type, rename_category

        name = self.new_category.strip()
        if not name:
            self.report({"WARNING"}, "Category name cannot be empty")
            return {"CANCELLED"}
        if name == self.old_category:
            return {"FINISHED"}

        existing = get_categories_for_type(self.modifier_type)
        if name in existing:
            self.report({"WARNING"}, f"Category '{name}' already exists")
            return {"CANCELLED"}

        count = rename_category(self.modifier_type, self.old_category, name)
        if count:
            self.report({"INFO"}, f"Renamed category to '{name}' ({count} presets)")
        else:
            self.report({"INFO"}, f"Renamed empty category to '{name}'")
        return {"FINISHED"}


class NEXUS_OT_modifier_preset_create_category(bpy.types.Operator):
    """Create a new empty category for organising presets"""

    bl_idname = "nexus.modifier_preset_create_category"
    bl_label = "New Category"
    bl_options = {"REGISTER", "INTERNAL"}

    modifier_type: StringProperty(default="")
    category_name: StringProperty(name="Name", default="New Category")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "category_name")

    def execute(self, context):
        from ..utils.modifier_presets import create_category

        name = self.category_name.strip()
        if not name:
            self.report({"WARNING"}, "Category name cannot be empty")
            return {"CANCELLED"}

        if create_category(self.modifier_type, name):
            self.report({"INFO"}, f"Created category: {name}")
        else:
            self.report({"WARNING"}, f"Category '{name}' already exists")
        return {"FINISHED"}


class NEXUS_OT_modifier_preset_delete_category(bpy.types.Operator):
    """Delete a category and move its presets to Uncategorized"""

    bl_idname = "nexus.modifier_preset_delete_category"
    bl_label = "Delete Category"
    bl_description = "Delete this category (presets move to Uncategorized)"
    bl_options = {"REGISTER", "INTERNAL"}

    modifier_type: StringProperty(default="")
    category_name: StringProperty(default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        from ..utils.modifier_presets import delete_category

        count = delete_category(self.modifier_type, self.category_name)
        if count:
            self.report({"INFO"}, f"Deleted category, {count} presets moved to Uncategorized")
        else:
            self.report({"INFO"}, "Deleted empty category")
        return {"FINISHED"}


class NEXUS_OT_modifier_preset_show_category_menu(bpy.types.Operator):
    """Open the category picker menu for a preset"""

    bl_idname = "nexus.modifier_preset_show_category_menu"
    bl_label = "Move to Category"
    bl_description = "Change this preset's category"
    bl_options = {"INTERNAL"}

    preset_id: StringProperty(name="Preset ID", default="")
    modifier_type: StringProperty(name="Modifier Type", default="")

    def execute(self, context):
        wm = context.window_manager
        wm.nexus_preset_move_id = self.preset_id
        wm.nexus_preset_move_modtype = self.modifier_type
        bpy.ops.wm.call_menu(name="NEXUS_MT_modifier_preset_category")
        return {"FINISHED"}


class NEXUS_MT_modifier_preset_category(bpy.types.Menu):
    bl_idname = "NEXUS_MT_modifier_preset_category"
    bl_label = "Move to Category"

    def draw(self, context):
        from ..utils.modifier_presets import (
            get_categories_for_type,
            get_preset,
        )

        layout = self.layout
        wm = context.window_manager
        preset_id = wm.nexus_preset_move_id
        mod_type = wm.nexus_preset_move_modtype

        preset = get_preset(preset_id)
        current_cat = preset.category if preset else ""

        icon = "RADIOBUT_ON" if not current_cat else "RADIOBUT_OFF"
        op = layout.operator(
            "nexus.modifier_preset_set_category",
            text="Uncategorized",
            icon=icon,
        )
        op.preset_id = preset_id
        op.new_category = "__NONE__"

        categories = sorted(get_categories_for_type(mod_type))
        if categories:
            layout.separator()
            for cat in categories:
                icon = "RADIOBUT_ON" if cat == current_cat else "RADIOBUT_OFF"
                op = layout.operator(
                    "nexus.modifier_preset_set_category",
                    text=cat,
                    icon=icon,
                )
                op.preset_id = preset_id
                op.new_category = cat

        layout.separator()
        op = layout.operator(
            "nexus.modifier_preset_new_category_dialog",
            text="New Category...",
            icon="ADD",
        )
        op.preset_id = preset_id


# ---------------------------------------------------------------------------
# Popup browser
# ---------------------------------------------------------------------------


class NEXUS_OT_modifier_preset_popup(bpy.types.Operator):
    """Browse and apply modifier presets"""

    bl_idname = "nexus.modifier_preset_popup"
    bl_label = "Modifier Presets"
    bl_description = "Browse and apply modifier presets"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        context.window_manager.invoke_popup(self, width=340)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        from ..icons import get_icon
        from ..modifiers import MODIFIER_REGISTRY
        from ..utils.modifier_presets import (
            get_categories_for_type,
            get_presets_for_type,
        )

        layout = self.layout
        obj = context.object
        if obj is None:
            return
        mod_type = obj.get("nexus_modifier_type")
        if mod_type is None:
            return

        mod_class = MODIFIER_REGISTRY.get(mod_type)

        layout.separator(factor=0.3)

        header = layout.row()
        header.scale_y = 1.3
        insydium_icon = get_icon("insydium")
        header_text = (
            f"NeXus {mod_class.object_label} Presets" if mod_class else "NeXus Modifier Presets"
        )
        if insydium_icon:
            header.label(text=header_text, icon_value=insydium_icon)
        else:
            header.label(text=header_text, icon="PRESET")

        layout.separator(factor=0.5)

        box = layout.box()
        default_row = box.row(align=True)
        default_row.scale_y = 1.2
        nexus_icon = get_icon("nexus")
        if nexus_icon:
            default_row.operator(
                "nexus.modifier_preset_apply_default",
                text="INSYDIUM Default",
                icon_value=nexus_icon,
            )
        else:
            default_row.operator(
                "nexus.modifier_preset_apply_default",
                text="INSYDIUM Default",
                icon="LOOP_BACK",
            )

        layout.separator(factor=0.8)

        presets = get_presets_for_type(mod_type)
        all_categories = sorted(get_categories_for_type(mod_type))

        preset_by_cat = {}
        uncategorized = []
        for p in presets:
            if p.category:
                preset_by_cat.setdefault(p.category, []).append(p)
            else:
                uncategorized.append(p)

        has_content = bool(presets) or bool(all_categories)

        if has_content:
            if uncategorized:
                lbl = layout.row()
                lbl.active = False
                lbl.label(text="User Presets")
                for preset in uncategorized:
                    self._draw_preset_row(layout, preset, mod_type)

            for cat_name in all_categories:
                layout.separator(factor=0.5)

                cat_header = layout.row(align=True)
                cat_header.scale_y = 1.1

                cat_header.label(text=cat_name, icon="FILE_FOLDER")

                sub = cat_header.row(align=True)
                sub.alignment = "RIGHT"
                sub.emboss = "NONE"
                op = sub.operator(
                    "nexus.modifier_preset_rename_category",
                    text="",
                    icon="GREASEPENCIL",
                )
                op.modifier_type = mod_type
                op.old_category = cat_name

                del_sub = sub.row(align=True)
                del_sub.alert = True
                op = del_sub.operator(
                    "nexus.modifier_preset_delete_category",
                    text="",
                    icon="X",
                )
                op.modifier_type = mod_type
                op.category_name = cat_name

                for preset in preset_by_cat.get(cat_name, []):
                    self._draw_preset_row(layout, preset, mod_type)

            layout.separator(factor=0.5)
        else:
            empty = layout.row()
            empty.active = False
            empty.alignment = "CENTER"
            empty.label(text="No saved presets")
            layout.separator(factor=0.5)

        save_row = layout.row()
        save_row.scale_y = 1.3
        save_row.operator(
            "nexus.modifier_preset_save",
            text="Save Current Settings",
            icon="ADD",
        )

        cat_row = layout.row()
        op = cat_row.operator(
            "nexus.modifier_preset_create_category",
            text="New Category...",
            icon="FILE_FOLDER",
        )
        op.modifier_type = mod_type

        layout.separator(factor=0.3)

    def _draw_preset_row(self, layout, preset, mod_type):
        row = layout.row(align=True)

        op = row.operator("nexus.modifier_preset_apply", text=preset.name)
        op.preset_id = preset.preset_id

        actions = row.row(align=True)
        actions.emboss = "NONE"

        op = actions.operator(
            "nexus.modifier_preset_show_category_menu",
            text="",
            icon="FILE_FOLDER",
        )
        op.preset_id = preset.preset_id
        op.modifier_type = mod_type

        op = actions.operator(
            "nexus.modifier_preset_rename",
            text="",
            icon="GREASEPENCIL",
        )
        op.preset_id = preset.preset_id

        del_btn = actions.row(align=True)
        del_btn.alert = True
        op = del_btn.operator(
            "nexus.modifier_preset_delete",
            text="",
            icon="X",
        )
        op.preset_id = preset.preset_id


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

modifier_preset_classes = [
    NEXUS_OT_modifier_preset_apply,
    NEXUS_OT_modifier_preset_apply_default,
    NEXUS_OT_modifier_preset_save,
    NEXUS_OT_modifier_preset_rename,
    NEXUS_OT_modifier_preset_delete,
    NEXUS_OT_modifier_preset_set_category,
    NEXUS_OT_modifier_preset_new_category_dialog,
    NEXUS_OT_modifier_preset_rename_category,
    NEXUS_OT_modifier_preset_create_category,
    NEXUS_OT_modifier_preset_delete_category,
    NEXUS_MT_modifier_preset_category,
    NEXUS_OT_modifier_preset_show_category_menu,
    NEXUS_OT_modifier_preset_popup,
]
