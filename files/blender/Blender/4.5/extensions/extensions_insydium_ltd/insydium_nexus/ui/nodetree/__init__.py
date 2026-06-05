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

import bpy
from bpy.props import IntProperty, StringProperty

from . import auto_rename
from .hierarchy import (
    hierarchy_fix_parent_indices_after_remove,
    hierarchy_get_descendants,
    hierarchy_is_ancestor_collapsed,
    hierarchy_recalculate_indent_levels,
    hierarchy_restore_item,
    hierarchy_snapshot_item,
)
from .operators import (
    NEXUS_MT_nodetree_add,
    NEXUS_OT_nodetree_add,
    NEXUS_OT_nodetree_clear,
    NEXUS_OT_nodetree_continuous_pick,
    NEXUS_OT_nodetree_create_and_add,
    NEXUS_OT_nodetree_hierarchy_folder_settings,
    NEXUS_OT_nodetree_hierarchy_indent,
    NEXUS_OT_nodetree_hierarchy_move,
    NEXUS_OT_nodetree_hierarchy_outdent,
    NEXUS_OT_nodetree_hierarchy_remove,
    NEXUS_OT_nodetree_move,
    NEXUS_OT_nodetree_remove,
    NEXUS_OT_nodetree_show_add_menu,
    NEXUS_OT_nodetree_toggle_enable,
    NEXUS_OT_nodetree_toggle_icon_flag,
    add_nodetree_item,
)
from .registry import (
    PerItemToggle,
    _nodetree_data_paths,
    _nodetree_per_item_toggles,
    _nodetree_registry,
    _nodetree_tree_types,
    get_child_cleanup_configs,
    get_nodetree_config,
    get_pending_ghost_slots,
    make_allowed_types_poll,
    make_drop_target_update,
    register_nodetree,
    validate_pending_nx_types,
)
from .ui import (
    NEXUS_UL_nodetree,
    NEXUS_UL_nodetree_hierarchy,
    NexusNodeTreeItem,
    NodeTreeDef,
    combine_nodetree_sync,
    draw_nodetree,
    draw_nodetree_hierarchy,
)

__all__ = [
    "NodeTreeDef",
    "NexusNodeTreeItem",
    "PerItemToggle",
    "add_nodetree_item",
    "auto_rename",
    "combine_nodetree_sync",
    "draw_nodetree",
    "draw_nodetree_hierarchy",
    "get_child_cleanup_configs",
    "get_nodetree_config",
    "get_pending_ghost_slots",
    "hierarchy_fix_parent_indices_after_remove",
    "hierarchy_get_descendants",
    "hierarchy_is_ancestor_collapsed",
    "hierarchy_recalculate_indent_levels",
    "hierarchy_restore_item",
    "hierarchy_snapshot_item",
    "make_allowed_types_poll",
    "make_drop_target_update",
    "register_nodetree",
    "validate_pending_nx_types",
]

classes = [
    NexusNodeTreeItem,
    NEXUS_OT_nodetree_toggle_enable,
    NEXUS_OT_nodetree_toggle_icon_flag,
    NEXUS_UL_nodetree,
    NEXUS_OT_nodetree_add,
    NEXUS_OT_nodetree_remove,
    NEXUS_OT_nodetree_move,
    NEXUS_OT_nodetree_clear,
    NEXUS_OT_nodetree_continuous_pick,
    NEXUS_OT_nodetree_create_and_add,
    NEXUS_OT_nodetree_show_add_menu,
    NEXUS_MT_nodetree_add,
    NEXUS_UL_nodetree_hierarchy,
    NEXUS_OT_nodetree_hierarchy_remove,
    NEXUS_OT_nodetree_hierarchy_move,
    NEXUS_OT_nodetree_hierarchy_indent,
    NEXUS_OT_nodetree_hierarchy_outdent,
    NEXUS_OT_nodetree_hierarchy_folder_settings,
]


def register():
    from bpy.utils import register_class, unregister_class

    for cls in classes:
        try:
            unregister_class(cls)
        except Exception:
            pass
        register_class(cls)

    bpy.types.WindowManager.nexus_nodetree_menu_id = StringProperty(
        name="Nodetree Menu ID",
        description="Current menu ID for nodetree add menu",
        default="",
    )
    bpy.types.WindowManager.nexus_nodetree_data_path = StringProperty(
        name="Nodetree Data Path",
        description="RNA path to the data object for nested nodetrees",
        default="",
    )
    bpy.types.WindowManager.nexus_nodetree_pre_add_index = IntProperty(
        name="Pre-Add Index",
        default=-1,
    )
    bpy.types.WindowManager.nexus_hierarchy_menu_id = StringProperty(
        name="Hierarchy Menu ID",
        description="Current menu ID for hierarchy poll checks",
        default="",
    )
    bpy.types.WindowManager.nexus_hierarchy_data_path = StringProperty(
        name="Hierarchy Data Path",
        description="RNA path for hierarchy poll checks",
        default="",
    )


def unregister():
    if hasattr(bpy.types.WindowManager, "nexus_nodetree_menu_id"):
        del bpy.types.WindowManager.nexus_nodetree_menu_id
    if hasattr(bpy.types.WindowManager, "nexus_nodetree_data_path"):
        del bpy.types.WindowManager.nexus_nodetree_data_path
    if hasattr(bpy.types.WindowManager, "nexus_nodetree_pre_add_index"):
        del bpy.types.WindowManager.nexus_nodetree_pre_add_index
    if hasattr(bpy.types.WindowManager, "nexus_hierarchy_menu_id"):
        del bpy.types.WindowManager.nexus_hierarchy_menu_id
    if hasattr(bpy.types.WindowManager, "nexus_hierarchy_data_path"):
        del bpy.types.WindowManager.nexus_hierarchy_data_path

    _nodetree_registry.clear()
    _nodetree_data_paths.clear()
    _nodetree_tree_types.clear()
    _nodetree_per_item_toggles.clear()

    from bpy.utils import unregister_class

    for cls in reversed(classes):
        try:
            unregister_class(cls)
        except RuntimeError:
            pass
