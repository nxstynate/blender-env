import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, FloatProperty
from mathutils import Vector, Matrix, Euler
import math
import gpu
from gpu_extras.batch import batch_for_shader
import blf
from ..utils.hdri import find_hdri_domes_and_mapping_nodes

class LIGHTW_OT_HDRIRotate(Operator):
    bl_idname = "light_wrangler.rotate_hdri"
    bl_label = "Rotate HDRI"
    bl_options = {'GRAB_CURSOR', 'BLOCKING'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.first_mouse = Vector((0, 0))
        self.initial_rotations = {}
        self.initial_object_rotations = {}
        self.mapping_nodes = []
        self.dome_objects = []
        self.is_dragging = False
        self._handle = None
        self.mouse_delta = 0.0
        self.initial_area = None
        self.initial_region = None

    def draw_callback_px(self, _self, context):
        if not self.is_dragging:
            return

        # Only draw in the viewport where we started
        if context.area != self.initial_area:
            return

        # Use the stored initial region for drawing
        region = self.initial_region
        ui_scale = bpy.context.preferences.view.ui_scale * 0.6

        # Adjust dimensions and sizes based on UI scale
        text_size = int(16 * ui_scale)
        height = int(20 * ui_scale)
        major_tick_height = int(15 * ui_scale)
        indicator_width = int(2 * ui_scale)
        tick_line_width = 1.0 * ui_scale  # Adjust line width for ticks

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        width = region.width
        y_position = int(0 * ui_scale)

        current_rotation = 0.0
        if self.mapping_nodes and len(self.mapping_nodes) > 0:
            first_node = self.mapping_nodes[0]
            if first_node:
                current_rotation = first_node.inputs['Rotation'].default_value[2]
        current_degrees = math.degrees(current_rotation)

        # Background strip
        vertices = (
            (0, y_position), (width, y_position),
            (width, y_position + height), (0, y_position + height)
        )
        indices = ((0, 1, 2), (2, 3, 0))
        batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
        shader.bind()
        shader.uniform_float("color", (0.2, 0.2, 0.2, 0.3))
        batch.draw(shader)

        # Fixed center indicator
        center_x = width / 2
        indicator_vertices = (
            (center_x - indicator_width, y_position),
            (center_x + indicator_width, y_position),
            (center_x + indicator_width, y_position + height + 5 * ui_scale),
            (center_x - indicator_width, y_position + height + 5 * ui_scale)
        )
        indicator_indices = ((0, 1, 2), (2, 3, 0))
        indicator_batch = batch_for_shader(shader, 'TRIS', {"pos": indicator_vertices}, indices=indicator_indices)
        shader.uniform_float("color", (1, 1, 1, 0.8))
        indicator_batch.draw(shader)

        # Set text size and color
        blf.color(0, 1, 1, 1, 0.8)
        blf.size(0, text_size)

        base_tick = math.floor(current_degrees / 15)  # Changed from 45 to 15
        
        # Increased range to maintain similar visible span (-24 to 48 instead of -8 to 16)
        for i in range(-24, 48):
            tick_degrees = (base_tick + i) * 15  # Changed from 45 to 15
            diff = tick_degrees - current_degrees
            x = center_x - (diff / 15) * (width / 24)  # Changed from + to -

            # Calculate distance from center using stronger easing function
            distance_from_center = abs(diff) / (15 * 24)  # Adjusted for new degree spacing
            # Stronger cubic easing
            ease = 1 - (distance_from_center * distance_from_center * 0.9)
            
            # More dramatic tick height variation (50% to 100%)
            tick_height = major_tick_height * (0.5 + (0.5 * ease))
            
            # Vary tick width (0.5 to 2.0 times the base width)
            tick_width = tick_line_width * (0.5 + (1.5 * ease))
            gpu.state.line_width_set(tick_width)
            
            # Draw individual tick with its own width
            tick_vertices = ((x, y_position), (x, y_position + tick_height))
            tick_batch = batch_for_shader(shader, 'LINES', {"pos": tick_vertices})
            shader.uniform_float("color", (1, 1, 1, 0.2 + (0.3 * ease)))
            tick_batch.draw(shader)

            # Only draw text for every 45 degrees to avoid crowding
            if tick_degrees % 45 == 0:
                current_text_size = int(text_size * (0.6 + (0.4 * ease)))
                blf.size(0, current_text_size)
                text_alpha = 0.2 + (0.8 * ease)
                blf.color(0, 1, 1, 1, text_alpha)
                text_y_offset = (text_size * (1 - ease) * 0.4)
                blf.position(0, x - 10 * ui_scale, y_position + height + 10 * ui_scale - text_y_offset, 0)
                blf.draw(0, f"{int(tick_degrees)}°")


    def modal(self, context, event):
        # Update current mouse position
        self.current_mouse_x = event.mouse_x
        self.current_mouse_y = event.mouse_y
        
        context.area.tag_redraw()
        
        if event.type == 'MOUSEMOVE' and self.is_dragging:
            context.window.cursor_modal_set('SCROLL_X')
            # Calculate raw rotation
            raw_delta = (event.mouse_x - self.first_mouse.x) * 0.0005
            
            # Convert to degrees, snap to nearest 0.1 degree, then back to radians
            degrees = math.degrees(raw_delta)
            snapped_degrees = round(degrees / 0.1) * 0.1
            snapped_radians = math.radians(snapped_degrees)
            
            # Update world HDRI mapping nodes
            for mapping_node in self.mapping_nodes:
                if mapping_node:
                    initial_rot = self.initial_rotations.get(mapping_node.name, 0)
                    current_rotation = mapping_node.inputs['Rotation'].default_value
                    current_rotation[2] = initial_rot + snapped_radians
            
            # Update dome objects
            for obj in self.dome_objects:
                if obj:
                    initial_rot = self.initial_object_rotations.get(obj.name, (0, 0, 0))
                    obj.rotation_euler.z = initial_rot[2] - snapped_radians

        elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'RIGHTMOUSE'}:
            if event.value in {'PRESS', 'RELEASE'}:
                self.is_dragging = False
                context.window.cursor_modal_restore()
                if self._handle is not None:
                    context.space_data.draw_handler_remove(self._handle, 'WINDOW')
                return {'FINISHED'}

        elif event.type == 'ESC':
            context.window.cursor_modal_restore()
            # Restore initial rotations
            for mapping_node in self.mapping_nodes:
                if mapping_node:
                    initial_rot = self.initial_rotations.get(mapping_node.name, 0)
                    mapping_node.inputs['Rotation'].default_value[2] = initial_rot
            
            for obj in self.dome_objects:
                if obj:
                    initial_rot = self.initial_object_rotations.get(obj.name, (0, 0, 0))
                    obj.rotation_euler = initial_rot
            
            if self._handle is not None:
                context.space_data.draw_handler_remove(self._handle, 'WINDOW')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.space_data.shading.type != 'RENDERED':
            self.report({'WARNING'}, "HDRI rotation only works in Rendered viewport mode")
            return {'CANCELLED'}

        # Store the initial viewport area and region
        self.initial_area = context.area
        self.initial_region = context.region

        self.first_mouse = Vector((event.mouse_x, event.mouse_y))
        self.is_dragging = True
        
        context.window.cursor_modal_set('SCROLL_X')
        
        self.mapping_nodes, self.dome_objects = find_hdri_domes_and_mapping_nodes()
        
        self.initial_rotations.clear()
        self.initial_object_rotations.clear()
        
        for mapping_node in self.mapping_nodes:
            if mapping_node:
                self.initial_rotations[mapping_node.name] = mapping_node.inputs['Rotation'].default_value[2]
        
        for obj in self.dome_objects:
            if obj:
                self.initial_object_rotations[obj.name] = obj.rotation_euler.copy()
        
        if not (self.mapping_nodes or self.dome_objects):
            self.report({'WARNING'}, "No HDRI environments found")
            context.window.cursor_modal_restore()
            return {'CANCELLED'}
        
        args = (self, context)
        self._handle = context.space_data.draw_handler_add(
            self.draw_callback_px, args, 'WINDOW', 'POST_PIXEL'
        )
        
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

# Registration
classes = (
    LIGHTW_OT_HDRIRotate,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls) 