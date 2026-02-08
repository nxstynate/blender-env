import bpy
import os
import re
import math
from bpy.app.handlers import persistent
from .. import ADDON_MODULE_NAME
from mathutils import Vector
from . import logger
from .blender_compat import create_node_tree_driver

def ensure_node_tree(light):
    """Ensure the light has a node tree and return the nodes."""
    if not light.use_nodes:
        light.use_nodes = True
    return light.node_tree.nodes, light.node_tree.links

def get_output_node(nodes):
    """Get or create the light output node."""
    output = next((n for n in nodes if n.type == 'OUTPUT_LIGHT'), None)
    if not output:
        output = nodes.new('ShaderNodeOutputLight')
        output.location = (300, 0)
    return output

def get_emission_node(nodes, links, output_node):
    """Get or create the emission node."""
    emission = next((n for n in nodes if n.type == 'EMISSION'), None)
    if not emission:
        emission = nodes.new('ShaderNodeEmission')
        emission.location = (100, 0)
        links.new(emission.outputs[0], output_node.inputs[0])
    return emission

def apply_gobo_to_light(light_obj, gobo_name):
    """Apply a Gobo texture to a light."""
    logger.debug(f"Applying gobo: {gobo_name}")
    append_gobo_node_group()

    light = light_obj.data  # Get the light data from the object
    if not light.use_nodes:
        light.use_nodes = True

    nodes = light.node_tree.nodes

    gobo_node_group = None
    for node in nodes:
        if node.type == "GROUP" and node.node_tree and "Gobo Light" in node.node_tree.name:
            gobo_node_group = node
            break

    if gobo_node_group is None:
        for node in nodes:
            nodes.remove(node)

        base_node_group = bpy.data.node_groups["Gobo Light"]
        node_group = base_node_group.copy()
        node_group.name = f"Gobo Light {light.name}"

        gobo_node_group = nodes.new(type="ShaderNodeGroup")
        gobo_node_group.node_tree = node_group
        gobo_node_group.location = (0, 0)
        gobo_node_group.width = 175

        light_output_node = nodes.new(type="ShaderNodeOutputLight")
        light_output_node.location = (400, 0)
        links = light.node_tree.links
        links.new(light_output_node.inputs["Surface"], gobo_node_group.outputs["Emission"])
        apply_initial_color_temp_global(light)
    else:
        # Ensure each light has its own unique node group
        if gobo_node_group.node_tree.users > 1:
            new_node_group = gobo_node_group.node_tree.copy()
            new_node_group.name = f"Gobo Light {light.name}"
            gobo_node_group.node_tree = new_node_group
        node_group = gobo_node_group.node_tree

    possible_extensions = [
        ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp",
        ".gif", ".psd", ".exr", ".hdr", ".svg", ".mp4", 
        ".m4v", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".webm", ".ogv"
    ]

    gobo_image_path = None
    searched_paths = []

    # Handle new format (full file paths) and backwards compatibility
    if os.path.isabs(gobo_name):
        # New format: full file path
        logger.debug(f"Processing full path gobo: {gobo_name}")
        
        # Check if this is a preview path that needs conversion to source texture
        if "gobo_previews" in gobo_name:
            # This is a built-in preview, convert to source texture path
            base_name = os.path.basename(gobo_name)
            base_name_no_ext = os.path.splitext(base_name)[0]
            
            # Build path to gobo_textures directory
            texture_dir = os.path.join(os.path.dirname(gobo_name).replace("gobo_previews", "gobo_textures"))
            
            # Search for the actual texture file with any extension
            gobo_image_path = None
            for ext in possible_extensions:
                test_path = os.path.join(texture_dir, base_name_no_ext + ext)
                if os.path.exists(test_path):
                    gobo_image_path = test_path
                    logger.debug(f"Found gobo texture at: {gobo_image_path}")
                    break
            
            if not gobo_image_path:
                # Fallback to preview if no texture found
                gobo_image_path = gobo_name
                logger.debug(f"No texture found, using preview: {gobo_image_path}")
        else:
            # This is a custom texture path, use it directly
            gobo_image_path = gobo_name
            logger.debug(f"Using custom gobo path directly: {gobo_image_path}")
    else:
        # Backwards compatibility: handle old structured format
        parts = gobo_name.split(':', 2)
        if len(parts) >= 3 and parts[0] == "user":
            logger.debug("Searching for custom gobo (old format with path)")
            # For user gobos, the third part is the full file path
            gobo_image_path = parts[2]
            
            # Check if the file exists
            if os.path.exists(gobo_image_path):
                logger.debug(f"Found custom gobo at: {gobo_image_path}")
            else:
                logger.warning(f"Custom gobo file not found: {gobo_image_path}")
                gobo_image_path = None
                
        elif len(parts) >= 3 and parts[0] == "builtin":
            logger.debug("Searching for built-in gobo (old format)")
            # For built-in gobos, extract just the filename
            gobo_filename = parts[2]
            gobo_name_no_ext = os.path.splitext(gobo_filename)[0]
            base_path = os.path.join(os.path.dirname(__file__), "..", "gobo_textures", gobo_name_no_ext)
            for ext in possible_extensions:
                test_path = base_path + ext
                searched_paths.append(test_path)
                if os.path.exists(test_path):
                    gobo_image_path = test_path
                    logger.debug(f"Found built-in gobo at: {gobo_image_path}")
                    break
                    
        elif gobo_name.startswith("user:"):
            # Old format compatibility: "user:filename"
            logger.debug("Searching for custom gobo (old format)")
            addon_prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
            custom_folder_paths = [addon_prefs.gobo_path, addon_prefs.gobo_path_2, addon_prefs.gobo_path_3]
            
            # Remove the "_thumb.png" suffix if present for custom gobos
            if gobo_name.endswith("_thumb.png"):
                gobo_name = gobo_name[:-10]  # Remove last 10 characters ("_thumb.png")
            
            for folder_path in custom_folder_paths:
                if folder_path:
                    test_path = os.path.join(folder_path, gobo_name[5:])
                    searched_paths.append(test_path)
                    if os.path.exists(test_path):
                        gobo_image_path = test_path
                        logger.debug(f"Found custom gobo at: {gobo_image_path}")
                        break
                    else:
                        for ext in possible_extensions:
                            test_path_with_ext = test_path + ext
                            searched_paths.append(test_path_with_ext)
                            if os.path.exists(test_path_with_ext):
                                gobo_image_path = test_path_with_ext
                                logger.debug(f"Found custom gobo at: {gobo_image_path}")
                                break
                    if gobo_image_path:
                        break
        else:
            # Old format compatibility: just filename for built-in
            logger.debug("Searching for built-in gobo (old format)")
            gobo_name_no_ext = os.path.splitext(gobo_name)[0]
            base_path = os.path.join(os.path.dirname(__file__), "..", "gobo_textures", gobo_name_no_ext)
            for ext in possible_extensions:
                test_path = base_path + ext
                searched_paths.append(test_path)
                if os.path.exists(test_path):
                    gobo_image_path = test_path
                    logger.debug(f"Found built-in gobo at: {gobo_image_path}")
                    break

    if gobo_image_path:
        for node in gobo_node_group.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                try:
                    node.image = bpy.data.images.load(gobo_image_path, check_existing=True)
                    node.image.colorspace_settings.name = "sRGB"
                    logger.debug(f"Image loaded: {node.image.name}")
                    
                    if is_video_file(gobo_image_path):
                        video_fps = get_video_frame_rate_from_blender(gobo_image_path)
                        project_fps = bpy.context.scene.render.fps
                        logger.debug(f"Video FPS: {video_fps}, Project FPS: {project_fps}")
                        
                        if video_fps:
                            # Invert the speed factor to maintain original timing
                            speed_factor = video_fps / project_fps
                            logger.debug(f"Speed factor: {speed_factor}")
                            
                            # Use compatibility function for driver creation
                            driver = create_node_tree_driver(
                                node.image_user,
                                "frame_offset",
                                light,
                                'LIGHT',
                                'nodes["Group"].inputs[8].default_value',
                                f'frame * {speed_factor} * var % {node.image.frame_duration}'
                            )
                            logger.debug(f"Driver expression set: {driver.expression}")
                            
                            node.image_user.use_cyclic = True
                            node.image_user.use_auto_refresh = True
                            logger.debug("Video settings applied: cyclic and auto-refresh enabled")
                except Exception as e:
                    logger.error(f"Error loading image: {e}")
                    logger.error(f"Attempted to load from path: {gobo_image_path}")
                break
    else:
        logger.warning("Gobo image path does not exist for any known extension")
        logger.warning(f"Gobo name: {gobo_name}")
        logger.warning(f"Searched paths:")
        for path in searched_paths:
            logger.warning(f"  - {path}")

    logger.debug(f"Final gobo_image_path: {gobo_image_path}")

    # Add spread/radius update logic at the end
    min_spread_degrees = 0.2
    max_spread_degrees = 10
    min_spread_radians = math.radians(min_spread_degrees)
    max_spread_radians = math.radians(max_spread_degrees)

    min_radius = 0.01
    max_radius = 0.3

    for node in light.node_tree.nodes:
        if (isinstance(node, bpy.types.ShaderNodeGroup) 
            and "Gobo Light" in node.node_tree.name):
            focus_node = node.inputs.get("Focus", None)
            if focus_node:
                focus = int(focus_node.default_value)
                light_obj["last_focus"] = focus
                
                if light.type == "AREA":
                    spread = max_spread_radians - (focus / 100) * (
                        max_spread_radians - min_spread_radians
                    )
                    spread = max(min(spread, max_spread_radians), min_spread_radians)
                    old_spread = light.spread
                    light.spread = spread
                elif light.type == "SPOT":
                    radius = max_radius - (focus / 100) * (max_radius - min_radius)
                    radius = max(min(radius, max_radius), min_radius)
                    old_radius = light.shadow_soft_size
                    light.shadow_soft_size = radius
                break
    
    # Create a volume cube for the gobo light (if it doesn't already exist)
    light_obj = None
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT' and obj.data == light:
            light_obj = obj
            break
    
    if light_obj and light_obj.type == 'LIGHT' and light.type in {'SPOT', 'AREA'}:
        # Check if this light already has a volume cube
        has_volume_cube = False
        if "associated_volume_cubes" in light_obj:
            volume_cubes = list(light_obj["associated_volume_cubes"])
            for cube_name in volume_cubes:
                if cube_name in bpy.data.objects:
                    has_volume_cube = True
                    break
        
        if not has_volume_cube:
            # Find the image texture node in the light's node tree
            image_texture_node = None
            density_value = 0.1  # Default density for volume scatter
            
            for node in light.node_tree.nodes:
                if node.type == 'GROUP':
                    if 'Focus' in node.inputs:
                        # Use focus to influence density - higher focus = lower density
                        focus = node.inputs['Focus'].default_value
                        density_value = 0.3 - (focus / 100) * 0.25  # Scale between 0.05 and 0.3
                    
                    for sub_node in node.node_tree.nodes:
                        if sub_node.type == 'TEX_IMAGE':
                            image_texture_node = sub_node
                            break
                    if image_texture_node:
                        break
            
            if image_texture_node:
                # Get light properties
                location = light_obj.location.copy()
                rotation = light_obj.rotation_euler.copy()
                
                # Calculate cube size based on view distance and light properties
                if light.type == 'SPOT':
                    # For spot lights, create a cube that fits the spot cone
                    spot_size = light.spot_size  # Spot cone angle in radians
                    
                    # Calculate distance to fit current view
                    view_distance = 10.0  # Default distance
                    if bpy.context.space_data and bpy.context.space_data.type == 'VIEW_3D':
                        view_distance = (bpy.context.space_data.region_3d.view_location - location).length
                    
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
                    cube = bpy.context.active_object
                    cube.rotation_euler = rotation
                    cube.scale = (cube_size, cube_size, cube_depth)
                    
                else:  # AREA light
                    # For area lights, create a cube that extends from the light
                    if light.shape == 'RECTANGLE':
                        size_x = light.size * light_obj.scale.x
                        size_y = light.size_y * light_obj.scale.y
                    else:  # 'SQUARE', 'DISK', 'ELLIPSE'
                        size_x = light.size * light_obj.scale.x
                        size_y = light.size * light_obj.scale.y
                    
                    # Calculate view distance
                    view_distance = 10.0  # Default distance
                    if bpy.context.space_data and bpy.context.space_data.type == 'VIEW_3D':
                        view_distance = (bpy.context.space_data.region_3d.view_location - location).length
                    
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
                    cube = bpy.context.active_object
                    cube.rotation_euler = rotation
                    cube.scale = (cube_size_x, cube_size_y, cube_depth)
                
                # Generate a unique name for the cube
                existing_names = {obj.name for obj in bpy.data.objects if "Gobo Volume" in obj.name}
                count = 1
                base_name = "Gobo Volume"
                cube_name = base_name
                while cube_name in existing_names:
                    cube_name = f"{base_name}.{str(count).zfill(3)}"
                    count += 1
                
                cube.name = cube_name
                
                # Create a new material for the volume
                material_name = f"{cube.name}_Material"
                volume_material = bpy.data.materials.new(name=material_name)
                cube.data.materials.append(volume_material)
                
                # Set up the volume material with the Gobo Volume node group
                volume_material.use_nodes = True
                nodes = volume_material.node_tree.nodes
                links = volume_material.node_tree.links
                
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
                if "Gobo Volume" in bpy.data.node_groups:
                    gobo_volume = nodes.new('ShaderNodeGroup')
                    gobo_volume.node_tree = bpy.data.node_groups["Gobo Volume"]
                    links.new(gobo_volume.outputs[0], output.inputs['Volume'])
                
                # Set material settings
                if hasattr(volume_material, 'blend_method'):
                    volume_material.blend_method = 'BLEND'
                
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
                # Store the original view distance for Z scale calculation
                view_distance = cube.scale.z
                if light.type == 'SPOT':
                    # For spot lights, X and Y scales are based on spot size
                    # Driver for X scale
                    x_driver = cube.driver_add("scale", 0).driver
                    x_driver.type = 'SCRIPTED'
                    var = x_driver.variables.new()
                    var.name = "spot_size"
                    var.type = 'SINGLE_PROP'
                    var.targets[0].id = light_obj
                    var.targets[0].data_path = "data.spot_size"
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
                    var.targets[0].id = light_obj
                    var.targets[0].data_path = "data.spot_size"
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
                    var.targets[0].id = light_obj
                    var.targets[0].data_path = "data.size"
                    x_driver.expression = "light_size * 1.2"
                    
                    # Driver for Y scale (depends on light shape)
                    y_driver = cube.driver_add("scale", 1).driver
                    y_driver.type = 'SCRIPTED'
                    
                    # Add variable for shape
                    var_shape = y_driver.variables.new()
                    var_shape.name = "shape"
                    var_shape.type = 'SINGLE_PROP'
                    var_shape.targets[0].id = light_obj
                    var_shape.targets[0].data_path = "data.shape"
                    
                    # Add variable for size
                    var_size = y_driver.variables.new()
                    var_size.name = "size"
                    var_size.type = 'SINGLE_PROP'
                    var_size.targets[0].id = light_obj
                    var_size.targets[0].data_path = "data.size"
                    
                    # Add variable for size_y (for RECTANGLE and ELLIPSE shapes)
                    var_size_y = y_driver.variables.new()
                    var_size_y.name = "size_y"
                    var_size_y.type = 'SINGLE_PROP'
                    var_size_y.targets[0].id = light_obj
                    var_size_y.targets[0].data_path = "data.size_y"
                    
                    # Expression that checks shape and uses appropriate dimension
                    y_driver.expression = "size_y * 1.2 if shape in ['RECTANGLE', 'ELLIPSE'] else size * 1.2"
                
                # Add driver for visibility based on the Activate checkbox
                # Hide the cube initially
                cube.hide_viewport = True
                cube.hide_render = True
                
                # Add driver for viewport visibility
                create_node_tree_driver(
                    cube,
                    "hide_viewport",
                    light,
                    'LIGHT',
                    'nodes["Group"].inputs[4].default_value',
                    "not var"
                )
                
                # Add driver for render visibility
                create_node_tree_driver(
                    cube,
                    "hide_render",
                    light,
                    'LIGHT',
                    'nodes["Group"].inputs[4].default_value',
                    "not var"
                )
                
                # Add drivers for Density and Uniformity
                # Driver for Density
                create_node_tree_driver(
                    gobo_volume.inputs[0],
                    "default_value",
                    light,
                    'LIGHT',
                    'nodes["Group"].inputs[5].default_value',
                    "var"
                )
                
                # Driver for Uniformity
                create_node_tree_driver(
                    gobo_volume.inputs[1],
                    "default_value",
                    light,
                    'LIGHT',
                    'nodes["Group"].inputs[6].default_value',
                    "var"
                )
                
                # Set the light object back as active
                light_obj.select_set(True)
                bpy.context.view_layer.objects.active = light_obj

def apply_hdri_to_light(light, hdri_name):
    """Apply an HDRI texture to a light."""
    append_hdri_node_group()

    if not light.data.use_nodes:
        light.data.use_nodes = True

    nodes = light.data.node_tree.nodes

    hdri_node_group = None
    for node in nodes:
        if node.type == "GROUP" and node.node_tree and "HDRI Light" in node.node_tree.name:
            hdri_node_group = node
            break

    if hdri_node_group is None:
        for node in nodes:
            nodes.remove(node)

        base_node_group = bpy.data.node_groups["HDRI Light"]
        node_group = base_node_group.copy()
        node_group.name = f"HDRI Light {light.name}"

        hdri_node_group = nodes.new(type="ShaderNodeGroup")
        hdri_node_group.node_tree = node_group
        hdri_node_group.location = (0, 0)
        hdri_node_group.width = 175

        light_output_node = nodes.new(type="ShaderNodeOutputLight")
        light_output_node.location = (400, 0)
        links = light.data.node_tree.links
        links.new(
            light_output_node.inputs["Surface"], hdri_node_group.outputs["Emission"]
        )

        apply_initial_color_temp_global(light.data)
    else:
        # Ensure each light has its own unique node group
        if hdri_node_group.node_tree.users > 1:
            new_node_group = hdri_node_group.node_tree.copy()
            new_node_group.name = f"HDRI Light {light.name}"
            hdri_node_group.node_tree = new_node_group
        node_group = hdri_node_group.node_tree

    possible_extensions = [
        ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".psd",
        ".exr", ".hdr", ".svg", ".mp4", ".m4v", ".avi", ".mov", ".wmv",
        ".flv", ".mkv", ".webm", ".ogv", ".webp"
    ]

    # Handle new format (full file paths) and backwards compatibility
    if os.path.isabs(hdri_name):
        # New format: full file path
        logger.debug(f"Processing full path HDRI: {hdri_name}")
        
        # Check if this is a preview path that needs conversion to source texture
        if "hdri_previews" in hdri_name:
            # This is a built-in preview, convert to source texture path
            base_name = os.path.basename(hdri_name)
            base_name_no_ext = os.path.splitext(base_name)[0]
            
            # Build path to hdri_textures directory
            texture_dir = os.path.join(os.path.dirname(hdri_name).replace("hdri_previews", "hdri_textures"))
            
            # Search for the actual texture file with any extension
            hdri_image_path = None
            for ext in possible_extensions:
                test_path = os.path.join(texture_dir, base_name_no_ext + ext)
                if os.path.exists(test_path):
                    hdri_image_path = test_path
                    logger.debug(f"Found HDRI texture at: {hdri_image_path}")
                    break
            
            if not hdri_image_path:
                # Fallback to preview if no texture found
                hdri_image_path = hdri_name
                logger.debug(f"No texture found, using preview: {hdri_image_path}")
        else:
            # This is a custom texture path, use it directly
            hdri_image_path = hdri_name
            logger.debug(f"Using custom HDRI path directly: {hdri_image_path}")
    else:
        # Backwards compatibility: handle old structured format
        parts = hdri_name.split(':', 2)
        if len(parts) >= 3 and parts[0] == "user":
            # For user HDRIs, the third part is the full file path
            hdri_image_path = parts[2]
        elif len(parts) >= 3 and parts[0] == "builtin":
            # For built-in HDRIs, extract just the filename
            hdri_filename = parts[2]
            hdri_name_no_ext = os.path.splitext(hdri_filename)[0]
            base_path = os.path.join(
                os.path.dirname(__file__), "..", "hdri_textures", hdri_name_no_ext
            )
            hdri_image_path = None
            for ext in possible_extensions:
                test_path = base_path + ext
                if os.path.exists(test_path):
                    hdri_image_path = test_path
                    break
        elif hdri_name.startswith("user:"):
            # Old format compatibility: "user:filepath"
            hdri_image_path = hdri_name[5:]
        else:
            # Old format compatibility: just filename for built-in
            hdri_name_no_ext = os.path.splitext(hdri_name)[0]
            base_path = os.path.join(
                os.path.dirname(__file__), "..", "hdri_textures", hdri_name_no_ext
            )
            hdri_image_path = None
            for ext in possible_extensions:
                test_path = base_path + ext
                if os.path.exists(test_path):
                    hdri_image_path = test_path
                    break

    if hdri_image_path:
        for node in hdri_node_group.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                try:
                    node.image = bpy.data.images.load(
                        hdri_image_path, check_existing=True
                    )
                    if is_video_file(hdri_image_path):
                        node.image_user.frame_duration = node.image.frame_duration
                        node.image_user.use_cyclic = True
                        node.image_user.use_auto_refresh = True
                except Exception as e:
                    logger.error(f"Error loading image: {e}")
                break
    else:
        logger.warning("HDRI image path does not exist for any known extension")
        logger.warning(f"HDRI image path: {hdri_image_path}")

    # Check if spread preservation is enabled in preferences
    from .. import ADDON_MODULE_NAME
    try:
        addon_prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
        preserve_spread = addon_prefs.preserve_light_spread
    except (AttributeError, KeyError):
        preserve_spread = False  # Default to False if preferences not available
    
    # Only apply spread adjustment if preservation is disabled
    if not preserve_spread:
        spread_value = None
        # Extract the filename from the full path/identifier for spread detection
        hdri_filename = hdri_name
        if ':' in hdri_name:
            parts = hdri_name.split(':', 2)
            if len(parts) >= 3:
                hdri_filename = os.path.basename(parts[2])
        
        match = re.search(r"spread(\d+)", hdri_filename)
        if match:
            spread_value = int(match.group(1))
        else:
            # Use default spread value of 180 degrees
            spread_value = 180

        if spread_value is not None:
            light.data.spread = math.radians(spread_value)

def apply_ies_to_light(light, ies_name):
    """Apply an IES profile to a light."""
    append_ies_node_group()

    light.data.shadow_soft_size = 0

    if not light.data.use_nodes:
        light.data.use_nodes = True
    nodes = light.data.node_tree.nodes

    ies_node_group = None
    for node in nodes:
        if node.type == "GROUP" and node.node_tree and "IES Light" in node.node_tree.name:
            ies_node_group = node
            break

    if ies_node_group is None:
        for node in nodes:
            nodes.remove(node)

        base_node_group = bpy.data.node_groups["IES Light"]
        node_group = base_node_group.copy()
        node_group.name = f"IES Light {light.name}"

        ies_node_group = nodes.new(type="ShaderNodeGroup")
        ies_node_group.node_tree = node_group
        ies_node_group.location = (0, 0)
        ies_node_group.width = 175

        light_output_node = nodes.new(type="ShaderNodeOutputLight")
        light_output_node.location = (400, 0)
        links = light.data.node_tree.links
        links.new(
            light_output_node.inputs["Surface"], ies_node_group.outputs["Emission"]
        )

        apply_initial_color_temp_global(light.data)
    else:
        # Ensure each light has its own unique node group
        if ies_node_group.node_tree.users > 1:
            new_node_group = ies_node_group.node_tree.copy()
            new_node_group.name = f"IES Light {light.name}"
            ies_node_group.node_tree = new_node_group
        node_group = ies_node_group.node_tree

    ies_filepath = None
    # Handle new format (full file paths) and backwards compatibility
    if os.path.isabs(ies_name):
        # New format: full file path
        logger.debug(f"Processing full path IES: {ies_name}")
        
        # Check if this is a preview path that needs conversion to IES profile
        if "ies_previews" in ies_name:
            # This is a built-in preview, convert to IES profile path
            base_name = os.path.basename(ies_name)
            base_name_no_ext = os.path.splitext(base_name)[0]
            
            # Build path to ies_profiles directory
            ies_dir = os.path.join(os.path.dirname(ies_name).replace("ies_previews", "ies_profiles"))
            ies_filepath = os.path.join(ies_dir, base_name_no_ext + ".ies")
            
            if not os.path.exists(ies_filepath):
                logger.warning(f"IES profile not found at: {ies_filepath}")
                ies_filepath = None
        else:
            # This is a custom preview path, need to find the corresponding .ies file
            addon_prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
            if addon_prefs.ies_profiles_path:
                # Extract filename from the preview path and change extension to .ies
                preview_filename = os.path.basename(ies_name)
                ies_filename = os.path.splitext(preview_filename)[0] + '.ies'
                ies_filepath = os.path.join(addon_prefs.ies_profiles_path, ies_filename)
                
                if not os.path.exists(ies_filepath):
                    logger.warning(f"IES profile not found at: {ies_filepath}")
                    ies_filepath = None
    else:
        # Backwards compatibility: handle old structured format
        parts = ies_name.split(':', 2)
        if len(parts) >= 3 and parts[0] == "user":
            # For user IES, we need to convert the preview image path to .ies file path
            addon_prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
            if addon_prefs.ies_profiles_path:
                # Extract filename from the preview path and change extension to .ies
                preview_filename = os.path.basename(parts[2])
                ies_filename = os.path.splitext(preview_filename)[0] + '.ies'
                ies_filepath = os.path.join(addon_prefs.ies_profiles_path, ies_filename)
        elif len(parts) >= 3 and parts[0] == "builtin":
            # For built-in IES, extract just the filename
            ies_filename = parts[2]
            ies_name_no_ext = os.path.splitext(ies_filename)[0]
            base_path = os.path.join(os.path.dirname(__file__), "..", "ies_profiles", ies_name_no_ext)
            ies_filepath = base_path + ".ies"
        elif ies_name.startswith("user:"):
            # Old format compatibility: "user:filename"
            addon_prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
            if addon_prefs.ies_profiles_path:
                ies_filepath = os.path.join(addon_prefs.ies_profiles_path, ies_name[5:])
        elif ies_name.startswith("builtin:"):
            # Old format compatibility: "builtin:filename"
            ies_name_no_prefix = ies_name[8:]  # Remove "builtin:" prefix
            ies_name_no_ext = os.path.splitext(ies_name_no_prefix)[0]
            base_path = os.path.join(os.path.dirname(__file__), "..", "ies_profiles", ies_name_no_ext)
            ies_filepath = base_path + ".ies"
        else:
            logger.warning(f"Unexpected IES name format: {ies_name}")
            return

    if ies_filepath and os.path.exists(ies_filepath):
        logger.debug(f"IES file exists: {ies_filepath}")
        shader_node_ies = None
        for node in ies_node_group.node_tree.nodes:
            if node.type == "TEX_IES":
                shader_node_ies = node
                break

        if shader_node_ies:
            try:
                shader_node_ies.filepath = ies_filepath
                shader_node_ies.mode = "EXTERNAL"
                logger.debug(
                    f"IES file set to ShaderNodeTexIES node: {shader_node_ies.filepath}"
                )
                logger.debug(f"Mode set to: {shader_node_ies.mode}")
            except Exception as e:
                logger.error(f"Error setting IES file to ShaderNodeTexIES node: {e}")
        else:
            logger.warning("No ShaderNodeTexIES node found in the group.")
    else:
        logger.warning(f"IES file does not exist: {ies_filepath}")

def apply_scrim_to_light(light_data_block):
    """Apply a scrim to a light."""
    append_scrim_node_group()

    if not light_data_block.use_nodes:
        light_data_block.use_nodes = True

    nodes = light_data_block.node_tree.nodes

    for node in nodes:
        nodes.remove(node)

    # Determine base node group name based on preference and Blender version
    addon_prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
    scrim_pref = getattr(addon_prefs, 'scrim_version', 'v2')
    
    if bpy.app.version >= (4, 3, 0):  # Blender 4.3+
        # Use preference directly
        if scrim_pref == 'v1':
            base_node_group_name = "Scrim Light v1"
        elif scrim_pref == 'v2':
            base_node_group_name = "Scrim Light v2"
        else:  # v2.1
            base_node_group_name = "Scrim Light v2.1"
    elif bpy.app.version >= (4, 0, 0):  # Blender 4.0-4.2
        base_node_group_name = "Scrim Light v1"
    else:  # Blender 3.x and below
        base_node_group_name = "Scrim Light"

    base_node_group = bpy.data.node_groups[base_node_group_name]
    unique_node_group_name = f"{base_node_group_name} {bpy.context.object.name}"

    if unique_node_group_name not in bpy.data.node_groups:
        node_group = base_node_group.copy()
        node_group.name = unique_node_group_name
    else:
        node_group = bpy.data.node_groups[unique_node_group_name]

    group_node = nodes.new(type="ShaderNodeGroup")
    group_node.node_tree = node_group
    group_node.location = (0, 0)
    group_node.width = 175

    light_output_node = nodes.new(type="ShaderNodeOutputLight")
    light_output_node.location = (400, 0)

    links = light_data_block.node_tree.links
    links.new(light_output_node.inputs["Surface"], group_node.outputs["Emission"])

def use_default_light(light):
    """Reset a light to its default state."""
    if not light.data.use_nodes:
        light.data.use_nodes = True
    nodes = light.data.node_tree.nodes

    for node in nodes:
        nodes.remove(node)

    emission_node = nodes.new(type="ShaderNodeEmission")
    emission_node.location = (0, 0)

    light_output_node = nodes.new(type="ShaderNodeOutputLight")
    light_output_node.location = (200, 0)

    links = light.data.node_tree.links
    links.new(emission_node.outputs["Emission"], light_output_node.inputs["Surface"])

def append_gobo_node_group():
    """Append the Gobo Light node group from the nodegroup blend file."""
    nodegroup_name = "Gobo Light"
    blender_version = bpy.app.version
    if blender_version[0] >= 4:
        nodegroup_blend_path = os.path.join(
            os.path.dirname(__file__), "..", "nodegroup-4.blend"
        )
    else:
        nodegroup_blend_path = os.path.join(
            os.path.dirname(__file__), "..", "nodegroup.blend"
        )

    if nodegroup_name not in bpy.data.node_groups:
        with bpy.data.libraries.load(nodegroup_blend_path, link=False) as (
            data_from,
            data_to,
        ):
            if nodegroup_name in data_from.node_groups:
                data_to.node_groups = [nodegroup_name]

def append_hdri_node_group():
    """Append the HDRI Light node group from the nodegroup blend file."""
    nodegroup_name = "HDRI Light"
    blender_version = bpy.app.version
    if blender_version[0] >= 4:
        nodegroup_blend_path = os.path.join(
            os.path.dirname(__file__), "..", "nodegroup-4.blend"
        )
    else:
        nodegroup_blend_path = os.path.join(
            os.path.dirname(__file__), "..", "nodegroup.blend"
        )

    if nodegroup_name not in bpy.data.node_groups:
        with bpy.data.libraries.load(nodegroup_blend_path, link=False) as (
            data_from,
            data_to,
        ):
            if nodegroup_name in data_from.node_groups:
                data_to.node_groups = [nodegroup_name]

def append_ies_node_group():
    """Append the IES Light node group from the nodegroup blend file."""
    nodegroup_name = "IES Light"
    blender_version = bpy.app.version
    if blender_version[0] >= 4:
        nodegroup_blend_path = os.path.join(
            os.path.dirname(__file__), "..", "nodegroup-4.blend"
        )
    else:
        nodegroup_blend_path = os.path.join(
            os.path.dirname(__file__), "..", "nodegroup.blend"
        )

    if nodegroup_name not in bpy.data.node_groups:
        with bpy.data.libraries.load(nodegroup_blend_path, link=False) as (
            data_from,
            data_to,
        ):
            if nodegroup_name in data_from.node_groups:
                data_to.node_groups = [nodegroup_name]

def append_scrim_node_group():
    """Append the Scrim Light node group from the nodegroup blend file."""
    blender_version = bpy.app.version
    
    # Get user preference for scrim version
    addon_prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
    scrim_pref = getattr(addon_prefs, 'scrim_version', 'v2')
    
    # Determine node group name based on preference and Blender version
    if bpy.app.version >= (4, 3, 0):  # Blender 4.3+
        # Use preference directly
        if scrim_pref == 'v1':
            nodegroup_name = "Scrim Light v1"
        elif scrim_pref == 'v2':
            nodegroup_name = "Scrim Light v2"
        else:  # v2.1
            nodegroup_name = "Scrim Light v2.1"
        nodegroup_blend_path = os.path.join(
            os.path.dirname(__file__), "..", "nodegroup-4.blend"
        )
    elif bpy.app.version >= (4, 0, 0):  # Blender 4.0-4.2
        nodegroup_name = "Scrim Light v1"
        nodegroup_blend_path = os.path.join(
            os.path.dirname(__file__), "..", "nodegroup-4.blend"
        )
    else:  # Blender 3.x and below
        nodegroup_name = "Scrim Light"
        nodegroup_blend_path = os.path.join(
            os.path.dirname(__file__), "..", "nodegroup.blend"
        )

    if nodegroup_name not in bpy.data.node_groups:
        with bpy.data.libraries.load(nodegroup_blend_path, link=False) as (
            data_from,
            data_to,
        ):
            if nodegroup_name in data_from.node_groups:
                data_to.node_groups = [nodegroup_name]

def apply_initial_color_temp_global(light_data_block):
    """Apply the initial color temperature to a light."""
    if light_data_block.use_nodes:
        addon_prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
        initial_light_temp = addon_prefs.initial_light_temp
        for node in light_data_block.node_tree.nodes:
            if "ColorTemp" in node.inputs:
                node.inputs["ColorTemp"].default_value = initial_light_temp
                break

def is_video_file(file_path):
    """Check if a file is a video file based on its extension."""
    video_extensions = [
        ".mp4",
        ".m4v",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".mkv",
        ".webm",
        ".ogv",
    ]
    return any(file_path.lower().endswith(ext) for ext in video_extensions)

def get_video_frame_rate_from_blender(video_path):
    """Get the frame rate of a video file using Blender's movieclip system."""
    try:
        video = bpy.data.movieclips.load(video_path)
        fps = video.fps
        bpy.data.movieclips.remove(video)  # Clean up after getting fps
        return fps
    except Exception as e:
        logger.error(f"Error getting video FPS: {e}")
        return None

@persistent
def update_light_spread(scene, depsgraph):
    """Update light spread/radius based on Gobo Light Focus value."""
    # Check if playback is active
    if bpy.context.screen and bpy.context.screen.is_animation_playing:
        return

    min_spread_degrees = 0.2
    max_spread_degrees = 10
    min_spread_radians = math.radians(min_spread_degrees)
    max_spread_radians = math.radians(max_spread_degrees)

    min_radius = 0.01
    max_radius = 0.3

    light = bpy.context.active_object

    if light and light.type == "LIGHT" and light.data.use_nodes:
        if light.data.type in ["AREA", "SPOT"]:
            for node in light.data.node_tree.nodes:
                if (isinstance(node, bpy.types.ShaderNodeGroup) 
                    and "Gobo Light" in node.node_tree.name):
                    focus_node = node.inputs.get("Focus", None)
                    if focus_node:
                        focus = int(focus_node.default_value)
                        last_focus = light.get("last_focus", None)
                        
                        # Get current spread/radius
                        if light.data.type == "AREA":
                            current_spread = light.data.spread
                            last_spread = light.get("last_spread", None)
                            
                            # Check if spread was changed externally
                            if last_spread is not None and last_spread != current_spread:
                                # Calculate focus from spread
                                focus_float = 100 * (max_spread_radians - current_spread) / (max_spread_radians - min_spread_radians)
                                focus = int(max(min(focus_float, 100), 0))
                                focus_node.default_value = focus
                                light["last_focus"] = focus
                            # Otherwise update spread from focus
                            elif last_focus is None or last_focus != focus:
                                spread = max_spread_radians - (focus / 100) * (max_spread_radians - min_spread_radians)
                                spread = max(min(spread, max_spread_radians), min_spread_radians)
                                light.data.spread = spread
                                
                            light["last_spread"] = current_spread
                            
                        elif light.data.type == "SPOT":
                            current_radius = light.data.shadow_soft_size
                            last_radius = light.get("last_radius", None)
                            
                            # Check if radius was changed externally
                            if last_radius is not None and last_radius != current_radius:
                                # Calculate focus from radius
                                focus_float = 100 * (max_radius - current_radius) / (max_radius - min_radius)
                                focus = int(max(min(focus_float, 100), 0))
                                focus_node.default_value = focus
                                light["last_focus"] = focus
                            # Otherwise update radius from focus
                            elif last_focus is None or last_focus != focus:
                                radius = max_radius - (focus / 100) * (max_radius - min_radius)
                                radius = max(min(radius, max_radius), min_radius)
                                light.data.shadow_soft_size = radius
                                
                            light["last_radius"] = current_radius
                            
                        break
