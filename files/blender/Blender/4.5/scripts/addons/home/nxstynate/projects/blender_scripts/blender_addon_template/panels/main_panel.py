
import bpy

class MainPanel(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "My Addon"
    bl_idname = "OBJECT_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'My Addon'

    def draw(self, context):
        layout = self.layout
        layout.operator("object.simple_operator")
