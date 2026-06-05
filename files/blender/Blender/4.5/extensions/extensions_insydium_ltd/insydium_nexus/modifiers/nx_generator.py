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

from ..properties.nx_generator import SPEC, NEXUS_UL_generator_layers
from .base import MenuCategory, NexusModifier, UIFlags


class NXGeneratorModifier(NexusModifier):
    object_type = "NX_GENERATOR"
    object_name = "nxGenerator"
    object_label = "Generator"
    object_description = "Instance meshes at every active particle position"
    icon_name = "nx_generator"
    category = "Generators"
    menu_category = MenuCategory.GENERATORS

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    # Real-geo path drives mesh writes from post_execute_pipeline, so opt out
    # of the standard Theron-handle sync.
    handles_own_sync = True

    _LIST_ID = "generator_layers"

    @classmethod
    def get_theron_type(cls, obj):
        return None

    @classmethod
    def sync_to_pipeline(cls, obj, scene, *, pipeline_handle, disabled, depsgraph=None) -> None:
        pass

    @classmethod
    def post_execute_pipeline(cls, obj, pipeline_handle, props, scene, *, depsgraph=None) -> None:
        if getattr(props, "display_mode", "PREVIEW") != "GEOMETRY":
            return
        from .nx_generator_realgeo import refresh_realgeo

        refresh_realgeo(obj, props, pipeline_handle)

    @classmethod
    def on_disable(cls, obj, props) -> None:
        from .nx_generator_realgeo import clear_points_geometry

        clear_points_geometry(obj)

    @classmethod
    def on_destroy(cls, mod_uid: str) -> None:
        from .nx_generator_realgeo import cleanup_orphaned_points

        cleanup_orphaned_points()

    @classmethod
    def get_modifier_properties(cls):
        return SPEC.build_preset_properties()

    @classmethod
    def on_create(cls, obj) -> None:
        """Add a default layer with spawn 100% so a fresh generator is usable."""
        try:
            layers = obj.nexus_modifier.generator_layers
        except (AttributeError, ReferenceError):
            return
        if len(layers) == 0:
            layers.add()
            obj.nexus_modifier.generator_layers_index = 0

    @classmethod
    def _draw_layer_settings(cls, col, item):
        col.prop(item, "obj")
        chance_row = col.row(align=True)
        chance_row.prop(item, "spawn_chance", slider=True)
        chance_row.prop(
            item,
            "locked",
            text="",
            icon="LOCKED" if item.locked else "UNLOCKED",
        )

        box = col.box()
        header = box.row()
        header.use_property_split = False
        header.use_property_decorate = False
        header.prop(
            item,
            "color_expanded",
            icon="TRIA_DOWN" if item.color_expanded else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        header.label(text="Colour")
        if item.color_expanded:
            body = box.column()
            body.use_property_split = True
            body.prop(item, "shading_mode")
            body.separator()
            body.prop(item, "color_source")
            if item.color_source == "CUSTOM":
                body.prop(item, "custom_color")
            body.prop(item, "color_variation_per_axis")
            if item.color_variation_per_axis:
                for prop_name, label in (
                    ("color_variation_r", "R"),
                    ("color_variation_g", "G"),
                    ("color_variation_b", "B"),
                ):
                    body.prop(item, prop_name, slider=True, text=label)
            else:
                body.prop(item, "color_variation", slider=True)
            body.separator()
            row = body.row(align=True)
            row.template_ID(item, "instance_material", new="nexus.generator_new_instance_material")

        box = col.box()
        header = box.row()
        header.use_property_split = False
        header.use_property_decorate = False
        header.prop(
            item,
            "scale_expanded",
            icon="TRIA_DOWN" if item.scale_expanded else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        header.label(text="Scale")
        if item.scale_expanded:
            body = box.column()
            body.use_property_split = True
            body.prop(item, "scale_source")
            if item.scale_source == "CUSTOM":
                body.prop(item, "custom_scale_per_axis")
                if item.custom_scale_per_axis:
                    body.prop(item, "custom_scale")
                else:
                    body.prop(item, "custom_scale_uniform")
            body.prop(item, "scale_variation_per_axis")
            if item.scale_variation_per_axis:
                for prop_name, label in (
                    ("scale_variation_x", "X"),
                    ("scale_variation_y", "Y"),
                    ("scale_variation_z", "Z"),
                ):
                    body.prop(item, prop_name, slider=True, text=label)
            else:
                body.prop(item, "scale_variation", slider=True)

        box = col.box()
        header = box.row()
        header.use_property_split = False
        header.use_property_decorate = False
        header.prop(
            item,
            "rotation_expanded",
            icon="TRIA_DOWN" if item.rotation_expanded else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        header.label(text="Rotation")
        if item.rotation_expanded:
            body = box.column()
            body.use_property_split = True
            body.prop(item, "rotation_source")
            if item.rotation_source == "CUSTOM":
                body.prop(item, "custom_rotation_per_axis")
                if item.custom_rotation_per_axis:
                    body.prop(item, "custom_rotation")
                else:
                    body.prop(item, "custom_rotation_uniform")
            body.prop(item, "rotation_variation_per_axis")
            if item.rotation_variation_per_axis:
                for prop_name, label in (
                    ("rotation_variation_x", "X"),
                    ("rotation_variation_y", "Y"),
                    ("rotation_variation_z", "Z"),
                ):
                    body.prop(item, prop_name, slider=True, text=label)
            else:
                body.prop(item, "rotation_variation", slider=True)

        box = col.box()
        header = box.row()
        header.use_property_split = False
        header.use_property_decorate = False
        header.prop(
            item,
            "animation_expanded",
            icon="TRIA_DOWN" if item.animation_expanded else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        header.label(text="Animation")
        if item.animation_expanded:
            body = box.column()
            body.use_property_split = True
            body.prop(item, "freeze_animation")
            if item.freeze_animation:
                row = body.row(align=True)
                sub = row.row(align=True)
                sub.enabled = False
                sub.prop(item, "frozen_frame")
                row.operator("nexus.generator_resnapshot_freeze", text="", icon="FILE_REFRESH")

    @classmethod
    def draw_ui(cls, layout, data):
        # Register list id for the framework's enable-toggle operator.
        from ..ui import draw_nodetree
        from ..ui.nodetree.registry import _nodetree_data_paths

        _nodetree_data_paths[cls._LIST_ID] = ""

        layout.prop(data, "display_mode")
        layout.separator(factor=0.5)

        draw_nodetree(
            layout,
            data,
            "source_emitters",
            "source_emitters_index",
            label="Source Emitters",
            allowed_types=["NX_EMITTER"],
        )
        layout.separator(factor=0.5)

        list_row = layout.row()
        list_row.template_list(
            NEXUS_UL_generator_layers.bl_idname,
            cls._LIST_ID,
            data,
            "generator_layers",
            data,
            "generator_layers_index",
            rows=4,
        )

        side = list_row.column(align=True)
        op = side.operator("nexus.nodetree_add", icon="ADD", text="")
        op.list_prop = "generator_layers"
        op.index_prop = "generator_layers_index"
        op.item_type = ""
        op.menu_id = ""
        op.data_path = ""

        op = side.operator("nexus.nodetree_remove", icon="REMOVE", text="")
        op.list_prop = "generator_layers"
        op.index_prop = "generator_layers_index"
        op.menu_id = ""
        op.data_path = ""

        side.separator()
        for direction, icon in (("UP", "TRIA_UP"), ("DOWN", "TRIA_DOWN")):
            op = side.operator("nexus.nodetree_move", icon=icon, text="")
            op.list_prop = "generator_layers"
            op.index_prop = "generator_layers_index"
            op.direction = direction
            op.data_path = ""

        # Active-layer settings panel
        layers = data.generator_layers
        idx = data.generator_layers_index
        if layers and 0 <= idx < len(layers):
            layout.separator(factor=0.5)
            settings = layout.column()
            settings.use_property_split = True
            cls._draw_layer_settings(settings, layers[idx])

    @classmethod
    def draw_viewport(cls, obj, props, context):
        pass
