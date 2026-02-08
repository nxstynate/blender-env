bl_info = {
    "name": "Light Wrangler",
    "author": "Leonid Altman",
    "version": (3, 2, 6),
    "blender": (4, 3, 0),
    "location": "3D View > Right-click menu > Light Wrangler",
    "description": "Advanced light manipulation tools",
    "category": "3D View",
    "doc_url": "https://superhivemarket.com/products/light-wrangler/docs"
}

ADDON_MODULE_NAME = __package__

# Import logger first so it's avaialable for all modules
from .utils import logger

logger.info("Light Wrangler addon loaded")

import bpy
import importlib
import sys
import os
import json
import re
from bpy.app.handlers import persistent
from .utils.blender_compat import supports_compositor, supports_object_visibility_toggle

# Import our modules
if "properties" in locals():
    importlib.reload(properties)
    importlib.reload(operators)
    importlib.reload(ui)
    importlib.reload(utils)
    importlib.reload(gizmos)
    
    importlib.reload(properties.properties)
    importlib.reload(operators.operators)
    importlib.reload(ui.ui)
    importlib.reload(utils.utils)
    importlib.reload(utils.drawing)
    importlib.reload(utils.preview_manager)
    importlib.reload(utils.previews)
    importlib.reload(gizmos.light_position_gizmos)
else:
    from . import properties
    from . import operators
    from . import ui
    from . import utils
    from . import gizmos

# Import preview functions after modules are loaded
from .utils.previews import (
    load_hdri_previews,
    load_gobo_previews,
    load_ies_previews,
    scan_and_generate_thumbnails,
    register_previews,
    unregister_previews
)

# Import the handler after utils is loaded
from .utils.texture_manager import update_light_spread

def update_preference(self, context):
    """
    Generic preference update handler that saves preferences.
    """
    save_all_preferences()

# Global flag to prevent keymap changes during registration
_addon_registering = False

def update_mode_switch_keys_preference(self, context):
    """Custom update handler that manages keymaps when preference changes."""
    save_all_preferences()

    # Prevent keymap manipulation during addon registration/startup
    global _addon_registering
    if _addon_registering:
        logger.info("Skipping keymap update - addon is registering")
        return

    # Safety check: Don't manipulate keymaps during addon registration
    # This prevents issues during Blender startup and preference imports
    try:
        # Check if we're in a safe context (not during registration)
        if not hasattr(bpy.context, 'preferences') or not hasattr(bpy.ops.lightwrangler, 'interactive_mode'):
            logger.warning("Skipping keymap update - addon not fully registered")
            return
    except:
        logger.warning("Skipping keymap update - context not available")
        return

    if not self.enable_mode_switch_keys:
        # User disabled - restore Blender's default collection keymaps and remove our addon keymaps
        logger.info("Disabling Light Wrangler mode switch keys")
        cleanup_light_wrangler_mode_keymaps(context)
        restore_collection_keymaps(context)
    else:
        # User enabled - clear user 1,2,3 keymaps and register our addon keymaps
        logger.info("Enabling Light Wrangler mode switch keys")
        override_collection_keymaps(context)
        register_mode_switch_keymaps(context)

def get_preferences_file_path():
    """
    Returns the file path for storing the addon's preferences.
    """
    try:
        preferences_base_path = bpy.utils.user_resource('SCRIPTS')
        preferences_path = os.path.join(preferences_base_path, "preferences")

        if not os.path.exists(preferences_path):
            os.makedirs(preferences_path, exist_ok=True)

        preferences_file = os.path.join(preferences_path, "light_wrangler_preferences.json")
        return preferences_file
    except PermissionError as e:
        logger.error(f"Permission denied when accessing preferences path: {str(e)}")
        return None

def save_all_preferences():
    """
    Saves all addon preferences to a JSON file.
    """
    try:
        preferences_file = get_preferences_file_path()
        prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences

        preferences_dict = {
            # Logging Settings
            "log_level": prefs.log_level,
            "show_developer_settings": prefs.show_developer_settings,
            
            # Asset Path Properties
            "hdri_path": prefs.hdri_path,
            "hdri_path_2": prefs.hdri_path_2,
            "hdri_path_3": prefs.hdri_path_3,
            "gobo_path": prefs.gobo_path,
            "gobo_path_2": prefs.gobo_path_2,
            "gobo_path_3": prefs.gobo_path_3,
            "ies_profiles_path": prefs.ies_profiles_path,
            "ies_previews_path": prefs.ies_previews_path,
            "last_360_hdri_directory": prefs.last_360_hdri_directory,
            "last_scrim_directory": prefs.last_scrim_directory,
            
            # Initial Light Settings
            "initial_light_distance": prefs.initial_light_distance,
            "initial_light_power": prefs.initial_light_power,
            "initial_light_size": prefs.initial_light_size,
            "initial_light_temp": prefs.initial_light_temp,
            "use_scrim_for_area_lights": prefs.use_scrim_for_area_lights,
            "enable_mode_switch_keys": prefs.enable_mode_switch_keys,
            
            # Light Customization Properties
            "organize_lights": prefs.organize_lights,
            
            # Light Behavior Settings
            "use_calculated_light": prefs.use_calculated_light,
            "adjustment_mode_entry": prefs.adjustment_mode_entry,
            "hide_viewport_overlays": prefs.hide_viewport_overlays,
            "show_help_by_default": prefs.show_help_by_default,
            "orbit_sensitivity": prefs.orbit_sensitivity,
            "orbit_snap_mode": prefs.orbit_snap_mode,
            "preserve_light_spread": prefs.preserve_light_spread,
            "gizmo_row_position": prefs.gizmo_row_position,
            
            # Preview System Settings
            "show_texture_labels": prefs.show_texture_labels,
            "texture_preview_scale": prefs.texture_preview_scale,
            "texture_popup_scale": prefs.texture_popup_scale,
            
        }

        with open(preferences_file, 'w') as file:
            json.dump(preferences_dict, file, indent=4)
    except Exception as e:
        logger.error(f"Failed to save preferences: {str(e)}")

def load_preferences():
    """
    Loads addon preferences from a JSON file.
    """
    try:
        preferences_file = get_preferences_file_path()

        if not os.path.exists(preferences_file):
            return {} 

        with open(preferences_file, 'r') as file:
            return json.load(file)
    except PermissionError as e:
        logger.error(f"Permission error accessing preferences file: {str(e)}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error reading preferences file: {str(e)}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading preferences: {str(e)}")
        return {}

def apply_preferences():
    """
    Applies saved preferences to the addon.
    """
    saved_prefs = load_preferences()
    if saved_prefs: 
        try:
            prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
            
            # Apply logging preferences first
            if 'log_level' in saved_prefs:
                prefs.log_level = saved_prefs['log_level']
                from .utils import logger
                logger.get_logger().set_log_level(prefs.log_level)
            
            # Apply developer settings
            if 'show_developer_settings' in saved_prefs:
                prefs.show_developer_settings = saved_prefs['show_developer_settings']
            
            # Apply asset paths
            if 'hdri_path' in saved_prefs:
                prefs.hdri_path = saved_prefs['hdri_path']
            if 'hdri_path_2' in saved_prefs:
                prefs.hdri_path_2 = saved_prefs['hdri_path_2']
            if 'hdri_path_3' in saved_prefs:
                prefs.hdri_path_3 = saved_prefs['hdri_path_3']
            if 'gobo_path' in saved_prefs:
                prefs.gobo_path = saved_prefs['gobo_path']
            if 'gobo_path_2' in saved_prefs:
                prefs.gobo_path_2 = saved_prefs['gobo_path_2']
            if 'gobo_path_3' in saved_prefs:
                prefs.gobo_path_3 = saved_prefs['gobo_path_3']
            if 'ies_profiles_path' in saved_prefs:
                prefs.ies_profiles_path = saved_prefs['ies_profiles_path']
            if 'ies_previews_path' in saved_prefs:
                prefs.ies_previews_path = saved_prefs['ies_previews_path']
            if 'last_360_hdri_directory' in saved_prefs:
                prefs.last_360_hdri_directory = saved_prefs['last_360_hdri_directory']
            if 'last_scrim_directory' in saved_prefs:
                prefs.last_scrim_directory = saved_prefs['last_scrim_directory']
            
            # Apply light settings
            if 'initial_light_distance' in saved_prefs:
                prefs.initial_light_distance = saved_prefs['initial_light_distance']
            if 'initial_light_power' in saved_prefs:
                prefs.initial_light_power = saved_prefs['initial_light_power']
            if 'initial_light_size' in saved_prefs:
                prefs.initial_light_size = saved_prefs['initial_light_size']
            if 'initial_light_temp' in saved_prefs:
                prefs.initial_light_temp = saved_prefs['initial_light_temp']
            
            # Apply light customization
            if 'organize_lights' in saved_prefs:
                prefs.organize_lights = saved_prefs['organize_lights']
            
            # Apply light behavior
            if 'use_calculated_light' in saved_prefs:
                prefs.use_calculated_light = saved_prefs['use_calculated_light']
            if 'adjustment_mode_entry' in saved_prefs:
                prefs.adjustment_mode_entry = saved_prefs['adjustment_mode_entry']
            if 'hide_viewport_overlays' in saved_prefs:
                prefs.hide_viewport_overlays = saved_prefs['hide_viewport_overlays']
            if 'show_help_by_default' in saved_prefs:
                prefs.show_help_by_default = saved_prefs['show_help_by_default']
            if 'orbit_sensitivity' in saved_prefs:
                prefs.orbit_sensitivity = saved_prefs['orbit_sensitivity']
            if 'orbit_snap_mode' in saved_prefs:
                prefs.orbit_snap_mode = saved_prefs['orbit_snap_mode']
            if 'use_scrim_for_area_lights' in saved_prefs:
                prefs.use_scrim_for_area_lights = saved_prefs['use_scrim_for_area_lights']
            if 'enable_mode_switch_keys' in saved_prefs:
                prefs.enable_mode_switch_keys = saved_prefs['enable_mode_switch_keys']
            if 'preserve_light_spread' in saved_prefs:
                prefs.preserve_light_spread = saved_prefs['preserve_light_spread']
            if 'gizmo_row_position' in saved_prefs:
                prefs.gizmo_row_position = saved_prefs['gizmo_row_position']
            
            # Apply preview system settings
            if 'show_texture_labels' in saved_prefs:
                prefs.show_texture_labels = saved_prefs['show_texture_labels']
            if 'texture_preview_scale' in saved_prefs:
                prefs.texture_preview_scale = saved_prefs['texture_preview_scale']
            if 'texture_popup_scale' in saved_prefs:
                prefs.texture_popup_scale = saved_prefs['texture_popup_scale']
            
            # Apply index mappings
        except Exception as e:
            logger.error(f"Error applying preferences: {str(e)}")

def update_hdri_path(self, context):
    """
    Updates the HDRI path preference and refreshes previews.
    """
    save_all_preferences()
    # Refresh thumbnails
    from .utils.previews import unregister_previews, register_previews
    unregister_previews()
    register_previews()

def update_gobo_path(self, context):
    """
    Updates the Gobo path preference and refreshes previews.
    """
    save_all_preferences()
    scan_and_generate_thumbnails()
    # Refresh thumbnails
    from .utils.previews import unregister_previews, register_previews
    unregister_previews()
    register_previews()

def update_ies_path(self, context):
    """
    Updates the IES path preference and refreshes previews.
    """
    save_all_preferences()
    # Refresh thumbnails
    from .utils.previews import unregister_previews, register_previews
    unregister_previews()
    register_previews()

class LIGHTW_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    # Move from __init__ to class-level properties
    _light_keymaps: list = []
    _original_keymaps: list = []

    # Add the show_developer_settings property
    show_developer_settings: bpy.props.BoolProperty(
        name="Show Developer Settings",
        description="Expand to show developer settings",
        default=False
    )

    # Logging Settings
    log_level: bpy.props.EnumProperty(
        name="Log Level",
        description="Set the verbosity of logging",
        items=[
            ('DEBUG', "Debug", "Show all log messages including debug information"),
            ('INFO', "Info", "Show informational messages and above"),
            ('WARNING', "Warning", "Show warnings and errors only"),
            ('ERROR', "Error", "Show only error messages"),
            ('CRITICAL', "Critical", "Show only critical error messages"),
        ],
        default='CRITICAL',
        update=update_preference
    )

    # Asset Path Properties
    last_360_hdri_directory: bpy.props.StringProperty(
        name="Last 360 HDRI Directory",
        description="Last directory used for saving 360° HDRI renders",
        default="",
        subtype='DIR_PATH',
        options={'SKIP_SAVE'}
    )

    last_scrim_directory: bpy.props.StringProperty(
        name="Last Scrim Directory",
        subtype='DIR_PATH',
        default=""
    )    

    hdri_path: bpy.props.StringProperty(
        name="HDRI Folder 1",
        description="Path to the directory where custom HDRIs are stored.",
        subtype='DIR_PATH',
        update=update_hdri_path
    )

    hdri_path_2: bpy.props.StringProperty(
        name="HDRI Folder 2",
        description="Path to the directory where custom HDRIs are stored.",
        subtype='DIR_PATH',
        update=update_hdri_path
    )

    hdri_path_3: bpy.props.StringProperty(
        name="HDRI Folder 3",
        description="Path to the directory where custom HDRIs are stored.",
        subtype='DIR_PATH',
        update=update_hdri_path
    )

    gobo_path: bpy.props.StringProperty(
        name="Gobo Folder 1",
        description="Path to the directory where custom Gobos are stored.",
        subtype='DIR_PATH',
        update=update_gobo_path
    )

    gobo_path_2: bpy.props.StringProperty(
        name="Gobo Folder 2",
        description="Path to the directory where custom Gobos are stored.",
        subtype='DIR_PATH',
        update=update_gobo_path
    )

    gobo_path_3: bpy.props.StringProperty(
        name="Gobo Folder 3",
        description="Path to the directory where custom Gobos are stored.",
        subtype='DIR_PATH',
        update=update_gobo_path
    )

    ies_profiles_path: bpy.props.StringProperty(
        name="IES Profiles Folder",
        description="Path to the directory where custom IES profiles are stored.",
        subtype='DIR_PATH',
        update=update_ies_path
    )

    ies_previews_path: bpy.props.StringProperty(
        name="IES Previews Folder",
        description="Path to the directory where custom IES preview images are stored.",
        subtype='DIR_PATH',
        update=update_ies_path
    )

    # Light Customization Properties
    organize_lights: bpy.props.BoolProperty(
        name="Organize Lights (Beta)",
        description="Automatically place new lights into a specific 'Lights' collection and rename them to reflect their light mode",
        default=False, 
        update=update_preference
    )

    initial_light_temp: bpy.props.IntProperty(
        name="Initial Light Temperature",
        description="Set the initial color temperature of the light. Set to 0 to disable and use plain RGB emission.",
        default=6500,
        min=0,
        max=20000,
        subtype="NONE",
        update=update_preference
    )

    # Existing properties...
    toggle_light_visibility: bpy.props.BoolProperty(
        name="Light Visibility by Selection",
        description="Light visibility to camera toggles with selection: visible when selected, not visible when unselected. Only works when real-time compositor is off.",
        default=True,
        update=update_preference
    )

    is_light_mode: bpy.props.BoolProperty(
        name="Is Light Mode",
        default=False
    )
    
    # Initial Light Settings
    initial_light_distance: bpy.props.FloatProperty(
        name="Initial Distance",
        description="Default distance from surface for new lights",
        default=1.5,
        min=0.1,
        soft_max=10.0,
        unit='LENGTH',
        update=update_preference
    )
    initial_light_power: bpy.props.FloatProperty(
        name="Initial Power",
        description="Default power for new lights (except Sun lights)",
        default=10.0,
        min=0.0,
        soft_max=1000.0,
        unit='POWER',
        update=update_preference
    )
    initial_light_size: bpy.props.FloatProperty(
        name="Initial Size",
        description="Default size for area lights",
        default=1.0,
        min=0.01,
        soft_max=5.0,
        unit='LENGTH',
        update=update_preference
    )
    use_scrim_for_area_lights: bpy.props.BoolProperty(
        name="Use Scrim for New Area Lights",
        description="Set whether new area lights in Cycles will use Scrim mode by default",
        default=True,
        update=update_preference
    )
    
    enable_mode_switch_keys: bpy.props.BoolProperty(
        name="Direct Mode Entry Keys (1, 2, 3) ⚠️",
        description="Skip TAB and jump straight to a positioning mode with 1, 2, or 3. These keys also switch modes during active positioning. CAUTION: This will override Blender's collection visibility shortcuts and may discard any custom keymaps you have for these keys",
        default=False,
        update=update_mode_switch_keys_preference
    )
    
    # Light Behavior Settings
    hide_viewport_overlays: bpy.props.BoolProperty(
        name="Hide Viewport Overlays",
        description="Toggle to enable or disable viewport overlays hiding",
        default=True,
        update=update_preference
    )

    show_help_by_default: bpy.props.BoolProperty(
        name="Show Help By Default",
        description="Whether to show the help panel by default in new sessions",
        default=False,
        update=update_preference
    )

    use_calculated_light: bpy.props.BoolProperty(
        name="Auto-Adjust Light Power",
        description="Automatically adjust light power to maintain consistent illumination when changing size, distance, or spread (disabled in Gobo mode)",
        default=True,
        update=update_preference
    )

    adjustment_mode_entry: bpy.props.EnumProperty(
        name="Initial Positioning Mode",
        description="Controls how lights behave when entering adjustment mode",
        items=[
            ("last_used", "Remember Per Light", "Use each light's previous pause/active state when adjusting"),
            ("always_inactive", "Always Start Paused", "Always begin with positioning paused"),
        ],
        default="last_used",
        update=update_preference
    )

    orbit_sensitivity: bpy.props.FloatProperty(
        name="Orbit Sensitivity",
        description="Sensitivity of orbit mode",
        default=1.0,
        min=0.1,
        max=2.0,
        update=update_preference
    )
    
    orbit_snap_mode: bpy.props.EnumProperty(
        name="Orbit Axis Snap Mode",
        description="Choose whether Ctrl snaps to view axes or world axes in orbit mode",
        items=[
            ('VIEW', "View Axes", "Snap to viewport-relative axes (up/down, left/right, forward/back)"),
            ('WORLD', "World Axes", "Snap to world axes (X, Y, Z)")
        ],
        default='VIEW',
        update=update_preference
    )

    preserve_light_spread: bpy.props.BoolProperty(
        name="Keep HDRI Spread Values",
        description="When enabled, changing HDRIs won't reset your light's spread value",
        default=False,  # Default to False to maintain current behavior
        update=update_preference
    )
    
    scrim_version: bpy.props.EnumProperty(
        name="Scrim Version",
        description="Choose which version of the Scrim Light node group to use",
        items=[
            ('v1', "Version 1", "Fully procedural - lightweight, cloud render compatible"),
            ('v2', "Version 2", "Procedural with additional EXR textures - enhanced quality, uses more memory"),
            ('v2.1', "Version 2.1", "Latest enhanced version with improved quality"),
        ],
        default='v2.1',
        update=update_preference
    )
    
    gizmo_row_position: bpy.props.IntProperty(
        name="Gizmo Row Position",
        description="Which row the gizmo appears in (1=first available row, 2=next row, etc.)",
        default=1,
        min=1,
        max=20,
        update=update_preference
    )
    
    # Preview System Settings
    
    
    # Texture Preview UI Settings
    show_texture_labels: bpy.props.BoolProperty(
        name="Show Texture Labels",
        description="Display filename labels below texture previews in the Light Customization panel",
        default=False,
        update=update_preference
    )
    
    texture_preview_scale: bpy.props.IntProperty(
        name="Texture Preview Size",
        description="Size of texture thumbnails in the Light Customization panel",
        default=7,
        min=3,
        max=15,
        update=update_preference
    )
    
    texture_popup_scale: bpy.props.IntProperty(
        name="Texture Popup Size",
        description="Size of texture thumbnails in the popup selection window",
        default=5,
        min=3,
        max=10,
        update=update_preference
    )


    @property
    def light_keymaps(self):
        return self._light_keymaps

    @property
    def original_keymaps(self):
        return self._original_keymaps
    
    
    
        
    def draw(self, context):
        layout = self.layout

        # Initial Light Settings
        light_settings = layout.box()
        light_settings.label(text="Initial Light Settings", icon="LIGHT")

        cols = light_settings.row().split(factor=0.5)
        col1 = cols.column()
        col1.prop(self, "initial_light_distance")
        col1.prop(self, "initial_light_power")
        

        col2 = cols.column()
        col2.prop(self, "initial_light_size")
        col2.prop(self, "initial_light_temp")

        # Behavior settings in two columns
        behavior_row = light_settings.row()
        col1 = behavior_row.column()
        col1.prop(self, "use_scrim_for_area_lights")
        
        col2 = behavior_row.column()
        col2.prop(self, "preserve_light_spread")
        
        # Show scrim version selector only for Blender 4.3+
        if bpy.app.version >= (4, 3, 0):
            scrim_row = light_settings.row()
            scrim_row.prop(self, "scrim_version")

        # Light Behavior Box
        behavior_box = layout.box()
        behavior_box.label(text="Light Behavior", icon="LIGHT")
        
        # Smart Adjustments and Auto Light Visibility in separate columns
        row = behavior_box.row()
        col1 = row.column()
        col1.prop(self, "use_calculated_light", text="Auto-Adjust Light Power")
        
        col2 = row.column()
        col2.prop(self, "toggle_light_visibility", text="Light Visibility by Selection")
        
        # Edit mode settings in one row
        edit_row = behavior_box.row(align=True)
        edit_row.label(text="Edit Mode Positioning:")
        edit_row.prop(self, "adjustment_mode_entry", text="")
        
        # Orbit sensitivity and snap mode
        behavior_box.prop(self, "orbit_sensitivity", slider=True)
        behavior_box.prop(self, "orbit_snap_mode")

        # Viewport Settings Box
        viewport_box = layout.box()
        viewport_box.label(text="Viewport Settings", icon="WINDOW")
        
        # Gizmo row position in half-width column
        cols = viewport_box.row().split(factor=0.5)
        col1 = cols.column()
        col1.prop(self, "gizmo_row_position")
        
        col2 = cols.column()
        # Empty column to maintain half-width layout
        
        # Hide viewport overlays checkbox
        viewport_box.prop(self, "hide_viewport_overlays")

        # Experimental Features Box
        experimental_box = layout.box()
        experimental_box.label(text="Experimental Features", icon="ERROR")
        
        col = experimental_box.column(align=True)
        col.prop(self, "organize_lights")
        
        # Preview System Settings Box
        preview_box = layout.box()
        preview_box.label(text="Preview System", icon="IMAGE_DATA")
        
        # First row - Size sliders side by side
        cols = preview_box.row().split(factor=0.5)
        col1 = cols.column()
        col1.prop(self, "texture_preview_scale")
        
        col2 = cols.column()
        col2.prop(self, "texture_popup_scale")
        
        # Second row - Checkbox
        preview_box.prop(self, "show_texture_labels")

        # Custom Light Assets Section
        path_settings = layout.box()
        path_settings.label(text="Custom Light Assets", icon="FILE_FOLDER")
        warning_box = path_settings.box()
        warning_box.alert = True
        warning_box.label(text="Only set these paths if you want to use your personal textures!", icon="INFO")
        
        # HDRI Folders
        for i, path_prop in enumerate(['hdri_path', 'hdri_path_2', 'hdri_path_3'], 1):
            split = path_settings.split(factor=0.85, align=True)
            split.prop(self, path_prop)
            col = split.column(align=True)
            row = col.row(align=True)
            row.operator("lightwrangler.refresh_hdri_path", text="", icon='FILE_REFRESH').path_index = i
            row.operator("lightwrangler.clear_hdri_directory_path", text="", icon='X').path_index = i

        # Gobo Folders
        for i, path_prop in enumerate(['gobo_path', 'gobo_path_2', 'gobo_path_3'], 1):
            split = path_settings.split(factor=0.85, align=True)
            split.prop(self, path_prop)
            col = split.column(align=True)
            row = col.row(align=True)
            row.operator("lightwrangler.refresh_gobo_path", text="", icon='FILE_REFRESH').path_index = i
            row.operator("lightwrangler.clear_gobo_directory_path", text="", icon='X').path_index = i

        # IES Folders
        ies_box = path_settings.box()
        ies_box.label(text="IES Folders")
        
        for path_prop, label in [('ies_profiles_path', 'IES Profiles'), ('ies_previews_path', 'IES Previews')]:
            split = ies_box.split(factor=0.85, align=True)
            split.prop(self, path_prop, text=label)
            col = split.column(align=True)
            row = col.row(align=True)
            row.operator("lightwrangler.refresh_ies_path", text="", icon='FILE_REFRESH')
            row.operator("lightwrangler.clear_ies_directory_path", text="", icon='X')

        # Validation and info message
        if self.ies_profiles_path and self.ies_previews_path:
            ies_box.label(text="IES folders are set correctly.", icon="CHECKMARK")
        else:
            ies_box.label(text="Both IES folders must be set for custom IES to work.", icon="INFO")

        # Asset copyright management
        # Keymap Section
        keymap_box = layout.box()
        keymap_box.label(text="Keyboard Shortcuts", icon='KEYINGSET')
        
        col = keymap_box.column()

        # Mode switch keys setting
        col.prop(self, "enable_mode_switch_keys")

        # Show compact warning when enabled
        if self.enable_mode_switch_keys:
            alert_box = col.box()
            alert_row = alert_box.row()
            alert_row.label(text="", icon='ERROR')
            alert_col = alert_row.column()
            alert_col.scale_y = 0.9
            alert_col.label(text="Collection keys (1,2,3) are redirected to Light Wrangler modes.")
            alert_col.label(text="Disabling will restore Blender's default collection visibility.")
        
        # Draw actual keymap items
        wm = context.window_manager
        kc = wm.keyconfigs.user
        addon_kc = wm.keyconfigs.addon

        if kc and addon_kc:
            # Map operator IDs to our operators and their names - only showing main shortcuts
            operator_mapping = {
                "light_wrangler.add_light": "lightwrangler.add_interactive_light",
                "light_wrangler.adjust_light": "lightwrangler.interactive_mode",
                "light_wrangler.rotate_hdri": "light_wrangler.rotate_hdri",
                "light_wrangler.pie_menu": "wm.call_menu_pie"
            }
            
            # Collect keymap items
            keymap_items = []
            km = kc.keymaps.get('3D View')
            addon_km = addon_kc.keymaps.get('3D View')
            if km and addon_km:
                for kmi in km.keymap_items:
                    for desired_id, actual_id in operator_mapping.items():
                        # Handle special case for pie menu
                        if desired_id == "light_wrangler.pie_menu":
                            if (kmi.idname == actual_id and
                                hasattr(kmi.properties, 'name') and
                                kmi.properties.name == "LIGHTW_MT_light_pie_menu"):
                                keymap_items.append((desired_id, km, kmi))
                        else:
                            # Only check the operator ID and exclude number key mode switches
                            if kmi.idname == actual_id and not (
                                kmi.idname == "lightwrangler.interactive_mode" and
                                kmi.type in {"ONE", "TWO", "THREE"}
                            ):
                                keymap_items.append((desired_id, km, kmi))

            # Draw keymap items in the desired order
            for desired_id, km, kmi in keymap_items:
                self.draw_keymap_item(kc, km, kmi, col, desired_id)

        # Documentation and Support Section
        doc_and_support = layout.box()
        doc_and_support.label(text="Documentation and Support", icon="HELP")
        doc_cols = doc_and_support.row()
        doc_cols.operator(
            "wm.url_open", text="Documentation"
        ).url = "https://superhivemarket.com/products/light-wrangler/docs"
        doc_cols.operator(
            "wm.url_open", text="Report a Bug", icon="URL"
        ).url = "mailto:contact@leonidaltman.com?subject=Light%20Wrangler%20Bug%20Report"
        
        # Add Developer Settings at the end with a collapsible box
        dev_box = layout.box()
        row = dev_box.row()
        row.prop(self, "show_developer_settings", icon="TRIA_DOWN" if self.show_developer_settings else "TRIA_RIGHT", 
                 icon_only=True, emboss=False)
        row.label(text="Developer Settings", icon="CONSOLE")
        
        # Only show the contents if expanded
        if self.show_developer_settings:
            dev_box.prop(self, "log_level")

    def draw_keymap_item(self, kc, km, kmi, layout, desired_id):
        # Map operator IDs to custom names
        op_names = {
            "light_wrangler.add_light": "Add Light",
            "light_wrangler.adjust_light": "Adjust Light",
            "light_wrangler.rotate_hdri": "Rotate HDRI",
            "light_wrangler.pie_menu": "Light Pie Menu"
        }
        
        # Get the custom name
        op_name = op_names[desired_id]
        
        row = layout.row()
        row.label(text=op_name)
        
        # Draw the keymap item properties directly
        row.prop(kmi, "type", text="", full_event=True)

# Global keymap storage
lw_addon_keymaps = []

@persistent
def update_light_visibility(scene, depsgraph):
    # Check if playback is active
    if bpy.context.screen and bpy.context.screen.is_animation_playing:
        logger.debug("Skipping light visibility update during playback")
        return

    # Early return if feature is disabled or not using Cycles
    if not bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences.toggle_light_visibility or \
       bpy.context.scene.render.engine != "CYCLES":
        return

    # Check if compositor is being used
    compositor_used = False
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            shading = area.spaces.active.shading
            if supports_compositor():
                if hasattr(shading, 'use_compositor') and shading.use_compositor in {'CAMERA', 'ALWAYS'}:
                    compositor_used = True
                    break
            else:
                compositor_used = False

    if compositor_used:
        return

    # Process each light in the scene
    for obj in (obj for obj in scene.objects if obj.type == "LIGHT"):
        # Skip if manual override is active
        if obj.get("manual_visibility_override", False):
            continue

        supports_visibility = supports_object_visibility_toggle()
        current_selection = obj.select_get()
        
        if supports_visibility:
            current_visibility = obj.visible_camera
        else:
            current_visibility = not obj.hide_render

        # Initialize tracking if needed
        if "prev_visible_camera" not in obj:
            obj["prev_visible_camera"] = current_visibility
            continue

        # Get previous state
        prev_visibility = obj.get("prev_visible_camera")
        
        # Detect manual changes
        if prev_visibility != current_visibility:  # Visibility changed
            if current_visibility != current_selection:  # And doesn't match what auto would set
                # This was a manual change - set override
                obj["manual_visibility_override"] = True
                continue

        # Apply automatic behavior
        if current_selection != current_visibility:
            if supports_visibility:
                obj.visible_camera = current_selection
            else:
                obj.hide_render = not current_selection
            try:
                obj["prev_visible_camera"] = current_selection
            except AttributeError as e:
                if "Writing to ID classes in this context is not allowed" in str(e):
                    # Skip the write operation when in restricted context
                    pass
                else:
                    # Re-raise if it's a different AttributeError
                    raise


def restore_collection_keymaps(context):
    """Restore default Blender collection visibility keymaps for 1,2,3."""
    wm = context.window_manager
    kc = wm.keyconfigs.user

    if "Object Mode" in kc.keymaps:
        km = kc.keymaps["Object Mode"]

        # First remove any existing 1,2,3 keymaps
        for kmi in list(km.keymap_items):
            if kmi.type in {'ONE', 'TWO', 'THREE'}:
                km.keymap_items.remove(kmi)

        # Restore default collection visibility keymaps
        for i, key in enumerate(['ONE', 'TWO', 'THREE'], 1):
            kmi = km.keymap_items.new("object.hide_collection", key, "PRESS")
            kmi.properties.collection_index = i
            logger.debug(f"Restored default: {key} -> collection {i}")

def override_collection_keymaps(context):
    """Override user's 1,2,3 keys for Light Wrangler use."""
    wm = context.window_manager
    kc = wm.keyconfigs.user

    if "Object Mode" in kc.keymaps:
        km = kc.keymaps["Object Mode"]

        # Remove all 1,2,3 keymaps to clear the way for Light Wrangler
        for kmi in list(km.keymap_items):
            if kmi.type in {'ONE', 'TWO', 'THREE'}:
                key_type = kmi.type
                idname = kmi.idname
                km.keymap_items.remove(kmi)
                logger.debug(f"Removed user keymap: {key_type} ({idname})")

def cleanup_light_wrangler_mode_keymaps(context):
    """Remove Light Wrangler 1,2,3 keymaps from addon keyconfig."""
    wm = context.window_manager
    kc = wm.keyconfigs.addon

    if kc:
        for km in list(kc.keymaps):
            if km.space_type == 'VIEW_3D':
                for kmi in list(km.keymap_items[:]):
                    if (kmi.idname == "lightwrangler.interactive_mode" and
                        kmi.type in {'ONE', 'TWO', 'THREE'}):
                        km.keymap_items.remove(kmi)

def register_mode_switch_keymaps(context):
    """Register 1,2,3 mode switch keymaps immediately."""
    # Check if the operator is registered
    if not hasattr(bpy.ops.lightwrangler, 'interactive_mode'):
        # Operator not registered yet, skip keymap registration
        return
    
    wm = context.window_manager
    kc = wm.keyconfigs.addon
    
    if kc:
        
        # Check if keymaps already exist to avoid duplicates
        existing_keymaps = []
        for km in kc.keymaps:
            if km.space_type == 'VIEW_3D':
                for kmi in km.keymap_items:
                    if (kmi.idname == "lightwrangler.interactive_mode" and 
                        kmi.type in {'ONE', 'TWO', 'THREE'}):
                        existing_keymaps.append(kmi.type)
        
        # Only register if not already registered
        if 'ONE' not in existing_keymaps or 'TWO' not in existing_keymaps or 'THREE' not in existing_keymaps:
            # Get or create the keymap
            km = None
            for existing_km in kc.keymaps:
                if existing_km.name == "3D View" and existing_km.space_type == "VIEW_3D":
                    km = existing_km
                    break
            
            if not km:
                km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
            
            # Register missing keymaps
            if 'ONE' not in existing_keymaps:
                kmi = km.keymap_items.new("lightwrangler.interactive_mode", "ONE", "PRESS")
                if hasattr(kmi.properties, 'mode'):
                    kmi.properties.mode = 'REFLECT'
            
            if 'TWO' not in existing_keymaps:
                kmi = km.keymap_items.new("lightwrangler.interactive_mode", "TWO", "PRESS")
                if hasattr(kmi.properties, 'mode'):
                    kmi.properties.mode = 'ORBIT'
            
            if 'THREE' not in existing_keymaps:
                kmi = km.keymap_items.new("lightwrangler.interactive_mode", "THREE", "PRESS")
                if hasattr(kmi.properties, 'mode'):
                    kmi.properties.mode = 'DIRECT'

def register_keymaps():
    """
    Register keyboard shortcuts for the addon.
    This function sets up the keymaps for light manipulation modes.
    """
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        # Register main light manipulation keymaps
        km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
        
        # # Register number keys for different modes
        # kmi = km.keymap_items.new("lightwrangler.interactive_mode", "ONE", "PRESS")
        # kmi.properties.mode = 'REFLECT'
        
        # kmi = km.keymap_items.new("lightwrangler.interactive_mode", "TWO", "PRESS")
        # kmi.properties.mode = 'ORBIT'
        
        # kmi = km.keymap_items.new("lightwrangler.interactive_mode", "THREE", "PRESS")
        # kmi.properties.mode = 'DIRECT'

        # Check if TAB is already assigned in 3D View
        tab_assigned = any(
            kmi.type == "TAB" and kmi.active
            for km in kc.keymaps
            for kmi in km.keymap_items
            if km.space_type == "VIEW_3D"
        )

        # Register TAB or Shift+TAB for resuming last mode
        if tab_assigned:
            kmi = km.keymap_items.new("lightwrangler.interactive_mode", "TAB", "PRESS", shift=True)
        else:
            kmi = km.keymap_items.new("lightwrangler.interactive_mode", "TAB", "PRESS")

        # Register Alt+Right Mouse for HDRI rotation
        kmi = km.keymap_items.new(
            "light_wrangler.rotate_hdri", 
            'RIGHTMOUSE',  
            'PRESS',
            alt=True
        )

        # Register F9 for adding a new light
        kmi = km.keymap_items.new("lightwrangler.add_interactive_light", "F9", "PRESS")
        kmi.properties.light_type = 'AREA'  # Default to Area light

        lw_addon_keymaps.append(km)

def unregister_keymaps():
    """
    Unregister all keyboard shortcuts set by the addon, except mode-switching number keys.
    """
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        for km in lw_addon_keymaps:
            try:
                # Remove all keymap items except 1,2,3 mode switches
                for kmi in list(km.keymap_items):  # Create a copy of the list to modify during iteration
                    if not (kmi.idname == "lightwrangler.interactive_mode" and 
                           kmi.type in {"ONE", "TWO", "THREE"} and 
                           not kmi.any and not kmi.shift and not kmi.ctrl and not kmi.alt):
                        km.keymap_items.remove(kmi)
            except Exception as e:
                logger.error(f"Failed to remove keymap {km.name}: {e}")
    lw_addon_keymaps.clear()




class LIGHTW_OT_RefreshHDRIPath(bpy.types.Operator):
    """Reloads the HDRI images from the selected folder"""
    bl_idname = "lightwrangler.refresh_hdri_path"
    bl_label = "Refresh"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    path_index: bpy.props.IntProperty()

    def execute(self, context):
        # Call the path update function which handles refresh
        prefs = context.preferences.addons[ADDON_MODULE_NAME].preferences
        update_hdri_path(prefs, context)
        return {'FINISHED'}

class LIGHTW_OT_RefreshGoboPath(bpy.types.Operator):
    """Reloads the Gobos from the selected folder"""
    bl_idname = "lightwrangler.refresh_gobo_path"
    bl_label = "Refresh"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    path_index: bpy.props.IntProperty()

    def execute(self, context):
        # Call the path update function which handles refresh
        prefs = context.preferences.addons[ADDON_MODULE_NAME].preferences
        update_gobo_path(prefs, context)
        return {'FINISHED'}

class LIGHTW_OT_ClearHDRIDirectoryPath(bpy.types.Operator):
    """Clear the HDRI Folder Path"""
    bl_idname = "lightwrangler.clear_hdri_directory_path"
    bl_label = "Clear"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    path_index: bpy.props.IntProperty()

    def execute(self, context):
        prefs = context.preferences.addons[ADDON_MODULE_NAME].preferences
        if self.path_index == 1:
            prefs.hdri_path = ""
        elif self.path_index == 2:
            prefs.hdri_path_2 = ""
        elif self.path_index == 3:
            prefs.hdri_path_3 = ""
        return {'FINISHED'}

class LIGHTW_OT_ClearGoboDirectoryPath(bpy.types.Operator):
    """Clear the Gobo Folder Path"""
    bl_idname = "lightwrangler.clear_gobo_directory_path"
    bl_label = "Clear"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    path_index: bpy.props.IntProperty()

    def execute(self, context):
        prefs = context.preferences.addons[ADDON_MODULE_NAME].preferences
        if self.path_index == 1:
            prefs.gobo_path = ""
        elif self.path_index == 2:
            prefs.gobo_path_2 = ""
        elif self.path_index == 3:
            prefs.gobo_path_3 = ""
        return {'FINISHED'}

class LIGHTW_OT_RefreshIESPath(bpy.types.Operator):
    """Reloads the IES profiles from the selected folders"""
    bl_idname = "lightwrangler.refresh_ies_path"
    bl_label = "Refresh IES Previews"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def execute(self, context):
        # Call the path update function which handles refresh
        prefs = context.preferences.addons[ADDON_MODULE_NAME].preferences
        update_ies_path(prefs, context)
        return {'FINISHED'}

class LIGHTW_OT_ClearIESDirectoryPath(bpy.types.Operator):
    """Clear the IES Directory Path"""
    bl_idname = "lightwrangler.clear_ies_directory_path"
    bl_label = "Clear"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def execute(self, context):
        prefs = context.preferences.addons[ADDON_MODULE_NAME].preferences
        prefs.ies_profiles_path = ""
        prefs.ies_previews_path = ""
        return {'FINISHED'}


# Store the current set of lights
_previous_lights = set()

@persistent
def handle_light_deletion(scene, depsgraph):
    """Handler that cleans up custom data blocks when lights are deleted"""
    global _previous_lights
    
    try:
        # Get current lights
        current_lights = {obj.name for obj in bpy.data.objects if obj.type == 'LIGHT'}
        
        # Find deleted lights
        deleted_lights = _previous_lights - current_lights
        
        # Clean up unused custom data blocks
        if deleted_lights:
            for light_data in bpy.data.lights:
                # Check if this is our custom data block and has no users
                if light_data.users == 0 and any(light_data.name.startswith(f"{type}.") 
                   for type in ["Point", "Spot", "Area", "Sun"]):
                    bpy.data.lights.remove(light_data)
        
        # Update previous lights for next check
        _previous_lights = current_lights
    except (AttributeError, ReferenceError):
        # Reset the set if we can't access the data
        _previous_lights = set()

@persistent
def handle_font_reload(dummy):
    """Reinitialize the font when a new file is loaded."""
    from .utils import font_manager
    font_manager.FontManager.get_instance().reinitialize()



def register():
    # Set registration flag to prevent keymap changes during startup
    global _addon_registering
    _addon_registering = True

    # Initialize logger first
    from .utils import logger

    # Set default log level
    logger.start_section("Addon Registration")
    logger.info("Manual reload mode active - Use Ctrl+Shift+R or Window menu to reload addon")
    
    # Unregister old addon version if it exists
    from .utils import unregister_old_addon_version
    unregister_old_addon_version()
    
    # Initialize font manager
    logger.start_section("Font Manager Initialization")
    from .utils import font_manager
    font_manager.FontManager.get_instance()
    logger.end_section()
    
    # Register path management operators first
    logger.start_section("Path Management Operators")
    try:
        bpy.utils.register_class(LIGHTW_OT_RefreshHDRIPath)
        bpy.utils.register_class(LIGHTW_OT_RefreshGoboPath)
        bpy.utils.register_class(LIGHTW_OT_RefreshIESPath)
        bpy.utils.register_class(LIGHTW_OT_ClearHDRIDirectoryPath)
        bpy.utils.register_class(LIGHTW_OT_ClearGoboDirectoryPath)
        bpy.utils.register_class(LIGHTW_OT_ClearIESDirectoryPath)
        logger.debug("Path management operators registered successfully")
    except Exception as e:
        logger.error(f"Failed to register path management operators: {e}")
    logger.end_section()
    
    # Safely register preferences class
    logger.start_section("Preferences Registration")
    try:
        bpy.utils.register_class(LIGHTW_AddonPreferences)
        # Load saved preferences after registering the class
        apply_preferences()
        
        # Update logger level from preferences
        try:
            prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
            logger.get_logger().set_log_level(prefs.log_level)
            logger.info(f"Log level set to {prefs.log_level}")
        except Exception as e:
            logger.warning(f"Could not set log level from preferences: {e}")
            
        logger.debug("Preferences registered and applied successfully")
    except ValueError as e:
        # If already registered, try to unregister first
        if "already registered" in str(e):
            logger.warning(f"Preferences class already registered: {e}")
            try:
                bpy.utils.unregister_class(LIGHTW_AddonPreferences)
                bpy.utils.register_class(LIGHTW_AddonPreferences)
                # Load saved preferences after re-registering
                apply_preferences()
                logger.debug("Preferences re-registered successfully")
            except Exception as e2:
                logger.error(f"Error during preferences re-registration: {e2}")
                logger.end_section()
                logger.end_section("Addon Registration")
                return
    logger.end_section()
    
    # Register all modules in the correct order
    logger.start_section("Module Registration")
    
    logger.start_section("Properties")
    properties.register()
    logger.end_section()
    
    logger.start_section("Operators")
    operators.register()
    logger.end_section()
    
    logger.start_section("UI")
    ui.register()
    logger.end_section()
    
    logger.start_section("Gizmos")
    gizmos.register()
    logger.end_section()
    
    logger.end_section("Module Registration")
    
    # Register previews system after preferences are available
    logger.start_section("Preview System")
    register_previews()
    logger.end_section()

    # Disable collection hotkeys and register our keymaps
    logger.start_section("Keymap Registration")
    register_keymaps()
    logger.end_section()
    
    # Register handlers
    logger.start_section("Handler Registration")
    
    # First, remove any existing handlers to prevent duplicates
    # This is important when reloading the addon
    for handler_list in [bpy.app.handlers.depsgraph_update_post, bpy.app.handlers.load_post]:
        for handler in list(handler_list):
            if hasattr(handler, "__name__") and handler.__name__ in ["update_light_visibility", "handle_light_deletion", "handle_font_reload", "update_light_spread"]:
                try:
                    handler_list.remove(handler)
                    logger.debug(f"Removed existing handler {handler.__name__} before registration")
                except ValueError:
                    logger.warning(f"Could not remove existing handler {handler.__name__}")
    
    # Define handlers to register with proper error handling
    handlers_to_register = [
        (update_light_visibility, "update_light_visibility", bpy.app.handlers.depsgraph_update_post),
        (handle_light_deletion, "handle_light_deletion", bpy.app.handlers.depsgraph_update_post),
        (handle_font_reload, "handle_font_reload", bpy.app.handlers.load_post),
        (update_light_spread, "update_light_spread", bpy.app.handlers.depsgraph_update_post)
    ]
    
    for handler, name, handler_list in handlers_to_register:
        try:
            # Check if handler is already registered to avoid duplicates
            if handler not in handler_list:
                handler_list.append(handler)
                logger.debug(f"Registered {name} handler")
            else:
                logger.warning(f"{name} handler already registered")
        except Exception as e:
            logger.error(f"Failed to register {name} handler: {e}")
    
    logger.debug("Handlers registered successfully")
    logger.end_section()
    
    # Initialize previous lights set only if we can access the data
    logger.start_section("Light Tracking Initialization")
    try:
        global _previous_lights
        if hasattr(bpy.data, 'objects'):
            _previous_lights = {obj.name for obj in bpy.data.objects if obj.type == 'LIGHT'}
            logger.debug(f"Initialized light tracking with {len(_previous_lights)} lights")
        else:
            _previous_lights = set()
            logger.debug("Initialized empty light tracking set (no access to bpy.data.objects)")
    except Exception as e:
        _previous_lights = set()
        logger.error(f"Error initializing light tracking: {e}")
    logger.end_section()
    
    # Clear registration flag - now safe for user-triggered keymap changes
    _addon_registering = False

    logger.end_section("Addon Registration")
    logger.info("Light Wrangler addon registered successfully")

def unregister():
    logger.start_section("Addon Unregistration")
    
    # Clean up font manager
    logger.start_section("Font Manager Cleanup")
    from .utils import font_manager
    font_manager.FontManager.get_instance().cleanup()
    logger.end_section()
    
    # Unregister handlers
    logger.start_section("Handler Unregistration")
    
    # Import handlers from light_operators to ensure we have references to them
    try:
        from .operators.light_operators import light_type_changed, handle_light_selection_change
    except ImportError as e:
        logger.warning(f"Could not import handlers from light_operators: {e}")
        # Create dummy handlers to avoid errors
        @persistent
        def light_type_changed(scene, depsgraph): pass
        
        @persistent
        def handle_light_selection_change(scene, depsgraph): pass
    
    # First, check for any handlers with the same name (in case of reloads)
    # This is more reliable than checking for specific handler references
    handler_names = ["light_type_changed", "handle_light_selection_change", 
                    "update_light_visibility", "handle_light_deletion", 
                    "handle_font_reload", "update_light_spread"]
    
    handlers_removed = False
    for handler_list in [bpy.app.handlers.depsgraph_update_post, bpy.app.handlers.load_post]:
        for handler in list(handler_list):
            if hasattr(handler, "__name__") and handler.__name__ in handler_names:
                try:
                    handler_list.remove(handler)
                    logger.debug(f"Removed handler {handler.__name__} by name")
                    handlers_removed = True
                except ValueError:
                    logger.warning(f"Could not remove handler {handler.__name__} by name")
    
    # Only try to remove by reference if we didn't remove any by name
    if not handlers_removed:
        # Remove all handlers with proper error handling
        handlers_to_remove = [
            (update_light_visibility, "update_light_visibility", bpy.app.handlers.depsgraph_update_post),
            (handle_light_deletion, "handle_light_deletion", bpy.app.handlers.depsgraph_update_post),
            (handle_font_reload, "handle_font_reload", bpy.app.handlers.load_post),
            (light_type_changed, "light_type_changed", bpy.app.handlers.depsgraph_update_post),
            (handle_light_selection_change, "handle_light_selection_change", bpy.app.handlers.depsgraph_update_post)
        ]
        
        for handler, name, handler_list in handlers_to_remove:
            try:
                if handler in handler_list:
                    handler_list.remove(handler)
                    logger.debug(f"Removed {name} handler")
                else:
                    # Only log at debug level to reduce warning spam
                    logger.debug(f"{name} handler not found in handler list")
            except Exception as e:
                logger.error(f"Error removing {name} handler: {e}")
    
    logger.end_section()
    
    # Restore original keymaps and unregister our keymaps
    logger.start_section("Keymap Unregistration")
    unregister_keymaps()
    logger.end_section()
    
    # Unregister in reverse order
    logger.start_section("Module Unregistration")
    try:
        logger.start_section("Asset Copyright")
        logger.end_section()

        logger.start_section("UI")
        ui.unregister()
        logger.end_section()

        logger.start_section("Operators")
        operators.unregister()
        logger.end_section()

        logger.start_section("Properties")
        properties.unregister()
        logger.end_section()

        logger.start_section("Gizmos")
        gizmos.unregister()
        logger.end_section()
        
        logger.start_section("Preferences")
        try:
            bpy.utils.unregister_class(LIGHTW_AddonPreferences)
            logger.debug("Preferences unregistered successfully")
        except (ValueError, RuntimeError) as e:
            logger.warning(f"Preferences class already unregistered: {e}")
        logger.end_section()
    except Exception as e:
        logger.error(f"Error during class unregistration: {str(e)}")
    logger.end_section("Module Unregistration")
    
    
    # Unregister previews system last
    logger.start_section("Preview System Unregistration")
    unregister_previews()
    logger.end_section()
    
    # Unregister path management operators
    logger.start_section("Path Management Operators Unregistration")
    try:
        bpy.utils.unregister_class(LIGHTW_OT_ClearIESDirectoryPath)
        bpy.utils.unregister_class(LIGHTW_OT_ClearGoboDirectoryPath)
        bpy.utils.unregister_class(LIGHTW_OT_ClearHDRIDirectoryPath)
        bpy.utils.unregister_class(LIGHTW_OT_RefreshIESPath)
        bpy.utils.unregister_class(LIGHTW_OT_RefreshGoboPath)
        bpy.utils.unregister_class(LIGHTW_OT_RefreshHDRIPath)
        logger.debug("Path management operators unregistered successfully")
    except Exception as e:
        logger.error(f"Error unregistering path management operators: {e}")
    logger.end_section()
    
    # Clear previous lights set
    logger.start_section("Light Tracking Cleanup")
    global _previous_lights
    _previous_lights.clear()
    logger.debug("Light tracking set cleared")
    logger.end_section()
    
    logger.end_section("Addon Unregistration")
    logger.info("Light Wrangler addon unregistered successfully")

if __name__ == "__main__":
    register()
