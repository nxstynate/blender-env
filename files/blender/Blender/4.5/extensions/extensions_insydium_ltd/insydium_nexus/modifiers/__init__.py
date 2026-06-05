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

from .base import NexusModifier, UIFlags
from .nx_cache import NXCacheModifier
from .nx_attract import NXAttractModifier
from .nx_avoid import NXAvoidModifier
from .nx_blend import NXBlendModifier
from .nx_collider import NXColliderModifier
from .nx_color import NXColorModifier
from .nx_constraints import NXConstraintsModifier
from .nx_cover import NXCoverModifier
from .nx_direction import NXDirectionModifier
from .nx_drag import NXDragModifier
from .nx_emitter import NXEmitterModifier
from .nx_explode import NXExplodeModifier
from .nx_explosiafx import NXExplosiaFXModifier
from .nx_falloff import NexusFalloff
from .nx_flock import NXFlockModifier
from .nx_fluids import NXFluidsModifier
from .nx_follow_geo import NXFollowGeoModifier
from .nx_generator import NXGeneratorModifier
from .nx_gravity import NXGravityModifier
from .nx_group import NexusGroup
from .nx_infectio import NXInfectioModifier
from .nx_kill import NXKillModifier
from .nx_limit import NXLimitModifier
from .nx_mesher import NXMesherModifier
from .nx_push import NXPushModifier
from .nx_question import NXQuestionModifier
from .nx_rotate import NXRotateModifier
from .nx_scale import NXScaleModifier
from .nx_speed import NXSpeedModifier
from .nx_spin import NXSpinModifier
from .nx_splash import NXSplashModifier
from .nx_sticky import NXStickyModifier
from .nx_trail import NXTrailModifier
from .nx_turbulence import NXTurbulenceModifier
from .nx_upres import NXUpresModifier
from .nx_vorticity import NXVorticityModifier
from .nx_wave import NXWaveModifier
from .nx_wind import NXWindModifier

MODIFIER_REGISTRY = {
    "NX_CACHE": NXCacheModifier,
    "NX_WIND": NXWindModifier,
    "NX_GRAVITY": NXGravityModifier,
    "NX_ATTRACT": NXAttractModifier,
    "NX_AVOID": NXAvoidModifier,
    "NX_BLEND": NXBlendModifier,
    "NX_COVER": NXCoverModifier,
    "NX_FLUIDS": NXFluidsModifier,
    "NX_FLOCK": NXFlockModifier,
    "NX_EXPLODE": NXExplodeModifier,
    "NX_EXPLOSIAFX": NXExplosiaFXModifier,
    "NX_FALLOFF": NexusFalloff,
    "NX_GENERATOR": NXGeneratorModifier,
    "NX_DIRECTION": NXDirectionModifier,
    "NX_DRAG": NXDragModifier,
    "NX_MESHER": NXMesherModifier,
    "NX_WAVE": NXWaveModifier,
    "NX_EMITTER": NXEmitterModifier,
    "NX_PUSH": NXPushModifier,
    "NX_ROTATE": NXRotateModifier,
    "NX_SCALE": NXScaleModifier,
    "NX_SPEED": NXSpeedModifier,
    "NX_SPIN": NXSpinModifier,
    "NX_SPLASH": NXSplashModifier,
    "NX_COLLIDER": NXColliderModifier,
    "NX_COLOR": NXColorModifier,
    "NX_CONSTRAINTS": NXConstraintsModifier,
    "NX_KILL": NXKillModifier,
    "NX_LIMIT": NXLimitModifier,
    "NX_TURBULENCE": NXTurbulenceModifier,
    "NX_FOLLOW_GEO": NXFollowGeoModifier,
    "NX_STICKY": NXStickyModifier,
    "NX_VORTICITY": NXVorticityModifier,
    "NX_INFECTIO": NXInfectioModifier,
    "NX_TRAIL": NXTrailModifier,
    "NX_UPRES": NXUpresModifier,
    "NX_GROUP": NexusGroup,
    "NX_QUESTION": NXQuestionModifier,
}


def get_modifier_class(modifier_type):
    return MODIFIER_REGISTRY.get(modifier_type)


def get_all_modifier_types():
    return list(MODIFIER_REGISTRY.keys())


def cleanup():
    from .base import NexusModifier

    for mod_cls in MODIFIER_REGISTRY.values():
        if mod_cls.on_state_clear is NexusModifier.on_state_clear:
            continue
        mod_cls.on_state_clear(free_resources=True)


def register():
    pass


def unregister():
    cleanup()


__all__ = [
    "NexusModifier",
    "NXCacheModifier",
    "UIFlags",
    "NXWindModifier",
    "NXGravityModifier",
    "NXAttractModifier",
    "NXAvoidModifier",
    "NXBlendModifier",
    "NXCoverModifier",
    "NXFluidsModifier",
    "NXFlockModifier",
    "NXExplodeModifier",
    "NXExplosiaFXModifier",
    "NexusFalloff",
    "NXGeneratorModifier",
    "NXDirectionModifier",
    "NXDragModifier",
    "NXMesherModifier",
    "NXWaveModifier",
    "NXEmitterModifier",
    "NXPushModifier",
    "NXRotateModifier",
    "NXScaleModifier",
    "NXSpeedModifier",
    "NXSpinModifier",
    "NXSplashModifier",
    "NXColliderModifier",
    "NXColorModifier",
    "NXConstraintsModifier",
    "NXKillModifier",
    "NXLimitModifier",
    "NXTurbulenceModifier",
    "NXFollowGeoModifier",
    "NXStickyModifier",
    "NXVorticityModifier",
    "NXInfectioModifier",
    "NXTrailModifier",
    "NXUpresModifier",
    "NexusGroup",
    "NXQuestionModifier",
    "MODIFIER_REGISTRY",
    "get_modifier_class",
    "get_all_modifier_types",
    "register",
    "unregister",
    "cleanup",
]
