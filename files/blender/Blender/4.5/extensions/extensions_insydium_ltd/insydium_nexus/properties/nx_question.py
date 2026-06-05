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
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
    PointerProperty,
)

from ..libs.modifier_preset_spec import CollectionPresetSpec, register_collection_preset
from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nexus_time import (
    draw_time_prop,
    get_prop_time_mode,
    nexus_time_property,
    to_time_fraction,
)
from ..libs.cache_spec import CacheKind, CacheSpec, ensure_camera_entry, evict_stale_entries_for
from ..libs.nodetree_sync import NodeTreeSyncSpec, make_cached_link_resolver, sync_nodetree
from ..libs.theron_sync import TRANSFORM_FACTORS, Transform
from ..ui.nodetree import (
    NexusNodeTreeItem,
    auto_rename,
    make_allowed_types_poll,
    make_drop_target_update,
    draw_nodetree,
)

from ..utils.tinted_icon import TintedIconCache

question_folder_icons = TintedIconCache("nx_question_folder")

QUESTION_NODE_TYPE_DEFS = {
    "QUESTION": {
        "name": "Question",
        "description": "If/Else conditional",
        "icon_name": "nx_question",
        "blender_icon": "QUESTION",
    },
    "ACTION": {
        "name": "Action",
        "description": "Set particle property or kill/spawn",
        "icon_name": "nx_question_action",
        "blender_icon": "PLAY",
    },
    "FOLDER": {
        "name": "Folder",
        "description": "Organizational folder",
        "icon_name": "nx_question_folder",
        "blender_icon": "FILE_FOLDER",
    },
    "LOOP": {
        "name": "Loop",
        "description": "Loop iteration",
        "icon_name": "nx_question_loop",
        "blender_icon": "FILE_REFRESH",
    },
    "VAR": {
        "name": "Variable",
        "description": "Variable declaration",
        "icon_name": "nx_question_var",
        "blender_icon": "DRIVER",
    },
    "SCRIPT": {
        "name": "Script",
        "description": "Custom GLSL script",
        "icon_name": "nx_question_script",
        "blender_icon": "SCRIPT",
    },
}

QUESTION_CONDITION_ITEMS = [
    ("IF", "If", "If condition"),
    ("ELSEIF", "Else If", "Else if condition"),
    ("ELSE", "Else", "Else fallback"),
]

QUESTION_OPERATOR_ITEMS = [
    ("NONE", "-", "No operator"),
    ("AND", "AND", "Logical AND"),
    ("AND_NOT", "AND NOT", "Logical AND NOT"),
    ("OR", "OR", "Logical OR"),
    ("OR_NOT", "OR NOT", "Logical OR NOT"),
]

QUESTION_IF_PARAM_ITEMS = [
    ("DOCUMENT", "Document", "Document-level condition"),
    ("PARTICLE", "Particle", "Particle-level condition"),
    ("MATH", "Math", "Math-based condition"),
]

QUESTION_IF_PARTICLE_ITEMS = [
    ("AGE", "Age", "Particle age"),
    ("COLOR", "Color", "Particle color"),
    ("COUNT", "Count", "Particle count"),
    ("DENSITY", "Fluid Density", "Fluid density"),
    ("DISTANCE", "Traveled", "Distance traveled"),
    ("EMITTER", "Emitter", "Emitter"),
    ("FALLOFF", "Field", "Falloff field"),
    ("FLAGS", "Flags", "Particle flags"),
    ("FUEL", "Fuel", "Fuel value"),
    ("GROUP", "Group", "Particle group"),
    ("ID", "ID", "Particle ID"),
    ("LIFE", "Life", "Particle lifetime"),
    ("MASS", "Mass", "Particle mass"),
    ("NEIGHBORS", "Neighbors", "Neighbor count"),
    ("POSITION", "Position", "Particle position"),
    ("RADIUS", "Radius", "Particle radius"),
    ("ROTATION", "Rotation", "Particle rotation"),
    ("SMOKE", "Smoke", "Smoke value"),
    ("SPEED", "Speed", "Particle speed"),
    ("TEMPERATURE", "Temperature", "Temperature value"),
    ("UVW", "UVW", "UVW coordinates"),
    ("VELOCITY", "Velocity", "Particle velocity"),
    ("VERTEXWEIGHT", "Vertex Weight", "Vertex weight"),
]

QUESTION_IF_VECTOR_ITEMS = [
    ("X", "X", "X component"),
    ("Y", "Y", "Y component"),
    ("Z", "Z", "Z component"),
    ("R", "R", "Red channel"),
    ("G", "G", "Green channel"),
    ("B", "B", "Blue channel"),
    ("BRIGHTNESS", "Brightness", "Color brightness"),
    ("RH", "H", "Rotation heading"),
    ("RP", "P", "Rotation pitch"),
    ("RB", "B", "Rotation bank"),
]

QUESTION_IF_DOCUMENT_ITEMS = [
    ("FRAME", "Frame", "Current frame"),
    ("CAMERA_DISTANCE", "Camera Distance", "Distance to camera"),
    ("CAMERA_FOV", "Camera FOV", "Camera field of view"),
    ("OBJECT_DISTANCE", "Object Distance", "Distance to object"),
    ("TIME", "Time", "Document time"),
]

QUESTION_IF_MATH_ITEMS = [
    ("CONST", "Value", "Constant value"),
    ("RANDOM", "Random", "Random value"),
    ("SPLINE", "Spline", "Spline-based value"),
    ("VAR", "Variable", "Variable value"),
    ("WAVE", "Wave", "Wave function"),
]

QUESTION_IF_OP_ITEMS = [
    ("LESS", "Less", "Less than"),
    ("LESSEQUAL", "Less-Equal", "Less than or equal"),
    ("EQUAL", "Equal", "Equal to"),
    ("NOTEQUAL", "Not Equal", "Not equal to"),
    ("GREATEREQUAL", "Greater-Equal", "Greater than or equal"),
    ("GREATER", "Greater", "Greater than"),
    ("WITHIN", "Within", "Within range"),
    ("NOTWITHIN", "Not Within", "Not within range"),
]

QUESTION_IF_INCLUDE_ITEMS = [
    ("WITHIN", "Within", "Included in set"),
    ("NOTWITHIN", "Not Within", "Not included in set"),
]

QUESTION_IF_MATH_DEPENDTIME_ITEMS = [
    ("OFF", "None", "No time dependency"),
    ("DOCUMENT", "Document", "Document time"),
    ("PARTICLE", "Particle", "Particle time"),
]

QUESTION_IF_DOCUMENT_OBJECT_MODE_ITEMS = [
    ("POINTS", "Points", "Point distance mode"),
    ("POSITION", "Position", "Position distance mode"),
    ("POLYGONS", "Polygons", "Polygon distance mode"),
    ("VOLUME", "Volume", "Volume distance mode"),
]

QUESTION_THEN_ITEMS = [
    ("ADD", "Add", "Add to particle property"),
    ("SET", "Set", "Set particle property"),
    ("SPAWN", "Spawn", "Spawn new particles"),
    ("KILL", "Kill", "Kill particle"),
    ("BREAK", "Break", "Break out of loop"),
]

QUESTION_SET_ITEMS = [
    ("AGE", "Age", "Set particle age"),
    ("COLOR", "Color", "Set particle color"),
    ("DISPLAY", "Display", "Set particle display"),
    ("FREEZE", "Freeze", "Set particle freeze"),
    ("GROUP", "Group", "Set particle group"),
    ("LIFE", "Life", "Set particle lifetime"),
    ("MASS", "Mass", "Set particle mass"),
    ("RADIUS", "Radius", "Set particle radius"),
    ("ROTATION", "Rotation", "Set particle rotation"),
    ("SCALE", "Scale", "Set particle scale"),
    ("SPEED", "Speed", "Set particle speed"),
    ("STICKY", "Sticky", "Set particle sticky"),
    ("USERDATA", "User Data", "Set user data"),
    ("VAR", "Variable", "Set variable"),
    ("VELOCITY", "Velocity", "Set particle velocity"),
]

QUESTION_SET_VAR_TO_ITEMS = [
    ("CONST", "Constant", "Set to constant value"),
    ("VALUE", "Question", "Set to current value"),
]

QUESTION_SET_PARTICLE_DISPLAY_ITEMS = [
    (
        "POINTS",
        "Points",
        "Display particles as dots",
    ),
    (
        "SQUARE",
        "Square",
        "Display particles as squares",
    ),
    (
        "DIRECTION",
        "Line",
        "Display particles as lines",
    ),
    (
        "BOX3D",
        "Box 3D",
        "Display particles as 3D boxes",
    ),
    (
        "BOX3D_FILLED",
        "Box 3D Filled",
        "Solid 3D boxes",
    ),
    (
        "CIRCLE",
        "Circle",
        "Display particles as circles",
    ),
    (
        "CIRCLE_FILLED",
        "Circle Filled",
        "Filled circles",
    ),
    (
        "PYRAMID",
        "Pyramid",
        "Display particles as pyramids",
    ),
    (
        "PYRAMID_FILLED",
        "Pyramid Filled",
        "Solid pyramids",
    ),
    (
        "ARROW",
        "Arrow",
        "Display particles as arrows",
    ),
    (
        "ARROW_FILLED",
        "Arrow Filled",
        "Solid arrows",
    ),
    (
        "AXIS",
        "Axis",
        "Display particle local axes (X=red, Y=green, Z=blue)",
    ),
    (
        "SPHERE",
        "Sphere",
        "Display particles as solid 3D spheres",
    ),
    (
        "SSF",
        "Screen Space Fluid",
        "Render particles as a screen-space fluid surface (OpenGL only)",
    ),
    ("NONE", "None", "Hide particle display"),
]

QUESTION_SPAWN_VELOCITY_DIR_ITEMS = [
    ("RANDOM", "Random", "Random spawn direction"),
    ("SOURCE", "Source", "Inherit source direction"),
]

QUESTION_LOOP_TYPE_ITEMS = [
    ("FOR_EACH", "For Each", "For each loop"),
    ("FOR_INDEX", "For Index", "For index loop"),
    ("TIME_CYCLE", "Time Cycle", "Time cycle loop"),
]

QUESTION_LOOP_FOR_EACH_ITEMS = [
    ("PARTICLE", "Particle", "For each particle"),
    ("NEIGHBOUR", "Neighbour", "For each neighbour"),
]

QUESTION_LOOP_TIME_FROM_ITEMS = [
    ("DOCUMENT", "Document", "Time from document"),
    ("PARTICLE", "Particle", "Time from particle"),
]

QUESTION_VAR_TYPE_ITEMS = [
    ("FLOAT", "Float", "Floating point variable"),
    ("INT", "Integer", "Integer variable"),
    ("VEC", "Vector", "Vector variable"),
    ("USERDATA", "User Data", "User data variable"),
]

_QUESTION_NODE_TYPE_ITEMS = []


def _on_question_item_add(context, obj, item):
    from ..ui.nodetree import hierarchy_get_descendants, hierarchy_recalculate_indent_levels

    props = obj.nexus_modifier
    items = props.question_items

    auto_rename.initialize_added(item, items, _question_item_base_name(item))

    pre_add_index = getattr(context.window_manager, "nexus_nodetree_pre_add_index", -1)
    new_item_idx = len(items) - 1

    if pre_add_index < 0 or pre_add_index >= new_item_idx:
        hierarchy_recalculate_indent_levels(items)
        return new_item_idx

    selected = items[pre_add_index]
    insert_after = pre_add_index

    if selected.item_type in _CONTAINER_TYPES and selected.expanded:
        item.parent_index = pre_add_index
        descendants = [
            d for d in hierarchy_get_descendants(items, pre_add_index) if d != new_item_idx
        ]
        if descendants:
            insert_after = max(descendants)
    else:
        item.parent_index = selected.parent_index
        descendants = [
            d for d in hierarchy_get_descendants(items, pre_add_index) if d != new_item_idx
        ]
        if descendants:
            insert_after = max(descendants)

    target_pos = insert_after + 1

    if target_pos < new_item_idx:
        items.move(new_item_idx, target_pos)

        for it in items:
            pi = it.parent_index
            if pi == new_item_idx:
                it.parent_index = target_pos
            elif target_pos <= pi < new_item_idx:
                it.parent_index = pi + 1

        hierarchy_recalculate_indent_levels(items)
        return target_pos

    hierarchy_recalculate_indent_levels(items)
    return new_item_idx


def build_question_enum_items():
    global _QUESTION_NODE_TYPE_ITEMS
    from ..icons import get_icon
    from ..ui import register_nodetree

    _QUESTION_NODE_TYPE_ITEMS = []

    for idx, (type_id, type_def) in enumerate(QUESTION_NODE_TYPE_DEFS.items()):
        icon_name = type_def.get("icon_name")
        icon_id = 0
        if icon_name:
            icon_id = get_icon(icon_name)

        if icon_id and icon_id > 0:
            _QUESTION_NODE_TYPE_ITEMS.append(
                (
                    type_id,
                    type_def["name"],
                    type_def["description"],
                    icon_id,
                    idx,
                )
            )
        else:
            blender_icon = type_def.get("blender_icon", "NONE")
            _QUESTION_NODE_TYPE_ITEMS.append(
                (
                    type_id,
                    type_def["name"],
                    type_def["description"],
                    blender_icon,
                    idx,
                )
            )

    register_nodetree(
        "question_items",
        _QUESTION_NODE_TYPE_ITEMS,
        "question_items",
        "question_items_index",
        on_add=_on_question_item_add,
        separator_after={"ACTION", "FOLDER"},
        hierarchy=True,
        container_types=_CONTAINER_TYPES,
        on_hierarchy_remove=_on_question_hierarchy_remove,
        on_hierarchy_move=_on_question_hierarchy_move,
        folder_type="FOLDER",
        folder_color_prop="folder_color",
        folder_icon_cache=question_folder_icons,
    )


def _get_question_node_type_items(self, context):
    return _QUESTION_NODE_TYPE_ITEMS


_CONTAINER_TYPES = {"QUESTION", "LOOP", "FOLDER"}


def _poll_camera(self, obj):
    return obj.type == "CAMERA"


_LOGIC_OP_MAP = {
    "NONE": "",
    "AND": "AND ",
    "OR": "OR ",
    "AND_NOT": "AND NOT ",
    "OR_NOT": "OR NOT ",
}

_PARTICLE_DISPLAY_NAMES = {item[0]: item[1] for item in QUESTION_IF_PARTICLE_ITEMS}

_VECTOR_SUFFIX_MAP = {
    "X": ".X",
    "Y": ".Y",
    "Z": ".Z",
}

_ROTATION_SUFFIX_MAP = {
    "RH": ".H",
    "RP": ".P",
    "RB": ".B",
}

_COLOR_SUFFIX_MAP = {
    "R": ".R",
    "G": ".G",
    "B": ".B",
    "BRIGHTNESS": " Brightness",
}

_COMPARISON_TEMPLATES = {
    "LESS": "{attrib} < {val}",
    "LESSEQUAL": "{attrib} <= {val}",
    "EQUAL": "{attrib} == {val}",
    "NOTEQUAL": "{attrib} != {val}",
    "GREATEREQUAL": "{attrib} >= {val}",
    "GREATER": "{attrib} > {val}",
    "WITHIN": "{val} <= {attrib} <= {top_val}",
    "NOTWITHIN": "Not ({val} <= {attrib} <= {top_val})",
}

_SET_DISPLAY_NAMES = {item[0]: item[1] for item in QUESTION_SET_ITEMS}

_INT_PARTICLE_TYPES = {"GROUP", "FLAGS", "ID", "COUNT", "NEIGHBORS"}
_TIME_PARTICLE_TYPES = {"AGE", "LIFE"}


def _format_float(value):
    s = f"{value:.4f}"
    s = s.rstrip("0").rstrip(".")
    return s


def _build_question_name(item, items):
    if item.condition == "ELSE":
        return "Else"

    if item.condition == "IF":
        logic_op = _LOGIC_OP_MAP.get(item.operator, "")
        parent_idx = item.parent_index
        if parent_idx >= 0 and parent_idx < len(items):
            if items[parent_idx].item_type != "QUESTION":
                logic_op = ""
        else:
            logic_op = ""
        op_str = f"{logic_op}If "
    else:
        op_str = "Else If "

    if item.if_param == "PARTICLE" and item.if_particle == "EMITTER":
        if item.if_include == "WITHIN":
            return f"{op_str}Emitter Within"
        if item.if_include == "NOTWITHIN":
            return f"{op_str}Emitter Not Within"

    is_bool_type = False
    attrib = ""

    if item.if_param == "MATH":
        if item.if_math == "RANDOM":
            rmin = _format_float(item.if_math_random_min)
            rmax = _format_float(item.if_math_random_max)
            attrib = f"Random({rmin} to {rmax})"
        elif item.if_math == "SPLINE":
            attrib = "Spline"
        elif item.if_math == "WAVE":
            attrib = "Wave"
        elif item.if_math == "CONST":
            attrib = _format_float(item.if_math_const_value)
        elif item.if_math == "VAR":
            attrib = item.if_math_var_name if item.if_math_var_name else "<undefined>"

    elif item.if_param == "DOCUMENT":
        if item.if_document == "FRAME":
            attrib = "Document Frame"
        elif item.if_document == "TIME":
            attrib = "Document Time"
        elif item.if_document == "OBJECT_DISTANCE":
            attrib = "Object Distance"
        elif item.if_document == "CAMERA_DISTANCE":
            attrib = "Camera Distance"
        elif item.if_document == "CAMERA_FOV":
            attrib = "Camera FOV"
            is_bool_type = True

    elif item.if_param == "PARTICLE":
        if item.if_particle == "FLAGS":
            flags = []
            if item.if_flag_collide_object:
                flags.append("Hit Object")
            if item.if_flag_collide_particle:
                flags.append("Hit Particle")
            if item.if_flag_group_changed:
                flags.append("Changed Group")
            if item.if_flag_stuck:
                flags.append("Stuck")
            if item.if_flag_frozen:
                flags.append("Frozen")
            if item.if_flag_born:
                flags.append("Born")
            flag_str = ", ".join(flags) if flags else "None"
            attrib = f"Flags [{flag_str}]"
            is_bool_type = True
        else:
            attrib = _PARTICLE_DISPLAY_NAMES.get(item.if_particle, item.if_particle)

    if item.if_param == "PARTICLE" and item.if_particle in {"POSITION", "VELOCITY", "UVW"}:
        attrib += _VECTOR_SUFFIX_MAP.get(item.if_vector, "")
    elif item.if_param == "PARTICLE" and item.if_particle == "ROTATION":
        attrib += _ROTATION_SUFFIX_MAP.get(item.if_vector, "")
    elif item.if_param == "PARTICLE" and item.if_particle == "COLOR":
        attrib += _COLOR_SUFFIX_MAP.get(item.if_vector, "")

    if is_bool_type:
        return f"{op_str}{attrib}"

    is_int = (item.if_param == "PARTICLE" and item.if_particle in _INT_PARTICLE_TYPES) or (
        item.if_param == "DOCUMENT" and item.if_document == "FRAME"
    )
    is_time = (item.if_param == "PARTICLE" and item.if_particle in _TIME_PARTICLE_TYPES) or (
        item.if_param == "DOCUMENT" and item.if_document == "TIME"
    )

    if is_int:
        val = str(item.if_than_int)
        top_val = str(item.if_than_int_top)
    elif is_time:
        time_suffix = "s" if get_prop_time_mode(item, "if_than_time") == "SECONDS" else "f"
        val = f"{_format_float(item.if_than_time)}{time_suffix}"
        top_suffix = "s" if get_prop_time_mode(item, "if_than_time_top") == "SECONDS" else "f"
        top_val = f"{_format_float(item.if_than_time_top)}{top_suffix}"
    else:
        val = _format_float(item.if_than)
        top_val = _format_float(item.if_than_top)

    template = _COMPARISON_TEMPLATES.get(item.if_op)
    if template:
        cond_str = template.format(attrib=attrib, val=val, top_val=top_val)
    else:
        cond_str = attrib

    return f"{op_str}{cond_str}"


def _build_action_name(item):
    if item.then == "SPAWN":
        return "Spawn Particles"
    if item.then == "KILL":
        return "Kill Particle"
    if item.then == "BREAK":
        return "Break"

    prop_name = _SET_DISPLAY_NAMES.get(item.set, item.set)

    if item.set in ("VAR", "USERDATA"):
        prop_name = item.set_prop_var_name if item.set_prop_var_name else "<undefined>"
        suffix = ""
        if item.set_var_to == "CONST":
            suffix = f" to {_format_float(item.set_prop_var_flt)}"
        if item.then == "SET":
            return f"Set {prop_name}{suffix}"
        return f"Add to {prop_name}{suffix}"

    if item.set == "GROUP":
        group_num = (
            item.set_prop_group.nexus_modifier.ID_NX_GROUP_ID if item.set_prop_group else "?"
        )
        if item.then == "SET":
            return f"Set Group to {group_num}"
        return f"Add to Group {group_num}"

    if item.then == "SET":
        return f"Set {prop_name}"
    if item.then == "ADD":
        return f"Add to {prop_name}"

    return prop_name


def _build_loop_name(item):
    prefix = f"Loop {item.loop_name} " if item.loop_name else "Loop "
    if item.loop_type == "FOR_EACH":
        if item.loop_for_each == "NEIGHBOUR":
            dist = _format_float(item.loop_for_each_neighbor_distance)
            return f"{prefix}for each neighbor within {dist}"
        if item.loop_for_each == "PARTICLE":
            return f"{prefix}for each particle"
        return f"{prefix}for each"
    if item.loop_type == "FOR_INDEX":
        return f"Loop from {item.loop_start} to {item.loop_end} step {item.loop_step}"
    if item.loop_type == "TIME_CYCLE":
        start_suffix = "s" if get_prop_time_mode(item, "loop_time_start") == "SECONDS" else "f"
        length_suffix = "s" if get_prop_time_mode(item, "loop_time_length") == "SECONDS" else "f"
        return (
            f"Loop from {_format_float(item.loop_time_start)}{start_suffix} "
            f"for {_format_float(item.loop_time_length)}{length_suffix} "
            f"repeat {item.loop_time_count}"
        )
    return "Loop"


def _build_var_name(item):
    var_name = item.var_name if item.var_name else "<undefined>"
    rw_suffix = " [Read/Write]" if item.var_type_write else "[Read Only]"
    particle_suffix = "[Particle]" if item.var_type_particle else ""
    ud_suffix = "[User Data]" if item.var_type == "USERDATA" else ""
    return f"{var_name}{rw_suffix}{particle_suffix}{ud_suffix}"


def _question_item_base_name(item) -> str:
    obj = item.id_data
    items = obj.nexus_modifier.question_items if obj is not None else ()

    item_type = item.item_type
    if item_type == "QUESTION":
        return _build_question_name(item, items)
    if item_type == "ACTION":
        return _build_action_name(item)
    if item_type == "LOOP":
        return _build_loop_name(item)
    if item_type == "VAR":
        return _build_var_name(item)
    if item_type == "SCRIPT":
        return "Script"
    if item_type == "FOLDER":
        return "Folder"
    return QUESTION_NODE_TYPE_DEFS.get(item_type, {}).get("name", "Item")


_trigger_auto_rename = auto_rename.on_trigger(
    base_name_fn=_question_item_base_name,
    collection_attr="question_items",
)


def _on_question_hierarchy_remove(context, obj):
    try:
        from ..editors.glsl_editor import close_all_editors_for_object

        close_all_editors_for_object(obj.name)
    except ImportError:
        pass


def _on_question_hierarchy_move(context, obj):
    try:
        from ..editors.glsl_editor import close_all_editors_for_object

        close_all_editors_for_object(obj.name)
    except ImportError:
        pass


class NexusQuestionItem(bpy.types.PropertyGroup):
    preset_uid: StringProperty(name="", default="", options={"HIDDEN"})

    name: StringProperty(
        name="Name",
        description="Item name",
        default="",
        update=auto_rename.on_name_update(),
    )

    is_renamed: BoolProperty(
        name="",
        default=False,
        options={"HIDDEN"},
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Enable this item",
        default=True,
    )

    item_type: EnumProperty(
        name="Item Type",
        description="Type of question item",
        items=_get_question_node_type_items,
        default=0,
        update=_trigger_auto_rename,
    )

    parent_index: IntProperty(
        name="Parent Index",
        description="Index of parent item (-1 for root)",
        default=-1,
    )

    indent_level: IntProperty(
        name="Indent Level",
        description="Visual indentation level",
        default=0,
        min=0,
    )

    expanded: BoolProperty(
        name="Expanded",
        description="Expand to show children",
        default=True,
    )

    # --- QUESTION properties ---

    condition: EnumProperty(
        name="Question",
        description="Condition type",
        items=QUESTION_CONDITION_ITEMS,
        default="IF",
        update=_trigger_auto_rename,
    )

    operator: EnumProperty(
        name="Operator",
        description="Logical operator",
        items=QUESTION_OPERATOR_ITEMS,
        default="NONE",
        update=_trigger_auto_rename,
    )

    if_param: EnumProperty(
        name="Category",
        description="Condition parameter source",
        items=QUESTION_IF_PARAM_ITEMS,
        default="PARTICLE",
        update=_trigger_auto_rename,
    )

    if_particle: EnumProperty(
        name="Data",
        description="Particle property to test",
        items=QUESTION_IF_PARTICLE_ITEMS,
        default="AGE",
        update=_trigger_auto_rename,
    )

    if_vector: EnumProperty(
        name="Vector Component",
        description="Vector component to test",
        items=QUESTION_IF_VECTOR_ITEMS,
        default="X",
        update=_trigger_auto_rename,
    )

    if_document: EnumProperty(
        name="Data",
        description="Document property to test",
        items=QUESTION_IF_DOCUMENT_ITEMS,
        default="TIME",
        update=_trigger_auto_rename,
    )

    if_math: EnumProperty(
        name="Data",
        description="Math source for condition",
        items=QUESTION_IF_MATH_ITEMS,
        default="RANDOM",
        update=_trigger_auto_rename,
    )

    if_op: EnumProperty(
        name="Condition",
        description="Comparison operator",
        items=QUESTION_IF_OP_ITEMS,
        default="GREATER",
        update=_trigger_auto_rename,
    )

    if_include: EnumProperty(
        name="Condition",
        description="Inclusion test",
        items=QUESTION_IF_INCLUDE_ITEMS,
        default="WITHIN",
        update=_trigger_auto_rename,
    )

    if_than: FloatProperty(
        name="Value",
        description="Comparison value",
        default=0.0,
        update=_trigger_auto_rename,
    )

    if_than_var: FloatProperty(
        name="Variation",
        description="Comparison value variation",
        default=0.0,
        min=0.0,
    )

    if_than_top: FloatProperty(
        name="To",
        description="Upper range value (for Within/Not Within)",
        default=1.0,
        update=_trigger_auto_rename,
    )

    if_than_int: IntProperty(
        name="Value",
        description="Integer comparison value",
        default=0,
        update=_trigger_auto_rename,
    )

    if_than_int_var: IntProperty(
        name="Variation",
        description="Integer comparison value variation",
        default=0,
        min=0,
    )

    if_than_int_top: IntProperty(
        name="To",
        description="Upper integer range value",
        default=1,
        update=_trigger_auto_rename,
    )

    if_than_time: nexus_time_property(
        "if_than_time",
        name="Time",
        description="Time comparison value",
        default=0.0,
        min=0.0,
        collection_path="question_items",
        update=_trigger_auto_rename,
    )

    if_than_time_var: nexus_time_property(
        "if_than_time_var",
        name="Variation",
        description="Time comparison value variation",
        default=0.0,
        min=0.0,
        collection_path="question_items",
    )

    if_than_time_top: nexus_time_property(
        "if_than_time_top",
        name="To",
        description="Upper time range value",
        default=24.0,
        min=0.0,
        collection_path="question_items",
        update=_trigger_auto_rename,
    )

    if_math_const_value: FloatProperty(
        name="Value",
        description="Constant math value",
        default=0.0,
        update=_trigger_auto_rename,
    )

    if_math_frequency: FloatProperty(
        name="Frequency",
        description="Wave frequency",
        default=1.0,
        min=0.0,
    )

    if_math_dependtime: EnumProperty(
        name="Time Variation",
        description="Time dependency for math",
        items=QUESTION_IF_MATH_DEPENDTIME_ITEMS,
        default="DOCUMENT",
    )

    if_math_dependindex: BoolProperty(
        name="Particle ID",
        description="Use particle index as input",
        default=True,
    )

    if_math_var_name: StringProperty(
        name="Variable Name",
        description="Name of variable to read",
        default="",
        update=_trigger_auto_rename,
    )

    if_math_random_min: FloatProperty(
        name="Min",
        description="Random minimum value",
        default=-1.0,
        update=_trigger_auto_rename,
    )

    if_math_random_max: FloatProperty(
        name="Max",
        description="Random maximum value",
        default=1.0,
        update=_trigger_auto_rename,
    )

    if_math_random_seed: IntProperty(
        name="Seed",
        description="Random seed",
        default=12345,
        min=0,
    )

    if_particle_neighbors_distance: FloatProperty(
        name="Distance",
        description="Neighbor search distance",
        default=0.1,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
    )

    if_once: BoolProperty(
        name="Check Once",
        description="Evaluate condition only once per particle",
        default=False,
    )

    if_document_object_mode: EnumProperty(
        name="Mode",
        description="Object distance measurement mode",
        items=QUESTION_IF_DOCUMENT_OBJECT_MODE_ITEMS,
        default="POSITION",
    )

    if_document_camera: PointerProperty(
        name="Camera",
        description="Camera to measure distance or FOV from",
        type=bpy.types.Object,
        poll=_poll_camera,
    )

    if_document_camera_fov_widen: FloatProperty(
        name="Widen FOV",
        description="Angle to widen the camera FOV by",
        default=0.0,
        subtype="ANGLE",
    )

    if_document_objects: CollectionProperty(
        name="Objects",
        type=NexusNodeTreeItem,
    )

    if_document_objects_index: IntProperty(
        name="Active Index",
        default=0,
        min=0,
    )

    if_document_objects_drop_target: PointerProperty(
        name="Add Object",
        description="Pick or drop an object to add it to the list",
        type=bpy.types.Object,
        update=make_drop_target_update(
            "if_document_objects",
            "if_document_objects_index",
            "if_document_objects_drop_target",
        ),
    )

    if_particle_emitters: CollectionProperty(
        name="Emitters",
        type=NexusNodeTreeItem,
    )

    if_particle_emitters_index: IntProperty(
        name="Active Index",
        default=0,
        min=0,
    )

    if_particle_emitters_drop_target: PointerProperty(
        name="Add Emitter",
        description="Pick or drop an emitter to add it to the list",
        type=bpy.types.Object,
        poll=make_allowed_types_poll(["NX_EMITTER"]),
        update=make_drop_target_update(
            "if_particle_emitters",
            "if_particle_emitters_index",
            "if_particle_emitters_drop_target",
        ),
    )

    if_flag_collide_object: BoolProperty(
        name="Hit Object",
        description="Collided with object",
        default=False,
        update=_trigger_auto_rename,
    )

    if_flag_collide_particle: BoolProperty(
        name="Hit Particle",
        description="Collided with particle",
        default=False,
        update=_trigger_auto_rename,
    )

    if_flag_group_changed: BoolProperty(
        name="Changed Group",
        description="Group was changed",
        default=False,
        update=_trigger_auto_rename,
    )

    if_flag_stuck: BoolProperty(
        name="Stuck",
        description="Particle is stuck",
        default=False,
        update=_trigger_auto_rename,
    )

    if_flag_frozen: BoolProperty(
        name="Frozen",
        description="Particle is frozen",
        default=False,
        update=_trigger_auto_rename,
    )

    if_flag_born: BoolProperty(
        name="Born",
        description="Particle was just born",
        default=False,
        update=_trigger_auto_rename,
    )

    weight: FloatProperty(
        name="Weight",
        description="Condition weight",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    # --- ACTION properties ---

    then: EnumProperty(
        name="Action",
        description="Action to perform",
        items=QUESTION_THEN_ITEMS,
        default="SET",
        update=_trigger_auto_rename,
    )

    set: EnumProperty(
        name="Set",
        description="Particle property to set",
        items=QUESTION_SET_ITEMS,
        default="COLOR",
        update=_trigger_auto_rename,
    )

    set_prop_color: FloatVectorProperty(
        name="Color",
        description="Color value to set",
        default=(0.9, 0.7, 0.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        size=3,
    )

    set_prop_color_var: FloatVectorProperty(
        name="Variation",
        description="Color variation",
        default=(0.0, 0.0, 0.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        size=3,
    )

    set_prop_float: FloatProperty(
        name="Value",
        description="Float value to set",
        default=5.0,
    )

    set_prop_float_var: FloatProperty(
        name="Variation",
        description="Float value variation",
        default=0.0,
        min=0.0,
    )

    set_prop_life: nexus_time_property(
        "set_prop_life",
        name="Life",
        description="Lifetime value",
        default=24.0,
        min=0.0,
        collection_path="question_items",
    )

    set_prop_life_var: nexus_time_property(
        "set_prop_life_var",
        name="Variation",
        description="Lifetime variation",
        default=0.0,
        min=0.0,
        collection_path="question_items",
    )

    set_prop_age: nexus_time_property(
        "set_prop_age",
        name="Age",
        description="Age value",
        default=24.0,
        min=0.0,
        collection_path="question_items",
    )

    set_prop_age_var: nexus_time_property(
        "set_prop_age_var",
        name="Variation",
        description="Age variation",
        default=0.0,
        min=0.0,
        collection_path="question_items",
    )

    set_prop_scale: FloatVectorProperty(
        name="Scale",
        description="Scale value",
        default=(1.0, 1.0, 1.0),
        subtype="XYZ",
        size=3,
    )

    set_prop_scale_var: FloatVectorProperty(
        name="Variation",
        description="Scale variation",
        default=(0.0, 0.0, 0.0),
        subtype="XYZ",
        min=0.0,
        size=3,
    )

    set_prop_rot: FloatVectorProperty(
        name="Rotation",
        description="Rotation value",
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
        size=3,
    )

    set_prop_rot_var: FloatVectorProperty(
        name="Variation",
        description="Rotation variation",
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
        min=0.0,
        size=3,
    )

    set_prop_vel: FloatVectorProperty(
        name="Velocity",
        description="Velocity value",
        default=(0.0, 0.0, 0.0),
        subtype="VELOCITY",
        size=3,
    )

    set_prop_vel_var: FloatVectorProperty(
        name="Variation",
        description="Velocity variation",
        default=(0.0, 0.0, 0.0),
        subtype="VELOCITY",
        min=0.0,
        size=3,
    )

    set_prop_group: PointerProperty(
        name="Group",
        description="Group to set",
        type=bpy.types.Object,
        poll=make_allowed_types_poll(["NX_GROUP"]),
        update=_trigger_auto_rename,
    )

    set_prop_var_name: StringProperty(
        name="Variable",
        description="Variable name to set",
        default="",
        update=_trigger_auto_rename,
    )

    set_prop_var_flt: FloatProperty(
        name="Value",
        description="Variable float value",
        default=0.0,
        update=_trigger_auto_rename,
    )

    set_var_to: EnumProperty(
        name="Set to",
        description="Variable assignment source",
        items=QUESTION_SET_VAR_TO_ITEMS,
        default="CONST",
        update=_trigger_auto_rename,
    )

    set_prop_freeze: BoolProperty(
        name="Freeze",
        description="Freeze particle",
        default=True,
    )

    set_prop_sticky: BoolProperty(
        name="Sticky",
        description="Make particle sticky",
        default=True,
    )

    set_delay: FloatProperty(
        name="Delay",
        description="Action delay percentage",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    set_delay_damping: FloatProperty(
        name="Damping",
        description="Delay damping percentage",
        default=20.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    set_once: BoolProperty(
        name="Set Once",
        description="Apply action only once per particle",
        default=False,
    )

    set_particle_display: EnumProperty(
        name="Display",
        description="Particle display mode",
        items=QUESTION_SET_PARTICLE_DISPLAY_ITEMS,
        default="POINTS",
    )

    # --- SPAWN properties ---

    spawn_count: IntProperty(
        name="Count",
        description="Number of particles to spawn",
        default=1,
        min=0,
    )

    spawn_dist: FloatProperty(
        name="Distance",
        description="Spawn distance from source",
        default=0.02,
        min=0.0,
        unit="LENGTH",
    )

    spawn_color: FloatVectorProperty(
        name="Color",
        description="Spawn particle color",
        default=(1.0, 0.749, 0.251),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        size=3,
    )

    spawn_fulllife: BoolProperty(
        name="Full Life",
        description="Use full lifetime for spawned particles",
        default=True,
    )

    spawn_life: nexus_time_property(
        "spawn_life",
        name="Life",
        description="Spawned particle lifetime",
        default=120.0,
        min=0.0,
        collection_path="question_items",
    )

    spawn_velocity_dir: EnumProperty(
        name="Velocity Direction",
        description="Direction of spawned particle velocity",
        items=QUESTION_SPAWN_VELOCITY_DIR_ITEMS,
        default="RANDOM",
    )

    spawn_speed: FloatProperty(
        name="Speed",
        description="Spawned particle speed",
        default=1.0,
        min=0.0,
        unit="LENGTH",
    )

    spawn_radius: FloatProperty(
        name="Radius",
        description="Spawned particle radius",
        default=0.05,
        min=0.0,
        unit="LENGTH",
    )

    spawn_parent_inherit: BoolProperty(
        name="Inherit Parent",
        description="Inherit properties from parent particle",
        default=True,
    )

    spawn_emitter: PointerProperty(
        name="Emitter",
        description="Emitter to spawn particles from",
        type=bpy.types.Object,
        poll=make_allowed_types_poll(["NX_EMITTER"]),
    )

    # --- LOOP properties ---

    loop_type: EnumProperty(
        name="Loop Type",
        description="Type of loop",
        items=QUESTION_LOOP_TYPE_ITEMS,
        default="TIME_CYCLE",
        update=_trigger_auto_rename,
    )

    loop_name: StringProperty(
        name="Loop Name",
        description="Name for the loop variable",
        default="",
        update=_trigger_auto_rename,
    )

    loop_for_each: EnumProperty(
        name="For Each",
        description="For each iteration target",
        items=QUESTION_LOOP_FOR_EACH_ITEMS,
        default="PARTICLE",
        update=_trigger_auto_rename,
    )

    loop_for_each_neighbor_distance: FloatProperty(
        name="Within Distance",
        description="Neighbor search distance",
        default=0.2,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
        update=_trigger_auto_rename,
    )

    loop_start: IntProperty(
        name="Start",
        description="Loop start index",
        default=0,
        update=_trigger_auto_rename,
    )

    loop_end: IntProperty(
        name="End",
        description="Loop end index",
        default=10,
        update=_trigger_auto_rename,
    )

    loop_step: IntProperty(
        name="Step",
        description="Loop step size",
        default=1,
        min=1,
        update=_trigger_auto_rename,
    )

    loop_time_start: nexus_time_property(
        "loop_time_start",
        name="Start Time",
        description="Time cycle start",
        default=0.0,
        min=0.0,
        collection_path="question_items",
        update=_trigger_auto_rename,
    )

    loop_time_length: nexus_time_property(
        "loop_time_length",
        name="Duration",
        description="Time cycle length",
        default=24.0,
        min=0.0,
        collection_path="question_items",
        update=_trigger_auto_rename,
    )

    loop_time_count: IntProperty(
        name="Count",
        description="Time cycle count",
        default=10,
        min=1,
        update=_trigger_auto_rename,
    )

    loop_time_from: EnumProperty(
        name="Time From",
        description="Time source",
        items=QUESTION_LOOP_TIME_FROM_ITEMS,
        default="PARTICLE",
    )

    loop_time_position: BoolProperty(
        name="Position",
        description="Interpolate position over time",
        default=True,
    )

    loop_time_velocity: BoolProperty(
        name="Velocity",
        description="Interpolate velocity over time",
        default=False,
    )

    loop_time_radius: BoolProperty(
        name="Radius",
        description="Interpolate radius over time",
        default=True,
    )

    loop_time_color: BoolProperty(
        name="Color",
        description="Interpolate color over time",
        default=True,
    )

    loop_time_mass: BoolProperty(
        name="Mass",
        description="Interpolate mass over time",
        default=False,
    )

    loop_time_rotation: BoolProperty(
        name="Rotation",
        description="Interpolate rotation over time",
        default=False,
    )

    # --- VAR properties ---

    var_name: StringProperty(
        name="Variable Name",
        description="Variable name",
        default="",
        update=_trigger_auto_rename,
    )

    var_type: EnumProperty(
        name="Type",
        description="Variable type",
        items=QUESTION_VAR_TYPE_ITEMS,
        default="FLOAT",
        update=_trigger_auto_rename,
    )

    var_type_write: BoolProperty(
        name="Writeable",
        description="Allow writing to this variable",
        default=False,
        update=_trigger_auto_rename,
    )

    var_type_particle: BoolProperty(
        name="Particle",
        description="Variable is per-particle",
        default=False,
        update=_trigger_auto_rename,
    )

    var_type_int_val: IntProperty(
        name="Value",
        description="Initial integer value",
        default=0,
    )

    var_type_flt_val: FloatProperty(
        name="Value",
        description="Initial float value",
        default=0.0,
    )

    var_type_vec_val: FloatVectorProperty(
        name="Value",
        description="Initial vector value",
        default=(0.0, 0.0, 0.0),
        subtype="XYZ",
        size=3,
    )

    # --- SCRIPT properties ---

    script_source: StringProperty(
        name="Script",
        description="GLSL source code for this script node",
        default="",
    )

    # --- FOLDER properties ---

    folder_color: FloatVectorProperty(
        name="Folder Color",
        description="Folder display color",
        default=(0.5, 0.5, 0.5),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        size=3,
    )


_VECTOR_PARTICLE_TYPES = {"COLOR", "POSITION", "VELOCITY", "ROTATION", "UVW"}
_FLAG_PARTICLE_TYPE = "FLAGS"
_INCLUDE_PARTICLE_TYPES = {"GROUP", "EMITTER", "COUNT", "ID"}


def _draw_question_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "condition")

    if item.condition != "ELSE":
        col.prop(item, "operator")
        col.prop(item, "if_param")

        if item.if_param == "PARTICLE":
            col.prop(item, "if_particle")

            if item.if_particle in _VECTOR_PARTICLE_TYPES:
                col.prop(item, "if_vector")

            if item.if_particle == _FLAG_PARTICLE_TYPE:
                col.prop(item, "if_flag_collide_object")
                col.prop(item, "if_flag_collide_particle")
                col.prop(item, "if_flag_group_changed")
                col.prop(item, "if_flag_stuck")
                col.prop(item, "if_flag_frozen")
                col.prop(item, "if_flag_born")

            if item.if_particle == "NEIGHBORS":
                col.prop(item, "if_particle_neighbors_distance")

        elif item.if_param == "DOCUMENT":
            col.prop(item, "if_document")

            if item.if_document == "OBJECT_DISTANCE":
                col.prop(item, "if_document_object_mode")

                draw_nodetree(
                    col,
                    item,
                    "if_document_objects",
                    "if_document_objects_index",
                    label="Objects",
                    data_path=item.path_from_id(),
                )
            elif item.if_document in ("CAMERA_DISTANCE", "CAMERA_FOV"):
                col.prop(item, "if_document_camera")

        elif item.if_param == "MATH":
            col.prop(item, "if_math")

            if item.if_math == "CONST":
                col.prop(item, "if_math_const_value")
            elif item.if_math == "RANDOM":
                col.prop(item, "if_math_random_min")
                col.prop(item, "if_math_random_max")
                col.prop(item, "if_math_random_seed")
            elif item.if_math == "VAR":
                col.prop(item, "if_math_var_name")
            elif item.if_math == "WAVE":
                col.prop(item, "if_math_frequency")
                col.prop(item, "if_math_dependtime")
                col.prop(item, "if_math_dependindex")
            elif item.if_math == "SPLINE":
                col.label(text="Spline (not yet configurable)")

        if item.if_param == "PARTICLE":
            if item.if_particle in _INCLUDE_PARTICLE_TYPES:
                col.prop(item, "if_include")
            elif item.if_particle != _FLAG_PARTICLE_TYPE:
                col.prop(item, "if_op")

            if item.if_particle != _FLAG_PARTICLE_TYPE:
                if item.if_particle in _INT_PARTICLE_TYPES:
                    col.prop(item, "if_than_int")
                    col.prop(item, "if_than_int_var")
                    if item.if_op in ("WITHIN", "NOTWITHIN"):
                        col.prop(item, "if_than_int_top")
                elif item.if_particle in _TIME_PARTICLE_TYPES:
                    draw_time_prop(col, item, "if_than_time")
                    draw_time_prop(col, item, "if_than_time_var")
                    if item.if_op in ("WITHIN", "NOTWITHIN"):
                        draw_time_prop(col, item, "if_than_time_top")
                elif item.if_particle == "EMITTER":
                    draw_nodetree(
                        col,
                        item,
                        "if_particle_emitters",
                        "if_particle_emitters_index",
                        label="Emitters",
                        data_path=item.path_from_id(),
                        allowed_types=["NX_EMITTER"],
                    )
                else:
                    col.prop(item, "if_than")
                    col.prop(item, "if_than_var")
                    if item.if_op in ("WITHIN", "NOTWITHIN"):
                        col.prop(item, "if_than_top")

        elif item.if_param == "DOCUMENT":
            if item.if_document != "CAMERA_FOV":
                col.prop(item, "if_op")
            if item.if_document == "FRAME":
                col.prop(item, "if_than_int")
                col.prop(item, "if_than_int_var")
                if item.if_op in ("WITHIN", "NOTWITHIN"):
                    col.prop(item, "if_than_int_top")
            elif item.if_document == "TIME":
                draw_time_prop(col, item, "if_than_time")
                draw_time_prop(col, item, "if_than_time_var")
                if item.if_op in ("WITHIN", "NOTWITHIN"):
                    draw_time_prop(col, item, "if_than_time_top")
            elif item.if_document == "CAMERA_FOV":
                col.prop(item, "if_document_camera_fov_widen")
            elif item.if_document in ("CAMERA_DISTANCE", "OBJECT_DISTANCE"):
                col.prop(item, "if_than")
                col.prop(item, "if_than_var")
                if item.if_op in ("WITHIN", "NOTWITHIN"):
                    col.prop(item, "if_than_top")

        elif item.if_param == "MATH":
            col.prop(item, "if_op")
            col.prop(item, "if_than")
            col.prop(item, "if_than_var")
            if item.if_op in ("WITHIN", "NOTWITHIN"):
                col.prop(item, "if_than_top")

    col.prop(item, "weight")
    col.prop(item, "if_once")


def _draw_action_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "then")

    col.prop(item, "weight")

    if item.then in ("SET", "ADD"):
        col.prop(item, "set")

        if item.set == "COLOR":
            col.prop(item, "set_prop_color")
            col.prop(item, "set_prop_color_var")
        elif item.set == "SPEED":
            col.prop(item, "set_prop_float", text="Speed")
            col.prop(item, "set_prop_float_var", text="Speed Variation")
        elif item.set == "MASS":
            col.prop(item, "set_prop_float", text="Mass")
            col.prop(item, "set_prop_float_var", text="Mass Variation")
        elif item.set == "RADIUS":
            col.prop(item, "set_prop_float", text="Radius")
            col.prop(item, "set_prop_float_var", text="Radius Variation")
        elif item.set == "VELOCITY":
            col.prop(item, "set_prop_vel")
            col.prop(item, "set_prop_vel_var")
        elif item.set == "ROTATION":
            col.prop(item, "set_prop_rot")
            col.prop(item, "set_prop_rot_var")
        elif item.set == "SCALE":
            col.prop(item, "set_prop_scale")
            col.prop(item, "set_prop_scale_var")
        elif item.set == "LIFE":
            draw_time_prop(col, item, "set_prop_life")
            draw_time_prop(col, item, "set_prop_life_var")
        elif item.set == "AGE":
            draw_time_prop(col, item, "set_prop_age")
            draw_time_prop(col, item, "set_prop_age_var")
        elif item.set == "GROUP":
            col.prop(item, "set_prop_group")
        elif item.set == "VAR":
            col.prop(item, "set_prop_var_name")
            col.prop(item, "set_var_to")
            col.prop(item, "set_prop_var_flt")
        elif item.set == "FREEZE":
            col.prop(item, "set_prop_freeze")
        elif item.set == "STICKY":
            col.prop(item, "set_prop_sticky")
        elif item.set == "DISPLAY":
            col.prop(item, "set_particle_display")
        elif item.set == "USERDATA":
            col.label(text="User Data")

        col.separator()
        col.prop(item, "set_delay")
        col.prop(item, "set_delay_damping")
        col.prop(item, "set_once")

    elif item.then == "SPAWN":
        col.prop(item, "set_once")
        col.prop(item, "spawn_count")
        col.prop(item, "spawn_dist")

        col.separator(type="LINE")
        col.prop(item, "spawn_emitter")
        col.separator(type="LINE")

        col.prop(item, "spawn_parent_inherit")

        sub = col.column()
        sub.enabled = not item.spawn_parent_inherit
        sub.prop(item, "spawn_fulllife")

        sub = col.column()
        sub.enabled = not item.spawn_parent_inherit and not item.spawn_fulllife
        draw_time_prop(sub, item, "spawn_life")

        col.prop(item, "spawn_velocity_dir")
        col.prop(item, "spawn_speed")

        sub = col.column()
        sub.enabled = not item.spawn_parent_inherit
        sub.prop(item, "spawn_radius")

        sub.separator(type="LINE")
        sub.prop(item, "spawn_color")


def _draw_loop_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "loop_type")

    if item.loop_type == "FOR_EACH":
        col.prop(item, "loop_for_each")

        if item.loop_for_each == "NEIGHBOUR":
            col.prop(item, "loop_for_each_neighbor_distance")

    elif item.loop_type == "FOR_INDEX":
        col.prop(item, "loop_start")
        col.prop(item, "loop_end")
        col.prop(item, "loop_step")

    elif item.loop_type == "TIME_CYCLE":
        draw_time_prop(col, item, "loop_time_start")
        draw_time_prop(col, item, "loop_time_length")
        col.prop(item, "loop_time_count")
        col.prop(item, "loop_time_from")

        col.separator()
        col.label(text="Channels:")
        col.prop(item, "loop_time_position")
        col.prop(item, "loop_time_velocity")
        col.prop(item, "loop_time_radius")
        col.prop(item, "loop_time_color")
        col.prop(item, "loop_time_mass")
        col.prop(item, "loop_time_rotation")

    col.separator()
    col.prop(item, "loop_name")


def _draw_script_settings(layout, item):
    from ..icons import get_icon

    col = layout.column()

    row = col.row(align=True)
    row.scale_y = 1.5
    row.operator(
        "nexus.open_glsl_editor",
        text="Edit Script...",
        icon_value=get_icon("nx_question_script"),
    )

    if item.script_source:
        box = col.box()
        lines = item.script_source.split("\n", 9)
        for line in lines[:8]:
            box.label(text=line if len(line) <= 60 else line[:57] + "...")
        if len(lines) > 8:
            box.label(text=f"... ({len(lines)} lines total)")
    else:
        col.label(text="No script defined", icon="INFO")


def _draw_var_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "var_name")
    col.prop(item, "var_type")
    col.prop(item, "var_type_write")
    col.prop(item, "var_type_particle")

    if item.var_type == "INT":
        col.prop(item, "var_type_int_val")
    elif item.var_type == "FLOAT":
        col.prop(item, "var_type_flt_val")
    elif item.var_type == "VEC":
        col.prop(item, "var_type_vec_val")


def _draw_folder_settings(layout, item):
    pass


QUESTION_DRAW_FUNCS = {
    "QUESTION": _draw_question_settings,
    "ACTION": _draw_action_settings,
    "LOOP": _draw_loop_settings,
    "SCRIPT": _draw_script_settings,
    "VAR": _draw_var_settings,
    "FOLDER": _draw_folder_settings,
}


def draw_question_item_settings(layout, item):
    draw_func = QUESTION_DRAW_FUNCS.get(item.item_type)
    if draw_func:
        draw_func(layout, item)


_QUESTION_TYPE_NODE_IDS = {
    "QUESTION": "ID_NX_QUESTION_TYPE_QUESTION",
    "ACTION": "ID_NX_QUESTION_TYPE_ACTION",
    "LOOP": "ID_NX_QUESTION_TYPE_LOOP",
    "SCRIPT": "ID_NX_QUESTION_TYPE_SCRIPT",
    "VAR": "ID_NX_QUESTION_TYPE_VAR",
    "FOLDER": "ID_NX_QUESTION_TYPE_FOLDER",
}

_CONDITION_IDS = {
    "IF": "ID_NX_QUESTION_CONDITION_IF",
    "ELSEIF": "ID_NX_QUESTION_CONDITION_ELSEIF",
    "ELSE": "ID_NX_QUESTION_CONDITION_ELSE",
}

_OPERATOR_IDS = {
    "NONE": "ID_NX_QUESTION_OPERATOR_NONE",
    "AND": "ID_NX_QUESTION_OPERATOR_AND",
    "AND_NOT": "ID_NX_QUESTION_OPERATOR_AND_NOT",
    "OR": "ID_NX_QUESTION_OPERATOR_OR",
    "OR_NOT": "ID_NX_QUESTION_OPERATOR_OR_NOT",
}

_IF_PARAM_IDS = {
    "DOCUMENT": "ID_NX_QUESTION_IF_PARAM_DOCUMENT",
    "PARTICLE": "ID_NX_QUESTION_IF_PARAM_PARTICLE",
    "MATH": "ID_NX_QUESTION_IF_PARAM_MATH",
}

_IF_PARTICLE_IDS = {
    "SPEED": "ID_NX_QUESTION_IF_PARTICLE_SPEED",
    "AGE": "ID_NX_QUESTION_IF_PARTICLE_AGE",
    "MASS": "ID_NX_QUESTION_IF_PARTICLE_MASS",
    "DISTANCE": "ID_NX_QUESTION_IF_PARTICLE_DISTANCE",
    "GROUP": "ID_NX_QUESTION_IF_PARTICLE_GROUP",
    "LIFE": "ID_NX_QUESTION_IF_PARTICLE_LIFE",
    "NEIGHBORS": "ID_NX_QUESTION_IF_PARTICLE_NEIGHBORS",
    "DENSITY": "ID_NX_QUESTION_IF_PARTICLE_DENSITY",
    "RADIUS": "ID_NX_QUESTION_IF_PARTICLE_RADIUS",
    "COLOR": "ID_NX_QUESTION_IF_PARTICLE_COLOR",
    "FLAGS": "ID_NX_QUESTION_IF_PARTICLE_FLAGS",
    "ID": "ID_NX_QUESTION_IF_PARTICLE_ID",
    "COUNT": "ID_NX_QUESTION_IF_PARTICLE_COUNT",
    "FALLOFF": "ID_NX_QUESTION_IF_PARTICLE_FALLOFF",
    "POSITION": "ID_NX_QUESTION_IF_PARTICLE_POSITION",
    "VELOCITY": "ID_NX_QUESTION_IF_PARTICLE_VELOCITY",
    "ROTATION": "ID_NX_QUESTION_IF_PARTICLE_ROTATION",
    "EMITTER": "ID_NX_QUESTION_IF_PARTICLE_EMITTER",
    "VERTEXWEIGHT": "ID_NX_QUESTION_IF_PARTICLE_VERTEXWEIGHT",
    "UVW": "ID_NX_QUESTION_IF_PARTICLE_UVW",
    "SMOKE": "ID_NX_QUESTION_IF_PARTICLE_SMOKE",
    "TEMPERATURE": "ID_NX_QUESTION_IF_PARTICLE_TEMPERATURE",
    "FUEL": "ID_NX_QUESTION_IF_PARTICLE_FUEL",
}

_IF_VECTOR_IDS = {
    "X": "ID_NX_QUESTION_IF_VECTOR_X",
    "Y": "ID_NX_QUESTION_IF_VECTOR_Y",
    "Z": "ID_NX_QUESTION_IF_VECTOR_Z",
    "R": "ID_NX_QUESTION_IF_VECTOR_R",
    "G": "ID_NX_QUESTION_IF_VECTOR_G",
    "B": "ID_NX_QUESTION_IF_VECTOR_B",
    "BRIGHTNESS": "ID_NX_QUESTION_IF_VECTOR_BRIGHTNESS",
    "RH": "ID_NX_QUESTION_IF_VECTOR_RH",
    "RP": "ID_NX_QUESTION_IF_VECTOR_RP",
    "RB": "ID_NX_QUESTION_IF_VECTOR_RB",
}

_IF_DOCUMENT_IDS = {
    "FRAME": "ID_NX_QUESTION_IF_DOCUMENT_FRAME",
    "CAMERA_DISTANCE": "ID_NX_QUESTION_IF_DOCUMENT_CAMERA_DISTANCE",
    "CAMERA_FOV": "ID_NX_QUESTION_IF_DOCUMENT_CAMERA_FOV",
    "OBJECT_DISTANCE": "ID_NX_QUESTION_IF_DOCUMENT_OBJECT_DISTANCE",
    "TIME": "ID_NX_QUESTION_IF_DOCUMENT_TIME",
}

_IF_MATH_IDS = {
    "CONST": "ID_NX_QUESTION_IF_MATH_CONST",
    "RANDOM": "ID_NX_QUESTION_IF_MATH_RANDOM",
    "SPLINE": "ID_NX_QUESTION_IF_MATH_SPLINE",
    "VAR": "ID_NX_QUESTION_IF_MATH_VAR",
    "WAVE": "ID_NX_QUESTION_IF_MATH_WAVE",
}

_IF_OP_IDS = {
    "LESS": "ID_NX_QUESTION_IF_OP_LESS",
    "LESSEQUAL": "ID_NX_QUESTION_IF_OP_LESSEQUAL",
    "EQUAL": "ID_NX_QUESTION_IF_OP_EQUAL",
    "NOTEQUAL": "ID_NX_QUESTION_IF_OP_NOTEQUAL",
    "GREATEREQUAL": "ID_NX_QUESTION_IF_OP_GREATEREQUAL",
    "GREATER": "ID_NX_QUESTION_IF_OP_GREATER",
    "WITHIN": "ID_NX_QUESTION_IF_OP_WITHIN",
    "NOTWITHIN": "ID_NX_QUESTION_IF_OP_NOTWITHIN",
}

_THEN_IDS = {
    "SET": "ID_NX_QUESTION_THEN_SET",
    "ADD": "ID_NX_QUESTION_THEN_ADD",
    "SPAWN": "ID_NX_QUESTION_THEN_CREATE",
    "KILL": "ID_NX_QUESTION_THEN_KILL",
    "BREAK": "ID_NX_QUESTION_THEN_STOP",
}

_SET_IDS = {
    "COLOR": "ID_NX_QUESTION_SET_COLOR",
    "RADIUS": "ID_NX_QUESTION_SET_RADIUS",
    "MASS": "ID_NX_QUESTION_SET_MASS",
    "GROUP": "ID_NX_QUESTION_SET_GROUP",
    "LIFE": "ID_NX_QUESTION_SET_LIFE",
    "SPEED": "ID_NX_QUESTION_SET_SPEED",
    "VELOCITY": "ID_NX_QUESTION_SET_VELOCITY",
    "ROTATION": "ID_NX_QUESTION_SET_ROTATION",
    "SCALE": "ID_NX_QUESTION_SET_SCALE",
    "AGE": "ID_NX_QUESTION_SET_AGE",
    "VAR": "ID_NX_QUESTION_SET_VAR",
    "FREEZE": "ID_NX_QUESTION_SET_FREEZE",
    "USERDATA": "ID_NX_QUESTION_SET_USERDATA",
    "DISPLAY": "ID_NX_QUESTION_SET_DISPLAY",
    "STICKY": "ID_NX_QUESTION_SET_STICKY",
}

_SET_VAR_TO_IDS = {
    "CONST": "ID_NX_QUESTION_SET_VAR_TO_CONST",
    "VALUE": "ID_NX_QUESTION_SET_VAR_TO_VALUE",
}

_SET_PARTICLE_DISPLAY_IDS = {
    "POINTS": "ID_NX_EMITTER_DISPLAY_MODE_DOT",
    "SQUARE": "ID_NX_EMITTER_DISPLAY_MODE_BOX",
    "DIRECTION": "ID_NX_EMITTER_DISPLAY_MODE_LINE",
    "BOX3D": "ID_NX_EMITTER_DISPLAY_MODE_BOX3D",
    "BOX3D_FILLED": "ID_NX_EMITTER_DISPLAY_MODE_BOX3D_FILLED",
    "CIRCLE": "ID_NX_EMITTER_DISPLAY_MODE_CIRCLE",
    "CIRCLE_FILLED": "ID_NX_EMITTER_DISPLAY_MODE_CIRCLE_FILLED",
    "PYRAMID": "ID_NX_EMITTER_DISPLAY_MODE_PYRAMID",
    "PYRAMID_FILLED": "ID_NX_EMITTER_DISPLAY_MODE_PYRAMID_FILLED",
    "ARROW": "ID_NX_EMITTER_DISPLAY_MODE_ARROW",
    "ARROW_FILLED": "ID_NX_EMITTER_DISPLAY_MODE_ARROW_FILLED",
    "SPHERE": "ID_NX_EMITTER_DISPLAY_MODE_SPHERE",
    "SSF": "ID_NX_EMITTER_DISPLAY_MODE_SSF",
    "AXIS": "ID_NX_EMITTER_DISPLAY_MODE_AXIS",
    "NONE": "ID_NX_EMITTER_DISPLAY_MODE_NONE",
}

_LOOP_TYPE_IDS = {
    "FOR_EACH": "ID_NX_QUESTION_LOOP_TYPE_FOR_EACH",
    "FOR_INDEX": "ID_NX_QUESTION_LOOP_TYPE_FOR_INDEX",
    "TIME_CYCLE": "ID_NX_QUESTION_LOOP_TYPE_TIME",
}

_LOOP_FOR_EACH_IDS = {
    "PARTICLE": "ID_NX_QUESTION_LOOP_FOR_EACH_PARTICLE",
    "NEIGHBOUR": "ID_NX_QUESTION_LOOP_FOR_EACH_NEIGHBOR",
}

_LOOP_TIME_FROM_IDS = {
    "DOCUMENT": "ID_NX_QUESTION_LOOP_TYPE_TIME_FROM_DOCUEMNT",
    "PARTICLE": "ID_NX_QUESTION_LOOP_TYPE_TIME_FROM_PARTICLE",
}

_VAR_TYPE_IDS = {
    "INT": "ID_NX_QUESTION_VAR_TYPE_INT",
    "FLOAT": "ID_NX_QUESTION_VAR_TYPE_FLT",
    "VEC": "ID_NX_QUESTION_VAR_TYPE_VEC",
    "USERDATA": "ID_NX_QUESTION_VAR_TYPE_USERDATA",
}

_IF_MATH_DEPENDTIME_IDS = {
    "OFF": "ID_NX_QUESTION_IF_MATH_DEPENDTIME_OFF",
    "PARTICLE": "ID_NX_QUESTION_IF_MATH_DEPENDTIME_PARTICLE",
    "DOCUMENT": "ID_NX_QUESTION_IF_MATH_DEPENDTIME_DOCUMENT",
}

_IF_DOCUMENT_OBJECT_MODE_IDS = {
    "POSITION": "ID_NX_QUESTION_IF_DOCUMENT_OBJECT_MODE_POSITION",
    "POINTS": "ID_NX_QUESTION_IF_DOCUMENT_OBJECT_MODE_POINTS",
    "POLYGONS": "ID_NX_QUESTION_IF_DOCUMENT_OBJECT_MODE_POLYGONS",
    "VOLUME": "ID_NX_QUESTION_IF_DOCUMENT_OBJECT_MODE_VOLUME",
}

_SPAWN_VELOCITY_DIR_IDS = {
    "SOURCE": "ID_NX_QUESTION_SPAWN_DIRECTION_SOURCE",
    "RANDOM": "ID_NX_QUESTION_SPAWN_DIRECTION_RANDOM",
}


def _sync_enum_int32(theron, nc, get, prop_id, value, id_map):
    mapped = id_map.get(value)
    if mapped is not None:
        theron.set_int32(nc, get(prop_id), get(mapped))


_question_poly_cache: dict = {}
_question_line_cache: dict = {}

QUESTION_POLY_SPEC = CacheSpec(
    kind=CacheKind.POLY,
    collection_attr="if_document_objects",
    cache_dict=_question_poly_cache,
)

QUESTION_LINE_SPEC = CacheSpec(
    kind=CacheKind.LINE,
    collection_attr="if_document_objects",
    cache_dict=_question_line_cache,
)

QUESTION_CAMERA_SPEC = CacheSpec(
    kind=CacheKind.CAMERA,
    collection_attr="if_document_camera",
    cache_dict={},
)

_question_active_cameras: set[str] = set()
_question_mesh_vertex_counts: dict[str, int] = {}


def _on_question_link_resolved(kind, target_obj, _handle, count_a, _count_b):
    if kind == "MESH":
        _question_mesh_vertex_counts[target_obj.name] = count_a


def _pre_question_objects_sync(
    _spec, _container, _props, *, obj=None, scene=None, depsgraph=None, collection_source=None
):
    del obj, scene, depsgraph, collection_source
    _question_mesh_vertex_counts.clear()


def _post_question_objects_sync(
    _spec, _container, _props, *, obj=None, scene=None, depsgraph=None, collection_source=None
):
    del obj, scene, depsgraph, collection_source
    _question_mesh_vertex_counts.clear()


_question_object_links = make_cached_link_resolver(
    poly_spec=QUESTION_POLY_SPEC,
    line_spec=QUESTION_LINE_SPEC,
    on_resolved=_on_question_link_resolved,
    extra_pre_syncer=_pre_question_objects_sync,
    extra_post_syncer=_post_question_objects_sync,
)

_QUESTION_OBJECT_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_QUESTION_IF_DOCUMENT_OBJECT_LIST",
    collection_attr="if_document_objects",
    sequential_node_id=True,
    pre_syncer=_question_object_links.pre_syncer,
    post_syncer=_question_object_links.post_syncer,
    node_link_resolver=_question_object_links.node_link_resolver,
    skip_if_no_link=True,
)


def _resolve_question_emitter_link(theron, item, _obj, scene, _depsgraph):
    from ..handlers.pipeline import get_nexus_obj_handle

    if item.obj is None:
        return None
    return get_nexus_obj_handle(scene, item.obj)


_QUESTION_EMITTER_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_QUESTION_EMITTERS",
    collection_attr="if_particle_emitters",
    sequential_node_id=True,
    node_link_resolver=_resolve_question_emitter_link,
    skip_if_no_link=True,
)


def _sync_question_node(theron, get, nc, item, item_orig, obj, scene, depsgraph):
    unit = TRANSFORM_FACTORS[Transform.UNIT_SCALE]
    pct = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]
    itype = item_orig.item_type

    if itype == "QUESTION":
        _sync_question_node_question(theron, nc, item, get, unit, pct, obj, scene, depsgraph)
    elif itype == "ACTION":
        _sync_question_node_action(theron, nc, item, get, unit, pct, scene)
    elif itype == "LOOP":
        _sync_question_node_loop(theron, nc, item, get, unit)
    elif itype == "VAR":
        _sync_question_node_var(theron, nc, item, get)
    elif itype == "FOLDER":
        _sync_question_node_folder(theron, nc, item, get)
    elif itype == "SCRIPT":
        _sync_question_node_script(theron, nc, item, get)


def _sync_question_node_question(theron, nc, item, get, unit, pct, obj, scene, depsgraph):

    _sync_enum_int32(theron, nc, get, "ID_NX_QUESTION_CONDITION", item.condition, _CONDITION_IDS)
    _sync_enum_int32(theron, nc, get, "ID_NX_QUESTION_OPERATOR", item.operator, _OPERATOR_IDS)
    _sync_enum_int32(theron, nc, get, "ID_NX_QUESTION_IF_PARAM", item.if_param, _IF_PARAM_IDS)
    _sync_enum_int32(
        theron, nc, get, "ID_NX_QUESTION_IF_PARTICLE", item.if_particle, _IF_PARTICLE_IDS
    )
    _sync_enum_int32(theron, nc, get, "ID_NX_QUESTION_IF_VECTOR", item.if_vector, _IF_VECTOR_IDS)
    _sync_enum_int32(
        theron, nc, get, "ID_NX_QUESTION_IF_DOCUMENT", item.if_document, _IF_DOCUMENT_IDS
    )
    _sync_enum_int32(theron, nc, get, "ID_NX_QUESTION_IF_MATH", item.if_math, _IF_MATH_IDS)
    _sync_enum_int32(theron, nc, get, "ID_NX_QUESTION_IF_OP", item.if_op, _IF_OP_IDS)
    _sync_enum_int32(theron, nc, get, "ID_NX_QUESTION_IF_INCLUDE", item.if_include, _IF_OP_IDS)

    def _sync_if_than_float():
        theron.set_float(nc, get("ID_NX_QUESTION_IF_THAN"), item.if_than)
        theron.set_float(nc, get("ID_NX_QUESTION_IF_THAN_VAR"), item.if_than_var)
        theron.set_float(nc, get("ID_NX_QUESTION_IF_THAN_TOP"), item.if_than_top)

    def _sync_if_than_int():
        theron.set_int32(nc, get("ID_NX_QUESTION_IF_THAN"), item.if_than_int)
        theron.set_int32(nc, get("ID_NX_QUESTION_IF_THAN_VAR"), item.if_than_int_var)
        theron.set_int32(nc, get("ID_NX_QUESTION_IF_THAN_TOP"), item.if_than_int_top)

    def _sync_if_than_time():
        mode = get_prop_time_mode(item, "if_than_time")
        num, den = to_time_fraction(float(item.if_than_time), mode=mode)
        theron.set_time(nc, get("ID_NX_QUESTION_IF_THAN"), num, den)

        mode = get_prop_time_mode(item, "if_than_time_var")
        num, den = to_time_fraction(float(item.if_than_time_var), mode=mode)
        theron.set_time(nc, get("ID_NX_QUESTION_IF_THAN_VAR"), num, den)

        mode = get_prop_time_mode(item, "if_than_time_top")
        num, den = to_time_fraction(float(item.if_than_time_top), mode=mode)
        theron.set_time(nc, get("ID_NX_QUESTION_IF_THAN_TOP"), num, den)

    if item.if_param == "PARTICLE":
        if item.if_particle in _INT_PARTICLE_TYPES:
            _sync_if_than_int()
        elif item.if_particle in _TIME_PARTICLE_TYPES:
            _sync_if_than_time()
        elif item.if_particle == "EMITTER":
            sync_nodetree(
                _QUESTION_EMITTER_TREE_SPEC,
                nc,
                item,
                obj=obj,
                scene=scene,
                depsgraph=depsgraph,
            )
        else:
            _sync_if_than_float()
    elif item.if_param == "MATH":
        _sync_if_than_float()
        theron.set_string(nc, get("ID_NX_QUESTION_IF_MATH_VAR_NAME"), item.if_math_var_name)
    elif item.if_param == "DOCUMENT":
        int_props = ["FRAME"]
        float_props = ["CAMERA_DISTANCE", "OBJECT_DISTANCE"]
        time_props = ["TIME"]

        if item.if_document in int_props:
            _sync_if_than_int()
        elif item.if_document in float_props:
            _sync_if_than_float()
        elif item.if_document == "CAMERA_FOV":
            theron.set_float(
                nc,
                get("ID_NX_QUESTION_IF_DOCUMENT_CAMERA_FOV_WIDEN"),
                item.if_document_camera_fov_widen,
            )
        elif item.if_document in time_props:
            _sync_if_than_time()
        else:
            print("nxQuestion: UNKNOWN DOCUMENT PROPERTY")
    else:
        print("nxQuestion: UNKNOWN QUESTION CATEGORY")

    theron.set_float(nc, get("ID_NX_QUESTION_IF_MATH_CONST_VALUE"), item.if_math_const_value)
    theron.set_float(nc, get("ID_NX_QUESTION_IF_MATH_FREQUENCY"), item.if_math_frequency)
    _sync_enum_int32(
        theron,
        nc,
        get,
        "ID_NX_QUESTION_IF_MATH_DEPENDTIME",
        item.if_math_dependtime,
        _IF_MATH_DEPENDTIME_IDS,
    )
    theron.set_bool(nc, get("ID_NX_QUESTION_IF_MATH_DEPENDINDEX"), item.if_math_dependindex)

    theron.set_float(nc, get("ID_NX_QUESTION_MATH_RANDOM_MIN"), item.if_math_random_min)
    theron.set_float(nc, get("ID_NX_QUESTION_MATH_RANDOM_MAX"), item.if_math_random_max)
    theron.set_int32(nc, get("ID_NX_QUESTION_MATH_RANDOM_SEED"), item.if_math_random_seed)

    theron.set_float(
        nc,
        get("ID_NX_QUESTION_IF_PARTICLE_NEIGHBORS_DISTANCE"),
        item.if_particle_neighbors_distance * unit,
    )

    theron.set_bool(nc, get("ID_NX_QUESTION_IF_ONCE"), item.if_once)

    theron.set_bool(
        nc,
        get("ID_NX_QUESTION_IF_PARTICLE_FLAGS_COLLIDE_OBJECT"),
        item.if_flag_collide_object,
    )
    theron.set_bool(
        nc,
        get("ID_NX_QUESTION_IF_PARTICLE_FLAGS_COLLIDE_PARTICLE"),
        item.if_flag_collide_particle,
    )
    theron.set_bool(
        nc,
        get("ID_NX_QUESTION_IF_PARTICLE_FLAGS_GROUP_CHANGED"),
        item.if_flag_group_changed,
    )
    theron.set_bool(nc, get("ID_NX_QUESTION_IF_PARTICLE_FLAGS_STUCK"), item.if_flag_stuck)
    theron.set_bool(nc, get("ID_NX_QUESTION_IF_PARTICLE_FLAGS_FROZEN"), item.if_flag_frozen)
    theron.set_bool(nc, get("ID_NX_QUESTION_IF_PARTICLE_FLAGS_BORN"), item.if_flag_born)

    theron.set_float(nc, get("ID_NX_QUESTION_WEIGHT"), item.weight * pct)

    _sync_enum_int32(
        theron,
        nc,
        get,
        "ID_NX_QUESTION_IF_DOCUMENT_OBJECT_MODE",
        item.if_document_object_mode,
        _IF_DOCUMENT_OBJECT_MODE_IDS,
    )

    if item.if_param == "DOCUMENT":
        if item.if_document in ("CAMERA_DISTANCE", "CAMERA_FOV"):
            from ..pipeline_manager.identity import ensure_object_uid

            mod_uid = ensure_object_uid(obj)
            cam_obj = item.if_document_camera
            camera_handle = ensure_camera_entry(QUESTION_CAMERA_SPEC, mod_uid, cam_obj)
            if camera_handle is not None:
                _question_active_cameras.add(cam_obj.name)
            theron.set_link(nc, get("ID_NX_QUESTION_IF_DOCUMENT_CAMERA"), camera_handle)
        elif item.if_document == "OBJECT_DISTANCE":
            sync_nodetree(
                _QUESTION_OBJECT_TREE_SPEC,
                nc,
                item,
                obj=obj,
                scene=scene,
                depsgraph=depsgraph,
            )


def _sync_question_node_action(theron, nc, item, get, unit, pct, scene):
    from ..handlers.pipeline import get_nexus_obj_handle

    _sync_enum_int32(theron, nc, get, "ID_NX_QUESTION_THEN", item.then, _THEN_IDS)
    _sync_enum_int32(theron, nc, get, "ID_NX_QUESTION_SET", item.set, _SET_IDS)

    theron.set_float(nc, get("ID_NX_QUESTION_WEIGHT"), item.weight * pct)

    s = item.set

    if s == "COLOR":
        c = item.set_prop_color
        theron.set_vector(nc, get("ID_NX_QUESTION_SET_PROP_COLOR"), c[0], c[1], c[2])
        cv = item.set_prop_color_var
        theron.set_vector(nc, get("ID_NX_QUESTION_SET_PROP_COLOR_VAR"), cv[0], cv[1], cv[2])
    elif s == "SPEED":
        theron.set_float(nc, get("ID_NX_QUESTION_SET_PROP_FLOAT"), item.set_prop_float * unit)
        theron.set_float(
            nc, get("ID_NX_QUESTION_SET_PROP_FLOAT_VAR"), item.set_prop_float_var * unit
        )
    elif s == "MASS":
        theron.set_float(nc, get("ID_NX_QUESTION_SET_PROP_FLOAT"), item.set_prop_float)
        theron.set_float(nc, get("ID_NX_QUESTION_SET_PROP_FLOAT_VAR"), item.set_prop_float_var)
    elif s == "RADIUS":
        theron.set_float(nc, get("ID_NX_QUESTION_SET_PROP_FLOAT"), item.set_prop_float * unit)
        theron.set_float(
            nc, get("ID_NX_QUESTION_SET_PROP_FLOAT_VAR"), item.set_prop_float_var * unit
        )
    elif s == "VELOCITY":
        v = item.set_prop_vel
        theron.set_vector(
            nc, get("ID_NX_QUESTION_SET_PROP_VEL"), v[0] * unit, v[1] * unit, v[2] * unit
        )
        vv = item.set_prop_vel_var
        theron.set_vector(
            nc, get("ID_NX_QUESTION_SET_PROP_VEL_VAR"), vv[0] * unit, vv[1] * unit, vv[2] * unit
        )
    elif s == "ROTATION":
        r = item.set_prop_rot
        theron.set_vector(nc, get("ID_NX_QUESTION_SET_PROP_ROT"), r[0], r[1], r[2])
        rv = item.set_prop_rot_var
        theron.set_vector(nc, get("ID_NX_QUESTION_SET_PROP_ROT_VAR"), rv[0], rv[1], rv[2])
    elif s == "SCALE":
        sc = item.set_prop_scale
        theron.set_vector(nc, get("ID_NX_QUESTION_SET_PROP_SCALE"), sc[0], sc[1], sc[2])
        scv = item.set_prop_scale_var
        theron.set_vector(nc, get("ID_NX_QUESTION_SET_PROP_SCALE_VAR"), scv[0], scv[1], scv[2])
    elif s == "LIFE":
        mode = get_prop_time_mode(item, "set_prop_life")
        num, den = to_time_fraction(float(item.set_prop_life), mode=mode)
        theron.set_time(nc, get("ID_NX_QUESTION_SET_PROP_LIFE"), num, den)
        mode = get_prop_time_mode(item, "set_prop_life_var")
        num, den = to_time_fraction(float(item.set_prop_life_var), mode=mode)
        theron.set_time(nc, get("ID_NX_QUESTION_SET_PROP_LIFE_VAR"), num, den)
    elif s == "AGE":
        mode = get_prop_time_mode(item, "set_prop_age")
        num, den = to_time_fraction(float(item.set_prop_age), mode=mode)
        theron.set_time(nc, get("ID_NX_QUESTION_SET_PROP_AGE"), num, den)
        mode = get_prop_time_mode(item, "set_prop_age_var")
        num, den = to_time_fraction(float(item.set_prop_age_var), mode=mode)
        theron.set_time(nc, get("ID_NX_QUESTION_SET_PROP_AGE_VAR"), num, den)
    elif s == "GROUP":
        link_handle = get_nexus_obj_handle(scene, item.set_prop_group)
        if link_handle is None:
            return False
        theron.set_link(nc, get("ID_NX_QUESTION_SET_PROP_GROUP"), link_handle)
    elif s == "VAR":
        theron.set_string(nc, get("ID_NX_QUESTION_SET_PROP_VAR"), item.set_prop_var_name)
        theron.set_float(nc, get("ID_NX_QUESTION_SET_PROP_VAR_FLT"), item.set_prop_var_flt)
        _sync_enum_int32(
            theron, nc, get, "ID_NX_QUESTION_SET_VAR_TO", item.set_var_to, _SET_VAR_TO_IDS
        )
    elif s == "FREEZE":
        theron.set_bool(nc, get("ID_NX_QUESTION_SET_PROP_FREEZE"), item.set_prop_freeze)
    elif s == "STICKY":
        theron.set_bool(nc, get("ID_NX_QUESTION_SET_PROP_STICKY"), item.set_prop_sticky)
    elif s == "DISPLAY":
        _sync_enum_int32(
            theron,
            nc,
            get,
            "ID_NX_QUESTION_SET_PARTICLE_DISPLAY",
            item.set_particle_display,
            _SET_PARTICLE_DISPLAY_IDS,
        )

    theron.set_float(nc, get("ID_NX_QUESTION_SET_DELAY"), item.set_delay * pct)
    theron.set_float(nc, get("ID_NX_QUESTION_SET_DELAY_DAMPING"), item.set_delay_damping * pct)
    theron.set_bool(nc, get("ID_NX_QUESTION_SET_ONCE"), item.set_once)

    if item.then == "SPAWN":
        theron.set_int32(nc, get("ID_NX_QUESTION_SPAWN_COUNT"), item.spawn_count)
        theron.set_float(nc, get("ID_NX_QUESTION_SPAWN_DIST"), item.spawn_dist * unit)
        sc = item.spawn_color
        theron.set_vector(nc, get("ID_NX_QUESTION_SPAWN_COLOR"), sc[0], sc[1], sc[2])
        theron.set_bool(nc, get("ID_NX_QUESTION_SPAWN_FULLLIFE"), item.spawn_fulllife)
        mode = get_prop_time_mode(item, "spawn_life")
        num, den = to_time_fraction(float(item.spawn_life), mode=mode)
        theron.set_time(nc, get("ID_NX_QUESTION_SPAWN_LIFE"), num, den)
        _sync_enum_int32(
            theron,
            nc,
            get,
            "ID_NX_QUESTION_SPAWN_VELOCITY",
            item.spawn_velocity_dir,
            _SPAWN_VELOCITY_DIR_IDS,
        )
        theron.set_float(nc, get("ID_NX_QUESTION_SPAWN_SPEED"), item.spawn_speed * unit)
        theron.set_float(nc, get("ID_NX_QUESTION_SPAWN_RADIUS"), item.spawn_radius * unit)
        theron.set_bool(nc, get("ID_NX_QUESTION_SPAWN_PARENT_INHERIT"), item.spawn_parent_inherit)

        spawn_emitter_handle = get_nexus_obj_handle(scene, item.spawn_emitter)
        if spawn_emitter_handle is not None:
            theron.set_link(nc, get("ID_NX_QUESTION_SPAWN_EMITTER"), spawn_emitter_handle)


def _sync_question_node_loop(theron, nc, item, get, unit):
    _sync_enum_int32(theron, nc, get, "ID_NX_QUESTION_LOOP_TYPE", item.loop_type, _LOOP_TYPE_IDS)
    _sync_enum_int32(
        theron, nc, get, "ID_NX_QUESTION_LOOP_FOR_EACH", item.loop_for_each, _LOOP_FOR_EACH_IDS
    )

    theron.set_float(
        nc,
        get("ID_NX_QUESTION_LOOP_FOR_EACH_NEIGHBOR_DISTANCE"),
        item.loop_for_each_neighbor_distance * unit,
    )

    theron.set_int32(nc, get("ID_NX_QUESTION_LOOP_START"), item.loop_start)
    theron.set_int32(nc, get("ID_NX_QUESTION_LOOP_END"), item.loop_end)
    theron.set_int32(nc, get("ID_NX_QUESTION_LOOP_STEP"), item.loop_step)

    mode = get_prop_time_mode(item, "loop_time_start")
    num, den = to_time_fraction(float(item.loop_time_start), mode=mode)
    theron.set_time(nc, get("ID_NX_QUESTION_LOOP_TYPE_TIME_START"), num, den)

    mode = get_prop_time_mode(item, "loop_time_length")
    num, den = to_time_fraction(float(item.loop_time_length), mode=mode)
    theron.set_time(nc, get("ID_NX_QUESTION_LOOP_TYPE_TIME_LENGTH"), num, den)

    theron.set_int32(nc, get("ID_NX_QUESTION_LOOP_TYPE_TIME_COUNT"), item.loop_time_count)

    _sync_enum_int32(
        theron,
        nc,
        get,
        "ID_NX_QUESTION_LOOP_TYPE_TIME_FROM",
        item.loop_time_from,
        _LOOP_TIME_FROM_IDS,
    )

    theron.set_bool(nc, get("ID_NX_QUESTION_LOOP_TYPE_TIME_POSITION"), item.loop_time_position)
    theron.set_bool(nc, get("ID_NX_QUESTION_LOOP_TYPE_TIME_VELOCITY"), item.loop_time_velocity)
    theron.set_bool(nc, get("ID_NX_QUESTION_LOOP_TYPE_TIME_RADIUS"), item.loop_time_radius)
    theron.set_bool(nc, get("ID_NX_QUESTION_LOOP_TYPE_TIME_COLOR"), item.loop_time_color)
    theron.set_bool(nc, get("ID_NX_QUESTION_LOOP_TYPE_TIME_MASS"), item.loop_time_mass)
    theron.set_bool(nc, get("ID_NX_QUESTION_LOOP_TYPE_TIME_ROTATION"), item.loop_time_rotation)


def _sync_question_node_var(theron, nc, item, get):

    theron.set_string(nc, get("ID_NX_QUESTION_VAR_NAME"), item.var_name)
    _sync_enum_int32(theron, nc, get, "ID_NX_QUESTION_VAR_TYPE", item.var_type, _VAR_TYPE_IDS)
    theron.set_bool(nc, get("ID_NX_QUESTION_VAR_TYPE_WRITE"), item.var_type_write)
    theron.set_bool(nc, get("ID_NX_QUESTION_VAR_TYPE_PARTICLE"), item.var_type_particle)
    theron.set_int32(nc, get("ID_NX_QUESTION_VAR_TYPE_INT_VAL"), item.var_type_int_val)
    theron.set_float(nc, get("ID_NX_QUESTION_VAR_TYPE_FLT_VAL"), item.var_type_flt_val)
    v = item.var_type_vec_val
    theron.set_vector(nc, get("ID_NX_QUESTION_VAR_TYPE_VEC_VAL"), v[0], v[1], v[2])


def _sync_question_node_folder(theron, nc, item, get):
    c = item.folder_color
    theron.set_vector(nc, get("ID_NX_QUESTION_FOLDER_COLOR"), c[0], c[1], c[2])


def _sync_question_node_script(theron, nc, item, get):
    theron.set_string(nc, get("ID_NX_QUESTION_SCRIPT_SOURCE"), item.script_source)


def _pre_question_tree_sync(
    _spec, _container, _props, *, obj=None, scene=None, depsgraph=None, collection_source=None
):
    del obj, scene, depsgraph, collection_source
    _question_active_cameras.clear()


def _post_question_tree_sync(
    _spec, _container, _props, *, obj=None, scene=None, depsgraph=None, collection_source=None
):
    del scene, depsgraph, collection_source
    if obj is not None:
        from ..pipeline_manager.identity import ensure_object_uid

        mod_uid = ensure_object_uid(obj)
        evict_stale_entries_for(QUESTION_CAMERA_SPEC, mod_uid, _question_active_cameras)
    _question_active_cameras.clear()


_QUESTION_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_QUESTION",
    collection_attr="question_items",
    type_id_map=_QUESTION_TYPE_NODE_IDS,
    parent_index_attr="parent_index",
    pre_dispatch_syncer_ctx=_sync_question_node,
    pre_syncer=_pre_question_tree_sync,
    post_syncer=_post_question_tree_sync,
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_QUESTION",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_QUESTION_ITERATIONS",
            prop=IntProperty(
                name="Iterations",
                description="Number of question iterations",
                default=1,
                min=1,
                max=50,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_QUESTION_ITERATION_WEIGHT",
            prop=FloatProperty(
                name="Iteration Weight",
                description="Weight applied per iteration",
                default=100.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="question_items",
            prop=CollectionProperty(
                name="Question Items",
                type=NexusQuestionItem,
            ),
        ),
        PropertyDescriptor(
            name="question_items_index",
            prop=IntProperty(
                name="Active Index",
                default=0,
                min=0,
            ),
        ),
    ),
    item_classes=(NexusQuestionItem,),
    enum_builders=(build_question_enum_items,),
    nodetree_sync=(_QUESTION_TREE_SPEC,),
)


register_collection_preset(
    "NX_QUESTION",
    CollectionPresetSpec(
        collection_attr="question_items",
        menu_id="question_items",
        hierarchy=True,
    ),
)
