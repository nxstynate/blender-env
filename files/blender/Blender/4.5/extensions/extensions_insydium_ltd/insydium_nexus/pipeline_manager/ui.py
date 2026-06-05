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

from ..icons import get_icon
from .utils import (
    build_hierarchy_cache,
    get_modifier_icon,
    is_valid_modifier,
)


class NEXUS_UL_pipeline(bpy.types.UIList):
    """UIList with hierarchy indentation. ``filter_items`` seeds the cache for ``draw_item``."""

    bl_idname = "NEXUS_UL_pipeline"

    def _get_cache(self, pipeline):
        cache = getattr(self, "_hier_cache", None)
        if cache is None or cache.item_count != len(pipeline.modifier_order):
            cache = build_hierarchy_cache(pipeline)
            self._hier_cache = cache
        return cache

    def _row_lookup(self, cache, index):
        if 0 <= index < cache.item_count:
            return (
                cache.depth[index],
                cache.has_children[index],
                cache.ancestor_disabled[index],
            )
        return (0, False, False)

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        pipeline = data

        if item.is_folder:
            self._draw_folder_item(context, layout, pipeline, item, index)
            return

        obj = item.modifier

        if not is_valid_modifier(obj):
            layout.label(text="[Deleted]", icon="ERROR")
            return

        cache = self._get_cache(pipeline)
        depth, item_has_children, ancestor_disabled = self._row_lookup(cache, index)

        row = layout.row(align=True)

        if depth > 0:
            indent = row.row(align=True)
            indent.ui_units_x = depth * 0.8
            indent.label(text="")

        props = obj.nexus_modifier
        mod_type = obj.get("nexus_modifier_type")

        is_cached = props.is_cached
        is_cached_full = props.is_cached_full

        if item_has_children:
            collapse_icon = "TRIA_DOWN" if not item.collapsed else "TRIA_RIGHT"
            op = row.operator(
                "nexus.pipeline_toggle_collapse",
                text="",
                icon=collapse_icon,
                emboss=False,
            )
            op.index = index
        else:
            sub = row.row(align=True)
            sub.ui_units_x = 1.0
            sub.label(text="")

        cache_sub = row.row(align=True)
        cache_sub.ui_units_x = 1.0
        if is_cached_full:
            cache_sub.label(text="", icon_value=get_icon("nx_cache_cached"))
        elif is_cached:
            cache_sub.label(text="", icon_value=get_icon("nx_cache_partial"))
        else:
            cache_sub.label(text="")

        icon_id = get_modifier_icon(mod_type, obj)

        name_sub = row.row(align=True)
        name_sub.enabled = not ancestor_disabled and props.enabled
        if icon_id:
            name_sub.prop(obj, "name", text="", emboss=False, icon_value=icon_id)
        else:
            name_sub.prop(obj, "name", text="", emboss=False, icon="MODIFIER")

        enable_sub = row.row(align=True)
        enable_sub.enabled = not ancestor_disabled
        enable_sub.ui_units_x = 1.0
        op = enable_sub.operator(
            "nexus.pipeline_toggle_enable",
            text="",
            icon_value=get_icon("nx_enable") if props.enabled else get_icon("nx_disable"),
            emboss=False,
        )
        op.index = index
        op.is_folder = False

    def _draw_folder_item(self, context, layout, pipeline, item, index):
        cache = self._get_cache(pipeline)
        depth, item_has_children, ancestor_disabled = self._row_lookup(cache, index)

        row = layout.row(align=True)

        if depth > 0:
            indent = row.row(align=True)
            indent.ui_units_x = depth * 0.8
            indent.label(text="")

        if item_has_children:
            collapse_icon = "TRIA_DOWN" if not item.collapsed else "TRIA_RIGHT"
            op = row.operator(
                "nexus.pipeline_toggle_collapse",
                text="",
                icon=collapse_icon,
                emboss=False,
            )
            op.index = index
        else:
            sub = row.row(align=True)
            sub.ui_units_x = 1.0
            sub.label(text="")

        from .folder_icons import get_folder_icon_id

        icon_sub = row.row(align=True)
        icon_sub.ui_units_x = 1.2
        icon_id = get_folder_icon_id(item.folder_id, tuple(item.folder_color))
        op = icon_sub.operator(
            "nexus.pipeline_folder_settings",
            text="",
            icon_value=icon_id,
            emboss=False,
        )
        op.index = index

        name_sub = row.row(align=True)
        name_sub.enabled = not ancestor_disabled and item.folder_enabled
        name_sub.prop(item, "folder_name", text="", emboss=False)

        enable_sub = row.row(align=True)
        enable_sub.enabled = not ancestor_disabled
        enable_sub.ui_units_x = 1.0
        op = enable_sub.operator(
            "nexus.pipeline_toggle_enable",
            text="",
            icon_value=get_icon("nx_enable") if item.folder_enabled else get_icon("nx_disable"),
            emboss=False,
        )
        op.index = index
        op.is_folder = True

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        count = len(items)

        cache = build_hierarchy_cache(data)
        self._hier_cache = cache

        flt_flags = [self.bitflag_filter_item] * count
        flt_neworder = list(range(count))

        ancestor_collapsed = cache.ancestor_collapsed
        for i in range(count):
            if i < cache.item_count and ancestor_collapsed[i]:
                flt_flags[i] = 0

        return flt_flags, flt_neworder


class NEXUS_MT_pipeline_add(bpy.types.Menu):
    """Add object to pipeline."""

    bl_idname = "NEXUS_MT_pipeline_add"
    bl_label = "Add"

    def draw(self, context):
        layout = self.layout
        from ..icons import get_icon

        layout.operator(
            "nexus.pipeline_add_folder",
            text="Folder",
            icon_value=get_icon("nx_folder"),
        )
        layout.separator()

        from ..menus import draw_modifier_entries

        draw_modifier_entries(layout)


class NEXUS_PT_pipeline_manager(bpy.types.Panel):
    bl_idname = "NEXUS_PT_pipeline_manager"
    bl_label = "NeXus"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "NeXus"

    @classmethod
    def poll(cls, context):
        from ..libs import theron

        return theron.is_initialized()

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        if not hasattr(scene, "nexus_pipeline"):
            layout.label(text="Pipeline not initialized", icon="ERROR")
            return

        pipeline = scene.nexus_pipeline

        row = layout.row(align=True)
        row.prop_enum(pipeline, "sidebar_tab", "HIERARCHY")
        row.prop_enum(pipeline, "sidebar_tab", "HUD")
        row.prop_enum(pipeline, "sidebar_tab", "DOCUMENT")
        layout.separator()

        if pipeline.sidebar_tab == "HIERARCHY":
            self._draw_hierarchy(layout, pipeline)
        elif pipeline.sidebar_tab == "HUD":
            self._draw_hud_settings(layout, pipeline.hud)
        elif pipeline.sidebar_tab == "DOCUMENT":
            self._draw_doc_settings(layout, pipeline.global_opts)

    def _draw_hierarchy(self, layout, pipeline):

        layout.operator("nexus.open_console", text="Open Particle Console")

        row = layout.row()
        row.template_list(
            "NEXUS_UL_pipeline",
            "",
            pipeline,
            "modifier_order",
            pipeline,
            "modifier_order_index",
            rows=5,
        )

        col = row.column(align=True)
        col.menu("NEXUS_MT_pipeline_add", icon="ADD", text="")
        col.operator("nexus.pipeline_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nexus.pipeline_move", icon="TRIA_UP", text="").direction = "UP"
        col.operator("nexus.pipeline_move", icon="TRIA_DOWN", text="").direction = "DOWN"
        col.separator()
        col.operator("nexus.pipeline_indent", icon="TRIA_RIGHT", text="")
        col.operator("nexus.pipeline_outdent", icon="TRIA_LEFT", text="")

        if len(pipeline.modifier_order) == 0:
            layout.label(text="No NeXus modifiers in scene", icon="INFO")

    def _draw_hud_settings(self, layout, hud):
        layout.prop(hud, "hud_enabled")
        layout.separator()

        col = layout.column()
        col.enabled = hud.hud_enabled

        col.use_property_split = True
        col.label(text="Appearance")
        col.prop(hud, "hud_font_size")
        col.prop(hud, "hud_opacity")
        col.prop(hud, "hud_text_color")
        col.prop(hud, "hud_bg_color")

        col.separator()
        col.label(text="Display Items:")

        for show_prop, spark_prop in (
            ("hud_show_particle_count", "hud_spark_particle_count"),
            ("hud_show_vram_usage", "hud_spark_vram_pct"),
            ("hud_show_frame_time", "hud_spark_frame_time"),
            ("hud_show_device_name", None),
            ("hud_show_release_info", None),
        ):
            row = col.row(align=True)
            row.prop(hud, show_prop)
            if spark_prop is not None:
                sub = row.row(align=True)
                sub.active = getattr(hud, show_prop)
                sub.prop(hud, spark_prop, text="", icon="GRAPH")

        col.separator()
        row = col.row()
        row.operator("nexus.hud_reset_position", icon="FILE_REFRESH")

    def _draw_doc_settings(self, layout, global_opts):
        layout.prop(global_opts, "substeps")


classes = [
    NEXUS_UL_pipeline,
    NEXUS_MT_pipeline_add,
    NEXUS_PT_pipeline_manager,
]


def register():
    from bpy.utils import register_class

    for cls in classes:
        try:
            register_class(cls)
        except ValueError:
            pass


def unregister():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        try:
            unregister_class(cls)
        except RuntimeError:
            pass
