import bpy
from . import key_names
from .blender_compat import supports_light_linking

# Common shortcuts that apply to all modes and light types
def get_common_shortcuts(shift_pressed=False, light_type='AREA'):
    """Get common shortcuts, with dynamic shift-based shortcuts."""
    adjustments = [
        ("🖱️", "Power"),
    ]
    
    # Add size-related shortcut based on light type
    if light_type == 'AREA':
        adjustments.append((key_names.format_key_combination("Shift+🖱️"), "Size"))
        # Add shift-dependent shortcuts for AREA lights only
        if shift_pressed:
            adjustments.extend([
                (key_names.format_key_combination("Shift+Alt+🖱️"), "Size X"),
                (key_names.format_key_combination("Shift+Ctrl+🖱️"), "Size Y"),
            ])
    elif light_type == 'SPOT':
        adjustments.append((key_names.format_key_combination("Shift+🖱️"), "Spot Size"))
    elif light_type == 'SUN':
        adjustments.append((key_names.format_key_combination("Shift+🖱️"), "Angle"))
        # Return early for SUN lights as they don't have other adjustments
        return {
            "Adjustments": adjustments
        }
    elif light_type == 'POINT':
        adjustments.append((key_names.format_key_combination("Shift+🖱️"), "Radius"))
    
    # Add remaining shortcuts for non-SUN lights
    if light_type != 'SUN':
        adjustments.extend([
            (key_names.format_key_combination("Alt+🖱️"), "Distance"),
            (key_names.format_key_combination("Z+🖱️"), "Rotation"),
        ])
        
        # Add spread only for AREA and SPOT lights
        if light_type in {'AREA', 'SPOT'}:
            adjustments.append((key_names.format_key_combination("Ctrl+🖱️"), "Spread"))
    
    return {
        "Adjustments": adjustments
    }

# Mode-specific adjustments
def get_orbit_adjustments(shift_pressed=False, light_type='AREA'):
    """Get orbit mode adjustments, with dynamic shift-based shortcuts."""
    adjustments = [
        ("🖱️", "Power"),
    ]
    
    # Add size-related shortcut based on light type
    if light_type == 'AREA':
        adjustments.append((key_names.format_key_combination("Shift+🖱️"), "Size"))
        # Add shift-dependent shortcuts for AREA lights only
        if shift_pressed:
            adjustments.extend([
                (key_names.format_key_combination("Shift+Alt+🖱️"), "Size X"),
                (key_names.format_key_combination("Shift+Ctrl+🖱️"), "Size Y"),
            ])
    elif light_type == 'SPOT':
        adjustments.append((key_names.format_key_combination("Shift+🖱️"), "Spot Size"))
    elif light_type == 'SUN':
        adjustments.append((key_names.format_key_combination("Shift+🖱️"), "Angle"))
        # For SUN lights, only add precise movement
        adjustments.append((key_names.format_key_combination("Shift"), "Precise Movement"))
        return {
            "Adjustments": adjustments
        }
    elif light_type == 'POINT':
        adjustments.append((key_names.format_key_combination("Shift+🖱️"), "Radius"))
    
    # Add remaining shortcuts for non-SUN lights
    if light_type != 'SUN':
        adjustments.extend([
            (key_names.format_key_combination("Alt+🖱️"), "Distance"),
            (key_names.format_key_combination("Z+🖱️"), "Rotation"),
        ])
        
        # Add spread only for AREA and SPOT lights
        if light_type in {'AREA', 'SPOT'}:
            adjustments.append((key_names.format_key_combination("Ctrl+🖱️"), "Spread"))
            
        adjustments.extend([
            (key_names.format_key_combination("Shift"), "Precise Movement"),
            (key_names.format_key_combination("Ctrl"), "Axis Snapping")
        ])
    
    return {
        "Adjustments": adjustments
    }

# Mode switch shortcuts based on current mode
def get_mode_switch_shortcuts(mode, is_paused):
    pause_action = "Unpause" if is_paused else "Pause"
    
    # Helper function to format mode text with indicator
    def format_mode_text(mode_text, is_current):
        return f"→ {mode_text}" if is_current else f"  {mode_text}"
    
    mode_switch = {
        'REFLECT': {
            "Mode Switch": [
                ("1", format_mode_text(pause_action, True)),
                ("2", format_mode_text("Orbit Mode", False)),
                ("3", format_mode_text("Direct Mode", False)),
            ]
        },
        'ORBIT': {
            "Mode Switch": [
                ("1", format_mode_text("Reflect Mode", False)),
                ("2", format_mode_text(pause_action, True)),
                ("3", format_mode_text("Direct Mode", False)),
            ]
        },
        'DIRECT': {
            "Mode Switch": [
                ("1", format_mode_text("Reflect Mode", False)),
                ("2", format_mode_text("Orbit Mode", False)),
                ("3", format_mode_text(pause_action, True)),
            ]
        }
    }
    return mode_switch.get(mode, {})

# Combined miscellaneous shortcuts
MISCELLANEOUS_SHORTCUTS = {
    "Miscellaneous": [
        ("L", "Link Lighting"),
        (key_names.format_key_combination("Shift+L"), "Shadow Linking"),
        ("I", "Isolate Light"),
        ("H", "Hide Light"),
        ("F", "False Color"),
    ]
}

def get_help_sections(context, mode, light_type, is_paused=False, shift_pressed=False):
    """Get relevant help sections based on context."""
    sections = {}
    
    # Add mode-specific adjustments or common adjustments
    if mode == 'ORBIT':
        sections.update(get_orbit_adjustments(shift_pressed, light_type))
    else:
        sections["Adjustments"] = get_common_shortcuts(shift_pressed, light_type)["Adjustments"]
    
    # Add mode-specific mode switch shortcuts
    mode_switch = get_mode_switch_shortcuts(mode, is_paused)
    if mode_switch:
        sections.update(mode_switch)
    
    # Add miscellaneous shortcuts if compatible render engine
    if supports_light_linking(context.scene.render.engine):
        sections.update(MISCELLANEOUS_SHORTCUTS)
    
    return sections

def format_shortcut(key, description):
    """Format a shortcut and its description."""
    return f"{key}|{description}"  # Use separator instead of fixed width padding

def format_section(title, shortcuts):
    """Format a section of shortcuts."""
    lines = [f"─── {title} ───"]
    for key, desc in shortcuts:
        lines.append(format_shortcut(key, desc))
    return lines

def get_formatted_help(context, mode, light_type, is_paused=False, shift_pressed=False):
    """Get fully formatted help text."""
    # Start with the help toggle as a top line
    formatted_lines = [format_shortcut("Q", "Hide Controls"), ""]
    
    # Add all other sections
    sections = get_help_sections(context, mode, light_type, is_paused, shift_pressed)
    for title, shortcuts in sections.items():
        if shortcuts:  # Only add section if it has shortcuts
            formatted_lines.extend(format_section(title, shortcuts))
            formatted_lines.append("")  # Add spacing between sections
    
    return formatted_lines

def format_status_bar_text(context, mode, light_type, shift_pressed=False, alt_pressed=False, ctrl_pressed=False, z_pressed=False, is_paused=False, precise_mode=False):
    """Format text for the status bar showing current mode and key shortcuts."""
    # Get the same help text as the HUD menu, using the actual pause state
    help_lines = get_formatted_help(context, mode, light_type, is_paused, shift_pressed)
    
    # Only use other shortcuts, not mode shortcuts
    other_shortcuts = []
    
    # Check for SIZE_X and SIZE_Y conditions, similar to how the HUD determines when to show them
    if light_type == 'AREA':
        if shift_pressed and alt_pressed:
            # Add SIZE_X hint to the beginning of other_shortcuts
            other_shortcuts.append("Size X")
        elif shift_pressed and ctrl_pressed:
            # Add SIZE_Y hint to the beginning of other_shortcuts
            other_shortcuts.append("Size Y")
    
    for line in help_lines:
        if line and not line.startswith("───"):
            if "|" in line:
                key, desc = line.split("|", 1)
                key = key.strip()
                desc = desc.strip()
                
                # Skip the Q shortcut
                if key == "Q":
                    continue
                    
                # Skip mode shortcuts to save space
                if desc.startswith("→") or "Mode" in desc or desc in {"Pause", "Unpause"}:
                    continue
                else:
                    other_shortcuts.append(f"{key}: {desc}")
            else:
                other_shortcuts.append(line)
    
    # Add precise mode toggle shortcut if in REFLECT or DIRECT mode
    if mode in ('REFLECT', 'DIRECT'):
        other_shortcuts.append("Space: Precise")
    
    # Join with bullet point separator
    return "  |  ".join(other_shortcuts) 