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

def hierarchy_get_descendants(collection, parent_idx):
    result = []
    for i, item in enumerate(collection):
        if item.parent_index == parent_idx:
            result.append(i)
            result.extend(hierarchy_get_descendants(collection, i))
    return result


def hierarchy_recalculate_indent_levels(collection):
    for i, item in enumerate(collection):
        level = 0
        pi = item.parent_index
        visited = set()
        while pi >= 0 and pi < len(collection) and pi not in visited:
            level += 1
            visited.add(pi)
            pi = collection[pi].parent_index
        item.indent_level = level


def hierarchy_fix_parent_indices_after_remove(collection, removed_indices):
    removed_set = set(removed_indices)
    index_map = {}
    new_idx = 0
    for old_idx in range(len(collection) + len(removed_indices)):
        if old_idx not in removed_set:
            index_map[old_idx] = new_idx
            new_idx += 1

    for item in collection:
        if item.parent_index >= 0:
            item.parent_index = index_map.get(item.parent_index, -1)


def hierarchy_is_ancestor_collapsed(collection, item):
    pi = item.parent_index
    visited = set()
    while pi >= 0 and pi < len(collection) and pi not in visited:
        visited.add(pi)
        if not collection[pi].expanded:
            return True
        pi = collection[pi].parent_index
    return False


def hierarchy_snapshot_item(item):
    snap = {}
    for prop in type(item).bl_rna.properties:
        if prop.is_readonly:
            continue
        pid = prop.identifier
        val = getattr(item, pid)
        if hasattr(prop, "array_length") and prop.array_length > 0:
            snap[pid] = list(val)
        else:
            snap[pid] = val
    return snap


def hierarchy_restore_item(item, snap):
    for pid, val in snap.items():
        try:
            setattr(item, pid, val)
        except (AttributeError, TypeError):
            pass
