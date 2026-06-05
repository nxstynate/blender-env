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

import inspect

from ..utils.curve import resolve_curve_slot_name, sync_curve_to_theron
from ..utils.gradient import (
    NexusGradient,
    build_default_gradient_stops_data,
    resolve_gradient_slot_name,
    sync_gradient_to_theron,
)
from .resource_spec import CurveSpec, CurveSpecs, GradientSpec, GradientSpecs


def resolve_curve_specs(
    specs: CurveSpecs,
    source=None,
) -> tuple[CurveSpec, ...]:
    if specs is None:
        return ()
    resolved = _resolve_specs(specs, source)
    return tuple(resolved or ())


def resolve_gradient_specs(
    specs: GradientSpecs,
    source=None,
) -> tuple[GradientSpec, ...]:
    if specs is None:
        return ()
    resolved = _resolve_specs(specs, source)
    return tuple(resolved or ())


def _resolve_specs(specs, source):
    if not callable(specs):
        return specs

    signature = inspect.signature(specs)
    if not signature.parameters:
        return specs()
    return specs(source)


def _resolve_param_id(get, param_id: str | int) -> int:
    if isinstance(param_id, str):
        return get(param_id)
    return param_id


def _should_sync_resource(resource_spec, evaluated_source, structural_source) -> bool:
    if resource_spec.sync_condition is None:
        return True
    if evaluated_source is None and structural_source is None:
        return False
    return bool(resource_spec.sync_condition(evaluated_source, structural_source))


def sync_curve_specs(
    theron, get, container, owner_obj, specs, *, source=None, evaluated_source=None
) -> None:
    if evaluated_source is None:
        evaluated_source = source
    for curve_spec in specs:
        if not curve_spec.theron_ids or not _should_sync_resource(
            curve_spec, evaluated_source, source
        ):
            continue

        slot_name = resolve_curve_slot_name(curve_spec, source)
        if slot_name is None:
            continue

        for theron_id in curve_spec.theron_ids:
            sync_curve_to_theron(
                theron,
                container,
                owner_obj,
                slot_name,
                _resolve_param_id(get, theron_id),
                default_ramp=curve_spec.default_points,
            )


def sync_gradient_specs(
    theron, get, container, owner_obj, specs, *, source=None, evaluated_source=None
) -> None:
    if evaluated_source is None:
        evaluated_source = source
    for gradient_spec in specs:
        if not gradient_spec.theron_ids or not _should_sync_resource(
            gradient_spec, evaluated_source, source
        ):
            continue

        slot_name = resolve_gradient_slot_name(gradient_spec, source)
        if slot_name is None:
            continue

        gradient = NexusGradient(owner_obj, slot_name)
        stops_data = gradient.extract_stops() or build_default_gradient_stops_data(gradient_spec)

        for theron_id in gradient_spec.theron_ids:
            grad_handle = theron.create_gradient(container, _resolve_param_id(get, theron_id))
            if grad_handle is None:
                continue
            sync_gradient_to_theron(theron, grad_handle, stops_data)
