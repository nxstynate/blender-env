
import bpy
import os

class CheckTexturesOperator(bpy.types.Operator):
    """Scans the scene for missing texture files and reports the results."""
    bl_idname = "object.check_missing_textures"
    bl_label = "Check for Missing Textures"

    def execute(self, context):
        props = context.scene.relink_assets_props
        props.missing_textures.clear()
        props.total_textures = 0
        props.missing_textures_count = 0

        for image in bpy.data.images:
            if image.source == 'FILE':
                props.total_textures += 1
                if not os.path.exists(bpy.path.abspath(image.filepath)):
                    item = props.missing_textures.add()
                    item.name = os.path.basename(image.filepath)
                    props.missing_textures_count += 1
        
        if props.missing_textures_count == 0:
            props.feedback_message = f"Found {props.total_textures} textures. None are missing."
        else:
            props.feedback_message = f"Found {props.missing_textures_count} missing textures out of {props.total_textures}."

        return {'FINISHED'}

def register():
    bpy.utils.register_class(CheckTexturesOperator)

def unregister():
    bpy.utils.unregister_class(CheckTexturesOperator)
