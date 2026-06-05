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

from dataclasses import dataclass, field


@dataclass
class ModifierPreset:
    preset_id: str
    name: str
    modifier_type: str
    category: str
    created: float
    properties: dict = field(default_factory=dict)
    curves: dict = field(default_factory=dict)
    gradients: dict = field(default_factory=dict)
    time_modes: dict = field(default_factory=dict)
    rate_modes: dict = field(default_factory=dict)
    collection_time_modes: dict = field(default_factory=dict)
    collection_time_values: dict = field(default_factory=dict)
    collection_rate_modes: dict = field(default_factory=dict)
    collections: dict = field(default_factory=dict)

    @property
    def data(self) -> dict:
        return {
            "properties": self.properties,
            "curves": self.curves,
            "gradients": self.gradients,
            "time_modes": self.time_modes,
            "rate_modes": self.rate_modes,
            "collection_time_modes": self.collection_time_modes,
            "collection_time_values": self.collection_time_values,
            "collection_rate_modes": self.collection_rate_modes,
            "collections": self.collections,
        }


_ALWAYS_EXCLUDE = frozenset({"ui_section", "rna_type", "name"})

_COLLECTION_UID_ATTRS = ("preset_uid", "curve_id", "layer_uid")

# Per-item identity suffixes are minted fresh on apply via add hooks; never reused.
_SKIP_ITEM_PROPS = frozenset({"rna_type", "preset_uid", "curve_id", "layer_uid"})


def _dict_or_empty(value, label: str) -> dict:
    """Tolerate tampered preset JSON: log and substitute `{}` for non-dicts."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    print(
        f"NeXus: ignoring malformed preset '{label}' "
        f"(expected dict, got {type(value).__name__})"
    )
    return {}


def _resolve_curve_specs(specs, item):
    from ..libs.resource_sync import resolve_curve_specs

    return list(resolve_curve_specs(specs, item))


def _resolve_gradient_specs(specs, item):
    from ..libs.resource_sync import resolve_gradient_specs

    return list(resolve_gradient_specs(specs, item))


def _detect_suffix_attr(*spec_lists) -> str | None:
    for specs in spec_lists:
        for s in specs:
            attr = getattr(s, "slot_suffix_attr", None)
            if attr:
                return attr
    return None


def _spec_suffix_attr(spec, item) -> str | None:
    """Resolve the suffix attr for a CollectionPresetSpec, deferring to the
    declared value or auto-detecting from the resolved curve/gradient specs.
    """
    if spec.suffix_attr:
        return spec.suffix_attr
    cs = _resolve_curve_specs(spec.curve_specs, item)
    gs = _resolve_gradient_specs(spec.gradient_specs, item)
    return _detect_suffix_attr(cs, gs)


def _collection_item_key(item, index: int) -> str:
    rna_props = item.bl_rna.properties
    if "preset_uid" in rna_props:
        uid = item.preset_uid
        if not uid:
            import os

            uid = os.urandom(8).hex()
            item.preset_uid = uid
        return f"uid:{uid}"
    for attr in ("curve_id", "layer_uid"):
        if attr in rna_props and getattr(item, attr, ""):
            return f"uid:{getattr(item, attr)}"
    return f"idx:{index}"


def _resolve_collection_item(collection, item_key: str):
    if item_key.startswith("uid:"):
        target = item_key[4:]
        if not target:
            return None
        for entry in collection:
            rna_props = entry.bl_rna.properties
            for attr in _COLLECTION_UID_ATTRS:
                if attr in rna_props and getattr(entry, attr) == target:
                    return entry
        return None
    if item_key.startswith("idx:"):
        try:
            idx = int(item_key[4:])
        except ValueError:
            return None
        if 0 <= idx < len(collection):
            return collection[idx]
    return None


def _get_collection_time_props(coll_attr: str) -> list[str]:
    from ..libs.nexus_time import get_time_collection_properties

    return [prop for attr, prop in get_time_collection_properties() if attr == coll_attr]


def _snapshot_item_resources(obj, item, spec) -> tuple[dict, dict]:
    from .curve import NexusCurve
    from .gradient import extract_gradient_stops

    curve_specs = _resolve_curve_specs(spec.curve_specs, item)
    gradient_specs = _resolve_gradient_specs(spec.gradient_specs, item)
    suffix_attr = spec.suffix_attr or _detect_suffix_attr(curve_specs, gradient_specs)

    curves: dict = {}
    gradients: dict = {}
    if not suffix_attr:
        return curves, gradients
    suffix = getattr(item, suffix_attr, "") if hasattr(item, suffix_attr) else ""
    if not suffix:
        return curves, gradients

    for cs in curve_specs:
        slot = f"{cs.slot_name}_{suffix}"
        nc = NexusCurve(obj, slot)
        points = nc.extract_points()
        if points is None:
            continue
        curve_obj = nc.curve
        handle_types = [p.handle_type for p in curve_obj.points] if curve_obj else []
        curves[cs.slot_name] = {
            "points": [list(p) for p in points],
            "handle_types": handle_types,
        }

    for gs in gradient_specs:
        slot = f"{gs.slot_name}_{suffix}"
        stops_data = extract_gradient_stops(obj, slot)
        if stops_data is None:
            continue
        gradients[gs.slot_name] = {
            "stops": [list(s) for s in stops_data["stops"]],
            "interpolation": stops_data["interpolation"],
            "color_mode": stops_data["color_mode"],
            "hue_interpolation": stops_data["hue_interpolation"],
        }

    return curves, gradients


def _snapshot_item_via_spec(obj, item, spec) -> dict:
    from ..libs.nexus_rate import _RATE_PROPERTY_REGISTRY, get_rate_mode
    from ..libs.nexus_time import get_prop_time_mode

    rna_props = item.bl_rna.properties
    item_data: dict = {}

    if "item_type" in rna_props:
        item_data["item_type"] = str(item.item_type)

    skip = _SKIP_ITEM_PROPS | set(spec.skip_props)
    scalars: dict = {}

    for prop_name, prop_def in rna_props.items():
        if prop_name in skip or prop_name == "item_type":
            continue
        prop_type = prop_def.type
        if prop_type in ("COLLECTION", "POINTER"):
            continue
        try:
            value = getattr(item, prop_name)
        except (AttributeError, TypeError):
            continue
        try:
            if prop_type in ("BOOLEAN", "INT", "FLOAT"):
                if prop_def.is_array:
                    scalars[prop_name] = list(value)
                elif prop_type == "BOOLEAN":
                    scalars[prop_name] = bool(value)
                elif prop_type == "INT":
                    scalars[prop_name] = int(value)
                else:
                    scalars[prop_name] = float(value)
            elif prop_type == "STRING":
                scalars[prop_name] = str(value)
            elif prop_type == "ENUM":
                if prop_def.is_enum_flag:
                    scalars[prop_name] = sorted(list(value))
                else:
                    scalars[prop_name] = str(value)
        except Exception as e:
            print(f"NeXus: Could not snapshot collection-item prop '{prop_name}': {e}")

    time_modes: dict = {}
    for tp_name in _get_collection_time_props(spec.collection_attr):
        if tp_name in rna_props:
            time_modes[tp_name] = get_prop_time_mode(item, tp_name)

    rate_modes: dict = {}
    for prop_name in rna_props.keys():
        if prop_name in _RATE_PROPERTY_REGISTRY:
            rate_modes[prop_name] = get_rate_mode(item, prop_name)

    item_data["scalars"] = scalars
    if time_modes:
        item_data["time_modes"] = time_modes
    if rate_modes:
        item_data["rate_modes"] = rate_modes

    curves, gradients = _snapshot_item_resources(obj, item, spec)
    if curves:
        item_data["curves"] = curves
    if gradients:
        item_data["gradients"] = gradients

    if spec.nested_specs:
        children: dict = {}
        for nested_spec in spec.nested_specs:
            if nested_spec.collection_attr not in rna_props:
                continue
            nested_coll = getattr(item, nested_spec.collection_attr, None)
            if nested_coll is None:
                continue
            nested_gate = nested_spec.item_capture_condition
            nested_out: list[dict] = []
            for sub_item in nested_coll:
                if nested_gate is not None:
                    try:
                        if not nested_gate(sub_item):
                            continue
                    except Exception as e:
                        print(
                            f"NeXus: item_capture_condition raised for "
                            f"'{nested_spec.collection_attr}'; dropping row: {e}"
                        )
                        continue
                nested_out.append(_snapshot_item_via_spec(obj, sub_item, nested_spec))
            children[nested_spec.collection_attr] = nested_out
        if children:
            item_data["children"] = children

    return item_data


def _snapshot_collections(obj, props, mod_type: str) -> dict:
    from ..libs.modifier_preset_spec import get_collection_preset_specs

    out: dict = {}
    for spec in get_collection_preset_specs(mod_type):
        collection = getattr(props, spec.collection_attr, None)
        if collection is None:
            continue
        gate = spec.item_capture_condition
        items_out: list[dict] = []
        for item in collection:
            if gate is not None:
                try:
                    if not gate(item):
                        continue
                except Exception as e:
                    print(
                        f"NeXus: item_capture_condition raised for "
                        f"'{spec.collection_attr}'; dropping row: {e}"
                    )
                    continue
            items_out.append(_snapshot_item_via_spec(obj, item, spec))
        out[spec.collection_attr] = items_out
    return out


_user_presets: list[ModifierPreset] = []
_user_preset_map: dict[str, ModifierPreset] = {}
_categories: dict[str, list[str]] = {}
_user_presets_path: str | None = None


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


def snapshot_modifier(obj) -> dict | None:
    from ..libs.nexus_rate import _RATE_PROPERTY_REGISTRY, get_rate_mode
    from ..libs.nexus_time import (
        get_prop_time_mode,
        get_time_collection_properties,
        get_time_property_names,
    )
    from ..modifiers import MODIFIER_REGISTRY
    from .curve import NexusCurve
    from .gradient import extract_gradient_stops

    mod_type = obj.get("nexus_modifier_type")
    mod_class = MODIFIER_REGISTRY.get(mod_type)
    if mod_class is None:
        return None

    from ..libs.modifier_spec import get_modifier_spec

    spec = get_modifier_spec(mod_type)
    props = obj.nexus_modifier
    prop_group_rna = props.bl_rna
    if spec is not None:
        prop_names = spec.build_snapshot_properties()
    else:
        prop_names = mod_class.get_modifier_properties()

    properties = {}
    for prop_name in prop_names:
        if prop_name in _ALWAYS_EXCLUDE:
            continue
        if prop_name not in prop_group_rna.properties:
            continue

        prop_def = prop_group_rna.properties[prop_name]
        prop_type = prop_def.type

        if prop_type in ("POINTER", "COLLECTION"):
            continue

        try:
            value = getattr(props, prop_name)

            if prop_type in ("BOOLEAN", "INT", "FLOAT"):
                if prop_def.is_array:
                    properties[prop_name] = list(value)
                elif prop_type == "BOOLEAN":
                    properties[prop_name] = bool(value)
                elif prop_type == "INT":
                    properties[prop_name] = int(value)
                else:
                    properties[prop_name] = float(value)

            elif prop_type == "STRING":
                properties[prop_name] = str(value)

            elif prop_type == "ENUM":
                if prop_def.is_enum_flag:
                    properties[prop_name] = sorted(list(value))
                else:
                    properties[prop_name] = str(value)

        except Exception as e:
            print(f"NeXus: Could not snapshot property '{prop_name}': {e}")

    curves = {}
    for curve_spec in mod_class.get_curve_specs():
        nc = NexusCurve(obj, curve_spec.slot_name)
        points = nc.extract_points()
        if points is None:
            continue
        curve_obj = nc.curve
        handle_types = [p.handle_type for p in curve_obj.points] if curve_obj else []
        curves[curve_spec.slot_name] = {
            "points": [list(p) for p in points],
            "handle_types": handle_types,
        }

    gradients = {}
    for gradient_spec in mod_class.get_gradient_specs():
        stops_data = extract_gradient_stops(obj, gradient_spec.slot_name)
        if stops_data is None:
            continue
        gradients[gradient_spec.slot_name] = {
            "stops": [list(s) for s in stops_data["stops"]],
            "interpolation": stops_data["interpolation"],
            "color_mode": stops_data["color_mode"],
            "hue_interpolation": stops_data["hue_interpolation"],
        }

    time_names = get_time_property_names()
    time_modes = {}
    for prop_name in prop_names:
        if prop_name in time_names:
            time_modes[prop_name] = get_prop_time_mode(props, prop_name)

    rate_modes = {}
    for prop_name in prop_names:
        if prop_name in _RATE_PROPERTY_REGISTRY:
            rate_modes[prop_name] = get_rate_mode(props, prop_name)

    collection_time_modes: dict[str, dict[str, dict[str, str]]] = {}
    collection_time_values: dict[str, dict[str, dict[str, float]]] = {}

    from ..libs.modifier_preset_spec import get_collection_preset_specs

    covered_attrs = {s.collection_attr for s in get_collection_preset_specs(mod_type)}

    # Per-item snapshots already carry time modes/values for covered specs;
    # this legacy payload only needs to fire for collections without a spec.
    coll_index: dict[str, list[str]] = {}
    for coll_attr, prop_name in get_time_collection_properties():
        if coll_attr in covered_attrs:
            continue
        coll_index.setdefault(coll_attr, []).append(prop_name)

    for coll_attr, time_prop_names in coll_index.items():
        collection = getattr(props, coll_attr, None)
        if collection is None:
            continue
        for index, item in enumerate(collection):
            modes_for_item: dict[str, str] = {}
            values_for_item: dict[str, float] = {}
            for tp_name in time_prop_names:
                if tp_name not in item.bl_rna.properties:
                    continue
                modes_for_item[tp_name] = get_prop_time_mode(item, tp_name)
                try:
                    values_for_item[tp_name] = float(getattr(item, tp_name))
                except (AttributeError, TypeError, ValueError):
                    continue
            if not modes_for_item and not values_for_item:
                continue
            key = _collection_item_key(item, index)
            if modes_for_item:
                collection_time_modes.setdefault(coll_attr, {})[key] = modes_for_item
            if values_for_item:
                collection_time_values.setdefault(coll_attr, {})[key] = values_for_item

    collections = _snapshot_collections(obj, props, mod_type)

    # Universal collection indexes (e.g. `mappings_index`) live on
    # NexusObjectProperties, not on any per-modifier descriptor list, so the
    # walk above misses them. Pick them up by collection_attr instead.
    for spec_for_idx in get_collection_preset_specs(mod_type):
        idx_attr = f"{spec_for_idx.collection_attr}_index"
        if idx_attr in properties:
            continue
        if idx_attr not in prop_group_rna.properties:
            continue
        try:
            properties[idx_attr] = int(getattr(props, idx_attr))
        except (AttributeError, TypeError, ValueError):
            continue

    return {
        "properties": properties,
        "curves": curves,
        "gradients": gradients,
        "time_modes": time_modes,
        "rate_modes": rate_modes,
        "collection_time_modes": collection_time_modes,
        "collection_time_values": collection_time_values,
        "collection_rate_modes": {},
        "collections": collections,
    }


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def apply_preset_data(obj, data: dict, *, context=None):
    import bpy

    from ..libs.modifier_preset_spec import get_collection_preset_specs
    from ..libs.nexus_rate import set_rate_mode
    from ..libs.nexus_time import set_prop_time_mode
    from ..modifiers import MODIFIER_REGISTRY
    from .curve import ensure_curve_ownership, get_curve_node_for_slot
    from .gradient import ensure_gradient_ownership, get_gradient_node_for_slot

    if context is None:
        context = bpy.context

    mod_type = obj.get("nexus_modifier_type")
    mod_class = MODIFIER_REGISTRY.get(mod_type)
    if mod_class is None:
        return

    ensure_gradient_ownership(obj, mod_class.get_gradient_specs() or None)
    ensure_curve_ownership(obj, mod_class.get_curve_specs() or None)

    props = obj.nexus_modifier
    prop_group_rna = props.bl_rna

    saved_props = _dict_or_empty(data.get("properties"), "properties")
    for prop_name, value in saved_props.items():
        if prop_name not in prop_group_rna.properties:
            continue
        try:
            setattr(props, prop_name, value)
        except Exception as e:
            print(f"NeXus: Could not apply property '{prop_name}': {e}")

    for slot_name, curve_data in _dict_or_empty(data.get("curves"), "curves").items():
        node = get_curve_node_for_slot(obj, slot_name)
        if node is None:
            continue
        _apply_curve_data(node, curve_data)

    for slot_name, grad_data in _dict_or_empty(data.get("gradients"), "gradients").items():
        node = get_gradient_node_for_slot(obj, slot_name)
        if node is None:
            continue
        _apply_gradient_data(node, grad_data)

    for prop_name, mode in _dict_or_empty(data.get("time_modes"), "time_modes").items():
        try:
            set_prop_time_mode(props, prop_name, mode)
        except Exception:
            pass

    for prop_name, mode in _dict_or_empty(data.get("rate_modes"), "rate_modes").items():
        try:
            set_rate_mode(props, prop_name, mode)
        except Exception:
            pass

    collections_data = _dict_or_empty(data.get("collections"), "collections")
    applied_attrs = _apply_covered_collections(
        obj, props, collections_data, mod_type, context=context
    )

    # Restore active-index for each covered collection. The covered-collection
    # apply path resets each `<coll>_index` to 0 then leaves it at the last
    # added item, which would otherwise clobber the captured selection.
    for spec in get_collection_preset_specs(mod_type):
        idx_attr = f"{spec.collection_attr}_index"
        if idx_attr not in saved_props:
            continue
        if idx_attr not in prop_group_rna.properties:
            continue
        coll_for_idx = getattr(props, spec.collection_attr, None)
        max_idx = max(0, len(coll_for_idx) - 1) if coll_for_idx is not None else 0
        try:
            value = max(0, min(int(saved_props[idx_attr]), max_idx))
            setattr(props, idx_attr, value)
        except Exception:
            pass

    _apply_collection_time(props, data, skip_attrs=applied_attrs)

    obj.update_tag()


def _apply_collection_time(props, data: dict, *, skip_attrs: set | None = None) -> None:
    from ..libs.nexus_time import set_prop_time_mode

    item_modes = _dict_or_empty(data.get("collection_time_modes"), "collection_time_modes")
    item_values = _dict_or_empty(data.get("collection_time_values"), "collection_time_values")
    if not item_modes and not item_values:
        return

    skip = skip_attrs or set()
    coll_names = (set(item_modes) | set(item_values)) - skip
    for coll_attr in coll_names:
        collection = getattr(props, coll_attr, None)
        if collection is None:
            continue

        modes_by_key = _dict_or_empty(
            item_modes.get(coll_attr), f"collection_time_modes.{coll_attr}"
        )
        values_by_key = _dict_or_empty(
            item_values.get(coll_attr), f"collection_time_values.{coll_attr}"
        )
        for item_key in set(modes_by_key) | set(values_by_key):
            item = _resolve_collection_item(collection, item_key)
            if item is None:
                continue

            for prop_name, mode in _dict_or_empty(
                modes_by_key.get(item_key), f"collection_time_modes.{coll_attr}[{item_key}]"
            ).items():
                if prop_name not in item.bl_rna.properties:
                    continue
                try:
                    set_prop_time_mode(item, prop_name, mode)
                except Exception:
                    pass

            for prop_name, value in _dict_or_empty(
                values_by_key.get(item_key),
                f"collection_time_values.{coll_attr}[{item_key}]",
            ).items():
                if prop_name not in item.bl_rna.properties:
                    continue
                try:
                    setattr(item, prop_name, value)
                except Exception:
                    pass


def _find_clear_spec(mod_type: str, list_prop: str):
    """Return a spec — top-level or nested — matching `list_prop`."""
    if not mod_type:
        return None
    from ..libs.modifier_preset_spec import get_collection_clear_specs

    for spec in get_collection_clear_specs(mod_type):
        if spec.collection_attr == list_prop:
            return spec
        for nested in spec.nested_specs:
            if nested.collection_attr == list_prop:
                return nested
    return None


def clear_collection_with_lifecycle(
    obj, collection, list_prop: str, *, context=None
) -> None:
    """Spec-aware clear: fires `on_remove` and releases per-item resources when a
    spec is registered for `list_prop`; otherwise falls back to `collection.clear()`."""
    mod_type = obj.get("nexus_modifier_type") if obj is not None else None
    spec = _find_clear_spec(mod_type, list_prop)
    if spec is None:
        collection.clear()
        return
    _clear_collection_via_spec(obj, collection, spec, context=context)


def _clear_collection_via_spec(obj, collection, spec, *, context=None) -> None:
    """Clear `collection` and release per-item resources; emit hierarchy-remove
    once after the clear so listeners match the operator's cleanup signal."""
    from ..ui.nodetree import _nodetree_registry
    from .curve import remove_item_curves
    from .gradient import remove_item_gradients

    on_remove = None
    on_hierarchy_remove = None
    if spec.menu_id:
        registry_entry = _nodetree_registry.get(spec.menu_id, {})
        on_remove = registry_entry.get("on_remove")
        if spec.hierarchy:
            on_hierarchy_remove = registry_entry.get("on_hierarchy_remove")

    for item in list(collection):
        for nested_spec in spec.nested_specs:
            nested_coll = getattr(item, nested_spec.collection_attr, None)
            if nested_coll is not None:
                _clear_collection_via_spec(obj, nested_coll, nested_spec, context=context)

        if on_remove is not None:
            try:
                on_remove(context, obj, item)
            except Exception as e:
                print(f"NeXus: on_remove failed for '{spec.collection_attr}': {e}")
            continue

        curve_specs = _resolve_curve_specs(spec.curve_specs, item)
        gradient_specs = _resolve_gradient_specs(spec.gradient_specs, item)
        suffix_attr = spec.suffix_attr or _detect_suffix_attr(curve_specs, gradient_specs)
        if not suffix_attr:
            continue
        suffix = getattr(item, suffix_attr, "") if hasattr(item, suffix_attr) else ""
        if not suffix:
            continue
        if curve_specs:
            try:
                remove_item_curves(obj, suffix, curve_specs)
            except Exception as e:
                print(f"NeXus: remove_item_curves failed for '{spec.collection_attr}': {e}")
        if gradient_specs:
            try:
                remove_item_gradients(obj, suffix, gradient_specs)
            except Exception as e:
                print(f"NeXus: remove_item_gradients failed for '{spec.collection_attr}': {e}")

    collection.clear()

    if on_hierarchy_remove is not None:
        try:
            on_hierarchy_remove(context, obj)
        except Exception as e:
            print(f"NeXus: on_hierarchy_remove failed for '{spec.collection_attr}': {e}")


def _add_item_via_spec(obj, props_or_parent, spec, item_data: dict, *, context=None):
    import bpy

    if spec.add_callback is not None:
        return spec.add_callback(obj, props_or_parent, item_data)

    if spec.menu_id:
        from ..ui.nodetree import add_nodetree_item

        idx_attr = f"{spec.collection_attr}_index"
        return add_nodetree_item(
            context if context is not None else bpy.context,
            obj,
            props_or_parent,
            spec.collection_attr,
            idx_attr,
            item_type=item_data.get("item_type", ""),
            menu_id=spec.menu_id,
            pre_add_index=-1,
        )

    collection = getattr(props_or_parent, spec.collection_attr, None)
    if collection is None:
        return None
    return collection.add()


def _apply_item_resources(obj, item, spec, item_data: dict) -> None:
    from .curve import get_curve_node_for_slot
    from .gradient import get_gradient_node_for_slot

    label = spec.collection_attr
    captured_curves = _dict_or_empty(item_data.get("curves"), f"{label}.curves")
    captured_grads = _dict_or_empty(item_data.get("gradients"), f"{label}.gradients")
    if not captured_curves and not captured_grads:
        return

    suffix_attr = _spec_suffix_attr(spec, item)
    if not suffix_attr:
        return
    suffix = getattr(item, suffix_attr, "") if hasattr(item, suffix_attr) else ""
    if not suffix:
        return

    for base_slot, curve_data in captured_curves.items():
        node = get_curve_node_for_slot(obj, f"{base_slot}_{suffix}")
        if node is None:
            continue
        _apply_curve_data(node, curve_data)

    for base_slot, grad_data in captured_grads.items():
        node = get_gradient_node_for_slot(obj, f"{base_slot}_{suffix}")
        if node is None:
            continue
        _apply_gradient_data(node, grad_data)


def _apply_item_via_spec(obj, item, spec, item_data: dict, *, context=None) -> None:
    from ..libs.nexus_rate import set_rate_mode
    from ..libs.nexus_time import set_prop_time_mode

    rna_props = item.bl_rna.properties
    label = spec.collection_attr

    skip = _SKIP_ITEM_PROPS | set(spec.skip_props)
    scalars = _dict_or_empty(item_data.get("scalars"), f"{label}.scalars")
    for prop_name, value in scalars.items():
        if prop_name not in rna_props:
            continue
        if prop_name in skip:
            continue
        try:
            setattr(item, prop_name, value)
        except Exception as e:
            print(f"NeXus: Could not apply scalar '{prop_name}' on '{label}': {e}")

    time_modes = _dict_or_empty(item_data.get("time_modes"), f"{label}.time_modes")
    for prop_name, mode in time_modes.items():
        if prop_name not in rna_props:
            continue
        try:
            set_prop_time_mode(item, prop_name, mode)
        except Exception:
            pass

    rate_modes = _dict_or_empty(item_data.get("rate_modes"), f"{label}.rate_modes")
    for prop_name, mode in rate_modes.items():
        if prop_name not in rna_props:
            continue
        try:
            set_rate_mode(item, prop_name, mode)
        except Exception:
            pass

    _apply_item_resources(obj, item, spec, item_data)

    children = _dict_or_empty(item_data.get("children"), f"{label}.children")
    if children and spec.nested_specs:
        for nested_spec in spec.nested_specs:
            nested_items_data = children.get(nested_spec.collection_attr)
            if nested_items_data is None:
                continue
            if not isinstance(nested_items_data, list):
                print(
                    f"NeXus: ignoring malformed nested preset "
                    f"'{nested_spec.collection_attr}' "
                    f"(expected list, got {type(nested_items_data).__name__})"
                )
                continue
            nested_coll = getattr(item, nested_spec.collection_attr, None)
            if nested_coll is None:
                continue
            _clear_collection_via_spec(obj, nested_coll, nested_spec, context=context)
            idx_attr = f"{nested_spec.collection_attr}_index"
            if hasattr(item, idx_attr):
                try:
                    setattr(item, idx_attr, 0)
                except Exception:
                    pass
            nested_gate = nested_spec.item_apply_condition
            for nested_item_data in nested_items_data:
                if not isinstance(nested_item_data, dict):
                    print(
                        f"NeXus: skipping malformed nested preset item in "
                        f"'{nested_spec.collection_attr}' "
                        f"(expected dict, got {type(nested_item_data).__name__})"
                    )
                    continue
                if nested_gate is not None:
                    try:
                        if not nested_gate(nested_item_data):
                            continue
                    except Exception as e:
                        print(
                            f"NeXus: item_apply_condition raised for "
                            f"'{nested_spec.collection_attr}'; dropping row: {e}"
                        )
                        continue
                nested_new = _add_item_via_spec(
                    obj, item, nested_spec, nested_item_data, context=context
                )
                if nested_new is None:
                    continue
                _apply_item_via_spec(
                    obj, nested_new, nested_spec, nested_item_data, context=context
                )

            # The nested rebuild leaves `<idx_attr>` pointing at the last
            # added item (via `add_nodetree_item`), or at 0 for bare adds.
            # Re-apply the captured parent-scoped index so the active row
            # matches what was saved.
            if idx_attr in scalars and hasattr(item, idx_attr):
                try:
                    setattr(item, idx_attr, scalars[idx_attr])
                except Exception:
                    pass


def _apply_covered_collections(
    obj, props, collections_data: dict, mod_type: str, *, context=None
) -> set[str]:
    """Replace covered collections from the payload; return the set of attrs
    actually replaced so the legacy fallback can patch the rest."""
    from ..libs.modifier_preset_spec import get_collection_preset_specs

    applied: set[str] = set()

    if not collections_data:
        return applied

    for spec in get_collection_preset_specs(mod_type):
        items_data = collections_data.get(spec.collection_attr)
        if items_data is None:
            continue
        if not isinstance(items_data, list):
            print(
                f"NeXus: ignoring malformed preset 'collections[{spec.collection_attr}]' "
                f"(expected list, got {type(items_data).__name__})"
            )
            continue
        collection = getattr(props, spec.collection_attr, None)
        if collection is None:
            continue

        _clear_collection_via_spec(obj, collection, spec, context=context)

        idx_attr = f"{spec.collection_attr}_index"
        if hasattr(props, idx_attr):
            try:
                setattr(props, idx_attr, 0)
            except Exception:
                pass

        for item_data in items_data:
            if not isinstance(item_data, dict):
                print(
                    f"NeXus: skipping malformed preset item in '{spec.collection_attr}' "
                    f"(expected dict, got {type(item_data).__name__})"
                )
                continue
            gate = spec.item_apply_condition
            if gate is not None:
                try:
                    if not gate(item_data):
                        continue
                except Exception as e:
                    print(
                        f"NeXus: item_apply_condition raised for "
                        f"'{spec.collection_attr}'; dropping row: {e}"
                    )
                    continue
            new_item = _add_item_via_spec(obj, props, spec, item_data, context=context)
            if new_item is None:
                continue
            _apply_item_via_spec(obj, new_item, spec, item_data, context=context)

        if spec.hierarchy:
            from ..ui.nodetree import hierarchy_recalculate_indent_levels

            hierarchy_recalculate_indent_levels(collection)

        applied.add(spec.collection_attr)

    return applied


def _apply_curve_data(node, curve_data: dict):
    points = curve_data.get("points", [])
    handle_types = curve_data.get("handle_types", [])
    if len(points) < 2:
        return

    mapping = node.mapping
    curve = mapping.curves[3]
    sorted_points = sorted(points, key=lambda p: p[0])

    while len(curve.points) > 2:
        curve.points.remove(curve.points[-1])

    curve.points[0].location = sorted_points[0]
    curve.points[1].location = sorted_points[-1]

    for px, py in sorted_points[1:-1]:
        curve.points.new(px, py)

    for i, point in enumerate(curve.points):
        point.handle_type = handle_types[i] if i < len(handle_types) else "AUTO"

    mapping.update()


def _apply_gradient_data(node, grad_data: dict):
    stops = grad_data.get("stops", [])
    if len(stops) < 2:
        return

    ramp = node.color_ramp
    sorted_stops = sorted(stops, key=lambda s: s[0])

    while len(ramp.elements) > 2:
        ramp.elements.remove(ramp.elements[1])

    ramp.elements[0].position = sorted_stops[0][0]
    ramp.elements[0].color = (
        sorted_stops[0][1],
        sorted_stops[0][2],
        sorted_stops[0][3],
        sorted_stops[0][4],
    )
    ramp.elements[-1].position = sorted_stops[-1][0]
    ramp.elements[-1].color = (
        sorted_stops[-1][1],
        sorted_stops[-1][2],
        sorted_stops[-1][3],
        sorted_stops[-1][4],
    )

    for pos, r, g, b, a in sorted_stops[1:-1]:
        elem = ramp.elements.new(pos)
        elem.color = (r, g, b, a)

    ramp.interpolation = grad_data.get("interpolation", "LINEAR")
    ramp.color_mode = grad_data.get("color_mode", "RGB")
    ramp.hue_interpolation = grad_data.get("hue_interpolation", "NEAR")


# ---------------------------------------------------------------------------
# Reset to defaults
# ---------------------------------------------------------------------------


def reset_to_defaults(obj, *, context=None):
    import bpy

    from ..libs.modifier_preset_spec import get_collection_clear_specs
    from ..modifiers import MODIFIER_REGISTRY
    from ..properties import NEXUS_ENUM_DEFAULTS
    from .curve import ensure_curve_ownership, get_curve_node_for_slot
    from .gradient import ensure_gradient_ownership, get_gradient_node_for_slot

    if context is None:
        context = bpy.context

    mod_type = obj.get("nexus_modifier_type")
    mod_class = MODIFIER_REGISTRY.get(mod_type)
    if mod_class is None:
        return

    ensure_gradient_ownership(obj, mod_class.get_gradient_specs() or None)
    ensure_curve_ownership(obj, mod_class.get_curve_specs() or None)

    from ..libs.modifier_spec import get_modifier_spec

    spec = get_modifier_spec(mod_type)
    props = obj.nexus_modifier
    prop_group_rna = props.bl_rna

    # Release per-item resources before the bare COLLECTION.clear() below
    # would orphan them.
    for preset_spec in get_collection_clear_specs(mod_type):
        collection = getattr(props, preset_spec.collection_attr, None)
        if collection is None:
            continue
        _clear_collection_via_spec(obj, collection, preset_spec, context=context)

    if spec is not None:
        prop_names = spec.build_reset_properties()
    else:
        prop_names = mod_class.get_modifier_properties()

    for prop_name in prop_names:
        if prop_name not in prop_group_rna.properties:
            continue

        prop_def = prop_group_rna.properties[prop_name]
        prop_type = prop_def.type

        try:
            if prop_type in ("BOOLEAN", "INT", "FLOAT"):
                if prop_def.is_array:
                    setattr(props, prop_name, prop_def.default_array[:])
                else:
                    setattr(props, prop_name, prop_def.default)

            elif prop_type == "STRING":
                setattr(props, prop_name, prop_def.default)

            elif prop_type == "ENUM":
                if prop_def.is_enum_flag:
                    setattr(props, prop_name, prop_def.default_flag)
                elif prop_name in NEXUS_ENUM_DEFAULTS:
                    setattr(props, prop_name, NEXUS_ENUM_DEFAULTS[prop_name])
                else:
                    default = prop_def.default
                    if isinstance(default, int):
                        try:
                            default = prop_def.enum_items[default].identifier
                        except (IndexError, KeyError):
                            print(
                                f"NeXus: Could not get enum identifier for "
                                f"'{prop_name}' at index {default}"
                            )
                            continue
                    setattr(props, prop_name, default)

            elif prop_type == "POINTER":
                setattr(props, prop_name, None)

            elif prop_type == "COLLECTION":
                getattr(props, prop_name).clear()

        except Exception as e:
            print(f"NeXus: Could not reset property '{prop_name}': {e}")

    for curve_spec in mod_class.get_curve_specs():
        node = get_curve_node_for_slot(obj, curve_spec.slot_name)
        if node is None:
            continue
        _apply_curve_data(
            node,
            {
                "points": [list(p) for p in curve_spec.default_points],
                "handle_types": [],
            },
        )

    for gradient_spec in mod_class.get_gradient_specs():
        node = get_gradient_node_for_slot(obj, gradient_spec.slot_name)
        if node is None:
            continue
        _apply_gradient_data(
            node,
            {
                "stops": [[s[0], *s[1]] for s in gradient_spec.default_stops],
                "interpolation": gradient_spec.default_interpolation,
                "color_mode": gradient_spec.default_color_mode,
                "hue_interpolation": gradient_spec.default_hue_interpolation,
            },
        )

    obj.update_tag()


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def init_user_presets(addon_package: str):
    global _user_presets_path

    import os

    try:
        import bpy

        presets_dir = bpy.utils.extension_path_user(addon_package, path="presets", create=True)
    except Exception:
        presets_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".user_presets",
        )
        os.makedirs(presets_dir, exist_ok=True)

    _user_presets_path = os.path.join(presets_dir, "user_modifier_presets.json")
    _load_user_presets()


def _load_user_presets():
    import json
    import os

    _user_presets.clear()
    _user_preset_map.clear()
    _categories.clear()

    if _user_presets_path is None or not os.path.isfile(_user_presets_path):
        return

    try:
        with open(_user_presets_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print(f"NeXus: Could not load user modifier presets: {e}")
        return

    for entry in data.get("presets", []):
        try:
            preset = ModifierPreset(
                preset_id=entry["preset_id"],
                name=entry["name"],
                modifier_type=entry["modifier_type"],
                category=entry.get("category", ""),
                created=entry.get("created", 0.0),
                properties=entry.get("properties", {}),
                curves=entry.get("curves", {}),
                gradients=entry.get("gradients", {}),
                time_modes=entry.get("time_modes", {}),
                rate_modes=entry.get("rate_modes", {}),
                collection_time_modes=entry.get("collection_time_modes", {}),
                collection_time_values=entry.get("collection_time_values", {}),
                collection_rate_modes=entry.get("collection_rate_modes", {}),
                collections=entry.get("collections", {}),
            )
            _user_presets.append(preset)
            _user_preset_map[preset.preset_id] = preset
        except (KeyError, TypeError) as e:
            print(f"NeXus: Skipping corrupt modifier preset entry: {e}")

    for mod_type, names in data.get("categories", {}).items():
        _categories[mod_type] = list(names)


def _save_user_presets():
    import json
    import os
    import tempfile

    if _user_presets_path is None:
        return

    data = {
        "version": 1,
        "categories": dict(_categories),
        "presets": [
            {
                "preset_id": p.preset_id,
                "name": p.name,
                "modifier_type": p.modifier_type,
                "category": p.category,
                "created": p.created,
                "properties": p.properties,
                "curves": p.curves,
                "gradients": p.gradients,
                "time_modes": p.time_modes,
                "rate_modes": p.rate_modes,
                "collection_time_modes": p.collection_time_modes,
                "collection_time_values": p.collection_time_values,
                "collection_rate_modes": p.collection_rate_modes,
                "collections": p.collections,
            }
            for p in _user_presets
        ],
    }

    try:
        dir_path = os.path.dirname(_user_presets_path)
        os.makedirs(dir_path, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=dir_path, delete=False, suffix=".tmp", mode="w", encoding="utf-8"
        ) as tmp:
            json.dump(data, tmp, indent=2)
            tmp_path = tmp.name
        os.replace(tmp_path, _user_presets_path)
    except OSError as e:
        print(f"NeXus: Could not save user modifier presets: {e}")


def _ensure_category(modifier_type: str, name: str):
    if not name:
        return
    cat_list = _categories.setdefault(modifier_type, [])
    if name not in cat_list:
        cat_list.append(name)


# ---------------------------------------------------------------------------
# Preset CRUD
# ---------------------------------------------------------------------------


def add_user_preset(name: str, modifier_type: str, category: str, data: dict) -> str:
    import os
    import time

    _ensure_category(modifier_type, category)

    preset_id = f"user_{os.urandom(4).hex()}"
    preset = ModifierPreset(
        preset_id=preset_id,
        name=name,
        modifier_type=modifier_type,
        category=category,
        created=time.time(),
        properties=data.get("properties", {}),
        curves=data.get("curves", {}),
        gradients=data.get("gradients", {}),
        time_modes=data.get("time_modes", {}),
        rate_modes=data.get("rate_modes", {}),
        collection_time_modes=data.get("collection_time_modes", {}),
        collection_time_values=data.get("collection_time_values", {}),
        collection_rate_modes=data.get("collection_rate_modes", {}),
        collections=data.get("collections", {}),
    )
    _user_presets.append(preset)
    _user_preset_map[preset_id] = preset
    _save_user_presets()
    return preset_id


def rename_user_preset(preset_id: str, new_name: str) -> bool:
    preset = _user_preset_map.get(preset_id)
    if preset is None:
        return False
    preset.name = new_name
    _save_user_presets()
    return True


def update_preset_category(preset_id: str, new_category: str) -> bool:
    preset = _user_preset_map.get(preset_id)
    if preset is None:
        return False
    _ensure_category(preset.modifier_type, new_category)
    preset.category = new_category
    _save_user_presets()
    return True


def rename_category(modifier_type: str, old_name: str, new_name: str) -> int:
    if not old_name or not new_name or old_name == new_name:
        return 0

    cat_list = _categories.get(modifier_type, [])
    for i, name in enumerate(cat_list):
        if name == old_name:
            cat_list[i] = new_name
            break

    count = 0
    for p in _user_presets:
        if p.modifier_type == modifier_type and p.category == old_name:
            p.category = new_name
            count += 1

    _save_user_presets()
    return count


def remove_user_preset(preset_id: str) -> bool:
    preset = _user_preset_map.pop(preset_id, None)
    if preset is None:
        return False
    _user_presets.remove(preset)
    _save_user_presets()
    return True


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------


def create_category(modifier_type: str, name: str) -> bool:
    cat_list = _categories.setdefault(modifier_type, [])
    if name in cat_list:
        return False
    cat_list.append(name)
    _save_user_presets()
    return True


def delete_category(modifier_type: str, name: str) -> int:
    cat_list = _categories.get(modifier_type, [])
    _categories[modifier_type] = [c for c in cat_list if c != name]

    count = 0
    for p in _user_presets:
        if p.modifier_type == modifier_type and p.category == name:
            p.category = ""
            count += 1

    _save_user_presets()
    return count


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def get_preset(preset_id: str) -> ModifierPreset | None:
    return _user_preset_map.get(preset_id)


def get_presets_for_type(modifier_type: str) -> list[ModifierPreset]:
    return [p for p in _user_presets if p.modifier_type == modifier_type]


def get_categories_for_type(modifier_type: str) -> list[str]:
    return list(_categories.get(modifier_type, []))


def get_user_presets() -> list[ModifierPreset]:
    return list(_user_presets)
