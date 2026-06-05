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

import json
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar


@dataclass
class BasePreset:
    preset_id: str
    name: str


T = TypeVar("T", bound=BasePreset)


class PresetStore(Generic[T], ABC):
    log_label = "preset"

    def __init__(self, filename: str):
        self._filename = filename
        self._path: str | None = None
        self._presets: list[T] = []
        self._map: dict[str, T] = {}

    def init(self, addon_package: str) -> None:
        try:
            import bpy

            presets_dir = bpy.utils.extension_path_user(addon_package, path="presets", create=True)
        except Exception:
            presets_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                ".user_presets",
            )
            os.makedirs(presets_dir, exist_ok=True)

        self._path = os.path.join(presets_dir, self._filename)
        self.load()

    def load(self) -> None:
        self._presets.clear()
        self._map.clear()

        if self._path is None or not os.path.isfile(self._path):
            return

        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            print(f"NeXus: Could not load user {self.log_label}s: {e}")
            return

        if not isinstance(data, dict):
            print(f"NeXus: Could not load user {self.log_label}s: invalid JSON root type")
            return

        presets = data.get("presets", [])
        if not isinstance(presets, list):
            print(f"NeXus: Could not load user {self.log_label}s: invalid presets payload")
            return

        for entry in presets:
            preset = self._deserialise(entry)
            if preset is None:
                continue
            self._presets.append(preset)
            self._map[preset.preset_id] = preset

        self._load_extra(data)

    def save(self) -> None:
        if self._path is None:
            return

        data: dict = {
            "version": 1,
            "presets": [self._serialise(preset) for preset in self._presets],
        }
        self._save_extra(data)

        try:
            dir_path = os.path.dirname(self._path)
            os.makedirs(dir_path, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=dir_path, delete=False, suffix=".tmp", mode="w", encoding="utf-8"
            ) as tmp:
                json.dump(data, tmp, indent=2)
                tmp_path = tmp.name
            os.replace(tmp_path, self._path)
        except OSError as e:
            print(f"NeXus: Could not save user {self.log_label}s: {e}")

    def add(self, preset: T) -> str:
        self._presets.append(preset)
        self._map[preset.preset_id] = preset
        self.save()
        return preset.preset_id

    def rename(self, preset_id: str, new_name: str) -> bool:
        preset = self._map.get(preset_id)
        if preset is None:
            return False
        preset.name = new_name
        self.save()
        return True

    def remove(self, preset_id: str) -> bool:
        preset = self._map.pop(preset_id, None)
        if preset is None:
            return False
        self._presets.remove(preset)
        self.save()
        return True

    def get(self, preset_id: str) -> T | None:
        return self._map.get(preset_id)

    def get_all(self) -> list[T]:
        return list(self._presets)

    def new_id(self) -> str:
        return f"user_{os.urandom(4).hex()}"

    @abstractmethod
    def _serialise(self, preset: T) -> dict:
        raise NotImplementedError

    @abstractmethod
    def _deserialise(self, entry: dict) -> T | None:
        raise NotImplementedError

    def _load_extra(self, data: dict) -> None:
        pass

    def _save_extra(self, data: dict) -> None:
        pass


class CategorisedPresetStore(PresetStore[T]):
    def __init__(self, filename: str):
        super().__init__(filename)
        self._categories: dict[str, list[str]] = {}

    def load(self) -> None:
        self._categories.clear()
        super().load()

    def _load_extra(self, data: dict) -> None:
        raw_categories = data.get("categories", {})
        if not isinstance(raw_categories, dict):
            return

        for key, names in raw_categories.items():
            if not isinstance(names, list):
                continue
            self._categories[key] = list(names)

    def _save_extra(self, data: dict) -> None:
        data["categories"] = dict(self._categories)

    def get_categories(self, key: str) -> list[str]:
        return list(self._categories.get(key, []))

    def ensure_category(self, key: str, name: str) -> None:
        if not name:
            return
        cat_list = self._categories.setdefault(key, [])
        if name not in cat_list:
            cat_list.append(name)

    def create_category(self, key: str, name: str) -> bool:
        cat_list = self._categories.setdefault(key, [])
        if name in cat_list:
            return False
        cat_list.append(name)
        self.save()
        return True

    def rename_category(self, key: str, old_name: str, new_name: str) -> int:
        if not old_name or not new_name or old_name == new_name:
            return 0

        cat_list = self._categories.get(key, [])
        for idx, name in enumerate(cat_list):
            if name == old_name:
                cat_list[idx] = new_name
                break

        count = 0
        for preset in self._presets:
            if self._category_key(preset) == key and self._category_of(preset) == old_name:
                self._set_category(preset, new_name)
                count += 1

        self.save()
        return count

    def delete_category(self, key: str, name: str) -> int:
        cat_list = self._categories.get(key, [])
        self._categories[key] = [category for category in cat_list if category != name]

        count = 0
        for preset in self._presets:
            if self._category_key(preset) == key and self._category_of(preset) == name:
                self._set_category(preset, "")
                count += 1

        self.save()
        return count

    def _category_key(self, preset: T) -> str:
        raise NotImplementedError

    def _category_of(self, preset: T) -> str:
        raise NotImplementedError

    def _set_category(self, preset: T, category: str) -> None:
        raise NotImplementedError
