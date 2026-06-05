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
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from . import theron_ids


def _resolve_id(id_value: Union[str, int]) -> int:
    if isinstance(id_value, str):
        return theron_ids.get(id_value)
    return id_value


class SyncType(Enum):
    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    LINK = "link"
    ENUM = "enum"
    VECTOR = "vector"
    PACKED_VECTOR = "packed_vector"
    TIME = "time"
    RATE = "rate"
    STRING = "string"


class Transform(Enum):
    NONE = "none"
    UNIT_SCALE = "unit_scale"
    PERCENT_TO_DECIMAL = "percent"
    DEGREES_TO_RADIANS = "deg_to_rad"
    RADIANS_TO_DEGREES = "rad_to_deg"


TRANSFORM_FACTORS = {
    Transform.NONE: 1.0,
    Transform.UNIT_SCALE: 1.0,
    Transform.PERCENT_TO_DECIMAL: 0.01,
}


@dataclass
class SyncSpec:
    blender_prop: str
    theron_id: Union[str, int]
    sync_type: SyncType
    transform: Transform = Transform.NONE
    source: Optional[Union[str, Callable[[Any, Any, Any, Any], Any]]] = None
    scale: float = 1.0
    transform_fn: Optional[Callable[[Any, Any, Any, Any], Any]] = None
    when: Optional[Callable[[Any, Any, Any, Any], bool]] = None
    enum_map: Optional[Dict[str, Union[str, int]]] = None
    condition: Optional[Callable[[Any], bool]] = None
    vector_ids: Optional[Tuple[Union[str, int], Union[str, int], Union[str, int]]] = None

    @classmethod
    def param(
        cls,
        kind: str,
        source: str | Callable[[Any, Any, Any, Any], Any],
        target: Union[str, int],
        *,
        scale: float = 1.0,
        transform: Optional[Callable[[Any, Any, Any, Any], Any]] = None,
        enum_map: Optional[Dict[str, Union[str, int]]] = None,
        when: Optional[Callable[[Any, Any, Any, Any], bool]] = None,
    ) -> "SyncSpec":
        kind_map = {
            "float": SyncType.FLOAT,
            "int": SyncType.INT,
            "bool": SyncType.BOOL,
            "enum": SyncType.ENUM,
            "vector": SyncType.PACKED_VECTOR,
            "time": SyncType.TIME,
            "string": SyncType.STRING,
        }
        sync_type = kind_map.get(kind)
        if sync_type is None:
            raise ValueError(f"Unsupported SyncSpec.param kind: {kind}")

        blender_prop = source if isinstance(source, str) else "__context_value__"
        return cls(
            blender_prop=blender_prop,
            theron_id=target,
            sync_type=sync_type,
            source=source,
            scale=scale,
            transform_fn=transform,
            enum_map=enum_map,
            when=when,
        )

    def __post_init__(self):
        if self.sync_type == SyncType.VECTOR and self.vector_ids is None:
            raise ValueError(
                f"SyncSpec for {self.blender_prop}: vector_ids required for VECTOR sync type"
            )
        if self.sync_type == SyncType.PACKED_VECTOR and self.vector_ids is not None:
            raise ValueError(
                f"SyncSpec for {self.blender_prop}: PACKED_VECTOR uses theron_id, not vector_ids"
            )


@dataclass
class ModifierSyncConfig:
    modifier_type: str
    specs: List[SyncSpec] = field(default_factory=list)


_sync_registry: Dict[str, ModifierSyncConfig] = {}
_blend_registry: Dict[str, Any] = {}


def get_declared_sync_specs(props: Any) -> tuple[SyncSpec, ...] | list[SyncSpec] | None:
    specs = getattr(type(props), "_sync_specs", None)
    if specs:
        return specs

    specs = getattr(props, "_sync_specs", None)
    if specs:
        return specs

    rna = getattr(props, "bl_rna", None)
    identifier = getattr(rna, "identifier", None)
    if identifier is None:
        return None

    try:
        import bpy
    except Exception:
        return None

    rna_cls = getattr(bpy.types, identifier, None)
    if rna_cls is None:
        return None
    return getattr(rna_cls, "_sync_specs", None)


def register_modifier_sync(modifier_type: str, specs: List[SyncSpec]) -> None:
    _sync_registry[modifier_type] = ModifierSyncConfig(modifier_type, specs)


def register_modifier_blend(modifier_type: str, blend_spec) -> None:
    _blend_registry[modifier_type] = blend_spec


def unregister_modifier_sync(modifier_type: str) -> None:
    _sync_registry.pop(modifier_type, None)


def get_modifier_sync(modifier_type: str) -> Optional[ModifierSyncConfig]:
    return _sync_registry.get(modifier_type)


def get_all_registered_syncs() -> Dict[str, ModifierSyncConfig]:
    return dict(_sync_registry)


def clear_sync_registry() -> None:
    _sync_registry.clear()
    _blend_registry.clear()


def _is_vector_like(value: Any, min_len: int = 3) -> bool:
    return hasattr(value, "__getitem__") and hasattr(value, "__len__") and len(value) >= min_len


def _apply_transform(value: Union[int, float], transform: Transform) -> Union[int, float]:
    import math

    if transform == Transform.NONE:
        return value
    elif transform == Transform.DEGREES_TO_RADIANS:
        return math.radians(value)
    elif transform == Transform.RADIANS_TO_DEGREES:
        return math.degrees(value)
    elif transform in TRANSFORM_FACTORS:
        return value * TRANSFORM_FACTORS[transform]
    return value


def _extract_vec3(value: Any) -> tuple[float, float, float] | None:
    try:
        return float(value[0]), float(value[1]), float(value[2])
    except Exception:
        pass

    try:
        seq = tuple(value)
    except Exception:
        return None

    if len(seq) < 3:
        return None
    return float(seq[0]), float(seq[1]), float(seq[2])


def sync_property(
    container: int,
    props: Any,
    spec: SyncSpec,
    *,
    obj=None,
    scene=None,
    depsgraph=None,
    theron_mod=None,
    id_resolver: Optional[Callable[[Union[str, int]], int]] = None,
) -> bool:
    return _sync_property_with_context(
        container,
        props,
        spec,
        obj=obj,
        scene=scene,
        depsgraph=depsgraph,
        theron_mod=theron_mod,
        id_resolver=id_resolver,
    )


def _sync_property_with_context(
    container: int,
    props: Any,
    spec: SyncSpec,
    *,
    obj=None,
    scene=None,
    depsgraph=None,
    theron_mod=None,
    id_resolver: Optional[Callable[[Union[str, int]], int]] = None,
) -> bool:
    from . import theron

    theron_ref = theron if theron_mod is None else theron_mod
    resolve_id = _resolve_id if id_resolver is None else id_resolver

    source = spec.source if spec.source is not None else spec.blender_prop
    if callable(source):
        value = source(props, obj, scene, depsgraph)
    else:
        value = getattr(props, source, None)
    if value is None:
        return False

    if spec.when is not None and not spec.when(props, obj, scene, depsgraph):
        return False

    if spec.condition is not None and not spec.condition(props):
        return False

    resolved_id = resolve_id(spec.theron_id)

    def _transform_scalar(raw):
        if spec.transform_fn is not None:
            out = spec.transform_fn(raw, props, obj, scene, depsgraph)
        else:
            out = _apply_transform(raw, spec.transform)
        return out * spec.scale

    if spec.sync_type == SyncType.LINK:
        if scene is None or value is None:
            return False
        from ..handlers.pipeline import get_nexus_obj_handle

        link_handle = get_nexus_obj_handle(scene, value)
        if link_handle is None:
            return False
        theron_ref.set_link(container, resolved_id, link_handle)
        return True

    if spec.sync_type == SyncType.FLOAT:
        transformed = float(_transform_scalar(float(value)))
        theron_ref.set_float(container, resolved_id, transformed)

    elif spec.sync_type == SyncType.INT:
        transformed = int(_transform_scalar(int(value)))
        theron_ref.set_int32(container, resolved_id, transformed)

    elif spec.sync_type == SyncType.BOOL:
        theron_ref.set_bool(container, resolved_id, bool(value))

    elif spec.sync_type == SyncType.TIME:
        from .nexus_time import get_prop_time_mode, to_time_fraction

        if isinstance(source, str):
            time_attr = source
        else:
            time_attr = spec.blender_prop
        prop_mode = get_prop_time_mode(props, time_attr)
        time_val = float(_transform_scalar(float(value)))
        num, den = to_time_fraction(time_val, mode=prop_mode)
        theron_ref.set_time(container, resolved_id, num, den)

    elif spec.sync_type == SyncType.RATE:
        from .nexus_rate import get_rate_mode, to_per_second

        rate_mode = get_rate_mode(props, spec.blender_prop)
        per_sec = to_per_second(int(value), mode=rate_mode)
        theron_ref.set_int32(container, resolved_id, int(per_sec))

        per_frame_id = resolve_id("ID_NX_EMITTER_SHOT_PER_FRAME")
        theron_ref.set_bool(container, per_frame_id, True)

    elif spec.sync_type == SyncType.ENUM:
        if spec.enum_map is not None:
            enum_value = spec.enum_map.get(value, 0)
        else:
            enum_value = value
        int_value = resolve_id(enum_value) if isinstance(enum_value, str) else enum_value
        theron_ref.set_int32(container, resolved_id, int_value)

    elif spec.sync_type == SyncType.VECTOR:
        x_id, y_id, z_id = spec.vector_ids
        if spec.transform_fn is not None:
            value = spec.transform_fn(value, props, obj, scene, depsgraph)
            factor = spec.scale
        else:
            factor = TRANSFORM_FACTORS.get(spec.transform, 1.0) * spec.scale

        vec = _extract_vec3(value)
        if vec is not None:
            x, y, z = vec
            theron_ref.set_float(container, resolve_id(x_id), x * factor)
            theron_ref.set_float(container, resolve_id(y_id), y * factor)
            theron_ref.set_float(container, resolve_id(z_id), z * factor)
        else:
            return False

    elif spec.sync_type == SyncType.PACKED_VECTOR:
        if spec.transform_fn is not None:
            value = spec.transform_fn(value, props, obj, scene, depsgraph)
            factor = spec.scale
        else:
            factor = TRANSFORM_FACTORS.get(spec.transform, 1.0) * spec.scale

        vec = _extract_vec3(value)
        if vec is not None:
            x, y, z = vec
            theron_ref.set_vector(
                container,
                resolved_id,
                x * factor,
                y * factor,
                z * factor,
            )
        else:
            return False

    elif spec.sync_type == SyncType.STRING:
        theron_ref.set_string(container, resolved_id, str(value))

    return True


def sync_properties(container: int, props: Any, modifier_type: str, scene: Any = None) -> int:
    config = _sync_registry.get(modifier_type)
    synced = 0
    if config:
        for spec in config.specs:
            if sync_property(container, props, spec, scene=scene):
                synced += 1

    blend_spec = _blend_registry.get(modifier_type)
    if blend_spec is not None:
        from . import theron, theron_ids

        blend_spec.sync(theron, theron_ids.get, container, props)
        synced += 2

    return synced


def sync_declared_specs(
    container: int,
    props: Any,
    *,
    scene: Any = None,
    obj: Any = None,
    depsgraph: Any = None,
) -> int:
    specs = get_declared_sync_specs(props)
    if not specs:
        return 0

    synced = 0
    for spec in specs:
        if sync_property(container, props, spec, scene=scene, obj=obj, depsgraph=depsgraph):
            synced += 1
    return synced


def create_enum_map_from_items(items: List[tuple]) -> Dict[str, int]:
    result = {}
    for i, item in enumerate(items):
        identifier = item[0]
        if len(item) >= 5:
            value = item[4]
        else:
            value = i
        result[identifier] = value
    return result


def validate_sync_specs(modifier_type: str, props_class: type) -> List[str]:
    config = _sync_registry.get(modifier_type)
    if not config:
        return [f"No sync config registered for {modifier_type}"]

    errors = []
    annotations = getattr(props_class, "__annotations__", {})

    for spec in config.specs:
        if spec.blender_prop not in annotations:
            errors.append(
                f"{modifier_type}: Property '{spec.blender_prop}' "
                f"not found in {props_class.__name__}"
            )

    return errors
