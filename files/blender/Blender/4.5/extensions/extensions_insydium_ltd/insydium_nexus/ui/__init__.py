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

from .nodetree import (
    NodeTreeDef,
    PerItemToggle,
    auto_rename,
    combine_nodetree_sync,
    draw_nodetree,
    draw_nodetree_hierarchy,
    get_child_cleanup_configs,
    get_nodetree_config,
    get_pending_ghost_slots,
    hierarchy_get_descendants,
    hierarchy_recalculate_indent_levels,
    make_allowed_types_poll,
    make_drop_target_update,
    register_nodetree,
    validate_pending_nx_types,
)
from .nodetree import (
    register as register_nodetree_module,
)
from .nodetree import (
    unregister as unregister_nodetree_module,
)

__all__ = [
    "NodeTreeDef",
    "PerItemToggle",
    "auto_rename",
    "combine_nodetree_sync",
    "draw_nodetree",
    "draw_nodetree_hierarchy",
    "get_child_cleanup_configs",
    "get_nodetree_config",
    "get_pending_ghost_slots",
    "hierarchy_get_descendants",
    "hierarchy_recalculate_indent_levels",
    "make_allowed_types_poll",
    "make_drop_target_update",
    "register_nodetree",
    "validate_pending_nx_types",
]


def register():
    register_nodetree_module()


def unregister():
    unregister_nodetree_module()
