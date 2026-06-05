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

"""Per-modifier-type cache of mapping metadata read from Theron.

Label resolution waterfall: info.name -> SyncSpec lookup -> "id_<N>" sentinel.
"""

from __future__ import annotations

from typing import NamedTuple, Tuple

from . import theron, theron_ids


class MappingMetadata(NamedTuple):
    mod_type: str
    dest_params: Tuple[theron.MappingParamInfo, ...]
    groups: Tuple[str, ...]
    map_to: Tuple[theron.MappingParamInfo, ...]
    map_to_groups: Tuple[str, ...]


_EMPTY = MappingMetadata(
    mod_type="",
    dest_params=(),
    groups=(),
    map_to=(),
    map_to_groups=(),
)

_cache: dict[str, MappingMetadata] = {}


def get_mapping_metadata(mod_type: str, handle: int) -> MappingMetadata:
    """Lazy per-type fetch. @param handle may be any live modifier of @p mod_type."""
    cached = _cache.get(mod_type)
    if cached is not None:
        return cached

    if handle == 0:
        return _EMPTY

    metadata = MappingMetadata(
        mod_type=mod_type,
        dest_params=tuple(theron.get_mapping_params(handle)),
        groups=tuple(theron.get_mapping_groups(handle)),
        map_to=tuple(theron.get_mapping_to(handle)),
        map_to_groups=tuple(theron.get_mapping_to_groups(handle)),
    )
    _cache[mod_type] = metadata
    return metadata


def invalidate_cache() -> None:
    """Call when Theron is reloaded / shut down so stale metadata doesn't survive."""
    _cache.clear()


def _resolve_theron_id_to_int(raw) -> int:
    if isinstance(raw, int):
        return raw
    try:
        return theron_ids.get(raw)
    except (KeyError, TypeError):
        return -1


def _deferred_prop_label(prop) -> str:
    kwargs = getattr(prop, "keywords", None)
    if not kwargs:
        return ""
    return kwargs.get("name", "") or ""


def _prop_label(cls, prop_name: str) -> str:
    # __annotations__ first since bl_rna can drop names starting with uppercase
    if cls is None or not prop_name:
        return ""
    ann = getattr(cls, "__annotations__", None) or {}
    prop = ann.get(prop_name)
    if prop is not None:
        label = _deferred_prop_label(prop)
        if label:
            return label
    try:
        rna_prop = cls.bl_rna.properties.get(prop_name)
        if rna_prop and rna_prop.name:
            return rna_prop.name
    except (AttributeError, RuntimeError):
        pass
    return ""


def _resolve_label_from_syncspecs(mod_type: str, theron_id_int: int) -> str:
    from .modifier_spec import get_modifier_spec

    spec = get_modifier_spec(mod_type)
    if spec is None:
        return ""

    # per-layer item-class sync specs
    for item_cls in spec.item_classes:
        specs = getattr(item_cls, "_sync_specs", None)
        if not specs:
            continue
        for sync_spec in specs:
            if _resolve_theron_id_to_int(sync_spec.theron_id) == theron_id_int:
                label = _prop_label(item_cls, sync_spec.blender_prop)
                if label:
                    return label
            if sync_spec.vector_ids:
                for axis_idx, vid in enumerate(sync_spec.vector_ids):
                    if _resolve_theron_id_to_int(vid) == theron_id_int:
                        label = _prop_label(item_cls, sync_spec.blender_prop)
                        if label:
                            axis = ["X", "Y", "Z"][axis_idx] if axis_idx < 3 else str(axis_idx)
                            return f"{label} {axis}"

    # BlendSpec on each nodetree_sync entry
    nodetree_specs = getattr(spec, "nodetree_sync", None) or ()
    for tree_spec in nodetree_specs:
        blend_spec = getattr(tree_spec, "blend_spec", None)
        if blend_spec is None:
            continue
        mode_id = _resolve_theron_id_to_int(getattr(blend_spec, "mode_id_name", None))
        strength_id = _resolve_theron_id_to_int(getattr(blend_spec, "strength_id_name", None))
        for item_cls in spec.item_classes:
            if mode_id == theron_id_int:
                label = _prop_label(item_cls, getattr(blend_spec, "mode_attr", "blend_mode"))
                if label:
                    return label
            if strength_id == theron_id_int:
                label = _prop_label(
                    item_cls, getattr(blend_spec, "strength_attr", "blend_strength")
                )
                if label:
                    return label

    # modifier-root descriptors (non-layered modifiers); read the deferred-prop kwarg directly
    for d in spec.descriptors:
        if d.prop is None:
            continue
        raw = d.theron_id if d.theron_id is not None else d.name
        if _resolve_theron_id_to_int(raw) == theron_id_int:
            label = _deferred_prop_label(d.prop)
            if label:
                return label
        for alias in getattr(d, "aliases", ()) or ():
            alias_id = getattr(alias, "theron_id", None)
            if alias_id is not None and _resolve_theron_id_to_int(alias_id) == theron_id_int:
                label = _deferred_prop_label(d.prop)
                if label:
                    return label

    return ""


def resolve_label(info: theron.MappingParamInfo, metadata: MappingMetadata) -> str:
    if info.name:
        return info.name
    if metadata.mod_type:
        spec_label = _resolve_label_from_syncspecs(metadata.mod_type, info.param)
        if spec_label:
            return spec_label
    return f"id_{info.param}"


def resolve_group_label(group_name: str, index: int) -> str:
    return group_name or f"Group {index}"
