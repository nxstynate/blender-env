import bpy

class LIGHTW_MT_ContextMenu(bpy.types.Menu):
    bl_label = "Light Operations"
    bl_idname = "LIGHTW_MT_context_menu"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_DEFAULT'
        
        # Add light option - explicitly set to Area light
        op = layout.operator("lightwrangler.add_interactive_light", text="Add Light", icon='LIGHT_AREA')
        op.light_type = 'AREA'  # Always set to Area light
        
        # Add Adjust Light option - always show but enable only if a light is selected
        active_obj = context.active_object
        row = layout.row()
        row.enabled = bool(active_obj and active_obj.type == 'LIGHT')
        row.operator("lightwrangler.interactive_mode", text="Adjust Light", icon='ARROW_LEFTRIGHT')
        
        # Add Duplicate Light option - enabled only if a light is selected
        row = layout.row()
        row.enabled = bool(active_obj and active_obj.type == 'LIGHT')
        row.operator("lightwrangler.duplicate_light", text="Duplicate Light", icon='DUPLICATE')
        
        # Add tracking options - only for AREA and SPOT lights
        if active_obj and active_obj.type == 'LIGHT' and active_obj.data.type in {'AREA', 'SPOT'}:
            track_to_constraints = [c for c in active_obj.constraints if c.type == 'TRACK_TO']

            if track_to_constraints:
                # Check if any constraints are unmuted (active)
                has_active_tracking = any(not c.mute for c in track_to_constraints)

                if has_active_tracking:
                    layout.operator("lightwrangler.clear_tracking", text="Disable Tracking", icon="X")
                else:
                    layout.operator("lightwrangler.enable_tracking", text="Enable Tracking", icon="CON_TRACKTO")
            else:
                layout.operator("lightwrangler.track_to_target", text="Track to Target", icon="CON_TRACKTO")
        
        # Add preferences option
        layout.separator()
        layout.operator("lightwrangler.open_preferences", text="Preferences", icon="PREFERENCES")

def draw_light_wrangler_menu(self, context):
    layout = self.layout
    layout.menu(LIGHTW_MT_ContextMenu.bl_idname, icon='LIGHT')
    layout.separator()

class LIGHTW_MT_LightPieMenu(bpy.types.Menu):
    bl_label = "Add Light"
    bl_idname = "LIGHTW_MT_light_pie_menu"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        
        # Left - Point Light
        pie.operator("lightwrangler.add_interactive_light", text="Point", icon='LIGHT_POINT').light_type = 'POINT'
        # Right - Area Light
        pie.operator("lightwrangler.add_interactive_light", text="Area", icon='LIGHT_AREA').light_type = 'AREA'
        # Bottom - Spot Light
        pie.operator("lightwrangler.add_interactive_light", text="Spot", icon='LIGHT_SPOT').light_type = 'SPOT'
        # Top - Sun Light
        pie.operator("lightwrangler.add_interactive_light", text="Sun", icon='LIGHT_SUN').light_type = 'SUN'

# Store keymap items here to remove them on unregister
addon_keymaps = []

# Registration
classes = (
    LIGHTW_MT_ContextMenu,
    LIGHTW_MT_LightPieMenu,
)

def register():
    from ..utils import logger
    logger.start_section("UI Classes")
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            logger.log_registration(cls.__name__)
        except Exception as e:
            logger.log_registration(cls.__name__, False, str(e))
    
    # Add to the beginning of the right-click menu
    try:
        bpy.types.VIEW3D_MT_object_context_menu.prepend(draw_light_wrangler_menu)
        logger.debug("Added Light Wrangler to context menu")
    except Exception as e:
        logger.error(f"Failed to add Light Wrangler to context menu: {e}")
    
    # Add the keymap
    try:
        wm = bpy.context.window_manager
        kc = wm.keyconfigs.addon
        if kc:
            km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
            kmi = km.keymap_items.new("wm.call_menu_pie", 'A', 'PRESS', ctrl=True, shift=True)
            kmi.properties.name = LIGHTW_MT_LightPieMenu.bl_idname
            addon_keymaps.append((km, kmi))
            logger.debug("Registered Light Wrangler pie menu keymap")
        else:
            logger.warning("No addon keyconfig available, keymap not registered")
    except Exception as e:
        logger.error(f"Failed to register keymap: {e}")
    
    logger.end_section()

def unregister():
    from ..utils import logger
    logger.start_section("UI Classes")
    
    # Remove from the right-click menu
    try:
        bpy.types.VIEW3D_MT_object_context_menu.remove(draw_light_wrangler_menu)
        logger.debug("Removed Light Wrangler from context menu")
    except Exception as e:
        logger.error(f"Failed to remove Light Wrangler from context menu: {e}")
    
    # Remove the keymap
    try:
        # Make a copy of the list since we'll be modifying it
        keymap_items = addon_keymaps.copy()
        for km, kmi in keymap_items:
            try:
                # More robust check for keymap item existence
                if km and hasattr(km, 'keymap_items') and kmi:
                    # Check if the keymap item is still in the collection
                    try:
                        # Find the keymap item by iterating through the collection
                        found = False
                        for item in km.keymap_items:
                            if item == kmi:
                                found = True
                                break
                        
                        if found:
                            km.keymap_items.remove(kmi)
                            # Get a safe name for logging
                            km_name = getattr(km, 'name', 'Unknown Keymap')
                            kmi_name = getattr(kmi, 'idname', 'Unknown Item')
                            logger.debug(f"Removed keymap item {kmi_name} from {km_name}")
                        else:
                            # Get a safe name for logging
                            km_name = getattr(km, 'name', 'Unknown Keymap')
                            kmi_name = getattr(kmi, 'idname', 'Unknown Item')
                            # Log at debug level instead of warning to reduce noise
                            logger.debug(f"Keymap item {kmi_name} not found in {km_name}")
                    except (ReferenceError, AttributeError) as e:
                        logger.debug(f"Could not access keymap item: {e}")
                else:
                    logger.debug(f"Invalid keymap or keymap item reference")
            except Exception as e:
                logger.error(f"Failed to remove individual keymap item: {str(e)}")
        
        # Clear the list regardless of any errors
        addon_keymaps.clear()
        logger.debug("Cleared addon_keymaps list")
    except Exception as e:
        logger.error(f"Failed to unregister keymaps: {str(e)}")
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
            logger.log_unregistration(cls.__name__)
        except Exception as e:
            logger.log_unregistration(cls.__name__, False, str(e))
    
    logger.end_section() 