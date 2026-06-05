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

from typing import Optional, Set

import bpy

from ..libs.cache_spec import (
    CacheKind,
    CacheSpec,
    ensure_poly_container_entry,
    evict_stale_entries_for,
)
from ..properties.nx_collider import SPEC, get_collider_ui_config
from .base import MenuCategory, NexusModifier, UIFlags

_collider_cache: dict[tuple[str, str], tuple[int, int, int, int]] = {}

_COLLIDER_CACHE_SPEC = CacheSpec(
    kind=CacheKind.POLY_CONTAINER,
    collection_attr="collider_objects",
    cache_dict=_collider_cache,
)


class NXColliderModifier(NexusModifier):
    object_type = "NX_COLLIDER"
    object_name = "nxCollider"
    object_label = "Collider"
    object_description = "Collide particles with mesh objects"
    icon_name = "nx_collider"
    category = "General"
    menu_category = MenuCategory.OBJECTS

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON
    cache_specs = (_COLLIDER_CACHE_SPEC,)
    handles_own_sync = True

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_collider_ui_config()
        cls.draw_property(layout, data, "collider_objects", ui_config)

    @classmethod
    def sync_to_pipeline(
        cls,
        obj: bpy.types.Object,
        scene: bpy.types.Scene,
        *,
        pipeline_handle: int,
        disabled: bool,
        depsgraph: bpy.types.Depsgraph | None = None,
    ) -> None:
        from ..libs.cache_spec import clear_cache
        from ..pipeline_manager.identity import ensure_object_uid

        mod_uid = ensure_object_uid(obj)

        if disabled:
            for spec in cls.cache_specs:
                clear_cache(spec, mod_name=mod_uid)
            return

        if depsgraph is not None:
            try:
                eval_obj = obj.evaluated_get(depsgraph)
                props = eval_obj.nexus_modifier
            except (RuntimeError, AttributeError):
                props = obj.nexus_modifier
        else:
            props = obj.nexus_modifier

        cls.sync_collider(
            obj,
            props,
            pipeline_handle,
            scene,
            depsgraph,
            collection_source=obj.nexus_modifier,
        )

    @classmethod
    def sync_collider(
        cls,
        obj: bpy.types.Object,
        props,
        pipeline_handle: int,
        scene: bpy.types.Scene,
        depsgraph: Optional[bpy.types.Depsgraph],
        collection_source=None,
    ) -> Set[str]:
        from ..libs import theron
        from ..libs.nodetree_sync import resolve_evaluated_item
        from ..libs.theron_sync import sync_declared_specs, sync_properties
        from ..pipeline_manager.identity import ensure_object_uid
        from ..utils import extract_mesh_data

        mod_uid = ensure_object_uid(obj)
        active_mesh_names: Set[str] = set()

        src = collection_source if collection_source is not None else props
        collection_orig = getattr(src, "collider_objects", None)
        if collection_orig is None:
            return active_mesh_names
        collection_eval = (
            getattr(props, "collider_objects", None)
            if collection_source is not None
            else collection_orig
        )

        for index, item_orig in enumerate(collection_orig):
            item = resolve_evaluated_item(collection_eval, index, item_orig)
            if not item.enabled:
                continue

            mesh_obj = item_orig.obj
            if mesh_obj is None or mesh_obj.type != "MESH":
                continue

            mesh_name = mesh_obj.name
            active_mesh_names.add(mesh_name)

            mesh_data = extract_mesh_data(mesh_obj, depsgraph)
            if mesh_data is None:
                continue
            vertices, polygons, vertex_count, poly_count, world_matrix = mesh_data

            def _on_new(ph, ch, _item=item):
                sync_properties(ch, props, "NX_COLLIDER")
                sync_declared_specs(ch, _item, scene=scene, obj=obj, depsgraph=depsgraph)
                return theron.add_collider_mesh(pipeline_handle, ph, ch)

            poly_handle, container_handle = ensure_poly_container_entry(
                _COLLIDER_CACHE_SPEC,
                mod_uid,
                mesh_name,
                vertices,
                polygons,
                vertex_count,
                poly_count,
                on_new=_on_new,
                matrix=world_matrix,
            )
            if poly_handle is None:
                continue

            sync_properties(container_handle, props, "NX_COLLIDER")
            sync_declared_specs(
                container_handle,
                item,
                scene=scene,
                obj=obj,
                depsgraph=depsgraph,
            )

        evict_stale_entries_for(_COLLIDER_CACHE_SPEC, mod_uid, active_mesh_names)
        return active_mesh_names

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, _props, _context) -> None:
        pass
