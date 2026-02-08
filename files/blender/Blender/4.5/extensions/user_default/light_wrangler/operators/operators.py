import bpy
import gpu
import blf
import time
import mathutils
from mathutils import Vector, Matrix, Euler
from bpy_extras import view3d_utils
from bpy.props import EnumProperty, FloatProperty, BoolProperty, StringProperty
from ..utils.drawing import draw_orbit_visualization
from ..utils.utils import raycast_from_mouse, hex_to_rgb, hide_viewport_elements, unhide_viewport_elements, find_layer_collection_recursive
from ..utils.raycast import multi_sample_raycast, stop_drawing
from ..utils.drawing import (
    draw_hud_text,
    format_property_text,
    get_property_label,
    calculate_light_shape_dimensions
)
from ..utils.light_linking import (
    is_blender_version_compatible,
    save_linking_state,
    revert_linking_state,
    handle_light_linking,
    
)
import bpy.types
import bpy_extras
import math
import bpy.app
from ..utils.colors import get_color
from .. import ADDON_MODULE_NAME
from ..utils import logger
from ..utils.blender_compat import supports_light_linking, get_preferences_section_name, create_node_tree_driver

last_activation_time = {}

def is_rendering_active(context):
    """Check if active rendering is enabled in any viewport."""
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D' and space.shading.type == 'RENDERED':
                    return True
    return False

def should_setup_custom_keymaps(context):
    """
    Determine if custom keymaps need to be set up.
    Returns True if our custom keymaps are not properly set up in addon keyconfig.
    """

    # Check if our custom keymaps are set up in addon keyconfig
    our_keymaps_active = False
    kc = context.window_manager.keyconfigs.addon
    if kc:
        for km in kc.keymaps:
            if km.space_type == 'VIEW_3D':
                for kmi in km.keymap_items:
                    if (kmi.idname == "lightwrangler.interactive_mode" and
                        kmi.type in {'ONE', 'TWO', 'THREE'} and
                        not kmi.any and not kmi.shift and not kmi.ctrl and not kmi.alt):
                        if kmi.active:
                            our_keymaps_active = True
                            break
                if our_keymaps_active:
                    break

    # We need setup if our custom keymaps aren't set up
    setup_needed = not our_keymaps_active
    return setup_needed

class LIGHTW_OT_InteractiveOperator(bpy.types.Operator):
    """Drag to adjust position"""
    bl_idname = "lightwrangler.interactive_mode"
    bl_label = "Light Wrangler Interactive Mode"
    bl_options = {'UNDO', 'GRAB_CURSOR', 'BLOCKING'}

    mode: EnumProperty(
        items=[
            ('REFLECT', "Reflect", "Position light by reflection angle"),
            ('DIRECT', "Direct", "Position light directly on surface"),
            ('ORBIT', "Orbit", "Orbit light around target point")
        ],
        name="Mode",
        description="Light positioning mode",
        default='DIRECT',
        update=lambda self, context: context.area.tag_redraw() if context.area else None
    )

    current_power: FloatProperty(default=100.0)
    current_size: FloatProperty(default=1.0)
    current_distance: FloatProperty(default=2.0)
    current_z_rotation: FloatProperty(default=0.0)
    
    # New property for pause state
    is_position_paused: BoolProperty(
        name="Position Paused",
        description="Whether light position updates are paused",
        default=False
    )

    # Property to track if tracking removal was confirmed
    tracking_confirmed: BoolProperty(
        name="Tracking Confirmed",
        description="Whether user confirmed tracking removal",
        default=False,
        options={'SKIP_SAVE'}
    )

    @classmethod
    def poll(cls, context):
        """Check if the operator can be called"""
        # Must have an active object that is a light
        if not context.active_object or context.active_object.type != 'LIGHT':
            cls.poll_message_set("Select a light to use this operator")
            return False
            
        # Check if we're in a valid 3D view context
        if context.area.type != 'VIEW_3D':
            cls.poll_message_set("Must be used in 3D View")
            return False
            
        return True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_values = {}
        self.light_object = None
        self._mode = 'DIRECT'
        self.start_mouse_x = 0
        self.start_mouse_y = 0
        self.z_key_pressed = False
        self._draw_handle = None
        self._draw_handle_2d = None
        self._draw_handle_help = None  # Separate handler for help HUD
        self.initial_area = None
        self.initial_region = None
        self._active_property = None
        self.shift_pressed = False
        self.alt_pressed = False
        self.slash_pressed = False  # Add slash key state tracking
        self.ctrl_pressed = False
        self._hovered_property = None
        # HUD tooltip attributes
        self._hover_start_time = None
        self._last_wheel_event_time = None
        self._running_modal = False
        # Track if operator was started with TAB
        self._started_with_tab = False
        # Track if we've received the first event
        self._first_event_received = False
        # Track snapped axis for visual feedback
        self._snapped_axis = None
        self._axis_sign = 1  # Direction along the snapped axis
        # CTRL snap threshold tracking
        self._ctrl_movement_accumulated = 0.0  # Track accumulated mouse movement
        self._ctrl_snap_threshold = 10  # Pixel threshold before snapping activates
        self._ctrl_snap_active = False  # Whether snapping is currently active
        # Light linking state
        self.original_linking_state = None
        self.light = None
        # Help HUD attributes
        self._help_fade_start = None
        self._help_alpha = 1.0
        self._help_fade_duration = 0.1  # Fade duration in seconds
        # Reference values for power adjustment
        self._reference_power = None
        self._reference_distance = None
        # Reference values for size-based power adjustment
        self._reference_size_power = None
        self._reference_size_x = None
        self._reference_size_y = None
        # Track if isolation was done before modal started
        self._was_isolated_before_modal = False
        
        # Track original hide state
        self._original_hide_state = False
        
        # Show help attribute
        self._show_help = True
        
        # Store tracking constraints info
        self.original_tracking_mute_states = []
        # Volume cubes tracking
        self.volume_cubes = []
        self.volume_cubes_visibility = {}

    @classmethod
    def draw_callback_3d(cls, operator, context):
        if operator.light_object:
            # Get the target point (either orbit center or surface hit point)
            if operator.mode == 'ORBIT':
                center = Vector(operator.light_object.get("lw_orbit_center", (0, 0, 0)))
            else:
                # For REFLECT and DIRECT modes, use the light's target point
                direction = -(operator.light_object.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0)))
                origin = operator.light_object.location
                success, location, normal, _, _, _ = context.scene.ray_cast(
                    depsgraph=context.evaluated_depsgraph_get(),
                    origin=origin,
                    direction=direction,
                    distance=10000.0
                )
                if success:
                    center = location
                else:
                    # Fallback to light's position if no hit point
                    center = operator.light_object.location

            draw_orbit_visualization(context, center, operator.light_object.location, operator.current_z_rotation, operator)

    @classmethod
    def draw_callback_help(cls, operator, context):
        """Dedicated callback for help HUD to prevent interference with other drawings."""
        if (not hasattr(operator, 'initial_area') or 
            context.area != operator.initial_area or 
            not hasattr(operator, 'initial_region') or 
            context.region != operator.initial_region):
            return
            
        # Draw help HUD if enabled
        if hasattr(operator, '_help_alpha'):
            from ..utils.drawing import draw_help_hud
            draw_help_hud(
                context,
                operator.mode,
                operator.light_object.data.type,
                alpha=operator._help_alpha,
                is_paused=operator.is_position_paused,
                show_help=operator._show_help,
                shift_pressed=operator.shift_pressed  # Pass the shift state
            )

    def get_hud_position(self, context):
        """Get the 2D position to draw HUD for any mode"""
        region = context.region
        rv3d = context.region_data
        if not (region and rv3d):
            return None

        if self.mode == 'ORBIT':
            # For orbit mode, use the orbit center
            center = Vector(self.light_object.get("lw_orbit_center", (0, 0, 0)))
            return bpy_extras.view3d_utils.location_3d_to_region_2d(region, rv3d, center)
        else:
            # For REFLECT and DIRECT modes, use the light's target point
            direction = -(self.light_object.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0)))
            origin = self.light_object.location
            success, location, normal, _, _, _ = context.scene.ray_cast(
                depsgraph=context.evaluated_depsgraph_get(),
                origin=origin,
                direction=direction,
                distance=10000.0
            )
            if success:
                return bpy_extras.view3d_utils.location_3d_to_region_2d(region, rv3d, location)
            else:
                # Fallback to light's position if no hit point
                return bpy_extras.view3d_utils.location_3d_to_region_2d(region, rv3d, self.light_object.location)

    @classmethod
    def draw_callback_2d(cls, operator, context):
        """Draw 2D overlay elements"""
        # Validate that we're in the expected viewport context
        if (not hasattr(operator, 'initial_area') or
            context.area != operator.initial_area or
            not hasattr(operator, 'initial_region') or
            context.region != operator.initial_region):
            return

        # Draw Apple-style viewport border (always on, no settings)
        from ..utils.drawing import draw_viewport_border
        draw_viewport_border(
            context,
            operator.mode,
            is_paused=operator.is_position_paused
        )

        # Show either active property value or hovered property label
        if hasattr(operator, '_active_property') and operator._active_property:
            center_2d = operator.get_hud_position(context)
            
            if center_2d:
                text = format_property_text(operator, operator._active_property)
                if text:
                    draw_hud_text(context, center_2d, text)
                
            # Reset hover start time when showing active property
            operator._hover_start_time = None
            
        elif hasattr(operator, '_hovered_property') and operator._hovered_property:
            # Tooltip delay logic
            current_time = time.time()
            tooltip_delay = 0.5  # Half second delay
            
            # Initialize hover start time if needed
            if operator._hover_start_time is None:
                operator._hover_start_time = current_time
            
            # Don't show tooltip if we recently had wheel activity
            if operator._last_wheel_event_time is not None:
                time_since_wheel = current_time - operator._last_wheel_event_time
                if time_since_wheel < tooltip_delay:
                    bpy.app.timers.register(operator.force_redraw, first_interval=(tooltip_delay - time_since_wheel))
                    return
            
            # Check if enough time has passed to show tooltip
            if (current_time - operator._hover_start_time) < tooltip_delay:
                bpy.app.timers.register(operator.force_redraw, first_interval=(tooltip_delay - (current_time - operator._hover_start_time)))
                return
            
            center_2d = operator.get_hud_position(context)
            
            if center_2d:
                # Show property label with light type
                label = get_property_label(operator._hovered_property, operator.light_object.data.type)
                if label:
                    # For SIZE_X and SIZE_Y, show only the label
                    if operator._hovered_property in {'SIZE_X', 'SIZE_Y'}:
                        draw_hud_text(context, center_2d, label)
                    else:
                        # For other properties, get the current value and show both label and value
                        value = format_property_text(operator, operator._hovered_property)
                        if value:
                            # Display both label and value
                            combined_text = f"{label}: {value}"
                            draw_hud_text(context, center_2d, combined_text)
                        else:
                            # Fallback to just the label if value formatting fails
                            draw_hud_text(context, center_2d, label)

    def apply_z_rotation(self, direction, z_rotation):
        rot_quat = direction.to_track_quat('-Z', 'Y')
        base_rot = rot_quat.to_euler()
        z_mat = Matrix.Rotation(z_rotation, 3, 'Z')
        final_rot = base_rot.to_matrix() @ z_mat
        return final_rot.to_euler()

    def correct_light_position(self, position, context):
        """Ensure light doesn't drop below the floor by checking its actual dimensions and rotation."""
        # Skip floor correction if we're hitting from significantly below (more than 45 degrees down)
        if hasattr(self, '_last_hit_point') and hasattr(self, '_last_hit_normal'):
            if self._last_hit_normal.z < -0.707:  # cos(45 degrees) ≈ 0.707
                return position
        
        light_data = self.light_object.data
        
        # Calculate minimum height based on actual light dimensions and rotation
        if light_data.type == 'AREA':
            if light_data.shape in {'RECTANGLE', 'ELLIPSE'}:
                width = light_data.size
                height = light_data.size_y
            else:  # SQUARE or DISK
                width = height = light_data.size
                
            # Get the light's rotation matrix
            rot_mat = self.light_object.rotation_euler.to_matrix()
            
            # Calculate the corners of the light in local space
            corners = [
                Vector((-width/2, -height/2, 0)),
                Vector((width/2, -height/2, 0)),
                Vector((width/2, height/2, 0)),
                Vector((-width/2, height/2, 0))
            ]
            
            # Transform corners by rotation and find lowest point
            min_height = 0.1  # Minimum base height
            for corner in corners:
                # Transform corner by light's rotation
                rotated_corner = rot_mat @ corner
                min_height = max(min_height, abs(rotated_corner.z))
                
        elif light_data.type == 'SPOT':
            # Use spot size to calculate the radius at the current distance
            radius = math.tan(light_data.spot_size * 0.5) * self.current_distance
            min_height = max(0.1, radius)
        elif light_data.type == 'POINT':
            min_height = max(0.1, light_data.shadow_soft_size * 0.5)
        else:  # SUN
            min_height = 0.0  # Sun lights don't need height correction
        
        # Cast ray downward from actual position to find floor
        ray_origin = position + Vector((0, 0, 0.5))  # Small offset to avoid surface precision issues
        ray_direction = Vector((0, 0, -1))  # Straight down
        
        success, location, normal, _, _, _ = context.scene.ray_cast(
            depsgraph=context.evaluated_depsgraph_get(),
            origin=ray_origin,
            direction=ray_direction,
            distance=1000.0  # Long enough to catch floor far below
        )
        
        if success:
            floor_height = location.z
            absolute_min_height = floor_height + min_height
            
            # If position is below minimum height, raise it while preserving aim direction
            if position.z < absolute_min_height:
                # Store original aim point before adjustment
                if self.mode in {'REFLECT', 'DIRECT'}:
                    direction = -(self.light_object.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0)))
                    success, aim_point, normal, _, _, _ = context.scene.ray_cast(
                        depsgraph=context.evaluated_depsgraph_get(),
                        origin=position,
                        direction=direction,
                        distance=10000.0
                    )
                    if not success:
                        aim_point = position + direction * self.current_distance
                else:
                    aim_point = None
                    
                # Adjust height
                adjusted_position = position.copy()
                adjusted_position.z = absolute_min_height
                
                # Preserve aim point if we have one
                if aim_point is not None:
                    direction = (aim_point - adjusted_position).normalized()
                    self.light_object.rotation_euler = self.apply_z_rotation(direction, self.current_z_rotation)
                
                return adjusted_position
        
        # If no floor found or no adjustment needed, return original position
        return position

    def position_light_for_mode(self, hit_loc, hit_normal, context):
        # Store hit info for floor correction logic
        self._last_hit_point = hit_loc
        self._last_hit_normal = hit_normal
        
        # Store target point for gizmo positioning
        self.light_object["target"] = tuple(hit_loc)

        region_data = context.region_data
        if not region_data:
            return

        view_matrix_inv = region_data.view_matrix.inverted()
        view_pos = view_matrix_inv.translation
        current_offset = self.light_object.get("lw_last_offset", 2.0)

        # Detect if we're in orthographic camera view
        is_ortho_camera = (region_data.view_perspective == 'CAMERA' and
                          context.scene.camera.data.type == 'ORTHO')

        if self.mode == 'REFLECT':
            stored_direction = self.light_object.get("lw_current_direction")
            if stored_direction is not None:
                direction = Vector(stored_direction)
                new_position = hit_loc - direction * current_offset
            else:
                if is_ortho_camera:
                    camera_matrix = context.scene.camera.matrix_world
                    view_vector = camera_matrix.to_3x3() @ Vector((0, 0, -1))
                else:
                    if region_data.is_perspective:
                        view_vector = (hit_loc - view_pos).normalized()
                    else:
                        view_vector = region_data.view_rotation @ Vector((0, 0, -1))

                # Calculate reflection
                reflection = view_vector.reflect(hit_normal)
                reflection.normalize()
                new_position = hit_loc + reflection * current_offset

        elif self.mode == 'DIRECT':
            stored_direction = self.light_object.get("lw_current_direction")
            if stored_direction is not None:
                direction = Vector(stored_direction)
                new_position = hit_loc - direction * current_offset
            else:
                new_position = hit_loc + hit_normal * current_offset

        # Correct position to prevent dropping below floor
        new_position = self.correct_light_position(new_position, context)
        self.light_object.location = new_position

        # Update light rotation
        direction = (hit_loc - self.light_object.location).normalized()
        self.light_object.rotation_euler = self.apply_z_rotation(direction, self.current_z_rotation)

    def orbit_light(self, context, event):
        center = Vector(self.light_object.get("lw_orbit_center", (0, 0, 0)))
        # Store target point for gizmo positioning
        self.light_object["target"] = tuple(center)

        if event.ctrl:
            # Calculate mouse movement
            dx = event.mouse_x - self.start_mouse_x
            dy = event.mouse_y - self.start_mouse_y

            # Track accumulated movement for threshold check
            movement = math.sqrt(dx * dx + dy * dy)
            self._ctrl_movement_accumulated += movement

            self.start_mouse_x = event.mouse_x
            self.start_mouse_y = event.mouse_y

            # Get view orientation vectors
            view_matrix = context.region_data.view_matrix
            view_right = Vector(view_matrix[0][:3])
            view_up = Vector(view_matrix[1][:3])

            # Base movement speed - increased for snapping mode to make transitions easier
            base_speed = 0.015  # 3x faster than normal orbit for quicker snap transitions

            # Apply orbit sensitivity from preferences
            preferences = context.preferences.addons[ADDON_MODULE_NAME].preferences
            sensitivity = preferences.orbit_sensitivity
            base_speed *= sensitivity

            # Don't apply shift precision when using Ctrl snapping
            # (Shift+Ctrl would be confusing and not useful for axis snapping)

            # Calculate rotation vector based on view orientation
            rotation_vector = (view_right * -dy + view_up * dx) * base_speed

            # Create rotation matrix from axis and angle
            rot_mat = Matrix.Rotation(rotation_vector.length, 4, rotation_vector.normalized())

            # Apply rotation to relative position
            relative_pos = self.light_object.location - center
            relative_pos.rotate(rot_mat)

            # Check if we've exceeded the threshold to activate snapping
            if self._ctrl_movement_accumulated >= self._ctrl_snap_threshold:
                self._ctrl_snap_active = True

            # Only snap if threshold has been exceeded
            if self._ctrl_snap_active:
                # Now snap the rotated position to nearest axis
                distance = relative_pos.length
                snap_mode = preferences.orbit_snap_mode

                if snap_mode == 'WORLD':
                    # Snap to world axes and intermediate positions
                    world_x = Vector((1, 0, 0))
                    world_y = Vector((0, 1, 0))
                    world_z = Vector((0, 0, 1))

                    # Include intermediate positions (45-degree angles between axes)
                    world_xy = (world_x + world_y).normalized()
                    world_xz = (world_x + world_z).normalized()
                    world_yz = (world_y + world_z).normalized()
                    world_xy_neg = (world_x - world_y).normalized()
                    world_xz_neg = (world_x - world_z).normalized()
                    world_yz_neg = (world_y - world_z).normalized()

                    # Calculate alignment with each axis and intermediate position
                    relative_pos_normalized = relative_pos.normalized()
                    alignments = [
                        # Cardinal axes
                        (abs(relative_pos_normalized.dot(world_x)), world_x, 'X'),
                        (abs(relative_pos_normalized.dot(world_y)), world_y, 'Y'),
                        (abs(relative_pos_normalized.dot(world_z)), world_z, 'Z'),
                        # Intermediate positions
                        (abs(relative_pos_normalized.dot(world_xy)), world_xy, 'XY'),
                        (abs(relative_pos_normalized.dot(world_xz)), world_xz, 'XZ'),
                        (abs(relative_pos_normalized.dot(world_yz)), world_yz, 'YZ'),
                        (abs(relative_pos_normalized.dot(world_xy_neg)), world_xy_neg, 'XY-'),
                        (abs(relative_pos_normalized.dot(world_xz_neg)), world_xz_neg, 'XZ-'),
                        (abs(relative_pos_normalized.dot(world_yz_neg)), world_yz_neg, 'YZ-')
                    ]

                    # Find best aligned position
                    alignments.sort(key=lambda x: x[0], reverse=True)
                    best_alignment, best_axis, axis_name = alignments[0]

                    # Snap to that position
                    self._snapped_axis = axis_name
                    axis_sign = math.copysign(1, relative_pos.dot(best_axis))
                    new_pos = center + best_axis * axis_sign * distance
                else:
                    # Snap to view axes and intermediate positions
                    view_forward = Vector(view_matrix[2][:3])

                    # Include intermediate positions (45-degree angles between view axes)
                    view_right_up = (view_right + view_up).normalized()
                    view_right_forward = (view_right + view_forward).normalized()
                    view_up_forward = (view_up + view_forward).normalized()
                    view_right_up_neg = (view_right - view_up).normalized()
                    view_right_forward_neg = (view_right - view_forward).normalized()
                    view_up_forward_neg = (view_up - view_forward).normalized()

                    # Calculate alignment with each view axis and intermediate position
                    relative_pos_normalized = relative_pos.normalized()
                    alignments = [
                        # Cardinal axes
                        (abs(relative_pos_normalized.dot(view_right)), view_right, 'VIEW_RIGHT'),
                        (abs(relative_pos_normalized.dot(view_up)), view_up, 'VIEW_UP'),
                        (abs(relative_pos_normalized.dot(view_forward)), view_forward, 'VIEW_FORWARD'),
                        # Intermediate positions
                        (abs(relative_pos_normalized.dot(view_right_up)), view_right_up, 'VIEW_RU'),
                        (abs(relative_pos_normalized.dot(view_right_forward)), view_right_forward, 'VIEW_RF'),
                        (abs(relative_pos_normalized.dot(view_up_forward)), view_up_forward, 'VIEW_UF'),
                        (abs(relative_pos_normalized.dot(view_right_up_neg)), view_right_up_neg, 'VIEW_RU-'),
                        (abs(relative_pos_normalized.dot(view_right_forward_neg)), view_right_forward_neg, 'VIEW_RF-'),
                        (abs(relative_pos_normalized.dot(view_up_forward_neg)), view_up_forward_neg, 'VIEW_UF-')
                    ]

                    # Find best aligned position
                    alignments.sort(key=lambda x: x[0], reverse=True)
                    best_alignment, best_axis, axis_name = alignments[0]

                    # Snap to that position
                    self._snapped_axis = axis_name
                    axis_sign = math.copysign(1, relative_pos.dot(best_axis))
                    new_pos = center + best_axis * axis_sign * distance

                # Update light position
                self.light_object.location = new_pos

                # Point light at center and maintain z-rotation
                direction = (center - new_pos).normalized()
                self.light_object.rotation_euler = self.apply_z_rotation(direction, self.current_z_rotation)
            else:
                # Threshold not met - apply normal orbit without snapping
                new_pos = center + relative_pos
                self.light_object.location = new_pos

                # Point light at center and maintain z-rotation
                direction = (center - new_pos).normalized()
                self.light_object.rotation_euler = self.apply_z_rotation(direction, self.current_z_rotation)
            
        else:
            # Clear snapped axis when Ctrl is not held
            self._snapped_axis = None
            
            dx = event.mouse_x - self.start_mouse_x
            dy = event.mouse_y - self.start_mouse_y
            
            self.start_mouse_x = event.mouse_x
            self.start_mouse_y = event.mouse_y
            
            # Get view orientation vectors
            view_matrix = context.region_data.view_matrix
            view_right = Vector(view_matrix[0][:3])
            view_up = Vector(view_matrix[1][:3])
            
            # Base movement speed
            base_speed = 0.005
            
            # Apply orbit sensitivity from preferences
            preferences = context.preferences.addons[ADDON_MODULE_NAME].preferences
            sensitivity = preferences.orbit_sensitivity
            base_speed *= sensitivity
            
            # Apply precision factor when shift is held
            if event.shift:
                base_speed *= 0.2  # 5x slower for precise control
            
            # Calculate rotation vector based on view orientation
            rotation_vector = (view_right * -dy + view_up * dx) * base_speed
            
            # Create rotation matrix from axis and angle
            rot_mat = Matrix.Rotation(rotation_vector.length, 4, rotation_vector.normalized())
            
            # Apply rotation to relative position
            relative_pos = self.light_object.location - center
            relative_pos.rotate(rot_mat)
            
            # Update light position
            new_pos = center + relative_pos
            self.light_object.location = new_pos
            
            # Point light at center and maintain z-rotation
            direction = (center - new_pos).normalized()
            self.light_object.rotation_euler = self.apply_z_rotation(direction, self.current_z_rotation)

    def get_current_z_rotation(self):
        """Extract just the roll component of light's current orientation"""
        # Get light's current orientation
        current_rot = self.light_object.rotation_euler.to_matrix()
        
        # Get light's current aim direction
        aim_dir = -(current_rot @ Vector((0.0, 0.0, 1.0)))
        
        # Get current up direction
        up_dir = (current_rot @ Vector((0.0, 1.0, 0.0)))
        
        # Create base rotation (no roll)
        base_rot = aim_dir.to_track_quat('-Z', 'Y').to_matrix()
        base_up = base_rot @ Vector((0.0, 1.0, 0.0))
        
        # Project current up onto plane perpendicular to aim
        up_proj = up_dir - up_dir.dot(aim_dir) * aim_dir
        base_up_proj = base_up - base_up.dot(aim_dir) * aim_dir
        
        # Normalize projections
        if up_proj.length > 0.000001:  # Avoid zero vectors
            up_proj.normalize()
        if base_up_proj.length > 0.000001:
            base_up_proj.normalize()
            
        # Get angle between projections
        return math.atan2(up_proj.cross(base_up_proj).dot(aim_dir), up_proj.dot(base_up_proj))

    def check_camera_view(self, context):
        """Check if we're currently looking through a LensSim camera"""
        return (context.space_data.region_3d.view_perspective == 'CAMERA' 
                and context.scene.camera is not None
                and context.scene.camera.get("lens_sim_cam", False))  # Check lens_sim_cam parameter

    def find_all_lens_sim_materials(self):
        """Find all LensSim materials directly from camera parameters"""
        lens_materials_by_camera = {}
        try:
            # Directly access all objects in the scene and filter by type
            for obj in bpy.context.scene.objects:
                if obj.type == 'CAMERA' and obj.get("lens_sim_cam", False):  # Check lens_sim_cam parameter
                    lens_sim_mat = obj.get("lens_sim_mat")  # Get material directly from camera
                    if lens_sim_mat:
                        lens_materials_by_camera[obj.name] = [lens_sim_mat]
        
            return lens_materials_by_camera
        except Exception as e:
            logger.error(f"Error finding lens sim materials: {str(e)}")
            return {}

    def store_lens_sim_state(self):
        """Store the initial state of all lens simulation previews"""
        try:
            # Check if we're in camera view first
            if not self.check_camera_view(bpy.context):
                self.camera_view_active = False
                return False

            self.camera_view_active = True
            self.lens_sim_states = {}
            
            # Find all materials for all cameras
            materials_by_camera = self.find_all_lens_sim_materials()
            
            for camera_name, materials in materials_by_camera.items():
                self.lens_sim_states[camera_name] = {}
                
                for mat in materials:
                    if mat and mat.node_tree and "LensSim" in mat.node_tree.nodes:
                        lens_sim_node = mat.node_tree.nodes["LensSim"]
                        if "viewport preview enable" in lens_sim_node.inputs:
                            self.lens_sim_states[camera_name][mat.name] = {
                                'preview_state': lens_sim_node.inputs["viewport preview enable"].default_value
                            }
            
            return bool(self.lens_sim_states)
        except Exception as e:
            logger.error(f"Error storing lens sim states: {str(e)}")
            return False

    def set_lens_sim_state(self, value):
        """Set the lens simulation preview state for all materials"""
        try:
            if not hasattr(self, 'camera_view_active') or not self.camera_view_active:
                return False

            if not hasattr(self, 'lens_sim_states'):
                return False

            success = False
            for camera_name, materials in self.lens_sim_states.items():
                for mat_name in materials:
                    mat = bpy.data.materials.get(mat_name)
                    if mat and mat.node_tree and "LensSim" in mat.node_tree.nodes:
                        lens_sim_node = mat.node_tree.nodes["LensSim"]
                        if "viewport preview enable" in lens_sim_node.inputs:
                            lens_sim_node.inputs["viewport preview enable"].default_value = bool(value)
                            success = True
            
            return success
        except Exception as e:
            logger.error(f"Error setting lens sim states: {str(e)}")
            return False

    def restore_lens_sim_state(self):
        """Restore all lens simulation previews to their initial states"""
        try:
            if not hasattr(self, 'camera_view_active') or not self.camera_view_active:
                return False

            if not hasattr(self, 'lens_sim_states'):
                logger.warning("No lens sim states stored to restore")
                return False

            success = False
            for camera_name, materials in self.lens_sim_states.items():
                for mat_name, state in materials.items():
                    mat = bpy.data.materials.get(mat_name)
                    if mat and mat.node_tree and "LensSim" in mat.node_tree.nodes:
                        lens_sim_node = mat.node_tree.nodes["LensSim"]
                        if "viewport preview enable" in lens_sim_node.inputs:
                            lens_sim_node.inputs["viewport preview enable"].default_value = state['preview_state']
                            success = True
            
            return success
        except Exception as e:
            logger.error(f"Error restoring lens sim states: {str(e)}")
            return False


    def create_keyframes(self, context):
        if not context.scene.tool_settings.use_keyframe_insert_auto:
            logger.info("Auto-keying is disabled, skipping keyframe creation")
            return
        
        prefs = context.preferences.edit
        light = self.light
        current_frame = context.scene.frame_current
        key_channels = {channel.upper() for channel in prefs.key_insert_channels}  # Ensure case-insensitivity
        
        logger.debug(f"=== Starting keyframe creation for light: {light.name} ===")
        logger.debug(f"Current frame: {current_frame}")
        logger.debug(f"'Only Insert Available' setting: {prefs.use_keyframe_insert_available}")
        logger.debug(f"Key channels enabled: {key_channels}")
        
        def keyframe_insert_with_prefs(obj, data_path, group=None):
            logger.debug(f"Attempting to insert keyframe:")
            logger.debug(f"- Object: {obj.name}")
            logger.debug(f"- Data path: {data_path}")
            logger.debug(f"- Group: {group}")
            
            if prefs.use_keyframe_insert_available:
                is_animated = (obj.animation_data and obj.animation_data.action and
                            any(fc.data_path == data_path for fc in obj.animation_data.action.fcurves))
                logger.debug(f"Checking if property is already animated: {is_animated}")
                if not is_animated:
                    logger.debug("Property not animated and 'Only Insert Available' is enabled - skipping")
                    return None
                    
            fcurve = obj.keyframe_insert(data_path=data_path, frame=current_frame, group=group)
            if fcurve:
                logger.debug("Keyframe inserted successfully")
                for fc in obj.animation_data.action.fcurves:
                    if fc.data_path == data_path:
                        for kf in fc.keyframe_points:
                            if kf.co[0] == current_frame:
                                kf.interpolation = prefs.keyframe_new_interpolation_type
                                kf.handle_left_type = prefs.keyframe_new_handle_type
                                kf.handle_right_type = prefs.keyframe_new_handle_type
                                logger.debug(f"Applied preferences:")
                                logger.debug(f"- Interpolation: {kf.interpolation}")
                                logger.debug(f"- Handle type: {kf.handle_left_type}")
            else:
                logger.debug("Failed to insert keyframe")
                pass
        
        logger.debug("Inserting transform keyframes...")
        if 'LOCATION' in key_channels:
            logger.debug("Location channel enabled - inserting location keyframe")
            keyframe_insert_with_prefs(light, "location", "Location")
        else:
            logger.debug("Location channel disabled - skipping")
            
        if 'ROTATION' in key_channels:
            logger.debug("Rotation channel enabled - inserting rotation keyframe")
            keyframe_insert_with_prefs(light, "rotation_euler", "Rotation")
        else:
            logger.debug("Rotation channel disabled - skipping")
        
        logger.debug("Inserting light property keyframes...")
        keyframe_insert_with_prefs(light.data, "energy", "Energy")
        
        if light.data.type == "AREA":
            logger.debug("Processing AREA light specific properties...")
            keyframe_insert_with_prefs(light.data, "size", "Light Settings")
            if light.data.shape in {'RECTANGLE', 'ELLIPSE'}:
                logger.debug(f"Light shape is {light.data.shape}, inserting size_y keyframe")
                keyframe_insert_with_prefs(light.data, "size_y", "Light Settings")
            keyframe_insert_with_prefs(light.data, "spread", "Light Settings")
            # Add shape keyframing for area lights
            logger.debug("Inserting shape keyframe")
            keyframe_insert_with_prefs(light.data, "shape", "Light Settings")
        elif light.data.type == "SPOT":
            logger.debug("Processing SPOT light specific properties...")
            keyframe_insert_with_prefs(light.data, "spot_size", "Light Settings")
            keyframe_insert_with_prefs(light.data, "spot_blend", "Light Settings")
        
        logger.debug("=== Keyframe creation completed ===")

    def check_for_tracking(self, context):
        """Check if light has tracking constraints without removing them"""
        light = context.active_object
        if not light or light.type != 'LIGHT':
            return False
        return any(c.type == 'TRACK_TO' and not c.mute for c in light.constraints)

    def clear_tracking_if_present(self, context):
        """Silently disable tracking constraints if present, preserving orientation"""
        light = context.active_object
        if not light or light.type != 'LIGHT':
            return False

        has_tracking = any(c.type == 'TRACK_TO' for c in light.constraints)
        if has_tracking:
            # Store current world matrix to preserve orientation
            final_matrix = light.matrix_world.copy()

            # Store original mute states and disable TRACK_TO constraints
            if not hasattr(self, 'original_tracking_mute_states'):
                self.original_tracking_mute_states = []

            for constraint in light.constraints:
                if constraint.type == 'TRACK_TO':
                    # Store original mute state
                    self.original_tracking_mute_states.append({
                        'name': constraint.name,
                        'was_muted': constraint.mute
                    })
                    # Disable the constraint
                    constraint.mute = True

            # Apply the final transformation back to preserve orientation
            light.matrix_world = final_matrix

            return True
        return False

    def update_status_bar_text(self, context):
        """Update the status bar text based on current state."""
        if not self.light_object:  # Guard against early calls before light_object is set
            return
            
        from ..utils.help_text import format_status_bar_text
        text = format_status_bar_text(
            context,
            self.mode,
            self.light_object.data.type,
            shift_pressed=self.shift_pressed,
            alt_pressed=self.alt_pressed,
            ctrl_pressed=self.ctrl_pressed,
            z_pressed=self.z_key_pressed,
            is_paused=self.is_position_paused,
            precise_mode=self.precise_mode if self.mode in ('REFLECT', 'DIRECT') else False
        )
        context.workspace.status_text_set(text)

    def invoke(self, context, event):
        # print("[OPERATOR] Invoke called")
        # print(f"[OPERATOR] Event type: {event.type}, value: {event.value}")
        # print(f"[OPERATOR] Initial pause state: {self.is_position_paused}")

        # Check if we need to set up custom keymaps
        if should_setup_custom_keymaps(context):
            # Get addon preferences
            prefs = context.preferences.addons[ADDON_MODULE_NAME].preferences

            # Register our mode-switching keymaps
            kc = context.window_manager.keyconfigs.addon
            km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")

            # Check if mode switch keys are enabled in preferences
            register_mode_keys = True
            try:
                prefs = context.preferences.addons[ADDON_MODULE_NAME].preferences
                register_mode_keys = prefs.enable_mode_switch_keys
            except:
                # If we can't get preferences, default to enabled for backward compatibility
                pass

            if register_mode_keys:

                # Register number keys for different modes
                kmi = km.keymap_items.new("lightwrangler.interactive_mode", "ONE", "PRESS")
                kmi.properties.mode = 'REFLECT'

                kmi = km.keymap_items.new("lightwrangler.interactive_mode", "TWO", "PRESS")
                kmi.properties.mode = 'ORBIT'

                kmi = km.keymap_items.new("lightwrangler.interactive_mode", "THREE", "PRESS")
                kmi.properties.mode = 'DIRECT'

            # Store these keymaps for later cleanup
            prefs._light_keymaps.extend([(km, kmi) for kmi in km.keymap_items if kmi.idname == "lightwrangler.interactive_mode"])

        # Check for tracking constraints and ask for confirmation if needed
        if not self.tracking_confirmed and self.check_for_tracking(context):
            # Redirect to confirmation dialog
            bpy.ops.lightwrangler.confirm_tracking_removal('INVOKE_DEFAULT', mode=self.mode)
            return {'CANCELLED'}

        # Clear tracking if confirmed or not present
        self.clear_tracking_if_present(context)

        # Store initial isolation state
        self._was_isolated_before_modal = context.scene.lightwrangler_props.is_isolated
        
        # Set flag if operator was started with TAB
        self._started_with_tab = (event.type == 'TAB')

        # Store and set initial lens sim state
        self.store_lens_sim_state()  # Store initial state
        self.set_lens_sim_state(True)  # Enable during operation

        # Get the light object
        self.light_object = context.active_object
        self.light = context.active_object  # For light linking
        if not self.light_object or self.light_object.type != 'LIGHT':
            self.report({'WARNING'}, "Active object is not a light.")
            return {'CANCELLED'}

        # If started with number keys (1/2/3), use the specified mode
        if event.type in {'ONE', 'TWO', 'THREE', 'NUMPAD_1', 'NUMPAD_2', 'NUMPAD_3'} and event.value == 'PRESS':
            if event.type in {'ONE', 'NUMPAD_1'}:
                self.mode = 'REFLECT'
            elif event.type in {'TWO', 'NUMPAD_2'}:
                self.mode = 'ORBIT'
            else:  # THREE or NUMPAD_3
                self.mode = 'DIRECT'
            self.light_object["lw_last_mode"] = self.mode
        else:
            # For all other cases (TAB or gizmo), restore last used mode
            self.mode = self.light_object.get("lw_last_mode", "DIRECT")
        
        # print(f"[OPERATOR] Mode set to: {self.mode}")

        # Set interactive mode flag AFTER setting the mode
        context.scene.lightwrangler_props.is_interactive_mode_active = True
        # print("[OPERATOR] Interactive mode flag set to True")

        # Switch to light data tab in Properties window
        for area in context.screen.areas:
            if area.type == 'PROPERTIES':
                try:
                    # First ensure we have the active light object
                    obj = context.active_object
                    if obj and obj.type == 'LIGHT':
                        # Make sure the light is selected and active
                        obj.select_set(True)
                        context.view_layer.objects.active = obj
                        # Switch to DATA properties
                        area.spaces[0].context = 'DATA'
                except Exception:
                    pass
                break

        # Initialize help panel state from stored value
        self._show_help = context.scene.lightwrangler_props.show_help
        
        scene_props = context.scene.lightwrangler_props
        preferences = context.preferences.addons[ADDON_MODULE_NAME].preferences

        # Hide viewport overlays if enabled in preferences and rendering is active
        if preferences.hide_viewport_overlays and is_rendering_active(context):
            hide_viewport_elements(context)

        # Store initial viewport context
        self.initial_area = context.area
        self.initial_region = context.region

        if context.active_object and context.active_object.type == "LIGHT":
            try:
                self.original_linking_state = save_linking_state(context.active_object)
            except ReferenceError:
                pass

        # Store original theme color
        try:
            self.original_theme_color = context.preferences.themes[0].view_3d.object_active.copy()
        except (AttributeError, TypeError):
            # Fallback for cases where copy() might fail
            try:
                # Try to convert to tuple
                theme_color = context.preferences.themes[0].view_3d.object_active
                self.original_theme_color = tuple(theme_color[:3]) if theme_color else (1.0, 0.5, 0.0)
            except:
                # Use default orange color as last resort
                self.original_theme_color = (1.0, 0.5, 0.0)

        # Store original hide state
        self._original_hide_state = self.light_object.hide_viewport
        
        # Initialize precise mode from stored state
        self.precise_mode = self.light_object.get("lw_last_precise_mode", False)

        # Set initial pause state based on preference and whether light is new
        if self.light_object.get("lw_newly_created", False):
            # Always start new lights in active/unpaused mode
            self.is_position_paused = False
            # print("[OPERATOR] New light - setting unpaused")
        else:
            if event.type == 'LEFTMOUSE':  # If started from gizmo click
                # Force unpaused state when starting from gizmo
                self.is_position_paused = False
                # print("[OPERATOR] Gizmo click - forcing unpaused state")
            elif preferences.adjustment_mode_entry == "always_inactive":
                # Force paused state when preference is set to always inactive
                self.is_position_paused = True
                # print("[OPERATOR] Preference always_inactive - setting paused")
            else:  # "last_used"
                # Use the last saved state for the light
                self.is_position_paused = self.light_object.get("lw_last_pause_state", False)
                # print(f"[OPERATOR] Using last pause state: {self.is_position_paused}")
        
        # print(f"[OPERATOR] Final pause state after setup: {self.is_position_paused}")

        # Set theme color based on initial pause state and precise mode
        if self.precise_mode and self.mode in ('REFLECT', 'DIRECT'):
            # Use precise mode color
            context.preferences.themes[0].view_3d.object_active = get_color('PRECISE', self.original_theme_color)
        elif self.is_position_paused:
            # Modify original theme color to appear paused
            context.preferences.themes[0].view_3d.object_active = get_color('PAUSED', self.original_theme_color)
        
        # Set initial cursor based on mode and pause state
        if self.mode == 'ORBIT':
            if self.is_position_paused:
                context.window.cursor_modal_set('DEFAULT')
            else:
                context.window.cursor_modal_set('NONE')
        else:
            context.window.cursor_modal_set('DEFAULT')

        light_data = self.light_object.data
        self.current_power = light_data.energy
        self.current_size = getattr(light_data, 'size', 1.0) if light_data.type in {'AREA', 'SPOT'} else 1.0
        self.current_distance = self.light_object.get("lw_last_offset", 2.0)
        
        # Extract current Z-rotation from light's orientation
        self.current_z_rotation = self.get_current_z_rotation()

        # Clear power adjustment reference values when in Gobo mode
        # This prevents auto-adjustment from interfering with gobo projections
        if self.is_gobo_mode():
            # Clear all reference values used for power calculations
            self._reference_size_power = None
            self._reference_size_x = None
            self._reference_size_y = None
            self._reference_spot_power = None
            self._reference_spot_angle = None
            self._reference_spot_distance_power = None
            self._reference_spot_distance = None
            self._reference_point_distance_power = None
            self._reference_point_distance = None
            self._reference_power = None
            self._reference_distance = None

        self.original_values = {
            'power': self.current_power,
            'distance': self.current_distance,
            'z_rotation': self.current_z_rotation,
            'color': light_data.color[:],
            'location': self.light_object.location.copy(),
            'rotation': self.light_object.rotation_euler.copy(),
            'last_mode': self.light_object.get("lw_last_mode", scene_props.last_mode),
            'orbit_center': tuple(self.light_object.get("lw_orbit_center", (0,0,0))) if "lw_orbit_center" in self.light_object else None,
            'light_type': light_data.type,  # Store original light type
            'lw_last_pause_state': self.light_object.get("lw_last_pause_state", False),  # Store original pause state
            'lw_last_precise_mode': self.light_object.get("lw_last_precise_mode", False)  # Store original precise mode state
        }
        
        # Store type-specific properties
        if light_data.type == 'AREA':
            self.original_values['shape'] = light_data.shape
            self.original_values['size'] = light_data.size
            self.original_values['spread'] = light_data.spread
            if light_data.shape in {'RECTANGLE', 'ELLIPSE'}:
                self.original_values['size_y'] = light_data.size_y
        elif light_data.type == 'SPOT':
            self.original_values['spot_size'] = light_data.spot_size
            self.original_values['spot_blend'] = light_data.spot_blend
        elif light_data.type == 'POINT':
            self.original_values['shadow_soft_size'] = light_data.shadow_soft_size
        elif light_data.type == 'SUN':
            self.original_values['angle'] = light_data.angle

        # Always check and update orbit center if needed, regardless of pause state
        if self.mode == 'ORBIT':
            # First check if orbit center exists
            if "lw_orbit_center" not in self.light_object:
                # No orbit center yet - establish it based on light's direction
                lamp_z_world = (self.light_object.matrix_world.to_3x3()
                               @ Vector((0, 0, -1))).normalized()
                origin = self.light_object.location
                success, location, normal, _, _, _ = context.scene.ray_cast(
                    depsgraph=context.evaluated_depsgraph_get(),
                    origin=origin,
                    direction=lamp_z_world,
                    distance=10000.0
                )
                if success:
                    self.light_object["lw_orbit_center"] = tuple(location)
                    # Store target point for gizmo positioning
                    self.light_object["target"] = tuple(location)

            # Existing position/rotation change check
            old_loc = Vector(self.light_object.get("lw_last_known_loc", (0, 0, 0)))
            current_loc = self.light_object.location
            
            # Get old and new forward directions instead of full rotation
            old_rot_tuple = self.light_object.get("lw_last_known_rot", (0, 0, 0))
            old_rot = mathutils.Euler(old_rot_tuple)
            old_matrix = old_rot.to_matrix()
            old_forward = -(old_matrix @ Vector((0.0, 0.0, 1.0)))
            current_forward = -(self.light_object.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0)))
            
            loc_changed = (current_loc - old_loc).length > 0.001
            # Compare forward directions instead of full rotation
            rot_changed = old_forward.dot(current_forward) < 0.999
            
            if loc_changed or rot_changed:
                lamp_z_world = (self.light_object.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
                origin = self.light_object.location
                success, location, normal, _, _, _ = context.scene.ray_cast(
                    depsgraph=context.evaluated_depsgraph_get(),
                    origin=origin,
                    direction=lamp_z_world,
                    distance=10000.0
                )
                if success:
                    self.light_object["lw_orbit_center"] = tuple(location)
                    # Store target point for gizmo positioning
                    self.light_object["target"] = tuple(location)

        # Only do initial positioning if not starting in paused mode
        if not self.is_position_paused:
            if self.mode in ('REFLECT', 'DIRECT'):
                hit_loc, hit_normal = multi_sample_raycast(context, event)
                if hit_loc is not None:
                    # Store target point for gizmo positioning
                    self.light_object["target"] = tuple(hit_loc)
                    self.position_light_for_mode(hit_loc, hit_normal, context)

        self.start_mouse_x = event.mouse_x
        self.start_mouse_y = event.mouse_y

        # Add the draw handlers with specific order
        args = (self, context)
        
        # Add help HUD handler first (lowest priority)
        self._draw_handle_help = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_callback_help, args, 'WINDOW', 'POST_PIXEL'
        )
        
        # Add 3D visualization handler
        self._draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_callback_3d, args, 'WINDOW', 'POST_VIEW'
        )
        
        # Add 2D overlay handler last (highest priority)
        self._draw_handle_2d = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_callback_2d, args, 'WINDOW', 'POST_PIXEL'
        )
        
        context.window_manager.modal_handler_add(self)

        # Find all volume cubes and store their visibility state
        self.volume_cubes = self.find_volume_cubes()
        self.volume_cubes_visibility = {cube: cube.hide_get() for cube in self.volume_cubes}

        # Hide all volume cubes
        for cube in self.volume_cubes:
            cube.hide_set(True)

        # Initialize status bar text
        self.update_status_bar_text(context)
        
        return {'RUNNING_MODAL'}

    def find_volume_cubes(self):
        """Find all volume cubes in the scene using the is_gobo_volume property"""
        # Get all objects in the current view layer
        view_layer_objects = set(bpy.context.view_layer.objects)
        # Only return volume cubes that are in the current view layer
        return [obj for obj in view_layer_objects if obj.get("is_gobo_volume", False)]

    def toggle_help(self):
        """Toggle help HUD visibility with fade effect"""
        self._show_help = not self._show_help
        # Store the new state in scene properties
        bpy.context.scene.lightwrangler_props.show_help = self._show_help
        # Also update the default preference
        prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
        prefs.show_help_by_default = self._show_help
        self._help_fade_start = time.time()
        
        # Set initial alpha based on the target state
        if self._show_help:
            # When showing, start from 0 and animate to 1
            self._help_alpha = 0.0
        else:
            # When hiding, start from 1 and animate to 0
            self._help_alpha = 1.0
        
        # Register a timer to handle fade animation
        if hasattr(self, '_fade_timer'):
            try:
                bpy.app.timers.unregister(self._fade_timer)
            except ValueError:
                pass
        
        self._fade_timer = bpy.app.timers.register(
            self._update_fade_animation,
            first_interval=0.0,
            persistent=False
        )

    def _update_fade_animation(self):
        """Timer callback to update fade animation"""
        if self._help_fade_start is not None:
            current_time = time.time()
            elapsed = current_time - self._help_fade_start
            
            if elapsed >= self._help_fade_duration:
                # Animation is complete
                self._help_alpha = 1.0 if self._show_help else 0.0
                self._help_fade_start = None
                # Force a redraw
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
                return None  # Unregister the timer
            else:
                # Calculate progress
                progress = elapsed / self._help_fade_duration
                if self._show_help:
                    # When showing, go from 0 to 1
                    self._help_alpha = progress
                else:
                    # When hiding, go from 1 to 0
                    self._help_alpha = 1.0 - progress
                
                # Force a redraw
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
                return 0.0  # Continue the timer
        return None  # Unregister the timer if no fade is in progress

    def update_help_fade(self, context):
        """Legacy update method - no longer needed as timer handles updates"""
        pass

    def cleanup_drawing(self, context):
        """Remove draw handlers in reverse order of creation."""
        if self._draw_handle_2d is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handle_2d, 'WINDOW')
            self._draw_handle_2d = None
            
        if self._draw_handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handle, 'WINDOW')
            self._draw_handle = None
            
        if self._draw_handle_help is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handle_help, 'WINDOW')
            self._draw_handle_help = None

        # Clear any running fade timer using the proper API
        if hasattr(self, '_fade_timer'):
            try:
                bpy.app.timers.unregister(self._fade_timer)
            except ValueError:
                # Timer was already unregistered
                pass
            delattr(self, '_fade_timer')
        
        # Force an immediate redraw
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

    def update_hovered_property(self):
        """Update which property would be modified based on held keys"""
        # Store previous property to detect changes
        previous_property = self._hovered_property

        # Clear hovered property if no modifier keys are pressed
        if not any([self.shift_pressed, self.alt_pressed, self.ctrl_pressed, self.z_key_pressed]):
            self._hovered_property = None
        else:
            if self.z_key_pressed:
                if self.light_object.data.type != 'SUN':  # Disable Z rotation for Sun lights
                    self._hovered_property = 'ROTATION'
                else:
                    self._hovered_property = None
            elif self.shift_pressed and self.ctrl_pressed:
                if self.light_object.data.type == 'AREA':
                    self._hovered_property = 'SIZE_Y'
                else:
                    self._hovered_property = None
            elif self.shift_pressed and self.alt_pressed:
                if self.light_object.data.type == 'AREA':
                    self._hovered_property = 'SIZE_X'
                else:
                    self._hovered_property = None
            elif self.ctrl_pressed:
                if self.light_object.data.type in {'SPOT', 'AREA'}:
                    self._hovered_property = 'SPREAD'
                else:
                    self._hovered_property = None
            elif self.shift_pressed:
                if self.light_object.data.type != 'SUN':
                    self._hovered_property = 'SIZE'
                else:
                    self._hovered_property = 'SIZE'  # For sun, this controls angle
            elif self.alt_pressed:
                if self.light_object.data.type != 'SUN':
                    self._hovered_property = 'DISTANCE'
                else:
                    self._hovered_property = None
            else:
                self._hovered_property = None

        # Reset hover start time if property changed
        if previous_property != self._hovered_property:
            self._hover_start_time = None
            # Update status bar text when hovered property changes
            self.update_status_bar_text(bpy.context)

    def revert_view_transform(self, context):
        """Revert the view transform to the previous setting if it was changed."""
        # Only act if we have previously stored a view transform (F was pressed during modal)
        if hasattr(self, 'previous_view_transform'):
            view_settings = context.scene.view_settings
            if view_settings.view_transform == 'False Color' and self.previous_view_transform != 'False Color':
                view_settings.view_transform = self.previous_view_transform
                self.report({'INFO'}, f"Restored to {self.previous_view_transform} view transform")

    def modal(self, context, event):
        # print(f"[OPERATOR] Modal event: {event.type}, value: {event.value}")
        # print(f"[OPERATOR] Current pause state: {self.is_position_paused}")
        # print(f"[OPERATOR] Current mode: {self.mode}")
        # print(f"[OPERATOR] Interactive mode active: {context.scene.lightwrangler_props.is_interactive_mode_active}")

        # Skip the first event entirely as it's the same one that started the operator
        if not self._first_event_received:
            self._first_event_received = True
            # print("[OPERATOR] First event skipped")
            return {'RUNNING_MODAL'}

        # Debug: Log ALL events when shift is pressed to see what's happening with mouse wheel
        # if self.shift_pressed or event.shift:
        #     print(f"SHIFT EVENT DEBUG: type={event.type}, value={event.value}, shift={event.shift}, ctrl={event.ctrl}, alt={event.alt}")

        scene_props = context.scene.lightwrangler_props

        # Track modifier key states
        if event.type in {'LEFT_SHIFT', 'RIGHT_SHIFT'}:
            self.shift_pressed = event.value == 'PRESS'
            # print(f"[OPERATOR] Shift state changed: {self.shift_pressed}")
            self.update_hovered_property()
        elif event.type == 'SLASH':
            self.slash_pressed = event.value == 'PRESS'
            # Make slash work like Shift
            self.shift_pressed = self.slash_pressed
            # print(f"[OPERATOR] Slash/Shift state changed: {self.shift_pressed}")
            self.update_hovered_property()
        elif event.type in {'LEFT_ALT', 'RIGHT_ALT'}:
            self.alt_pressed = event.value == 'PRESS'
            # print(f"[OPERATOR] Alt state changed: {self.alt_pressed}")
            if self.alt_pressed and self.light_object.data.type == 'AREA':
                # Store reference values when Alt is first pressed
                self._reference_power = self.light_object.data.energy
                self._reference_distance = self.current_distance
            self.update_hovered_property()
        elif event.type in {'LEFT_CTRL', 'RIGHT_CTRL'}:
            self.ctrl_pressed = event.value == 'PRESS'
            # print(f"[OPERATOR] Ctrl state changed: {self.ctrl_pressed}")
            self.update_hovered_property()

            # Reset tracking variables when CTRL state changes
            if self.ctrl_pressed:
                # Starting CTRL - reset accumulated movement
                self._ctrl_movement_accumulated = 0.0
                self._ctrl_snap_active = False
                # Reset mouse start position to prevent jumps
                self.start_mouse_x = event.mouse_x
                self.start_mouse_y = event.mouse_y
            else:
                # Releasing CTRL - clear snap state
                self._ctrl_movement_accumulated = 0.0
                self._ctrl_snap_active = False
                self._snapped_axis = None
        elif event.type == 'Z':
            self.z_key_pressed = event.value == 'PRESS'
            # print(f"[OPERATOR] Z state changed: {self.z_key_pressed}")
            self.update_hovered_property()

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            stop_drawing()  # Stop raycast visualization
            self.cleanup_drawing(context)
            # Restore original theme color
            context.preferences.themes[0].view_3d.object_active = self.original_theme_color
            if event.type == 'ESC':
                revert_linking_state(context, self.light, self.original_linking_state)
            self.cancel(context)
            return {'CANCELLED'}

        elif event.type == 'L' and event.value == 'PRESS' and is_blender_version_compatible():
            if bpy.context.active_object and bpy.context.active_object.type == "LIGHT":
                last_activation_time["Light Linking"] = time.time()

                for area in bpy.context.screen.areas:
                    if area.type == "PROPERTIES":
                        for space in area.spaces:
                            if space.type == "PROPERTIES":
                                space.context = "OBJECT"
                        break

            if event.shift:
                self.link_object(context, event, is_blocker=True)
            else:
                self.link_object(context, event, is_blocker=False)

        # Handle finish events
        if event.type in {'LEFTMOUSE', 'RET'} or (event.type == 'TAB' and event.value == 'RELEASE' and not self._started_with_tab):
            stop_drawing()  # Stop raycast visualization
            self.cleanup_drawing(context)
            # Restore original theme color
            context.preferences.themes[0].view_3d.object_active = self.original_theme_color
            self.execute(context)
            return {'FINISHED'}
            
        # Handle initial TAB event
        if event.type == 'TAB' and self._started_with_tab:
            if event.value == 'RELEASE':
                self._started_with_tab = False  # Clear the flag after the initial TAB release
            return {'RUNNING_MODAL'}

        # Mode switching with per-light memory and pause handling
        if (event.type == 'ONE' or event.type == 'NUMPAD_1') and event.value == 'PRESS':
            # print("[OPERATOR] ONE key pressed")
            if self.mode == 'REFLECT':
                # Toggle pause state
                self.is_position_paused = not self.is_position_paused
                # print(f"[OPERATOR] Toggling pause state to: {self.is_position_paused}")
                # Update theme color based on pause state
                if self.is_position_paused:
                    # Modify original theme color to appear paused
                    context.preferences.themes[0].view_3d.object_active = get_color('PAUSED', self.original_theme_color)
                    context.window.cursor_modal_set('DEFAULT')  # Show cursor when paused
                else:
                    context.preferences.themes[0].view_3d.object_active = self.original_theme_color
                    context.window.cursor_modal_set('NONE')  # Hide cursor when active
                if context.area:
                    context.area.tag_redraw()
                self.update_status_bar_text(context)  # Update status bar
                return {'RUNNING_MODAL'}
            
            # print("[OPERATOR] Switching to REFLECT mode")
            self.mode = 'REFLECT'
            self.light_object["lw_last_mode"] = 'REFLECT'  # Store on light
            scene_props.last_mode = 'REFLECT'  # Keep scene default updated
            context.window.cursor_modal_set('DEFAULT')
            self.is_position_paused = False  # Reset pause state on mode change
            # print("[OPERATOR] Reset pause state on mode change")
            # Apply theme color based on precise mode state
            if self.precise_mode:
                context.preferences.themes[0].view_3d.object_active = get_color('PRECISE', self.original_theme_color)
            else:
                context.preferences.themes[0].view_3d.object_active = self.original_theme_color
            hit_loc, hit_normal = multi_sample_raycast(context, event)
            if hit_loc is not None:
                self.position_light_for_mode(hit_loc, hit_normal, context)
            self.update_status_bar_text(context)
            # Force redraw for border color update
            if context.area:
                context.area.tag_redraw()

        elif (event.type == 'TWO' or event.type == 'NUMPAD_2') and event.value == 'PRESS':
            # print("[OPERATOR] TWO key pressed")
            if self.mode == 'ORBIT':
                # Toggle pause state
                self.is_position_paused = not self.is_position_paused
                # print(f"[OPERATOR] Toggling pause state to: {self.is_position_paused}")
                # Update theme color based on pause state
                if self.is_position_paused:
                    # Modify original theme color to appear paused
                    context.preferences.themes[0].view_3d.object_active = get_color('PAUSED', self.original_theme_color)
                    context.window.cursor_modal_set('DEFAULT')  # Show cursor when paused
                else:
                    context.preferences.themes[0].view_3d.object_active = self.original_theme_color
                    context.window.cursor_modal_set('NONE')  # Hide cursor when active
                if context.area:
                    context.area.tag_redraw()
                self.update_status_bar_text(context)  # Update status bar
                return {'RUNNING_MODAL'}
                
            # print("[OPERATOR] Switching to ORBIT mode")
            self.mode = 'ORBIT'
            self.light_object["lw_last_mode"] = 'ORBIT'  # Store on light
            scene_props.last_mode = 'ORBIT'  # Keep scene default updated
            context.window.cursor_modal_set('NONE')
            self.is_position_paused = False  # Reset pause state on mode change
            # print("[OPERATOR] Reset pause state on mode change")
            # Restore original theme color when switching modes
            context.preferences.themes[0].view_3d.object_active = self.original_theme_color
            hit_loc, hit_normal = multi_sample_raycast(context, event)
            if hit_loc is not None:
                self.light_object["lw_orbit_center"] = tuple(hit_loc)
                self.start_mouse_x = event.mouse_x
                self.start_mouse_y = event.mouse_y
            self.update_status_bar_text(context)
            # Force redraw for border color update
            if context.area:
                context.area.tag_redraw()

        elif (event.type == 'THREE' or event.type == 'NUMPAD_3') and event.value == 'PRESS':
            # print("[OPERATOR] THREE key pressed")
            if self.mode == 'DIRECT':
                # Toggle pause state
                self.is_position_paused = not self.is_position_paused
                # print(f"[OPERATOR] Toggling pause state to: {self.is_position_paused}")
                # Update theme color based on pause state
                if self.is_position_paused:
                    # Modify original theme color to appear paused
                    context.preferences.themes[0].view_3d.object_active = get_color('PAUSED', self.original_theme_color)
                    context.window.cursor_modal_set('DEFAULT')  # Show cursor when paused
                else:
                    context.preferences.themes[0].view_3d.object_active = self.original_theme_color
                    context.window.cursor_modal_set('NONE')  # Hide cursor when active
                if context.area:
                    context.area.tag_redraw()
                self.update_status_bar_text(context)  # Update status bar
                return {'RUNNING_MODAL'}
                
            # print("[OPERATOR] Switching to DIRECT mode")
            self.mode = 'DIRECT'
            self.light_object["lw_last_mode"] = 'DIRECT'  # Store on light
            scene_props.last_mode = 'DIRECT'  # Keep scene default updated
            context.window.cursor_modal_set('DEFAULT')
            self.is_position_paused = False  # Reset pause state on mode change
            # print("[OPERATOR] Reset pause state on mode change")
            # Apply theme color based on precise mode state
            if self.precise_mode:
                context.preferences.themes[0].view_3d.object_active = get_color('PRECISE', self.original_theme_color)
            else:
                context.preferences.themes[0].view_3d.object_active = self.original_theme_color
            hit_loc, hit_normal = multi_sample_raycast(context, event)
            if hit_loc is not None:
                self.position_light_for_mode(hit_loc, hit_normal, context)
            self.update_status_bar_text(context)
            # Force redraw for border color update
            if context.area:
                context.area.tag_redraw()

        # Handle mouse movement
        if event.type == 'MOUSEMOVE':
            # print("[OPERATOR] Mouse movement detected")
            # print(f"[OPERATOR] Pause state during mouse move: {self.is_position_paused}")
            # Clear active property on mouse movement
            self._active_property = None
            if not self.is_position_paused:  # Only update position if not paused
                # print("[OPERATOR] Updating position (not paused)")
                if self.mode == 'ORBIT':
                    self.orbit_light(context, event)
                elif self.mode in ('REFLECT', 'DIRECT'):
                    # Use single sample raycast if in precise mode
                    if self.precise_mode:
                        from ..utils.raycast import single_sample_raycast
                        hit_loc, hit_normal = single_sample_raycast(context, event)
                    else:
                        hit_loc, hit_normal = multi_sample_raycast(context, event)
                    if hit_loc is not None and hit_normal is not None:
                        self.position_light_for_mode(hit_loc, hit_normal, context)
            else:
            #       print("[OPERATOR] Position update skipped (paused)")
                pass

        # Property adjustments
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'WHEELRIGHTMOUSE', 'WHEELLEFTMOUSE', 'UP_ARROW', 'DOWN_ARROW', 'TRACKPADPAN'}:
            if event.type != 'TRACKPADPAN' and event.value == 'PRESS' or event.type == 'TRACKPADPAN':
                # Debug prints for Blender 4.5 beta issue
                # print(f"EVENT: type={event.type}, value={event.value}, shift={event.shift}, ctrl={event.ctrl}, alt={event.alt}")
                # print(f"ADJUST: type={event.type}, value={event.value}, shift={event.shift}, ctrl={event.ctrl}, alt={event.alt}")
                # print(f"ADJUST PROPS: shift={event.shift}, ctrl={event.ctrl}, alt={event.alt}, self.shift_pressed={self.shift_pressed}")
                
                if event.type == 'TRACKPADPAN':
                    direction = (event.mouse_y - event.mouse_prev_y) * 0.05
                else:
                    direction = 1 if event.type in {'WHEELUPMOUSE', 'WHEELRIGHTMOUSE', 'UP_ARROW'} else -1
                
                self.adjust_light_properties(context, event, direction)
        elif event.type in {'LEFT_SHIFT', 'RIGHT_SHIFT', 'LEFT_ALT', 'RIGHT_ALT', 'LEFT_CTRL', 'RIGHT_CTRL', 'Z', 'SLASH'}:
            # Clear active property when modifier key is released
            if event.value == 'RELEASE':
                self._active_property = None

        # Handle help toggle
        if event.type == 'Q' and event.value == 'PRESS':
            self.toggle_help()
            return {'RUNNING_MODAL'}

        # Handle False Color toggle
        elif event.type == 'F' and event.value == 'PRESS':
            view_settings = bpy.context.scene.view_settings
            
            # Initialize previous_view_transform if it doesn't exist
            if not hasattr(self, 'previous_view_transform'):
                self.previous_view_transform = view_settings.view_transform
            
            try:
                # If we're already in False Color and it was the original mode
                if view_settings.view_transform == 'False Color' and self.previous_view_transform == 'False Color':
                    self.report({'INFO'}, "Already in False Color mode")
                # Normal toggle behavior
                elif view_settings.view_transform != 'False Color':
                    self.previous_view_transform = view_settings.view_transform
                    view_settings.view_transform = 'False Color'
                    self.report({'INFO'}, "Switched to False Color mode")
                else:
                    view_settings.view_transform = self.previous_view_transform
                    self.report({'INFO'}, f"Restored to {self.previous_view_transform} view transform")
                
                # Update the last activation time for highlighting
                last_activation_time["False Color"] = time.time()
                
            except Exception as e:
                self.report({'ERROR'}, f"Could not set False Color: {str(e)}")
                logger.error(f"Error details: {str(e)}")
            
            return {"RUNNING_MODAL"}
        
        # Handle precise mode toggle with SPACE (only for REFLECT and DIRECT modes)
        if event.type == 'SPACE' and event.value == 'PRESS' and not event.shift:
            if self.mode in ('REFLECT', 'DIRECT'):
                self.precise_mode = not self.precise_mode
                # Update theme color for visual feedback
                if self.precise_mode:
                    # Use a distinct color for precise mode
                    context.preferences.themes[0].view_3d.object_active = get_color('PRECISE', self.original_theme_color)
                else:
                    # Restore to normal or paused color
                    if self.is_position_paused:
                        context.preferences.themes[0].view_3d.object_active = get_color('PAUSED', self.original_theme_color)
                    else:
                        context.preferences.themes[0].view_3d.object_active = self.original_theme_color
                
                # Update light position immediately with the new mode
                if not self.is_position_paused:
                    if self.precise_mode:
                        from ..utils.raycast import single_sample_raycast
                        hit_loc, hit_normal = single_sample_raycast(context, event)
                    else:
                        hit_loc, hit_normal = multi_sample_raycast(context, event)
                    if hit_loc is not None and hit_normal is not None:
                        self.position_light_for_mode(hit_loc, hit_normal, context)
                
                self.update_status_bar_text(context)
                return {"RUNNING_MODAL"}

        # Handle light type toggle with Shift+SPACE
        if event.type == 'SPACE' and event.value == 'PRESS' and event.shift:
            if self.light_object.data.type in {'SPOT', 'AREA'}:
                # Store current properties
                old_type = self.light_object.data.type
                old_energy = self.light_object.data.energy
                old_color = self.light_object.data.color[:]
                old_location = self.light_object.location.copy()
                old_rotation = self.light_object.rotation_euler.copy()
                
                # Store whether this was a newly created light
                was_newly_created = "lw_newly_created" in self.light_object
                
                # Store size-related properties
                if old_type == 'AREA':
                    old_size = self.light_object.data.size
                    if self.light_object.data.shape in {'RECTANGLE', 'ELLIPSE'}:
                        old_size_y = self.light_object.data.size_y
                    else:
                        old_size_y = old_size
                    old_spread = self.light_object.data.spread
                else:  # SPOT
                    old_spot_size = self.light_object.data.spot_size
                    old_spot_blend = self.light_object.data.spot_blend
                
                # Determine new type
                new_type = 'AREA' if old_type == 'SPOT' else 'SPOT'
                
                # Store the original name
                original_name = self.light_object.name
                
                # Create new light object of the desired type
                bpy.ops.object.light_add(type=new_type)
                new_light = context.active_object
                
                # Copy transform
                new_light.location = old_location
                new_light.rotation_euler = old_rotation
                
                # Copy common properties
                new_light.data.energy = old_energy
                new_light.data.color = old_color
                
                # Set type-specific properties with size conversion
                if new_type == 'AREA':
                    # Convert from spot to area
                    # Use spot size to determine area light size (spot_size is in radians)
                    spot_angle = old_spot_size  # in radians
                    # Calculate area size based on spot angle and current distance
                    target_width = 2 * self.current_distance * math.tan(spot_angle / 2)
                    new_light.data.size = target_width
                    new_light.data.shape = 'SQUARE'
                    # Convert spot blend to spread (inverted relationship)
                    spread = math.radians(180) * (1 - old_spot_blend)
                    new_light.data.spread = max(math.radians(1), min(math.radians(180), spread))
                else:  # SPOT
                    # Convert from area to spot
                    # Calculate spot angle based on area size and current distance
                    target_angle = 2 * math.atan2(old_size / 2, self.current_distance)
                    new_light.data.spot_size = target_angle
                    # Convert spread to spot blend (inverted relationship)
                    blend = 1 - (old_spread / math.radians(180))
                    new_light.data.spot_blend = max(0, min(1, blend))
                
                # Copy custom properties
                for key in self.light_object.keys():
                    if key not in ['lw_newly_created']:  # Don't copy these flags
                        try:
                            # Check if the property is an IDPropertyGroup
                            prop_value = self.light_object[key]
                            if isinstance(prop_value, dict) and key in new_light and isinstance(new_light[key], dict):
                                # For IDPropertyGroup, copy individual values instead of direct assignment
                                for subkey in prop_value.keys():
                                    try:
                                        new_light[key][subkey] = prop_value[subkey]
                                    except TypeError:
                                        # Skip if we can't copy a specific subproperty
                                        pass
                            else:
                                # For regular properties, direct assignment
                                new_light[key] = prop_value
                        except (TypeError, AttributeError) as e:
                            # Skip properties that can't be copied
                            logger.error(f"Could not copy property {key}: {e}")
                
                # Preserve newly created state if this was a new light
                if was_newly_created:
                    new_light["lw_newly_created"] = True
                
                # Store reference to old object for cleanup
                old_light = self.light_object
                
                # Update operator's reference to the new light
                self.light_object = new_light
                self.light = new_light  # Update light reference for light linking
                
                # Restore original name
                new_light.name = original_name

                # Update light linking state for the new light
                try:
                    self.original_linking_state = save_linking_state(new_light)
                except ReferenceError:
                    pass
                
                # Apply Scrim customization for area lights
                if new_type == 'AREA':
                    try:
                        if context.scene.render.engine == 'CYCLES':
                            bpy.ops.lightwrangler.apply_custom_data_block(
                                light_name=new_light.name,
                                light_type='AREA',
                                customization="Scrim"
                            )
                        else:
                            bpy.ops.lightwrangler.apply_custom_data_block(
                                light_name=new_light.name,
                                light_type='AREA',
                                customization="Default"
                            )
                    except Exception as e:
                        logger.warning(f"Could not apply customization: {e}")
                else:
                    try:
                        bpy.ops.lightwrangler.apply_custom_data_block(
                            light_name=new_light.name,
                            light_type=new_type,
                            customization="Default"
                        )
                    except Exception as e:
                        logger.warning(f"Could not apply Default customization: {e}")
                
                # Delete the old light object (this will also remove its data)
                bpy.data.objects.remove(old_light, do_unlink=True)
                
                # Ensure the new light is selected and active
                new_light.select_set(True)
                context.view_layer.objects.active = new_light
                
                # Force a redraw
                if context.area:
                    context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        # Handle light isolation
        if event.type == 'I' and event.value == 'PRESS':
            bpy.ops.lightwrangler.toggle_visibility()
            return {'RUNNING_MODAL'}

        # Handle light hiding
        if event.type == 'H' and event.value == 'PRESS':
            self.light_object.hide_viewport = not self.light_object.hide_viewport
            # Ensure light remains selected and active
            self.light_object.select_set(True)
            context.view_layer.objects.active = self.light_object
            return {'RUNNING_MODAL'}

        if context.area:
            context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def is_gobo_mode(self):
        """
        Check if the current light has Gobo customization active.

        Returns:
            bool: True if light is in Gobo mode, False otherwise
        """
        if not self.light_object or self.light_object.type != 'LIGHT':
            return False

        light_type = self.light_object.data.type
        customization_key = f"last_customization_{light_type}"
        current_customization = self.light_object.get(customization_key, "Default")

        return current_customization == "Gobo"

    def calculate_area_power_adjustment(self, old_size_x, old_size_y, new_size_x, new_size_y):
        """
        Calculate the required power adjustment when area light size changes.
        Respects Blender 4.5's normalize property for proper behavior.
        
        Blender 4.5+ with normalize ON: No adjustment (let Blender handle it)
        Blender 4.5+ with normalize OFF: Inverse scaling to maintain constant total power
        Blender < 4.5: Linear scaling to maintain constant brightness
        
        Args:
            old_size_x (float): Previous width of the light
            old_size_y (float): Previous height of the light
            new_size_x (float): New width of the light
            new_size_y (float): New height of the light
            
        Returns:
            float: The new power value to maintain consistent illumination
        """
        # Initialize reference values if not set
        if not hasattr(self, '_reference_size_power') or self._reference_size_power is None:
            self._reference_size_power = self.current_power
            self._reference_size_x = old_size_x
            self._reference_size_y = old_size_y if self.light_object.data.shape in {'RECTANGLE', 'ELLIPSE'} else old_size_x
            return self.current_power
            
        # Calculate reference area (from when we started adjusting)
        reference_area = self._reference_size_x * self._reference_size_y
        
        # Calculate new area
        new_area = new_size_x * (new_size_y if self.light_object.data.shape in {'RECTANGLE', 'ELLIPSE'} else new_size_x)
        
        # Avoid division by zero
        if reference_area == 0 or new_area == 0:
            return self.current_power
            
        area_ratio = new_area / reference_area
        
        # Check if Blender has normalize property (4.5+)
        if hasattr(self.light_object.data, 'normalize'):
            if self.light_object.data.normalize:
                # Normalize ON: Blender maintains constant total power
                # We don't adjust - let Blender handle the size/power relationship
                return self.current_power
            else:
                # Normalize OFF: Blender maintains constant power per area
                # We apply inverse scaling to maintain constant total power
                return self._reference_size_power / area_ratio
        else:
            # Blender < 4.5: Behaves like normalize=ON (constant total power)
            # Apply linear scaling to maintain constant brightness per area
            return self._reference_size_power * area_ratio

    def calculate_spot_angle_power_adjustment(self, old_angle, new_angle):
        """
        Calculate power adjustment when spot angle changes to maintain constant illumination.
        
        Args:
            old_angle (float): Previous spot angle in radians
            new_angle (float): New spot angle in radians
        
        Returns:
            float: New power value to maintain same illuminance at center
        """
        # Initialize reference values if not set
        if not hasattr(self, '_reference_spot_power') or self._reference_spot_power is None:
            self._reference_spot_power = self.current_power
            self._reference_spot_angle = old_angle
            return self.current_power
            
        # Calculate solid angles (approximating spot as cone)
        old_solid_angle = 2 * math.pi * (1 - math.cos(old_angle / 2))
        new_solid_angle = 2 * math.pi * (1 - math.cos(new_angle / 2))
        
        # Special handling for very narrow angles (< 10 degrees)
        if math.degrees(new_angle) < 10:
            # Use gentler scaling for narrow angles to prevent extreme power jumps
            power_scale = (new_solid_angle / old_solid_angle) ** 0.125  # eighth root for very gradual change
        else:
            # For normal angles, use square root scaling
            power_scale = math.sqrt(new_solid_angle / old_solid_angle)
        
        return self._reference_spot_power / power_scale  # Inverse relationship for spots

    def calculate_spot_distance_power_adjustment(self, old_distance, new_distance):
        """
        Calculate power adjustment when spot distance changes using inverse square law.
        
        Args:
            old_distance (float): Previous distance
            new_distance (float): New distance
        
        Returns:
            float: New power value to maintain same illuminance
        """
        # Initialize reference values if not set
        if not hasattr(self, '_reference_spot_distance_power') or self._reference_spot_distance_power is None:
            self._reference_spot_distance_power = self.current_power
            self._reference_spot_distance = old_distance
            return self.current_power
        
        # Calculate using inverse square law
        distance_ratio = new_distance / self._reference_spot_distance
        return self._reference_spot_distance_power * (distance_ratio * distance_ratio)

    def calculate_point_distance_power_adjustment(self, old_distance, new_distance):
        """
        Calculate power adjustment when point light distance changes using inverse square law.

        Args:
            old_distance (float): Previous distance
            new_distance (float): New distance

        Returns:
            float: New power value to maintain same illuminance
        """
        # Initialize reference values if not set
        if not hasattr(self, '_reference_point_distance_power') or self._reference_point_distance_power is None:
            self._reference_point_distance_power = self.current_power
            self._reference_point_distance = old_distance
            return self.current_power

        # Calculate using inverse square law
        distance_ratio = new_distance / self._reference_point_distance
        return self._reference_point_distance_power * (distance_ratio * distance_ratio)

    def adjust_light_properties(self, context, event, adjustment_direction):
        self._last_wheel_event_time = time.time()  # Record wheel event time for tooltip delay
        light_data = self.light_object.data
        light_type = light_data.type
        
        # Debug: Check both sources of modifier key state for Blender 4.5 beta issue
        shift_state = self.shift_pressed or self.slash_pressed or event.shift
        alt_state = self.alt_pressed or event.alt
        ctrl_state = self.ctrl_pressed or event.ctrl
        
        # print(f"MODIFIER STATES: self.shift_pressed={self.shift_pressed}, event.shift={event.shift}, final_shift={shift_state}")
        # print(f"MODIFIER STATES: self.alt_pressed={self.alt_pressed}, event.alt={event.alt}, final_alt={alt_state}")
        # print(f"MODIFIER STATES: self.ctrl_pressed={self.ctrl_pressed}, event.ctrl={event.ctrl}, final_ctrl={ctrl_state}")
        
        # Store original position and orientation
        original_position = self.light_object.location.copy()
        original_rotation = self.light_object.rotation_euler.copy()
        
        if self.z_key_pressed:
            if light_type == 'SUN':  # Skip rotation adjustment for SUN lights
                return
                
            self._active_property = 'ROTATION'
            
            # Calculate rotation delta
            if event.type == 'TRACKPADPAN':
                delta = -5.0 * adjustment_direction
            else:
                delta = 5.0 if adjustment_direction < 0 else -5.0  # Reversed direction for mouse wheel
            
            # Convert to radians and update current rotation
            rotation_delta = math.radians(delta)
            self.current_z_rotation = ((self.current_z_rotation + rotation_delta + math.pi) 
                                   % (2 * math.pi) - math.pi)  # Keep angle in [-π, π] range
            
            # Calculate light direction first
            light_direction = -(self.light_object.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0)))
            
            if self.mode == 'ORBIT':
                center = Vector(self.light_object.get("lw_orbit_center", (0, 0, 0)))
                # For orbit mode, recalculate light direction based on center point
                light_direction = (center - self.light_object.location).normalized()
            
            self.light_object.rotation_euler = self.apply_z_rotation(light_direction, self.current_z_rotation)
            
        elif (shift_state) and (ctrl_state):
            # Handle Shift+Ctrl combination for area lights
            if light_type == 'AREA':
                # Store current sizes for power calculation
                old_size_x = light_data.size
                old_size_y = light_data.size_y if light_data.shape in {'RECTANGLE', 'ELLIPSE'} else light_data.size
                
                # Auto-convert shape if needed
                if light_data.shape == 'SQUARE':
                    current_size = light_data.size
                    light_data.shape = 'RECTANGLE'
                    light_data.size = current_size  # Preserve X dimension
                    light_data.size_y = current_size  # Set Y dimension equal to X
                elif light_data.shape == 'DISK':
                    current_size = light_data.size
                    light_data.shape = 'ELLIPSE'
                    light_data.size = current_size  # Preserve X dimension
                    light_data.size_y = current_size  # Set Y dimension equal to X
                    
                if light_data.shape in {'RECTANGLE', 'ELLIPSE'}:
                    self._active_property = 'SIZE_Y'
                    adjustment = 0.05 * abs(adjustment_direction)
                    if adjustment_direction > 0:
                        light_data.size_y += light_data.size_y * adjustment
                    else:
                        light_data.size_y = max(0.01, light_data.size_y - light_data.size_y * adjustment)

                    # Calculate and apply power adjustment if enabled (excluding Gobo mode)
                    if context.preferences.addons[ADDON_MODULE_NAME].preferences.use_calculated_light and not self.is_gobo_mode():
                        new_power = self.calculate_area_power_adjustment(
                            old_size_x, old_size_y,
                            light_data.size, light_data.size_y
                        )
                        self.current_power = new_power
                        self.apply_power()
                    
        elif (shift_state) and (alt_state):
            # Handle Shift+Alt combination for area lights
            if light_type == 'AREA':
                # Store current sizes for power calculation
                old_size_x = light_data.size
                old_size_y = light_data.size_y if light_data.shape in {'RECTANGLE', 'ELLIPSE'} else light_data.size
                
                # Auto-convert shape if needed
                if light_data.shape == 'SQUARE':
                    current_size = light_data.size
                    light_data.shape = 'RECTANGLE'
                    light_data.size = current_size  # Preserve X dimension
                    light_data.size_y = current_size  # Set Y dimension equal to X
                elif light_data.shape == 'DISK':
                    current_size = light_data.size
                    light_data.shape = 'ELLIPSE'
                    light_data.size = current_size  # Preserve X dimension
                    light_data.size_y = current_size  # Set Y dimension equal to X
                    
                if light_data.shape in {'RECTANGLE', 'ELLIPSE'}:
                    self._active_property = 'SIZE_X'
                    adjustment = 0.05 * abs(adjustment_direction)
                    if adjustment_direction > 0:
                        light_data.size += light_data.size * adjustment
                    else:
                        light_data.size = max(0.01, light_data.size - light_data.size * adjustment)

                    # Calculate and apply power adjustment if enabled (excluding Gobo mode)
                    if context.preferences.addons[ADDON_MODULE_NAME].preferences.use_calculated_light and not self.is_gobo_mode():
                        new_power = self.calculate_area_power_adjustment(
                            old_size_x, old_size_y,
                            light_data.size, light_data.size_y
                        )
                        self.current_power = new_power
                        self.apply_power()
                    
        elif shift_state:
            self._active_property = 'SIZE'
            adjustment = 0.05 * abs(adjustment_direction)
            
            if light_type == 'SPOT':
                old_spot_size = light_data.spot_size
                if adjustment_direction > 0:
                    light_data.spot_size += light_data.spot_size * adjustment
                else:
                    light_data.spot_size = max(math.radians(1), light_data.spot_size - light_data.spot_size * adjustment)

                # Calculate and apply power adjustment if enabled (excluding Gobo mode)
                if context.preferences.addons[ADDON_MODULE_NAME].preferences.use_calculated_light and not self.is_gobo_mode():
                    new_power = self.calculate_spot_angle_power_adjustment(
                        old_spot_size,
                        light_data.spot_size
                    )
                    self.current_power = new_power
                    self.apply_power()
                    
            elif light_type == 'POINT':
                if adjustment_direction > 0:
                    light_data.shadow_soft_size += light_data.shadow_soft_size * adjustment
                else:
                    light_data.shadow_soft_size = max(0.01, light_data.shadow_soft_size - light_data.shadow_soft_size * adjustment)
                    
            elif light_type == 'AREA':
                # Store current sizes for power calculation
                old_size_x = light_data.size
                old_size_y = light_data.size_y if light_data.shape in {'RECTANGLE', 'ELLIPSE'} else light_data.size
                
                # Original proportional scaling behavior
                if adjustment_direction > 0:
                    light_data.size += light_data.size * adjustment
                    if light_data.shape in {'RECTANGLE', 'ELLIPSE'}:
                        light_data.size_y += light_data.size_y * adjustment
                else:
                    light_data.size = max(0.01, light_data.size - light_data.size * adjustment)
                    if light_data.shape in {'RECTANGLE', 'ELLIPSE'}:
                        light_data.size_y = max(0.01, light_data.size_y - light_data.size_y * adjustment)

                # Calculate and apply power adjustment if enabled (excluding Gobo mode)
                if context.preferences.addons[ADDON_MODULE_NAME].preferences.use_calculated_light and not self.is_gobo_mode():
                    new_power = self.calculate_area_power_adjustment(
                        old_size_x, old_size_y,
                        light_data.size, light_data.size_y
                    )
                    self.current_power = new_power
                    self.apply_power()

            elif light_type == 'SUN':
                # Adjust sun angle with limits (0.1 to 180 degrees)
                if adjustment_direction > 0:
                    light_data.angle = min(math.radians(180), light_data.angle + light_data.angle * adjustment)
                else:
                    light_data.angle = max(math.radians(0.1), light_data.angle - light_data.angle * adjustment)
            
        elif ctrl_state:
            self._active_property = 'SPREAD'
            if light_type == 'SPOT':
                delta = 0.05 * abs(adjustment_direction)
                if event.type == 'TRACKPADPAN':
                    # Invert direction only for spread/blend to maintain its current behavior
                    adjustment_direction = -adjustment_direction
                if adjustment_direction > 0:
                    light_data.spot_blend = min(1.0, light_data.spot_blend + delta)
                else:
                    light_data.spot_blend = max(0.0, light_data.spot_blend - delta)
                
            elif light_type == 'AREA':
                current_degrees = math.degrees(light_data.spread)
                old_spread = light_data.spread
                
                if event.type == 'TRACKPADPAN':
                    # Invert direction only for spread to maintain its current behavior
                    adjustment_direction = -adjustment_direction
                
                if adjustment_direction > 0:
                    if current_degrees >= 4:
                        increment = math.radians(5) * abs(adjustment_direction)
                    else:
                        increment = math.radians(1) * abs(adjustment_direction)
                    light_data.spread = min(math.radians(180), light_data.spread + increment)
                else:
                    if current_degrees > 6:
                        decrement = math.radians(5) * abs(adjustment_direction)
                    else:
                        decrement = math.radians(1) * abs(adjustment_direction)
                    light_data.spread = max(math.radians(1), light_data.spread - decrement)
                
                # Adjust power based on spread change if enabled (excluding Gobo mode)
                if context.preferences.addons[ADDON_MODULE_NAME].preferences.use_calculated_light and not self.is_gobo_mode():
                    # Calculate solid angle ratio (approximation)
                    old_solid_angle = 2 * math.pi * (1 - math.cos(old_spread / 2))
                    new_solid_angle = 2 * math.pi * (1 - math.cos(light_data.spread / 2))
                    
                    # Special handling for small spread angles (below 10 degrees)
                    if math.degrees(light_data.spread) < 10:
                        # Use an eighth root for very small angles to make power adjustment extremely gradual
                        # Add check to prevent division by zero
                        if old_solid_angle > 0:
                            power_scale = (new_solid_angle / old_solid_angle) ** 0.125  # Eighth root for extremely gradual change
                        else:
                            # If old_solid_angle is zero, use a default scale or skip adjustment
                            power_scale = 1.0  # No change in power
                    else:
                        # Use square root scaling for normal angles
                        # Add check to prevent division by zero
                        if old_solid_angle > 0:
                            power_scale = math.sqrt(new_solid_angle / old_solid_angle)
                        else:
                            power_scale = 1.0  # No change in power
                        
                    self.current_power = self.current_power * power_scale
                    self.apply_power()
            
        elif event.alt:
            if light_type != 'SUN':  # Skip distance adjustment for SUN lights
                self._active_property = 'DISTANCE'
                old_distance = self.current_distance
                current_distance = self.current_distance
                adjustment = 0.05 * current_distance * abs(adjustment_direction)
                
                if adjustment_direction > 0:
                    self.current_distance = max(0.01, current_distance - adjustment)
                else:
                    self.current_distance = current_distance + adjustment

                # Calculate and apply new power for area and spot lights if auto-adjustment is enabled (excluding Gobo mode)
                if context.preferences.addons[ADDON_MODULE_NAME].preferences.use_calculated_light and not self.is_gobo_mode():
                    if light_type == 'AREA' and self._reference_power is not None and self._reference_distance is not None:
                        distance_ratio = self.current_distance / self._reference_distance
                        new_power = self._reference_power * (distance_ratio * distance_ratio)
                        self.current_power = new_power
                        self.apply_power()
                    elif light_type == 'SPOT':
                        new_power = self.calculate_spot_distance_power_adjustment(
                            old_distance,
                            self.current_distance
                        )
                        self.current_power = new_power
                        self.apply_power()
                    elif light_type == 'POINT':
                        new_power = self.calculate_point_distance_power_adjustment(
                            old_distance,
                            self.current_distance
                        )
                        self.current_power = new_power
                        self.apply_power()

                # Apply distance without full position update
                if self.mode == 'ORBIT':
                    # Use safe getter with default value to prevent KeyError
                    orbit_center = Vector(self.light_object.get("lw_orbit_center", (0, 0, 0)))
                    direction = (self.light_object.location - orbit_center).normalized()
                    self.light_object.location = orbit_center + direction * self.current_distance
                else:
                    direction = -(self.light_object.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0)))
                    if hasattr(self, '_last_hit_point'):
                        self.light_object.location = self._last_hit_point + (-direction * self.current_distance)
                    else:
                        self.light_object.location += direction * (self.current_distance - self.light_object.get("lw_last_offset", 2.0))
                
                self.light_object["lw_last_offset"] = self.current_distance
            
        else:
            self._active_property = 'POWER'
            if light_type == 'SUN':
                adjustment = 0.005 * self.current_power * abs(adjustment_direction)  # Reduced from 0.01
            else:
                adjustment = 0.05 * self.current_power * abs(adjustment_direction)  # Reduced from 0.1
                
            if adjustment_direction > 0:
                self.current_power += adjustment
            else:
                self.current_power = max(0.01, self.current_power - adjustment)
                
            self.apply_power()

        # After ANY property change, update position using the same logic as mouse movement
        if light_type != 'SUN' and self.mode != 'ORBIT':
            if hasattr(self, '_last_hit_point') and hasattr(self, '_last_hit_normal'):
                self.position_light_for_mode(self._last_hit_point, self._last_hit_normal, context)

    def apply_distance(self):
        if self.mode == 'ORBIT':
            # Use safe getter with default value to prevent KeyError
            orbit_center = Vector(self.light_object.get("lw_orbit_center", (0, 0, 0)))
            direction = (self.light_object.location - orbit_center).normalized()
            self.light_object.location = orbit_center + direction * self.current_distance
        else:
            direction = -(self.light_object.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0)))
            success, target, normal, _, _, _ = bpy.context.scene.ray_cast(
                depsgraph=bpy.context.evaluated_depsgraph_get(),
                origin=self.light_object.location,
                direction=direction,
                distance=10000.0
            )
            
            if success:
                self.light_object.location = target + (-direction * self.current_distance)
            else:
                self.light_object.location += direction * (self.current_distance - self.light_object.get("lw_last_offset", 2.0))
                
            self.light_object["lw_last_offset"] = self.current_distance

    def apply_power(self):
        if bpy.context.scene.render.engine == 'octane':
            # For Octane lights, adjust power through the Texture emission node
            if self.light_object.data.node_tree and "Texture emission" in self.light_object.data.node_tree.nodes:
                self.light_object.data.node_tree.nodes["Texture emission"].inputs[1].default_value = self.current_power
        else:
            # For Cycles/Eevee lights, use the standard energy property
            self.light_object.data.energy = self.current_power

    def execute(self, context):
        # Clear status text before finishing
        context.workspace.status_text_set(None)
        if not self.light_object:
            self.light_object = context.active_object
            if not self.light_object or self.light_object.type != 'LIGHT':
                self.report({'WARNING'}, "Active object is not a light.")
                return {'CANCELLED'}
                
        # Clear interactive mode flag
        context.scene.lightwrangler_props.is_interactive_mode_active = False

        # Restore lens sim state
        self.restore_lens_sim_state()

        # Clear the newly created flag if it exists
        if "lw_newly_created" in self.light_object:
            del self.light_object["lw_newly_created"]

        # Clear reference values
        for attr in ['_reference_spot_power', '_reference_spot_angle',
                     '_reference_spot_distance_power', '_reference_spot_distance',
                     '_reference_point_distance_power', '_reference_point_distance']:
            if hasattr(self, attr):
                delattr(self, attr)
        
        # Store final mode and offset
        self.light_object["lw_last_mode"] = self.mode
        self.light_object["lw_last_offset"] = getattr(self, 'current_distance', 2.0)
        
        # Store final pause state
        self.light_object["lw_last_pause_state"] = self.is_position_paused
        
        # Store final precise mode state
        self.light_object["lw_last_precise_mode"] = self.precise_mode
        
        # Update orbit center only when finalizing REFLECT or DIRECT modes
        if self.mode in ('REFLECT', 'DIRECT') and hasattr(self, '_last_hit_point'):
            self.light_object["lw_orbit_center"] = tuple(self._last_hit_point)
        
        # Store final Z-rotation
        self.light_object["lw_last_z_rotation"] = getattr(self, 'current_z_rotation', 0.0)
        
        # Store last known position and rotation for orbit mode
        self.light_object["lw_last_known_loc"] = tuple(self.light_object.location)
        self.light_object["lw_last_known_rot"] = tuple(self.light_object.rotation_euler)
        
        # Restore cursor state
        context.window.cursor_modal_set('DEFAULT')
        
        # Restore viewport overlays if they were hidden
        if context.preferences.addons[ADDON_MODULE_NAME].preferences.hide_viewport_overlays:
            unhide_viewport_elements(context)
        
        # Only revert isolation if it wasn't isolated before modal started
        if context.scene.lightwrangler_props.is_isolated and not self._was_isolated_before_modal:
            bpy.ops.lightwrangler.toggle_visibility()
        
        # Restore original hide state
        if self.light_object:
            self.light_object.hide_viewport = self._original_hide_state
            # Ensure light remains selected and active
            self.light_object.select_set(True)
            context.view_layer.objects.active = self.light_object

        # Only create keyframes if auto-keying is enabled
        if context.scene.tool_settings.use_keyframe_insert_auto:
            self.create_keyframes(context)

        self.cleanup_drawing(context)
        # Revert view transform if it was changed
        self.revert_view_transform(context)

        # Restore volume cubes visibility
        if hasattr(self, 'volume_cubes_visibility'):
            for cube, was_hidden in self.volume_cubes_visibility.items():
                try:
                    # If cube is valid and exists, restore its visibility
                    if cube.users >= 0:  # This will raise ReferenceError if the object is invalid
                        cube.hide_set(was_hidden)
                except ReferenceError:
                    continue  # Skip deleted cubes

        return {'FINISHED'}

    def cancel(self, context):
        # Clear status text before cancelling
        context.workspace.status_text_set(None)
        """Handle operator cancellation by restoring all original properties."""
        stop_drawing()  # Stop raycast visualization
        self.cleanup_drawing(context)

        # Restore lens sim state
        self.restore_lens_sim_state()

        # Clear interactive mode flag
        context.scene.lightwrangler_props.is_interactive_mode_active = False

        # Clear target point
        if self.light_object and "target" in self.light_object:
            del self.light_object["target"]

        # Clear reference values
        for attr in ['_reference_spot_power', '_reference_spot_angle',
                     '_reference_spot_distance_power', '_reference_spot_distance',
                     '_reference_point_distance_power', '_reference_point_distance']:
            if hasattr(self, attr):
                delattr(self, attr)

        # Restore viewport overlays if they were hidden
        if context.preferences.addons[ADDON_MODULE_NAME].preferences.hide_viewport_overlays:
            unhide_viewport_elements(context)

        # Only revert isolation if it wasn't isolated before modal started
        if context.scene.lightwrangler_props.is_isolated and not self._was_isolated_before_modal:
            bpy.ops.lightwrangler.toggle_visibility()

        if self.light_object:
            # Restore original hide state
            self.light_object.hide_viewport = self._original_hide_state
            # Ensure light remains selected and active
            self.light_object.select_set(True)
            context.view_layer.objects.active = self.light_object
            
            # Check if this is a newly created light
            if "lw_newly_created" in self.light_object:
                # If this was a new light being added, delete it on cancel
                bpy.data.objects.remove(self.light_object, do_unlink=True)
            elif hasattr(self, 'original_values'):
                # For existing lights, restore all original properties
                original_type = self.original_values.get('light_type')
                current_type = self.light_object.data.type

                # If type has changed, create new light of original type
                if original_type and original_type != current_type:
                    # Create new light of original type
                    bpy.ops.object.light_add(type=original_type)
                    new_light = context.active_object
                    
                    # Copy transform
                    new_light.location = self.original_values['location']
                    new_light.rotation_euler = self.original_values['rotation']
                    
                    # Copy basic properties
                    new_light.data.energy = self.original_values['power']
                    new_light.data.color = self.original_values['color']
                    
                    # Store old light for cleanup
                    old_light = self.light_object
                    
                    # Update operator reference
                    self.light_object = new_light
                    self.light = new_light
                    
                    # Restore original name
                    new_light.name = old_light.name

                    # Restore or remove lw_last_offset
                    if 'distance' in self.original_values:
                        new_light["lw_last_offset"] = self.original_values['distance']
                    
                    # Delete the temporary light
                    bpy.data.objects.remove(old_light, do_unlink=True)
                else:
                    # If type hasn't changed, restore position and basic properties
                    self.light_object.location = self.original_values['location']
                    self.light_object.rotation_euler = self.original_values['rotation']
                    light_data = self.light_object.data
                    light_data.energy = self.original_values['power']
                    light_data.color = self.original_values['color']

                    # Restore or remove lw_last_offset
                    if 'distance' in self.original_values:
                        self.light_object["lw_last_offset"] = self.original_values['distance']

                # Now restore type-specific properties
                light_data = self.light_object.data
                if light_data.type == 'AREA':
                    light_data.shape = self.original_values.get('shape', 'SQUARE')
                    light_data.size = self.original_values.get('size', 1.0)
                    light_data.spread = self.original_values.get('spread', math.radians(180))
                    if light_data.shape in {'RECTANGLE', 'ELLIPSE'}:
                        light_data.size_y = self.original_values.get('size_y', 1.0)
                elif light_data.type == 'SPOT':
                    light_data.spot_size = self.original_values.get('spot_size', math.radians(45.0))
                    light_data.spot_blend = self.original_values.get('spot_blend', 0.15)
                elif light_data.type == 'POINT':
                    light_data.shadow_soft_size = self.original_values.get('shadow_soft_size', 0.0)
                elif light_data.type == 'SUN':
                    light_data.angle = self.original_values.get('angle', math.radians(0.526))

                # Restore custom properties
                if self.original_values.get('last_mode'):
                    self.light_object["lw_last_mode"] = self.original_values['last_mode']
                elif "lw_last_mode" in self.light_object:
                    del self.light_object["lw_last_mode"]

                if self.original_values.get('orbit_center'):
                    self.light_object["lw_orbit_center"] = self.original_values['orbit_center']
                elif "lw_orbit_center" in self.light_object:
                    del self.light_object["lw_orbit_center"]

                # Restore original pause state if it existed before the operator started
                if "lw_last_pause_state" in self.original_values:
                    self.light_object["lw_last_pause_state"] = self.original_values['lw_last_pause_state']
                elif "lw_last_pause_state" in self.light_object:
                    del self.light_object["lw_last_pause_state"]
                
                # Restore original precise mode state if it existed before the operator started
                if "lw_last_precise_mode" in self.original_values:
                    self.light_object["lw_last_precise_mode"] = self.original_values['lw_last_precise_mode']
                elif "lw_last_precise_mode" in self.light_object:
                    del self.light_object["lw_last_precise_mode"]

                # Update light linking reference before reverting state
                self.light = self.light_object

                # Restore tracking constraint mute states
                if hasattr(self, 'original_tracking_mute_states'):
                    for mute_info in self.original_tracking_mute_states:
                        # Find the constraint by name
                        for constraint in self.light_object.constraints:
                            if constraint.name == mute_info['name'] and constraint.type == 'TRACK_TO':
                                # Restore original mute state
                                constraint.mute = mute_info['was_muted']
                                break

        # Restore cursor state
        context.window.cursor_modal_set('DEFAULT')

        # Revert view transform if it was changed
        self.revert_view_transform(context)

        # Restore volume cubes visibility
        if hasattr(self, 'volume_cubes_visibility'):
            for cube, was_hidden in self.volume_cubes_visibility.items():
                try:
                    # If cube is valid and exists, restore its visibility
                    if cube.users >= 0:  # This will raise ReferenceError if the object is invalid
                        cube.hide_set(was_hidden)
                except ReferenceError:
                    continue  # Skip deleted cubes

        return {'CANCELLED'}

    def force_redraw(self):
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        return None

    def link_object(self, context, event, is_blocker):
        # Check if the current render engine supports light linking
        if not supports_light_linking(context.scene.render.engine):
            self.report({'WARNING'}, "Light linking is only available in Cycles or EEVEE render engines")
            return

        # Get object under cursor using the provided ray-casting code
        region = context.region
        rv3d = context.region_data
        coord = event.mouse_region_x, event.mouse_region_y

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
                # Default to a reasonable value if not in a 3D view
                near_clip = 0.1

        if is_ortho_camera:
            camera_matrix = context.scene.camera.matrix_world
            camera_direction = camera_matrix.to_3x3() @ Vector((0, 0, -1))
            mouse_pos_3d = view3d_utils.region_2d_to_location_3d(region, rv3d, coord, camera_matrix.translation)
            ray_origin = mouse_pos_3d + camera_direction * near_clip  # Adjust origin
            ray_direction = camera_direction
        else:
            ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
            ray_direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
            ray_origin += ray_direction * near_clip  # Adjust origin

        result, location, normal, index, object, matrix = context.scene.ray_cast(
            context.view_layer.depsgraph,
            ray_origin,
            ray_direction
        )

        if result and object and self.light:
            # Ensure the light is the active object
            context.view_layer.objects.active = self.light
            
            # Ensure the appropriate collection exists
            self.ensure_light_linking_collection(context, is_blocker)
            
            # Get the appropriate collection
            light_linking = self.light.light_linking
            collection = light_linking.blocker_collection if is_blocker else light_linking.receiver_collection
            
            if collection:
                collection_name = collection.name
                
                # Initialize link_state before any conditional blocks
                link_state = 'INCLUDE'
                if object.name in collection.objects:
                    link_state = object.get('light_linking_state', 'INCLUDE')
                
                if object.name not in collection.objects:
                    bpy.ops.object.select_all(action='DESELECT')
                    object.select_set(True)
                    
                    is_first_object = len(collection.objects) == 0
                    
                    if is_blocker:
                        result = bpy.ops.object.light_linking_blockers_link(link_state='INCLUDE')
                        if result == {'FINISHED'}:
                            if is_first_object:
                                status_message = f"{object.name} is now the only object that casts shadow from {self.light.name}"
                            else:
                                status_message = f"{object.name} now casts shadow from {self.light.name}"
                            object['light_linking_state'] = 'INCLUDE'
                        else:
                            status_message = f"Failed to link {object.name} to cast shadow from {self.light.name}"
                            return
                    else:
                        result = bpy.ops.object.light_linking_receivers_link(link_state='INCLUDE')
                        if result == {'FINISHED'}:
                            if is_first_object:
                                status_message = f"{object.name} is now the only object that receives light from {self.light.name}"
                            else:
                                status_message = f"{object.name} now receives light from {self.light.name}"
                            object['light_linking_state'] = 'INCLUDE'
                        else:
                            status_message = f"Failed to link {object.name} to receive light from {self.light.name}"
                            return
                else:
                    bpy.ops.object.select_all(action='DESELECT')
                    object.select_set(True)
                    
                    if link_state == 'INCLUDE':
                        is_only_object = len(collection.objects) == 1
                        
                        if is_blocker:
                            result = bpy.ops.object.light_linking_blockers_link(link_state='EXCLUDE')
                            if result == {'FINISHED'}:
                                if is_only_object:
                                    status_message = f"{object.name}, the only blocker, no longer casts shadow from {self.light.name}"
                                else:
                                    status_message = f"{object.name} no longer casts shadow from {self.light.name}"
                                object['light_linking_state'] = 'EXCLUDE'
                            else:
                                status_message = f"Failed to exclude {object.name} from casting shadow from {self.light.name}"
                                return
                        else:
                            result = bpy.ops.object.light_linking_receivers_link(link_state='EXCLUDE')
                            if result == {'FINISHED'}:
                                if is_only_object:
                                    status_message = f"{object.name}, the only receiver, now ignores light from {self.light.name}"
                                else:
                                    status_message = f"{object.name} now ignores light from {self.light.name}"
                                object['light_linking_state'] = 'EXCLUDE'
                            else:
                                status_message = f"Failed to exclude {object.name} from receiving light from {self.light.name}"
                                return
                    else:
                        if object.name in collection.objects:
                            collection.objects.unlink(object)
                            if is_blocker:
                                status_message = f"{object.name} removed from shadow linking collection for {self.light.name}"
                            else:
                                status_message = f"{object.name} removed from light linking collection for {self.light.name}"

                            # Check if the collection is now empty
                            if len(collection.objects) == 0:
                                # Check if the collection is used only for this light linking
                                is_unused = True
                                for obj in bpy.data.objects:
                                    if obj.type == 'LIGHT' and obj != self.light:
                                        if (is_blocker and obj.light_linking.blocker_collection == collection) or \
                                        (not is_blocker and obj.light_linking.receiver_collection == collection):
                                            is_unused = False
                                            break

                                if is_unused:
                                    # Remove the collection from all scenes and viewlayers
                                    for scene in bpy.data.scenes:
                                        if collection.name in scene.collection.children:
                                            scene.collection.children.unlink(collection)
                                        for layer in scene.view_layers:
                                            if collection.name in layer.layer_collection.children:
                                                layer.layer_collection.children.unlink(collection)
                                    
                                    # Remove the collection from Blender's data
                                    bpy.data.collections.remove(collection, do_unlink=True)
                                    
                                    # Purge the collection from memory
                                    bpy.data.orphans_purge(do_recursive=True)
                                    
                                    if is_blocker:
                                        self.light.light_linking.blocker_collection = None
                                    else:
                                        self.light.light_linking.receiver_collection = None
                                    
                                    # Set collection to None after deletion
                                    collection = None

                            if 'light_linking_state' in object:
                                del object['light_linking_state']
            
                # Check if collection still exists before accessing it
                if collection and collection_name in bpy.data.collections:
                    pass
                else:
                    pass
                
                # Deselect the object
                object.select_set(False)
                
                # Reselect the light
                self.light.select_set(True)
                context.view_layer.objects.active = self.light

                # Display the improved status message
                self.report({'INFO'}, status_message)

        else:
            self.report({'WARNING'}, "No object under mouse or no active light")

    def ensure_light_linking_collection(self, context, is_blocker):
        if not is_blender_version_compatible():
            return

        light = context.active_object
        if is_blocker:
            if not light.light_linking.blocker_collection:
                bpy.ops.object.light_linking_blocker_collection_new()
        else:
            if not light.light_linking.receiver_collection:
                bpy.ops.object.light_linking_receiver_collection_new()

    def create_new_collection(self, context, name):
        """Create a new collection and ensure it's properly linked to the view layer"""
        new_collection = bpy.data.collections.new(name=name)
        context.scene.collection.children.link(new_collection)
        

        layer_collection = find_layer_collection_recursive(
            context.view_layer.layer_collection, 
            new_collection.name
        )
        if layer_collection:
            layer_collection.exclude = False
            
        return new_collection

    def move_to_collection(self, collection, *objects):
        """Move objects to a collection, unlinking them from their current collections"""
        for obj in objects:
            for col in obj.users_collection:
                col.objects.unlink(obj)
            collection.objects.link(obj)

class LIGHTW_OT_AddInteractiveLight(bpy.types.Operator):
    """Add a light and enter interactive positioning mode"""
    bl_idname = "lightwrangler.add_interactive_light"
    bl_label = "Add Interactive Light"
    bl_options = {'UNDO'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    light_type: EnumProperty(
        items=[
            ('AREA', "Area", "Add an area light"),
            ('POINT', "Point", "Add a point light"),
            ('SPOT', "Spot", "Add a spot light"),
            ('SUN', "Sun", "Add a sun light")
        ],
        name="Type",
        default='AREA'
    )

    def execute(self, context):
        # Fix the preferences access
        prefs = context.preferences.addons[ADDON_MODULE_NAME].preferences
        
        # Create the selected light type based on render engine
        if context.scene.render.engine == 'octane' and self.light_type == 'AREA':
            # Create Octane area light
            bpy.ops.octane.quick_add_octane_area_light()
            light = context.active_object
        else:
            # Create standard Blender light
            bpy.ops.object.light_add(type=self.light_type, location=(0, 0, 9))
            light = context.active_object
            
        light["lw_newly_created"] = True
        
        # Organize lights if the preference is enabled
        if prefs.organize_lights:
            lights_collection = bpy.data.collections.get("Lights")
            if not lights_collection:
                lights_collection = bpy.data.collections.new("Lights")
                context.scene.collection.children.link(lights_collection)
                lights_collection.color_tag = 'COLOR_05'  # Blue color tag
            else:
                if lights_collection.color_tag != 'COLOR_05':
                    lights_collection.color_tag = 'COLOR_05'
            

            layer_collection = find_layer_collection_recursive(
                context.view_layer.layer_collection, 
                lights_collection.name
            )
            
            if layer_collection:
                # Auto-enable the collection if it's excluded
                if layer_collection.exclude:
                    layer_collection.exclude = False
                    
                # Now link the light to the collection
                if light.name not in lights_collection.objects:
                    lights_collection.objects.link(light)
                
                # Unlink from other collections
                for collection in light.users_collection:
                    if collection != lights_collection:
                        collection.objects.unlink(light)
        
        # Set initial light properties based on type and render engine
        if context.scene.render.engine == 'octane' and self.light_type == 'AREA':
            # Octane area lights might have different properties
            # The properties will be set by the quick_add_octane_area_light operator
            pass
        elif self.light_type == 'AREA':
            # Standard Blender area lights use all settings directly
            light.data.energy = prefs.initial_light_power
            light.data.size = prefs.initial_light_size
            light.data.spread = math.radians(180)  # Default to 180 degrees (full spread)
        elif self.light_type == 'POINT':
            # Point lights just use power, shadow size stays 0
            light.data.energy = prefs.initial_light_power
            light.data.shadow_soft_size = 0.0  # No shadow softness by default
        elif self.light_type == 'SPOT':
            # Spot lights use power only
            light.data.energy = prefs.initial_light_power
            light.data.spot_size = math.radians(45.0)  # Blender default
            light.data.spot_blend = 0.15  # Blender default
        elif self.light_type == 'SUN':
            # Sun lights use their own defaults
            light.data.energy = 1.0  # Blender default
            light.data.angle = math.radians(0.526)  # ~0.5 degrees
            
        # Set initial distance
        light["lw_last_offset"] = prefs.initial_light_distance
        
        # Set initial mode from preferences for new lights
        light["lw_last_mode"] = 'REFLECT'
        
        # Set initial pause state for new lights (always start active/unpaused)
        light["lw_last_pause_state"] = False
        
        # Mark as newly created
        light["lw_newly_created"] = True
        
        # Apply customizations based on render engine and light type
        if context.scene.render.engine == 'octane' and self.light_type == 'AREA':
            # Octane lights don't need additional customization
            pass
        elif self.light_type == 'AREA' and context.scene.render.engine == 'CYCLES':
            customization_mode = "Scrim" if prefs.use_scrim_for_area_lights else "Default"
            bpy.ops.lightwrangler.apply_custom_data_block(
                light_name=light.name,
                light_type=self.light_type,
                customization=customization_mode
            )
        else:
            bpy.ops.lightwrangler.apply_custom_data_block(
                light_name=light.name,
                light_type=self.light_type,
                customization="Default"
            )
        
        # Start interactive mode immediately
        bpy.ops.lightwrangler.interactive_mode('INVOKE_DEFAULT', mode='REFLECT')
        
        return {'FINISHED'}

class LIGHTW_OT_OpenPreferences(bpy.types.Operator):
    """Opens Light Wrangler Preferences"""
    bl_idname = "lightwrangler.open_preferences"
    bl_label = "Open Preferences"

    def execute(self, context):
        try:
            # Try the standard approach first
            section_name = get_preferences_section_name()
            if section_name == "Extensions":
                bpy.context.preferences.active_section = "EXTENSIONS"
            else:
                bpy.context.preferences.active_section = "ADDONS"
            bpy.ops.preferences.addon_show(module=ADDON_MODULE_NAME)
        except Exception as e:
            # If standard approach fails, try alternative methods
            try:
                # Method 2: Open preferences without addon_show
                bpy.ops.screen.userpref_show()
                section_name = get_preferences_section_name()
                if section_name == "Extensions":
                    bpy.context.preferences.active_section = "EXTENSIONS"
                else:
                    bpy.context.preferences.active_section = "ADDONS"
                
                # Try to expand our addon if possible
                for addon in context.preferences.addons:
                    if addon.module == ADDON_MODULE_NAME:
                        addon.preferences.show_expanded = True
                        break
                        
                self.report({'INFO'}, "Opened preferences window. Please find Light Wrangler in the list.")
            except Exception as fallback_error:
                # If all methods fail, provide manual instructions
                self.report({'ERROR'}, 
                    f"Unable to open preferences automatically. "
                    f"Please open Edit > Preferences > {get_preferences_section_name()} "
                    f"and search for 'Light Wrangler'")
                return {'CANCELLED'}
        
        return {"FINISHED"}

class LIGHTW_OT_DuplicateLight(bpy.types.Operator):
    """Duplicate the selected light and enter interactive positioning mode"""
    bl_idname = "lightwrangler.duplicate_light"
    bl_label = "Duplicate Light"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'LIGHT'

    def execute(self, context):
        # Get the source light
        source_light = context.active_object
        
        # Duplicate the light and its data
        new_light = source_light.copy()
        new_light.data = source_light.data.copy()
        
        # Copy all custom properties except lw_newly_created
        for key in source_light.keys():
            if key != "lw_newly_created":
                try:
                    # Check if the property is an IDPropertyGroup
                    prop_value = source_light[key]
                    if isinstance(prop_value, dict) and key in new_light and isinstance(new_light[key], dict):
                        # For IDPropertyGroup, copy individual values instead of direct assignment
                        for subkey in prop_value.keys():
                            try:
                                new_light[key][subkey] = prop_value[subkey]
                            except TypeError:
                                # Skip if we can't copy a specific subproperty
                                pass
                    else:
                        # For regular properties, direct assignment
                        new_light[key] = prop_value
                except (TypeError, AttributeError) as e:
                    print(f"Could not copy property {key}: {e}")
        
        # Mark as newly created for interactive operator
        new_light["lw_newly_created"] = True
        
        # Link to the same collections as the source light
        for collection in source_light.users_collection:
            collection.objects.link(new_light)
        
        # Check if the source light has associated volume cubes
        if "associated_volume_cubes" in source_light:
            # Get the list of volume cubes
            volume_cubes = list(source_light["associated_volume_cubes"])
            
            # Create a new list for the duplicated light
            new_light["associated_volume_cubes"] = []
            
            # Duplicate each volume cube
            for cube_name in volume_cubes:
                if cube_name in bpy.data.objects:
                    cube = bpy.data.objects[cube_name]
                    
                    # Duplicate the cube
                    new_cube = cube.copy()
                    if cube.data:
                        new_cube.data = cube.data.copy()
                    
                    # Copy materials
                    if len(cube.material_slots) > 0 and cube.material_slots[0].material:
                        material = cube.material_slots[0].material
                        new_material = material.copy()
                        new_cube.material_slots[0].material = new_material
                    
                    # Link to the same collections
                    for collection in cube.users_collection:
                        collection.objects.link(new_cube)
                    
                    # Update parent relationship and ensure correct positioning
                    # First clear any existing parent relationship
                    if new_cube.parent:
                        matrix_world = new_cube.matrix_world.copy()
                        new_cube.parent = None
                        new_cube.matrix_world = matrix_world
                    
                    # Now set the parent to the new light with the correct transformation
                    new_cube.parent = new_light
                    new_cube.matrix_parent_inverse = new_light.matrix_world.inverted()
                    
                    # Update custom properties
                    new_cube["volume_parent_light"] = new_light.name
                    new_cube["is_gobo_volume"] = True
                    
                    # Add to the new light's list
                    new_volume_cubes = list(new_light["associated_volume_cubes"])
                    new_volume_cubes.append(new_cube.name)
                    new_light["associated_volume_cubes"] = new_volume_cubes
                    
                    # Update drivers to point to the new light's node tree
                    # Viewport and render visibility drivers
                    if new_cube.animation_data and new_cube.animation_data.drivers:
                        for fcurve in new_cube.animation_data.drivers:
                            if fcurve.data_path in ["hide_viewport", "hide_render"]:
                                for var in fcurve.driver.variables:
                                    if var.type == 'SINGLE_PROP' and var.targets[0].id_type == 'NODETREE':
                                        var.targets[0].id = new_light.data.node_tree
                    
                    # Find and update Gobo Volume node group drivers
                    if len(new_cube.material_slots) > 0 and new_cube.material_slots[0].material:
                        new_material = new_cube.material_slots[0].material
                        if new_material.node_tree:
                            for node in new_material.node_tree.nodes:
                                if node.type == 'GROUP' and node.node_tree and "Gobo Volume" in node.node_tree.name:
                                    # Recreate drivers for Density (input 0)
                                    if len(node.inputs) > 0:
                                        # Remove existing driver if any
                                        try:
                                            node.inputs[0].driver_remove("default_value")
                                        except:
                                            pass
                                        
                                        # Create new driver for Density
                                        create_node_tree_driver(
                                            node.inputs[0],
                                            "default_value",
                                            new_light.data,
                                            'LIGHT',
                                            'nodes["Group"].inputs[5].default_value',
                                            "var"
                                        )
                                    
                                    # Recreate drivers for Uniformity (input 1)
                                    if len(node.inputs) > 1:
                                        # Remove existing driver if any
                                        try:
                                            node.inputs[1].driver_remove("default_value")
                                        except:
                                            pass
                                        
                                        # Create new driver for Uniformity
                                        create_node_tree_driver(
                                            node.inputs[1],
                                            "default_value",
                                            new_light.data,
                                            'LIGHT',
                                            'nodes["Group"].inputs[6].default_value',
                                            "var"
                                        )
        
        # Select and make active
        source_light.select_set(False)
        new_light.select_set(True)
        context.view_layer.objects.active = new_light
        
        # Start interactive mode
        bpy.ops.lightwrangler.interactive_mode('INVOKE_DEFAULT', mode='REFLECT')
        
        return {'FINISHED'}

class LIGHTW_OT_TrackToTarget(bpy.types.Operator):
    """Constrain selected area light(s) to a target, which may be a new or existing empty/object"""
    bl_idname = "lightwrangler.track_to_target"
    bl_label = "Track to Target"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        lights = [
            obj
            for obj in context.selected_objects
            if obj.type == "LIGHT"
            and obj.data.type in {"AREA", "SPOT"}
        ]
        others = [obj for obj in context.selected_objects if obj.type != "LIGHT"]
        return lights and (len(others) <= 1)

    def execute(self, context):
        lights = [
            obj
            for obj in context.selected_objects
            if obj.type == "LIGHT"
            and obj.data.type in {"AREA", "SPOT"}
        ]
        others = [obj for obj in context.selected_objects if obj.type != "LIGHT"]

        if len(lights) == 1 and len(others) == 0:
            self.track_to_new_empty(context, lights[0])
        elif len(lights) > 1 and len(others) == 0:
            self.track_to_new_empty(context, *lights)
        elif len(others) == 1:
            for light in lights:
                self.add_track_to_constraint(light, others[0])

        return {"FINISHED"}

    def track_to_new_empty(self, context, *lights):
        reference_light = context.active_object
        origin = reference_light.location
        direction = reference_light.rotation_euler.to_matrix() @ Vector((0, 0, -1))
        result, location, normal, index, object, matrix = context.scene.ray_cast(
            context.view_layer.depsgraph, origin, direction
        )

        if result:
            average_dimension = sum(object.dimensions) / 3
            size_cm = (
                average_dimension / 20 * bpy.context.scene.unit_settings.scale_length
            )
            size = min(max(size_cm, 0.01), 0.1)
            bpy.ops.object.empty_add(type="SPHERE", location=location, radius=size)
            empty = context.active_object

            light_index = (
                "." + reference_light.name.split(".")[-1]
                if "." in reference_light.name
                else ""
            )
            light_base_name = (
                ".".join(reference_light.name.split(".")[:-1])
                if "." in reference_light.name
                else reference_light.name
            )
            empty.name = f"{light_base_name}{light_index}_target"

            collection_name = "Lights" if len(lights) > 1 else reference_light.name
            new_collection = self.create_new_collection(context, collection_name)

            if new_collection:
                empty.name = f"{new_collection.name}_target"

            for light in lights:
                self.add_track_to_constraint(light, empty)

            self.move_to_collection(new_collection, *lights, empty)

    def add_track_to_constraint(self, light, target):
        constraint = light.constraints.new("TRACK_TO")
        constraint.target = target
        constraint.track_axis = "TRACK_NEGATIVE_Z"
        constraint.up_axis = "UP_Y"

    def create_new_collection(self, context, name):
        """Create a new collection and ensure it's properly linked to the view layer"""
        new_collection = bpy.data.collections.new(name=name)
        context.scene.collection.children.link(new_collection)
        
        # Ensure the collection is visible in the view layer
        
        layer_collection = find_layer_collection_recursive(
            context.view_layer.layer_collection, 
            new_collection.name
        )
        if layer_collection:
            layer_collection.exclude = False
            
        return new_collection

    def move_to_collection(self, collection, *objects):
        """Move objects to a collection, unlinking them from their current collections"""
        for obj in objects:
            for col in obj.users_collection:
                col.objects.unlink(obj)
            collection.objects.link(obj)

class LIGHTW_OT_ClearTracking(bpy.types.Operator):
    """Disable tracking constraints while preserving orientation"""
    bl_idname = "lightwrangler.clear_tracking"
    bl_label = "Clear Tracking"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        light = context.active_object
        return light and light.type == "LIGHT" and any(c.type == 'TRACK_TO' and not c.mute for c in light.constraints)

    def execute(self, context):
        light = context.active_object

        # Get the final world matrix of the light (including constraint effects)
        final_matrix = light.matrix_world.copy()

        # Find and disable TRACK_TO constraints
        for constraint in light.constraints:
            if constraint.type == 'TRACK_TO':
                constraint.mute = True

        # Apply the final transformation back to the light
        light.matrix_world = final_matrix

        return {'FINISHED'}

class LIGHTW_OT_EnableTracking(bpy.types.Operator):
    """Re-enable muted tracking constraints"""
    bl_idname = "lightwrangler.enable_tracking"
    bl_label = "Enable Tracking"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        light = context.active_object
        return light and light.type == "LIGHT" and any(c.type == 'TRACK_TO' and c.mute for c in light.constraints)

    def execute(self, context):
        light = context.active_object

        # Find and enable TRACK_TO constraints
        for constraint in light.constraints:
            if constraint.type == 'TRACK_TO':
                constraint.mute = False

        return {'FINISHED'}

# Registration
classes = (
    LIGHTW_OT_InteractiveOperator,
    LIGHTW_OT_AddInteractiveLight,
    LIGHTW_OT_OpenPreferences,
    LIGHTW_OT_DuplicateLight,
    LIGHTW_OT_TrackToTarget,
    LIGHTW_OT_ClearTracking,
    LIGHTW_OT_EnableTracking,
)

def register():
    from ..utils import logger
    logger.start_section("Operator Classes")
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            logger.log_registration(cls.__name__)
        except Exception as e:
            logger.log_registration(cls.__name__, False, str(e))
    
    logger.end_section()

def unregister():
    from ..utils import logger
    logger.start_section("Operator Classes")
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
            logger.log_unregistration(cls.__name__)
        except Exception as e:
            logger.log_unregistration(cls.__name__, False, str(e))
    
    logger.end_section()
