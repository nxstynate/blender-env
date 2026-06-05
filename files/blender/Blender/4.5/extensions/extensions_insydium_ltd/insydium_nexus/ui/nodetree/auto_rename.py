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

"""Auto-rename helper for nodetree layer items.

Pairs with `register_nodetree`. Modifiers with a layer collection (e.g.
nx_turbulence layers, nx_color layers, nx_question items) want layers to start
with a sensible default name and to re-derive that name when the type or other
relevant properties change - but only if the user hasn't manually edited the
name. Each layer item carries an `is_renamed` BoolProperty to track that.

The pieces a property group needs:

- `name` StringProperty with `update=on_name_update(...)`
- `is_renamed` BoolProperty(default=False, options={"HIDDEN"})
- the rename-trigger property (typically `item_type`) with
  `update=on_trigger(base_name_fn=..., collection_attr=...)`
- the nodetree's `on_add` callback should call `initialize_added(item, items, base)`

Suppression uses a depth counter rather than a single boolean so that a nested
auto-rename (e.g. an `extra=` hook on `on_name_update` that itself triggers
another auto-rename) cannot prematurely re-enable rename tracking for the
outer call. Blender property updates run synchronously on a single thread, so
the counter only ever has to defend against direct recursion within the same
update chain.
"""

from typing import Any, Callable

from ...utils import generate_unique_name

_suppress_depth = 0


def _resolve_collection(item: Any, context: Any, collection_attr: str):
    obj = getattr(item, "id_data", None)
    if obj is None and context is not None:
        obj = getattr(context, "object", None)
    if obj is None:
        return None
    props = getattr(obj, "nexus_modifier", None)
    if props is None:
        return None
    return getattr(props, collection_attr, None)


def auto_rename(item: Any, items: Any, base_name: str) -> None:
    """Set `item.name` to a unique variant of `base_name` against `items`.

    Suppresses the name update callback so the assignment doesn't get treated
    as a manual rename. Reentrant via a depth counter.
    """
    global _suppress_depth
    item_ptr = item.as_pointer()
    existing = [
        items[i].name
        for i in range(len(items))
        if items[i].as_pointer() != item_ptr and items[i].name
    ]
    new_name = generate_unique_name(base_name, existing)

    _suppress_depth += 1
    try:
        item.name = new_name
    finally:
        _suppress_depth -= 1


def initialize_added(item: Any, items: Any, base_name: str) -> None:
    """Use from a nodetree on_add to give a fresh item its default name."""
    auto_rename(item, items, base_name)
    item.is_renamed = False


def on_name_update(
    extra: Callable[[Any, Any], bool] | None = None,
) -> Callable[[Any, Any], None]:
    """Build an `update=` callback for the `name` StringProperty.

    Marks the item as user-renamed unless the assignment came from
    `auto_rename`. If `extra(self, context)` returns True, skip the
    rename-tracking step (used by nx_explosiafx to lazily create curves on
    first naming without flagging it as a rename).
    """

    def _cb(self, context):
        if extra is not None and extra(self, context):
            return
        if _suppress_depth == 0:
            self.is_renamed = True

    return _cb


def on_trigger(
    *,
    base_name_fn: Callable[[Any], str],
    collection_attr: str,
    only_if_type: str | None = None,
    pre: Callable[[Any, Any], None] | None = None,
) -> Callable[[Any, Any], None]:
    """Build an `update=` callback for properties that should re-run auto-rename.

    `pre(self, context)` runs unconditionally first (e.g. to tag the viewport
    for redraw). If `only_if_type` is set, the rename only runs when
    `self.item_type` matches it. The rename is skipped when
    `self.is_renamed` is True.
    """

    def _cb(self, context):
        if pre is not None:
            pre(self, context)
        if only_if_type is not None and self.item_type != only_if_type:
            return
        if self.is_renamed:
            return
        items = _resolve_collection(self, context, collection_attr)
        if items is None:
            return
        auto_rename(self, items, base_name_fn(self))

    return _cb


def base_name_from_defs(defs: dict, fallback: str = "Layer") -> Callable[[Any], str]:
    """Convenience for the common case `defs[item.item_type]["name"]`."""

    def _fn(item):
        return defs.get(item.item_type, {}).get("name", fallback)

    return _fn
