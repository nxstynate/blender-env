
import bpy

class SimpleOperator(bpy.types.Operator):
    """A simple operator that prints a message to the console"""
    bl_idname = "object.simple_operator"
    bl_label = "Simple Operator"

    def execute(self, context):
        print("Hello, Blender!")
        return {'FINISHED'}
