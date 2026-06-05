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

"""IntelliSense-style completion engine for the GLSL Script Editor.

Provides context-aware completions for GLSL built-ins and the NeXus particle
API, plus signature help for function calls. Pure data/logic -- no PyQt6
dependency.
"""

from __future__ import annotations

import dataclasses
import enum
import re

from .highlighter import (
    GLSL_BUILTIN_FUNCTIONS,
    GLSL_KEYWORDS,
    GLSL_TYPES,
    NEXUS_BUILTIN_FUNCTIONS,
)
from .snippets import GLSL_SNIPPETS

# ---------------------------------------------------------------------------
# Enums and data classes
# ---------------------------------------------------------------------------


class CompletionKind(enum.IntEnum):
    KEYWORD = 0
    TYPE = 1
    FUNCTION = 2
    PROPERTY = 3
    METHOD = 4
    VARIABLE = 5
    NAMESPACE = 6
    SWIZZLE = 7
    SNIPPET = 8
    DEFINE = 9


_KIND_PRIORITY: dict[CompletionKind, str] = {
    CompletionKind.VARIABLE: "0",
    CompletionKind.PROPERTY: "1",
    CompletionKind.METHOD: "2",
    CompletionKind.FUNCTION: "3",
    CompletionKind.NAMESPACE: "4",
    CompletionKind.TYPE: "5",
    CompletionKind.KEYWORD: "6",
    CompletionKind.SWIZZLE: "7",
    CompletionKind.SNIPPET: "8",
    CompletionKind.DEFINE: "0",
}


@dataclasses.dataclass(frozen=True, slots=True)
class CompletionItem:
    label: str
    insert_text: str
    kind: CompletionKind
    type_text: str
    access: str
    detail: str
    sort_key: str


@dataclasses.dataclass(frozen=True, slots=True)
class SignatureInfo:
    label: str
    parameters: tuple[tuple[str, str, str], ...]
    return_type: str
    description: str


class CompletionContext(enum.Enum):
    GLOBAL = "global"
    NAMESPACE_DOT = "namespace"
    SWIZZLE_DOT = "swizzle"
    NONE = "none"


@dataclasses.dataclass(frozen=True, slots=True)
class FunctionScope:
    """A function body range for parameter scoping."""

    name: str
    start_line: int
    end_line: int
    params: tuple[str, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class WorkspaceSymbols:
    completions: tuple[CompletionItem, ...]
    signatures: dict[str, SignatureInfo]
    variable_types: dict[str, str]
    function_scopes: tuple[FunctionScope, ...]
    scoped_completions: dict[str, tuple[CompletionItem, ...]]
    scoped_variable_types: dict[str, dict[str, str]]


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------


def fuzzy_match(pattern: str, label: str) -> tuple[bool, int]:
    """Case-insensitive fuzzy match with scoring.

    Returns ``(matched, score)``.  Higher score = better match.
    """
    if not pattern:
        return (True, 0)
    pat = pattern.lower()
    lab_lower = label.lower()
    pat_len = len(pat)
    lab_len = len(label)

    j = 0
    for ch in pat:
        j = lab_lower.find(ch, j)
        if j == -1:
            return (False, 0)
        j += 1

    def _score(positions):
        s = 0
        for i, li in enumerate(positions):
            if li == 0 and i == 0:
                s += 20
            if li > 0 and (
                (label[li].isupper() and label[li - 1].islower()) or label[li - 1] == "_"
            ):
                s += 10
            if i > 0:
                gap = li - positions[i - 1] - 1
                if gap == 0:
                    s += 8
                else:
                    s -= 3 + gap - 1
        return s

    greedy = []
    pi = 0
    for li in range(lab_len):
        if pi < pat_len and lab_lower[li] == pat[pi]:
            greedy.append(li)
            pi += 1
    score = _score(greedy)

    boundary = []
    search_from = 0
    for pi in range(pat_len):
        best = -1
        for li in range(search_from, lab_len):
            if lab_lower[li] != pat[pi]:
                continue
            if best == -1:
                best = li
            is_boundary = (
                li == 0
                or (label[li].isupper() and li > 0 and label[li - 1].islower())
                or (li > 0 and label[li - 1] == "_")
            )
            if is_boundary:
                temp = li + 1
                ok = True
                for k in range(pi + 1, pat_len):
                    temp = lab_lower.find(pat[k], temp)
                    if temp == -1:
                        ok = False
                        break
                    temp += 1
                if ok:
                    best = li
                    break
        if best == -1:
            break
        boundary.append(best)
        search_from = best + 1

    if len(boundary) == pat_len:
        bs = _score(boundary)
        if bs > score:
            score = bs

    return (True, score)


# ---------------------------------------------------------------------------
# Function scope lookup
# ---------------------------------------------------------------------------


def find_enclosing_scope(
    scopes: tuple[FunctionScope, ...],
    cursor_line: int,
) -> FunctionScope | None:
    """Return the innermost FunctionScope containing *cursor_line*."""
    best: FunctionScope | None = None
    for scope in scopes:
        if scope.start_line <= cursor_line <= scope.end_line:
            if best is None or (
                (scope.end_line - scope.start_line) < (best.end_line - best.start_line)
            ):
                best = scope
    return best


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item(
    label: str,
    kind: CompletionKind,
    type_text: str = "",
    access: str = "",
    detail: str = "",
    insert_text: str | None = None,
) -> CompletionItem:
    return CompletionItem(
        label=label,
        insert_text=insert_text if insert_text is not None else label,
        kind=kind,
        type_text=type_text,
        access=access,
        detail=detail,
        sort_key=_KIND_PRIORITY[kind] + label,
    )


def _prop(label: str, type_text: str, access: str, detail: str) -> CompletionItem:
    return _item(label, CompletionKind.PROPERTY, type_text, access, detail)


def _method(
    label: str,
    type_text: str,
    detail: str,
    insert_text: str,
) -> CompletionItem:
    return _item(
        label,
        CompletionKind.METHOD,
        type_text,
        "",
        detail,
        insert_text=insert_text,
    )


VAR_TYPE_TO_GLSL: dict[str, str] = {
    "FLOAT": "float",
    "INT": "int",
    "VEC": "vec3",
    "USERDATA": "int",
}


# ---------------------------------------------------------------------------
# NeXus API database
# ---------------------------------------------------------------------------

_PARTICLE_MEMBERS: tuple[CompletionItem, ...] = (
    _prop("age", "float", "RW", "Particle age in seconds"),
    _prop("time", "float", "RW", "Particle age in seconds"),
    _prop("frame", "int", "R", "Particle age in frames"),
    _prop("speed", "float", "RW", "Particle speed"),
    _prop("group", "int", "RW", "Particle group"),
    _prop("radius", "float", "RW", "Particle radius"),
    _prop("mass", "float", "RW", "Particle mass"),
    _prop("life", "float", "RW", "Particle lifespan in seconds"),
    _prop("id", "int", "R", "Particle ID"),
    _prop("flags", "int", "RW", "Particle flags"),
    _prop("display", "uint", "RW", "Particle display flags"),
    _prop("distance", "float", "R", "Distance the particle has travelled"),
    _prop("friction", "float", "R", "Particle friction"),
    _prop("bounce", "float", "R", "Particle bounce"),
    _prop("emitter", "int", "R", "Particle emitter index"),
    _prop("color", "vec3", "RW", "Particle RGB color"),
    _prop("position", "vec3", "RW", "Particle position"),
    _prop("velocity", "vec3", "RW", "Particle velocity"),
    _prop("rotation", "vec3", "RW", "Particle rotation"),
    _prop("scale", "vec3", "RW", "Particle scale"),
    _prop("origin", "vec3", "R", "Particle position at the start of the current frame"),
    _prop("uvw", "vec3", "R", "Particle UVW coordinates"),
    _prop("vertex", "float", "R", "Particle vertex weight"),
    _prop("density", "float", "R", "Particle density, calculated live"),
    _prop("born", "bool", "R", "True if the particle was born this frame"),
    _prop("field", "float", "R", "Falloff/field value for the particle"),
    _prop("random", "float", "R", "Random value derived from the particle ID"),
    _prop("index", "int", "R", "Particle index on the GPU"),
    _prop("smoke", "float", "RW", "Particle smoke value (nxExplosiaFX)"),
    _prop("temperature", "float", "RW", "Particle temperature value (nxExplosiaFX)"),
    _prop("fuel", "float", "RW", "Particle fuel value (nxExplosiaFX)"),
    _method("neighbors", "int", "Number of particles within distance", "neighbors("),
)

_PARTICLES_MEMBERS: tuple[CompletionItem, ...] = tuple(
    _prop(m.label, m.type_text, "R", m.detail)
    for m in _PARTICLE_MEMBERS
    if m.label not in ("speed", "neighbors")
)

_DOC_MEMBERS: tuple[CompletionItem, ...] = (
    _prop("time", "float", "R", "Document time in seconds"),
    _prop("delta", "float", "R", "Time elapsed since the last frame in seconds"),
    _prop("frame", "int", "R", "Current document frame"),
    _prop("fps", "int", "R", "Document frame rate"),
)

_MATH_MEMBERS: tuple[CompletionItem, ...] = (
    _method("random", "float", "Random value generated from seed", "random("),
)

_COMPUTE_MEMBERS: tuple[CompletionItem, ...] = (
    _prop("iteration", "int", "R", "Current nxQuestion iteration"),
    _prop("iterationcount", "int", "R", "Total number of iterations set in nxQuestion"),
)

_EMITTERS_MEMBERS: tuple[CompletionItem, ...] = (
    _prop("count", "int", "R", "Number of emitters on the GPU"),
)

_EMITTER_MEMBERS: tuple[CompletionItem, ...] = (
    _prop("first", "int", "R", "Index of the first particle for this emitter"),
    _prop("count", "int", "R", "Number of particles for this emitter"),
    _prop("seed", "int", "R", "Random seed for this emitter"),
    _method("create", "int", "Creates a new particle on the GPU", "create("),
)

_NEWPARTICLE_MEMBERS: tuple[CompletionItem, ...] = (
    _prop("userdata", "int", "RW", "User-defined integer value"),
    _prop("emitter", "int", "RW", "GPU emitter index"),
    _prop("position", "vec3", "RW", "Particle position"),
    _prop("velocity", "vec3", "RW", "Particle velocity"),
    _prop("radius", "float", "RW", "Particle radius"),
    _prop("color", "vec3", "RW", "Particle RGB color"),
    _prop("life", "float", "RW", "Particle lifespan"),
    _prop("flags", "int", "RW", "Particle flags"),
)

_NEXUS_API: dict[str, tuple[CompletionItem, ...]] = {
    "particle": _PARTICLE_MEMBERS,
    "particles": _PARTICLES_MEMBERS,
    "doc": _DOC_MEMBERS,
    "math": _MATH_MEMBERS,
    "compute": _COMPUTE_MEMBERS,
    "emitters": _EMITTERS_MEMBERS,
    "emitter": _EMITTER_MEMBERS,
    "newparticle": _NEWPARTICLE_MEMBERS,
}


# ---------------------------------------------------------------------------
# Member type map (for swizzle resolution)
# ---------------------------------------------------------------------------


def _build_member_types() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for ns_name, members in _NEXUS_API.items():
        ns_map: dict[str, str] = {}
        for m in members:
            if m.type_text:
                ns_map[m.label] = m.type_text
        result[ns_name] = ns_map
    return result


_MEMBER_TYPES: dict[str, dict[str, str]] = _build_member_types()


# ---------------------------------------------------------------------------
# GLSL built-in function database
# ---------------------------------------------------------------------------

_GLSL_FUNCTION_TYPE_MAP: dict[str, str] = {
    "sin": "float",
    "cos": "float",
    "tan": "float",
    "asin": "float",
    "acos": "float",
    "atan": "float",
    "pow": "genType",
    "exp": "genType",
    "exp2": "genType",
    "log": "genType",
    "log2": "genType",
    "sqrt": "genType",
    "inversesqrt": "genType",
    "abs": "genType",
    "sign": "genType",
    "floor": "genType",
    "ceil": "genType",
    "fract": "genType",
    "trunc": "genType",
    "round": "genType",
    "mod": "genType",
    "min": "genType",
    "max": "genType",
    "clamp": "genType",
    "mix": "genType",
    "step": "genType",
    "smoothstep": "genType",
    "length": "float",
    "distance": "float",
    "dot": "float",
    "cross": "vec3",
    "normalize": "genType",
    "reflect": "genType",
    "refract": "genType",
    "faceforward": "genType",
    "texture": "vec4",
    "texture2D": "vec4",
    "texture3D": "vec4",
    "textureCube": "vec4",
    "radians": "genType",
    "degrees": "genType",
    "all": "bool",
    "any": "bool",
    "not": "bvec",
    "equal": "bvec",
    "notEqual": "bvec",
    "greaterThan": "bvec",
    "greaterThanEqual": "bvec",
    "lessThan": "bvec",
    "lessThanEqual": "bvec",
    "transpose": "mat",
    "dFdx": "genType",
    "dFdy": "genType",
    "fwidth": "genType",
}

_GLSL_FUNCTION_ITEMS: tuple[CompletionItem, ...] = tuple(
    _item(
        fn,
        CompletionKind.FUNCTION,
        type_text=_GLSL_FUNCTION_TYPE_MAP.get(fn, "genType"),
        detail="GLSL built-in function",
        insert_text=fn + "(",
    )
    for fn in GLSL_BUILTIN_FUNCTIONS
)


# ---------------------------------------------------------------------------
# Swizzle completions
# ---------------------------------------------------------------------------


def _swizzle(label: str, type_text: str) -> CompletionItem:
    return _item(label, CompletionKind.SWIZZLE, type_text, detail="Vector swizzle")


_SWIZZLES_VEC2: tuple[CompletionItem, ...] = (
    _swizzle("x", "float"),
    _swizzle("y", "float"),
    _swizzle("xy", "vec2"),
    _swizzle("yx", "vec2"),
    _swizzle("r", "float"),
    _swizzle("g", "float"),
    _swizzle("rg", "vec2"),
)

_SWIZZLES_VEC3: tuple[CompletionItem, ...] = (
    _swizzle("x", "float"),
    _swizzle("y", "float"),
    _swizzle("z", "float"),
    _swizzle("xy", "vec2"),
    _swizzle("xz", "vec2"),
    _swizzle("yz", "vec2"),
    _swizzle("yx", "vec2"),
    _swizzle("zx", "vec2"),
    _swizzle("zy", "vec2"),
    _swizzle("xyz", "vec3"),
    _swizzle("r", "float"),
    _swizzle("g", "float"),
    _swizzle("b", "float"),
    _swizzle("rgb", "vec3"),
)

_SWIZZLES_VEC4: tuple[CompletionItem, ...] = (
    _swizzle("x", "float"),
    _swizzle("y", "float"),
    _swizzle("z", "float"),
    _swizzle("w", "float"),
    _swizzle("xy", "vec2"),
    _swizzle("xz", "vec2"),
    _swizzle("yz", "vec2"),
    _swizzle("yx", "vec2"),
    _swizzle("zx", "vec2"),
    _swizzle("zy", "vec2"),
    _swizzle("xw", "vec2"),
    _swizzle("yw", "vec2"),
    _swizzle("zw", "vec2"),
    _swizzle("wx", "vec2"),
    _swizzle("wy", "vec2"),
    _swizzle("wz", "vec2"),
    _swizzle("xyz", "vec3"),
    _swizzle("xyzw", "vec4"),
    _swizzle("r", "float"),
    _swizzle("g", "float"),
    _swizzle("b", "float"),
    _swizzle("a", "float"),
    _swizzle("rgb", "vec3"),
    _swizzle("rgba", "vec4"),
)

_SWIZZLE_MAP: dict[str, tuple[CompletionItem, ...]] = {
    "vec2": _SWIZZLES_VEC2,
    "vec3": _SWIZZLES_VEC3,
    "vec4": _SWIZZLES_VEC4,
}


# ---------------------------------------------------------------------------
# Global completions
# ---------------------------------------------------------------------------

_NAMESPACE_DETAILS: dict[str, str] = {
    "particle": "Current particle data",
    "particles": "Indexed particle array (read-only)",
    "doc": "Document/scene information",
    "math": "Math utility functions",
    "compute": "nxQuestion iteration data",
    "emitters": "Emitter count information",
    "emitter": "Indexed emitter data",
    "newparticle": "Indexed new particle creation data",
}

_GLOBAL_COMPLETIONS: tuple[CompletionItem, ...] = tuple(
    sorted(
        [_item(kw, CompletionKind.KEYWORD, detail="GLSL keyword") for kw in GLSL_KEYWORDS]
        + [_item(tp, CompletionKind.TYPE, detail="GLSL type") for tp in GLSL_TYPES]
        + list(_GLSL_FUNCTION_ITEMS)
        + [
            _item(
                ns,
                CompletionKind.NAMESPACE,
                detail=_NAMESPACE_DETAILS.get(ns, "NeXus namespace"),
            )
            for ns in NEXUS_BUILTIN_FUNCTIONS
        ],
        key=lambda item: item.sort_key,
    )
)


# ---------------------------------------------------------------------------
# Signature database
# ---------------------------------------------------------------------------

_SIGNATURES: dict[str, SignatureInfo] = {
    "particle.neighbors": SignatureInfo(
        label="int neighbors(float distance)",
        parameters=(("distance", "float", "Search radius"),),
        return_type="int",
        description="Number of particles within distance",
    ),
    "math.random": SignatureInfo(
        label="float random(int seed)",
        parameters=(("seed", "int", "Random seed"),),
        return_type="float",
        description="Random value generated from seed",
    ),
    "emitter.create": SignatureInfo(
        label=(
            "int create(vec3 position, vec3 velocity, vec3 color,"
            " float radius, float life, int flags, int userdata)"
        ),
        parameters=(
            ("position", "vec3", "Particle position"),
            ("velocity", "vec3", "Particle velocity"),
            ("color", "vec3", "Particle RGB color"),
            ("radius", "float", "Particle radius"),
            ("life", "float", "Particle lifespan"),
            ("flags", "int", "Particle flags (use 0)"),
            ("userdata", "int", "User-defined integer"),
        ),
        return_type="int",
        description="Creates a new particle on the GPU",
    ),
    "sin": SignatureInfo(
        label="float sin(float x)",
        parameters=(("x", "float", "Angle in radians"),),
        return_type="float",
        description="Returns the sine of the angle",
    ),
    "cos": SignatureInfo(
        label="float cos(float x)",
        parameters=(("x", "float", "Angle in radians"),),
        return_type="float",
        description="Returns the cosine of the angle",
    ),
    "tan": SignatureInfo(
        label="float tan(float x)",
        parameters=(("x", "float", "Angle in radians"),),
        return_type="float",
        description="Returns the tangent of the angle",
    ),
    "asin": SignatureInfo(
        label="float asin(float x)",
        parameters=(("x", "float", "Value in range [-1, 1]"),),
        return_type="float",
        description="Returns the arc sine of the value",
    ),
    "acos": SignatureInfo(
        label="float acos(float x)",
        parameters=(("x", "float", "Value in range [-1, 1]"),),
        return_type="float",
        description="Returns the arc cosine of the value",
    ),
    "atan": SignatureInfo(
        label="float atan(float x)",
        parameters=(("x", "float", "Angle in radians"),),
        return_type="float",
        description="Returns the arc tangent of the value",
    ),
    "pow": SignatureInfo(
        label="genType pow(genType x, genType y)",
        parameters=(("x", "genType", "Base"), ("y", "genType", "Exponent")),
        return_type="genType",
        description="Returns x raised to the power y",
    ),
    "exp": SignatureInfo(
        label="genType exp(genType x)",
        parameters=(("x", "genType", "Value"),),
        return_type="genType",
        description="Returns the natural exponentiation of x",
    ),
    "log": SignatureInfo(
        label="genType log(genType x)",
        parameters=(("x", "genType", "Value"),),
        return_type="genType",
        description="Returns the natural logarithm of x",
    ),
    "sqrt": SignatureInfo(
        label="genType sqrt(genType x)",
        parameters=(("x", "genType", "Value"),),
        return_type="genType",
        description="Returns the square root of x",
    ),
    "abs": SignatureInfo(
        label="genType abs(genType x)",
        parameters=(("x", "genType", "Value"),),
        return_type="genType",
        description="Returns the absolute value of x",
    ),
    "sign": SignatureInfo(
        label="genType sign(genType x)",
        parameters=(("x", "genType", "Value"),),
        return_type="genType",
        description="Returns -1.0, 0.0, or 1.0",
    ),
    "floor": SignatureInfo(
        label="genType floor(genType x)",
        parameters=(("x", "genType", "Value"),),
        return_type="genType",
        description="Returns the nearest integer less than or equal to x",
    ),
    "ceil": SignatureInfo(
        label="genType ceil(genType x)",
        parameters=(("x", "genType", "Value"),),
        return_type="genType",
        description="Returns the nearest integer greater than or equal to x",
    ),
    "fract": SignatureInfo(
        label="genType fract(genType x)",
        parameters=(("x", "genType", "Value"),),
        return_type="genType",
        description="Returns x - floor(x)",
    ),
    "mod": SignatureInfo(
        label="genType mod(genType x, genType y)",
        parameters=(("x", "genType", "Value"), ("y", "genType", "Modulus")),
        return_type="genType",
        description="Returns x modulo y",
    ),
    "min": SignatureInfo(
        label="genType min(genType x, genType y)",
        parameters=(("x", "genType", "Value"), ("y", "genType", "Value")),
        return_type="genType",
        description="Returns the lesser of x and y",
    ),
    "max": SignatureInfo(
        label="genType max(genType x, genType y)",
        parameters=(("x", "genType", "Value"), ("y", "genType", "Value")),
        return_type="genType",
        description="Returns the greater of x and y",
    ),
    "clamp": SignatureInfo(
        label="genType clamp(genType x, genType min, genType max)",
        parameters=(
            ("x", "genType", "Value"),
            ("min", "genType", "Lower bound"),
            ("max", "genType", "Upper bound"),
        ),
        return_type="genType",
        description="Clamps x between min and max",
    ),
    "mix": SignatureInfo(
        label="genType mix(genType x, genType y, float/genType a)",
        parameters=(
            ("x", "genType", "Start"),
            ("y", "genType", "End"),
            ("a", "float/genType", "Interpolation factor"),
        ),
        return_type="genType",
        description="Linear interpolation between x and y",
    ),
    "step": SignatureInfo(
        label="genType step(genType edge, genType x)",
        parameters=(("edge", "genType", "Edge value"), ("x", "genType", "Value")),
        return_type="genType",
        description="Returns 0.0 if x < edge, else 1.0",
    ),
    "smoothstep": SignatureInfo(
        label="genType smoothstep(genType edge0, genType edge1, genType x)",
        parameters=(
            ("edge0", "genType", "Lower edge"),
            ("edge1", "genType", "Upper edge"),
            ("x", "genType", "Value"),
        ),
        return_type="genType",
        description="Hermite interpolation between 0 and 1",
    ),
    "length": SignatureInfo(
        label="float length(genType x)",
        parameters=(("x", "genType", "Vector"),),
        return_type="float",
        description="Returns the length of the vector",
    ),
    "distance": SignatureInfo(
        label="float distance(genType p0, genType p1)",
        parameters=(("p0", "genType", "Point A"), ("p1", "genType", "Point B")),
        return_type="float",
        description="Returns the distance between two points",
    ),
    "dot": SignatureInfo(
        label="float dot(genType x, genType y)",
        parameters=(("x", "genType", "Vector A"), ("y", "genType", "Vector B")),
        return_type="float",
        description="Returns the dot product of two vectors",
    ),
    "cross": SignatureInfo(
        label="vec3 cross(vec3 x, vec3 y)",
        parameters=(("x", "vec3", "Vector A"), ("y", "vec3", "Vector B")),
        return_type="vec3",
        description="Returns the cross product of two vectors",
    ),
    "normalize": SignatureInfo(
        label="genType normalize(genType x)",
        parameters=(("x", "genType", "Vector"),),
        return_type="genType",
        description="Returns a unit vector in the same direction",
    ),
    "reflect": SignatureInfo(
        label="genType reflect(genType I, genType N)",
        parameters=(
            ("I", "genType", "Incident vector"),
            ("N", "genType", "Normal vector"),
        ),
        return_type="genType",
        description="Returns the reflection direction",
    ),
    "refract": SignatureInfo(
        label="genType refract(genType I, genType N, float eta)",
        parameters=(
            ("I", "genType", "Incident vector"),
            ("N", "genType", "Normal vector"),
            ("eta", "float", "Refraction index ratio"),
        ),
        return_type="genType",
        description="Returns the refraction direction",
    ),
    "texture": SignatureInfo(
        label="vec4 texture(sampler2D sampler, vec2 coord)",
        parameters=(
            ("sampler", "sampler2D", "Texture sampler"),
            ("coord", "vec2", "Texture coordinates"),
        ),
        return_type="vec4",
        description="Samples a texture at the given coordinates",
    ),
}

_KNOWN_NAMESPACES: frozenset[str] = frozenset(_NEXUS_API.keys())
_INDEXED_NAMESPACES: frozenset[str] = frozenset({"particles", "emitter", "newparticle"})
_VEC_TYPES: frozenset[str] = frozenset({"vec2", "vec3", "vec4"})

_TYPE_PATTERN = r"\b(" + "|".join(sorted(GLSL_TYPES, key=len, reverse=True)) + r")\s+(\w+)"
_RE_TYPED_IDENT = re.compile(_TYPE_PATTERN)
_RE_ADDITIONAL_DECL = re.compile(r",\s*(\w+)")
_RE_DEFINE = re.compile(r"^\s*#define\s+(\w+)", re.MULTILINE)
_RE_STRUCT = re.compile(r"\bstruct\s+(\w+)")
_GLSL_RESERVED: frozenset[str] = frozenset(GLSL_TYPES) | frozenset(GLSL_KEYWORDS)


# ---------------------------------------------------------------------------
# Workspace symbol extraction
# ---------------------------------------------------------------------------


def _strip_comments_and_strings(source: str) -> str:
    result = []
    i = 0
    length = len(source)
    in_line_comment = False
    in_block_comment = False
    in_string = False
    in_char = False

    while i < length:
        ch = source[i]

        if in_line_comment:
            if ch == "\n":
                result.append("\n")
                in_line_comment = False
            else:
                result.append(" ")
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and i + 1 < length and source[i + 1] == "/":
                result.append("  ")
                i += 2
                in_block_comment = False
            elif ch == "\n":
                result.append("\n")
                i += 1
            else:
                result.append(" ")
                i += 1
            continue

        if in_string:
            if ch == "\\" and i + 1 < length:
                result.append("  ")
                i += 2
            elif ch == '"':
                result.append(" ")
                i += 1
                in_string = False
            elif ch == "\n":
                result.append("\n")
                i += 1
                in_string = False
            else:
                result.append(" ")
                i += 1
            continue

        if in_char:
            if ch == "\\" and i + 1 < length:
                result.append("  ")
                i += 2
            elif ch == "'":
                result.append(" ")
                i += 1
                in_char = False
            elif ch == "\n":
                result.append("\n")
                i += 1
                in_char = False
            else:
                result.append(" ")
                i += 1
            continue

        if ch == "/" and i + 1 < length:
            next_ch = source[i + 1]
            if next_ch == "/":
                result.append("  ")
                i += 2
                in_line_comment = True
                continue
            if next_ch == "*":
                result.append("  ")
                i += 2
                in_block_comment = True
                continue

        if ch == '"':
            result.append(" ")
            i += 1
            in_string = True
            continue

        if ch == "'":
            result.append(" ")
            i += 1
            in_char = True
            continue

        result.append(ch)
        i += 1

    return "".join(result)


def extract_workspace_symbols(source: str) -> WorkspaceSymbols:
    from bisect import bisect_right

    cleaned = _strip_comments_and_strings(source)

    line_starts = [0]
    for i, ch in enumerate(cleaned):
        if ch == "\n":
            line_starts.append(i + 1)

    items: dict[str, CompletionItem] = {}
    signatures: dict[str, SignatureInfo] = {}
    variable_types: dict[str, str] = {}
    function_scopes: list[FunctionScope] = []
    scoped_completions: dict[str, list[CompletionItem]] = {}
    scoped_variable_types: dict[str, dict[str, str]] = {}

    for match in _RE_TYPED_IDENT.finditer(cleaned):
        type_name = match.group(1)
        ident_name = match.group(2)

        if ident_name == "main":
            continue

        end = match.end()
        scan = end
        while scan < len(cleaned) and cleaned[scan] in " \t":
            scan += 1

        if scan < len(cleaned) and cleaned[scan] == "(":
            paren_start = scan
            depth = 1
            scan += 1
            while scan < len(cleaned) and depth > 0:
                if cleaned[scan] == "(":
                    depth += 1
                elif cleaned[scan] == ")":
                    depth -= 1
                scan += 1
            paren_end = scan

            param_text = cleaned[paren_start + 1 : paren_end - 1]
            param_matches = _RE_TYPED_IDENT.findall(param_text)

            sig_params: list[tuple[str, str, str]] = []
            param_items: list[CompletionItem] = []
            param_types: dict[str, str] = {}
            for p_type, p_name in param_matches:
                sig_params.append((p_name, p_type, ""))
                param_items.append(
                    _item(
                        p_name,
                        CompletionKind.VARIABLE,
                        type_text=p_type,
                        detail="Parameter",
                    )
                )
                param_types[p_name] = p_type

            body_scan = paren_end
            while body_scan < len(cleaned) and cleaned[body_scan] in " \t\n":
                body_scan += 1

            is_definition = body_scan < len(cleaned) and cleaned[body_scan] == "{"
            if is_definition and param_items:
                brace_start = body_scan
                brace_depth = 1
                body_scan += 1
                while body_scan < len(cleaned) and brace_depth > 0:
                    if cleaned[body_scan] == "{":
                        brace_depth += 1
                    elif cleaned[body_scan] == "}":
                        brace_depth -= 1
                    body_scan += 1
                brace_end = body_scan - 1

                start_line = bisect_right(line_starts, brace_start) - 1
                end_line = bisect_right(line_starts, brace_end) - 1

                function_scopes.append(
                    FunctionScope(
                        name=ident_name,
                        start_line=start_line,
                        end_line=end_line,
                        params=tuple(p_name for _, p_name in param_matches),
                    )
                )
                scoped_completions[ident_name] = param_items
                scoped_variable_types[ident_name] = param_types
            elif not is_definition:
                for p_type, p_name in param_matches:
                    items[p_name] = _item(
                        p_name,
                        CompletionKind.VARIABLE,
                        type_text=p_type,
                        detail="Parameter",
                    )
                    variable_types[p_name] = p_type

            items[ident_name] = _item(
                ident_name,
                CompletionKind.FUNCTION,
                type_text=type_name,
                detail="User function",
                insert_text=ident_name + "(",
            )
            signatures[ident_name] = SignatureInfo(
                label="{} {}({})".format(
                    type_name,
                    ident_name,
                    ", ".join("{} {}".format(pt, pn) for pn, pt, _ in sig_params),
                ),
                parameters=tuple(sig_params),
                return_type=type_name,
                description="User function",
            )
        else:
            items[ident_name] = _item(
                ident_name,
                CompletionKind.VARIABLE,
                type_text=type_name,
                detail="User variable",
            )
            variable_types[ident_name] = type_name

            trail_start = end
            trail_end = len(cleaned)
            for stop_ch in (";", "{", ")", "("):
                stop_idx = cleaned.find(stop_ch, trail_start)
                if stop_idx != -1 and stop_idx < trail_end:
                    trail_end = stop_idx
            trail_text = cleaned[trail_start:trail_end]
            for extra_name in _RE_ADDITIONAL_DECL.findall(trail_text):
                if extra_name in _GLSL_RESERVED:
                    break
                items[extra_name] = _item(
                    extra_name,
                    CompletionKind.VARIABLE,
                    type_text=type_name,
                    detail="User variable",
                )
                variable_types[extra_name] = type_name

    for match in _RE_DEFINE.finditer(cleaned):
        name = match.group(1)
        if name != "main":
            items[name] = _item(
                name,
                CompletionKind.DEFINE,
                type_text="macro",
                detail="Preprocessor define",
            )

    for match in _RE_STRUCT.finditer(cleaned):
        name = match.group(1)
        items[name] = _item(
            name,
            CompletionKind.TYPE,
            type_text="struct",
            detail="User struct",
        )

    completions = tuple(sorted(items.values(), key=lambda item: item.sort_key))
    return WorkspaceSymbols(
        completions=completions,
        signatures=signatures,
        variable_types=variable_types,
        function_scopes=tuple(function_scopes),
        scoped_completions={k: tuple(v) for k, v in scoped_completions.items()},
        scoped_variable_types=scoped_variable_types,
    )


def build_external_var_completions(
    user_vars: tuple[tuple[str, str, bool, bool, str], ...],
) -> tuple[tuple[CompletionItem, ...], dict[str, str]]:
    """Build completion items and type map from external nxQuestion VAR items.

    Returns (completions, variable_types) where variable_types maps
    var_name -> glsl_type for swizzle resolution.
    """
    items: list[CompletionItem] = []
    types: dict[str, str] = {}
    seen: set[str] = set()
    for var_name, var_type, is_writable, is_per_particle, value_str in user_vars:
        if var_name in seen:
            continue
        seen.add(var_name)
        glsl_type = VAR_TYPE_TO_GLSL.get(var_type, "float")
        access = "RW" if is_writable else "R"
        label = "Per-particle" if is_per_particle else "Variable"
        detail = f"{label} = {value_str}" if value_str else label
        items.append(
            _item(
                var_name,
                CompletionKind.VARIABLE,
                type_text=glsl_type,
                access=access,
                detail=detail,
            )
        )
        types[var_name] = glsl_type
    return tuple(items), types


# ---------------------------------------------------------------------------
# Context analyzer
# ---------------------------------------------------------------------------


def analyze_context(
    line_text: str,
    col: int,
    in_comment_or_string: bool = False,
    user_variable_types: dict[str, str] | None = None,
    scoped_variable_types: dict[str, str] | None = None,
) -> tuple[CompletionContext, str, str]:
    if in_comment_or_string:
        return (CompletionContext.NONE, "", "")

    text = line_text[:col]

    pos = len(text) - 1

    prefix_chars: list[str] = []
    while pos >= 0 and (text[pos].isalnum() or text[pos] == "_"):
        prefix_chars.append(text[pos])
        pos -= 1
    prefix = "".join(reversed(prefix_chars))

    if pos < 0 or text[pos] != ".":
        return (CompletionContext.GLOBAL, "", prefix)

    # First dot found
    pos -= 1  # skip the dot

    # Collect the identifier or bracket expression before the first dot
    first_ident = ""
    if pos >= 0 and text[pos] == "]":
        # Walk back to find matching '['
        pos -= 1
        bracket_depth = 1
        while pos >= 0 and bracket_depth > 0:
            if text[pos] == "]":
                bracket_depth += 1
            elif text[pos] == "[":
                bracket_depth -= 1
            pos -= 1
        # Now collect the identifier before '['
        ident_chars: list[str] = []
        while pos >= 0 and (text[pos].isalnum() or text[pos] == "_"):
            ident_chars.append(text[pos])
            pos -= 1
        first_ident = "".join(reversed(ident_chars))
    elif pos >= 0 and (text[pos].isalnum() or text[pos] == "_"):
        ident_chars = []
        while pos >= 0 and (text[pos].isalnum() or text[pos] == "_"):
            ident_chars.append(text[pos])
            pos -= 1
        first_ident = "".join(reversed(ident_chars))

    # Check if there's a second dot (namespace.member.prefix)
    if pos >= 0 and text[pos] == ".":
        pos -= 1

        ns_chars: list[str] = []
        # Handle possible bracket before the namespace dot
        if pos >= 0 and text[pos] == "]":
            pos -= 1
            bracket_depth = 1
            while pos >= 0 and bracket_depth > 0:
                if text[pos] == "]":
                    bracket_depth += 1
                elif text[pos] == "[":
                    bracket_depth -= 1
                pos -= 1
            while pos >= 0 and (text[pos].isalnum() or text[pos] == "_"):
                ns_chars.append(text[pos])
                pos -= 1
        elif pos >= 0 and (text[pos].isalnum() or text[pos] == "_"):
            while pos >= 0 and (text[pos].isalnum() or text[pos] == "_"):
                ns_chars.append(text[pos])
                pos -= 1

        namespace = "".join(reversed(ns_chars))
        member = first_ident

        if namespace in _KNOWN_NAMESPACES:
            member_type = _MEMBER_TYPES.get(namespace, {}).get(member, "")
            if member_type in _VEC_TYPES:
                return (CompletionContext.SWIZZLE_DOT, member_type, prefix)

        return (CompletionContext.GLOBAL, "", prefix)

    # Single dot: namespace.prefix
    if first_ident in _KNOWN_NAMESPACES:
        return (CompletionContext.NAMESPACE_DOT, first_ident, prefix)

    if user_variable_types is not None and first_ident in user_variable_types:
        var_type = user_variable_types[first_ident]
        if var_type in _VEC_TYPES:
            return (CompletionContext.SWIZZLE_DOT, var_type, prefix)

    if scoped_variable_types is not None and first_ident in scoped_variable_types:
        var_type = scoped_variable_types[first_ident]
        if var_type in _VEC_TYPES:
            return (CompletionContext.SWIZZLE_DOT, var_type, prefix)

    return (CompletionContext.GLOBAL, "", prefix)


# ---------------------------------------------------------------------------
# Completion provider
# ---------------------------------------------------------------------------


def get_completions(
    line_text: str,
    col: int,
    in_comment_or_string: bool = False,
    workspace: WorkspaceSymbols | None = None,
    *,
    cursor_line: int = -1,
    _precomputed: tuple[CompletionContext, str, str] | None = None,
) -> list[CompletionItem]:
    if _precomputed is not None:
        context, qualifier, prefix = _precomputed
    else:
        context, qualifier, prefix = analyze_context(
            line_text,
            col,
            in_comment_or_string,
            user_variable_types=workspace.variable_types if workspace else None,
        )

    if context == CompletionContext.NONE:
        return []

    if context == CompletionContext.GLOBAL:
        if not prefix:
            return []
        scored: list[tuple[int, CompletionItem]] = []
        for item in _GLOBAL_COMPLETIONS:
            matched, sc = fuzzy_match(prefix, item.label)
            if matched:
                scored.append((sc, item))
        if workspace is not None:
            for item in workspace.completions:
                matched, sc = fuzzy_match(prefix, item.label)
                if matched:
                    scored.append((sc, item))
        if workspace is not None and cursor_line >= 0 and workspace.function_scopes:
            scope = find_enclosing_scope(workspace.function_scopes, cursor_line)
            if scope is not None and scope.name in workspace.scoped_completions:
                for item in workspace.scoped_completions[scope.name]:
                    matched, sc = fuzzy_match(prefix, item.label)
                    if matched:
                        scored.append((sc, item))
        for snippet in GLSL_SNIPPETS:
            matched, sc = fuzzy_match(prefix, snippet.trigger)
            if matched:
                scored.append(
                    (
                        sc,
                        CompletionItem(
                            label=snippet.trigger,
                            insert_text=snippet.trigger,
                            kind=CompletionKind.SNIPPET,
                            type_text="Snippet",
                            access="",
                            detail=snippet.description,
                            sort_key="1" + snippet.trigger,
                        ),
                    )
                )
        scored.sort(key=lambda x: (-x[0], x[1].sort_key))
        return [item for _, item in scored]

    if context == CompletionContext.NAMESPACE_DOT:
        members = _NEXUS_API.get(qualifier, ())
        if not prefix:
            return sorted(members, key=lambda item: item.sort_key)
        scored = []
        for item in members:
            matched, sc = fuzzy_match(prefix, item.label)
            if matched:
                scored.append((sc, item))
        scored.sort(key=lambda x: (-x[0], x[1].sort_key))
        return [item for _, item in scored]

    if context == CompletionContext.SWIZZLE_DOT:
        swizzles = _SWIZZLE_MAP.get(qualifier, ())
        if not prefix:
            return sorted(swizzles, key=lambda item: item.sort_key)
        scored = []
        for item in swizzles:
            matched, sc = fuzzy_match(prefix, item.label)
            if matched:
                scored.append((sc, item))
        scored.sort(key=lambda x: (-x[0], x[1].sort_key))
        return [item for _, item in scored]

    return []


# ---------------------------------------------------------------------------
# Signature help
# ---------------------------------------------------------------------------


def find_active_signature(
    full_text: str,
    cursor_pos: int,
) -> tuple[str | None, int]:
    pos = cursor_pos - 1
    depth = 0
    in_string = False
    string_char = ""

    while pos >= 0:
        ch = full_text[pos]

        if in_string:
            if ch == string_char:
                num_slashes = 0
                p = pos - 1
                while p >= 0 and full_text[p] == "\\":
                    num_slashes += 1
                    p -= 1
                if num_slashes % 2 == 0:
                    in_string = False
            pos -= 1
            continue

        if ch in ('"', "'"):
            in_string = True
            string_char = ch
            pos -= 1
            continue

        # Skip block comments (scanning backward: we hit */ first)
        if ch == "/" and pos > 0 and full_text[pos - 1] == "*":
            pos -= 2
            while pos > 0:
                if full_text[pos] == "*" and full_text[pos - 1] == "/":
                    pos -= 2
                    break
                pos -= 1
            else:
                pos = -1
            continue

        # Skip single-line comments (walk back past all content to //)
        if ch == "/" and pos > 0 and full_text[pos - 1] == "/":
            pos -= 2
            while pos >= 0 and full_text[pos] != "\n":
                pos -= 1
            continue

        if ch == ")":
            depth += 1
            pos -= 1
            continue

        if ch == "(":
            if depth > 0:
                depth -= 1
                pos -= 1
                continue
            # Found the unmatched opening paren
            paren_pos = pos

            # Extract function name before the paren
            name_end = pos - 1
            while name_end >= 0 and full_text[name_end] == " ":
                name_end -= 1

            name_chars: list[str] = []
            name_pos = name_end
            while name_pos >= 0 and (
                full_text[name_pos].isalnum() or full_text[name_pos] in "_.]"
            ):
                if full_text[name_pos] == "]":
                    # Skip bracket contents
                    name_pos -= 1
                    bd = 1
                    while name_pos >= 0 and bd > 0:
                        if full_text[name_pos] == "]":
                            bd += 1
                        elif full_text[name_pos] == "[":
                            bd -= 1
                        name_pos -= 1
                    continue
                name_chars.append(full_text[name_pos])
                name_pos -= 1

            raw_name = "".join(reversed(name_chars))

            # Normalize indexed namespace references:
            # "emitter.create" stays, "particles.neighbors" stays
            # Handle cases where brackets were skipped and dot remains
            func_name = raw_name

            # Count commas between paren and cursor, respecting nesting
            comma_count = 0
            scan_depth = 0
            scan_in_string = False
            scan_string_char = ""
            scan_pos = paren_pos + 1

            while scan_pos < cursor_pos:
                sc = full_text[scan_pos]

                if scan_in_string:
                    if sc == scan_string_char and (
                        scan_pos == 0 or full_text[scan_pos - 1] != "\\"
                    ):
                        scan_in_string = False
                    scan_pos += 1
                    continue

                if sc in ('"', "'"):
                    scan_in_string = True
                    scan_string_char = sc
                    scan_pos += 1
                    continue

                if sc in ("(", "["):
                    scan_depth += 1
                elif sc in (")", "]"):
                    scan_depth -= 1
                elif sc == "," and scan_depth == 0:
                    comma_count += 1

                scan_pos += 1

            return (func_name, comma_count) if func_name else (None, -1)

        pos -= 1

    return (None, -1)


def get_signature_info(
    function_name: str,
    user_signatures: dict[str, SignatureInfo] | None = None,
) -> SignatureInfo | None:
    result = _SIGNATURES.get(function_name)
    if result is not None:
        return result
    if user_signatures is not None:
        return user_signatures.get(function_name)
    return None
