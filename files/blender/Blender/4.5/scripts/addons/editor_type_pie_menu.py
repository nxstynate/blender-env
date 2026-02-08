# SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
# Editor Type Pie Menu Add-on for Blender 4.x
# ============================================================================
# This add-on creates a pie menu for switching the editor type of the
# area (pane) currently under the mouse cursor.
#
# KEYBINDING: Alt+E (configurable in the KEYBINDING CONFIGURATION section below)
# ============================================================================

bl_info = {
    "name": "Editor Type Pie Menu",
    "author": "Claude",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "Hotkey: Alt+E (customizable)",
    "description": "Pie menu to switch editor type of the hovered pane",
    "category": "Interface",
}

import bpy
from bpy.types import Operator, Menu

# ============================================================================
# KEYBINDING CONFIGURATION
# ============================================================================
# Change these values to customize the hotkey that opens the pie menu.
# Common key options: 'E', 'Q', 'TAB', 'SPACE', etc.
# Modifier options: Set to True or False

HOTKEY_KEY = 'E'           # The main key
HOTKEY_ALT = True          # Alt modifier
HOTKEY_CTRL = False        # Ctrl modifier
HOTKEY_SHIFT = False       # Shift modifier

# ============================================================================
# EDITOR TYPE DEFINITIONS
# ============================================================================
# Each entry: (display_name, area.type, area.ui_type)
#
# For most editors, area.type and area.ui_type are the same.
# For Node Editor subtypes (Shader, Geometry Nodes, Compositor),
# area.type is 'NODE_EDITOR' but ui_type differs:
#   - Shader Editor: ui_type = 'ShaderNodeTree'
#   - Geometry Nodes: ui_type = 'GeometryNodeTree'
#   - Compositor: ui_type = 'CompositorNodeTree'

EDITOR_TYPES = [
    # (Display Name, area.type, area.ui_type)
    ("3D Viewport",         "VIEW_3D",      "VIEW_3D"),
    ("UV Editor",           "IMAGE_EDITOR", "UV"),
    ("Shader Editor",       "NODE_EDITOR",  "ShaderNodeTree"),
    ("Geometry Nodes",      "NODE_EDITOR",  "GeometryNodeTree"),
    ("Timeline",            "DOPESHEET_EDITOR", "TIMELINE"),
    ("Graph Editor",        "GRAPH_EDITOR", "FCURVES"),
    ("Dope Sheet",          "DOPESHEET_EDITOR", "DOPESHEET"),
    ("Outliner",            "OUTLINER",     "OUTLINER"),
    ("File Browser",        "FILE_BROWSER", "FILES"),
]

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_area_under_mouse(context, mouse_x, mouse_y):
    """
    Find the area (pane) under the given screen coordinates.
    
    Args:
        context: Blender context
        mouse_x: Absolute X coordinate on screen
        mouse_y: Absolute Y coordinate on screen
    
    Returns:
        The bpy.types.Area under the mouse, or None if not found.
    
    How it works:
        - Iterates through all areas in the current screen
        - Checks if mouse coordinates fall within each area's bounding box
        - Areas are defined by (x, y, width, height) in screen coordinates
    """
    for area in context.screen.areas:
        # Area bounds check
        if (area.x <= mouse_x < area.x + area.width and
            area.y <= mouse_y < area.y + area.height):
            return area
    return None


def get_region_in_area(area, region_type='WINDOW'):
    """
    Get a specific region within an area.
    
    Args:
        area: The bpy.types.Area to search
        region_type: Type of region to find (default 'WINDOW')
    
    Returns:
        The matching region or the first available region.
    """
    for region in area.regions:
        if region.type == region_type:
            return region
    # Fallback to first region if WINDOW not found
    return area.regions[0] if area.regions else None


# ============================================================================
# OPERATOR: Switch Editor Type
# ============================================================================

class SCREEN_OT_switch_editor_type(Operator):
    """Switch the editor type of the area under the mouse cursor"""
    bl_idname = "screen.switch_editor_type_hover"
    bl_label = "Switch Editor Type (Hover)"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Properties to store target editor type
    area_type: bpy.props.StringProperty(
        name="Area Type",
        description="The area.type value for the target editor",
        default="VIEW_3D"
    )
    
    ui_type: bpy.props.StringProperty(
        name="UI Type", 
        description="The area.ui_type value for the target editor",
        default="VIEW_3D"
    )
    
    # Store mouse position from invoke
    mouse_x: bpy.props.IntProperty(default=0)
    mouse_y: bpy.props.IntProperty(default=0)
    
    @classmethod
    def description(cls, context, properties):
        """Dynamic description based on target editor type."""
        for name, atype, utype in EDITOR_TYPES:
            if properties.area_type == atype and properties.ui_type == utype:
                return f"Switch hovered area to {name}"
        return "Switch editor type of hovered area"
    
    def invoke(self, context, event):
        """
        Called when operator is invoked (from menu click).
        Captures mouse position and executes.
        """
        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        return self.execute(context)
    
    def execute(self, context):
        """
        Switch the editor type of the area under the mouse.
        
        Node Editor Subtype Switching:
            The Node Editor has multiple subtypes (Shader, Geometry, Compositor).
            These share area.type = 'NODE_EDITOR' but differ in area.ui_type:
            - ShaderNodeTree: Opens shader node editor
            - GeometryNodeTree: Opens geometry nodes editor
            - CompositorNodeTree: Opens compositor
            
            We first set area.type, then area.ui_type to handle this correctly.
        """
        # Find the target area under mouse
        target_area = get_area_under_mouse(context, self.mouse_x, self.mouse_y)
        
        if target_area is None:
            self.report({'WARNING'}, "No area found under mouse cursor")
            return {'CANCELLED'}
        
        # Get a region for context override
        target_region = get_region_in_area(target_area)
        
        if target_region is None:
            self.report({'WARNING'}, "Could not find region in target area")
            return {'CANCELLED'}
        
        try:
            # Step 1: Set the base area type
            # This changes the fundamental editor type
            target_area.type = self.area_type
            
            # Step 2: Set the ui_type for subtypes (crucial for Node Editor)
            # For most editors, this matches area.type
            # For Node Editor subtypes, this switches between Shader/Geo/Compositor
            # For Image Editor, UV vs regular image editor
            # For Dopesheet, Timeline vs Dope Sheet
            target_area.ui_type = self.ui_type
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to switch editor type: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


# ============================================================================
# OPERATOR: Open Pie Menu (captures mouse position)
# ============================================================================

class SCREEN_OT_editor_type_pie_call(Operator):
    """Open the Editor Type pie menu at current mouse position"""
    bl_idname = "screen.editor_type_pie_call"
    bl_label = "Editor Type Pie Menu"
    
    def invoke(self, context, event):
        """
        Store mouse position globally so menu items can access it,
        then open the pie menu.
        
        We store coordinates in window manager's temporary namespace
        because pie menu items can't directly access the original event.
        """
        # Store mouse position for the switch operator to use later
        # Using window_manager as a temporary storage location
        wm = context.window_manager
        wm["_editor_pie_mouse_x"] = event.mouse_x
        wm["_editor_pie_mouse_y"] = event.mouse_y
        
        # Call the pie menu
        bpy.ops.wm.call_menu_pie(name="SCREEN_MT_editor_type_pie")
        
        return {'FINISHED'}


# ============================================================================
# OPERATOR: Switch with Stored Mouse Position
# ============================================================================

class SCREEN_OT_switch_editor_stored_pos(Operator):
    """Switch editor using stored mouse position from pie menu call"""
    bl_idname = "screen.switch_editor_stored_pos"
    bl_label = "Switch Editor (Stored Position)"
    bl_options = {'REGISTER', 'UNDO'}
    
    area_type: bpy.props.StringProperty(default="VIEW_3D")
    ui_type: bpy.props.StringProperty(default="VIEW_3D")
    editor_name: bpy.props.StringProperty(default="3D Viewport")
    
    @classmethod
    def description(cls, context, properties):
        return f"Switch to {properties.editor_name}"
    
    def execute(self, context):
        """Use stored mouse position to find and switch the target area."""
        wm = context.window_manager
        
        # Retrieve stored mouse position
        mouse_x = wm.get("_editor_pie_mouse_x", 0)
        mouse_y = wm.get("_editor_pie_mouse_y", 0)
        
        if mouse_x == 0 and mouse_y == 0:
            self.report({'WARNING'}, "Could not determine target area")
            return {'CANCELLED'}
        
        # Find target area
        target_area = get_area_under_mouse(context, mouse_x, mouse_y)
        
        if target_area is None:
            self.report({'WARNING'}, "No area found at stored position")
            return {'CANCELLED'}
        
        try:
            # Switch editor type (see detailed comments in main switch operator)
            target_area.type = self.area_type
            target_area.ui_type = self.ui_type
        except Exception as e:
            self.report({'ERROR'}, f"Failed to switch: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


# ============================================================================
# PIE MENU
# ============================================================================

class SCREEN_MT_editor_type_pie(Menu):
    """
    Pie menu for switching editor types.
    
    Pie Menu Layout:
        Pie menus in Blender have 8 positions arranged in a circle:
        - Items are added in order: W, E, S, N, NW, NE, SW, SE
        - Position 0 (West): First item added
        - Position 1 (East): Second item added
        - Position 2 (South): Third item added
        - etc.
        
        We have 9 items, so the layout will use all 8 primary positions
        plus one overflow. Blender handles overflow gracefully.
    """
    bl_idname = "SCREEN_MT_editor_type_pie"
    bl_label = "Switch Editor Type"
    
    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        
        # Pie positions are filled in this order:
        # W(0), E(1), S(2), N(3), NW(4), NE(5), SW(6), SE(7)
        #
        # Logical grouping for our editors:
        # W:  3D Viewport (most used)
        # E:  Outliner (often on right side)
        # S:  Timeline (often at bottom)
        # N:  UV Editor (common for modeling)
        # NW: Shader Editor
        # NE: Geometry Nodes
        # SW: Dope Sheet
        # SE: Graph Editor
        # Extra: File Browser (will appear as 9th item)
        
        ordered_editors = [
            ("3D Viewport",    "VIEW_3D",          "VIEW_3D"),          # W
            ("Outliner",       "OUTLINER",         "OUTLINER"),         # E
            ("Timeline",       "DOPESHEET_EDITOR", "TIMELINE"),         # S
            ("UV Editor",      "IMAGE_EDITOR",     "UV"),               # N
            ("Shader Editor",  "NODE_EDITOR",      "ShaderNodeTree"),   # NW
            ("Geometry Nodes", "NODE_EDITOR",      "GeometryNodeTree"), # NE
            ("Dope Sheet",     "DOPESHEET_EDITOR", "DOPESHEET"),        # SW
            ("Graph Editor",   "GRAPH_EDITOR",     "FCURVES"),          # SE
            ("3D Viewport",    "VIEW_3D",          "VIEW_3D"),          # 9th (duplicate for quick access)
        ]
        
        for name, area_type, ui_type in ordered_editors:
            op = pie.operator(
                "screen.switch_editor_stored_pos",
                text=name,
                icon=self.get_editor_icon(area_type, ui_type)
            )
            op.area_type = area_type
            op.ui_type = ui_type
            op.editor_name = name
    
    @staticmethod
    def get_editor_icon(area_type, ui_type):
        """
        Return appropriate icon for each editor type.
        Icons help users quickly identify editors in the pie menu.
        """
        icons = {
            ("VIEW_3D", "VIEW_3D"): "VIEW3D",
            ("IMAGE_EDITOR", "UV"): "UV",
            ("NODE_EDITOR", "ShaderNodeTree"): "SHADING_RENDERED",
            ("NODE_EDITOR", "GeometryNodeTree"): "GEOMETRY_NODES",
            ("DOPESHEET_EDITOR", "TIMELINE"): "TIME",
            ("GRAPH_EDITOR", "FCURVES"): "GRAPH",
            ("DOPESHEET_EDITOR", "DOPESHEET"): "ACTION",
            ("OUTLINER", "OUTLINER"): "OUTLINER",
        }
        return icons.get((area_type, ui_type), "NONE")


# ============================================================================
# KEYMAP REGISTRATION
# ============================================================================

# Store keymap items for proper cleanup
addon_keymaps = []


def register_keymaps():
    """
    Register the hotkey for opening the pie menu.
    
    The keymap is added to 'Window' context so it works globally,
    regardless of which editor is currently active.
    """
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    
    if kc is None:
        # Can happen in background mode
        return
    
    # Add to Window keymap (global context)
    km = kc.keymaps.new(name="Window", space_type='EMPTY')
    
    kmi = km.keymap_items.new(
        "screen.editor_type_pie_call",  # Operator to call
        type=HOTKEY_KEY,                # Key (configured at top of file)
        value='PRESS',                  # Trigger on key press
        alt=HOTKEY_ALT,                 # Alt modifier
        ctrl=HOTKEY_CTRL,               # Ctrl modifier  
        shift=HOTKEY_SHIFT,             # Shift modifier
    )
    
    addon_keymaps.append((km, kmi))


def unregister_keymaps():
    """Remove all registered keymaps on addon unload."""
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    SCREEN_OT_switch_editor_type,
    SCREEN_OT_editor_type_pie_call,
    SCREEN_OT_switch_editor_stored_pos,
    SCREEN_MT_editor_type_pie,
)


def register():
    """Register add-on classes and keymaps."""
    for cls in classes:
        bpy.utils.register_class(cls)
    register_keymaps()
    print("Editor Type Pie Menu: Registered (Hotkey: Alt+E)")


def unregister():
    """Unregister add-on classes and keymaps."""
    unregister_keymaps()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("Editor Type Pie Menu: Unregistered")


if __name__ == "__main__":
    register()
