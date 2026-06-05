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
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
)

from ..ui import get_pending_ghost_slots, make_allowed_types_poll, make_drop_target_update
from .mapping import NexusMappingEntry
from .nx_attract import SPEC as ATTRACT_SPEC
from .nx_avoid import SPEC as AVOID_SPEC
from .nx_avoid import NexusAvoidItem
from .nx_blend import SPEC as BLEND_SPEC
from .nx_cache import SPEC as CACHE_SPEC
from .nx_cache import NEXUS_UL_cache_sources, NexusCacheSourceItem
from .nx_collider import SPEC as COLLIDER_SPEC
from .nx_collider import NexusColliderItem
from .nx_color import SPEC as COLOR_SPEC
from .nx_color import NexusColorLayerItem
from .nx_constraints import SPEC as CONSTRAINTS_SPEC
from .nx_constraints import NexusConstraintLayerItem
from .nx_cover import SPEC as COVER_SPEC
from .nx_cover import NexusCoverItem
from .nx_direction import SPEC as DIRECTION_SPEC
from .nx_direction import NexusDirectionLayerItem
from .nx_drag import SPEC as DRAG_SPEC
from .nx_emitter import SPEC as EMITTER_SPEC
from .nx_emitter import (
    NexusEmitterExtendedDataItem,
    NexusEmitterGroupItem,
    NexusEmitterModifierItem,
    NexusEmitterObjectItem,
)
from .nx_explode import SPEC as EXPLODE_SPEC
from .nx_explosiafx import SPEC as EXPLOSIAFX_SPEC
from .nx_explosiafx import (
    NexusEFXColliderItem,
    NexusEFXForceLayerItem,
    NexusEFXPAdvectItem,
    NexusEFXSourceItem,
)
from .nx_falloff import SPEC as FALLOFF_SPEC
from .nx_flock import SPEC as FLOCK_SPEC
from .nx_flock import (
    NexusFlockAvoidanceItem,
    NexusFlockBehaviorItem,
    NexusFlockReactionItem,
)
from .nx_fluids import SPEC as FLUIDS_SPEC
from .nx_follow_geo import SPEC as FOLLOW_GEO_SPEC
from .nx_follow_geo import NexusFollowGeoExtendedItem, NexusFollowGeoItem
from .nx_generator import SPEC as GENERATOR_SPEC
from .nx_generator import (
    NEXUS_UL_generator_layers,
    NexusGeneratorLayerItem,
    NexusGeneratorSourceEmitterItem,
)
from .nx_gravity import SPEC as GRAVITY_SPEC
from .nx_group import SPEC as GROUP_SPEC
from .nx_infectio import SPEC as INFECTIO_SPEC
from .nx_infectio import NexusInfectioSeedItem
from .nx_kill import SPEC as KILL_SPEC
from .nx_kill import NexusKillItem
from .nx_limit import SPEC as LIMIT_SPEC
from .nx_limit import NexusLimitLayerItem
from .nx_mesher import SPEC as MESHER_SPEC
from .nx_mesher import NexusMesherLayerItem
from .nx_push import SPEC as PUSH_SPEC
from .nx_question import SPEC as QUESTION_SPEC
from .nx_question import NexusQuestionItem
from .nx_rotate import SPEC as ROTATE_SPEC
from .nx_scale import SPEC as SCALE_SPEC
from .nx_scale import NexusScaleLayerItem
from .nx_speed import SPEC as SPEED_SPEC
from .nx_speed import NexusSpeedLayerItem
from .nx_spin import SPEC as SPIN_SPEC
from .nx_spin import NexusSpinLayerItem
from .nx_splash import SPEC as SPLASH_SPEC
from .nx_sticky import SPEC as STICKY_SPEC
from .nx_sticky import NexusStickyItem
from .nx_trail import SPEC as TRAIL_SPEC
from .nx_trail import NexusTrailEmitterItem
from .nx_turbulence import SPEC as TURBULENCE_SPEC
from .nx_turbulence import NexusTurbulenceLayerItem
from .nx_upres import SPEC as UPRES_SPEC
from .nx_upres import NexusUpresEmitterItem
from .nx_vorticity import SPEC as VORTICITY_SPEC
from .nx_wave import SPEC as WAVE_SPEC
from .nx_wind import SPEC as WIND_SPEC

NEXUS_ENUM_DEFAULTS = {}

for _s in (
    CACHE_SPEC,
    AVOID_SPEC,
    BLEND_SPEC,
    COLLIDER_SPEC,
    COLOR_SPEC,
    CONSTRAINTS_SPEC,
    COVER_SPEC,
    DIRECTION_SPEC,
    EMITTER_SPEC,
    EXPLOSIAFX_SPEC,
    FALLOFF_SPEC,
    FLOCK_SPEC,
    FLUIDS_SPEC,
    FOLLOW_GEO_SPEC,
    INFECTIO_SPEC,
    LIMIT_SPEC,
    MESHER_SPEC,
    QUESTION_SPEC,
    SCALE_SPEC,
    SPEED_SPEC,
    SPIN_SPEC,
    TURBULENCE_SPEC,
    WAVE_SPEC,
):
    if _s.enum_defaults:
        NEXUS_ENUM_DEFAULTS.update(_s.enum_defaults)

ALL_SPECS = (
    CACHE_SPEC,
    ATTRACT_SPEC,
    AVOID_SPEC,
    BLEND_SPEC,
    COLLIDER_SPEC,
    COLOR_SPEC,
    CONSTRAINTS_SPEC,
    COVER_SPEC,
    DIRECTION_SPEC,
    DRAG_SPEC,
    EMITTER_SPEC,
    EXPLOSIAFX_SPEC,
    EXPLODE_SPEC,
    FALLOFF_SPEC,
    FLOCK_SPEC,
    FLUIDS_SPEC,
    FOLLOW_GEO_SPEC,
    GENERATOR_SPEC,
    GRAVITY_SPEC,
    GROUP_SPEC,
    INFECTIO_SPEC,
    KILL_SPEC,
    LIMIT_SPEC,
    MESHER_SPEC,
    PUSH_SPEC,
    QUESTION_SPEC,
    ROTATE_SPEC,
    SCALE_SPEC,
    SPEED_SPEC,
    SPIN_SPEC,
    SPLASH_SPEC,
    STICKY_SPEC,
    TRAIL_SPEC,
    TURBULENCE_SPEC,
    UPRES_SPEC,
    VORTICITY_SPEC,
    WAVE_SPEC,
    WIND_SPEC,
)


def _on_enabled_update(self, context):
    """Cascade disable/restore children when a modifier is toggled."""
    scene = context.scene
    if not hasattr(scene, "nexus_pipeline"):
        return
    pipeline = scene.nexus_pipeline

    owner = None
    for obj in bpy.data.objects:
        try:
            if obj.nexus_modifier == self:
                owner = obj
                break
        except (AttributeError, ReferenceError):
            continue

    if owner is None:
        return

    from ..pipeline_manager.utils import (
        cascade_disable_children,
        restore_enabled_children,
    )

    for item in pipeline.modifier_order:
        if item.modifier == owner:
            if self.enabled:
                restore_enabled_children(pipeline, item)
            else:
                cascade_disable_children(pipeline, item)
            break


def _get_ui_section_items(self, context):
    if context is None:
        return [("OBJECT_PROPERTIES", "Object Properties", "")]

    obj = context.object
    if obj is None or "nexus_modifier_type" not in obj:
        return [("OBJECT_PROPERTIES", "Object Properties", "")]

    from ..modifiers import MODIFIER_REGISTRY
    from ..modifiers.base import NexusModifier

    mod_class = MODIFIER_REGISTRY.get(obj["nexus_modifier_type"])
    if mod_class is None:
        return [("OBJECT_PROPERTIES", "Object Properties", "")]

    items = [("OBJECT_PROPERTIES", "Object Properties", "")]

    for section_id, label in mod_class.get_tabs(self):
        items.append((section_id, label, ""))

    if issubclass(mod_class, NexusModifier):
        items.append(("GROUPS_AFFECTED", "Groups Affected", ""))
        items.append(("MAPPING", "Mapping", ""))
        items.append(("FALLOFF", "Falloff", ""))

    return items


_poll_group = make_allowed_types_poll(["NX_GROUP"])
_poll_falloff = make_allowed_types_poll(["NX_FALLOFF"])


class NexusAffectedGroupItem(bpy.types.PropertyGroup):
    obj: PointerProperty(name="Group", type=bpy.types.Object, poll=_poll_group)
    enabled: BoolProperty(name="Enabled", default=True)


class NexusFalloffItem(bpy.types.PropertyGroup):
    obj: PointerProperty(name="Falloff", type=bpy.types.Object)
    enabled: BoolProperty(name="Enabled", default=True)

    # -- Blend --
    falloff_blend_mode: EnumProperty(
        name="Blend",
        description="Blend mode for falloff",
        items=[
            ("NORMAL", "Normal", "Normal blend"),
            ("ADD", "Add", "Add blend"),
            ("SUB", "Subtract", "Subtract blend"),
            ("MULT", "Multiply", "Multiply blend"),
            ("DIFFERENCE", "Difference", "Difference blend"),
            ("SCREEN", "Screen", "Screen blend"),
            ("OVERLAY", "Overlay", "Overlay blend"),
            ("MIN", "Min", "Minimum blend"),
            ("MAX", "Max", "Maximum blend"),
        ],
        default="NORMAL",
    )
    falloff_blend_strength: FloatProperty(
        name="Strength",
        description="Blend strength",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )


class NexusObjectProperties(bpy.types.PropertyGroup):
    ui_section: EnumProperty(
        name="Section",
        description="Active UI section",
        items=_get_ui_section_items,
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Enable or disable this modifier",
        default=True,
        update=_on_enabled_update,
    )

    visible_in_editor: BoolProperty(
        name="Visible in Editor",
        description="Show gizmos for this modifier in the viewport",
        default=True,
    )

    is_cached: BoolProperty(default=False)
    is_cached_full: BoolProperty(default=False)

    # Pure scene-link list; not portable preset data.
    groups_affected: CollectionProperty(
        name="Groups Affected",
        type=NexusAffectedGroupItem,
    )
    groups_affected_index: IntProperty(
        name="Active Group Index",
        default=0,
        min=0,
    )
    groups_affected_drop_target: PointerProperty(
        name="Add Object",
        description="Pick or drop an object to add it to the Groups Affected list",
        type=bpy.types.Object,
        poll=_poll_group,
        update=make_drop_target_update(
            "groups_affected", "groups_affected_index", "groups_affected_drop_target"
        ),
    )

    # Pipeline hierarchy / handle-state list; needs its own restore design.
    falloffs: CollectionProperty(
        name="Falloffs",
        type=NexusFalloffItem,
    )
    falloffs_index: IntProperty(
        name="Active Falloff Index",
        default=0,
        min=0,
    )
    falloffs_drop_target: PointerProperty(
        name="Add Object",
        description="Pick or drop an object to add it to the Falloffs list",
        type=bpy.types.Object,
        poll=_poll_falloff,
        update=make_drop_target_update("falloffs", "falloffs_index", "falloffs_drop_target"),
    )

    mappings: CollectionProperty(
        name="Mappings",
        type=NexusMappingEntry,
    )
    mappings_index: IntProperty(
        name="Active Mapping Index",
        default=0,
        min=0,
    )

    cache_sources: CollectionProperty(
        name="Cache Sources",
        type=NexusCacheSourceItem,
    )
    cache_sources_index: IntProperty(
        name="Active Cache Source Index",
        default=0,
        min=0,
    )


for _spec in ALL_SPECS:
    NexusObjectProperties.__annotations__.update(_spec.build_properties_dict())

NexusObjectProperties.__annotations__.update(get_pending_ghost_slots())

classes = [
    NexusMappingEntry,
    NexusCacheSourceItem,
    NexusAffectedGroupItem,
    NexusAvoidItem,
    NexusColliderItem,
    NexusEmitterObjectItem,
    NexusEmitterExtendedDataItem,
    NexusEmitterGroupItem,
    NexusEmitterModifierItem,
    NexusCoverItem,
    NexusColorLayerItem,
    NexusFalloffItem,
    NexusFlockAvoidanceItem,
    NexusFlockBehaviorItem,
    NexusFlockReactionItem,
    NexusDirectionLayerItem,
    NexusKillItem,
    NexusFollowGeoExtendedItem,
    NexusFollowGeoItem,
    NexusGeneratorLayerItem,
    NexusGeneratorSourceEmitterItem,
    NEXUS_UL_generator_layers,
    NEXUS_UL_cache_sources,
    NexusLimitLayerItem,
    NexusMesherLayerItem,
    NexusScaleLayerItem,
    NexusStickyItem,
    NexusTrailEmitterItem,
    NexusSpeedLayerItem,
    NexusSpinLayerItem,
    NexusInfectioSeedItem,
    NexusTurbulenceLayerItem,
    NexusUpresEmitterItem,
    NexusConstraintLayerItem,
    NexusEFXSourceItem,
    NexusEFXColliderItem,
    NexusEFXForceLayerItem,
    NexusEFXPAdvectItem,
    NexusQuestionItem,
    NexusObjectProperties,
]


def _attach_runtime_item_sync_specs() -> None:
    """Ensure registered RNA classes expose latest class-level _sync_specs."""
    for spec in ALL_SPECS:
        for item_cls in spec.item_classes:
            sync_specs = getattr(item_cls, "_sync_specs", None)
            if not sync_specs:
                continue
            runtime_cls = getattr(bpy.types, item_cls.__name__, None)
            if runtime_cls is None:
                continue
            setattr(runtime_cls, "_sync_specs", sync_specs)


def register():
    for spec in ALL_SPECS:
        spec.register()

    from bpy.utils import register_class

    for cls in classes:
        try:
            register_class(cls)
        except ValueError:
            pass

    _attach_runtime_item_sync_specs()

    bpy.types.Object.nexus_modifier = PointerProperty(type=NexusObjectProperties)


def unregister():
    del bpy.types.Object.nexus_modifier

    from bpy.utils import unregister_class

    for cls in reversed(classes):
        try:
            unregister_class(cls)
        except RuntimeError:
            pass

    from ..libs.modifier_spec import clear_modifier_spec_registry
    from ..libs.theron_sync import clear_sync_registry

    clear_sync_registry()
    clear_modifier_spec_registry()
