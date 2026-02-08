import bpy
import os
from .operators import LIGHTW_OT_InteractiveOperator
from ..utils.blender_compat import create_node_tree_driver
from ..utils.texture_manager import (
    is_video_file,
    get_video_frame_rate_from_blender,
    append_gobo_node_group,
    append_hdri_node_group,
    append_ies_node_group,
    append_scrim_node_group,
    apply_scrim_to_light,
    apply_gobo_to_light,
    apply_hdri_to_light,
    apply_ies_to_light
)
from bpy.props import StringProperty, EnumProperty, BoolProperty
from bpy.app.handlers import persistent
import math
import time
from mathutils import Vector, Matrix
import gpu
import blf
from bpy_extras import view3d_utils
from ..utils.drawing import draw_orbit_visualization
from ..utils.utils import raycast_from_mouse, hex_to_rgb, hide_viewport_elements, unhide_viewport_elements
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
    handle_light_linking
)
import bpy.types
import bpy_extras
from ..utils.colors import get_color
from .. import ADDON_MODULE_NAME
from ..utils import logger
from ..utils.blender_compat import world_has_nodes

# Global variable for tracking light updates
is_updating_light = False
is_handling_selection = False

def hextorgb(hex_color):
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16)/255 for i in (0, 2, 4))

class LIGHTW_GGT_light_controls(bpy.types.GizmoGroup):
    bl_idname = "LIGHTW_GGT_light_controls"
    bl_label = "Viewport Gizmos"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE', 'SHOW_MODAL_ALL', 'SELECT'}

    # Constants for gizmo positioning (to be adjusted to match Blender's built-in gizmos)
    GIZMO_MARGIN_RIGHT = 28  # Distance from right edge
    GIZMO_MARGIN_TOP = 347    # Distance from top edge
    GIZMO_SCALE = 14.2       # Size of the gizmo

    @classmethod
    def poll(cls, context):
        # Don't show gizmos while interactive operator is running
        if context.scene.lightwrangler_props.is_interactive_mode_active:
            return False
        return context.object and context.object.type == 'LIGHT'

    def setup(self, context):
        from ..utils.viewport_positioning import calculate_gizmo_scale
        
        alpha = 0.8
        color = (0.15, 0.15, 0.15)  # Base gray for inactive state
        color_highlight = (0.4, 0.4, 0.4)  # Lighter gray for highlight
        alpha_highlight = 0.8
        scale_basis = calculate_gizmo_scale(context)

        # Visibility toggle gizmo
        self.visibility_gizmo = self.create_gizmo(context, "GIZMO_GT_button_2d", "OUTLINER_OB_LIGHT", alpha, color, color_highlight, alpha_highlight, scale_basis, "lightwrangler.toggle_visibility", "Toggle Light Visibility")

    def create_gizmo(self, context, gizmo_type, icon, alpha, color, color_highlight, alpha_highlight, scale_basis, operator, description):
        gzm = self.gizmos.new(gizmo_type)
        gzm.icon = icon
        gzm.draw_options = {'BACKDROP', 'OUTLINE'}
        gzm.scale_basis = scale_basis
        gzm.color = color
        gzm.alpha = alpha
        gzm.color_highlight = color_highlight
        gzm.alpha_highlight = alpha_highlight
        gzm.target_set_operator(operator)
        gzm.use_draw_modal = True
        return gzm

    def is_world_emitting(self, scene):
        """Check if the World is emitting light"""
        if scene.world and world_has_nodes(scene.world):
            for node in scene.world.node_tree.nodes:
                if node.type in {'BACKGROUND', 'EMISSION', 'BSDF_PRINCIPLED'}:
                    if not node.mute and node.inputs.get('Strength') and node.inputs['Strength'].default_value > 0:
                        return True
        return False

    def draw_prepare(self, context):
        from ..utils.viewport_positioning import calculate_gizmo_position
        from .. import ADDON_MODULE_NAME
        
        light = context.object
        scene = context.scene

        # Get row position from preferences
        try:
            prefs = context.preferences.addons[ADDON_MODULE_NAME].preferences
            row_position = prefs.gizmo_row_position
        except:
            row_position = 5

        # Calculate position using new row-based system
        pos_x, pos_y = calculate_gizmo_position(context, row_position)

        # Check if isolation was actively performed
        is_actively_isolated = scene.lightwrangler_props.is_isolated

        # Update gizmo color based on the isolation state
        if light:
            if is_actively_isolated:
                self.visibility_gizmo.color = context.preferences.themes[0].view_3d.object_active  # Theme color for active state
            else:
                # Gray colors for normal state
                self.visibility_gizmo.color = (0.35, 0.35, 0.35) if light.hide_viewport else (0.15, 0.15, 0.15)

        # Apply the calculated positions to the gizmo matrix
        self.visibility_gizmo.matrix_basis[0][3] = pos_x
        self.visibility_gizmo.matrix_basis[1][3] = pos_y
        self.visibility_gizmo.matrix_basis[2][3] = 0  # Z position remains 0 for 2D gizmos

last_activation_time = {}

class LIGHTW_OT_confirm_cycles_switch(bpy.types.Operator):
    bl_idname = "lightwrangler.confirm_cycles_switch"
    bl_label = "Switch to Cycles"
    bl_description = "Switch to Cycles render engine for light customization"
    bl_options = {'INTERNAL'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    light_name: bpy.props.StringProperty()
    light_type: bpy.props.StringProperty()
    customization: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.render.engine = 'CYCLES'
        bpy.ops.lightwrangler.apply_custom_data_block(
            light_name=self.light_name,
            light_type=self.light_type,
            customization=self.customization
        )
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def draw(self, context):
        self.layout.label(text="Switch to Cycles to edit light customization?")

class LIGHTW_OT_confirm_tracking_removal(bpy.types.Operator):
    bl_idname = "lightwrangler.confirm_tracking_removal"
    bl_label = "Disable Tracking to Move Light"
    bl_description = "Disable tracking constraint to allow light manipulation"
    bl_options = {'INTERNAL'}

    mode: bpy.props.StringProperty()

    def execute(self, context):
        # Call the main interactive operator with tracking confirmation flag
        bpy.ops.lightwrangler.interactive_mode(
            'INVOKE_DEFAULT',
            mode=self.mode,
            tracking_confirmed=True
        )
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Light tracking prevents repositioning.")
        layout.label(text="Remove tracking to move the light?")

class LIGHTW_OT_apply_custom_data_block(bpy.types.Operator):
    bl_idname = "lightwrangler.apply_custom_data_block"
    bl_label = "Apply Custom Data Block"
    bl_options = {"REGISTER", "UNDO"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    bl_description = "Apply a specific customization to the selected light"
    light_name: bpy.props.StringProperty()
    light_type: bpy.props.StringProperty()
    customization: bpy.props.StringProperty()

    @classmethod
    def description(cls, context, properties):
        descriptions = {
            "Gobo": "Apply a Gobo texture to the light",
            "HDRI": "Apply HDRI texture to the light",
            "IES": "Apply an IES light profile to the light",
            "Scrim": "Apply a Scrim node group",
            "Default": "Don't apply any customizations",
        }
        return descriptions.get(properties.customization, cls.bl_description)

    def execute(self, context):
        # Get addon preferences
        addon_prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
        initial_light_temp = addon_prefs.initial_light_temp
        new_block_created = False
        light_obj = bpy.data.objects.get(self.light_name)
        if not light_obj:
            self.report({"ERROR"}, "Light object not found.")
            return {"CANCELLED"}

        if light_obj.name.startswith("Starlight Sun"):
            return {"CANCELLED"}

        # Store original settings before any changes
        original_settings = {}
        if light_obj.data:
            original_settings = self.store_light_settings(light_obj.data)

        id_prop_key = f"custom_data_block_{self.light_type}_{self.customization}"
        
        # Get or create the new data block
        if id_prop_key in light_obj:
            existing_data_block = light_obj[id_prop_key]
            if existing_data_block and existing_data_block.name in bpy.data.lights:
                new_data_block = existing_data_block
                new_block_created = False  # Existing block, don't apply settings
            else:
                self.report(
                    {"ERROR"},
                    "Referenced data block not found or invalid. A new one will be created.",
                )
                new_data_block = self.create_new_data_block(light_obj, id_prop_key)
                new_block_created = True
        elif self.customization == "Default" and not any(prop.startswith("custom_data_block_") for prop in light_obj.keys()):
            new_data_block = self.refurbish_default_data_block(light_obj, id_prop_key)
            new_block_created = True
        else:
            new_data_block = self.create_new_data_block(light_obj, id_prop_key)
            new_block_created = True

        # Only apply settings and setup nodes for new data blocks
        if new_block_created:
            if original_settings:
                self.apply_stored_settings(new_data_block, original_settings)

            # Set up node groups and customization only for new blocks
            if self.customization == "Gobo":
                append_gobo_node_group()
                # Inherit folder from scene's last used gobo folder
                if not new_data_block.gobo_root_folder and bpy.context.scene.last_gobo_folder:
                    new_data_block.gobo_root_folder = bpy.context.scene.last_gobo_folder
                    # Update categories for this folder
                    from ..utils.preview_manager import update_light_categories
                    update_light_categories(new_data_block, 'gobo')
                # Don't set enum value as it may be empty
                apply_gobo_to_light(light_obj, "Window-004")
            elif self.customization == "HDRI":
                append_hdri_node_group()
                # Inherit folder from scene's last used HDRI folder
                if not new_data_block.hdri_root_folder and bpy.context.scene.last_hdri_folder:
                    new_data_block.hdri_root_folder = bpy.context.scene.last_hdri_folder
                    # Update categories for this folder
                    from ..utils.preview_manager import update_light_categories
                    update_light_categories(new_data_block, 'hdri')
                # Don't set enum value as it may be empty
                apply_hdri_to_light(light_obj, "03_Octabox_Medium_01_spread155")
            elif self.customization == "IES":
                append_ies_node_group()
                # Inherit folder from scene's last used IES folder
                if not new_data_block.ies_root_folder and bpy.context.scene.last_ies_folder:
                    new_data_block.ies_root_folder = bpy.context.scene.last_ies_folder
                    # Update categories for this folder
                    from ..utils.preview_manager import update_light_categories
                    update_light_categories(new_data_block, 'ies')
                # Don't set enum value as it may be empty
                apply_ies_to_light(light_obj, os.path.join(os.path.dirname(os.path.dirname(__file__)), "ies_previews", "accent-light-004.jpg"))
            elif self.customization == "Scrim":
                append_scrim_node_group()
                apply_scrim_to_light(new_data_block)

            # Apply initial color temp only for new blocks
            self.apply_initial_color_temp(new_data_block, initial_light_temp)

        # Now it's safe to assign the data block
        light_obj.data = new_data_block
        light_obj.data.type = self.light_type

        if hasattr(light_obj.data, "photographer"):
            photographer_settings = light_obj.data.photographer
            if not (hasattr(photographer_settings, "gobo") and photographer_settings.gobo) and not (hasattr(photographer_settings, "ies") and photographer_settings.ies):
                self.ensure_node_group_connection(light_obj.data, self.customization)

        try:
            light_obj["customization"] = self.customization
            light_obj[f"last_customization_{self.light_type}"] = self.customization
        except Exception as e:
            logger.error(f"Failed to set customization properties: {e}")
            
        if addon_prefs.organize_lights and context.scene.render.engine in ["CYCLES", "octane"]:
            logger.debug(f"Light renaming triggered for {light_obj.name}")
            old_name = light_obj.name
            light_obj.name = new_data_block.name
            logger.debug(f"Renamed light from {old_name} to {light_obj.name}")
            
            # Update any volume cubes that reference this light
            volume_cubes_updated = 0
            for obj in bpy.data.objects:
                if obj.get("is_gobo_volume") and obj.get("volume_parent_light") == old_name:
                    logger.debug(f"Found volume cube {obj.name} referencing old light name")
                    obj["volume_parent_light"] = light_obj.name
                    volume_cubes_updated += 1
                    logger.debug(f"Updated volume cube {obj.name} to reference new light name {light_obj.name}")
            
            logger.debug(f"Updated {volume_cubes_updated} volume cube(s) to reference the new light name")
        
        return {"FINISHED"}

    def store_light_settings(self, light_data):
        """Store all relevant light settings from the current data block"""
        settings = {}
        
        # Store common properties
        common_properties = ["color", "use_shadow", "shadow_color", "energy"]
        for prop in common_properties:
            if hasattr(light_data, prop):
                settings[prop] = getattr(light_data, prop)

        # Store type-specific properties
        type_specific_properties = {
            "POINT": ["shadow_soft_size", "falloff_type"],
            "SPOT": ["spot_size", "spot_blend", "show_cone", "shadow_soft_size"],
            "AREA": ["shape", "size", "size_y"],
            "SUN": ["angle", "sky_intensity", "contact_shadow_distance"]
        }
        
        if light_data.type in type_specific_properties:
            for prop in type_specific_properties[light_data.type]:
                if hasattr(light_data, prop):
                    settings[prop] = getattr(light_data, prop)

        # Store node settings if available
        if light_data.use_nodes:
            settings['use_nodes'] = True
            settings['node_settings'] = {}
            for node in light_data.node_tree.nodes:
                if "ColorTemp" in node.inputs:
                    settings['node_settings']['color_temp'] = node.inputs["ColorTemp"].default_value

        return settings

    def apply_stored_settings(self, new_data_block, settings):
        """Apply stored settings to the new data block"""
        # Define allowed properties based on light type
        type_specific_properties = {
            "POINT": ["shadow_soft_size", "falloff_type"],
            "SPOT": ["spot_size", "spot_blend", "show_cone", "shadow_soft_size"],
            "AREA": ["shape", "size", "size_y"],
            "SUN": ["angle", "sky_intensity", "contact_shadow_distance"]
        }
        
        # Common properties that should always transfer
        common_properties = ["color", "use_shadow", "shadow_color", "energy"]
        
        # Combine common and type-specific properties
        allowed_properties = common_properties + type_specific_properties.get(new_data_block.type, [])

        # Apply only allowed properties
        for prop, value in settings.items():
            if prop in allowed_properties and hasattr(new_data_block, prop):
                try:
                    setattr(new_data_block, prop, value)
                except:
                    logger.error(f"Failed to set property {prop}")

        # Apply node settings if available
        if settings.get('use_nodes') and settings.get('node_settings'):
            new_data_block.use_nodes = True
            if 'color_temp' in settings['node_settings']:
                for node in new_data_block.node_tree.nodes:
                    if "ColorTemp" in node.inputs:
                        node.inputs["ColorTemp"].default_value = settings['node_settings']['color_temp']
                        break

    def apply_initial_color_temp(self, light_data_block, temp_value):
        if light_data_block.use_nodes:
            for node in light_data_block.node_tree.nodes:
                if "ColorTemp" in node.inputs:
                    node.inputs["ColorTemp"].default_value = temp_value
                    break

    def create_new_data_block(self, light_obj, id_prop_key):
        readable_light_type = self.light_type.capitalize()
        new_data_block_name = f"{readable_light_type}.{self.customization}"

        new_data_block = bpy.data.lights.new(
            name=new_data_block_name, type=self.light_type
        )

        # Apply initial area light size from preferences if it's an area light
        if self.light_type == 'AREA':
            addon_prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
            new_data_block.size = addon_prefs.initial_light_size
            new_data_block.size_y = addon_prefs.initial_light_size

        if self.customization == "Gobo":
            append_gobo_node_group()
            light_obj.data = new_data_block  # Set the data block before applying
            
            # Inherit folder from scene's last used gobo folder
            if not new_data_block.gobo_root_folder and bpy.context.scene.last_gobo_folder:
                new_data_block.gobo_root_folder = bpy.context.scene.last_gobo_folder
                # Update categories for this folder
                from ..utils.preview_manager import update_light_categories
                update_light_categories(new_data_block, 'gobo')
            
            # Apply default gobo
            apply_gobo_to_light(light_obj, "Window-004")
            
            # Set the enum to match the applied texture
            gobo_preview_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gobo_previews", "Window-004.png")
            if hasattr(new_data_block, 'gobo_enum'):
                try:
                    new_data_block.gobo_enum = gobo_preview_path
                    # Also set the identifier for change detection
                    if hasattr(new_data_block, 'gobo_identifier'):
                        new_data_block.gobo_identifier = gobo_preview_path
                except:
                    # If the enum value doesn't exist, silently continue
                    pass
            
        elif self.customization == "HDRI":
            append_hdri_node_group()
            light_obj.data = new_data_block  # Set the data block before applying
            
            # Inherit folder from scene's last used HDRI folder
            if not new_data_block.hdri_root_folder and bpy.context.scene.last_hdri_folder:
                new_data_block.hdri_root_folder = bpy.context.scene.last_hdri_folder
                # Update categories for this folder
                from ..utils.preview_manager import update_light_categories
                update_light_categories(new_data_block, 'hdri')
            
            # Apply default HDRI
            apply_hdri_to_light(light_obj, "03_Octabox_Medium_01_spread155")
            
            # Set the enum to match the applied texture
            hdri_preview_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hdri_previews", "03_Octabox_Medium_01_spread155.jpg")
            if hasattr(new_data_block, 'hdri_enum'):
                try:
                    new_data_block.hdri_enum = hdri_preview_path
                    # Also set the identifier for change detection
                    if hasattr(new_data_block, 'hdri_identifier'):
                        new_data_block.hdri_identifier = hdri_preview_path
                except:
                    # If the enum value doesn't exist, silently continue
                    pass
            
        elif self.customization == "IES":
            append_ies_node_group()
            light_obj.data = new_data_block  # Set the data block before applying
            
            # Inherit folder from scene's last used IES folder
            if not new_data_block.ies_root_folder and bpy.context.scene.last_ies_folder:
                new_data_block.ies_root_folder = bpy.context.scene.last_ies_folder
                # Update categories for this folder
                from ..utils.preview_manager import update_light_categories
                update_light_categories(new_data_block, 'ies')
            
            # Apply default IES profile
            ies_preview_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ies_previews", "accent-light-004.jpg")
            apply_ies_to_light(light_obj, ies_preview_path)
            
            # Set the enum to match the applied texture
            if hasattr(new_data_block, 'ies_enum'):
                try:
                    new_data_block.ies_enum = ies_preview_path
                    # Also set the identifier for change detection
                    if hasattr(new_data_block, 'ies_identifier'):
                        new_data_block.ies_identifier = ies_preview_path
                except:
                    # If the enum value doesn't exist, silently continue
                    pass
        elif self.customization == "Scrim":
            append_scrim_node_group()
            light_obj.data = new_data_block  # Set the data block before applying
            apply_scrim_to_light(new_data_block)

        light_obj[id_prop_key] = new_data_block
        return new_data_block

    def refurbish_default_data_block(self, light_obj, id_prop_key):
        readable_light_type = self.light_type.capitalize()
        new_data_block_name = f"{readable_light_type}.{self.customization}"

        old_data_block = light_obj.data
        old_data_block.name = new_data_block_name
        new_data_block = old_data_block

        light_obj.data = new_data_block
        light_obj[id_prop_key] = new_data_block
        return new_data_block

    def ensure_node_group_connection(self, light_data_block, customization):
        if not light_data_block.use_nodes:
            light_data_block.use_nodes = True

        nodes = light_data_block.node_tree.nodes
        output_node = next(
            (node for node in nodes if node.type == "OUTPUT_LIGHT"), None
        )

        customization_key_phrases = {
            "Gobo": "Gobo Light",
            "HDRI": "HDRI Light",
            "IES": "IES Light",
            "Scrim": "Scrim Light",
        }

        key_phrase = customization_key_phrases.get(customization)
        if key_phrase:
            group_node = next(
                (
                    node
                    for node in nodes
                    if node.type == "GROUP" and key_phrase in node.node_tree.name
                ),
                None,
            )

            if group_node and output_node:
                if not any(
                    link.to_node == output_node for link in group_node.outputs[0].links
                ):
                    light_data_block.node_tree.links.new(
                        group_node.outputs[0], output_node.inputs[0]
                    )

class LIGHTW_OT_LightTypeChanged(bpy.types.Operator):
    """Update light type and apply custom data block"""
    bl_idname = "lightwrangler.light_type_changed"
    bl_label = "Custom Light Setup"
    bl_options = {"REGISTER", "UNDO"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def poll(cls, context):
        active_obj = context.active_object
        return active_obj is not None and active_obj.type == "LIGHT"

    def execute(self, context):
        # Check if interactive mode is active using the flag
        if context.scene.lightwrangler_props.is_interactive_mode_active:
            return {"CANCELLED"}

        active_obj = context.active_object
        prefs = context.preferences.addons[ADDON_MODULE_NAME].preferences

        # Apply the customization
        try:
            if active_obj and active_obj.type == 'LIGHT':
                current_light_type = active_obj.data.type

                if (
                    "last_light_type" in active_obj
                    and active_obj["last_light_type"] == current_light_type
                ):
                    return {"CANCELLED"}

                last_customization = active_obj.get(
                    f"last_customization_{current_light_type}", "Default"
                )
                result = self.apply_custom_data_block(
                    active_obj.name, current_light_type, last_customization
                )

                if result:
                    active_obj["last_light_type"] = current_light_type
                    return {"FINISHED"}
                else:
                    return {"CANCELLED"}
        except Exception as error:
            self.report({"ERROR"}, f"Error applying custom data block: {error}")
            return {"CANCELLED"}

    def apply_custom_data_block(self, light_name, light_type, customization):
        try:
            bpy.ops.lightwrangler.apply_custom_data_block(
                light_name=light_name,
                light_type=light_type,
                customization=customization,
            )
            return True
        except Exception as error:
            self.report({"ERROR"}, f"Error applying custom data block: {error}")
            return False

class LIGHTW_OT_convert_to_plane(bpy.types.Operator):
    """Convert the selected light to a plane with the current gobo stencil texture"""
    bl_idname = "lightwrangler.convert_to_plane"
    bl_label = "Convert to Plane"
    bl_options = {'REGISTER', 'UNDO'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'LIGHT' and 
                context.active_object.data.type == 'AREA')

    def execute(self, context):
        light_obj = context.active_object
        if not light_obj:
            self.report({'WARNING'}, "No light selected")
            return {'CANCELLED'}

        image_texture_node = None
        rotation_value = 0
        invert_gobo_value = False
        playback_speed_value = 1.0  # Default value

        if light_obj.data.use_nodes:
            for node in light_obj.data.node_tree.nodes:
                if node.type == 'GROUP':
                    if 'Rotation' in node.inputs:
                        rotation_value = node.inputs['Rotation'].default_value
                    if 'Invert Gobo' in node.inputs:
                        invert_gobo_value = node.inputs['Invert Gobo'].default_value
                    # Get playback speed from input index 8
                    playback_speed_value = node.inputs[8].default_value
                    
                    for sub_node in node.node_tree.nodes:
                        if sub_node.type == 'TEX_IMAGE':
                            image_texture_node = sub_node
                            break
                    if image_texture_node:
                        break

        location = light_obj.location.copy()
        rotation = light_obj.rotation_euler.copy()
        
        # Get the actual size of the light, accounting for both intrinsic size and scaling
        if light_obj.data.type == 'AREA':
            size_x = light_obj.data.size * light_obj.scale.x
            size_y = light_obj.data.size_y * light_obj.scale.y if light_obj.data.shape == 'RECTANGLE' else light_obj.data.size * light_obj.scale.y
        else:  # For other light types, use scaling
            size_x = light_obj.scale.x
            size_y = light_obj.scale.y

        bpy.data.objects.remove(light_obj, do_unlink=True)

        # Create plane with the correct size
        bpy.ops.mesh.primitive_plane_add(size=1, location=location)
        plane = context.active_object
        plane.rotation_euler = rotation
        plane.scale = (size_x, size_y, 1)  # Set scale to match light size and scaling

        plane.name = self.generate_unique_name("Gobo Plane")

        material_name = f"{plane.name}_Material"
        new_material = bpy.data.materials.new(name=material_name)
        plane.data.materials.append(new_material)

        self.append_node_group(new_material, image_texture_node, rotation_value, invert_gobo_value, playback_speed_value)

        plane.display_type = 'TEXTURED'

        self.report({'INFO'}, f"Gobo converted to plane with material {material_name}")
        return {'FINISHED'}

    def generate_unique_name(self, base_name):
        existing_names = {obj.name for obj in bpy.data.objects if base_name in obj.name}
        count = 1
        new_name = base_name
        while new_name in existing_names:
            new_name = f"{base_name}.{str(count).zfill(3)}"
            count += 1
        return new_name

    def append_node_group(self, material, image_texture_node, rotation_value, invert_gobo_value, playback_speed_value):
        nodegroup_name = "Gobo Stencil"
        blender_version = bpy.app.version
        if blender_version[0] >= 4:
            nodegroup_blend_path = os.path.join(os.path.dirname(__file__), "..", "nodegroup-4.blend")
        else:
            nodegroup_blend_path = os.path.join(os.path.dirname(__file__), "..", "nodegroup.blend")

        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        nodes.clear()

        with bpy.data.libraries.load(nodegroup_blend_path, link=False) as (data_from, data_to):
            if nodegroup_name in data_from.node_groups:
                data_to.node_groups = [nodegroup_name]

        if nodegroup_name in bpy.data.node_groups:
            original_node_group = bpy.data.node_groups[nodegroup_name]
            node_group = original_node_group.copy() 
            node_group.use_fake_user = False

            group_node = nodes.new(type='ShaderNodeGroup')
            group_node.node_tree = node_group
            group_node.location = (0, 0)
            group_node.width = 175 

            material_output = nodes.new(type='ShaderNodeOutputMaterial')
            material_output.location = (400, 0) 

            links.new(group_node.outputs[0], material_output.inputs['Surface'])

            if image_texture_node:
                for sub_node in group_node.node_tree.nodes:
                    if sub_node.type == 'TEX_IMAGE':
                        sub_node.image = image_texture_node.image
                        sub_node.image_user.frame_duration = image_texture_node.image_user.frame_duration
                        sub_node.image_user.frame_start = image_texture_node.image_user.frame_start
                        sub_node.image_user.frame_offset = image_texture_node.image_user.frame_offset
                        sub_node.image_user.use_auto_refresh = image_texture_node.image_user.use_auto_refresh
                        
                        # Add video driver setup
                        if is_video_file(sub_node.image.filepath):
                            video_fps = get_video_frame_rate_from_blender(sub_node.image.filepath)
                            project_fps = bpy.context.scene.render.fps
                            
                            if video_fps:
                                speed_factor = video_fps / project_fps
                                # Use compatibility function for driver creation
                                driver = create_node_tree_driver(
                                    sub_node.image_user,
                                    "frame_offset",
                                    material,
                                    'MATERIAL',
                                    'nodes["Group"].inputs[3].default_value',
                                    f'frame * {speed_factor} * var % {sub_node.image.frame_duration}'
                                )
                                sub_node.image_user.use_cyclic = True
                                sub_node.image_user.use_auto_refresh = True
                        break

            if 'Rotation' in group_node.inputs:
                group_node.inputs['Rotation'].default_value = rotation_value
            if 'Invert Gobo' in group_node.inputs:
                group_node.inputs['Invert Gobo'].default_value = invert_gobo_value
            # Set playback speed directly to input index 3
            group_node.inputs[3].default_value = playback_speed_value

            if hasattr(material, 'blend_method'):
                material.blend_method = 'CLIP'
            if hasattr(material, 'shadow_method'):
                material.shadow_method = 'CLIP'

class LIGHTW_OT_create_volume_cube(bpy.types.Operator):
    """Create a volume cube for God rays with the current gobo texture"""
    bl_idname = "lightwrangler.create_volume_cube"
    bl_label = "Create Volume Cube"
    bl_options = {'REGISTER', 'UNDO'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'LIGHT' and
                context.active_object.data.type in {'SPOT', 'AREA'})

    def execute(self, context):
        light_obj = context.active_object
        if not light_obj:
            self.report({'WARNING'}, "No light selected")
            return {'CANCELLED'}

        # Find the image texture node in the light's node tree
        image_texture_node = None
        rotation_value = 0
        invert_gobo_value = False
        playback_speed_value = 1.0  # Default value
        density_value = 0.1  # Default density for volume scatter

        if light_obj.data.use_nodes:
            for node in light_obj.data.node_tree.nodes:
                if node.type == 'GROUP':
                    if 'Rotation' in node.inputs:
                        rotation_value = node.inputs['Rotation'].default_value
                    if 'Invert Gobo' in node.inputs:
                        invert_gobo_value = node.inputs['Invert Gobo'].default_value
                    if 'Focus' in node.inputs:
                        # Use focus to influence density - higher focus = lower density
                        focus = node.inputs['Focus'].default_value
                        density_value = 0.3 - (focus / 100) * 0.25  # Scale between 0.05 and 0.3
                    # Get playback speed from input index 5
                    playback_speed_value = node.inputs[5].default_value
                    
                    for sub_node in node.node_tree.nodes:
                        if sub_node.type == 'TEX_IMAGE':
                            image_texture_node = sub_node
                            break
                    if image_texture_node:
                        break

        if not image_texture_node:
            self.report({'WARNING'}, "No gobo texture found in the light")
            return {'CANCELLED'}

        # Get light properties
        location = light_obj.location.copy()
        rotation = light_obj.rotation_euler.copy()
        
        # Calculate cube size based on view distance and light properties
        # For a spot light, use the cone angle and distance
        # For an area light, use the size and a reasonable depth
        
        if light_obj.data.type == 'SPOT':
            # For spot lights, create a cube that fits the spot cone
            spot_size = light_obj.data.spot_size  # Spot cone angle in radians
            spot_blend = light_obj.data.spot_blend  # Spot blend (softness)
            
            # Calculate distance to fit current view
            view_distance = 10.0  # Default distance
            if context.space_data and context.space_data.type == 'VIEW_3D':
                view_distance = (context.space_data.region_3d.view_location - location).length
            
            # Calculate cone radius at the view distance
            cone_radius = math.tan(spot_size / 2) * view_distance
            
            # Create cube slightly larger than the cone
            cube_size = cone_radius * 2.2  # Make it a bit larger than the cone
            cube_depth = view_distance * 1.5  # Make it deeper than the view distance
            
            # Position the cube in front of the light
            forward_vector = Vector((0, 0, -1))  # Spot lights point along -Z
            forward_vector.rotate(rotation)
            cube_location = location + forward_vector * (cube_depth / 2)
            
            # Create the cube
            bpy.ops.mesh.primitive_cube_add(size=1, location=cube_location)
            cube = context.active_object
            cube.rotation_euler = rotation
            cube.scale = (cube_size, cube_size, cube_depth)
            
            # print(f"[DEBUG] Creating volume cube for light: {light_obj.name}")
            # Ensure cube is in the same collection as the light
            light_collection = next(iter(light_obj.users_collection), None)
            if light_collection:
                # print(f"[DEBUG] Moving cube from {[c.name for c in cube.users_collection]} to light's collection: {light_collection.name}")
                # Remove from all current collections
                for collection in cube.users_collection:
                    collection.objects.unlink(cube)
                # Add to light's collection
                light_collection.objects.link(cube)
                # print(f"[DEBUG] Cube is now in collection: {light_collection.name}")
            
        else:  # AREA light
            # For area lights, create a cube that extends from the light
            if light_obj.data.shape == 'RECTANGLE':
                size_x = light_obj.data.size * light_obj.scale.x
                size_y = light_obj.data.size_y * light_obj.scale.y
            else:  # 'SQUARE', 'DISK', 'ELLIPSE'
                size_x = light_obj.data.size * light_obj.scale.x
                size_y = light_obj.data.size * light_obj.scale.y
            
            # Calculate view distance
            view_distance = 10.0  # Default distance
            if context.space_data and context.space_data.type == 'VIEW_3D':
                view_distance = (context.space_data.region_3d.view_location - location).length
            
            # Create cube slightly larger than the area light
            cube_size_x = size_x * 1.2
            cube_size_y = size_y * 1.2
            cube_depth = view_distance * 1.5
            
            # Position the cube in front of the light
            forward_vector = Vector((0, 0, -1))  # Area lights face along -Z
            forward_vector.rotate(rotation)
            cube_location = location + forward_vector * (cube_depth / 2)
            
            # Create the cube
            bpy.ops.mesh.primitive_cube_add(size=1, location=cube_location)
            cube = context.active_object
            cube.rotation_euler = rotation
            cube.scale = (cube_size_x, cube_size_y, cube_depth)

            # print(f"[DEBUG] Creating volume cube for light: {light_obj.name}")
            # Ensure cube is in the same collection as the light
            light_collection = next(iter(light_obj.users_collection), None)
            if light_collection:
                # print(f"[DEBUG] Moving cube from {[c.name for c in cube.users_collection]} to light's collection: {light_collection.name}")
                # Remove from all current collections
                for collection in cube.users_collection:
                    collection.objects.unlink(cube)
                # Add to light's collection
                light_collection.objects.link(cube)
                # print(f"[DEBUG] Cube is now in collection: {light_collection.name}")

            # Name the cube
            cube.name = self.generate_unique_name("Gobo Volume")

        # Create a new material for the volume
        material_name = f"{cube.name}_Material"
        volume_material = bpy.data.materials.new(name=material_name)
        cube.data.materials.append(volume_material)

        # Set up the volume material with the gobo texture
        self.create_volume_material(volume_material, image_texture_node, density_value)

        # Set display settings for better viewport visualization
        cube.display_type = 'WIRE'
        
        # Make the cube not selectable to prevent accidental selection
        cube.hide_select = True
        
        # Parent the cube to the light
        cube.parent = light_obj
        cube.matrix_parent_inverse = light_obj.matrix_world.inverted()
        
        # Add custom properties for relationship tracking
        cube["volume_parent_light"] = light_obj.name
        cube["is_gobo_volume"] = True
        
        # Store reference to this volume cube in the light
        if "associated_volume_cubes" not in light_obj:
            light_obj["associated_volume_cubes"] = []
        
        # Convert the IDPropertyArray to a list, modify it, and set it back
        volume_cubes = list(light_obj["associated_volume_cubes"])
        if cube.name not in volume_cubes:
            volume_cubes.append(cube.name)
            light_obj["associated_volume_cubes"] = volume_cubes

        # Add drivers to keep the cube's scale in sync with the light's dimensions
        self.add_scale_drivers(cube, light_obj)

        self.report({'INFO'}, f"Created volume cube for God rays with material {material_name}")
        return {'FINISHED'}

    def add_scale_drivers(self, cube, light):
        """Add drivers to the cube's scale to keep it in sync with the light's dimensions"""
        # Store the original view distance for Z scale calculation
        view_distance = cube.scale.z
        if light.data.type == 'SPOT':
            # For spot lights, X and Y scales are based on spot size
            # Driver for X scale
            x_driver = cube.driver_add("scale", 0).driver
            x_driver.type = 'SCRIPTED'
            var = x_driver.variables.new()
            var.name = "spot_size"
            var.type = 'SINGLE_PROP'
            var.targets[0].id = light  # Set to light object, not light.data
            var.targets[0].data_path = "data.spot_size"  # Include data. prefix
            var_dist = x_driver.variables.new()
            var_dist.name = "distance"
            var_dist.type = 'SINGLE_PROP'
            var_dist.targets[0].id = cube
            var_dist.targets[0].data_path = "scale.z"
            x_driver.expression = "2.2 * tan(spot_size/2) * distance/1.5"
            
            # Driver for Y scale (same as X for spot lights)
            y_driver = cube.driver_add("scale", 1).driver
            y_driver.type = 'SCRIPTED'
            var = y_driver.variables.new()
            var.name = "spot_size"
            var.type = 'SINGLE_PROP'
            var.targets[0].id = light  # Set to light object, not light.data
            var.targets[0].data_path = "data.spot_size"  # Include data. prefix
            var_dist = y_driver.variables.new()
            var_dist.name = "distance"
            var_dist.type = 'SINGLE_PROP'
            var_dist.targets[0].id = cube
            var_dist.targets[0].data_path = "scale.z"
            y_driver.expression = "2.2 * tan(spot_size/2) * distance/1.5"
            
        else:  # AREA light
            # Driver for X scale
            x_driver = cube.driver_add("scale", 0).driver
            x_driver.type = 'SCRIPTED'
            var = x_driver.variables.new()
            var.name = "light_size"
            var.type = 'SINGLE_PROP'
            var.targets[0].id = light  # Set to light object, not light.data
            var.targets[0].data_path = "data.size"  # Include data. prefix
            x_driver.expression = "light_size * 1.2"
            
            # Driver for Y scale (depends on light shape)
            y_driver = cube.driver_add("scale", 1).driver
            y_driver.type = 'SCRIPTED'
            
            # Add variable for shape
            var_shape = y_driver.variables.new()
            var_shape.name = "shape"
            var_shape.type = 'SINGLE_PROP'
            var_shape.targets[0].id = light  # Set to light object, not light.data
            var_shape.targets[0].data_path = "data.shape"  # Include data. prefix
            
            # Add variable for size
            var_size = y_driver.variables.new()
            var_size.name = "size"
            var_size.type = 'SINGLE_PROP'
            var_size.targets[0].id = light  # Set to light object, not light.data
            var_size.targets[0].data_path = "data.size"  # Include data. prefix
            
            # Add variable for size_y (for RECTANGLE and ELLIPSE shapes)
            var_size_y = y_driver.variables.new()
            var_size_y.name = "size_y"
            var_size_y.type = 'SINGLE_PROP'
            var_size_y.targets[0].id = light  # Set to light object, not light.data
            var_size_y.targets[0].data_path = "data.size_y"  # Include data. prefix
            
            # Expression that checks shape and uses appropriate dimension
            y_driver.expression = "size_y * 1.2 if shape in ['RECTANGLE', 'ELLIPSE'] else size * 1.2"
        
        # We don't add a driver for Z scale (depth) as it's based on view distance
        # and doesn't need to change with the light's dimensions

    def generate_unique_name(self, base_name):
        existing_names = {obj.name for obj in bpy.data.objects if base_name in obj.name}
        count = 1
        new_name = base_name
        while new_name in existing_names:
            new_name = f"{base_name}.{str(count).zfill(3)}"
            count += 1
        return new_name

    def create_volume_material(self, material, image_texture_node, density_value):
        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        # Clear default nodes
        nodes.clear()

        # Create nodes for volume shader
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (300, 0)

        # Append Gobo Volume node group
        nodegroup_blend_path = os.path.join(os.path.dirname(__file__), "..", "nodegroup-4.blend")
        with bpy.data.libraries.load(nodegroup_blend_path, link=False) as (data_from, data_to):
            if "Gobo Volume" in data_from.node_groups:
                data_to.node_groups = ["Gobo Volume"]

        # Create and connect Gobo Volume node group
        gobo_volume = nodes.new('ShaderNodeGroup')
        gobo_volume.node_tree = bpy.data.node_groups["Gobo Volume"]
        links.new(gobo_volume.outputs[0], output.inputs['Volume'])

        # Set material settings - use version-appropriate attributes
        if hasattr(material, 'blend_method'):
            material.blend_method = 'BLEND'
        
        return material

class LIGHTW_OT_toggle_visibility(bpy.types.Operator):
    """Isolate current light"""
    bl_idname = "lightwrangler.toggle_visibility"
    bl_label = "Toggle Light Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        current_object = context.object
        
        # Check if lightwrangler_props exists
        if not hasattr(scene, "lightwrangler_props"):
            self.report({'ERROR'}, "Light Wrangler properties not available. The addon may be in the process of unregistering.")
            return {'CANCELLED'}

        def world_is_emitting():
            if scene.world and scene.world.node_tree:
                for node in scene.world.node_tree.nodes:
                    if node.type in {'BACKGROUND', 'EMISSION', 'BSDF_PRINCIPLED'}:
                        if node.inputs.get('Strength') and node.inputs['Strength'].default_value > 0:
                            return True
                output_node = next((node for node in scene.world.node_tree.nodes if node.type == 'OUTPUT_WORLD'), None)
                if output_node and output_node.inputs['Surface'].links:
                    return True
            return False

        def get_emitting_nodes():
            if scene.world and scene.world.node_tree:
                return [node for node in scene.world.node_tree.nodes 
                        if node.type in {'BACKGROUND', 'EMISSION', 'BSDF_PRINCIPLED'}]
            return []

        def is_emission_object(obj):
            if obj.type == 'MESH' and obj.material_slots:
                for mat_slot in obj.material_slots:
                    if mat_slot.material and mat_slot.material.node_tree:
                        if any(get_emission_nodes_from_tree(mat_slot.material.node_tree)):
                            return True
            return False

        def get_emission_nodes(obj):
            emission_nodes_info = []
            if obj.material_slots:
                for slot_idx, mat_slot in enumerate(obj.material_slots):
                    if mat_slot.material and mat_slot.material.node_tree:
                        nodes = get_emission_nodes_from_tree(mat_slot.material.node_tree)
                        for node in nodes:
                            emission_nodes_info.append({
                                'node': node,
                                'material': mat_slot.material,
                                'slot_index': slot_idx
                            })
            return emission_nodes_info

        def get_emission_nodes_from_tree(node_tree):
            emission_nodes = []
            if node_tree is None or not hasattr(node_tree, 'nodes'):
                return emission_nodes
            for node in node_tree.nodes:
                if node.type in {'EMISSION', 'BSDF_PRINCIPLED'}:
                    if node.type == 'EMISSION' or (node.type == 'BSDF_PRINCIPLED' and 'Emission Strength' in node.inputs):
                        emission_nodes.append(node)
                elif node.type == 'GROUP' and node.node_tree is not None:
                    emission_nodes.extend(get_emission_nodes_from_tree(node.node_tree))
            return emission_nodes

        def get_emission_strength(node):
            if node.type == 'EMISSION':
                return node.inputs['Strength'].default_value
            elif node.type == 'BSDF_PRINCIPLED' and 'Emission Strength' in node.inputs:
                return node.inputs['Emission Strength'].default_value
            return 0

        def set_emission_strength(node, strength):
            if node.type == 'EMISSION':
                node.inputs['Strength'].default_value = strength
            elif node.type == 'BSDF_PRINCIPLED' and 'Emission Strength' in node.inputs:
                node.inputs['Emission Strength'].default_value = strength

        if not current_object and not world_is_emitting():
            self.report({'WARNING'}, "No light source selected to isolate")
            return {'CANCELLED'}

        is_world_background = current_object is None and world_is_emitting()

        light_sources = [obj for obj in bpy.data.objects if obj.type == 'LIGHT']
        emissive_objects = [obj for obj in bpy.data.objects if is_emission_object(obj)]

        if not scene.lightwrangler_props.is_isolated:
            # Start isolation mode
            scene.lightwrangler_props.original_states.clear()
            
            # Store light states
            for obj in light_sources:
                item = scene.lightwrangler_props.original_states.add()
                item.name = obj.name
                item.hide_viewport = obj.hide_viewport
            
            # Store emissive object states with material info
            for obj in emissive_objects:
                item = scene.lightwrangler_props.original_states.add()
                item.name = obj.name
                item.hide_viewport = False  # Not hiding mesh objects
                
                for node_info in get_emission_nodes(obj):
                    node = node_info['node']
                    material = node_info['material']
                    slot_index = node_info['slot_index']
                    
                    node_state = item.emission_states.add()
                    node_state.node_name = node.name
                    node_state.node_type = node.type
                    node_state.strength = get_emission_strength(node)
                    node_state.material_name = material.name
                    node_state.material_slot_index = slot_index

            # Store world states
            scene.lightwrangler_props.original_world_states.clear()
            for node in get_emitting_nodes():
                item = scene.lightwrangler_props.original_world_states.add()
                item.name = node.name
                item.mute = node.mute

            # Apply isolation: hide all lights except current
            for obj in light_sources:
                obj.hide_viewport = obj != current_object if current_object else True
            
            # Turn off emission for all objects except current
            for obj in emissive_objects:
                # Check if this is the object we want to isolate
                is_current_emissive = (obj == current_object)
                
                for node_info in get_emission_nodes(obj):
                    node = node_info['node']
                    # Only keep emission if this is the current object
                    set_emission_strength(node, get_emission_strength(node) if is_current_emissive else 0)
            
            # Handle world lighting
            for node in get_emitting_nodes():
                node.mute = not is_world_background
            
            scene.lightwrangler_props.is_isolated = True

            if current_object:
                self.report({'INFO'}, f"Isolated light: {current_object.name}")
            else:
                self.report({'INFO'}, "Isolated world lighting")

        else:
            # End isolation mode - restore original states
            for item in scene.lightwrangler_props.original_states:
                obj = bpy.data.objects.get(item.name)
                if obj:
                    if obj.type == 'LIGHT':
                        obj.hide_viewport = item.hide_viewport
                    else:
                        # For emissive objects, restore emission values by material and node
                        for node_state in item.emission_states:
                            # Check if material still exists
                            slot_index = node_state.material_slot_index
                            if 0 <= slot_index < len(obj.material_slots):
                                mat_slot = obj.material_slots[slot_index]
                                
                                # Double-check material name matches
                                if mat_slot.material and mat_slot.material.name == node_state.material_name:
                                    # Find and restore the node
                                    for node in get_emission_nodes_from_tree(mat_slot.material.node_tree):
                                        if node.name == node_state.node_name and node.type == node_state.node_type:
                                            set_emission_strength(node, node_state.strength)
                                            break

            # Restore world lighting
            for item in scene.lightwrangler_props.original_world_states:
                if scene.world and scene.world.node_tree:
                    node = scene.world.node_tree.nodes.get(item.name)
                    if node:
                        node.mute = item.mute
            
            scene.lightwrangler_props.is_isolated = False
            self.report({'INFO'}, "All lights restored")

        context.view_layer.update()
        return {'FINISHED'}

@persistent
def light_type_changed(scene, depsgraph):
    if bpy.context.screen and bpy.context.screen.is_animation_playing:
        return

    global is_updating_light
    
    # Safely check if lightwrangler_props exists
    if not hasattr(scene, "lightwrangler_props"):
        return
        
    is_interactive = scene.lightwrangler_props.is_interactive_mode_active
    
    if is_updating_light or is_interactive:
        return

    active_obj = bpy.context.active_object
    
    if active_obj and active_obj.type == "LIGHT":
        is_updating_light = True
        try:
            bpy.app.timers.register(lambda: bpy.ops.lightwrangler.light_type_changed() and None, first_interval=0.0)
        except Exception as e:
            pass
        finally:
            is_updating_light = False

@persistent
def handle_light_selection_change(scene, depsgraph):
    """Handle light selection changes to transfer isolation state"""
    # Skip in any of these cases:
    # - Interactive mode is active (modal operator)
    # - Animation playback
    # - Not in isolation mode
    
    # Safely check if lightwrangler_props exists
    if not hasattr(scene, "lightwrangler_props"):
        return
        
    if (scene.lightwrangler_props.is_interactive_mode_active or
        bpy.context.screen and bpy.context.screen.is_animation_playing or
        not scene.lightwrangler_props.is_isolated):
        return
        
    global is_handling_selection
    if is_handling_selection:
        return
        
    context = bpy.context
    active_obj = context.active_object
    
    # If no light is selected or non-light is selected, revert isolation
    if not active_obj or active_obj.type != 'LIGHT':
        try:
            is_handling_selection = True
            bpy.ops.lightwrangler.toggle_visibility()
        except Exception as e:
            logger.error(f"Error reverting isolation: {e}")
        finally:
            is_handling_selection = False
        return

    def is_emission_object(obj):
        if obj.type == 'MESH' and obj.material_slots:
            for mat_slot in obj.material_slots:
                if mat_slot.material and mat_slot.material.node_tree:
                    if any(get_emission_nodes_from_tree(mat_slot.material.node_tree)):
                        return True
        return False

    def get_emission_nodes(obj):
        emission_nodes_info = []
        if obj.material_slots:
            for slot_idx, mat_slot in enumerate(obj.material_slots):
                if mat_slot.material and mat_slot.material.node_tree:
                    nodes = get_emission_nodes_from_tree(mat_slot.material.node_tree)
                    for node in nodes:
                        emission_nodes_info.append({
                            'node': node,
                            'material': mat_slot.material,
                            'slot_index': slot_idx
                        })
        return emission_nodes_info

    def get_emission_nodes_from_tree(node_tree):
        emission_nodes = []
        if node_tree is None or not hasattr(node_tree, 'nodes'):
            return emission_nodes
        for node in node_tree.nodes:
            if node.type in {'EMISSION', 'BSDF_PRINCIPLED'}:
                if node.type == 'EMISSION' or (node.type == 'BSDF_PRINCIPLED' and 'Emission Strength' in node.inputs):
                    emission_nodes.append(node)
            elif node.type == 'GROUP' and node.node_tree is not None:
                emission_nodes.extend(get_emission_nodes_from_tree(node.node_tree))
        return emission_nodes

    def get_emitting_nodes():
        if scene.world and scene.world.node_tree:
            return [node for node in scene.world.node_tree.nodes 
                    if node.type in {'BACKGROUND', 'EMISSION', 'BSDF_PRINCIPLED'}]
        return []

    def set_emission_strength(node, strength):
        if node.type == 'EMISSION':
            node.inputs['Strength'].default_value = strength
        elif node.type == 'BSDF_PRINCIPLED' and 'Emission Strength' in node.inputs:
            node.inputs['Emission Strength'].default_value = strength
        
    try:
        is_handling_selection = True
        
        # Get all lights and emissive objects
        light_sources = [obj for obj in bpy.data.objects if obj.type == 'LIGHT']
        emissive_objects = [obj for obj in bpy.data.objects if is_emission_object(obj)]

        # If we're already isolated and selected a different light, transfer isolation
        for light in light_sources:
            if light != active_obj:
                light.hide_viewport = True
            else:
                light.hide_viewport = False
                
        # Handle emissive objects
        for obj in emissive_objects:
            for node_info in get_emission_nodes(obj):
                node = node_info['node']
                set_emission_strength(node, 0)
                
        # Handle world lighting
        for node in get_emitting_nodes():
            node.mute = True
                
        # Ensure the active light is selected and active
        active_obj.select_set(True)
        context.view_layer.objects.active = active_obj
    finally:
        is_handling_selection = False

@persistent
def cleanup_orphaned_volume_cubes(scene, depsgraph):
    """Check for and remove volume cubes whose parent lights have been deleted or fix parenting if separated"""
    # Skip during animation playback for performance
    if bpy.context.screen and bpy.context.screen.is_animation_playing:
        return
        
    # Find all volume cubes
    volume_cubes = [obj for obj in bpy.data.objects 
                   if obj.get("is_gobo_volume") and obj.get("volume_parent_light")]
    
    for cube in volume_cubes:
        parent_light_name = cube["volume_parent_light"]
        parent_light = bpy.data.objects.get(parent_light_name)
        
        if not parent_light:
            # If parent light doesn't exist anymore, delete the volume cube
            # First, remove any drivers to prevent crashes during autosave
            if cube.animation_data and cube.animation_data.drivers:
                # Remove all drivers from the cube
                for driver in cube.animation_data.drivers:
                    cube.driver_remove(driver.data_path, driver.array_index)
            
            # Check for material with drivers
            if cube.data and cube.data.materials:
                for material_slot in cube.material_slots:
                    if material_slot.material:
                        material = material_slot.material
                        
                        # Remove drivers from material if any
                        if material.animation_data and material.animation_data.drivers:
                            for driver in material.animation_data.drivers:
                                material.driver_remove(driver.data_path, driver.array_index)
                        
                        # Check for node group drivers
                        if material.node_tree:
                            for node in material.node_tree.nodes:
                                if node.type == 'GROUP' and node.node_tree and "Gobo Volume" in node.node_tree.name:
                                    # Remove drivers from node inputs
                                    for i, input in enumerate(node.inputs):
                                        try:
                                            # Try to remove driver if it exists
                                            node.inputs[i].driver_remove("default_value")
                                        except:
                                            pass
                        
                        # Now remove the material
                        bpy.data.materials.remove(material)
            
            # Remove the cube's mesh data
            mesh_data = cube.data
            bpy.data.objects.remove(cube)
            if mesh_data and mesh_data.users == 0:
                bpy.data.meshes.remove(mesh_data)
        else:
            # Check both parent relationship and collection match
            needs_fix = False
            if cube.parent != parent_light:
                needs_fix = True
            
            # Check if cube is in the same collection as the light
            light_collection = next(iter(parent_light.users_collection), None)
            if light_collection and light_collection not in cube.users_collection:
                needs_fix = True
                
            if needs_fix:
                # Store current world transform
                world_matrix = cube.matrix_world.copy()
                
                if light_collection:
                    # Remove from all current collections
                    for collection in cube.users_collection:
                        collection.objects.unlink(cube)
                    # Add to light's collection
                    light_collection.objects.link(cube)
                
                # Restore parenting
                cube.parent = parent_light
                cube.matrix_parent_inverse = parent_light.matrix_world.inverted()
                
                # Restore world transform
                cube.matrix_world = world_matrix

class LIGHTW_OT_RefreshGoboPreview(bpy.types.Operator):
    """Gobo preview is outdated as the folder contents changed"""
    bl_idname = "lightwrangler.refresh_gobo_preview"
    bl_label = "Refresh Gobo Library"
    bl_description = "Gobo preview is outdated as the folder contents changed"
    bl_options = {'INTERNAL'}
    
    def execute(self, context):
        light_obj = context.object
        if light_obj and light_obj.type == 'LIGHT':
            light_data = light_obj.data
            
            # Store the current identifier (the texture that should be selected)
            if hasattr(light_data, 'gobo_identifier'):
                stored_identifier = light_data.gobo_identifier
                
                # Force the enum to update by setting it to the stored identifier
                # This triggers the UI to select the correct thumbnail
                if hasattr(light_data, 'gobo_enum'):
                    try:
                        light_data.gobo_enum = stored_identifier
                    except:
                        # If the stored identifier is no longer valid, just sync them
                        light_data.gobo_identifier = light_data.gobo_enum
            
            # Force UI redraw
            for area in context.screen.areas:
                if area.type == 'PROPERTIES':
                    area.tag_redraw()
                    
        return {'FINISHED'}

class LIGHTW_OT_RefreshHDRIPreview(bpy.types.Operator):
    """HDRI preview is outdated as the folder contents changed"""
    bl_idname = "lightwrangler.refresh_hdri_preview"
    bl_label = "Refresh HDRI Library"
    bl_description = "HDRI preview is outdated as the folder contents changed"
    bl_options = {'INTERNAL'}
    
    def execute(self, context):
        light_obj = context.object
        if light_obj and light_obj.type == 'LIGHT':
            light_data = light_obj.data
            
            # Store the current identifier (the texture that should be selected)
            if hasattr(light_data, 'hdri_identifier'):
                stored_identifier = light_data.hdri_identifier
                
                # Force the enum to update by setting it to the stored identifier
                # This triggers the UI to select the correct thumbnail
                if hasattr(light_data, 'hdri_enum'):
                    try:
                        light_data.hdri_enum = stored_identifier
                    except:
                        # If the stored identifier is no longer valid, just sync them
                        light_data.hdri_identifier = light_data.hdri_enum
            
            # Force UI redraw
            for area in context.screen.areas:
                if area.type == 'PROPERTIES':
                    area.tag_redraw()
                    
        return {'FINISHED'}

class LIGHTW_OT_RefreshIESPreview(bpy.types.Operator):
    """IES preview is outdated as the folder contents changed"""
    bl_idname = "lightwrangler.refresh_ies_preview"
    bl_label = "Refresh IES Library"
    bl_description = "IES preview is outdated as the folder contents changed"
    bl_options = {'INTERNAL'}
    
    def execute(self, context):
        light_obj = context.object
        if light_obj and light_obj.type == 'LIGHT':
            light_data = light_obj.data
            
            # Store the current identifier (the texture that should be selected)
            if hasattr(light_data, 'ies_identifier'):
                stored_identifier = light_data.ies_identifier
                
                # Force the enum to update by setting it to the stored identifier
                # This triggers the UI to select the correct thumbnail
                if hasattr(light_data, 'ies_enum'):
                    try:
                        light_data.ies_enum = stored_identifier
                    except:
                        # If the stored identifier is no longer valid, just sync them
                        light_data.ies_identifier = light_data.ies_enum
            
            # Force UI redraw
            for area in context.screen.areas:
                if area.type == 'PROPERTIES':
                    area.tag_redraw()
                    
        return {'FINISHED'}

class LIGHTW_OT_ClearGoboRootFolder(bpy.types.Operator):
    """Clear gobo root folder"""
    bl_idname = "lightwrangler.clear_gobo_root_folder"
    bl_label = "Clear Gobo Folder"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        light_obj = context.object
        if light_obj and light_obj.type == 'LIGHT':
            light_data = light_obj.data
            light_data.gobo_root_folder = ""
            self.report({'INFO'}, "Gobo folder cleared")
        return {'FINISHED'}

class LIGHTW_OT_ClearHDRIRootFolder(bpy.types.Operator):
    """Clear HDRI root folder"""
    bl_idname = "lightwrangler.clear_hdri_root_folder"
    bl_label = "Clear HDRI Folder"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        light_obj = context.object
        if light_obj and light_obj.type == 'LIGHT':
            light_data = light_obj.data
            light_data.hdri_root_folder = ""
            self.report({'INFO'}, "HDRI folder cleared")
        return {'FINISHED'}

class LIGHTW_OT_ClearIESRootFolder(bpy.types.Operator):
    """Clear IES root folder"""
    bl_idname = "lightwrangler.clear_ies_root_folder"
    bl_label = "Clear IES Folder"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        light_obj = context.object
        if light_obj and light_obj.type == 'LIGHT':
            light_data = light_obj.data
            light_data.ies_root_folder = ""
            self.report({'INFO'}, "IES folder cleared")
        return {'FINISHED'}

# List of all classes in this file
classes = (
    LIGHTW_GGT_light_controls,
    LIGHTW_OT_confirm_cycles_switch,
    LIGHTW_OT_confirm_tracking_removal,
    LIGHTW_OT_apply_custom_data_block,
    LIGHTW_OT_LightTypeChanged,
    LIGHTW_OT_convert_to_plane,
    LIGHTW_OT_create_volume_cube,
    LIGHTW_OT_toggle_visibility,
    LIGHTW_OT_RefreshGoboPreview,
    LIGHTW_OT_RefreshHDRIPreview,
    LIGHTW_OT_RefreshIESPreview,
    LIGHTW_OT_ClearGoboRootFolder,
    LIGHTW_OT_ClearHDRIRootFolder,
    LIGHTW_OT_ClearIESRootFolder,
)

def register():
    from ..utils import logger
    logger.start_section("Light Operators")
    
    # Register classes
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            logger.log_registration(cls.__name__)
        except Exception as e:
            logger.log_registration(cls.__name__, False, str(e))
    
    # Register handlers
    logger.start_section("Handlers")
    try:
        bpy.app.handlers.depsgraph_update_post.append(light_type_changed)
        logger.debug("Registered light_type_changed handler")
    except Exception as e:
        logger.error(f"Failed to register light_type_changed handler: {e}")
        
    try:
        bpy.app.handlers.depsgraph_update_post.append(handle_light_selection_change)
        logger.debug("Registered handle_light_selection_change handler")
    except Exception as e:
        logger.error(f"Failed to register handle_light_selection_change handler: {e}")
    
    # Register the cleanup handler for orphaned volume cubes
    try:
        bpy.app.handlers.depsgraph_update_post.append(cleanup_orphaned_volume_cubes)
        logger.debug("Registered cleanup_orphaned_volume_cubes handler")
    except Exception as e:
        logger.error(f"Failed to register cleanup_orphaned_volume_cubes handler: {e}")
    
    logger.end_section()
    logger.end_section()

def unregister():
    from ..utils import logger
    logger.start_section("Light Operators Handlers")
    
    # Safely unregister the handlers
    try:
        # First check if the handlers exist in the handler list
        handlers_found = False
        for handler in bpy.app.handlers.depsgraph_update_post:
            if hasattr(handler, "__name__") and handler.__name__ in ["handle_light_selection_change", "light_type_changed", "cleanup_orphaned_volume_cubes"]:
                handlers_found = True
                break
        
        # Only log warnings if we actually found handlers
        if handlers_found:
            if handle_light_selection_change in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(handle_light_selection_change)
                logger.debug("Removed handle_light_selection_change handler")
            else:
                logger.warning("handle_light_selection_change handler not found in depsgraph_update_post")
            
            if light_type_changed in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(light_type_changed)
                logger.debug("Removed light_type_changed handler")
            else:
                logger.warning("light_type_changed handler not found in depsgraph_update_post")
                
            if cleanup_orphaned_volume_cubes in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(cleanup_orphaned_volume_cubes)
                logger.debug("Removed cleanup_orphaned_volume_cubes handler")
            else:
                logger.warning("cleanup_orphaned_volume_cubes handler not found in depsgraph_update_post")
        else:
            # Just log at debug level if no handlers were found
            logger.debug("No Light Operators handlers found in depsgraph_update_post")
    except Exception as e:
        logger.error(f"Error removing Light Operators handlers: {e}")
    
    logger.end_section()
    
    # Unregister classes
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
            logger.log_unregistration(cls.__name__)
        except Exception as e:
            logger.log_unregistration(cls.__name__, False, str(e)) 