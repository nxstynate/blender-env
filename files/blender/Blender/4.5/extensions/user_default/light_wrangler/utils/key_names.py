import platform

def get_os_specific_key_names():
    """Get OS-specific key names for modifiers and special keys."""
    os_name = platform.system()
    
    if os_name == 'Darwin':  # macOS
        return {
            'Shift': '⇧',
            'Alt': '⌥',
            'Ctrl': '⌃',
            'Tab': '⇥',
            'Left Click': 'Left Click',
            'Right Click': 'Right Click',
        }
    else:  # Windows or Linux
        return {
            'Shift': 'Shift',
            'Alt': 'Alt',
            'Ctrl': 'Ctrl',
            'Tab': 'Tab',
            'Left Click': 'Left Click',
            'Right Click': 'Right Click',
        }

def format_key_combination(key_combo):
    """Format a key combination using OS-specific symbols."""
    os_specific_keys = get_os_specific_key_names()
    
    # Split the key combination into parts
    parts = key_combo.split('+')
    formatted_parts = []
    
    for part in parts:
        part = part.strip()
        # Replace known keys with their OS-specific versions
        formatted_part = os_specific_keys.get(part, part)
        formatted_parts.append(formatted_part)
    
    # Join with + for Windows/Linux, space for macOS
    if platform.system() == 'Darwin':
        return ' '.join(formatted_parts)
    else:
        return '+'.join(formatted_parts) 