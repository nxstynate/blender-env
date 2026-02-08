import bpy
from bpy.props import StringProperty, BoolProperty, IntProperty, FloatProperty, PointerProperty

class RelinkTexturesProperties(bpy.types.PropertyGroup):
    search_path: StringProperty(
        name="Search Path",
        subtype='DIR_PATH',
        default="",
        description="Directory to search for missing textures"
    )
    feedback_message: StringProperty(
        name="Feedback",
        default="",
        description="Live feedback message"
    )
    progress_value: FloatProperty(
        name="Progress",
        default=0.0,
        min=0.0,
        max=100.0,
        description="Progress of the relinking process"
    )
    missing_textures_count: IntProperty(
        name="Missing Textures",
        default=0,
        description="Number of missing textures"
    )
    missing_textures_list: StringProperty(
        name="Missing Textures List",
        default="",
        description="List of missing textures (for display)"
    )

def register_properties():
    bpy.utils.register_class(RelinkTexturesProperties)
    bpy.types.Scene.relink_textures_props = PointerProperty(type=RelinkTexturesProperties)

def unregister_properties():
    bpy.utils.unregister_class(RelinkTexturesProperties)
    del bpy.types.Scene.relink_textures_props
