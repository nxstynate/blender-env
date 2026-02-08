# System Colors - iOS/macOS style
SYSTEM_GRAY = '#B0B0B0'  # System Gray
SYSTEM_GRAY_2 = '#AEAEB2'  # System Gray 2
SYSTEM_GRAY_3 = '#C7C7CC'  # System Gray 3

# UI State Colors
STATE_INACTIVE = '#C4A484'  # Used for paused/inactive states
STATE_SECONDARY = '#AEAEB2'  # Used for secondary/disabled states
STATE_TERTIARY = '#C7C7CC'  # Used for tertiary/background states

# Mapping current usage
PAUSED = STATE_INACTIVE  # Current paused state color
ACTIVE = None  # Will be set from original theme color

from mathutils import Vector

def make_color_paused(color):
    """Convert a color to its paused state by desaturating and lightening it.
    
    Args:
        color: Original color as (R, G, B) tuple with values from 0.0 to 1.0
        
    Returns:
        tuple: Modified (R, G, B) tuple with values from 0.0 to 1.0
    """
    # Convert to Vector for easier math operations
    color_vec = Vector(color)
    
    # Calculate luminance (perceived brightness)
    luminance = color_vec.x * 0.299 + color_vec.y * 0.587 + color_vec.z * 0.114
    
    # Create a desaturated version by mixing with gray
    desaturated = Vector((luminance, luminance, luminance))
    mix_factor = 0.5  # 70% desaturated
    result = color_vec.lerp(desaturated, mix_factor)
    
    # Lighten the result
    lighten_amount = 0.2
    result = result + Vector((lighten_amount, lighten_amount, lighten_amount))
    
    # Clamp values between 0 and 1
    return (
        min(1.0, max(0.0, result.x)),
        min(1.0, max(0.0, result.y)),
        min(1.0, max(0.0, result.z))
    )

def make_color_precise(color):
    """Convert a color to its precise mode state by shifting toward cyan/teal.
    
    Args:
        color: Original color as (R, G, B) tuple with values from 0.0 to 1.0
        
    Returns:
        tuple: Modified (R, G, B) tuple with values from 0.0 to 1.0
    """
    # Convert to Vector for easier math operations
    color_vec = Vector(color)
    
    # Create a cyan/teal target color
    cyan_target = Vector((0.2, 0.8, 0.9))
    
    # Mix original color with cyan (40% cyan for distinctive look)
    mix_factor = 0.4
    result = color_vec.lerp(cyan_target, mix_factor)
    
    # Clamp values between 0 and 1
    return (
        min(1.0, max(0.0, result.x)),
        min(1.0, max(0.0, result.y)),
        min(1.0, max(0.0, result.z))
    )

def get_color(color_id, original_theme_color=None):
    """Get color by semantic ID. Returns tuple of RGB values (0-1).
    
    Args:
        color_id (str): Semantic ID of the color (e.g., 'PAUSED', 'PRECISE', 'STATE_INACTIVE')
        original_theme_color (tuple, optional): Original theme color to modify for paused/precise state
        
    Returns:
        tuple: (R, G, B) tuple with values from 0.0 to 1.0
    """
    # Handle cases where original_theme_color is needed but not provided
    if original_theme_color is None and color_id in ('PAUSED', 'PRECISE'):
        # Use a default orange color as fallback
        original_theme_color = (1.0, 0.5, 0.0)
    
    if color_id == 'PAUSED' and original_theme_color is not None:
        return make_color_paused(original_theme_color)
    elif color_id == 'PRECISE' and original_theme_color is not None:
        return make_color_precise(original_theme_color)
        
    from .utils import hex_to_rgb
    
    color_map = {
        'STATE_INACTIVE': STATE_INACTIVE,
        'STATE_SECONDARY': STATE_SECONDARY,
        'STATE_TERTIARY': STATE_TERTIARY,
    }
    
    hex_color = color_map.get(color_id)
    if hex_color:
        return hex_to_rgb(hex_color)
    
    # Never return None - return a default color instead
    return (1.0, 0.5, 0.0)  # Default orange color 