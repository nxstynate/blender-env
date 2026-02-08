import bpy

class LIGHTW_PT_RenderHDRIPanel(bpy.types.Panel):
    bl_label = "HDRI Scene Rendering"
    bl_idname = "WORLD_PT_lightw_hdri_render"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "world"

    @classmethod
    def poll(cls, context):
        return bpy.app.version >= (4, 0, 0)

    def draw(self, context):
        layout = self.layout
        
        # Resolution selection with label
        row = layout.row()
        row.label(text="Select Resolution:")
        # Add info icon that opens popup
        row.operator("lightwrangler.show_hdri_info", text="", icon='INFO')
        
        row = layout.row(align=True)
        
        # Resolution buttons in a more compact layout
        ops = row.operator("lightwrangler.render_360_hdri", text="2K")
        ops.resolution_x = 2048
        ops.resolution_y = 1024

        ops = row.operator("lightwrangler.render_360_hdri", text="4K")
        ops.resolution_x = 4096
        ops.resolution_y = 2048

        ops = row.operator("lightwrangler.render_360_hdri", text="8K")
        ops.resolution_x = 8192
        ops.resolution_y = 4096

        ops = row.operator("lightwrangler.render_360_hdri", text="16K")
        ops.resolution_x = 16384
        ops.resolution_y = 8192

class LIGHTW_PT_RenderScrimHDRIPanel(bpy.types.Panel):
    bl_label = "Export Scrim as HDR"
    bl_idname = "DATA_PT_lightw_scrim_hdri_render"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return (bpy.app.version >= (4, 0, 0) and 
                context.scene.render.engine == "CYCLES" and
                context.object is not None and 
                context.object.type == "LIGHT" and
                context.object.data.type == "AREA" and
                context.object.get("last_customization_AREA", "Default") == "Scrim")

    def draw(self, context):
        layout = self.layout
        
        # Resolution selection with label
        row = layout.row()
        row.label(text="Select Resolution:")
        # Add info icon that opens popup
        row.operator("lightwrangler.show_scrim_hdri_info", text="", icon='INFO')
        
        row = layout.row(align=True)
        
        # Resolution buttons in a more compact layout
        ops = row.operator("lightwrangler.render_scrim_hdri", text="1K")
        ops.resolution = 1024

        ops = row.operator("lightwrangler.render_scrim_hdri", text="2K")
        ops.resolution = 2048

        ops = row.operator("lightwrangler.render_scrim_hdri", text="3K")
        ops.resolution = 3072

        ops = row.operator("lightwrangler.render_scrim_hdri", text="4K")
        ops.resolution = 4096

class LIGHTW_OT_ShowHDRIInfo(bpy.types.Operator):
    bl_idname = "lightwrangler.show_hdri_info"
    bl_label = "HDRI Render Tips"
    bl_description = "Show usage tips for HDRI rendering"
    
    def execute(self, context):
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=365) 
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="Quick Tips:", icon='INFO')
        
        # Create a box for better visual grouping
        box = layout.box()
        col = box.column()
        row = col.row()
        split = row.split(factor=0.05)
        split.label(text="•")
        split.label(text="360° camera position is determined by 3D cursor location", icon='CURSOR')
        
        row = col.row()
        split = row.split(factor=0.05)
        split.label(text="•")
        split.label(text="To exclude lights from rendering, hide them in viewport", icon='HIDE_ON')

class LIGHTW_OT_ShowScrimHDRIInfo(bpy.types.Operator):
    bl_idname = "lightwrangler.show_scrim_hdri_info"
    bl_label = "Export Scrim as HDR Tips"
    bl_description = "Show usage tips for exporting scrim as HDR"
    
    def execute(self, context):
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=365) 
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="Quick Tips:", icon='INFO')
        
        # Create a box for better visual grouping
        box = layout.box()
        col = box.column()
        row = col.row()
        split = row.split(factor=0.05)
        split.label(text="•")
        split.label(text="Renders your scrim pattern into square HDR image", icon='LIGHT_AREA')
        
        row = col.row()
        split = row.split(factor=0.05)
        split.label(text="•")
        split.label(text="Use in different rendering engines or other applications", icon='TEXTURE')

# Registration
classes = (
    LIGHTW_PT_RenderHDRIPanel,
    LIGHTW_PT_RenderScrimHDRIPanel,
    LIGHTW_OT_ShowHDRIInfo,
    LIGHTW_OT_ShowScrimHDRIInfo,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)