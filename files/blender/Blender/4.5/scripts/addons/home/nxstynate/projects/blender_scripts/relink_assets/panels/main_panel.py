
import bpy

class MainPanel(bpy.types.Panel):
    """Creates a Panel in the 3D View Sidebar."""
    bl_label = "Relink Textures"
    bl_idname = "OBJECT_PT_relink_textures"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Relink Textures'

    def draw(self, context):
        layout = self.layout
        props = context.scene.relink_assets_props

        # Check for Missing Textures
        layout.operator("object.check_missing_textures")

        # Status and Feedback
        layout.label(text="Status:")
        box = layout.box()
        box.label(text=props.feedback_message)

        if props.missing_textures_count > 0:
            box.label(text=f"Total Textures: {props.total_textures}")
            box.label(text=f"Missing: {props.missing_textures_count}")

            # Missing Textures List
            if props.missing_textures:
                layout.label(text="Missing Files:")
                scroll_box = layout.box()
                for item in props.missing_textures:
                    scroll_box.label(text=item.name)

            # Relink Section
            layout.separator()
            layout.label(text="Relink Missing Textures:")
            col = layout.column(align=True)
            col.prop(props, "search_path")
            col.operator("object.relink_textures")
            
            # Progress Bar
            layout.progress(factor=props.progress / 100.0)

def register():
    bpy.utils.register_class(MainPanel)

def unregister():
    bpy.utils.unregister_class(MainPanel)
