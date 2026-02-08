bl_info = {
    "name": "Relink Textures Addon",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Relink Textures",
    "description": "Automatically finds and relinks missing textures in your Blender project.",
    "warning": "",
    "wiki_url": "",
    "category": "Development",
}

import bpy

from .operators.relink_operators import CheckMissingTexturesOperator, RelinkMissingTexturesOperator
from .panels.main_panel import RelinkTexturesPanel
from .properties import register_properties, unregister_properties

classes = (
    CheckMissingTexturesOperator,
    RelinkMissingTexturesOperator,
    RelinkTexturesPanel,
)

def register():
    register_properties()
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_properties()

if __name__ == "__main__":
    register()