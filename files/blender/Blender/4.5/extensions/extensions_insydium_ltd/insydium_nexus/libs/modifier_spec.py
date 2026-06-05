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

from dataclasses import dataclass
from typing import Any, Callable

from .theron_ids import THERON_IS_ACTIVE
from .theron_sync import SyncSpec, SyncType, Transform


@dataclass(frozen=True)
class AliasSpec:
    theron_id: str
    condition: Callable | None = None


_PROP_TYPE_MAP = {
    "FloatProperty": SyncType.FLOAT,
    "IntProperty": SyncType.INT,
    "BoolProperty": SyncType.BOOL,
    "EnumProperty": SyncType.ENUM,
    "FloatVectorProperty": SyncType.PACKED_VECTOR,
    "StringProperty": SyncType.STRING,
}


def deduce_sync_type(prop: Any) -> SyncType | None:
    if prop is None:
        return None
    func = getattr(prop, "function", None)
    if func is None:
        return None
    return _PROP_TYPE_MAP.get(func.__name__)


@dataclass(frozen=True)
class PropertyDescriptor:
    name: str
    prop: Any | None = None
    preset: bool = True
    reset: bool | None = None
    snapshot: bool | None = None
    theron_id: str | int | None = None
    sync_type: SyncType | None = None
    transform: Transform = Transform.NONE
    condition: Callable | None = None
    when: Callable | None = None
    scale: float = 1.0
    enum_map: dict[str, str | int] | None = None
    no_sync: bool = False
    aliases: tuple[AliasSpec, ...] = ()


ENABLED_DESCRIPTOR = PropertyDescriptor(
    name="enabled",
    prop=None,
    theron_id=THERON_IS_ACTIVE,
    sync_type=SyncType.BOOL,
    preset=False,
)


_spec_registry: dict[str, ModifierPropertySpec] = {}


def get_modifier_spec(modifier_type: str) -> ModifierPropertySpec | None:
    return _spec_registry.get(modifier_type)


@dataclass
class ModifierPropertySpec:
    modifier_type: str
    descriptors: tuple[PropertyDescriptor, ...]
    item_classes: tuple[type, ...] = ()
    enum_builders: tuple[Callable, ...] = ()
    nodetree_sync: tuple = ()
    cache_specs: tuple = ()
    blend_spec: Any | None = None
    enum_defaults: dict[str, str] | None = None

    def build_properties_dict(self) -> dict[str, Any]:
        return {d.name: d.prop for d in self.descriptors if d.prop is not None}

    def build_sync_specs(self) -> list[SyncSpec]:
        from . import theron_ids

        specs: list[SyncSpec] = []
        for d in self.descriptors:
            if d.no_sync:
                continue

            target_id = d.theron_id if d.theron_id is not None else d.name
            if isinstance(target_id, str) and not theron_ids.has(target_id):
                continue

            resolved_type = d.sync_type if d.sync_type is not None else deduce_sync_type(d.prop)
            if resolved_type is None:
                continue

            specs.append(
                SyncSpec(
                    blender_prop=d.name,
                    theron_id=target_id,
                    sync_type=resolved_type,
                    transform=d.transform,
                    condition=d.condition,
                    when=d.when,
                    scale=d.scale,
                    enum_map=d.enum_map,
                )
            )

            for alias in d.aliases:
                if not theron_ids.has(alias.theron_id):
                    continue
                specs.append(
                    SyncSpec(
                        blender_prop=d.name,
                        theron_id=alias.theron_id,
                        sync_type=resolved_type,
                        transform=d.transform,
                        condition=alias.condition if alias.condition is not None else d.condition,
                        when=d.when,
                        scale=d.scale,
                        enum_map=d.enum_map,
                    )
                )

        return specs

    def build_preset_properties(self) -> list[str]:
        return [d.name for d in self.descriptors if d.preset]

    def build_reset_properties(self) -> list[str]:
        props: list[str] = []
        for descriptor in self.descriptors:
            include = descriptor.preset if descriptor.reset is None else descriptor.reset
            if include:
                props.append(descriptor.name)
        return props

    def build_snapshot_properties(self) -> list[str]:
        props: list[str] = []
        for descriptor in self.descriptors:
            include = descriptor.preset if descriptor.snapshot is None else descriptor.snapshot
            if include:
                props.append(descriptor.name)
        return props

    def register(self) -> None:
        from .theron_sync import register_modifier_blend, register_modifier_sync

        _spec_registry[self.modifier_type] = self
        specs = self.build_sync_specs()
        if specs:
            register_modifier_sync(self.modifier_type, specs)
        if self.blend_spec is not None:
            register_modifier_blend(self.modifier_type, self.blend_spec)
        for builder in self.enum_builders:
            builder()


def clear_modifier_spec_registry() -> None:
    _spec_registry.clear()
