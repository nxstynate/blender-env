import bpy
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d, region_2d_to_location_3d
from mathutils import Vector, Quaternion
import math
import gpu
from gpu_extras.batch import batch_for_shader
import time

# Global variables to store drawing state
_draw_handle = None
_draw_data = None
_adaptive_scaler = None
_last_mouse_pos = None
_last_time = None
_visualization_enabled = False  # New global to control visualization

class AdaptiveScaler:
    def __init__(self):
        self.moving_average_window = []  # For velocity smoothing
        self.ma_window_size = 30  # Moving average window size
        self.min_scale = 0.05
        self.default_radius = 1.0
        self.last_scale = None
        
    def calculate_radius(self, base_radius, current_pos, last_pos, time_delta):
        """
        Calculate pattern radius based on mouse movement velocity using adaptive thresholds.
        """
        if last_pos is None or time_delta <= 0:
            self.last_scale = self.default_radius
            return base_radius * self.default_radius
            
        # Calculate raw velocity
        raw_velocity = (current_pos - last_pos).length / time_delta
        
        # Update moving average window
        self.moving_average_window.append(raw_velocity)
        if len(self.moving_average_window) > self.ma_window_size:
            self.moving_average_window.pop(0)
            
        # Calculate moving average
        if len(self.moving_average_window) > 0:
            velocity = sum(self.moving_average_window) / len(self.moving_average_window)
        else:
            velocity = raw_velocity
            
        # Use default radius until we have enough samples
        if len(self.moving_average_window) < 3:
            self.last_scale = self.default_radius
            return base_radius * self.default_radius
            
        # Simple fixed thresholds
        slow_threshold = 7.0  # Very slow movement
        fast_threshold = 50.0  # Definitely fast movement
        
        # Simple linear scale calculation
        if velocity <= slow_threshold:
            scale = self.min_scale
        elif velocity >= fast_threshold:
            scale = 1.0
        else:
            # Linear interpolation
            t = (velocity - slow_threshold) / (fast_threshold - slow_threshold)
            scale = self.min_scale + (1.0 - self.min_scale) * t
        
        self.last_scale = scale
        # print(f"Raw vel: {raw_velocity:.1f}, Avg vel: {velocity:.1f}, Scale: {scale:.2f}")
        return base_radius * scale

def update_mouse_data(context, event):
    """Update mouse position and timing data for velocity calculation"""
    global _last_mouse_pos, _last_time, _adaptive_scaler
    
    # Define base radius at the start
    base_radius = 75.0  # Default base radius
    
    current_time = time.time()
    current_pos = Vector((event.mouse_x, event.mouse_y))
    
    if _adaptive_scaler is None:
        _adaptive_scaler = AdaptiveScaler()
        # print("Created new AdaptiveScaler")
    
    if _last_mouse_pos is None:
        _last_mouse_pos = current_pos
        _last_time = current_time
        # print("Initialized mouse position tracking")
        return base_radius
        
    time_delta = current_time - _last_time
    
    # Calculate new radius
    new_radius = _adaptive_scaler.calculate_radius(base_radius, current_pos, _last_mouse_pos, time_delta)
    
    # Update stored values
    _last_mouse_pos = current_pos
    _last_time = current_time
    
    return new_radius

def draw_callback_2d(context):
    """Callback for drawing the raycast pattern"""
    if _draw_data is None:
        return
        
    center_2d, pattern, hit = _draw_data
    draw_raycast_pattern(context, center_2d, pattern, hit)

def start_drawing():
    """Start the drawing system"""
    global _draw_handle
    if _draw_handle is None:
        # Add the draw handler
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_2d, (bpy.context,), 'WINDOW', 'POST_PIXEL'
        )
        
def stop_drawing():
    """Stop the drawing system"""
    global _draw_handle
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
        _draw_handle = None

def update_visualization(center_2d, pattern, hit):
    """Update the visualization data"""
    global _draw_data
    _draw_data = (center_2d, pattern, hit)
    # Force a redraw
    for area in bpy.context.screen.areas:
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
    
    gpu.state.blend_set('NONE')

def generate_sample_pattern(radius=75.0, view_distance=None, is_ortho=False):
    """
    Generate a density-weighted sunflower (Vogel spiral) sampling pattern.
    Points are distributed in a spiral pattern with decreasing density from center to edge.
    Radius adapts to view distance if provided (in perspective mode).
    """
    # Use the provided adaptive radius directly, only adjust for view distance if needed
    if view_distance is not None and not is_ortho:
        # Scale the adaptive radius based on view distance
        view_scale = max(0.2, min(1.0, 1.0 - (view_distance * 0.05)))
        radius = radius * view_scale
    
    # print(f"Final pattern radius: {radius:.1f}")  # Debug print
    
    # Start with center point
    samples = [(0, 0)]
    
    # Number of points 
    num_points = 19*2
    
    # Golden angle in radians
    golden_angle = math.pi * (3 - math.sqrt(5))
    
    # Generate points
    for i in range(1, num_points):
        # Calculate distance from center with non-linear spacing
        # This creates gradually increasing gaps between points
        density_falloff = 1.5  # Adjust this value to control density falloff (1.0 = linear, >1.0 = faster falloff)
        distance_factor = (i / (num_points - 1)) ** density_falloff
        r = radius * distance_factor
        
        # Calculate angle using golden angle
        theta = i * golden_angle
        
        # Convert to Cartesian coordinates
        x = r * math.cos(theta)
        y = r * math.sin(theta)
        samples.append((x, y))
    
    return samples

def slerp_normals(normals, previous_normal=None, smoothing_factor=0.3):
    """
    Perform spherical linear interpolation on a list of normals with temporal smoothing.
    Uses quaternions for stable interpolation of multiple directions.
    
    Args:
        normals: List of current normal vectors
        previous_normal: The previous frame's smoothed normal (if any)
        smoothing_factor: Factor between 0 and 1, higher means more responsive (less smoothing)
    """
    if not normals:
        return Vector((0, 0, 1))
    if len(normals) == 1 and previous_normal is None:
        return normals[0].normalized()
        
    # First do spatial SLERP on current normals
    up = Vector((0, 0, 1))
    quats = []
    for normal in normals:
        # Skip zero vectors
        if normal.length < 0.0001:
            continue
            
        # Get rotation axis and angle
        normal = normal.normalized()
        axis = up.cross(normal)
        if axis.length < 0.0001:  # Vectors are parallel
            if normal.dot(up) > 0:
                quats.append(Quaternion())  # Identity quaternion
            else:
                quats.append(Quaternion((1, 0, 0), math.pi))  # 180° rotation around X
            continue
            
        angle = up.angle(normal)
        quats.append(Quaternion(axis.normalized(), angle))
    
    if not quats:
        return Vector((0, 0, 1))
        
    # Average the quaternions for spatial smoothing
    result = Quaternion()
    for quat in quats:
        # Ensure we're interpolating along the shortest path
        if result.dot(quat) < 0:
            result += -quat
        else:
            result += quat
            
    result.normalize()
    current_normal = (result @ up).normalized()
    
    # Apply temporal smoothing if we have a previous normal
    if previous_normal is not None:
        # Convert previous normal to quaternion (same process as above)
        prev_axis = up.cross(previous_normal)
        if prev_axis.length < 0.0001:
            prev_quat = Quaternion() if previous_normal.dot(up) > 0 else Quaternion((1, 0, 0), math.pi)
        else:
            prev_angle = up.angle(previous_normal)
            prev_quat = Quaternion(prev_axis.normalized(), prev_angle)
            
        # Convert current normal to quaternion
        curr_axis = up.cross(current_normal)
        if curr_axis.length < 0.0001:
            curr_quat = Quaternion() if current_normal.dot(up) > 0 else Quaternion((1, 0, 0), math.pi)
        else:
            curr_angle = up.angle(current_normal)
            curr_quat = Quaternion(curr_axis.normalized(), curr_angle)
            
        # Perform spherical linear interpolation between previous and current
        smoothed_quat = prev_quat.slerp(curr_quat, smoothing_factor)
        return (smoothed_quat @ up).normalized()
        
    return current_normal

def lerp_normals(normals, previous_normal=None, smoothing_factor=0.2):
    """
    Perform linear interpolation on a list of normals with temporal smoothing.
    Simple weighted average approach for comparison with SLERP.
    
    Args:
        normals: List of current normal vectors
        previous_normal: The previous frame's smoothed normal (if any)
        smoothing_factor: Factor between 0 and 1, higher means more responsive (less smoothing)
    """
    if not normals:
        return Vector((0, 0, 1))
    if len(normals) == 1 and previous_normal is None:
        return normals[0].normalized()
    
    # First do spatial averaging of current normals
    current_normal = Vector((0, 0, 0))
    for normal in normals:
        if normal.length < 0.0001:  # Skip zero vectors
            continue
        current_normal += normal.normalized()
    
    if current_normal.length < 0.0001:
        return Vector((0, 0, 1))
    
    current_normal.normalize()
    
    # Apply temporal smoothing if we have a previous normal
    if previous_normal is not None:
        # Linear interpolation between previous and current normal
        smoothed_normal = previous_normal.lerp(current_normal, smoothing_factor)
        return smoothed_normal.normalized()
    
    return current_normal

def raycast_from_coords(context, coord_x, coord_y, region, rv3d):
    """
    Perform a single raycast from given coordinates.
    Returns (success, location, normal).
    """
    # Detect if we're in orthographic camera view
    is_ortho_camera = (rv3d.view_perspective == 'CAMERA' and
                      context.scene.camera.data.type == 'ORTHO')

    # Determine clipping settings based on the view
    if rv3d.view_perspective == 'CAMERA':
        # Use camera clipping settings
        camera = context.scene.camera
        near_clip = camera.data.clip_start
    else:
        # Use viewport clipping settings
        space = context.space_data
        if space.type == 'VIEW_3D':
            near_clip = space.clip_start
        else:
            near_clip = 0.1  # Default fallback

    if is_ortho_camera:
        # Orthographic camera specific handling
        camera_matrix = context.scene.camera.matrix_world
        camera_direction = camera_matrix.to_3x3() @ Vector((0, 0, -1))
        mouse_pos_3d = region_2d_to_location_3d(region, rv3d, (coord_x, coord_y), camera_matrix.translation)
        if mouse_pos_3d is None:
            return False, None, None
        ray_origin = mouse_pos_3d + camera_direction * near_clip
        ray_direction = camera_direction
    else:
        # Regular viewport handling (perspective or ortho)
        ray_origin = region_2d_to_origin_3d(region, rv3d, (coord_x, coord_y))
        ray_direction = region_2d_to_vector_3d(region, rv3d, (coord_x, coord_y))
        if ray_origin is None or ray_direction is None:
            return False, None, None
        ray_origin += ray_direction * near_clip

    success, location, normal, _, _, _ = context.scene.ray_cast(
        depsgraph=context.evaluated_depsgraph_get(),
        origin=ray_origin,
        direction=ray_direction,
        distance=10000.0
    )
    
    return success, location, normal

def enable_visualization(enable=True):
    """Enable or disable the raycast pattern visualization"""
    global _visualization_enabled
    _visualization_enabled = enable
    if not enable:
        stop_drawing()

def single_sample_raycast(context, event):
    """
    Perform single raycast at exact mouse position with no averaging.
    Used for precise mode where exact surface normal is needed.
    Returns (hit_location, hit_normal) if successful, or (None, None) if not.
    
    Args:
        context: Blender context
        event: Mouse event
    """
    region = context.region
    rv3d = context.region_data
    if not region or not rv3d:
        return None, None
    
    # Convert event coords to region coords
    base_x = event.mouse_x - region.x
    base_y = event.mouse_y - region.y
    
    # Perform single raycast at exact mouse position
    success, location, normal = raycast_from_coords(
        context, base_x, base_y, region, rv3d
    )
    
    if success and location is not None and normal is not None:
        return Vector(location), Vector(normal)
    
    return None, None

def multi_sample_raycast(context, event, use_lerp=True):
    """
    Perform multi-sample raycasting around the mouse position.
    Uses adaptive pattern scaling based on mouse movement speed.
    Returns (hit_location, hit_normal) if successful, or (None, None) if not.
    
    Args:
        context: Blender context
        event: Mouse event
        use_lerp: If True, uses linear interpolation instead of SLERP
    """
    # Update pattern radius based on mouse movement
    adaptive_radius = update_mouse_data(context, event)
    
    # Only start drawing system if visualization is enabled
    if _visualization_enabled:
        start_drawing()
    
    region = context.region
    rv3d = context.region_data
    if not region or not rv3d:
        return None, None
    
    # Convert event coords to region coords
    base_x = event.mouse_x - region.x
    base_y = event.mouse_y - region.y
    
    # First, get the center hit point (where user is pointing)
    center_success, center_location, center_normal = raycast_from_coords(
        context, base_x, base_y, region, rv3d
    )
    
    # Calculate view distance for adaptive sampling (only in perspective mode)
    view_distance = None
    is_ortho = rv3d.is_perspective == False
    if center_success and center_location is not None and not is_ortho:
        view_matrix = rv3d.view_matrix
        view_pos = view_matrix.inverted().translation
        view_distance = (Vector(center_location) - view_pos).length
    
    # Generate sample pattern with adaptive radius
    sample_pattern = generate_sample_pattern(adaptive_radius, view_distance, is_ortho)
    
    # Update the visualization only if enabled
    if _visualization_enabled:
        update_visualization(Vector((base_x, base_y)), sample_pattern, center_success)
    
    if not center_success or center_location is None:
        return None, None
    
    # Get sample positions for normal averaging
    sample_positions = [(base_x + dx, base_y + dy) for dx, dy in sample_pattern]
    
    # Collect normals from successful hits
    normals = []
    if center_normal is not None:
        normals.append(Vector(center_normal))  # Include center normal
    
    # Perform raycasts for each sample point (for normal averaging only)
    for x, y in sample_positions[1:]:  # Skip center point as we already processed it
        success, location, normal = raycast_from_coords(context, x, y, region, rv3d)
        if success and normal is not None:
            normals.append(Vector(normal))
    
    # If we don't have any valid normals, use just the center normal
    if not normals:
        return Vector(center_location), Vector(center_normal)
    
    # Get the previous smoothed normal if it exists
    previous_normal = None
    if hasattr(multi_sample_raycast, "previous_normal"):
        previous_normal = multi_sample_raycast.previous_normal
    
    # Use either LERP or SLERP for normal interpolation with temporal smoothing
    if use_lerp:
        avg_normal = lerp_normals(normals, previous_normal)
    else:
        avg_normal = slerp_normals(normals, previous_normal)
    
    # Store the smoothed normal for next frame
    multi_sample_raycast.previous_normal = avg_normal
    
    return Vector(center_location), avg_normal 