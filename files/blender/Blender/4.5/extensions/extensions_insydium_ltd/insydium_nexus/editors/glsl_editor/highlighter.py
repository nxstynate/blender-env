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

import os
import sys

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "..", "vendor")
try:
    from PyQt6 import QtCore, QtGui  # noqa: E402
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Module-level token lists (importable by the completer and other modules)
# ---------------------------------------------------------------------------

GLSL_KEYWORDS = [
    "break",
    "case",
    "continue",
    "default",
    "discard",
    "do",
    "else",
    "for",
    "if",
    "return",
    "switch",
    "while",
    "const",
    "in",
    "inout",
    "out",
    "uniform",
    "varying",
    "attribute",
    "layout",
    "flat",
    "smooth",
    "centroid",
    "struct",
    "precision",
    "highp",
    "mediump",
    "lowp",
    "true",
    "false",
    "buffer",
    "shared",
    "coherent",
    "volatile",
    "restrict",
    "readonly",
    "writeonly",
]

GLSL_TYPES = [
    "void",
    "bool",
    "int",
    "uint",
    "float",
    "double",
    "vec2",
    "vec3",
    "vec4",
    "ivec2",
    "ivec3",
    "ivec4",
    "uvec2",
    "uvec3",
    "uvec4",
    "bvec2",
    "bvec3",
    "bvec4",
    "mat2",
    "mat3",
    "mat4",
    "mat2x2",
    "mat2x3",
    "mat2x4",
    "mat3x2",
    "mat3x3",
    "mat3x4",
    "mat4x2",
    "mat4x3",
    "mat4x4",
    "dvec2",
    "dvec3",
    "dvec4",
    "dmat2",
    "dmat3",
    "dmat4",
    "sampler1D",
    "sampler2D",
    "sampler3D",
    "samplerCube",
    "sampler2DShadow",
    "samplerCubeShadow",
]

GLSL_BUILTIN_FUNCTIONS = [
    "abs",
    "acos",
    "all",
    "any",
    "asin",
    "atan",
    "ceil",
    "clamp",
    "cos",
    "cross",
    "degrees",
    "distance",
    "dot",
    "equal",
    "exp",
    "exp2",
    "faceforward",
    "floor",
    "fract",
    "greaterThan",
    "greaterThanEqual",
    "inversesqrt",
    "length",
    "lessThan",
    "lessThanEqual",
    "log",
    "log2",
    "max",
    "min",
    "mix",
    "mod",
    "normalize",
    "not",
    "notEqual",
    "pow",
    "radians",
    "reflect",
    "refract",
    "round",
    "sign",
    "sin",
    "smoothstep",
    "sqrt",
    "step",
    "tan",
    "texture",
    "texture2D",
    "texture3D",
    "textureCube",
    "transpose",
    "trunc",
    "dFdx",
    "dFdy",
    "fwidth",
    "floatBitsToInt",
    "floatBitsToUint",
    "intBitsToFloat",
    "uintBitsToFloat",
    "texelFetch",
    "textureSize",
    "textureLod",
    "isnan",
    "isinf",
    "modf",
    "fma",
    "bitfieldExtract",
    "bitCount",
    "findMSB",
    "findLSB",
    "packUnorm2x16",
    "unpackUnorm2x16",
]

NEXUS_BUILTIN_FUNCTIONS = [
    "particle",
    "particles",
    "doc",
    "emitter",
    "emitters",
    "newparticle",
    "compute",
    "math",
]

# Block states for multi-line comment tracking
_STATE_NORMAL = 0
_STATE_IN_MULTILINE_COMMENT = 1


def _build_word_pattern(words):
    joined = "|".join(words)
    return QtCore.QRegularExpression(r"\b(" + joined + r")\b")


class GLSLSyntaxHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._rules = []

        self._build_rules()
        self._multiline_comment_format = self._make_format(theme.comment, italic=True)
        self._comment_start = QtCore.QRegularExpression(r"/\*")
        self._comment_end = QtCore.QRegularExpression(r"\*/")

    def _make_format(self, color_str, bold=False, italic=False):
        fmt = QtGui.QTextCharFormat()
        fmt.setForeground(QtGui.QColor(color_str))
        if bold:
            fmt.setFontWeight(QtGui.QFont.Weight.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt

    def _build_rules(self):
        theme = self._theme

        keyword_fmt = self._make_format(theme.keyword, bold=True)
        self._rules.append((_build_word_pattern(GLSL_KEYWORDS), keyword_fmt))

        type_fmt = self._make_format(theme.type_color)
        self._rules.append((_build_word_pattern(GLSL_TYPES), type_fmt))

        all_builtins = GLSL_BUILTIN_FUNCTIONS + NEXUS_BUILTIN_FUNCTIONS
        builtin_fmt = self._make_format(theme.builtin_func)
        self._rules.append((_build_word_pattern(all_builtins), builtin_fmt))

        number_fmt = self._make_format(theme.number)
        self._rules.append(
            (
                QtCore.QRegularExpression(r"\b\d+\.?\d*([eE][+-]?\d+)?[fFuU]?\b"),
                number_fmt,
            )
        )
        self._rules.append(
            (
                QtCore.QRegularExpression(r"\b0[xX][0-9a-fA-F]+[uU]?\b"),
                number_fmt,
            )
        )

        string_fmt = self._make_format(theme.string)
        self._rules.append(
            (
                QtCore.QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'),
                string_fmt,
            )
        )

        preprocessor_fmt = self._make_format(theme.preprocessor)
        self._rules.append(
            (
                QtCore.QRegularExpression(
                    r"^\s*#\w+.*$",
                    QtCore.QRegularExpression.PatternOption.MultilineOption,
                ),
                preprocessor_fmt,
            )
        )

        comment_fmt = self._make_format(theme.comment, italic=True)
        self._rules.append(
            (
                QtCore.QRegularExpression(r"//[^\n]*"),
                comment_fmt,
            )
        )

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            match_iter = pattern.globalMatch(text)
            while match_iter.hasNext():
                match = match_iter.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

        self._apply_multiline_comments(text)

    def _apply_multiline_comments(self, text):
        self.setCurrentBlockState(_STATE_NORMAL)

        if self.previousBlockState() == _STATE_IN_MULTILINE_COMMENT:
            start_index = 0
            end_search_offset = 0
        else:
            match = self._comment_start.match(text)
            if match.hasMatch():
                start_index = match.capturedStart()
                end_search_offset = start_index + 2
            else:
                start_index = -1
                end_search_offset = 0

        while start_index >= 0:
            end_match = self._comment_end.match(text, end_search_offset)

            if not end_match.hasMatch():
                self.setCurrentBlockState(_STATE_IN_MULTILINE_COMMENT)
                comment_length = len(text) - start_index
            else:
                comment_length = end_match.capturedEnd() - start_index

            self.setFormat(start_index, comment_length, self._multiline_comment_format)

            next_match = self._comment_start.match(text, start_index + comment_length)
            if next_match.hasMatch():
                start_index = next_match.capturedStart()
                end_search_offset = start_index + 2
            else:
                start_index = -1
