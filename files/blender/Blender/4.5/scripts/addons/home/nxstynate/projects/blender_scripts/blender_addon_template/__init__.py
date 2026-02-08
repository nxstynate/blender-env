
bl_info = {
    "name": "My Blender Addon",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > My Addon",
    "description": "A boilerplate for creating Blender addons",
    "warning": "",
    "wiki_url": "",
    "category": "Development",
}

import bpy

from .operators.simple_operator import SimpleOperator
from .panels.main_panel import MainPanel

classes = (
    SimpleOperator,
    MainPanel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
