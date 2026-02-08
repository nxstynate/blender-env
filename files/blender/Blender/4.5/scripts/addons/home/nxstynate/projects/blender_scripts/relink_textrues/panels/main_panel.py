import bpy

class RelinkTexturesPanel(bpy.types.Panel):
    bl_label = "Relink Textures"
    bl_idname = "VIEW3D_PT_relink_textures"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Relink Textures'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.relink_textures_props

        # Search Path
        layout.prop(props, "search_path")

        # Check Missing Textures Button
        layout.operator("relink.check_missing_textures")

        # Missing Textures Count
        row = layout.row()
        row.label(text=f"Missing Textures: {props.missing_textures_count}")

        # Missing Textures List (read-only)
        if props.missing_textures_list:
            box = layout.box()
            box.label(text="Missing:")
            for item in props.missing_textures_list.split(', '):
                box.label(text=item)

        # Relink Missing Textures Button
        layout.operator("relink.relink_missing_textures")

        # Live Feedback
        layout.label(text=props.feedback_message)

        # Progress Bar
        row = layout.row(align=True)
        row.prop(props, "progress_value", text="Progress", slider=False)
        row.label(text=f"{props.progress_value:.0f}%")
