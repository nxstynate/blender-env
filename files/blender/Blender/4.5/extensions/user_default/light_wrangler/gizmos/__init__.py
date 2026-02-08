"""
Light Wrangler gizmos package.
Contains viewport gizmo implementations for light manipulation.
"""

from . import light_position_gizmos

def register():
    light_position_gizmos.register()

def unregister():
    light_position_gizmos.unregister() 