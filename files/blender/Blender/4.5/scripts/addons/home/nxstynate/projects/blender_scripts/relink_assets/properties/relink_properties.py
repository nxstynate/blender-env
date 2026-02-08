import bpy

class MissingTextureItem(bpy.types.PropertyGroup):
    """Represents a single missing texture file."""
    name: bpy.props.StringProperty(name="File Name")

class RelinkProperties(bpy.types.PropertyGroup):
    search_path: bpy.props.StringProperty(
        name="Search Path",
        description="Select the base folder to search for missing textures",
        subtype='DIR_PATH'
    )
    
    feedback_message: bpy.props.StringProperty(
        name="Feedback",
        description="Live feedback from the relinking process",
        default="Ready"
    )
    
    progress: bpy.props.IntProperty(
        name="Progress",
        description="Progress of the relinking process",
        default=0,
        min=0,
        max=100,
        subtype='PERCENTAGE'
    )

    total_textures: bpy.props.IntProperty(
        name="Total Textures",
        description="Total number of image textures in the scene",
        default=0
    )

    missing_textures_count: bpy.props.IntProperty(
        name="Missing Textures",
        description="Number of missing textures",
        default=0
    )

    missing_textures: bpy.props.CollectionProperty(
        name="Missing Textures List",
        type=MissingTextureItem
    )

    active_missing_texture_index: bpy.props.IntProperty()


def register():
    bpy.utils.register_class(MissingTextureItem)
    bpy.utils.register_class(RelinkProperties)
    bpy.types.Scene.relink_assets_props = bpy.props.PointerProperty(type=RelinkProperties)

def unregister():
    del bpy.types.Scene.relink_assets_props
    bpy.utils.unregister_class(RelinkProperties)
    bpy.utils.unregister_class(MissingTextureItem)