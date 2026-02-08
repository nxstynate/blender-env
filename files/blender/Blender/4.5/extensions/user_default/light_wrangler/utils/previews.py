import bpy
import bpy.utils.previews
import os
import re
import math
from .texture_manager import get_video_frame_rate_from_blender
from .preview_manager import get_enum_items_for_type, get_preview_collection, unregister_preview_collection, clear_cache

def register_previews():
    """Register all preview collections and property enums."""
    from . import logger
    logger.start_section("Preview Collections")
    
    # Initialize the centralized preview collection
    get_preview_collection()
    logger.debug("Created centralized preview collection")
    
    # Register identifier storage properties
    bpy.types.Light.hdri_identifier = bpy.props.StringProperty(
        name="HDRI Identifier",
        description="Stores the identifier of the selected HDRI",
        default=""
    )
    bpy.types.Light.gobo_identifier = bpy.props.StringProperty(
        name="Gobo Identifier", 
        description="Stores the identifier of the selected Gobo",
        default=""
    )
    bpy.types.Light.ies_identifier = bpy.props.StringProperty(
        name="IES Identifier",
        description="Stores the identifier of the selected IES profile",
        default=""
    )
    logger.debug("Registered identifier storage properties on Light")
    
    # Register property enums
    for preview_type in ['gobo', 'hdri', 'ies']:
        try:
            # Create a wrapper function that captures the preview_type
            def make_items_callback(pt):
                def items_callback(self, context):
                    return get_enum_items_for_type(self, context, pt)
                return items_callback
            
            setattr(bpy.types.Light, f'{preview_type}_enum', bpy.props.EnumProperty(
                items=make_items_callback(preview_type),
                name=f"{preview_type.upper()} Texture" if preview_type != 'ies' else "IES Profile",
                description="",
                update=globals()[f'update_{preview_type}_texture']
            ))
            logger.debug(f"Registered {preview_type}_enum property on Light")
        except Exception as e:
            logger.error(f"Failed to register {preview_type}_enum property: {e}")
    
    # Scan for video thumbnails if needed
    try:
        scan_and_generate_thumbnails()
    except Exception as e:
        logger.error(f"Failed to scan for video thumbnails: {e}")
    
    logger.end_section()

def unregister_previews():
    """Unregister and clean up all preview collections."""
    from . import logger
    logger.start_section("Preview Collections")
    
    # Unregister the centralized collection
    unregister_preview_collection()
    logger.debug("Unregistered centralized preview collection")
    
    # Remove identifier storage properties
    for prop in ['hdri_identifier', 'gobo_identifier', 'ies_identifier']:
        if hasattr(bpy.types.Light, prop):
            try:
                delattr(bpy.types.Light, prop)
                logger.debug(f"Unregistered {prop} property from Light")
            except Exception as e:
                logger.error(f"Failed to unregister {prop} property: {e}")
    
    # Remove property enums
    for preview_type in ['gobo', 'hdri', 'ies']:
        if hasattr(bpy.types.Light, f'{preview_type}_enum'):
            try:
                delattr(bpy.types.Light, f'{preview_type}_enum')
                logger.debug(f"Unregistered {preview_type}_enum property from Light")
            except Exception as e:
                logger.error(f"Failed to unregister {preview_type}_enum property: {e}")
    
    logger.end_section()

def scan_and_generate_thumbnails():
    """Scan for video files and generate thumbnails if needed."""
    from .. import ADDON_MODULE_NAME
    addon_prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
    custom_folder_paths = [addon_prefs.gobo_path, addon_prefs.gobo_path_2, addon_prefs.gobo_path_3]
    video_extensions = ('.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm', '.ogv')
    videos_needing_thumbnails = []

    for folder_path in custom_folder_paths:
        if folder_path and os.path.exists(folder_path):
            for filename in os.listdir(folder_path):
                if filename.lower().endswith(video_extensions):
                    video_path = os.path.join(folder_path, filename)
                    thumbnail_path = os.path.join(folder_path, f"{os.path.splitext(filename)[0]}_thumb.png")
                    if not os.path.exists(thumbnail_path):
                        videos_needing_thumbnails.append((video_path, thumbnail_path))
        elif folder_path:
            logger.warning(f"Custom gobo folder path does not exist: {folder_path}")

    if videos_needing_thumbnails:
        for video_path, thumbnail_path in videos_needing_thumbnails:
            generate_thumbnail(video_path, thumbnail_path)

def generate_thumbnail(video_path, output_path):
    """Generate a thumbnail for a video file."""
    try:
        original_scene = bpy.context.scene
        scene = bpy.data.scenes.new(name="Thumbnail Scene")
        bpy.context.window.scene = scene

        # Set square resolution
        thumbnail_size = 200
        scene.render.resolution_x = thumbnail_size
        scene.render.resolution_y = thumbnail_size
        scene.render.filepath = output_path
        scene.render.image_settings.file_format = 'PNG'

        # Set color management
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
        scene.display_settings.display_device = 'sRGB'

        if scene.sequence_editor is None:
            scene.sequence_editor_create()

        seq = scene.sequence_editor.sequences.new_movie(
            name=os.path.basename(video_path),
            filepath=video_path,
            channel=1,
            frame_start=1
        )

        scene.frame_start = 1
        scene.frame_end = seq.frame_final_duration
        middle_frame = seq.frame_final_duration // 2
        scene.frame_current = middle_frame

        # Calculate scaling and positioning
        scale_factor = thumbnail_size / seq.elements[0].orig_height
        scaled_width = seq.elements[0].orig_width * scale_factor

        if scaled_width > thumbnail_size:
            scale_factor = thumbnail_size / seq.elements[0].orig_width
            seq.transform.scale_x = scale_factor
            seq.transform.scale_y = scale_factor
            seq.transform.offset_y = (thumbnail_size - seq.elements[0].orig_height * scale_factor) / 2
        else:
            seq.transform.scale_x = scale_factor
            seq.transform.scale_y = scale_factor
            seq.transform.offset_x = (thumbnail_size - scaled_width) / 2

        # Set color space
        seq.colorspace_settings.name = 'sRGB'
        scene.sequencer_colorspace_settings.name = 'sRGB'

        bpy.ops.render.render(write_still=True)
        
        bpy.data.scenes.remove(scene)
        bpy.context.window.scene = original_scene
        
        logger.info(f"Generated thumbnail for {os.path.basename(video_path)}")
    except Exception as e:
        logger.error(f"Error generating thumbnail for {os.path.basename(video_path)}:")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        import traceback
        traceback.print_exc()

def update_gobo_texture(self, context):
    """Update handler for when a gobo texture is selected."""
    from .texture_manager import apply_gobo_to_light
    light = context.object
    
    # Handle special cases
    if self.gobo_enum == '__empty__':
        return
    
    # Store the identifier for persistence
    self.gobo_identifier = self.gobo_enum
    
    # Pass the full enum value to preserve user/builtin prefix and path
    # The texture manager will handle parsing the identifier
    apply_gobo_to_light(light, self.gobo_enum)

def update_hdri_texture(self, context):
    """Update handler for when an HDRI texture is selected."""
    from .texture_manager import apply_hdri_to_light
    light = context.object
    
    # Handle special cases
    if self.hdri_enum == '__empty__':
        return
    
    # Store the identifier for persistence
    self.hdri_identifier = self.hdri_enum
    
    # Pass the full enum value to preserve user/builtin prefix and path
    # The texture manager will handle parsing the identifier
    apply_hdri_to_light(light, self.hdri_enum)

def update_ies_texture(self, context):
    """Update handler for when an IES profile is selected."""
    from .texture_manager import apply_ies_to_light
    light = context.object
    
    # Handle special cases
    if self.ies_enum == '__empty__':
        return
    
    # Store the identifier for persistence
    self.ies_identifier = self.ies_enum
    
    # Pass the full enum value to preserve user/builtin prefix
    # The texture manager will handle parsing the identifier
    apply_ies_to_light(light, self.ies_enum)

def update_all_gobo_drivers():
    """Update all Gobo drivers in the scene."""
    project_fps = bpy.context.scene.render.fps
    
    # Update lights with Gobo Light node groups
    for light in bpy.data.lights:
        if light.use_nodes:
            for node in light.node_tree.nodes:
                if (node.type == "GROUP" and 
                    node.node_tree and 
                    "Gobo Light" in node.node_tree.name):
                    update_video_drivers_in_node_group(node.node_tree, project_fps)
    
    # Update materials with Gobo Stencil node groups
    for mat in bpy.data.materials:
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if (node.type == "GROUP" and 
                    node.node_tree and 
                    "Gobo Stencil" in node.node_tree.name):
                    update_video_drivers_in_node_group(node.node_tree, project_fps)

def update_video_drivers_in_node_group(node_tree, project_fps):
    """Helper function to update video drivers in a node group."""
    for tex_node in node_tree.nodes:
        if (tex_node.type == "TEX_IMAGE" and 
            tex_node.image and 
            hasattr(tex_node.image, 'filepath') and
            is_video_file(tex_node.image.filepath)):
            
            try:
                video_fps = get_video_frame_rate_from_blender(tex_node.image.filepath)
                if video_fps:
                    speed_factor = video_fps / project_fps
                    
                    tex_node.image_user.driver_remove("frame_offset")
                    driver = tex_node.image_user.driver_add("frame_offset").driver
                    driver.type = 'SCRIPTED'
                    driver.expression = f"frame * {speed_factor} % {tex_node.image.frame_duration}"
            except Exception as e:
                logger.error(f"Error updating driver in {node_tree.name}: {e}")

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

# Legacy compatibility functions - these can be removed in future versions
def load_gobo_previews():
    """Legacy function - previews are now loaded on demand."""
    clear_cache('gobo')

def load_hdri_previews():
    """Legacy function - previews are now loaded on demand."""
    clear_cache('hdri')

def load_ies_previews():
    """Legacy function - previews are now loaded on demand."""
    clear_cache('ies')