
bl_info = {
    "name": "Relink Missing Textures",
    "author": "NXSTYNATE",
    "version": (1, 1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Relink Textures",
    "description": "Recursively finds and relinks missing texture files.",
    "warning": "",
    "wiki_url": "",
    "category": "System",
}

import bpy

from . import properties
from . import operators
from . import panels

def register():
    properties.register()
    operators.register()
    panels.register()

def unregister():
    panels.unregister()
    operators.unregister()
    properties.unregister()

if __name__ == "__main__":
    register()
