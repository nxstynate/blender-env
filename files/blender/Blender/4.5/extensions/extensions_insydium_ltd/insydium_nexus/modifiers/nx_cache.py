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

from ..properties.nx_cache import SPEC
from .base import MenuCategory, NexusObject, UIFlags


def _format_bytes(n: int) -> str:
    for unit, threshold in (("GB", 1_000_000_000), ("MB", 1_000_000), ("KB", 1_000)):
        if n >= threshold:
            return f"{n / threshold:.1f} {unit}"
    return f"{n} B"


class NXCacheModifier(NexusObject):
    object_type = "NX_CACHE"
    object_name = "nxCache"
    object_label = "Cache"
    object_description = "Read/write cached NeXus simulation data"
    icon_name = "nx_cache_icon"
    category = "Simulation"
    menu_category = MenuCategory.EMITTER

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def post_execute_object(
        cls, obj: bpy.types.Object, handle: int, props, scene: bpy.types.Scene, **_kwargs
    ) -> None:
        from ..libs import theron
        from ..handlers import pipeline as pipeline_handler

        pipeline = pipeline_handler.get_pipeline(scene)
        if pipeline is None:
            return

        status = theron.get_cache_status(pipeline, handle)
        if status is None:
            return

        cached_frames, _job_complete, mem_size, disk_size, uncompressed_size = status
        props.cache_info_frames = f"{cached_frames} / {scene.frame_end - scene.frame_start}"
        props.cache_info_memory = _format_bytes(mem_size)
        props.cache_info_disk_space = _format_bytes(disk_size)
        props.cache_info_uncompressed = _format_bytes(uncompressed_size)
        props.cache_info_compression_ratio = (
            f"{uncompressed_size / disk_size:.2f}x" if disk_size > 0 else ""
        )

        cls._sync_sources(handle, props, scene)

    @classmethod
    def post_sync(
        cls, obj, container, handle, props, scene, original_props=None, **_kwargs
    ) -> None:
        from ..handlers.pipeline import get_nexus_obj_handle
        from ..libs import theron
        from ..libs.theron_ids import get as get_theron_id

        source_props = original_props if original_props is not None else props

        sources_tree_id = get_theron_id("ID_NX_CACHE_SOURCES")
        tree = theron.get_node_tree(container, sources_tree_id)

        if tree is None:
            existing = [s.obj for s in source_props.cache_sources if s.obj is not None]
            if not existing:
                return

            tree = theron.create_node_tree(container, sources_tree_id)
            if tree is None:
                return

            for source_obj in existing:
                source_handle = get_nexus_obj_handle(scene, source_obj)
                if source_handle is None:
                    continue
                node = theron.node_tree_insert(tree, None, None)
                if node is not None:
                    theron.set_node_link(node, source_handle)

        state_by_handle: dict[int, tuple[bool, bool]] = {}
        for item in source_props.cache_sources:
            if item.obj is None:
                continue
            src_handle = get_nexus_obj_handle(scene, item.obj)
            if src_handle is not None:
                state_by_handle[src_handle] = (item.enabled, item.locked)

        if not state_by_handle:
            return

        locked_id = get_theron_id("ID_NX_CACHE_SOURCE_IS_LOCKED")

        node = theron.node_tree_get_first(tree)
        while node is not None:
            link_handle = theron.get_node_link(node)
            if link_handle is not None:
                state = state_by_handle.get(link_handle)
                if state is not None:
                    enabled, locked = state
                    theron.set_node_enabled(node, enabled)
                    nc = theron.create_node_container(node)
                    if nc is not None:
                        theron.set_bool(nc, locked_id, locked)
            node = theron.node_tree_get_next(tree, node)

    @classmethod
    def _sync_sources(cls, handle: int, props, scene: bpy.types.Scene) -> None:
        from ..handlers.pipeline import find_object_for_handle
        from ..libs import theron
        from ..libs.theron_ids import get as get_theron_id

        container = theron.get_object_container(handle)
        if container is None:
            return

        sources_tree_id = get_theron_id("ID_NX_CACHE_SOURCES")
        tree = theron.get_node_tree(container, sources_tree_id)
        if tree is None:
            return

        linked_objs = []
        node = theron.node_tree_get_first(tree)
        while node is not None:
            link_handle = theron.get_node_link(node)
            if link_handle is not None:
                source_obj = find_object_for_handle(scene, link_handle)
                if source_obj is not None:
                    linked_objs.append(source_obj)
            node = theron.node_tree_get_next(tree, node)

        current_names = [s.obj.name for s in props.cache_sources if s.obj is not None]
        new_names = [o.name for o in linked_objs]
        if current_names == new_names:
            return

        state_by_name = {
            s.obj.name: (s.enabled, s.locked) for s in props.cache_sources if s.obj is not None
        }

        props.cache_sources.clear()
        for source_obj in linked_objs:
            item = props.cache_sources.add()
            item.obj = source_obj
            if source_obj.name in state_by_name:
                item.enabled, item.locked = state_by_name[source_obj.name]

    @classmethod
    def draw_ui(cls, layout, data):
        col = layout.column()
        col.use_property_split = True

        row = col.row(align=True)
        row.prop(data, "ID_NX_CACHE_MODE", expand=True)

        col.separator(type="LINE")

        col.prop(data, "ID_NX_CACHE_FORMAT")
        col.prop(data, "ID_NX_CACHE_SCALE")

        col.separator(type="LINE")
        col.prop(data, "ID_NX_CACHE_RECORD_DATA")

        if data.ID_NX_CACHE_RECORD_DATA == "ID_NX_CACHE_RECORD_DATA_CUSTOM":
            from ..properties.nx_cache import _CACHE_RECORD_PROPS

            grid = col.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
            grid.use_property_split = False
            for key, _, _ in _CACHE_RECORD_PROPS:
                grid.prop(data, f"ID_NX_CACHE_RECORD_PROP_{key}")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_CACHE_VOXEL_FORMAT")
        col.prop(data, "ID_NX_CACHE_VOXEL_SCALE")

        header, body = col.panel("nx_cache_efx_channels", default_closed=True)
        header.label(text="EFX Channels")
        if body is not None:
            from ..properties.nx_cache import _CACHE_EFX_CHANNELS

            body.use_property_split = False
            for key, label, _, _ in _CACHE_EFX_CHANNELS:
                prop_name = f"ID_NX_CACHE_VOXEL_CHANNEL_{key}"
                split = body.split(factor=0.5)
                split.prop(data, prop_name, text=label)
                split.prop(data, f"{prop_name}_NAME", text="")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_CACHE_DIRECTORY")
        col.prop(data, "ID_NX_CACHE_COMPRESS")
        col.prop(data, "ID_NX_CACHE_MEMORY_USE_LIMIT")

        row = layout.row(align=True)
        row.operator("nexus.cache_build", text="Build Cache")
        row.operator("nexus.cache_empty", text="Empty Cache")

        layout.separator(factor=0.5)
        cls._draw_info_section(layout, data)

        layout.separator(type="LINE")
        cls._draw_sources_list(layout, data)

    @classmethod
    def _draw_sources_list(cls, layout, data):
        layout.label(text="Sources")
        layout.template_list(
            "NEXUS_UL_cache_sources",
            "",
            data,
            "cache_sources",
            data,
            "cache_sources_index",
            rows=4,
        )

    @classmethod
    def _draw_info_section(cls, layout, data):
        layout.separator(type="LINE")

        box = layout.box()
        col = box.column(align=True)

        for label, attr in (
            ("Cached Frames", "cache_info_frames"),
            ("Memory Used", "cache_info_memory"),
            ("Compressed Size", "cache_info_disk_space"),
            ("Uncompressed Size", "cache_info_uncompressed"),
        ):
            if attr == "cache_info_disk_space" and not data.ID_NX_CACHE_COMPRESS:
                continue
            split = col.split(factor=0.5)
            name_col = split.column()
            name_col.alignment = "RIGHT"
            name_col.label(text=label)
            value = getattr(data, attr, "")
            if attr == "cache_info_disk_space" and value:
                ratio = getattr(data, "cache_info_compression_ratio", "")
                value = f"{value} ({ratio})" if ratio != "" else value
            split.label(text=value if value else "N/A")
