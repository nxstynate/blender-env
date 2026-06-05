"""Auto-generated ctypes bindings from theron.h

Generated: 2026-06-01 22:07 UTC
Source: theron.h

Do not edit manually. Re-generate with:
    python tools/generate_theron_bindings.py
"""

import ctypes
import sys
from enum import IntEnum


# =============================================================================
# Structs
# =============================================================================


class TrVec2(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float)]


class TrDVec2(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class TrVec3(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("z", ctypes.c_float),
    ]


class TrVec4(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("z", ctypes.c_float),
        ("w", ctypes.c_float),
    ]


class TrDVec3(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_double),
        ("y", ctypes.c_double),
        ("z", ctypes.c_double),
    ]


class TrMatrix(ctypes.Structure):
    _fields_ = [
        ("off", TrVec3),
        ("v1", TrVec3),
        ("v2", TrVec3),
        ("v3", TrVec3),
    ]


class TrDMatrix(ctypes.Structure):
    _fields_ = [
        ("off", TrDVec3),
        ("v1", TrDVec3),
        ("v2", TrDVec3),
        ("v3", TrDVec3),
    ]


class TrTime(ctypes.Structure):
    _fields_ = [("numerator", ctypes.c_int64), ("denominator", ctypes.c_int64)]


class TrPolygon(ctypes.Structure):
    _fields_ = [
        ("a", ctypes.c_int32),
        ("b", ctypes.c_int32),
        ("c", ctypes.c_int32),
        ("d", ctypes.c_int32),
    ]


class TrSegment(ctypes.Structure):
    _fields_ = [("cnt", ctypes.c_int32), ("closed", ctypes.c_bool)]


class TrNoisePrefs(ctypes.Structure):
    _fields_ = [
        ("octaves", ctypes.c_int),
        ("scale", ctypes.c_float),
        ("persistence", ctypes.c_float),
        ("lacunarity", ctypes.c_float),
        ("frequency", ctypes.c_float),
        ("amplitude", ctypes.c_float),
        ("absolute", ctypes.c_int),
    ]


class TrBufferExport(ctypes.Structure):
    if sys.platform == "win32":
        _fields_ = [
        ("handle", ctypes.c_void_p),
        ("size", ctypes.c_uint64),
        ("uid", ctypes.c_uint64),
    ]
    elif sys.platform == "darwin":
        _fields_ = [
        ("mtlBuffer", ctypes.c_void_p),
        ("size", ctypes.c_uint64),
        ("uid", ctypes.c_uint64),
    ]
    else:
        _fields_ = [
        ("fileDescriptor", ctypes.c_int),
        ("size", ctypes.c_uint64),
        ("uid", ctypes.c_uint64),
    ]


class TrNotify(ctypes.Structure):
    _fields_ = [
        ("kind", ctypes.c_int),
        ("severity", ctypes.c_int),
        ("title", ctypes.c_char * 128),
        ("body", ctypes.c_char * 1024),
        ("url", ctypes.c_char * 512),
    ]


class TrMappingParamInfo(ctypes.Structure):
    _fields_ = [
        ("param", ctypes.c_int32),
        ("group", ctypes.c_int32),
        ("name", ctypes.c_char_p),
    ]


class TrMappingLayerInfo(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint64)]


class TrGradientKnot(ctypes.Structure):
    _fields_ = [
        ("col", TrDVec3),
        ("pos", ctypes.c_double),
        ("interpolation", ctypes.c_int),
    ]


class TrSpline2DKnot(ctypes.Structure):
    _fields_ = [
        ("pos", TrDVec2),
        ("vTangentLeft", TrDVec2),
        ("vTangentRight", TrDVec2),
        ("interpolation", ctypes.c_int),
    ]


class TrTrailSourceDesc(ctypes.Structure):
    _fields_ = [
        ("structSize", ctypes.c_int32),
        ("emitterIndex", ctypes.c_uint32),
        ("enabled", ctypes.c_int32),
        ("lengthMode", ctypes.c_int32),
        ("trailTime", TrTime),
        ("trailDistance", ctypes.c_float),
        ("frameSampling", ctypes.c_int32),
        ("fullSceneTrail", ctypes.c_int32),
        ("colorMode", ctypes.c_int32),
        ("color", ctypes.c_float * 4),
        ("thicknessMode", ctypes.c_int32),
        ("thicknessValue", ctypes.c_float),
        ("thicknessVariation", ctypes.c_float),
        ("thicknessSplineMax", ctypes.c_float),
        ("thicknessSplineTime", TrTime),
        ("noThicknessColorData", ctypes.c_int32),
        ("trailColorMode", ctypes.c_int32),
        ("freezeMode", ctypes.c_int32),
        ("freezeMovement", ctypes.c_int32),
        ("freezeScale", ctypes.c_int32),
        ("variation", ctypes.c_float),
        ("algorithm", ctypes.c_int32),
        ("segmentLength", ctypes.c_int32),
        ("gapLength", ctypes.c_int32),
        ("multipleMode", ctypes.c_int32),
        ("sequenceCount", ctypes.c_int32),
        ("sequenceLength", ctypes.c_int32),
        ("emitChains", ctypes.c_int32),
        ("minDistance", ctypes.c_float),
        ("maxDistance", ctypes.c_float),
        ("maxConnections", ctypes.c_int32),
        ("skipParticles", ctypes.c_int32),
        ("destinationGroups", ctypes.c_int32),
        ("specificGroupId", ctypes.c_int32),
        ("maxNumber", ctypes.c_int32),
        ("clusterDistance", ctypes.c_float),
        ("minParticlesInCluster", ctypes.c_int32),
    ]


class TrTrailSplineRange(ctypes.Structure):
    _fields_ = [
        ("firstPoint", ctypes.c_int32),
        ("pointCount", ctypes.c_int32),
        ("sourceId", ctypes.c_uint32),
        ("flags", ctypes.c_int32),
    ]


class TrTrailSourceInfo(ctypes.Structure):
    _fields_ = [
        ("sourceId", ctypes.c_uint32),
        ("sourceIndex", ctypes.c_int32),
        ("emitterIndex", ctypes.c_uint32),
        ("enabled", ctypes.c_int32),
    ]


class TrTrailBufferBundle(ctypes.Structure):
    _fields_ = [
        ("structSize", ctypes.c_int32),
        ("reserved0", ctypes.c_int32),
        ("uid", ctypes.c_uint64),
        ("history", TrBufferExport),
        ("topology", TrBufferExport),
        ("color", TrBufferExport),
        ("thickness", TrBufferExport),
        ("sourceLocalIndices", TrBufferExport),
        ("liveEndpoint", TrBufferExport),
        ("slotsPerParticle", ctypes.c_int32),
        ("historyParticleCapacity", ctypes.c_int32),
        ("sourceCount", ctypes.c_int32),
        ("sourceLocalStride", ctypes.c_int32),
    ]


# =============================================================================
# Enums
# =============================================================================


class TrResult(IntEnum):
    TR_RESULT_SUCCESS = 0
    TR_RESULT_UNKNOWN = 1
    TR_RESULT_OUT_OF_RANGE = 2
    TR_RESULT_BAD_CAST = 3
    TR_RESULT_RUNTIME_ERROR = 4
    TR_RESULT_GPU_ERROR = 5
    TR_RESULT_BAD_ARGUMENTS = 6
    TR_RESULT_MEMORY_ALLOC = 7
    TR_RESULT_DEVICE_MEMORY_ALLOC = 8
    TR_RESULT_LICENSE_FAIL = 9
    TR_RESULT_LICENSE_NO_NET = 10
    TR_RESULT_LICENSE_NOT_SET = 11


class TrNoiseType(IntEnum):
    TR_NOISE_TYPE_SIMPLEX = 0
    TR_NOISE_TYPE_FBM = 1
    TR_NOISE_TYPE_TURBULENCE = 2
    TR_NOISE_TYPE_WAVY_TURBULENCE = 3
    TR_NOISE_TYPE_VORONOISE = 4
    TR_NOISE_TYPE_CUBIC = 5


class TrParticleProperty(IntEnum):
    TR_PARTICLE_PROPERTY_POSITION = 0
    TR_PARTICLE_PROPERTY_VELOCITY = 1
    TR_PARTICLE_PROPERTY_ORIGIN_POS = 2
    TR_PARTICLE_PROPERTY_COLOR = 3
    TR_PARTICLE_PROPERTY_SCALE = 4
    TR_PARTICLE_PROPERTY_ROTATION = 5
    TR_PARTICLE_PROPERTY_FLUID_SURFACE = 6
    TR_PARTICLE_PROPERTY_UVW = 7
    TR_PARTICLE_PROPERTY_ROTATION_UP = 8
    TR_PARTICLE_PROPERTY_MASS = 9
    TR_PARTICLE_PROPERTY_DELTA = 10
    TR_PARTICLE_PROPERTY_TIME = 11
    TR_PARTICLE_PROPERTY_RADIUS = 12
    TR_PARTICLE_PROPERTY_GROUP = 13
    TR_PARTICLE_PROPERTY_ID = 14
    TR_PARTICLE_PROPERTY_FLAGS = 15
    TR_PARTICLE_PROPERTY_DISTANCE = 16
    TR_PARTICLE_PROPERTY_FRICTION = 17
    TR_PARTICLE_PROPERTY_BOUNCE = 18
    TR_PARTICLE_PROPERTY_EMITTER_INDEX = 19
    TR_PARTICLE_PROPERTY_GRANULAR = 20
    TR_PARTICLE_PROPERTY_LIFE = 21
    TR_PARTICLE_PROPERTY_VERTEX_WEIGHT = 22
    TR_PARTICLE_PROPERTY_DENSITY = 23
    TR_PARTICLE_PROPERTY_NB_DIST = 24
    TR_PARTICLE_PROPERTY_MOD_TIME = 25
    TR_PARTICLE_PROPERTY_CUSTOM_DATA = 26
    TR_PARTICLE_PROPERTY_VERTEX_INDEX = 27
    TR_PARTICLE_PROPERTY_FOAM = 28
    TR_PARTICLE_PROPERTY_DISPLAY = 29
    TR_PARTICLE_PROPERTY_SUBFRAME_DELTA = 30
    TR_PARTICLE_PROPERTY_SMOKE = 31
    TR_PARTICLE_PROPERTY_TEMPERATURE = 32
    TR_PARTICLE_PROPERTY_FUEL = 33
    TR_PARTICLE_PROPERTY___SIZE__ = 34


class TrParticleCopyMode(IntEnum):
    TR_PARTICLE_COPY_MODE_GPU_ONLY = 0
    TR_PARTICLE_COPY_MODE_GPU_CPU = 1
    TR_PARTICLE_COPY_MODE_CPU_GPU = 2


class TrHandedness(IntEnum):
    TR_HANDEDNESS_LEFT = 0
    TR_HANDEDNESS_RIGHT = 1


class TrModifierType(IntEnum):
    TR_MODIFIER_TYPE_GRAVITY = 0
    TR_MODIFIER_TYPE_PUSH = 1
    TR_MODIFIER_TYPE_MESHER = 2
    TR_MODIFIER_TYPE_TURBULENCE = 3
    TR_MODIFIER_TYPE_WIND = 4
    TR_MODIFIER_TYPE_EXPLOSIAFX = 5
    TR_MODIFIER_TYPE_KILL = 6
    TR_MODIFIER_TYPE_SPH_FLUIDS = 7
    TR_MODIFIER_TYPE_PBD_FLUIDS = 8
    TR_MODIFIER_TYPE_COLOR = 9
    TR_MODIFIER_TYPE_SPLASH = 10
    TR_MODIFIER_TYPE_WAVE = 11
    TR_MODIFIER_TYPE_DIRECTION = 12
    TR_MODIFIER_TYPE_ROTATE = 13
    TR_MODIFIER_TYPE_ATTRACT = 14
    TR_MODIFIER_TYPE_DRAG = 15
    TR_MODIFIER_TYPE_SCALE = 16
    TR_MODIFIER_TYPE_INFECTIO = 17
    TR_MODIFIER_TYPE_AVOID = 18
    TR_MODIFIER_TYPE_SPEED = 19
    TR_MODIFIER_TYPE_BLEND = 20
    TR_MODIFIER_TYPE_EXPLODE = 21
    TR_MODIFIER_TYPE_SPIN = 22
    TR_MODIFIER_TYPE_COVER = 23
    TR_MODIFIER_TYPE_VORTICITY = 24
    TR_MODIFIER_TYPE_LIMIT = 25
    TR_MODIFIER_TYPE_FOLLOW_SURFACE = 26
    TR_MODIFIER_TYPE_UPRES = 27
    TR_MODIFIER_TYPE_STICKY = 28
    TR_MODIFIER_TYPE_FLOCK = 29
    TR_MODIFIER_TYPE_CONSTRAINTS = 30
    TR_MODIFIER_TYPE_FLIP_FLUIDS = 31
    TR_MODIFIER_TYPE_QUESTION = 32


class TrEFXChannel(IntEnum):
    TR_EFX_CHANNEL_SMOKE = 0
    TR_EFX_CHANNEL_TEMPERATURE = 1
    TR_EFX_CHANNEL_FUEL = 2
    TR_EFX_CHANNEL_COLOR_R = 3
    TR_EFX_CHANNEL_COLOR_G = 4
    TR_EFX_CHANNEL_COLOR_B = 5


class TrGradientKnotInterpolation(IntEnum):
    TR_GRADIENT_KNOT_INTERPOLATION_CONSTANT = 0
    TR_GRADIENT_KNOT_INTERPOLATION_LINEAR = 1
    TR_GRADIENT_KNOT_INTERPOLATION_EASE = 2
    TR_GRADIENT_KNOT_INTERPOLATION_CARDINAL = 3
    TR_GRADIENT_KNOT_INTERPOLATION_B_SPLINE = 4


class TrGradientColorMode(IntEnum):
    TR_GRADIENT_COLOR_MODE_RGB = 0
    TR_GRADIENT_COLOR_MODE_HSV = 1
    TR_GRADIENT_COLOR_MODE_HSL = 2


class TrGradientHueInterpolation(IntEnum):
    TR_GRADIENT_HUE_INTERPOLATION_NEAR = 0
    TR_GRADIENT_HUE_INTERPOLATION_FAR = 1
    TR_GRADIENT_HUE_INTERPOLATION_CW = 2
    TR_GRADIENT_HUE_INTERPOLATION_CCW = 3


class TrSplineKnotInterpolation(IntEnum):
    TR_SPLINE_KNOT_INTERPOLATION_LINEAR = 0
    TR_SPLINE_KNOT_INTERPOLATION_CARDINAL = 1


# =============================================================================
# Function signatures
# =============================================================================

def setup_function_signatures(lib: ctypes.CDLL) -> None:
    """Auto-generated from theron.h. Do not edit manually."""

    lib.trGetVersion.restype = None
    lib.trGetVersion.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]

    lib.trGetVersionStr.restype = ctypes.c_char_p
    lib.trGetVersionStr.argtypes = []

    lib.trGetBuildType.restype = ctypes.c_char_p
    lib.trGetBuildType.argtypes = []

    lib.trGetBuildDate.restype = ctypes.c_int64
    lib.trGetBuildDate.argtypes = []

    lib.trSubmitBugReport.restype = ctypes.c_int
    lib.trSubmitBugReport.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_int),
    ]

    lib.trSetLicenseInfo.restype = ctypes.c_int
    lib.trSetLicenseInfo.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]

    lib.trInitialise.restype = ctypes.c_int
    lib.trInitialise.argtypes = []

    lib.trShutdown.restype = ctypes.c_int
    lib.trShutdown.argtypes = []

    lib.trUsageRecord.restype = ctypes.c_int
    lib.trUsageRecord.argtypes = [ctypes.c_char_p]

    lib.trUsageFlush.restype = ctypes.c_int
    lib.trUsageFlush.argtypes = []

    lib.trUsageSetConsent.restype = ctypes.c_int
    lib.trUsageSetConsent.argtypes = [ctypes.c_int]

    lib.trPollNotify.restype = ctypes.c_int
    lib.trPollNotify.argtypes = [ctypes.POINTER(TrNotify), ctypes.POINTER(ctypes.c_int)]

    lib.trSelectDevice.restype = ctypes.c_int
    lib.trSelectDevice.argtypes = [ctypes.c_int]

    lib.trSetCompiledShaderCacheDir.restype = ctypes.c_int
    lib.trSetCompiledShaderCacheDir.argtypes = [ctypes.c_char_p]

    lib.trEnsureCompiledShaders_Async.restype = ctypes.c_int
    lib.trEnsureCompiledShaders_Async.argtypes = []

    lib.trCheckShaderCacheStatus.restype = ctypes.c_int
    lib.trCheckShaderCacheStatus.argtypes = [ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]

    lib.trCreateModifierPipeline.restype = ctypes.c_int
    lib.trCreateModifierPipeline.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.POINTER(TrVec3), ctypes.POINTER(TrVec3), ctypes.c_double]

    lib.trDestroyModifierPipeline.restype = ctypes.c_int
    lib.trDestroyModifierPipeline.argtypes = [ctypes.c_void_p]

    lib.trExecuteFrame.restype = ctypes.c_int
    lib.trExecuteFrame.argtypes = [ctypes.c_void_p, ctypes.c_int64]

    lib.trAddModifier.restype = ctypes.c_int
    lib.trAddModifier.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]

    lib.trModifierMove.restype = ctypes.c_int
    lib.trModifierMove.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    lib.trGetModifierContainer.restype = ctypes.c_int
    lib.trGetModifierContainer.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trGetMappingParamCount.restype = ctypes.c_int
    lib.trGetMappingParamCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32)]

    lib.trGetMappingParam.restype = ctypes.c_int
    lib.trGetMappingParam.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(TrMappingParamInfo)]

    lib.trGetMappingGroupCount.restype = ctypes.c_int
    lib.trGetMappingGroupCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32)]

    lib.trGetMappingGroup.restype = ctypes.c_int
    lib.trGetMappingGroup.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.POINTER(ctypes.c_char))]

    lib.trGetMappingToCount.restype = ctypes.c_int
    lib.trGetMappingToCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32)]

    lib.trGetMappingTo.restype = ctypes.c_int
    lib.trGetMappingTo.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(TrMappingParamInfo)]

    lib.trGetMappingToGroupCount.restype = ctypes.c_int
    lib.trGetMappingToGroupCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32)]

    lib.trGetMappingToGroup.restype = ctypes.c_int
    lib.trGetMappingToGroup.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.POINTER(ctypes.c_char))]

    lib.trGetMappingLayerCount.restype = ctypes.c_int
    lib.trGetMappingLayerCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32)]

    lib.trGetMappingLayer.restype = ctypes.c_int
    lib.trGetMappingLayer.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(TrMappingLayerInfo)]

    lib.trGetEFXChannel.restype = ctypes.c_int
    lib.trGetEFXChannel.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_float),
    ]

    lib.trGetEFXChannelUpres.restype = ctypes.c_int
    lib.trGetEFXChannelUpres.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_float),
    ]

    lib.trGetEFXGridSize.restype = ctypes.c_int
    lib.trGetEFXGridSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]

    lib.trGetEFXVoxelSize.restype = ctypes.c_int
    lib.trGetEFXVoxelSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float)]

    lib.trGetEFXVoxelSizeUpres.restype = ctypes.c_int
    lib.trGetEFXVoxelSizeUpres.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float)]

    lib.trIsEFXChannelAvailable.restype = ctypes.c_int
    lib.trIsEFXChannelAvailable.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]

    lib.trIsEFXChannelUpresAvailable.restype = ctypes.c_int
    lib.trIsEFXChannelUpresAvailable.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]

    lib.trGetEFXSpeed.restype = ctypes.c_int
    lib.trGetEFXSpeed.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_float),
    ]

    lib.trGetEFXChannelsSmoke.restype = ctypes.c_int
    lib.trGetEFXChannelsSmoke.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_float),
    ]

    lib.trGetEFXChannelsTemperature.restype = ctypes.c_int
    lib.trGetEFXChannelsTemperature.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_float),
    ]

    lib.trGetEFXSolidSDFVoxelVertex.restype = ctypes.c_int
    lib.trGetEFXSolidSDFVoxelVertex.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_float),
    ]

    lib.trGetEFXVoxelIsActive.restype = ctypes.c_int
    lib.trGetEFXVoxelIsActive.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_int)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_float),
    ]

    lib.trGetEFXVelocity.restype = ctypes.c_int
    lib.trGetEFXVelocity.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_float),
    ]

    lib.trGetEFXRegularizedDomain.restype = ctypes.c_int
    lib.trGetEFXRegularizedDomain.argtypes = [
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_float),
    ]

    lib.trGetEFXVRAMPersistent_GiB.restype = ctypes.c_int
    lib.trGetEFXVRAMPersistent_GiB.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]

    lib.trGetEFXVRAMPeak_GiB.restype = ctypes.c_int
    lib.trGetEFXVRAMPeak_GiB.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]

    lib.trGetFLIPFluidsLiquidPhi.restype = ctypes.c_int
    lib.trGetFLIPFluidsLiquidPhi.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_float),
    ]

    lib.trGetFLIPFluidsSolidSDF.restype = ctypes.c_int
    lib.trGetFLIPFluidsSolidSDF.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_float),
    ]

    lib.trGetFLIPFluidsVelocity.restype = ctypes.c_int
    lib.trGetFLIPFluidsVelocity.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_float),
    ]

    lib.trGetFLIPFluidsRegularizedDomain.restype = ctypes.c_int
    lib.trGetFLIPFluidsRegularizedDomain.argtypes = [
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_float),
    ]

    lib.trFreeModifier.restype = ctypes.c_int
    lib.trFreeModifier.argtypes = [ctypes.c_void_p]

    lib.trCreateEmitter.restype = ctypes.c_int
    lib.trCreateEmitter.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trGetEmitterContainer.restype = ctypes.c_int
    lib.trGetEmitterContainer.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trGetEmitterObjectIndex.restype = ctypes.c_int
    lib.trGetEmitterObjectIndex.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32)]

    lib.trFreeEmitter.restype = ctypes.c_int
    lib.trFreeEmitter.argtypes = [ctypes.c_void_p]

    lib.trCreateParticleGroup.restype = ctypes.c_int
    lib.trCreateParticleGroup.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trAddEmitterToGroup.restype = ctypes.c_int
    lib.trAddEmitterToGroup.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    lib.trRemoveEmitterFromGroup.restype = ctypes.c_int
    lib.trRemoveEmitterFromGroup.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    lib.trFreeParticleGroup.restype = ctypes.c_int
    lib.trFreeParticleGroup.argtypes = [ctypes.c_void_p]

    lib.trCreateFalloff.restype = ctypes.c_int
    lib.trCreateFalloff.argtypes = [ctypes.POINTER(ctypes.c_void_p)]

    lib.trFreeFalloff.restype = ctypes.c_int
    lib.trFreeFalloff.argtypes = [ctypes.c_void_p]

    lib.trCreateCamera.restype = ctypes.c_int
    lib.trCreateCamera.argtypes = [ctypes.POINTER(ctypes.c_void_p)]

    lib.trSetCameraFov.restype = ctypes.c_int
    lib.trSetCameraFov.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_double]

    lib.trSetCameraProjection.restype = ctypes.c_int
    lib.trSetCameraProjection.argtypes = [ctypes.c_void_p, ctypes.c_int32]

    lib.trSetCameraOrthoScale.restype = ctypes.c_int
    lib.trSetCameraOrthoScale.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_double]

    lib.trFreeObject.restype = ctypes.c_int
    lib.trFreeObject.argtypes = [ctypes.c_void_p]

    lib.trModifierSetMg.restype = ctypes.c_int
    lib.trModifierSetMg.argtypes = [ctypes.c_void_p, ctypes.POINTER(TrDMatrix)]

    lib.trEmitterSetMg.restype = ctypes.c_int
    lib.trEmitterSetMg.argtypes = [ctypes.c_void_p, ctypes.POINTER(TrDMatrix)]

    lib.trSetMg.restype = ctypes.c_int
    lib.trSetMg.argtypes = [ctypes.c_void_p, ctypes.POINTER(TrDMatrix)]

    lib.trGetContainer.restype = ctypes.c_int
    lib.trGetContainer.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trAddColliderMesh.restype = ctypes.c_int
    lib.trAddColliderMesh.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

    lib.trCreateCacheInstance.restype = ctypes.c_int
    lib.trCreateCacheInstance.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trBuildFullCache_Async.restype = ctypes.c_int
    lib.trBuildFullCache_Async.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    lib.trCancelCacheBuild.restype = ctypes.c_int
    lib.trCancelCacheBuild.argtypes = [ctypes.c_void_p]

    lib.trGetCacheStatus.restype = ctypes.c_int
    lib.trGetCacheStatus.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int64),
        ctypes.POINTER(ctypes.c_bool),
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    ]

    lib.trClearCache.restype = ctypes.c_int
    lib.trClearCache.argtypes = [ctypes.c_void_p]

    lib.trClearCacheFrame.restype = ctypes.c_int
    lib.trClearCacheFrame.argtypes = [ctypes.c_void_p, ctypes.c_int64]

    lib.trSetFps.restype = ctypes.c_int
    lib.trSetFps.argtypes = [ctypes.c_void_p, ctypes.c_double]

    lib.trSetSubsteps.restype = ctypes.c_int
    lib.trSetSubsteps.argtypes = [ctypes.c_void_p, ctypes.c_int64]

    lib.trSetMinMaxTime.restype = ctypes.c_int
    lib.trSetMinMaxTime.argtypes = [ctypes.c_void_p, TrTime, TrTime]

    lib.trCreateContainer.restype = ctypes.c_int
    lib.trCreateContainer.argtypes = [ctypes.POINTER(ctypes.c_void_p)]

    lib.trFreeContainer.restype = ctypes.c_int
    lib.trFreeContainer.argtypes = [ctypes.c_void_p]

    lib.trSetInt32.restype = ctypes.c_int
    lib.trSetInt32.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32]

    lib.trSetFloat.restype = ctypes.c_int
    lib.trSetFloat.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_double]

    lib.trSetBool.restype = ctypes.c_int
    lib.trSetBool.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_bool]

    lib.trSetTime.restype = ctypes.c_int
    lib.trSetTime.argtypes = [ctypes.c_void_p, ctypes.c_int32, TrTime]

    lib.trSetVector.restype = ctypes.c_int
    lib.trSetVector.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(TrDVec3)]

    lib.trSetMemory.restype = ctypes.c_int
    lib.trSetMemory.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_int64]

    lib.trSetLink.restype = ctypes.c_int
    lib.trSetLink.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p]

    lib.trSetString.restype = ctypes.c_int
    lib.trSetString.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_char_p]

    lib.trCreateNodeTree.restype = ctypes.c_int
    lib.trCreateNodeTree.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)]

    lib.trCreateGradient.restype = ctypes.c_int
    lib.trCreateGradient.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)]

    lib.trCreateSpline.restype = ctypes.c_int
    lib.trCreateSpline.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)]

    lib.trSetContainer.restype = ctypes.c_int
    lib.trSetContainer.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p]

    lib.trGetInt32.restype = ctypes.c_int
    lib.trGetInt32.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_int32)]

    lib.trGetFloat.restype = ctypes.c_int
    lib.trGetFloat.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_double)]

    lib.trGetBool.restype = ctypes.c_int
    lib.trGetBool.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_bool)]

    lib.trGetTime.restype = ctypes.c_int
    lib.trGetTime.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_double)]

    lib.trGetVector.restype = ctypes.c_int
    lib.trGetVector.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(TrDVec3)]

    lib.trGetNodeTree.restype = ctypes.c_int
    lib.trGetNodeTree.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)]

    lib.trGetMemory.restype = ctypes.c_int
    lib.trGetMemory.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_int64)]

    lib.trNodeTreeClear.restype = ctypes.c_int
    lib.trNodeTreeClear.argtypes = [ctypes.c_void_p]

    lib.trNodeTreeInsert.restype = ctypes.c_int
    lib.trNodeTreeInsert.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trSetNodeId.restype = ctypes.c_int
    lib.trSetNodeId.argtypes = [ctypes.c_void_p, ctypes.c_int32]

    lib.trSetNodeEnabled.restype = ctypes.c_int
    lib.trSetNodeEnabled.argtypes = [ctypes.c_void_p, ctypes.c_bool]

    lib.trSetNodeIconFlags.restype = ctypes.c_int
    lib.trSetNodeIconFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

    lib.trCreateNodeContainer.restype = ctypes.c_int
    lib.trCreateNodeContainer.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trGetNodeContainer.restype = ctypes.c_int
    lib.trGetNodeContainer.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trNodeTreeGetFirst.restype = ctypes.c_int
    lib.trNodeTreeGetFirst.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trNodeTreeGetLast.restype = ctypes.c_int
    lib.trNodeTreeGetLast.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trNodeTreeGetNext.restype = ctypes.c_int
    lib.trNodeTreeGetNext.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trNodeTreeGetPrev.restype = ctypes.c_int
    lib.trNodeTreeGetPrev.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trNodeTreeGetiNext.restype = ctypes.c_int
    lib.trNodeTreeGetiNext.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trNodeTreeGetUp.restype = ctypes.c_int
    lib.trNodeTreeGetUp.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trNodeTreeGetDown.restype = ctypes.c_int
    lib.trNodeTreeGetDown.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trSetNodeLink.restype = ctypes.c_int
    lib.trSetNodeLink.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    lib.trGetNodeLink.restype = ctypes.c_int
    lib.trGetNodeLink.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

    lib.trSetParticleCopyMode.restype = ctypes.c_int
    lib.trSetParticleCopyMode.argtypes = [ctypes.c_void_p, ctypes.c_int]

    lib.trGetParticleCount.restype = ctypes.c_int
    lib.trGetParticleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]

    lib.trGetParticlePosition.restype = ctypes.c_int
    lib.trGetParticlePosition.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(TrVec3)]

    lib.trGetParticleVelocity.restype = ctypes.c_int
    lib.trGetParticleVelocity.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(TrVec3)]

    lib.trGetParticleRadius.restype = ctypes.c_int
    lib.trGetParticleRadius.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_float)]

    lib.trGetParticleColour.restype = ctypes.c_int
    lib.trGetParticleColour.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(TrVec3)]

    lib.trGetParticleRotation.restype = ctypes.c_int
    lib.trGetParticleRotation.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(TrVec3)]

    lib.trGetParticleDisplayMode.restype = ctypes.c_int
    lib.trGetParticleDisplayMode.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_int32)]

    lib.trGetParticleEmitterIndex.restype = ctypes.c_int
    lib.trGetParticleEmitterIndex.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_int32)]

    lib.trGetParticlePropertyData.restype = ctypes.c_int
    lib.trGetParticlePropertyData.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]

    lib.trGetEmitterParticleData.restype = ctypes.c_int
    lib.trGetEmitterParticleData.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]

    lib.trGetEmitterParticleCount.restype = ctypes.c_int
    lib.trGetEmitterParticleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]

    lib.trGetParticleDataBufferExport.restype = ctypes.c_int
    lib.trGetParticleDataBufferExport.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(TrBufferExport)]

    lib.trGetParticleDrawModeBufferExports.restype = ctypes.c_int
    lib.trGetParticleDrawModeBufferExports.argtypes = [ctypes.c_void_p, ctypes.POINTER(TrBufferExport), ctypes.POINTER(TrBufferExport)]

    lib.trGetParticleDrawModeHostBuffers.restype = ctypes.c_int
    lib.trGetParticleDrawModeHostBuffers.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_int32)),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_uint32)),
    ]

    lib.trGetParticleIDLUTBufferExport.restype = ctypes.c_int
    lib.trGetParticleIDLUTBufferExport.argtypes = [ctypes.c_void_p, ctypes.POINTER(TrBufferExport), ctypes.POINTER(ctypes.c_uint64)]

    lib.trGetParticleConstraintsBufferExport.restype = ctypes.c_int
    lib.trGetParticleConstraintsBufferExport.argtypes = [ctypes.c_void_p, ctypes.POINTER(TrBufferExport)]

    lib.trParticleHasProperty.restype = ctypes.c_int
    lib.trParticleHasProperty.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]

    lib.trGetEmitterCount.restype = ctypes.c_int
    lib.trGetEmitterCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]

    lib.trGetEmitter.restype = ctypes.c_int
    lib.trGetEmitter.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]

    lib.trCreatePolygonObject.restype = ctypes.c_int
    lib.trCreatePolygonObject.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)]

    lib.trGetPolygonObjectPoints.restype = ctypes.c_int
    lib.trGetPolygonObjectPoints.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(TrDVec3))]

    lib.trGetPolygonObjectPolygons.restype = ctypes.c_int
    lib.trGetPolygonObjectPolygons.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(TrPolygon))]

    lib.trFreePolygonObject.restype = ctypes.c_int
    lib.trFreePolygonObject.argtypes = [ctypes.c_void_p]

    lib.trCreatePolygonObjectWithData.restype = ctypes.c_int
    lib.trCreatePolygonObjectWithData.argtypes = [
        ctypes.c_int32,
        ctypes.POINTER(TrDVec3),
        ctypes.c_int32,
        ctypes.POINTER(TrPolygon),
        ctypes.POINTER(ctypes.c_void_p),
    ]

    lib.trResizePolygonObject.restype = ctypes.c_int
    lib.trResizePolygonObject.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32]

    lib.trCreateLineObject.restype = ctypes.c_int
    lib.trCreateLineObject.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)]

    lib.trGetLineObjectPoints.restype = ctypes.c_int
    lib.trGetLineObjectPoints.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(TrDVec3))]

    lib.trGetLineObjectSegments.restype = ctypes.c_int
    lib.trGetLineObjectSegments.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(TrSegment))]

    lib.trFreeLineObject.restype = ctypes.c_int
    lib.trFreeLineObject.argtypes = [ctypes.c_void_p]

    lib.trCreateLineObjectWithData.restype = ctypes.c_int
    lib.trCreateLineObjectWithData.argtypes = [
        ctypes.c_int32,
        ctypes.POINTER(TrDVec3),
        ctypes.c_int32,
        ctypes.POINTER(TrSegment),
        ctypes.POINTER(ctypes.c_void_p),
    ]

    lib.trSetGradientKnot.restype = ctypes.c_int
    lib.trSetGradientKnot.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(TrGradientKnot)]

    lib.trResizeGradient.restype = ctypes.c_int
    lib.trResizeGradient.argtypes = [ctypes.c_void_p, ctypes.c_int32]

    lib.trSetGradientColorMode.restype = ctypes.c_int
    lib.trSetGradientColorMode.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]

    lib.trSetSplineKnot.restype = ctypes.c_int
    lib.trSetSplineKnot.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(TrSpline2DKnot)]

    lib.trResizeSpline.restype = ctypes.c_int
    lib.trResizeSpline.argtypes = [ctypes.c_void_p, ctypes.c_int32]

    lib.trNoisePrefsInit.restype = ctypes.c_int
    lib.trNoisePrefsInit.argtypes = [ctypes.POINTER(TrNoisePrefs)]

    lib.trNoiseEval1D.restype = ctypes.c_int
    lib.trNoiseEval1D.argtypes = [
        ctypes.POINTER(TrVec3),
        ctypes.POINTER(ctypes.c_float),
        ctypes.c_uint64,
        ctypes.c_int,
        ctypes.POINTER(TrNoisePrefs),
        ctypes.c_float,
    ]

    lib.trNoiseEval2D.restype = ctypes.c_int
    lib.trNoiseEval2D.argtypes = [ctypes.POINTER(TrVec3), ctypes.POINTER(TrVec2), ctypes.c_uint64, ctypes.c_int, ctypes.POINTER(TrNoisePrefs), ctypes.c_float]

    lib.trNoiseEval3D.restype = ctypes.c_int
    lib.trNoiseEval3D.argtypes = [ctypes.POINTER(TrVec3), ctypes.POINTER(TrVec3), ctypes.c_uint64, ctypes.c_int, ctypes.POINTER(TrNoisePrefs), ctypes.c_float]

    lib.trGenerateNoisePreview.restype = ctypes.c_int
    lib.trGenerateNoisePreview.argtypes = [
        ctypes.POINTER(ctypes.c_float),
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(TrNoisePrefs),
        ctypes.c_float,
        ctypes.c_float,
        ctypes.c_float,
        ctypes.c_float,
        ctypes.POINTER(ctypes.c_float),
        ctypes.c_int,
    ]

    lib.trGetAvailableVRAM.restype = ctypes.c_int
    lib.trGetAvailableVRAM.argtypes = [ctypes.POINTER(ctypes.c_uint64)]

    lib.trGetTotalVRAM.restype = ctypes.c_int
    lib.trGetTotalVRAM.argtypes = [ctypes.POINTER(ctypes.c_uint64)]

    lib.trGetAllocatedVRAM.restype = ctypes.c_int
    lib.trGetAllocatedVRAM.argtypes = [ctypes.POINTER(ctypes.c_uint64)]

    lib.trSetVRAMLimit.restype = ctypes.c_int
    lib.trSetVRAMLimit.argtypes = [ctypes.c_uint64]

    lib.trGetGPUName.restype = ctypes.c_int
    lib.trGetGPUName.argtypes = [ctypes.c_size_t, ctypes.c_char_p, ctypes.POINTER(ctypes.c_size_t)]

    lib.trGetCurrentDeviceName.restype = ctypes.c_int
    lib.trGetCurrentDeviceName.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_size_t)]

    lib.trGetAvailableGPUCount.restype = ctypes.c_int
    lib.trGetAvailableGPUCount.argtypes = [ctypes.POINTER(ctypes.c_size_t)]

    lib.trAddTrailSource.restype = ctypes.c_int
    lib.trAddTrailSource.argtypes = [ctypes.c_void_p, ctypes.POINTER(TrTrailSourceDesc), ctypes.POINTER(ctypes.c_uint32)]

    lib.trRemoveTrailSource.restype = ctypes.c_int
    lib.trRemoveTrailSource.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

    lib.trUpdateTrailSource.restype = ctypes.c_int
    lib.trUpdateTrailSource.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(TrTrailSourceDesc)]

    lib.trClearTrailSources.restype = ctypes.c_int
    lib.trClearTrailSources.argtypes = [ctypes.c_void_p]

    lib.trGetTrailSourceCount.restype = ctypes.c_int
    lib.trGetTrailSourceCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]

    lib.trGetTrailSourceInfos.restype = ctypes.c_int
    lib.trGetTrailSourceInfos.argtypes = [ctypes.c_void_p, ctypes.POINTER(TrTrailSourceInfo), ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]

    lib.trSetTrailSlotsPerParticle.restype = ctypes.c_int
    lib.trSetTrailSlotsPerParticle.argtypes = [ctypes.c_void_p, ctypes.c_int32]

    lib.trGetTrailBufferExports.restype = ctypes.c_int
    lib.trGetTrailBufferExports.argtypes = [ctypes.c_void_p, ctypes.POINTER(TrTrailBufferBundle)]

    lib.trGetTrailSplineDataSize.restype = ctypes.c_int
    lib.trGetTrailSplineDataSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32)]

    lib.trReadTrailSplineData.restype = ctypes.c_int
    lib.trReadTrailSplineData.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(TrTrailSplineRange),
        ctypes.POINTER(TrVec4),
        ctypes.POINTER(TrVec4),
        ctypes.c_int32,
        ctypes.c_int32,
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_int32),
        ctypes.POINTER(ctypes.c_int32),
        ctypes.POINTER(ctypes.c_int32),
    ]

    lib.trSetTrailSourceGradient.restype = ctypes.c_int
    lib.trSetTrailSourceGradient.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]

    lib.trClearTrailSourceGradient.restype = ctypes.c_int
    lib.trClearTrailSourceGradient.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

    lib.trSetTrailSourceCurve.restype = ctypes.c_int
    lib.trSetTrailSourceCurve.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]

    lib.trClearTrailSourceCurve.restype = ctypes.c_int
    lib.trClearTrailSourceCurve.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

    lib.trValidateGlsl.restype = ctypes.c_int
    lib.trValidateGlsl.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.POINTER(ctypes.c_char))]

    lib.trFreeString.restype = None
    lib.trFreeString.argtypes = [ctypes.c_char_p]
