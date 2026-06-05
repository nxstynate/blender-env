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

import json
from pathlib import Path
from typing import Dict, Optional

_ids: Optional[Dict[str, int]] = None


def _ensure_loaded() -> Dict[str, int]:
    global _ids
    if _ids is None:
        json_path = Path(__file__).parent / "theron_ids.json"
        if not json_path.exists():
            raise FileNotFoundError(
                f"theron_ids.json not found at {json_path}. "
                "Run: python tools/generate_theron_ids.py"
            )
        with open(json_path, "r") as f:
            data = json.load(f)
        _ids = data.get("ids", data)
    return _ids


def get(name: str) -> int:
    ids = _ensure_loaded()
    if name not in ids:
        prefix = name.rsplit("_", 1)[0] + "_" if "_" in name else name[:10]
        similar = [k for k in ids.keys() if k.startswith(prefix)][:5]
        hint = f" Similar: {', '.join(similar)}" if similar else ""
        raise KeyError(f"'{name}' not found in theron_ids.json.{hint}")
    return ids[name]


def get_all() -> Dict[str, int]:
    return dict(_ensure_loaded())


def has(name: str) -> bool:
    return name in _ensure_loaded()


THERON_IS_ACTIVE = 100
