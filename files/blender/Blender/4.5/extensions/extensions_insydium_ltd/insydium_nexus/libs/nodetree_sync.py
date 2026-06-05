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

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .resource_spec import CurveSpecs, GradientSpecs
from .theron_sync import SyncSpec, get_declared_sync_specs, sync_property


def sync_enum_mapped(theron, get, nc, param_id: str, value, enum_map: dict[str, str]) -> None:
    """Write an enum value through a value->Theron-ID map."""
    id_name = enum_map.get(value)
    if id_name is not None:
        theron.set_int32(nc, get(param_id), get(id_name))


def sync_time_prop(
    theron,
    get,
    nc,
    param_id: str,
    item,
    attr: str,
    *,
    get_mode: Callable | None = None,
    to_fraction: Callable | None = None,
) -> None:
    """Write a time property by resolving its per-property display mode."""
    if get_mode is None or to_fraction is None:
        from .nexus_time import get_prop_time_mode, to_time_fraction

        get_mode = get_prop_time_mode
        to_fraction = to_time_fraction

    mode = get_mode(item, attr)
    t_num, t_den = to_fraction(float(getattr(item, attr)), mode=mode)
    theron.set_time(nc, get(param_id), t_num, t_den)


def sync_params(
    theron,
    get,
    nc,
    item,
    param_specs: tuple[SyncSpec, ...] | list[SyncSpec],
    *,
    obj=None,
    scene=None,
    depsgraph=None,
) -> None:
    """Sync a parameter table into a node container."""
    for spec in param_specs:
        sync_property(
            nc,
            item,
            spec,
            obj=obj,
            scene=scene,
            depsgraph=depsgraph,
            theron_mod=theron,
            id_resolver=get,
        )


@dataclass(frozen=True)
class CachedLinkResolverHooks:
    pre_syncer: Callable
    node_link_resolver: Callable
    post_syncer: Callable


def make_cached_link_resolver(
    *,
    poly_spec=None,
    line_spec=None,
    active_names: set[str] | None = None,
    on_resolved: Callable[[str, Any, int, int, int], None] | None = None,
    extra_pre_syncer: Callable | None = None,
    extra_post_syncer: Callable | None = None,
) -> CachedLinkResolverHooks:
    """Create pre/link/post hooks for cache-backed mesh/curve node links."""
    if poly_spec is None and line_spec is None:
        raise ValueError("make_cached_link_resolver requires poly_spec and/or line_spec")

    if active_names is None:
        active_names = set()

    def _pre_sync(
        _spec, _container, _props, *, obj=None, scene=None, depsgraph=None, collection_source=None
    ):
        active_names.clear()
        if extra_pre_syncer is not None:
            extra_pre_syncer(
                _spec,
                _container,
                _props,
                obj=obj,
                scene=scene,
                depsgraph=depsgraph,
                collection_source=collection_source,
            )

    def _resolve_link(_theron, item, obj, _scene, depsgraph):
        if obj is None or item.obj is None:
            return None

        from ..pipeline_manager.identity import ensure_object_uid

        mod_uid = ensure_object_uid(obj)

        obj_kind = item.obj.type
        target_name = item.obj.name

        if obj_kind == "MESH" and poly_spec is not None:
            from ..utils import extract_mesh_data
            from .cache_spec import ensure_poly_entry

            mesh_data = extract_mesh_data(item.obj, depsgraph)
            if mesh_data is None:
                return None
            vertices, polygons, vertex_count, poly_count, world_matrix = mesh_data
            obj_handle = ensure_poly_entry(
                poly_spec,
                mod_uid,
                target_name,
                vertices,
                polygons,
                vertex_count,
                poly_count,
                matrix=world_matrix,
            )
            if obj_handle is None:
                return None
            if on_resolved is not None:
                on_resolved(obj_kind, item.obj, obj_handle, vertex_count, poly_count)
        elif obj_kind == "CURVE" and line_spec is not None:
            from ..utils import extract_line_data
            from .cache_spec import ensure_line_entry

            line_data = extract_line_data(item.obj, depsgraph)
            if line_data is None:
                return None
            vertices, segments, vertex_count, seg_count, world_matrix = line_data
            obj_handle = ensure_line_entry(
                line_spec,
                mod_uid,
                target_name,
                vertices,
                segments,
                vertex_count,
                seg_count,
                matrix=world_matrix,
            )
            if obj_handle is None:
                return None
            if on_resolved is not None:
                on_resolved(obj_kind, item.obj, obj_handle, vertex_count, seg_count)
        else:
            return None

        active_names.add(target_name)
        return obj_handle

    def _post_sync(
        _spec, _container, _props, *, obj=None, scene=None, depsgraph=None, collection_source=None
    ):
        if obj is not None:
            from ..pipeline_manager.identity import ensure_object_uid
            from .cache_spec import evict_stale_entries_for

            mod_uid = ensure_object_uid(obj)
            if poly_spec is not None:
                evict_stale_entries_for(poly_spec, mod_uid, active_names)
            if line_spec is not None:
                evict_stale_entries_for(line_spec, mod_uid, active_names)
        active_names.clear()
        if extra_post_syncer is not None:
            extra_post_syncer(
                _spec,
                _container,
                _props,
                obj=obj,
                scene=scene,
                depsgraph=depsgraph,
                collection_source=collection_source,
            )

    return CachedLinkResolverHooks(
        pre_syncer=_pre_sync,
        node_link_resolver=_resolve_link,
        post_syncer=_post_sync,
    )


@dataclass(frozen=True)
class BlendSpec:
    mode_id_name: str
    strength_id_name: str
    id_map: dict[str, str]
    mode_attr: str = "blend_mode"
    strength_attr: str = "blend_strength"
    strength_scale: float = 0.01
    labels: dict[str, tuple[str, str]] | None = None

    def sync(self, theron, get, nc, item, *, strength_override: float | None = None):
        mode_val = getattr(item, self.mode_attr, None)
        mode_default = next(iter(self.id_map.values()), None)
        mode_id = get(self.id_map.get(mode_val, mode_default))
        theron.set_int32(nc, get(self.mode_id_name), mode_id)

        if strength_override is not None:
            strength = strength_override
        else:
            strength = getattr(item, self.strength_attr, 1.0) * self.strength_scale
        theron.set_float(nc, get(self.strength_id_name), strength)

    def enum_items(self) -> list[tuple[str, str, str]]:
        if self.labels is not None:
            return [(k, v[0], v[1]) for k, v in self.labels.items()]
        return [(k, k.replace("_", " ").title(), "") for k in self.id_map]

    def attach_properties(
        self,
        props_dict: dict,
        *,
        mode_name: str = "Blend Mode",
        mode_description: str = "",
        strength_name: str = "Strength",
        strength_description: str = "Blend strength",
        strength_default: float = 100.0,
        strength_max: float = 100.0,
        strength_soft_max: float | None = None,
    ) -> None:
        from bpy.props import EnumProperty, FloatProperty

        props_dict[self.mode_attr] = EnumProperty(
            name=mode_name,
            description=mode_description,
            items=self.enum_items(),
            default=next(iter(self.id_map)),
        )
        props_dict[self.strength_attr] = FloatProperty(
            name=strength_name,
            description=strength_description,
            default=strength_default,
            min=0.0,
            max=strength_max,
            soft_max=strength_soft_max if strength_soft_max is not None else strength_max,
            subtype="PERCENTAGE",
        )


@dataclass(frozen=True)
class NodeTreeSyncSpec:
    tree_id_name: str
    collection_attr: str
    tree_syncer: Callable | None = None
    pre_syncer: Callable | None = None
    post_syncer: Callable | None = None

    type_id_map: dict[str, str | int] = field(default_factory=dict)
    default_type_id: str | int | None = None
    node_id_offset: int = 0

    node_id_resolver: Callable[[Any, int], int | None] | None = None
    sequential_node_id: bool = False

    node_link_resolver: Callable | None = None
    skip_if_no_link: bool = False

    layer_op_id_name: str | None = None
    blend_spec: BlendSpec | None = None
    enabled_disables_blend: bool = False

    pre_dispatch_syncer: Callable | None = None
    pre_dispatch_syncer_ctx: Callable | None = None
    per_type_syncers: dict[str, Callable] = field(default_factory=dict)
    curve_specs: CurveSpecs = None
    gradient_specs: GradientSpecs = None
    per_item_post_syncer: Callable | None = None

    parent_index_attr: str | None = None
    condition: Callable[[Any], bool] | None = None


def _resolve_type_val(get, type_id: str | int | None) -> int | None:
    if type_id is None:
        return None
    if isinstance(type_id, str):
        return get(type_id)
    return type_id


def resolve_evaluated_item(evaluated_collection, index: int, fallback):
    if evaluated_collection is None:
        return fallback
    try:
        if index < len(evaluated_collection):
            return evaluated_collection[index]
    except (TypeError, ReferenceError):
        pass
    return fallback


def sync_nodetree(
    spec: NodeTreeSyncSpec,
    container: int,
    props,
    *,
    obj=None,
    scene=None,
    depsgraph=None,
    collection_source=None,
) -> None:
    if spec.condition is not None and not spec.condition(props):
        return

    if spec.tree_syncer is not None:
        spec.tree_syncer(
            spec,
            container,
            props,
            obj=obj,
            scene=scene,
            depsgraph=depsgraph,
            collection_source=collection_source,
        )
        return

    from . import theron, theron_ids
    from .resource_sync import (
        resolve_curve_specs,
        resolve_gradient_specs,
        sync_curve_specs,
        sync_gradient_specs,
    )

    get = theron_ids.get

    if spec.pre_syncer is not None:
        spec.pre_syncer(
            spec,
            container,
            props,
            obj=obj,
            scene=scene,
            depsgraph=depsgraph,
            collection_source=collection_source,
        )

    tree = theron.create_node_tree(container, get(spec.tree_id_name))
    if tree is None:
        if spec.post_syncer is not None:
            spec.post_syncer(
                spec,
                container,
                props,
                obj=obj,
                scene=scene,
                depsgraph=depsgraph,
                collection_source=collection_source,
            )
        return

    items_orig = getattr(
        collection_source if collection_source is not None else props, spec.collection_attr
    )
    items_eval = (
        getattr(props, spec.collection_attr, None) if collection_source is not None else items_orig
    )

    node_handles: dict[int, Any] = {}
    prev_sibling: dict[int, Any] = {}
    skipped: set[int] = set()
    inserted_count = 0

    for index, item_orig in enumerate(items_orig):
        item = resolve_evaluated_item(items_eval, index, item_orig)
        item_enabled = item.enabled

        if not item_enabled and not spec.enabled_disables_blend:
            skipped.add(index)
            continue

        if spec.parent_index_attr is not None:
            parent_idx = getattr(item_orig, spec.parent_index_attr, -1)
        else:
            parent_idx = -1

        if parent_idx >= 0:
            if parent_idx in skipped:
                skipped.add(index)
                continue
            parent_node = node_handles.get(parent_idx)
            if parent_node is None:
                skipped.add(index)
                continue
        else:
            parent_node = None

        link_handle = None
        if spec.skip_if_no_link and spec.node_link_resolver is not None:
            link_handle = spec.node_link_resolver(theron, item_orig, obj, scene, depsgraph)
            if link_handle is None:
                skipped.add(index)
                continue

        prev_node = prev_sibling.get(parent_idx)
        node = theron.node_tree_insert(tree, parent_node, prev_node)
        if node is None:
            continue

        item_type = getattr(item_orig, "item_type", None)

        if spec.sequential_node_id:
            node_id = inserted_count
        elif spec.node_id_resolver is not None:
            node_id = spec.node_id_resolver(item_orig, index)
        else:
            if item_type:
                type_id = spec.type_id_map.get(item_type, spec.default_type_id)
            else:
                type_id = spec.default_type_id
            type_val = _resolve_type_val(get, type_id)
            if type_val is not None:
                node_id = spec.node_id_offset + type_val
            else:
                node_id = None

        if node_id is not None:
            theron.set_node_id(node, node_id)

        if spec.skip_if_no_link and link_handle is not None:
            theron.set_node_link(node, link_handle)
        elif spec.node_link_resolver is not None:
            link_handle = spec.node_link_resolver(theron, item_orig, obj, scene, depsgraph)
            if link_handle is not None:
                theron.set_node_link(node, link_handle)

        nc = theron.create_node_container(node)

        if nc is not None:
            if spec.layer_op_id_name is not None and node_id is not None:
                theron.set_int32(nc, get(spec.layer_op_id_name), node_id)

            if spec.blend_spec is not None:
                strength_override = None if item_enabled else 0.0
                spec.blend_spec.sync(theron, get, nc, item, strength_override=strength_override)

            item_sync_specs = get_declared_sync_specs(item)
            if item_sync_specs:
                sync_params(
                    theron,
                    get,
                    nc,
                    item,
                    item_sync_specs,
                    obj=obj,
                    scene=scene,
                    depsgraph=depsgraph,
                )

            if spec.pre_dispatch_syncer is not None:
                spec.pre_dispatch_syncer(theron, get, nc, item, item_orig, obj)

            if spec.pre_dispatch_syncer_ctx is not None:
                spec.pre_dispatch_syncer_ctx(
                    theron, get, nc, item, item_orig, obj, scene, depsgraph
                )

            if item_type is not None and spec.per_type_syncers:
                syncer = spec.per_type_syncers.get(item_type)
                if syncer is not None:
                    syncer(theron, get, nc, item, item_orig, obj)

            curve_specs = resolve_curve_specs(spec.curve_specs, item_orig)
            if curve_specs:
                sync_curve_specs(
                    theron, get, nc, obj, curve_specs, source=item_orig, evaluated_source=item
                )

            gradient_specs = resolve_gradient_specs(spec.gradient_specs, item_orig)
            if gradient_specs:
                sync_gradient_specs(
                    theron, get, nc, obj, gradient_specs, source=item_orig, evaluated_source=item
                )

        if spec.per_item_post_syncer is not None:
            spec.per_item_post_syncer(theron, get, node, nc, item, item_orig, obj)

        node_handles[index] = node
        prev_sibling[parent_idx] = node
        inserted_count += 1

    if spec.post_syncer is not None:
        spec.post_syncer(
            spec,
            container,
            props,
            obj=obj,
            scene=scene,
            depsgraph=depsgraph,
            collection_source=collection_source,
        )


def sync_nodetrees(
    specs: tuple[NodeTreeSyncSpec, ...] | list[NodeTreeSyncSpec],
    container: int,
    props,
    **kwargs,
) -> None:
    for spec in specs:
        sync_nodetree(spec, container, props, **kwargs)
