import bpy
from bpy.types import GizmoGroup
from mathutils import Vector, Matrix
import math
from ..utils.utils import raycast_from_mouse
from ..utils.drawing import draw_orbit_visualization

class LIGHTW_GGT_light_position_gizmos(GizmoGroup):
    bl_idname = "LIGHTW_GGT_light_position_gizmos"
    bl_label = "Light Position Gizmos"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT'}

    # Store references to gizmos
    reflect_gizmo = None
    direct_gizmo = None
    orbit_gizmo = None
    _last_mode = None
    _last_active_state = None  # Track active state

    @classmethod
    def poll(cls, context):
        # Only show when a light is selected and it's not a point light
        is_valid = (context.object and 
                context.object.type == 'LIGHT' and 
                context.object.data.type != 'POINT')
        # print(f"[GIZMO] Poll called, valid: {is_valid}")
        return is_valid

    def get_current_mode(self, context):
        """Get the current mode based on operator state"""
        light_obj = context.object
        mode = light_obj.get("lw_last_mode", "DIRECT")
        # print(f"[GIZMO] Current mode: {mode}")
        return mode

    def setup(self, context):
        # Get the current light and its mode
        # print("[GIZMO] Setup called")
        
        current_mode = self.get_current_mode(context)
        
        # Define colors based on active state
        is_active = context.scene.lightwrangler_props.is_interactive_mode_active
        # print(f"[GIZMO] Interactive mode active: {is_active}")

        theme = context.preferences.themes[0]
        try:
            color = theme.view_3d.object_active[:3]
        except (AttributeError, IndexError):
            color = (0.95, 0.95, 0.97)

        # Clear existing gizmos
        self.clear_gizmos()
        
        # Create gizmo for current mode
        if current_mode == "REFLECT":
            self.create_gizmo("REFLECT", "GIZMO_GT_move_3d", "RING_2D", {"ALIGN_VIEW"}, 0.055, color)
        elif current_mode == "DIRECT":
            self.create_gizmo("DIRECT", "GIZMO_GT_move_3d", "RING_2D", {"FILL", "ALIGN_VIEW"}, 0.055, color)
        elif current_mode == "ORBIT":
            self.create_gizmo("ORBIT", "GIZMO_GT_dial_3d", "RING_2D", {"FILL_SELECT", "ANGLE_MIRROR"}, 0.12, color)
        
        # Store current mode and active state
        self._last_mode = current_mode
        self._last_active_state = is_active

    def create_gizmo(self, mode, gizmo_type, draw_style, draw_options, scale_basis, color):
        # print(f"[GIZMO] Creating gizmo for mode: {mode}")
        mpr = self.gizmos.new(gizmo_type)
        if gizmo_type != "GIZMO_GT_dial_3d":
            mpr.draw_style = draw_style
        mpr.draw_options = draw_options
        mpr.scale_basis = scale_basis
        mpr.color = color
        mpr.alpha = 0.8
        mpr.color_highlight = tuple(min(c * 1.2, 1.0) for c in color)
        mpr.alpha_highlight = 1.0
        
        # Set up operator without mode to match TAB key behavior
        # print("[GIZMO] Setting up operator target")
        op_props = mpr.target_set_operator("lightwrangler.interactive_mode")
        if op_props:
            # print("[GIZMO] Operator properties set")
            # print(f"[GIZMO] Mode: {mode}")
            # print(f"[GIZMO] Operator properties: {dir(op_props)}")
            pass
        else:
            # print("[GIZMO] No operator properties available")
            pass
        
        # Store reference based on mode
        if mode == "REFLECT":
            self.reflect_gizmo = mpr
        elif mode == "DIRECT":
            self.direct_gizmo = mpr
        elif mode == "ORBIT":
            self.orbit_gizmo = mpr
        
        # Initial matrix setup
        light_obj = bpy.context.object
        mpr.matrix_basis = light_obj.matrix_world.normalized()
        # print("[GIZMO] Gizmo creation complete")

    def clear_gizmos(self):
        # print("[GIZMO] Clearing gizmos")
        for gz in self.gizmos:
            self.gizmos.remove(gz)
        self.reflect_gizmo = None
        self.direct_gizmo = None
        self.orbit_gizmo = None

    def refresh(self, context):
        light_obj = context.object
        if not light_obj or light_obj.type != 'LIGHT':
            # print("[GIZMO] Refresh - No valid light object")
            return

        # Get current mode and active state
        current_mode = self.get_current_mode(context)
        is_active = context.scene.lightwrangler_props.is_interactive_mode_active
        # print(f"[GIZMO] Refresh - Mode: {current_mode}, Active: {is_active}")
        # print(f"[GIZMO] Last mode: {self._last_mode}, Last active: {self._last_active_state}")
        
        # If mode or active state has changed, recreate gizmos
        if current_mode != self._last_mode or is_active != self._last_active_state:
            # print("[GIZMO] Mode or active state changed, recreating gizmos")
            self.setup(context)
            return
        
        # Get the current gizmo
        current_gizmo = (self.reflect_gizmo if current_mode == "REFLECT" else
                        self.direct_gizmo if current_mode == "DIRECT" else
                        self.orbit_gizmo)
        
        if current_gizmo:
            # print("[GIZMO] Current gizmo found, updating position")
            depsgraph = context.evaluated_depsgraph_get()
            self.update_gizmo_position(current_gizmo, light_obj, depsgraph)
        else:
            # print("[GIZMO] No current gizmo found")
            pass

    def update_gizmo_position(self, mpr, light_obj, depsgraph):
        # print("[GIZMO] Updating gizmo position")
        # Get the light's current forward direction
        light_forward = (light_obj.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))).normalized()
        
        # Check for stored target
        target = light_obj.get("target", None)
        if target is not None:
            # print(f"[GIZMO] Found target: {target}")
            # For all modes, validate the target by checking direction
            if bpy.context.scene.lightwrangler_props.is_interactive_mode_active:
                # During operator, always use stored target
                # print("[GIZMO] Using stored target (interactive mode)")
                mpr.matrix_basis = Matrix.Translation(Vector(target))
                return
            else:
                # After operator ends, validate target
                light_to_target = (Vector(target) - light_obj.location).normalized()
                angle = light_forward.angle(light_to_target)
                if angle <= math.radians(0.2):  # Small tolerance
                    # Target is still valid
                    # print("[GIZMO] Using stored target (valid angle)")
                    mpr.matrix_basis = Matrix.Translation(Vector(target))
                    return

        # Fallback to raycast if target is invalid or doesn't exist
        # print("[GIZMO] Using raycast fallback")
        ray_origin = light_obj.location
        ray_direction = light_forward
        result, location, normal, index, object, matrix = depsgraph.scene.ray_cast(
            depsgraph, ray_origin, ray_direction
        )

        if result:
            # print(f"[GIZMO] Raycast hit at: {location}")
            mpr.matrix_basis = Matrix.Translation(location)
        else:
            # Place gizmo at a default distance along the light's forward direction
            default_distance = light_obj.get("lw_last_offset", 10.0)
            fallback_location = ray_origin + ray_direction * default_distance
            # print(f"[GIZMO] Using fallback location: {fallback_location}")
            mpr.matrix_basis = Matrix.Translation(fallback_location)

    def draw_prepare(self, context):
        """Update gizmos before drawing"""
        # print("[GIZMO] Draw prepare called")
        self.refresh(context)

# Registration
def register():
    from ..utils import logger
    try:
        bpy.utils.register_class(LIGHTW_GGT_light_position_gizmos)
        logger.log_registration("LIGHTW_GGT_light_position_gizmos")
    except Exception as e:
        logger.log_registration("LIGHTW_GGT_light_position_gizmos", False, str(e))

def unregister():
    from ..utils import logger
    try:
        bpy.utils.unregister_class(LIGHTW_GGT_light_position_gizmos)
        logger.log_unregistration("LIGHTW_GGT_light_position_gizmos")
    except Exception as e:
        logger.log_unregistration("LIGHTW_GGT_light_position_gizmos", False, str(e)) 