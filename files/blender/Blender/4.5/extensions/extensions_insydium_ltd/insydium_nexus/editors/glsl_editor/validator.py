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

"""GLSL validation via Theron's linked glslang.

Calls ``theron.validate_glsl_source()`` to compile user source as a
``#version 450`` Vulkan compute shader, matching the Theron runtime
environment.

Before compilation, the user's source undergoes the same keyword
replacements that Theron performs (``particle.position`` ->
``particlePosition``, ``particles[n].velocity`` ->
``GetParticleVectorData(n, ...)``, etc.) so that validation matches
runtime behaviour.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto

# ---------------------------------------------------------------------------
# Diagnostic data structure
# ---------------------------------------------------------------------------


class Severity(Enum):
    ERROR = auto()
    WARNING = auto()


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A single compiler diagnostic tied to a source line."""

    line: int
    column: int
    severity: Severity
    message: str


# ---------------------------------------------------------------------------
# Validation preamble -- matches Theron's Vulkan runtime (#version 450)
# ---------------------------------------------------------------------------

_VAR_GLSL_DEFAULTS: dict[str, str] = {
    "float": "0.0",
    "int": "0",
    "vec3": "vec3(0.0)",
}

_VAR_TYPE_TO_GLSL: dict[str, str] = {
    "FLOAT": "float",
    "INT": "int",
    "VEC": "vec3",
    "USERDATA": "int",
}

# TODO: move this to theron lib
_VALIDATION_PREAMBLE_450 = ""

_PREAMBLE_LINE_COUNT_450 = _VALIDATION_PREAMBLE_450.count("\n")


# ---------------------------------------------------------------------------
# Keyword replacement -- mirrors Theron's nxquestion.cpp preprocessing
# ---------------------------------------------------------------------------

_RE_PARTICLES_POSITION = re.compile(r"particles\[([^\]]+)\]\.position")
_RE_PARTICLES_VELOCITY = re.compile(r"particles\[([^\]]+)\]\.velocity")
_RE_PARTICLES_COLOR = re.compile(r"particles\[([^\]]+)\]\.color")
_RE_PARTICLES_AGE = re.compile(r"particles\[([^\]]+)\]\.age")
_RE_PARTICLES_TIME = re.compile(r"particles\[([^\]]+)\]\.time")
_RE_PARTICLES_RADIUS = re.compile(r"particles\[([^\]]+)\]\.radius")
_RE_PARTICLES_MASS = re.compile(r"particles\[([^\]]+)\]\.mass")
_RE_PARTICLES_LIFE = re.compile(r"particles\[([^\]]+)\]\.life")
_RE_PARTICLES_DISTANCE = re.compile(r"particles\[([^\]]+)\]\.distance")
_RE_PARTICLES_GROUP = re.compile(r"particles\[([^\]]+)\]\.group")
_RE_PARTICLES_FLAGS = re.compile(r"particles\[([^\]]+)\]\.flags")
_RE_PARTICLES_ID = re.compile(r"particles\[([^\]]+)\]\.id")
_RE_PARTICLES_ROTATION = re.compile(r"particles\[([^\]]+)\]\.rotation")
_RE_PARTICLES_SCALE = re.compile(r"particles\[([^\]]+)\]\.scale")
_RE_PARTICLES_ORIGIN = re.compile(r"particles\[([^\]]+)\]\.origin")
_RE_PARTICLES_UVW = re.compile(r"particles\[([^\]]+)\]\.uvw")
_RE_PARTICLES_SMOKE = re.compile(r"particles\[([^\]]+)\]\.smoke")
_RE_PARTICLES_TEMPERATURE = re.compile(r"particles\[([^\]]+)\]\.temperature")
_RE_PARTICLES_FUEL = re.compile(r"particles\[([^\]]+)\]\.fuel")
_RE_PARTICLES_VERTEX = re.compile(r"particles\[([^\]]+)\]\.vertex")
_RE_PARTICLES_FRICTION = re.compile(r"particles\[([^\]]+)\]\.friction")
_RE_PARTICLES_BOUNCE = re.compile(r"particles\[([^\]]+)\]\.bounce")
_RE_PARTICLES_DISPLAY = re.compile(r"particles\[([^\]]+)\]\.display")
_RE_PARTICLES_EMITTER = re.compile(r"particles\[([^\]]+)\]\.emitter")

_RE_EMITTER_CREATE_PREFIX = re.compile(r"emitter\[([^\]]+)\]\.create\(")
_RE_EMITTER_FIRST = re.compile(r"emitter\[([^\]]+)\]\.first")
_RE_EMITTER_COUNT = re.compile(r"emitter\[([^\]]+)\]\.count")
_RE_EMITTER_SEED = re.compile(r"emitter\[([^\]]+)\]\.seed")

_RE_NEWPARTICLE = re.compile(
    r"newparticle\[([^\]]+)\]\.(position|velocity|color|radius|life|flags|userdata|emitter)"
)

_RE_PARTICLE_NEIGHBORS_PREFIX = re.compile(r"particle\.neighbors\(")
_RE_MATH_RANDOM_PREFIX = re.compile(r"math\.random\(")
_RE_PRINT_PREFIX = re.compile(r"print\s*\(")

_RE_HAS_VOID_MAIN = re.compile(r"\bvoid\s+main\s*\(")

_SIMPLE_REPLACEMENTS: list[tuple[str, str]] = [
    ("particle.position", "particlePosition"),
    ("particle.velocity", "particleVelocity"),
    ("particle.color", "particleColor"),
    ("particle.rotation", "particleRotation"),
    ("particle.scale", "particleScale"),
    ("particle.origin", "particleOriginPosition"),
    ("particle.uvw", "particleUVW"),
    ("particle.age", "particleTime"),
    ("particle.time", "particleTime"),
    ("particle.frame", "int(particleTime*float(docFPS))"),
    ("particle.speed", "particleSpeed"),
    ("particle.life", "particleLife"),
    ("particle.mass", "particleMass"),
    ("particle.radius", "particleRadius"),
    ("particle.distance", "particleDistance"),
    ("particle.vertex", "particleVertexWeight"),
    ("particle.id", "particleID"),
    ("particle.group", "particleGroup"),
    ("particle.flags", "particleFlags"),
    ("particle.display", "particleDisplay"),
    ("particle.born", "bool(particleFlags & XPARTICLE_FLAGS_BORN)"),
    ("particle.field", "falloff"),
    ("particle.random", "rnd01(particleID, 0)"),
    ("particle.index", "index"),
    ("particle.smoke", "particleSmoke"),
    ("particle.temperature", "particleTemperature"),
    ("particle.fuel", "particleFuel"),
    ("particle.density", "GetDensity(index)"),
    ("particle.friction", "0.0"),
    ("particle.bounce", "0.0"),
    ("particle.emitter", "0"),
    ("doc.time", "docTime"),
    ("doc.delta", "TIME_DELTA"),
    ("doc.frame", "docFrame"),
    ("doc.fps", "docFPS"),
    ("compute.iteration", "_iterationPass"),
    ("compute.iterationcount", "_iterationCount"),
    ("emitters.count", "emitterCount"),
]


def _find_balanced_close(source: str, open_pos: int) -> int:
    """Return the index of the closing ')' that balances the '(' at *open_pos*.

    Returns -1 if no balanced close is found.
    """
    depth = 1
    i = open_pos + 1
    length = len(source)
    while i < length:
        ch = source[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _replace_balanced_paren_call(
    source: str,
    prefix_re: re.Pattern[str],
    formatter,
) -> str:
    """Replace calls matched by *prefix_re* (which ends at the opening paren)
    using balanced-paren matching for the argument list.

    *formatter* receives ``(match, args_str)`` where *match* is the prefix
    regex match and *args_str* is the full parenthesised argument text
    (without the outer parens).  It returns the replacement string.
    """
    result_parts: list[str] = []
    last_end = 0

    for m in prefix_re.finditer(source):
        if m.start() < last_end:
            continue
        open_pos = m.end() - 1
        close_pos = _find_balanced_close(source, open_pos)
        if close_pos == -1:
            continue
        args_str = source[open_pos + 1 : close_pos]
        result_parts.append(source[last_end : m.start()])
        result_parts.append(formatter(m, args_str))
        last_end = close_pos + 1

    if not result_parts:
        return source

    result_parts.append(source[last_end:])
    return "".join(result_parts)


def _strip_print_preserve_lines(source: str) -> str:
    """Replace ``print(...);`` calls with comments preserving newline count."""
    result_parts: list[str] = []
    last_end = 0

    for m in _RE_PRINT_PREFIX.finditer(source):
        if m.start() < last_end:
            continue
        open_pos = m.end() - 1
        close_pos = _find_balanced_close(source, open_pos)
        if close_pos == -1:
            continue
        stmt_end = close_pos + 1
        while stmt_end < len(source) and source[stmt_end] in " \t":
            stmt_end += 1
        if stmt_end < len(source) and source[stmt_end] == ";":
            stmt_end += 1
        original_text = source[m.start() : stmt_end]
        newline_count = original_text.count("\n")
        replacement = "/* print removed */" + "\n" * newline_count
        result_parts.append(source[last_end : m.start()])
        result_parts.append(replacement)
        last_end = stmt_end

    if not result_parts:
        return source

    result_parts.append(source[last_end:])
    return "".join(result_parts)


def _replace_keywords(source: str) -> str:
    """Apply Theron-style keyword replacements to user GLSL source.

    Complex regex-based patterns are applied first, then simple string
    replacements in longest-match order.
    """
    source = _strip_print_preserve_lines(source)

    source = _RE_PARTICLES_POSITION.sub(
        r"GetParticleVectorData(\1, PARTICLE_POSITION_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_VELOCITY.sub(
        r"GetParticleVectorData(\1, PARTICLE_VELOCITY_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_COLOR.sub(
        r"GetParticleVectorData(\1, PARTICLE_COLOR_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_AGE.sub(
        r"GetParticleFloatData(\1, PARTICLE_TIME_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_TIME.sub(
        r"GetParticleFloatData(\1, PARTICLE_TIME_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_RADIUS.sub(
        r"GetParticleFloatData(\1, PARTICLE_RADIUS_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_MASS.sub(
        r"GetParticleFloatData(\1, PARTICLE_MASS_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_LIFE.sub(
        r"GetParticleFloatData(\1, PARTICLE_LIFE_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_DISTANCE.sub(
        r"GetParticleFloatData(\1, PARTICLE_DISTANCE_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_GROUP.sub(
        r"GetParticleIntData(\1, PARTICLE_GROUP_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_FLAGS.sub(
        r"GetParticleIntData(\1, PARTICLE_FLAGS_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_ID.sub(
        r"GetParticleIntData(\1, PARTICLE_ID_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_ROTATION.sub(
        r"GetParticleVectorData(\1, PARTICLE_ROTATION_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_SCALE.sub(
        r"GetParticleVectorData(\1, PARTICLE_SCALE_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_ORIGIN.sub(
        r"GetParticleVectorData(\1, PARTICLE_ORIGINPOS_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_UVW.sub(
        r"GetParticleVectorData(\1, PARTICLE_UVW_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_SMOKE.sub(
        r"GetParticleFloatData(\1, PARTICLE_SMOKE_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_TEMPERATURE.sub(
        r"GetParticleFloatData(\1, PARTICLE_TEMPERATURE_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_FUEL.sub(
        r"GetParticleFloatData(\1, PARTICLE_FUEL_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_VERTEX.sub(
        r"GetParticleFloatData(\1, PARTICLE_VERTEXWEIGHT_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_FRICTION.sub(
        r"GetParticleFloatData(\1, PARTICLE_FRICTION_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_BOUNCE.sub(
        r"GetParticleFloatData(\1, PARTICLE_BOUNCE_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_DISPLAY.sub(
        r"GetParticleIntData(\1, PARTICLE_DISPLAY_OFFSET)",
        source,
    )
    source = _RE_PARTICLES_EMITTER.sub(
        r"GetParticleIntData(\1, PARTICLE_EMITTER_INDEX_OFFSET)",
        source,
    )

    source = _replace_balanced_paren_call(
        source,
        _RE_EMITTER_CREATE_PREFIX,
        lambda m, args: f"SpawnParticle({m.group(1)}, {args})",
    )
    source = _RE_EMITTER_FIRST.sub(r"_emitter_first(\1)", source)
    source = _RE_EMITTER_COUNT.sub(r"_emitter_count(\1)", source)
    source = _RE_EMITTER_SEED.sub(r"_emitter_seed(\1)", source)

    source = _RE_NEWPARTICLE.sub(r"_newparticles[\1].\2", source)

    source = _replace_balanced_paren_call(
        source,
        _RE_PARTICLE_NEIGHBORS_PREFIX,
        lambda m, args: f"GetNeighbors(index, {args})",
    )
    source = _replace_balanced_paren_call(
        source,
        _RE_MATH_RANDOM_PREFIX,
        lambda m, args: f"rnd01({args}, 0)",
    )

    for old, new in sorted(_SIMPLE_REPLACEMENTS, key=lambda x: len(x[0]), reverse=True):
        source = source.replace(old, new)

    return source


# ---------------------------------------------------------------------------
# Theron glslang backend
# ---------------------------------------------------------------------------


class _TheronCompiler:
    """Validates GLSL via Theron's linked glslang library."""

    def available(self) -> bool:
        return True

    def compile(self, source_bytes: bytes) -> tuple[bool, str]:
        from ...libs import theron

        source_str = source_bytes.decode("utf-8")
        return theron.validate_glsl_source(source_str)


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_theron_compiler: _TheronCompiler | None = None


def _get_theron_compiler() -> _TheronCompiler:
    global _theron_compiler
    if _theron_compiler is None:
        _theron_compiler = _TheronCompiler()
    return _theron_compiler


# ---------------------------------------------------------------------------
# Error log parsing -- glslang output
# ---------------------------------------------------------------------------

_RE_GLSLANG = re.compile(
    r"^(ERROR|WARNING):\s*(?:stdin|\S+):(\d+):\s*(.+)",
    re.IGNORECASE,
)


def _parse_glslang_log(log: str, line_offset: int) -> list[Diagnostic]:
    """Parse glslang output into diagnostics.

    *line_offset* is subtracted from every reported line number so that
    diagnostics map back to the user's original source.
    """
    diagnostics: list[Diagnostic] = []
    seen: set[tuple[int, str]] = set()

    for raw_line in log.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        m = _RE_GLSLANG.match(raw_line)
        if not m:
            continue
        sev_str = m.group(1).lower()
        line_num = int(m.group(2))
        message = m.group(3).strip()
        if "compilation terminated" in message.lower():
            continue
        severity = Severity.WARNING if sev_str == "warning" else Severity.ERROR
        adjusted_line = max(1, line_num - line_offset)
        key = (adjusted_line, message)
        if key in seen:
            continue
        seen.add(key)
        diagnostics.append(
            Diagnostic(
                line=adjusted_line,
                column=0,
                severity=severity,
                message=message,
            )
        )

    return diagnostics


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_validator_info() -> str:
    """Return a human-readable description of the active validation backend."""
    return "GLSL 4.50 \u2022 Vulkan Compute \u2022 Theron glslang"


_RE_BARE_INDEXED_NS = re.compile(
    r"\b(emitter|particles|newparticle)\.(\w+)",
)


def _check_bare_namespace_usage(source: str) -> list[Diagnostic]:
    """Detect bare use of indexed namespaces without ``[n]`` brackets."""
    diagnostics: list[Diagnostic] = []
    for i, line in enumerate(source.splitlines(), 1):
        for m in _RE_BARE_INDEXED_NS.finditer(line):
            ns = m.group(1)
            member = m.group(2)
            diagnostics.append(
                Diagnostic(
                    line=i,
                    column=m.start(),
                    severity=Severity.ERROR,
                    message=(
                        f"'{ns}' requires an index — use {ns}[n].{member} instead of {ns}.{member}"
                    ),
                )
            )
    return diagnostics


def _build_var_declarations(user_vars: tuple[tuple[str, str, bool, bool, str], ...]) -> str:
    if not user_vars:
        return ""
    seen: set[str] = set()
    lines: list[str] = []
    for var_name, var_type, writable, _particle, _value in user_vars:
        if not var_name or not var_name.strip() or var_name in seen:
            continue
        seen.add(var_name)
        glsl_type = _VAR_TYPE_TO_GLSL.get(var_type, "float")
        default = _VAR_GLSL_DEFAULTS.get(glsl_type, "0")
        qualifier = "" if writable else "const "
        lines.append(f"{qualifier}{glsl_type} {var_name} = {glsl_type}({default});")
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def validate_glsl(
    source: str,
    user_vars: tuple[tuple[str, str, bool, bool, str], ...] = (),
) -> list[Diagnostic]:
    """Validate *source* as GLSL and return diagnostics.

    The source undergoes Theron-style keyword replacement (e.g.
    ``particle.position`` -> ``particlePosition``) and is prepended with
    a validation preamble declaring all API variables and functions.

    Uses Theron's linked glslang to compile as a ``#version 450`` Vulkan
    compute shader (matching Theron's runtime).
    """
    if not source or not source.strip():
        return []

    compiler = _get_theron_compiler()
    if not compiler.available():
        return [
            Diagnostic(
                line=1,
                column=0,
                severity=Severity.ERROR,
                message="GLSL validation unavailable \u2014 Theron library not loaded",
            )
        ]

    bare_errors = _check_bare_namespace_usage(source)
    if bare_errors:
        return bare_errors

    processed = _replace_keywords(source)

    added_main_wrapper = False
    if not _RE_HAS_VOID_MAIN.search(processed):
        processed = "void main() {\n" + processed + "\n}\n"
        added_main_wrapper = True

    var_block = _build_var_declarations(user_vars)
    full_source = _VALIDATION_PREAMBLE_450 + var_block + processed
    source_bytes = full_source.encode("utf-8")
    success, log_text = compiler.compile(source_bytes)

    if success:
        return []
    if log_text:
        line_offset = _PREAMBLE_LINE_COUNT_450 + var_block.count("\n")
        if added_main_wrapper:
            line_offset += 1
        return _parse_glslang_log(log_text, line_offset)

    return []
