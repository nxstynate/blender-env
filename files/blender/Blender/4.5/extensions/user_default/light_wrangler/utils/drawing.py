import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Matrix
import math
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_location_3d
import blf
from . import font_manager
from .blender_compat import get_font_size

def get_property_label(property_type, light_type='POINT'):
    """Return user-friendly label for property type based on light type"""
    if property_type == 'SIZE':
        if light_type == 'POINT':
            return "Radius"
        elif light_type == 'SUN':
            return "Angle"
        elif light_type == 'SPOT':
            return "Spot Size"
        else:  # AREA
            return "Size"
    elif property_type == 'SPREAD':
        if light_type == 'SPOT':
            return "Blend"
        return "Spread"
    elif property_type == 'POWER':
        if light_type == 'SUN':
            return "Strength"
        return "Power"
            
    # Other properties remain the same
    labels = {
        'SIZE_X': "Width",
        'SIZE_Y': "Height",
        'DISTANCE': "Distance",
        'ROTATION': "Rotation"
    }
    return labels.get(property_type)

def calculate_light_shape_dimensions(context, light_object, base_ring_size):
    """Calculate fixed dimensions for light shape visualization."""
    light_data = light_object.data
    
    # Use fixed size relative to ring
    fixed_size = base_ring_size * 0.4  # 40% of ring size
    
    if light_data.type != 'AREA':
        return fixed_size, fixed_size
        
    # For area lights, maintain aspect ratio but with fixed base size
    if light_data.shape in {'SQUARE', 'DISK'}:
        return fixed_size, fixed_size
    else:  # RECTANGLE or ELLIPSE
        # Keep aspect ratio but ensure larger dimension is fixed_size
        if light_data.size == 0:
            return fixed_size, fixed_size
            
        ratio = light_data.size_y / light_data.size
        if ratio > 1.0:
            # Height is larger, keep it at fixed_size and scale width down
            return fixed_size / ratio, fixed_size
        else:
            # Width is larger or equal, keep it at fixed_size and scale height down
            return fixed_size, fixed_size * ratio

def create_superellipse_vertices(x, y, width, height, radius, segments_per_corner=16):
    """Create vertices for a superellipse (squircle) shape using Apple's corner style."""
    vertices = []
    
    # Superellipse power (Apple uses ~5 for their UI)
    n = 5
    
    # Generate vertices for each corner
    for corner in range(4):
        # Calculate corner center
        if corner == 0:   # Top right
            cx, cy = x + width - radius, y + height - radius
            start_angle, end_angle = 0, math.pi/2
        elif corner == 1: # Top left
            cx, cy = x + radius, y + height - radius
            start_angle, end_angle = math.pi/2, math.pi
        elif corner == 2: # Bottom left
            cx, cy = x + radius, y + radius
            start_angle, end_angle = math.pi, 3*math.pi/2
        else:           # Bottom right
            cx, cy = x + width - radius, y + radius
            start_angle, end_angle = 3*math.pi/2, 2*math.pi
            
        # Generate corner vertices
        for i in range(segments_per_corner + 1):
            angle = start_angle + (end_angle - start_angle) * (i / segments_per_corner)
            # Superellipse formula
            dx = math.cos(angle)
            dy = math.sin(angle)
            # Apply superellipse power
            dx = math.copysign(math.pow(abs(dx), 2/n), dx)
            dy = math.copysign(math.pow(abs(dy), 2/n), dy)
            vertices.append((cx + dx * radius, cy + dy * radius))
            
    return vertices

def get_ui_scale_font_size():
    """Calculate font size based on Blender's UI scale preferences"""
    ui_scale = bpy.context.preferences.system.ui_scale  # EXACTLY as they do - system not view!
    base_ui_scale = 1.25
    scale_factor = ui_scale / base_ui_scale
    return int(14 * scale_factor)  # Their exact base size of 14

def draw_hud_text(context, center_2d, text):
    """Draw minimal, modern HUD text with Apple-style rounded corners."""
    if not center_2d:
        return

    # Set up font drawing with font and UI-scaled size
    font_id = 0  # Use Blender's built-in font
    font_size = get_ui_scale_font_size()
    compat_font_size = get_font_size()
    if compat_font_size > 0:
        blf.size(font_id, font_size, 72)  # For Blender 2.x
    else:
        blf.size(font_id, font_size)  # For Blender 3.x+
    
    # Get text dimensions
    text_width, text_height = blf.dimensions(font_id, text)
    
    # Clean, minimal padding (scaled with font size)
    padding_scale = font_size / 13  # Scale padding relative to default font size
    padding_x = int(10 * padding_scale)
    padding_y = int(6 * padding_scale)
    bg_width = text_width + (padding_x * 2)
    bg_height = text_height + (padding_y * 2)
    
    # Position above center (scaled with font size)
    x = int(center_2d[0] - bg_width/2)
    y = int(center_2d[1] + 28 * padding_scale)
    
    # Apple-style corner radius (proportional to height)
    corner_radius = min(bg_height * 0.35, 8.0 * padding_scale)  # Cap at scaled 8px
    
    # Draw with GPU shader
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    shader.bind()
    gpu.state.blend_set('ALPHA')
    
    # Create superellipse vertices
    vertices = create_superellipse_vertices(x, y, bg_width, bg_height, corner_radius)
    
    # Draw background with frosted glass effect
    shader.uniform_float("color", (1.0, 1.0, 1.0, 0.12))
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})
    batch.draw(shader)
    
    # Draw text
    text_y = y + ((bg_height - text_height) / 2)
    blf.position(font_id, x + padding_x, text_y, 0)
    blf.color(font_id, 1.0, 1.0, 1.0, 0.9)
    blf.draw(font_id, text)
    
    gpu.state.blend_set('NONE')

def format_property_text(operator, property_type):
    """Format property values with Apple-style typography and measurements."""
    
    def get_appropriate_unit(value1, value2=None):
        """Determine the appropriate unit for one or two values"""
        unit_system = bpy.context.scene.unit_settings.system
        if unit_system == 'IMPERIAL':
            inches1 = value1 * 39.3701
            inches2 = value2 * 39.3701 if value2 is not None else inches1
            max_inches = max(inches1, inches2) if value2 is not None else inches1
            
            if max_inches < 1:
                return 'th'
            elif max_inches < 12:
                return 'in'
            else:
                return 'ft'
        else:  # METRIC
            max_value = max(value1, value2) if value2 is not None else value1
            if max_value < 0.01:
                return 'mm'
            elif max_value < 1:
                return 'cm'
            else:
                return 'm'
    
    def format_dimension(value, unit_type=None, hide_unit=False):
        """Format dimension with smart unit display"""
        if unit_type is None:
            unit_type = get_appropriate_unit(value)
            
        unit_system = bpy.context.scene.unit_settings.system
        
        if unit_system == 'IMPERIAL':
            inches = value * 39.3701
            if unit_type == 'th':
                val = inches * 16
                unit = " th"
            elif unit_type == 'in':
                val = inches
                unit = "″"
            else:  # 'ft'
                val = inches / 12
                unit = "′"
        else:  # METRIC
            if unit_type == 'mm':
                val = value * 1000
                unit = " mm"
            elif unit_type == 'cm':
                val = value * 100
                unit = " cm"
            else:  # 'm'
                val = value
                unit = " m"
                
        # Format number
        if unit_type in ['m', 'ft', 'in']:
            formatted = f"{val:.1f}".rstrip('0').rstrip('.')
        else:
            formatted = f"{val:.0f}"
            
        return formatted if hide_unit else formatted + unit
    
    def format_angle(radians):
        """Format angle with smart degree display"""
        degrees = math.degrees(radians)
        return f"{round(degrees)}°"
    
    if property_type == 'POWER':
        value = operator.current_power
        if operator.light_object.data.type == 'SUN':
            return f"{value:.2f}"  # Sun strength is unitless
        if value >= 1000:
            return f"{value/1000:.1f} kW"
        elif value < 1:
            return f"{value*1000:.0f} mW"
        return f"{value:.0f} W"
        
    elif property_type in {'SIZE', 'SIZE_X', 'SIZE_Y'}:
        light_data = operator.light_object.data
        if light_data.type == 'AREA':
            # Always show both dimensions for area lights
            if hasattr(light_data, 'shape') and light_data.shape in {'RECTANGLE', 'ELLIPSE'}:
                # Determine consistent unit type based on larger dimension
                unit_type = get_appropriate_unit(light_data.size, light_data.size_y)
                return f"{format_dimension(light_data.size, unit_type, True)} × {format_dimension(light_data.size_y, unit_type)}"
            return format_dimension(light_data.size)
        elif light_data.type == 'SPOT':
            return format_angle(light_data.spot_size)
        elif light_data.type == 'POINT':
            return format_dimension(light_data.shadow_soft_size)
        elif light_data.type == 'SUN':
            return format_angle(light_data.angle)
        return None
        
    elif property_type == 'DISTANCE':
        return format_dimension(operator.current_distance)
        
    elif property_type == 'ROTATION':
        return format_angle(operator.current_z_rotation)
        
    elif property_type == 'SPREAD':
        light_data = operator.light_object.data
        if light_data.type == 'SPOT':
            # For spot lights, show blend value as percentage
            return f"{light_data.spot_blend * 100:.0f}%"
        elif light_data.type == 'AREA':
            # For area lights, show spread angle in degrees
            return format_angle(light_data.spread)
        return None
        
    return None

def draw_orbit_visualization(context, center, light_location, current_z_rotation, operator):
    """Draw updated visualization with view-adaptive geometry."""
    # Validate viewport context
    if (not hasattr(operator, 'initial_area') or 
        context.area != operator.initial_area or 
        not hasattr(operator, 'initial_region') or 
        context.region != operator.initial_region):
        return

    region = context.region
    rv3d = context.region_data
    
    # Compute base size
    center_2d = location_3d_to_region_2d(region, rv3d, center)
    if center_2d is None:
        return

    screen_factor = 0.05  # Base fraction of the region height
    pixel_offset = region.height * screen_factor
    offset_2d = center_2d + Vector((pixel_offset, 0))
    world_offset = region_2d_to_location_3d(region, rv3d, offset_2d, center)
    if world_offset is None:
        return
    base_size = (world_offset - center).length

    RING_RADIUS = base_size  # Ring size stays constant
    TICK_SIZE = base_size * 0.05
    SEGMENTS = 64

    # Determine colors
    view_dir = rv3d.view_matrix.to_3x3()[2]
    rot_matrix = operator.light_object.matrix_world.to_3x3().transposed()
    ring_up = Vector((0, 0, 1)) @ rot_matrix
    viewing_from_front = view_dir.dot(ring_up) > 0

    # Get theme color
    THEME_COLOR = context.preferences.themes[0].view_3d.object_active

    # Create colors
    if viewing_from_front:
        BASE_COLOR = (*THEME_COLOR, 0.9)
        BASE_XRAY = (*THEME_COLOR, 0.9)
    else:
        backside_base = (
            THEME_COLOR[0] * 0.55 + 0.2,
            THEME_COLOR[1] * 0.55 + 0.18,
            THEME_COLOR[2] * 0.55 + 0.3
        )
        BASE_COLOR = (*backside_base, 0.9)
        BASE_XRAY = (*[c * 0.8 for c in backside_base], 0.15)

    # Use base colors for all elements
    SHAPE_COLOR = BASE_COLOR
    SHAPE_XRAY = BASE_XRAY
    MEASURE_COLOR = (*THEME_COLOR, 0.9)
    MEASURE_XRAY = (*THEME_COLOR, 0.15)

    # Setup GPU shader and state
    shader_3d = gpu.shader.from_builtin('UNIFORM_COLOR')
    shader_3d.bind()
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('LESS_EQUAL')

    # Draw measurement line with animation for distance property
    light_dir = (light_location - center).normalized()
    light_distance = (light_location - center).length

    vertices = [center, light_location]
    
    # Draw visible part of measurement line
    gpu.state.depth_test_set('LESS_EQUAL')
    batch = batch_for_shader(shader_3d, 'LINES', {"pos": vertices})
    line_color = list(MEASURE_COLOR)
    shader_3d.uniform_float("color", tuple(line_color))
    batch.draw(shader_3d)

    # Draw occluded part of measurement line
    gpu.state.depth_test_set('GREATER')
    batch = batch_for_shader(shader_3d, 'LINES', {"pos": vertices})
    line_color = list(MEASURE_XRAY)  # Use XRAY color for occluded part
    shader_3d.uniform_float("color", tuple(line_color))
    batch.draw(shader_3d)

    # Draw ticks along the measurement line
    tick_count = min(int(light_distance / (RING_RADIUS * 0.25)), 64)
    if tick_count > 0:
        tick_spacing = light_distance / tick_count
        for i in range(tick_count):
            dist = tick_spacing * (i + 1)
            tick_pos = center + light_dir * dist
            # Use light's local Y axis as the fixed tick direction
            tick_right = (Vector((0, 1, 0)) @ rot_matrix).normalized() * TICK_SIZE
            vertices = [tick_pos - tick_right, tick_pos + tick_right]
            
            # Draw visible tick
            gpu.state.depth_test_set('LESS_EQUAL')
            batch = batch_for_shader(shader_3d, 'LINES', {"pos": vertices})
            shader_3d.uniform_float("color", MEASURE_COLOR)
            batch.draw(shader_3d)
            
            # Draw occluded tick
            gpu.state.depth_test_set('GREATER')
            batch = batch_for_shader(shader_3d, 'LINES', {"pos": vertices})
            shader_3d.uniform_float("color", MEASURE_XRAY)
            batch.draw(shader_3d)
            
            # Draw distance text at the midpoint tick
            if i == tick_count // 2:
                text_pos = tick_pos + tick_right * 1.2
                text_2d = location_3d_to_region_2d(region, rv3d, text_pos)
                if text_2d:
                    font_size = 11
                    compat_font_size = get_font_size()
                    if compat_font_size > 0:
                        blf.size(0, font_size, 72)  # For Blender 2.x
                    else:
                        blf.size(0, font_size)  # For Blender 3.x+
                    blf.color(0, *MEASURE_COLOR)
                    blf.position(0, text_2d.x, text_2d.y, 0)
                    blf.draw(0, f"{light_distance:.1f}m")

    # Draw the orbit ring and its elements only in orbit mode
    if operator.mode == 'ORBIT':
        # -------------------------------------------------------------------------
        # Internal helper: create ring vertices
        # -------------------------------------------------------------------------
        def create_ring_vertices(horizontal=True, occluded=False):
            vertices = []
            segment_angle = (2 * math.pi) / SEGMENTS
            for i in range(SEGMENTS + 1):
                # To create a dotted effect for occluded segments, skip every other segment
                if occluded and i % 2 == 0:
                    continue
                
                angle = i * segment_angle
                if horizontal:
                    x = math.cos(angle) * RING_RADIUS
                    y = math.sin(angle) * RING_RADIUS
                    z = 0.0
                else:
                    x = math.cos(angle) * RING_RADIUS
                    y = 0.0
                    z = math.sin(angle) * RING_RADIUS
                vertex = Vector((x, y, z)) @ rot_matrix + center
                vertices.append(tuple(vertex))
                
                # For occluded segments, add a small gap to accent the dotted effect
                if occluded:
                    gap_angle = angle + segment_angle * 0.6
                    if horizontal:
                        x = math.cos(gap_angle) * RING_RADIUS
                        y = math.sin(gap_angle) * RING_RADIUS
                        z = 0.0
                    else:
                        x = math.cos(gap_angle) * RING_RADIUS
                        y = 0.0
                        z = math.sin(gap_angle) * RING_RADIUS
                    vertex = Vector((x, y, z)) @ rot_matrix + center
                    vertices.append(tuple(vertex))
            return vertices

        # Draw the primary (visible) and occluded orbit rings
        gpu.state.depth_test_set('LESS_EQUAL')
        vertices = create_ring_vertices(horizontal=True, occluded=False)
        batch = batch_for_shader(shader_3d, 'LINE_STRIP', {"pos": vertices})
        shader_3d.uniform_float("color", BASE_COLOR)
        batch.draw(shader_3d)

        gpu.state.depth_test_set('GREATER')
        vertices = create_ring_vertices(horizontal=True, occluded=True)
        batch = batch_for_shader(shader_3d, 'LINES', {"pos": vertices})
        shader_3d.uniform_float("color", BASE_XRAY)
        batch.draw(shader_3d)

        # Draw rotation markers on the ring
        gpu.state.depth_test_set('LESS_EQUAL')
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            marker_offset = Vector((math.cos(rad), math.sin(rad), 0)) * RING_RADIUS
            marker_pos = center + (marker_offset @ rot_matrix)
            marker_dir = (marker_pos - center).normalized()
            marker_end = marker_pos + marker_dir * (TICK_SIZE * 1.5)
            
            vertices = [marker_pos, marker_end]
            batch = batch_for_shader(shader_3d, 'LINES', {"pos": vertices})
            shader_3d.uniform_float("color", MEASURE_COLOR)
            batch.draw(shader_3d)
            
            # Label the marker if it aligns with the current rotation
            if abs(math.degrees(current_z_rotation) - angle) < 22.5:
                text_pos = marker_end + marker_dir * (TICK_SIZE * 2)
                text_2d = location_3d_to_region_2d(region, rv3d, text_pos)
                if text_2d:
                    font_size = 11
                    compat_font_size = get_font_size()
                    if compat_font_size > 0:
                        blf.size(0, font_size, 72)  # For Blender 2.x
                    else:
                        blf.size(0, font_size)  # For Blender 3.x+
                    blf.color(0, *MEASURE_COLOR)
                    blf.position(0, text_2d.x, text_2d.y, 0)
                    blf.draw(0, f"{angle}°")

    # Draw the light shape for all modes
    shape_size_x, shape_size_y = calculate_light_shape_dimensions(context, operator.light_object, RING_RADIUS)
    projection_point = center + light_dir * RING_RADIUS

    def create_light_shape_vertices(occluded=False):
        vertices = []
        local_segments = SEGMENTS // 2
        for i in range(local_segments + 1):
            if occluded and i % 2 == 0:
                continue
                
            angle = (i / local_segments) * 2 * math.pi
            if operator.light_object.data.type == 'AREA' and hasattr(operator.light_object.data, 'shape'):
                light_shape = operator.light_object.data.shape
                if light_shape in {'SQUARE', 'RECTANGLE'}:
                    angle_cos = math.cos(angle)
                    angle_sin = math.sin(angle)
                    x = math.copysign(shape_size_x, angle_cos) if abs(angle_cos) > 0.7071 else shape_size_x * angle_cos * 1.4142
                    y = math.copysign(shape_size_y, angle_sin) if abs(angle_sin) > 0.7071 else shape_size_y * angle_sin * 1.4142
                else:  # 'DISK' or 'ELLIPSE'
                    x = math.cos(angle) * shape_size_x
                    y = math.sin(angle) * shape_size_y
            else:  # For non-area lights or area lights without shape, draw a simple circle
                x = math.cos(angle) * shape_size_x
                y = math.sin(angle) * shape_size_y
            vertex = Vector((x, y, 0.0)) @ rot_matrix + projection_point
            vertices.append(tuple(vertex))
            
            if occluded:
                gap_angle = angle + (2 * math.pi / local_segments) * 0.8
                if operator.light_object.data.type == 'AREA' and hasattr(operator.light_object.data, 'shape'):
                    light_shape = operator.light_object.data.shape
                    if light_shape in {'SQUARE', 'RECTANGLE'}:
                        angle_cos = math.cos(gap_angle)
                        angle_sin = math.sin(gap_angle)
                        x = math.copysign(shape_size_x, angle_cos) if abs(angle_cos) > 0.7071 else shape_size_x * angle_cos * 1.4142
                        y = math.copysign(shape_size_y, angle_sin) if abs(angle_sin) > 0.7071 else shape_size_y * angle_sin * 1.4142
                    else:  # 'DISK' or 'ELLIPSE'
                        x = math.cos(gap_angle) * shape_size_x
                        y = math.sin(gap_angle) * shape_size_y
                else:  # For non-area lights or area lights without shape, draw a simple circle
                    x = math.cos(gap_angle) * shape_size_x
                    y = math.sin(gap_angle) * shape_size_y
                vertex = Vector((x, y, 0.0)) @ rot_matrix + projection_point
                vertices.append(tuple(vertex))
        return vertices

    # Draw light shape with boosted colors
    gpu.state.depth_test_set('LESS_EQUAL')
    vertices = create_light_shape_vertices(occluded=False)
    batch = batch_for_shader(shader_3d, 'LINE_STRIP', {"pos": vertices})
    shader_3d.uniform_float("color", SHAPE_COLOR)
    batch.draw(shader_3d)

    gpu.state.depth_test_set('GREATER')
    vertices = create_light_shape_vertices(occluded=True)
    batch = batch_for_shader(shader_3d, 'LINES', {"pos": vertices})
    shader_3d.uniform_float("color", SHAPE_XRAY)
    batch.draw(shader_3d)

    # Draw light direction indicator for all modes
    direction_length = RING_RADIUS * 0.3
    direction_end = projection_point - light_dir * direction_length
    vertices = [projection_point, direction_end]
    
    gpu.state.depth_test_set('LESS_EQUAL')
    batch = batch_for_shader(shader_3d, 'LINES', {"pos": vertices})
    shader_3d.uniform_float("color", MEASURE_COLOR)
    batch.draw(shader_3d)
    
    gpu.state.depth_test_set('GREATER')
    batch = batch_for_shader(shader_3d, 'LINES', {"pos": vertices})
    shader_3d.uniform_float("color", MEASURE_XRAY)
    batch.draw(shader_3d)

    # Draw mode-specific elements for REFLECT and DIRECT modes
    if operator.mode in {'REFLECT', 'DIRECT'}:
        # Draw normal vector for surface alignment
        normal_length = RING_RADIUS * 0.5
        normal_dir = -(light_location - center).normalized()
        normal_end = center + normal_dir * normal_length
        
        vertices = [center, normal_end]
        
        gpu.state.depth_test_set('LESS_EQUAL')
        batch = batch_for_shader(shader_3d, 'LINES', {"pos": vertices})
        shader_3d.uniform_float("color", (*THEME_COLOR, 0.5))
        batch.draw(shader_3d)
        
        if operator.mode == 'REFLECT':
            # Draw reflection vector
            reflection = normal_dir - 2 * (normal_dir.dot(-light_dir)) * (-light_dir)
            reflection_end = center + reflection * normal_length
            
            vertices = [center, reflection_end]
            
            gpu.state.depth_test_set('LESS_EQUAL')
            batch = batch_for_shader(shader_3d, 'LINES', {"pos": vertices})
            shader_3d.uniform_float("color", (*THEME_COLOR, 0.5))
            batch.draw(shader_3d)

    # Restore GPU state
    gpu.state.blend_set('NONE')
    gpu.state.depth_test_set('NONE')

def cleanup_drawing(self, context):
    if self._draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(self._draw_handle, 'WINDOW')
        self._draw_handle = None
        # Force a redraw of all 3D viewports
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

def draw_raycast_pattern(context, center_2d, pattern, hit=True):
    """Draw the raycast sampling pattern in the viewport for debugging."""
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    shader.bind()
    gpu.state.blend_set('ALPHA')
    
    # Colors for hit/miss visualization
    hit_color = (0.2, 0.8, 0.2, 0.5)  # Green for hits
    miss_color = (0.8, 0.2, 0.2, 0.5)  # Red for misses
    
    # Draw center point larger
    vertices = []
    center_size = 4.0
    vertices.extend([
        (center_2d[0] - center_size, center_2d[1] - center_size),
        (center_2d[0] + center_size, center_2d[1] - center_size),
        (center_2d[0] + center_size, center_2d[1] + center_size),
        (center_2d[0] - center_size, center_2d[1] + center_size)
    ])
    
    shader.uniform_float("color", hit_color if hit else miss_color)
    batch = batch_for_shader(shader, 'LINE_LOOP', {"pos": vertices})
    batch.draw(shader)
    
    # Draw sample points
    point_size = 2.0
    for dx, dy in pattern:
        x = center_2d[0] + dx
        y = center_2d[1] + dy
        vertices = [
            (x - point_size, y - point_size),
            (x + point_size, y - point_size),
            (x + point_size, y + point_size),
            (x - point_size, y + point_size)
        ]
        batch = batch_for_shader(shader, 'LINE_LOOP', {"pos": vertices})
        batch.draw(shader)
    
    # Draw circles connecting the points
    for circle_idx in range(3):  # We have 3 circles
        circle_points = []
        radius = pattern[1 + circle_idx * 12][0]  # Get radius from first point of each circle
        segments = 32
        for i in range(segments + 1):
            angle = 2 * math.pi * i / segments
            x = center_2d[0] + radius * math.cos(angle)
            y = center_2d[1] + radius * math.sin(angle)
            circle_points.append((x, y))
        
        shader.uniform_float("color", (0.4, 0.6, 0.8, 0.3))  # Light blue for circles
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": circle_points})
        batch.draw(shader)
    
    gpu.state.blend_set('NONE') 

def draw_help_hud(context, mode, light_type, position='BOTTOM_RIGHT', alpha=0.9, is_paused=False, show_help=True, shift_pressed=False):
    """Draw help HUD with shortcuts and controls."""
    from . import help_text
    from .viewport_positioning import get_n_panel_width
    
    # Get formatted help text
    help_lines = help_text.get_formatted_help(context, mode, light_type, is_paused, shift_pressed)
    if not help_lines:
        return
        
    # Set up font drawing
    font_id = 0
    custom_font_id = font_manager.get_font_id()
    font_size = get_ui_scale_font_size()
    base_font_size = font_size
    
    def calculate_height(lines):
        """Calculate total height needed for given lines"""
        height = 0
        for line in lines:
            if line:
                height += line_height
                if line.startswith("───"):
                    height += section_spacing - line_height
        return height
    
    def remove_section(lines, section_name):
        """Remove a section from lines"""
        filtered_lines = []
        skip_section = False
        for line in lines:
            if line and line.startswith("───"):
                if section_name in line:
                    skip_section = True
                else:
                    skip_section = False
                    filtered_lines.append(line)
            elif not skip_section:
                filtered_lines.append(line)
        return filtered_lines
    
    # Calculate dimensions with refined spacing
    max_width = 0
    line_height = int(font_size * 1.6)  # Standard line height for Atkinson
    section_spacing = int(font_size * 1.8)  # Standard section spacing
    padding_y = int(18 * (font_size / 12))  # Increased padding for larger text
    
    # Initialize column widths
    shortcut_column_width = 0
    description_column_width = 0
    
    # Get available height and width
    available_height = context.region.height
    available_width = context.region.width
    
    # Calculate initial total height and measure text dimensions in one pass
    total_height = 0
    working_lines = help_lines.copy()
    
    # First check if we need to remove sections
    temp_height = calculate_height(working_lines)
    required_height = temp_height + (padding_y * 2.5)
    
    if required_height > available_height:
        # Try removing Basic Controls
        working_lines = remove_section(working_lines, "Basic Controls")
        temp_height = calculate_height(working_lines)
        required_height = temp_height + (padding_y * 2.5)
        
        if required_height > available_height:
            # Try removing Light Linking
            working_lines = remove_section(working_lines, "Light Linking")
            temp_height = calculate_height(working_lines)
            required_height = temp_height + (padding_y * 2.5)
            
            if required_height > available_height:
                # Try removing Adjustments
                working_lines = remove_section(working_lines, "Adjustments")
                temp_height = calculate_height(working_lines)
                required_height = temp_height + (padding_y * 2.5)
    
    # Now measure dimensions with final set of lines
    for line in working_lines:
        if line:  # Skip empty lines in measurement
            if line.startswith("───"):
                blf.size(font_id, int(font_size * 0.75))  # Reduced from 0.85 to 0.75
                text_width, _ = blf.dimensions(font_id, line)
                max_width = max(max_width, text_width)
            else:
                if "|" in line:  # It's a shortcut line
                    key, description = line.split("|", 1)
                    key = key.strip()
                    description = description.strip()
                    
                    # Use custom font for shortcut width measurement
                    if bpy.app.version < (3, 0, 0):
                        blf.size(custom_font_id, font_size, 72)  # For Blender 2.x
                    else:
                        blf.size(custom_font_id, font_size)  # For Blender 3.x+
                    key_width, _ = blf.dimensions(custom_font_id, key)
                    
                    # Use regular font for description width measurement
                    if bpy.app.version < (3, 0, 0):
                        blf.size(font_id, font_size, 72)  # For Blender 2.x
                    else:
                        blf.size(font_id, font_size)  # For Blender 3.x+
                    desc_width, _ = blf.dimensions(font_id, description)
                    
                    shortcut_column_width = max(shortcut_column_width, key_width)
                    description_column_width = max(description_column_width, desc_width)
            
            total_height += line_height
            if line.startswith("───"):
                total_height += section_spacing - line_height  # Adjust for section spacing
    
    help_lines = working_lines
    
    # Add minimal padding
    padding_x = int(24 * (font_size / 12))  # Increased horizontal padding
    
    # Calculate spacing between columns - at least 1x font size or 8% of shortcut width, whichever is larger
    min_spacing = int(font_size * 1.0)  # Reduced from 3.0 to 1.0
    spacing_based_on_width = int(shortcut_column_width * 0.08)  # Reduced from 0.25 to 0.08
    description_spacing = max(min_spacing, spacing_based_on_width)
    
    # Calculate total width needed with proper spacing
    total_width = shortcut_column_width + description_spacing + description_column_width + (padding_x * 2)
    max_width = max(max_width, total_width)

    # If total width is too large, reduce font size
    if total_width > available_width * 0.95:  # Leave 5% margin
        scale_factor = (available_width * 0.95) / total_width
        font_size = int(font_size * scale_factor)
        base_font_size = font_size
        # Recalculate all dimensions with new font size
        return draw_help_hud(context, mode, light_type, position, alpha, is_paused, show_help, shift_pressed)
    
    # Calculate position based on viewport
    region = context.region
    if position == 'BOTTOM_RIGHT':
        x = region.width - max_width - padding_x
        # Adjust for N-panel when region overlap is enabled
        if context.preferences.system.use_region_overlap:
            x -= get_n_panel_width(context)
        y = 0  # Remove bottom padding
    elif position == 'BOTTOM_LEFT':
        x = padding_x
        y = 0  # Remove bottom padding
    else:
        x = region.width - max_width - padding_x
        # Also adjust for default case (fallback to BOTTOM_RIGHT behavior)
        if context.preferences.system.use_region_overlap:
            x -= get_n_panel_width(context)
        y = 0  # Remove bottom padding
    
    # Background dimensions
    bg_width = max_width + padding_x
    bg_height = total_height + (padding_y * 2.5)  # Increased bottom padding
    
    # Calculate slide offset based on show_help state and alpha
    slide_amount = bg_height - (padding_y * 3.5)  # Leave just enough space for one line
    
    if show_help:
        # When help is shown, panel should slide up from hidden to shown
        y = -slide_amount + (slide_amount * alpha)
        
        # Draw background with GPU shader
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        shader.bind()
        gpu.state.blend_set('ALPHA')
        
        # Create rounded rectangle for background
        corner_radius = min(bg_height * 0.05, 12.0)  # Increased corner radius
        vertices = create_superellipse_vertices(x, y, bg_width, bg_height, corner_radius)
        
        # Draw frosted glass background with alpha fade
        shader.uniform_float("color", (0.12, 0.12, 0.12, 0.75 * alpha))
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})
        batch.draw(shader)
        
        # Draw very subtle border with alpha fade
        shader.uniform_float("color", (1.0, 1.0, 1.0, 0.02 * alpha))
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": vertices})
        batch.draw(shader)
        
        # Update y_offset based on slide position
        y_offset = y + bg_height - padding_y - font_size
        
        # Initialize last_was_header before drawing text content
        last_was_header = False
        
        # Draw text content
        for line in help_lines:
            if not line:  # Skip empty lines
                y_offset -= line_height * 0.3
                continue
                
            if line.startswith("───"):  # Section header
                if not last_was_header:
                    y_offset -= section_spacing - line_height  # Adjust for section spacing
                
                # Draw header text
                header_font_size = int(base_font_size * 0.75)  # Reduced from 0.85 to 0.75
                compat_font_size = get_font_size()
                if compat_font_size > 0:
                    blf.size(font_id, header_font_size, 72)  # For Blender 2.x
                else:
                    blf.size(font_id, header_font_size)  # For Blender 3.x+
                header_text = "".join([c + "\u200A" for c in line[4:-4].upper()]).rstrip()  # Using hair space (U+200A)
                
                # Draw header text with same color as descriptions
                blf.color(font_id, 0.7, 0.7, 0.7, alpha)
                blf.position(font_id, x + padding_x, y_offset, 0)
                blf.draw(font_id, header_text)
                
                last_was_header = True
            else:
                # Split line into key and description
                if "|" in line:  # It's a shortcut line
                    key, description = line.split("|", 1)
                    key = key.strip()
                    description = description.strip()
                    
                    # Draw key with simple text, no styling
                    if bpy.app.version < (3, 0, 0):
                        blf.size(font_id, base_font_size, 72)  # For Blender 2.x
                    else:
                        blf.size(font_id, base_font_size)  # For Blender 3.x+
                    
                    # Draw key text aligned to the left
                    current_x = x + padding_x
                    # Use our custom font
                    if bpy.app.version < (3, 0, 0):
                        blf.size(custom_font_id, base_font_size, 72)  # For Blender 2.x
                    else:
                        blf.size(custom_font_id, base_font_size)  # For Blender 3.x+
                    blf.color(custom_font_id, 0.95, 0.95, 0.95, alpha)
                    blf.position(custom_font_id, current_x, y_offset, 0)
                    blf.draw(custom_font_id, key)
                    
                    # Draw description aligned after the shortcut column with fixed spacing
                    description_x = x + padding_x + shortcut_column_width + description_spacing
                    blf.position(font_id, description_x, y_offset, 0)
                    
                    # Check if this is a mode line (indicated by the arrow)
                    is_current_mode = description.startswith("→")
                    if is_current_mode:
                        # Brighter color for current mode
                        blf.color(font_id, 1.0, 1.0, 1.0, alpha)
                    else:
                        # Dimmer color for other modes
                        blf.color(font_id, 0.7, 0.7, 0.7, alpha)
                    
                    blf.draw(font_id, description)
                
                last_was_header = False
                
            y_offset -= line_height
    else:
        # When help is hidden, show minimal hint text
        mode_text = "Controls "
        key_text = "[Q]"
        
        # Calculate text dimensions
        compat_font_size = get_font_size()
        if compat_font_size > 0:
            blf.size(font_id, base_font_size, 72)  # For Blender 2.x
        else:
            blf.size(font_id, base_font_size)  # For Blender 3.x+
        mode_width, text_height = blf.dimensions(font_id, mode_text)
        
        # Fixed position at bottom right
        x = region.width - (mode_width + padding_x * 2 + blf.dimensions(custom_font_id, key_text)[0])
        # Adjust for N-panel when region overlap is enabled
        if context.preferences.system.use_region_overlap:
            x -= get_n_panel_width(context)
        y = padding_y
        
        # Draw mode text
        blf.color(font_id, 0.7, 0.7, 0.7, 1.0)
        blf.position(font_id, x, y, 0)
        blf.draw(font_id, mode_text)
        
        # Draw [Q] with custom monospaced font
        if bpy.app.version < (3, 0, 0):
            blf.size(custom_font_id, base_font_size, 72)  # For Blender 2.x
        else:
            blf.size(custom_font_id, base_font_size)  # For Blender 3.x+
        blf.color(custom_font_id, 0.95, 0.95, 0.95, 1.0)
        blf.position(custom_font_id, x + mode_width, y, 0)
        blf.draw(custom_font_id, key_text)

    gpu.state.blend_set('NONE')


def draw_viewport_border(context, mode, is_paused=False):
    """Draw a simple feathered border using Blender's native selection color.

    Args:
        context: Blender context
        mode: Current mode (unused - uses theme color)
        is_paused: Whether positioning is paused
    """
    region = context.region
    if not region:
        return

    # Simple border settings
    BORDER_WIDTH = 8.0  # Width of the feathered border
    FEATHER_STEPS = 4   # Number of alpha gradient steps

    # Get Blender's native selection color from theme
    theme = context.preferences.themes[0]
    selection_color = theme.view_3d.object_active
    base_color = (selection_color[0], selection_color[1], selection_color[2])

    # Adjust opacity based on state
    max_opacity = 0.3 if not is_paused else 0.1

    # Setup GPU
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')

    width = region.width
    height = region.height

    shader.bind()

    # Draw feathered border as multiple strips with decreasing opacity
    for step in range(FEATHER_STEPS):
        # Calculate alpha for this step (stronger at edge, fading inward)
        alpha_factor = (FEATHER_STEPS - step) / FEATHER_STEPS
        alpha = max_opacity * alpha_factor
        color = (*base_color, alpha)

        # Calculate border position for this step
        border_offset = step * (BORDER_WIDTH / FEATHER_STEPS)

        shader.uniform_float("color", color)

        # Top border
        vertices = [
            (border_offset, height - border_offset),
            (width - border_offset, height - border_offset),
            (width - border_offset, height - border_offset - (BORDER_WIDTH / FEATHER_STEPS)),
            (border_offset, height - border_offset - (BORDER_WIDTH / FEATHER_STEPS))
        ]
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})
        batch.draw(shader)

        # Bottom border
        vertices = [
            (border_offset, border_offset + (BORDER_WIDTH / FEATHER_STEPS)),
            (width - border_offset, border_offset + (BORDER_WIDTH / FEATHER_STEPS)),
            (width - border_offset, border_offset),
            (border_offset, border_offset)
        ]
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})
        batch.draw(shader)

        # Left border
        vertices = [
            (border_offset, border_offset),
            (border_offset + (BORDER_WIDTH / FEATHER_STEPS), border_offset),
            (border_offset + (BORDER_WIDTH / FEATHER_STEPS), height - border_offset),
            (border_offset, height - border_offset)
        ]
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})
        batch.draw(shader)

        # Right border
        vertices = [
            (width - border_offset - (BORDER_WIDTH / FEATHER_STEPS), border_offset),
            (width - border_offset, border_offset),
            (width - border_offset, height - border_offset),
            (width - border_offset - (BORDER_WIDTH / FEATHER_STEPS), height - border_offset)
        ]
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})
        batch.draw(shader)

    gpu.state.blend_set('NONE') 