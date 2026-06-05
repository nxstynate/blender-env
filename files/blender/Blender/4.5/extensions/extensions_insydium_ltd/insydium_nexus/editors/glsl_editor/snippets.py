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

"""Snippet definitions and tabstop parser for the GLSL Script Editor.

Pure Python -- no PyQt5 dependency.
"""

from __future__ import annotations

import dataclasses
import re


@dataclasses.dataclass(frozen=True, slots=True)
class SnippetDef:
    trigger: str
    label: str
    body: str
    description: str


@dataclasses.dataclass(slots=True)
class ParsedTabstop:
    index: int
    placeholder: str
    offset: int
    length: int


@dataclasses.dataclass(slots=True)
class ParsedSnippet:
    text: str
    tabstops: list[ParsedTabstop]


_RE_TABSTOP = re.compile(r"\$\{(\d+):([^}]*)\}|\$(\d+)")


def parse_snippet_body(body: str, indent: str, indent_unit: str) -> ParsedSnippet:
    """Parse a snippet body with tabstop markers.

    *indent* is the leading whitespace of the line where the snippet
    is being inserted.  *indent_unit* is the editor's indent string
    (spaces or tab).
    """
    text = body.replace("\\n", "\n").replace("\\t", indent_unit)

    lines = text.split("\n")
    for i in range(1, len(lines)):
        lines[i] = indent + lines[i]
    text = "\n".join(lines)

    placeholders: dict[int, str] = {}
    for m in _RE_TABSTOP.finditer(text):
        if m.group(1) is not None:
            idx = int(m.group(1))
            if idx not in placeholders:
                placeholders[idx] = m.group(2)
        else:
            idx = int(m.group(3))
            if idx not in placeholders:
                placeholders[idx] = ""

    tabstops: list[ParsedTabstop] = []
    result_parts: list[str] = []
    last_end = 0
    offset = 0

    for m in _RE_TABSTOP.finditer(text):
        before = text[last_end : m.start()]
        result_parts.append(before)
        offset += len(before)

        if m.group(1) is not None:
            idx = int(m.group(1))
            placeholder = m.group(2)
        else:
            idx = int(m.group(3))
            placeholder = placeholders.get(idx, "")

        tabstops.append(
            ParsedTabstop(
                index=idx,
                placeholder=placeholder,
                offset=offset,
                length=len(placeholder),
            )
        )
        result_parts.append(placeholder)
        offset += len(placeholder)
        last_end = m.end()

    result_parts.append(text[last_end:])
    return ParsedSnippet(text="".join(result_parts), tabstops=tabstops)


# -- Snippet registry -------------------------------------------------------

GLSL_SNIPPETS: tuple[SnippetDef, ...] = (
    SnippetDef(
        "for",
        "for loop",
        "for (int ${1:i} = ${2:0}; $1 < ${3:count}; $1++) {\\n\\t${0}\\n}",
        "for (int i = 0; i < count; i++)",
    ),
    SnippetDef(
        "if",
        "if statement",
        "if (${1:condition}) {\\n\\t${0}\\n}",
        "if (condition) { ... }",
    ),
    SnippetDef(
        "ife",
        "if-else",
        "if (${1:condition}) {\\n\\t${2}\\n} else {\\n\\t${0}\\n}",
        "if-else block",
    ),
    SnippetDef(
        "while",
        "while loop",
        "while (${1:condition}) {\\n\\t${0}\\n}",
        "while (condition) { ... }",
    ),
    SnippetDef(
        "fn",
        "function",
        "${1:void} ${2:name}(${3:params}) {\\n\\t${0}\\n}",
        "function definition",
    ),
    SnippetDef(
        "func",
        "function",
        "${1:void} ${2:name}(${3:params}) {\\n\\t${0}\\n}",
        "function definition",
    ),
    SnippetDef(
        "struct",
        "struct",
        "struct ${1:Name} {\\n\\t${0}\\n};",
        "struct definition",
    ),
    SnippetDef(
        "main",
        "main function",
        "void main() {\\n\\t${0}\\n}",
        "void main() { ... }",
    ),
    SnippetDef(
        "vec3",
        "vec3 constructor",
        "vec3(${1:0.0}, ${2:0.0}, ${3:0.0})",
        "vec3(x, y, z)",
    ),
    SnippetDef(
        "vec4",
        "vec4 constructor",
        "vec4(${1:0.0}, ${2:0.0}, ${3:0.0}, ${4:1.0})",
        "vec4(x, y, z, w)",
    ),
)

_SNIPPET_BY_TRIGGER: dict[str, SnippetDef] = {s.trigger: s for s in GLSL_SNIPPETS}


def get_snippet_by_trigger(trigger: str) -> SnippetDef | None:
    return _SNIPPET_BY_TRIGGER.get(trigger)


def get_snippet_completions(prefix: str) -> list[SnippetDef]:
    """Return SnippetDefs matching *prefix* (case-insensitive prefix match)."""
    results = []
    for snippet in GLSL_SNIPPETS:
        if snippet.trigger.startswith(prefix.lower()):
            results.append(snippet)
    return results
