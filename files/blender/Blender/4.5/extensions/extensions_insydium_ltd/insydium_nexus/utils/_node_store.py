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

"""Hidden-material node storage shared by the curve and gradient workarounds.

Blender still has no way to store ``CurveMapping`` or ``ColorRamp`` on a
``PropertyGroup``. Both subsystems work around this by allocating a hidden
material per kind, placing one ShaderNode per ``(object, slot)`` in it, and
referencing that node through a stable prefixed name derived from an object UID.
"""

import os
from dataclasses import dataclass

import bpy


@dataclass(frozen=True)
class NodeStoreConfig:
    material_name: str
    uid_prop: str
    node_prefix: str


def _generate_uid() -> str:
    return os.urandom(4).hex()


class NodeStore:
    __slots__ = ("_config",)

    def __init__(self, config: NodeStoreConfig):
        self._config = config

    @property
    def config(self) -> NodeStoreConfig:
        return self._config

    def get_material(self) -> bpy.types.Material | None:
        return bpy.data.materials.get(self._config.material_name)

    def ensure_material(self) -> bpy.types.Material:
        mat = bpy.data.materials.get(self._config.material_name)
        if mat is None:
            mat = bpy.data.materials.new(self._config.material_name)
            mat.use_nodes = True
            mat.use_fake_user = True
        return mat

    def get_uid(self, obj: bpy.types.Object) -> str | None:
        return obj.get(self._config.uid_prop)

    def set_uid(self, obj: bpy.types.Object, uid: str) -> None:
        obj[self._config.uid_prop] = uid

    def get_or_create_uid(self, obj: bpy.types.Object) -> str:
        uid = self.get_uid(obj)
        if uid is None:
            uid = _generate_uid()
            self.set_uid(obj, uid)
        return uid

    def rotate_uid(self, obj: bpy.types.Object) -> str:
        uid = _generate_uid()
        self.set_uid(obj, uid)
        return uid

    def node_name(self, uid: str, slot: str) -> str:
        return f"{self._config.node_prefix}{uid}.{slot}"

    def get_node(self, obj: bpy.types.Object, slot: str) -> bpy.types.ShaderNode | None:
        uid = self.get_uid(obj)
        if uid is None:
            return None
        return self.get_node_by_uid(uid, slot)

    def get_node_by_uid(self, uid: str, slot: str) -> bpy.types.ShaderNode | None:
        mat = self.get_material()
        if mat is None or mat.node_tree is None:
            return None
        return mat.node_tree.nodes.get(self.node_name(uid, slot))

    def remove_nodes_for(self, obj: bpy.types.Object) -> int:
        uid = self.get_uid(obj)
        if uid is None:
            return 0

        mat = self.get_material()
        if mat is None or mat.node_tree is None:
            return 0

        prefix = f"{self._config.node_prefix}{uid}."
        to_remove = [node for node in mat.node_tree.nodes if node.name.startswith(prefix)]
        for node in to_remove:
            mat.node_tree.nodes.remove(node)
        return len(to_remove)

    def is_shared(self, obj: bpy.types.Object) -> bool:
        uid = self.get_uid(obj)
        if uid is None:
            return False

        for other in bpy.data.objects:
            if other.name == obj.name:
                continue
            if other.get(self._config.uid_prop) == uid:
                return True
        return False

    def iter_live_uids(self) -> set[str]:
        return {
            uid for obj in bpy.data.objects if (uid := obj.get(self._config.uid_prop)) is not None
        }

    def cleanup_orphans(self, valid_uids: set[str] | None = None) -> int:
        mat = self.get_material()
        if mat is None or mat.node_tree is None:
            return 0

        live = self.iter_live_uids() if valid_uids is None else valid_uids
        prefix = self._config.node_prefix

        to_remove = []
        for node in mat.node_tree.nodes:
            if not node.name.startswith(prefix):
                continue
            parts = node.name.split(".", 4)
            if len(parts) < 4:
                continue
            if parts[2] not in live:
                to_remove.append(node)

        for node in to_remove:
            mat.node_tree.nodes.remove(node)

        return len(to_remove)
