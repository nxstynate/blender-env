import bpy
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d
from mathutils import Vector

__all__ = [
    'hex_to_rgb',
    'raycast_from_mouse',
    'hide_viewport_elements',
    'unhide_viewport_elements'
]

# Global state for viewport overlay management
original_visibility_states = {}
original_toolbar_state = {}  # New global for toolbar state

def hex_to_rgb(hex_color):
    """Convert hex color string to RGB tuple.
    
    Args:
        hex_color (str): Hex color in format '#RRGGBB' or 'RRGGBB'
        
    Returns:
        tuple: (R, G, B) tuple with values from 0.0 to 1.0
    """
    # Remove '#' if present
    hex_color = hex_color.lstrip('#')
    
    # Convert hex to RGB values (0-255)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    # Convert to float values (0.0-1.0)
    return (r/255.0, g/255.0, b/255.0)

def find_layer_collection_recursive(layer_collection, name):
    """
    Recursively search for a layer collection by name.
    
    Args:
        layer_collection: The root layer collection to start searching from
        name: The name of the collection to find
        
    Returns:
        The found LayerCollection or None if not found
    """
    if layer_collection.name == name:
        return layer_collection
    
    for child in layer_collection.children:
        found = find_layer_collection_recursive(child, name)
        if found:
            return found
    
    return None 


def raycast_from_mouse(context, event):
    """
    Raycast from the mouse position in the 3D View, returning
    (hit_location, hit_normal) if successful, or (None, None) if not.
    """
    region = context.region
    rv3d = context.region_data
    if not region or not rv3d:
        return None, None
    
    # Convert event coords to region coords
    coord = (event.mouse_x - region.x, event.mouse_y - region.y)

    ray_origin = region_2d_to_origin_3d(region, rv3d, coord)
    ray_dir = region_2d_to_vector_3d(region, rv3d, coord)
    if ray_origin is None or ray_dir is None:
        return None, None

    success, location, normal, _, _, _ = context.scene.ray_cast(
        depsgraph=context.evaluated_depsgraph_get(),
        origin=ray_origin,
        direction=ray_dir,
        distance=10000.0
    )

    if success:
        return location, normal
    return None, None

def get_rendering_viewports(context):
    """Return a list of viewports where rendering is active."""
    rendering_viewports = []
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D' and space.shading.type == 'RENDERED':
                    rendering_viewports.append((area, space))
    return rendering_viewports

def hide_viewport_elements(context):
    """Hide viewport overlay elements and store their original states."""
    global original_visibility_states, original_toolbar_state
    original_visibility_states = {}
    original_toolbar_state = {}

    # Get all rendering viewports
    rendering_viewports = get_rendering_viewports(context)

    # Define overlay and gizmo attributes
    overlay_attributes = [
        "show_relationship_lines",
        "show_floor",
        "show_cursor",
        "show_axis_x",
        "show_axis_y",
        "show_axis_z",
        "show_face_orientation",
        "show_wireframes",
        "show_object_origins_all",
        "show_outline_selected",
        "show_motion_paths",
        "show_bones",
        "show_stats",
        "show_text",
        "show_annotation",
    ]

    gizmo_attributes = [
        "show_gizmo",
        "show_gizmo_context",
        "show_gizmo_tool",
        "show_gizmo_object_rotate",
        "show_gizmo_object_translate",
        "show_gizmo_object_scale",
        "show_gizmo_navigate",
    ]

    # Store and hide elements for each rendering viewport
    for area, space in rendering_viewports:
        area_key = area.as_pointer()
        original_visibility_states[area_key] = {}

        # Handle toolbar
        for region in area.regions:
            if region.type == 'TOOLS':
                original_toolbar_state[area_key] = region.width > 1
                if region.width > 1:  # If toolbar is visible
                    with bpy.context.temp_override(area=area, space_data=space):
                        bpy.ops.wm.context_set_value(data_path="space_data.show_region_toolbar", value="False")

        # Handle overlay attributes
        for attr in overlay_attributes:
            if hasattr(space.overlay, attr):
                original_visibility_states[area_key][attr] = getattr(space.overlay, attr)
                setattr(space.overlay, attr, False)

        # Handle gizmo attributes
        for attr in gizmo_attributes:
            if hasattr(space, attr):
                original_visibility_states[area_key][attr] = getattr(space, attr)
                if attr == "show_gizmo":
                    setattr(space, attr, True)
                else:
                    setattr(space, attr, False)

def unhide_viewport_elements(context):
    """Restore viewport overlay elements to their original states."""
    global original_visibility_states, original_toolbar_state

    # Get all rendering viewports
    rendering_viewports = get_rendering_viewports(context)

    # Restore elements for each rendering viewport
    for area, space in rendering_viewports:
        area_key = area.as_pointer()

        # Restore toolbar state
        if area_key in original_toolbar_state and original_toolbar_state[area_key]:
            with bpy.context.temp_override(area=area, space_data=space):
                bpy.ops.wm.context_set_value(data_path="space_data.show_region_toolbar", value="True")

        # Restore overlay and gizmo states
        if area_key in original_visibility_states:
            for attr, value in original_visibility_states[area_key].items():
                if hasattr(space.overlay, attr):
                    setattr(space.overlay, attr, value)
                elif hasattr(space, attr):
                    setattr(space, attr, value)

    # Clear stored states
    original_visibility_states.clear()
    original_toolbar_state.clear() 