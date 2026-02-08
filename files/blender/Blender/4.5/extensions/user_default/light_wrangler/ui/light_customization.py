import bpy
from bpy.types import Panel
from .. import ADDON_MODULE_NAME
from ..utils.blender_compat import get_supported_render_engines, is_eevee_engine

class LIGHTW_PT_LightCustomization(Panel):
    bl_label = "Light Customization"
    bl_idname = "LIGHTW_PT_light_customization"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def poll(cls, context):
        prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
        
        return (
            (context.scene.render.engine in get_supported_render_engines())
            and context.object is not None
            and context.object.type == "LIGHT"
        )
        
    def draw(self, context):
        layout = self.layout
        light_obj = context.object
        light_data = light_obj.data
        prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
        
        last_customization_key = f"last_customization_{light_data.type}"
        current_customization = light_obj.get(last_customization_key, "Default")
        
        if (is_eevee_engine(context.scene.render.engine) or context.scene.render.engine == "octane") and current_customization in ["Scrim", "HDRI", "Gobo"]:
            box = layout.box()
            op = box.operator(
                "lightwrangler.confirm_cycles_switch",
                text="Activate Cycles to Edit"
            )
            op.light_name = light_obj.name
            op.light_type = light_data.type
            op.customization = current_customization
        else:
            # Existing draw logic for Cycles and non-limited Eevee modes
            if light_data.type == "POINT":
                self.draw_customization_buttons(
                    layout, light_obj, "POINT", ["Default", "IES"]
                )
            elif light_data.type == "SPOT":
                self.draw_customization_buttons(
                    layout, light_obj, "SPOT", ["Default", "Gobo"]
                )
            elif light_data.type == "AREA":
                self.draw_customization_buttons(
                    layout, light_obj, "AREA", ["Default", "Scrim", "HDRI", "Gobo"]
                )
            elif light_data.type == "SUN":
                self.draw_customization_buttons(layout, light_obj, "SUN", ["Default"])
            
    def draw_customization_buttons(self, layout, light_obj, light_type, options):
        prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
        last_customization_key = f"last_customization_{light_type}"
        current_customization = light_obj.get(last_customization_key, "Default")

        row = layout.row(align=True)

        for option in options:
            if (is_eevee_engine(bpy.context.scene.render.engine) or bpy.context.scene.render.engine == "octane") and option in ["Scrim", "HDRI", "Gobo", "IES"]:
                op = row.operator(
                    "lightwrangler.confirm_cycles_switch",
                    text=option,
                    depress=option == current_customization,
                )
            else:
                op = row.operator(
                    "lightwrangler.apply_custom_data_block",
                    text=option,
                    depress=option == current_customization,
                )
            op.light_name = light_obj.name
            op.light_type = light_type
            op.customization = option

        if current_customization in ["Gobo", "HDRI", "IES"]:
            box = layout.box()
            col = box.column()

            if current_customization == "Gobo":
                # Per-light folder UI temporarily hidden - using addon preference paths instead
                # folder_row = col.row(align=True)
                # folder_row.prop(light_obj.data, 'gobo_root_folder', text="")
                # if light_obj.data.gobo_root_folder:
                #     folder_row.operator('lightwrangler.clear_gobo_root_folder', icon='X', text="")
                #     col.separator(factor=0.5)
                
                # Rest of Gobo UI
                # Check if stored identifier matches current enum selection
                gobo_identifier = getattr(light_obj.data, 'gobo_identifier', '')
                gobo_enum = getattr(light_obj.data, 'gobo_enum', '')
                
                if gobo_identifier and gobo_enum and gobo_identifier != gobo_enum:
                    # Show refresh button when mismatch detected
                    row = col.row(align=True)
                    row.scale_y = 2.0  # Make button more prominent
                    row.operator('lightwrangler.refresh_gobo_preview', icon='FILE_REFRESH')
                else:
                    # Show normal preview grid
                    col.template_icon_view(
                        light_obj.data,
                        "gobo_enum",
                        show_labels=prefs.show_texture_labels,
                        scale_popup=prefs.texture_popup_scale,
                        scale=prefs.texture_preview_scale,
                    )
                # Only show Convert to Plane button for area lights
                if light_type == 'AREA':
                    # Add buttons in a row
                    row = col.row(align=True)
                    # Add the "Convert to Plane" button
                    row.operator(
                        "lightwrangler.convert_to_plane",
                        text="Convert to Plane",
                        icon='MESH_PLANE'
                    )
            elif current_customization == "HDRI":
                # Per-light folder UI temporarily hidden - using addon preference paths instead
                # folder_row = col.row(align=True)
                # folder_row.prop(light_obj.data, 'hdri_root_folder', text="")
                # if light_obj.data.hdri_root_folder:
                #     folder_row.operator('lightwrangler.clear_hdri_root_folder', icon='X', text="")
                #     col.separator(factor=0.5)
                
                # Rest of HDRI UI
                # Check if stored identifier matches current enum selection
                hdri_identifier = getattr(light_obj.data, 'hdri_identifier', '')
                hdri_enum = getattr(light_obj.data, 'hdri_enum', '')
                
                if hdri_identifier and hdri_enum and hdri_identifier != hdri_enum:
                    # Show refresh button when mismatch detected
                    row = col.row(align=True)
                    row.scale_y = 2.0  # Make button more prominent
                    row.operator('lightwrangler.refresh_hdri_preview', icon='FILE_REFRESH')
                else:
                    # Show normal preview grid
                    col.template_icon_view(
                        light_obj.data,
                        "hdri_enum",
                        show_labels=prefs.show_texture_labels,
                        scale_popup=prefs.texture_popup_scale,
                        scale=prefs.texture_preview_scale,
                    )
            elif current_customization == "IES":
                # Per-light folder UI temporarily hidden - using addon preference paths instead
                # folder_row = col.row(align=True)
                # folder_row.prop(light_obj.data, 'ies_root_folder', text="")
                # if light_obj.data.ies_root_folder:
                #     folder_row.operator('lightwrangler.clear_ies_root_folder', icon='X', text="")
                #     col.separator(factor=0.5)
                
                # Rest of IES UI
                # Check if stored identifier matches current enum selection
                ies_identifier = getattr(light_obj.data, 'ies_identifier', '')
                ies_enum = getattr(light_obj.data, 'ies_enum', '')
                
                if ies_identifier and ies_enum and ies_identifier != ies_enum:
                    # Show refresh button when mismatch detected
                    row = col.row(align=True)
                    row.scale_y = 2.0  # Make button more prominent
                    row.operator('lightwrangler.refresh_ies_preview', icon='FILE_REFRESH')
                else:
                    # Show normal preview grid
                    col.template_icon_view(
                        light_obj.data, 
                        "ies_enum", 
                        show_labels=prefs.show_texture_labels, 
                        scale_popup=prefs.texture_popup_scale, 
                        scale=prefs.texture_preview_scale
                    )

        elif current_customization == "Scrim":
            mat = bpy.data.materials.get("Scrim Preview")

# List of all classes in this file
classes = (
    LIGHTW_PT_LightCustomization,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls) 