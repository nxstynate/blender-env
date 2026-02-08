"""Centralized preview management system with caching and performance optimizations."""

import bpy
import bpy.utils.previews
import os
import re
import warnings
from typing import List, Tuple, Optional
from .. import ADDON_MODULE_NAME
from . import logger

# Global preview collection
preview_collection = None


# Supported formats
GOBO_FORMATS = ('.jpg', '.jpeg', '.png', '.webp', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm', '.ogv')
HDRI_FORMATS = ('.jpg', '.jpeg', '.png', '.hdr', '.exr', '.tif', '.tiff', '.webp')
IES_FORMATS = ('.png', '.jpg', '.jpeg')  # For preview images, not actual IES files


def get_preview_collection():
    """Get the global preview collection, creating it if necessary."""
    global preview_collection
    if preview_collection is None:
        preview_collection = bpy.utils.previews.new()
        # Add custom attributes for caching
        # We keep dict approach for Light Wrangler's multiple directories
        preview_collection.library_prev_dir = {}  # Dict to store cached directories by type
        preview_collection.library_prevs = {}     # Dict to store cached enum items by type
    return preview_collection

def unregister_preview_collection():
    """Unregister and clean up the preview collection."""
    global preview_collection
    if preview_collection is not None:
        bpy.utils.previews.remove(preview_collection)
        preview_collection = None


def create_enum_item(identifier: str, display_name: str, filepath: str, icon_id: int, index: int) -> Tuple:
    """Create a properly formatted enum item tuple.
    
    Using full filepath as identifier.
    (identifier, display_name, filepath, icon_id, index)
    """
    return (identifier, display_name, filepath or "", icon_id, index)


def get_placeholder_path(placeholder_type: str) -> str:
    """Get path to placeholder image."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    placeholders = {
        'empty': os.path.join(base_dir, 'icons', 'empty.png'),
        'needs_thumb': os.path.join(base_dir, 'icons', 'needs_thumb.png'),
    }
    
    # Get the requested placeholder path
    placeholder_path = placeholders.get(placeholder_type, placeholders['empty'])
    
    # If the specific placeholder doesn't exist, fall back to needs_thumb.png
    if not os.path.exists(placeholder_path):
        fallback_path = placeholders['needs_thumb']
        if os.path.exists(fallback_path):
            return fallback_path
        else:
            # Last resort - return path anyway (will show broken icon rather than crash)
            logger.warning(f"Placeholder image not found: {placeholder_path}")
    
    return placeholder_path

def scan_directory_for_files(directory: str, formats: Tuple[str, ...]) -> List[str]:
    """
    Scan directory for files matching formats.
    Returns list of filepaths sorted naturally.
    """
    if not directory or not os.path.exists(directory):
        return []
    
    files = []
    for filename in os.listdir(directory):
        if filename.lower().endswith(formats):
            filepath = os.path.join(directory, filename)
            files.append(filepath)
    
    # Sort alphabetically by filename (case-insensitive)
    files.sort(key=lambda x: os.path.basename(x).lower())
    
    return files

def load_preview_items(preview_type: str, directory: str, 
                      formats: Tuple[str, ...]) -> List[Tuple]:
    """
    Load preview items from directory with caching support.
    Returns list of enum items.
    """
    logger.debug(f"load_preview_items - type: {preview_type}, dir: {directory}")
    logger.debug(f"Formats to scan: {formats}")
    
    pcoll = get_preview_collection()
    
    # Generate cache key
    cache_key = f"{preview_type}:{directory}"
    
    # Check cache
    if (cache_key in pcoll.library_prev_dir and 
        pcoll.library_prev_dir[cache_key] == directory and
        cache_key in pcoll.library_prevs):
        # Return cached items silently
        cached = pcoll.library_prevs[cache_key]
        logger.debug(f"Returning {len(cached)} cached items for {cache_key}")
        return cached
    
    enum_items = []
    
    # Scan directory
    files = scan_directory_for_files(directory, formats)
    
    # Debug output for scanning
    logger.debug(f"Scanned {len(files)} files in {directory}")
    
    # Load previews
    for i, filepath in enumerate(files):
        name = os.path.basename(filepath)
        
        # Use full filepath as identifier
        identifier = filepath
        
        # Check if already loaded
        if identifier not in pcoll:
            try:
                # Check for thumbnail first
                thumbnail_path = get_thumbnail_path(filepath)
                if os.path.exists(thumbnail_path):
                    # Suppress TIFF metadata warnings
                    with warnings.catch_warnings():
                        warnings.filterwarnings('ignore', message='.*Unknown field with tag.*')
                        pcoll.load(identifier, thumbnail_path, 'IMAGE')
                else:
                    # Try loading original
                    with warnings.catch_warnings():
                        warnings.filterwarnings('ignore', message='.*Unknown field with tag.*')
                        pcoll.load(identifier, filepath, 'IMAGE')
            except Exception as e:
                # Load placeholder on error
                placeholder_path = get_placeholder_path('empty')
                pcoll.load(identifier, placeholder_path, 'IMAGE')
                logger.error(f"Error loading preview for {name}: {e}")
        
        # Add to enum items with formatted display name
        display_name = os.path.splitext(name)[0].replace('.', ' ').replace('_', ' ').lower().capitalize()
        # Don't use index here - it will be assigned later when combining all items
        enum_items.append(create_enum_item(identifier, display_name, filepath, pcoll[identifier].icon_id, 0))
    
    # Handle empty directory
    if not enum_items:
        empty_icon_name = 'empty'
        if empty_icon_name not in pcoll:
            empty_path = get_placeholder_path('empty')
            pcoll.load(empty_icon_name, empty_path, 'IMAGE')
        enum_items.append(create_enum_item('__empty__', "Empty", "No files found", pcoll[empty_icon_name].icon_id, 0))
    
    # Update cache
    pcoll.library_prev_dir[cache_key] = directory
    pcoll.library_prevs[cache_key] = enum_items
    
    return enum_items

def get_thumbnail_path(source_file: str) -> str:
    """Get thumbnail path for a source file."""
    path, filename = os.path.split(source_file)
    name_no_ext = os.path.splitext(filename)[0]
    
    # Check for video thumbnail first (generated by Light Wrangler)
    video_thumb = os.path.join(path, f"{name_no_ext}_thumb.png")
    if os.path.exists(video_thumb):
        return video_thumb
    
    # Check for _thumbnails folder
    thumb_dir = os.path.join(path, "_thumbnails")
    if os.path.exists(thumb_dir):
        thumb_path = os.path.join(thumb_dir, f"{name_no_ext}.png")
        if os.path.exists(thumb_path):
            return thumb_path
    
    # Check for same-name PNG
    png_path = os.path.join(path, f"{name_no_ext}.png")
    if os.path.exists(png_path) and png_path != source_file:
        return png_path
    
    return ""

def clear_cache(preview_type: Optional[str] = None):
    """Clear preview cache for specific type or all types."""
    pcoll = get_preview_collection()
    
    if preview_type:
        # Clear specific type
        keys_to_remove = [k for k in pcoll.library_prev_dir.keys() 
                         if k.startswith(f"{preview_type}:")]
        if keys_to_remove:
            logger.debug(f"Cache cleared for {preview_type}")
        for key in keys_to_remove:
            pcoll.library_prev_dir.pop(key, None)
            pcoll.library_prevs.pop(key, None)
    else:
        # Clear all
        if pcoll.library_prev_dir:
            logger.debug(f"All preview cache cleared")
        pcoll.library_prev_dir.clear()
        pcoll.library_prevs.clear()

def update_light_categories(light_data, preview_type: str) -> None:
    """
    Placeholder for backwards compatibility.
    No longer needed with simplified folder browser approach.
    """
    pass
    
    # Clear cache for this type to force preview refresh
    clear_cache(preview_type)

def get_enum_items_for_type(self, context, preview_type: str):
    """Get enum items for specific preview type with proper context handling."""
    logger.debug(f"get_enum_items_for_type called with preview_type: {preview_type}")
    
    if context is None:
        logger.debug("Context is None, returning empty list")
        return []
    
    # Check if this is a light data block (has type attribute with POINT, SPOT, AREA, or SUN)
    if hasattr(self, 'type') and self.type in ['POINT', 'SPOT', 'AREA', 'SUN']:
        logger.debug(f"Light data block detected, type: {self.type}")
        # Set the appropriate formats
        if preview_type == 'gobo':
            formats = GOBO_FORMATS
        elif preview_type == 'hdri':
            formats = HDRI_FORMATS
        elif preview_type == 'ies':
            formats = IES_FORMATS
        else:
            logger.debug(f"Unknown preview_type: {preview_type}")
            return []
    else:
        logger.debug("Not a light data block or missing type attribute")
        return []
    
    # Build paths list - always include built-in textures
    base_paths = []
    
    # Add built-in preview path
    if preview_type == 'gobo':
        builtin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gobo_previews")
        base_paths.append(('builtin', builtin_path))
        logger.debug(f"Added builtin gobo path: {builtin_path}, exists: {os.path.exists(builtin_path)}")
    elif preview_type == 'hdri':
        builtin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hdri_previews")
        base_paths.append(('builtin', builtin_path))
        logger.debug(f"Added builtin hdri path: {builtin_path}, exists: {os.path.exists(builtin_path)}")
    elif preview_type == 'ies':
        builtin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ies_previews")
        base_paths.append(('builtin', builtin_path))
        logger.debug(f"Added builtin ies path: {builtin_path}, exists: {os.path.exists(builtin_path)}")
    
    # Get addon preferences and add user folders
    try:
        import bpy
        from .. import ADDON_MODULE_NAME
        addon_prefs = context.preferences.addons.get(ADDON_MODULE_NAME)
        if addon_prefs:
            addon_prefs = addon_prefs.preferences
            
            # Add user folders based on preview type
            if preview_type == 'gobo':
                # Add all three gobo folders if they exist
                for folder_attr in ['gobo_path', 'gobo_path_2', 'gobo_path_3']:
                    folder_path = getattr(addon_prefs, folder_attr, None)
                    if folder_path and os.path.exists(folder_path):
                        base_paths.append(('user', folder_path))
                        logger.debug(f"Added user gobo path from {folder_attr}: {folder_path}")
            elif preview_type == 'hdri':
                # Add all three HDRI folders if they exist
                for folder_attr in ['hdri_path', 'hdri_path_2', 'hdri_path_3']:
                    folder_path = getattr(addon_prefs, folder_attr, None)
                    if folder_path and os.path.exists(folder_path):
                        base_paths.append(('user', folder_path))
                        logger.debug(f"Added user HDRI path from {folder_attr}: {folder_path}")
            elif preview_type == 'ies':
                # Add IES profiles folder if it exists
                # Note: For IES, we use ies_previews_path for previews if available,
                # otherwise fall back to ies_profiles_path
                ies_preview_path = getattr(addon_prefs, 'ies_previews_path', None)
                ies_profiles_path = getattr(addon_prefs, 'ies_profiles_path', None)
                
                if ies_preview_path and os.path.exists(ies_preview_path):
                    base_paths.append(('user', ies_preview_path))
                    logger.debug(f"Added user IES preview path: {ies_preview_path}")
                elif ies_profiles_path and os.path.exists(ies_profiles_path):
                    base_paths.append(('user', ies_profiles_path))
                    logger.debug(f"Added user IES profiles path: {ies_profiles_path}")
    except Exception as e:
        logger.debug(f"Could not get addon preferences: {e}")
    
    # Use the paths directly without category filtering
    paths = []
    for path_type, base_path in base_paths:
        if base_path and os.path.exists(base_path):
            paths.append((path_type, base_path))
            logger.debug(f"Added {path_type} path: {base_path}")
    
    logger.debug(f"Total paths to scan: {len(paths)}")
    
    all_items = []
    for path_type, path in paths:
        if path and os.path.exists(path):
            logger.debug(f"Loading items from {path_type} path: {path}")
            items = load_preview_items(
                preview_type, 
                path, 
                formats
            )
            logger.debug(f"Loaded {len(items)} items from {path}")
            all_items.extend(items)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_items = []
    for item in all_items:
        if item[0] not in seen:
            seen.add(item[0])
            unique_items.append(item)
    
    logger.debug(f"Total items after deduplication: {len(unique_items)}")
    
    # Simple alphabetical sort by filepath
    # Files are already sorted within load_preview_items by scan_directory_for_files
    final_items = unique_items
    
    # Re-index all items with sequential indices to avoid collisions
    final_items = [(item[0], item[1], item[2], item[3], i) for i, item in enumerate(final_items)]
    
    logger.debug(f"Final items count: {len(final_items)}")
    if final_items:
        logger.debug(f"First item: {final_items[0][1]} (id: {final_items[0][0][:50]}...)")
    
    if not final_items:
        logger.debug("No items found, returning empty placeholder")
        # Get empty icon for consistent return value
        pcoll = get_preview_collection()
        empty_icon_name = 'empty'
        if empty_icon_name not in pcoll:
            empty_path = get_placeholder_path('empty')
            pcoll.load(empty_icon_name, empty_path, 'IMAGE')
        return [create_enum_item('__empty__', "Empty", "No files found", pcoll[empty_icon_name].icon_id, 0)]
    
    # Note: Blender automatically maintains selection when identifiers match
    # We don't need to manually set the enum value here as that would cause recursion
    # The stored identifier in {preview_type}_identifier is used by Blender to match selections
    
    return final_items