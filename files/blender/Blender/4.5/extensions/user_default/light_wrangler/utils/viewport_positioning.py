# Light Wrangler - Advanced light manipulation tools for Blender
# Copyright (C) 2025 Leonid Altman
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

def calc_pixel_size(context):
    """Calculate pixel size based on DPI and UI line width (Blender-native method)"""
    dpi = context.preferences.system.dpi
    ui_line_width = context.preferences.system.ui_line_width
    pixelsize = max(1, int(dpi / 64))
    pixelsize = max(1, pixelsize + ui_line_width)
    return pixelsize

def calc_widget_unit(context):
    """Calculate Blender's standard widget unit size"""
    pixel_size = context.preferences.system.pixel_size
    scale_factor = context.preferences.system.dpi / 72
    widget_unit = round(18 * scale_factor + 0.00001) + (2 * pixel_size)
    return widget_unit

def calc_icon_offset_from_axis(context):
    """Calculate offset needed to avoid mini-axis gizmos"""
    view_pref = context.preferences.view
    pixel_size = context.preferences.system.pixel_size
    ui_scale = context.preferences.system.ui_scale
    widget_unit = calc_widget_unit(context)
    offset = (widget_unit * 2.5) + (view_pref.mini_axis_size * pixel_size * 2)
    return offset / ui_scale

def get_n_panel_width(context):
    """Get width of N-panel (UI region)"""
    for region in context.area.regions:
        if region.type == "UI":
            return region.width
    return 0

def get_header_height(context):
    """Get height of header region"""
    for region in context.area.regions:
        if region.type == "HEADER":
            return region.height
    return 0

def get_base_navigation_height(context):
    """Calculate height used by built-in navigation gizmos and controls"""
    ui_scale = context.preferences.system.ui_scale
    view_pref = context.preferences.view
    
    # Base icon offset
    icon_offset_mini = 28 + 2
    icon_offset = view_pref.gizmo_size_navigate_v3d / 2.0 + 10.0
    
    # Calculate offset based on mini-axis type
    if view_pref.mini_axis_type == "MINIMAL":
        icon_offset_from_axis = calc_icon_offset_from_axis(context)
    elif view_pref.mini_axis_type == "GIZMO":
        icon_offset_from_axis = icon_offset * 2.1
    else:  # NONE
        icon_offset_from_axis = icon_offset_mini * 0.75
    
    h = icon_offset_from_axis
    
    # Add navigation controls height if visible
    if context.space_data.show_gizmo_navigate and view_pref.show_navigate_ui:
        h += icon_offset_mini * 4
    
    return h * ui_scale

def calculate_gizmo_row_height(context, row_position):
    """Calculate height for a specific gizmo row position"""
    ui_scale = context.preferences.system.ui_scale
    
    # Get the base height used by built-in navigation controls
    base_height = get_base_navigation_height(context)
    
    # Define the height of a single gizmo row (30 pixels like Colorista)
    # We multiply by ui_scale to ensure it's scaled correctly
    row_height = 30 * ui_scale
    
    # Calculate the final offset
    # We subtract 1 because rows are 1-indexed for users (row 1 = first additional row)
    additional_rows = max(0, row_position - 1)
    final_height = base_height + (additional_rows * row_height)
    
    return final_height

def calculate_gizmo_position(context, row_position=5):
    """Calculate optimal position for viewport gizmos based on row position"""
    ui_scale = context.preferences.system.ui_scale
    region = context.region
    
    # Base position (right edge with small margin)
    base_margin = (28 + 2) * 0.75
    x = region.width - base_margin * ui_scale
    y = region.height
    
    # Adjust for region overlap
    if context.preferences.system.use_region_overlap:
        # Subtract N-panel width
        x -= get_n_panel_width(context)
        
        # Subtract header height (doubled for safety)
        y -= get_header_height(context) * 2
    
    # Subtract height for the specified row position
    y -= calculate_gizmo_row_height(context, row_position)
    
    return x, y

def calculate_gizmo_scale(context):
    """Calculate appropriate gizmo scale - using Colorista's hardcoded approach"""
    # Colorista uses: (80 * 0.35) / 2 = 14.0
    # We'll use a similar hardcoded value for consistency
    scale = 14.0
    return scale