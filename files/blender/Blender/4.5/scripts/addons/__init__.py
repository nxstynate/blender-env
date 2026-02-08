# __init__.py - Main add-on registration file

bl_info = {
    "name": "Collection Batch Linker",
    "author": "Assistant",
    "version": (1, 0, 0),
    "blender": (4, 5, 0),
    "location": "View3D > N-Panel > Collection Batch Linker",
    "description": "Batch-inject linked collections from master source to target blend files",
    "category": "Import-Export",
    "support": "COMMUNITY",
}

import bpy
import sys
import os
from pathlib import Path

# Add the add-on directory to Python path for imports
addon_dir = Path(__file__).parent
if str(addon_dir) not in sys.path:
    sys.path.append(str(addon_dir))

from . import ui
from . import operators
from . import core
from . import preferences

modules = [
    preferences,
    core,
    operators,
    ui,
]

def register():
    """Register all add-on classes and properties"""
    for module in modules:
        if hasattr(module, 'register'):
            module.register()

def unregister():
    """Unregister all add-on classes and properties"""
    for module in reversed(modules):
        if hasattr(module, 'unregister'):
            module.unregister()

if __name__ == "__main__":
    register()
