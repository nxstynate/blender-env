"""
Blender version compatibility utilities for Light Wrangler.

Handles breaking changes between Blender versions, particularly:
- Blender 5.0: world.use_nodes removal
- Blender 5.0: EEVEE render engine identifier changes
"""

import bpy


def world_has_nodes(world):
    """
    Check if a world has nodes enabled, compatible across Blender versions.
    
    Args:
        world: bpy.types.World object
        
    Returns:
        bool: True if world has nodes enabled/available
    """
    if not world:
        return False
    
    # Blender 5.0+: world.use_nodes removed, always has node tree
    if bpy.app.version >= (5, 0, 0):
        return world.node_tree is not None
    
    # Blender <5.0: check use_nodes property
    return world.use_nodes and world.node_tree is not None


def get_supported_render_engines():
    """
    Get set of render engines supported by Light Wrangler for current Blender version.
    
    Returns:
        set: Supported render engine identifiers
    """
    engines = {"CYCLES", "BLENDER_EEVEE", "octane"}
    
    # Blender <5.0: EEVEE Next exists as separate engine
    if bpy.app.version < (5, 0, 0):
        engines.add("BLENDER_EEVEE_NEXT")
    
    return engines


def is_eevee_engine(engine_name):
    """
    Check if the given engine is any variant of EEVEE.
    
    Args:
        engine_name (str): Render engine identifier
        
    Returns:
        bool: True if engine is EEVEE variant
    """
    if bpy.app.version >= (5, 0, 0):
        return engine_name == "BLENDER_EEVEE"
    else:
        return engine_name in {"BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"}


def get_eevee_engines():
    """
    Get set of EEVEE engine identifiers for current Blender version.
    
    Returns:
        set: EEVEE engine identifiers
    """
    if bpy.app.version >= (5, 0, 0):
        return {"BLENDER_EEVEE"}
    else:
        return {"BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"}


def supports_light_linking(engine_name):
    """
    Check if the given render engine supports light linking.
    
    Args:
        engine_name (str): Render engine identifier
        
    Returns:
        bool: True if engine supports light linking
    """
    if engine_name == "CYCLES":
        return True
    
    # EEVEE light linking support
    return is_eevee_engine(engine_name)


def get_cycles_compute_device_type():
    """
    Get Cycles compute device type, compatible across Blender versions.
    
    Returns:
        str or None: Compute device type ('CPU', 'CUDA', 'OPTIX', 'METAL', etc.) 
                     or None if Cycles addon not available
    """
    try:
        prefs = bpy.context.preferences
        
        # Both versions use the same access pattern, but Blender 5.0 
        # breaks dict-style addon access. The proper API still works.
        cycles_addon = prefs.addons.get('cycles')
        if cycles_addon and hasattr(cycles_addon, 'preferences'):
            return cycles_addon.preferences.compute_device_type
        
        return None
    except (AttributeError, KeyError):
        return None


def get_font_size():
    """
    Get appropriate font size for UI text, compatible across Blender versions.
    
    Returns:
        int: Font size (0 for Blender 3.0+, 12 for older versions)
    """
    if bpy.app.version >= (3, 0, 0):
        return 0  # Use default font size
    else:
        return 12  # Legacy font size


def get_preferences_section_name():
    """
    Get the correct preferences section name for addons.
    
    Returns:
        str: "Extensions" for Blender 4.2+, "Add-ons" for older versions
    """
    if bpy.app.version >= (4, 2, 0):
        return "Extensions"
    else:
        return "Add-ons"


def supports_compositor():
    """
    Check if compositor is available and enabled.
    
    Returns:
        bool: True if compositor is supported and enabled
    """
    if bpy.app.version >= (5, 0, 0):
        # Blender 5.0+ - compositor always uses nodes, check compositing_node_group
        scene = bpy.context.scene
        return (hasattr(scene, 'compositing_node_group') and
                scene.compositing_node_group is not None and
                len(scene.compositing_node_group.nodes) > 0)
    elif bpy.app.version >= (3, 0, 0):
        # Blender 3.0-4.x - check scene.use_nodes
        scene = bpy.context.scene
        if hasattr(scene, 'use_nodes'):
            return (scene.use_nodes and
                    scene.node_tree is not None and
                    len(scene.node_tree.nodes) > 0)
        return False
    else:
        # Legacy compositor check (pre-3.0)
        return bpy.context.scene.use_nodes


def supports_object_visibility_toggle():
    """
    Check if object visibility toggle is supported for this Blender version.
    
    Returns:
        bool: True if visibility toggle is supported
    """
    return bpy.app.version >= (3, 0, 0)


def supports_scrim_version_selection():
    """
    Check if Scrim version selection is supported.
    
    Returns:
        bool: True if Scrim version selection is available (Blender 4.3+)
    """
    return bpy.app.version >= (4, 3, 0)


def get_nodegroup_blend_filename():
    """
    Get the appropriate nodegroup blend filename for current Blender version.

    Returns:
        str: Filename for nodegroup blend file
    """
    if bpy.app.version >= (4, 0, 0):
        return "nodegroup-4.blend"
    else:
        return "nodegroup.blend"


def create_node_tree_driver(target_obj, property_path, source_id, source_type, source_path, expression="var"):
    """
    Create a driver that references node tree properties, handling Blender 5.0 changes.

    In Blender 5.0, node trees cannot be directly used as driver target IDs.
    We must reference them through their parent object (Light, Material, etc.)

    Args:
        target_obj: Object to add the driver to (e.g., node input socket)
        property_path: Property path for the driver (e.g., "default_value")
        source_id: The source ID for the driver (Light, Material, or Object)
        source_type: The type of source ('LIGHT', 'MATERIAL', 'OBJECT')
        source_path: Path to the property in the source
        expression: Driver expression (default "var")

    Returns:
        driver: The created driver object, or None if failed
    """
    try:
        # Remove existing driver if any
        try:
            target_obj.driver_remove(property_path)
        except:
            pass

        # Create new driver
        driver = target_obj.driver_add(property_path).driver
        driver.type = 'SCRIPTED'

        # Create variable
        var = driver.variables.new()
        var.name = "var"
        var.type = 'SINGLE_PROP'

        if bpy.app.version >= (5, 0, 0):
            # In Blender 5.0, we cannot use node_tree directly as target ID
            # We must reference through the parent object
            var.targets[0].id_type = source_type
            var.targets[0].id = source_id

            # Adjust the path to include node_tree prefix if needed
            if source_type in ['LIGHT', 'MATERIAL'] and not source_path.startswith('node_tree.'):
                var.targets[0].data_path = f'node_tree.{source_path}'
            else:
                var.targets[0].data_path = source_path
        else:
            # In Blender 4.x, we can use node_tree directly
            if source_type in ['LIGHT', 'MATERIAL'] and hasattr(source_id, 'node_tree'):
                var.targets[0].id_type = 'NODETREE'
                var.targets[0].id = source_id.node_tree
                var.targets[0].data_path = source_path
            else:
                var.targets[0].id_type = source_type
                var.targets[0].id = source_id
                var.targets[0].data_path = source_path

        driver.expression = expression

        return driver

    except Exception as e:
        print(f"Failed to create driver: {e}")
        return None