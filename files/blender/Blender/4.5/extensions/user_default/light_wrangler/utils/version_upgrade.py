"""
Utility module for handling version upgrades of the Light Wrangler addon.
This module contains functions to ensure smooth transitions between different versions
of the addon, particularly for unregistering components from previous versions.
"""

import bpy
from bpy.app.handlers import persistent
from . import logger

def unregister_old_addon_version():
    """
    Unregister all components from the previous version of the Light Wrangler addon.
    This function is called at the beginning of the register() function to ensure
    a clean transition between versions without requiring manual uninstallation.
    """
    logger.start_section("Old Version Cleanup")
    
    # Unregister old classes
    unregister_old_classes()
    
    # Remove old properties
    remove_old_properties()
    
    # Remove old handlers
    remove_old_handlers()
    
    # Clean up old menu items
    remove_old_menu_items()
    
    # Unregister old keymaps
    unregister_old_keymaps()
    
    logger.end_section()
    logger.info("Old version cleanup completed")

def unregister_old_classes():
    """
    Attempt to unregister classes from the previous version of the addon.
    """
    logger.start_section("Old Classes")
    
    # List of class names from the previous version
    old_class_names = [
        "EmissionNodeState", "ClearHDRIDirectoryPath", "ClearGoboDirectoryPath", 
        "LightWranglerPreferences", "LightVisibilityState", "WorldNodeMuteState", 
        "LightWranglerProperties", "LIGHT_OT_apply_custom_data_block", 
        "OpenAddonPreferencesOperator", "MainPanel", "LightIntersectionGizmoGroup", 
        "LIGHT_GGT_lw_viewport_gizmos", "LIGHT_OT_lw_toggle_visibility", 
        "LightWranglerHintsProperties", "ConvertToPlaneOperator", "RefreshHDRIPath", 
        "RefreshGoboPath", "CopyAndAdjustLightOperator", "LightOperationsSubMenu", 
        "OpenMailOperator", "ProxyLightAtPointOperator", "AddEmptyAtIntersectionOperator", 
        "LightAtPointOperator", "AdjustLightPositionOperator", "Two_AdjustLightPositionOperator",
        "Three_AdjustLightPositionOperator", "TabAdjustLightPositionOperator",
        "LightWranglerSettings", "OBJECT_OT_LightTypeChanged", "LIGHT_OT_ScrimPreviewCreator",
        "RenderScrimOperator", "Render360HDROperator", "HDRI_PT_RenderPanel",
        "RefreshIESPath", "ClearIESDirectoryPath", "ClearTrackingOperator",
        "LIGHT_OT_confirm_cycles_switch", "LightWrangler_OT_hdri_rotate",
        "HDRI_OT_ShowInfo"
    ]
    
    # Try to unregister each class
    for class_name in old_class_names:
        try:
            # Find the class in bpy.types
            cls = getattr(bpy.types, class_name, None)
            if cls is not None:
                bpy.utils.unregister_class(cls)
                logger.log_unregistration(class_name)
            else:
                logger.debug(f"Class {class_name} not found, skipping")
        except Exception as e:
            logger.debug(f"Failed to unregister {class_name}: {e}")
    
    logger.end_section()

def remove_old_properties():
    """
    Remove properties registered by the previous version of the addon.
    """
    logger.start_section("Old Properties")
    
    # List of property paths from the previous version
    old_properties = [
        (bpy.types.WindowManager, "is_light_adjust_active"),
        (bpy.types.Scene, "light_wrangler"),
        (bpy.types.Scene, "light_wrangler_settings"),
        (bpy.types.Scene, "modal_running"),
        (bpy.types.Scene, "light_wrangler_hints")
    ]
    
    # Try to remove each property
    for prop_class, prop_name in old_properties:
        try:
            if hasattr(prop_class, prop_name):
                delattr(prop_class, prop_name)
                logger.debug(f"Removed property {prop_class.__name__}.{prop_name}")
            else:
                logger.debug(f"Property {prop_class.__name__}.{prop_name} not found, skipping")
        except Exception as e:
            logger.debug(f"Failed to remove property {prop_class.__name__}.{prop_name}: {e}")
    
    logger.end_section()

def remove_old_handlers():
    """
    Remove handlers registered by the previous version of the addon.
    """
    logger.start_section("Old Handlers")
    
    # List of handler names from the previous version
    old_handler_names = [
        "on_fps_change",
        "update_light_spread",
        "light_type_changed",
        "sync_node_values_handler",
        "after_load_handler",
        "update_light_visibility",
        "light_selection_handler"
    ]
    
    # Handler lists to check
    handler_lists = [
        bpy.app.handlers.depsgraph_update_post,
        bpy.app.handlers.depsgraph_update_pre,
        bpy.app.handlers.load_post
    ]
    
    # Remove handlers by name
    for handler_list in handler_lists:
        for handler in list(handler_list):
            if hasattr(handler, "__name__") and handler.__name__ in old_handler_names:
                try:
                    handler_list.remove(handler)
                    logger.debug(f"Removed handler {handler.__name__}")
                except ValueError:
                    logger.debug(f"Failed to remove handler {handler.__name__}")
    
    logger.end_section()

def remove_old_menu_items():
    """
    Remove menu items added by the previous version of the addon.
    """
    logger.start_section("Old Menu Items")
    
    # Try to remove menu items
    try:
        # We don't know the exact functions used, so we'll use placeholders
        # In a real implementation, you might need to define these functions
        # or import them from the old addon if possible
        menu_func_context_menu = lambda self, context: None
        menu_func_light_add = lambda self, context: None
        
        # Try to remove from menus
        try:
            bpy.types.VIEW3D_MT_object_context_menu.remove(menu_func_context_menu)
            logger.debug("Removed context menu item")
        except Exception as e:
            logger.debug(f"Failed to remove context menu item: {e}")
        
        try:
            bpy.types.VIEW3D_MT_light_add.remove(menu_func_light_add)
            logger.debug("Removed light add menu item")
        except Exception as e:
            logger.debug(f"Failed to remove light add menu item: {e}")
    except Exception as e:
        logger.debug(f"Error during menu cleanup: {e}")
    
    logger.end_section()

def unregister_old_keymaps():
    """
    Unregister keymaps from the previous version of the addon.
    """
    logger.start_section("Old Keymaps")
    
    # Try to clean up keymaps
    try:
        wm = bpy.context.window_manager
        kc = wm.keyconfigs.addon
        
        if kc:
            # We don't have access to the old keymap list, so we'll try to remove
            # keymaps based on the operator names
            old_operator_names = [
                "lightwrangler.proxy_light_at_point",
                "lightwrangler.adjust_light_position",
                # "lightwrangler.two_adjust_light_position",
                # "lightwrangler.three_adjust_light_position",
                "lightwrangler.tab_adjust_light_position",
                "lightwrangler.hdri_rotate"
            ]
            
            # Check all keymaps for these operators
            for km in kc.keymaps:
                for kmi in list(km.keymap_items):
                    if kmi.idname in old_operator_names:
                        try:
                            km.keymap_items.remove(kmi)
                            logger.debug(f"Removed keymap for {kmi.idname}")
                        except Exception as e:
                            logger.debug(f"Failed to remove keymap for {kmi.idname}: {e}")
    except Exception as e:
        logger.debug(f"Error during keymap cleanup: {e}")
    
    logger.end_section()

# def toggle_collection_hotkeys(key_types, action_idname, enable=True):
#     """
#     Toggle the active state of collection hotkeys.
    
#     :param key_types: List of key types to toggle
#     :param action_idname: The idname of the action to toggle
#     :param enable: Whether to enable (True) or disable (False) the hotkeys
#     """
#     try:
#         wm = bpy.context.window_manager
#         kc = wm.keyconfigs.user
#         target_keymaps = ["Object Mode", "3D View"]

#         for key_type in key_types:
#             for keymap_name, keymap in kc.keymaps.items():
#                 if keymap_name in target_keymaps:
#                     for item in keymap.keymap_items:
#                         try:
#                             if item.type == key_type and item.idname == action_idname:
#                                 item.active = enable
#                                 logger.debug(f"{'Enabled' if enable else 'Disabled'} {key_type} hotkey in {keymap_name}")
#                         except Exception as e:
#                             logger.debug(f"Error {'enabling' if enable else 'disabling'} hotkey {key_type} in {keymap_name}: {e}")
#     except Exception as e:
#         logger.debug(f"Error in toggle_collection_hotkeys: {e}")

# def enable_collection_hotkeys(key_types, action_idname):
#     """
#     Enable specified collection hotkeys.
#     """
#     toggle_collection_hotkeys(key_types, action_idname, enable=True) 