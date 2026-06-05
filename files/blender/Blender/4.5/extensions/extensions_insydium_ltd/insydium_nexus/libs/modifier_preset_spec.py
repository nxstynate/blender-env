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

"""Declarative metadata for modifier-preset capture and reset cleanup.

Property modules register a `CollectionPresetSpec` per opted-in collection;
the engine in `utils/modifier_presets.py` consumes them generically.
Unregistered collections are skipped on snapshot. POINTER values are never
captured — presets carry portable config, not scene links.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

CurveSpecsLike = Any
GradientSpecsLike = Any


@dataclass(frozen=True)
class CollectionPresetSpec:
    collection_attr: str

    # Add path: `add_callback` wins, else `menu_id` runs `add_nodetree_item`,
    # else a bare `collection.add()`.
    menu_id: str | None = None
    add_callback: Callable[[Any, Any, dict], Any] | None = None

    # Per-item resources. May be a list of CurveSpec/GradientSpec or a
    # callable. A callable with no args is invoked once at use time; one
    # taking a single `source` argument receives the live item (used for
    # type-conditional dispatch like nx_follow_geo OFFSET vs TWIST).
    curve_specs: CurveSpecsLike = None
    gradient_specs: GradientSpecsLike = None

    # Slot suffix attribute. If unset the engine inspects the first
    # curve/gradient spec's `slot_suffix_attr`.
    suffix_attr: str | None = None

    # Hierarchy collections need indent-level recalc after apply.
    hierarchy: bool = False

    # Nested sub-collections owned by parent items. Each nested spec is
    # captured/applied recursively against the parent item.
    nested_specs: tuple["CollectionPresetSpec", ...] = ()

    # Extra item-attribute names to skip during scalar capture. The engine
    # always skips `rna_type` and the well-known identity suffixes
    # (`preset_uid` / `curve_id` / `layer_uid`). Add here if a collection
    # has runtime-only fields that must not be captured.
    skip_props: tuple[str, ...] = field(default_factory=tuple)

    # Per-item gates. Rows are dropped when the predicate returns False:
    # `item_capture_condition(item)` on snapshot, `item_apply_condition(item_data)` on apply.
    item_capture_condition: Callable[[Any], bool] | None = None
    item_apply_condition: Callable[[dict], bool] | None = None


_per_type: dict[str, list[CollectionPresetSpec]] = {}
_universal: list[CollectionPresetSpec] = []
_cleanup_per_type: dict[str, list[CollectionPresetSpec]] = {}


def register_collection_preset(modifier_type: str, spec: CollectionPresetSpec) -> None:
    """Register a per-modifier preset spec.

    Idempotent against the same `(modifier_type, collection_attr)` key:
    re-registering replaces the existing entry.
    """
    bucket = _per_type.setdefault(modifier_type, [])
    for i, existing in enumerate(bucket):
        if existing.collection_attr == spec.collection_attr:
            bucket[i] = spec
            return
    bucket.append(spec)


def register_universal_collection_preset(spec: CollectionPresetSpec) -> None:
    """Register a spec that applies to every modifier (e.g. mappings)."""
    for i, existing in enumerate(_universal):
        if existing.collection_attr == spec.collection_attr:
            _universal[i] = spec
            return
    _universal.append(spec)


def register_collection_cleanup(modifier_type: str, spec: CollectionPresetSpec) -> None:
    """Register a collection for reset cleanup only — not preset-captured.

    Honours `menu_id` / `curve_specs` / `gradient_specs` / `nested_specs` for
    per-item resource release.
    """
    bucket = _cleanup_per_type.setdefault(modifier_type, [])
    for i, existing in enumerate(bucket):
        if existing.collection_attr == spec.collection_attr:
            bucket[i] = spec
            return
    bucket.append(spec)


def get_collection_preset_specs(modifier_type: str) -> list[CollectionPresetSpec]:
    """Return the universal specs followed by the per-modifier specs."""
    return list(_universal) + list(_per_type.get(modifier_type, []))


def get_collection_cleanup_specs(modifier_type: str) -> list[CollectionPresetSpec]:
    """Return cleanup-only specs for a modifier type."""
    return list(_cleanup_per_type.get(modifier_type, []))


def get_collection_clear_specs(modifier_type: str) -> list[CollectionPresetSpec]:
    """Return preset specs followed by cleanup-only specs."""
    return get_collection_preset_specs(modifier_type) + get_collection_cleanup_specs(
        modifier_type
    )


def iter_all_specs() -> Iterable[tuple[str | None, CollectionPresetSpec]]:
    """Yield every registered spec as `(modifier_type, spec)`. `modifier_type` is
    None for universal specs. Useful for diagnostics/tests.
    """
    for spec in _universal:
        yield None, spec
    for mod_type, specs in _per_type.items():
        for spec in specs:
            yield mod_type, spec


def clear_registry_for_tests() -> None:
    _per_type.clear()
    _universal.clear()
    _cleanup_per_type.clear()
