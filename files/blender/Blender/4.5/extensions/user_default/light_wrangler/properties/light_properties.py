import bpy

# State dictionary to keep track of the addon's state
state = {
    "operator_running": False,
    "last_active_object_name": None,
    "last_active_object_update_counter": 0,
    "last_customization": "",
}

def add_custom_properties_to_lights():
    light_types = ["POINT", "SPOT", "AREA", "SUN"]
    custom_options = {
        "POINT": ["Default", "IES"],
        "SPOT": ["Default", "Gobo"],
        "AREA": ["Default", "Scrim", "HDRI", "Gobo"],
        "SUN": ["Default"],
    }

    for light_type in light_types:
        for option in custom_options[light_type]:
            prop_name = f"{light_type.lower()}_{option.lower()}"
            setattr(bpy.types.Light, prop_name, bpy.props.BoolProperty(name=prop_name))
    
    # Add root folder properties for per-light texture paths
    bpy.types.Light.gobo_root_folder = bpy.props.StringProperty(
        name="Gobo Folder",
        description="Folder containing gobo textures for this light",
        subtype='DIR_PATH',
        update=update_gobo_root_folder,
    )
    
    bpy.types.Light.hdri_root_folder = bpy.props.StringProperty(
        name="HDRI Folder",
        description="Folder containing HDRI textures for this light",
        subtype='DIR_PATH',
        update=update_hdri_root_folder,
    )
    
    bpy.types.Light.ies_root_folder = bpy.props.StringProperty(
        name="IES Folder",
        description="Folder containing IES profiles for this light",
        subtype='DIR_PATH',
        update=update_ies_root_folder,
    )

def update_gobo_root_folder(self, context):
    """Update when gobo folder changes."""
    # Update scene's last used folder
    context.scene.last_gobo_folder = self.gobo_root_folder
    # Reset enum to trigger refresh
    if hasattr(self, 'gobo_enum'):
        self['gobo_enum'] = 0

def update_hdri_root_folder(self, context):
    """Update when HDRI folder changes."""
    # Update scene's last used folder
    context.scene.last_hdri_folder = self.hdri_root_folder
    # Reset enum to trigger refresh
    if hasattr(self, 'hdri_enum'):
        self['hdri_enum'] = 0

def update_ies_root_folder(self, context):
    """Update when IES folder changes."""
    # Update scene's last used folder
    context.scene.last_ies_folder = self.ies_root_folder
    # Reset enum to trigger refresh
    if hasattr(self, 'ies_enum'):
        self['ies_enum'] = 0


def register():
    add_custom_properties_to_lights()

def unregister():
    # Clean up custom properties
    light_types = ["POINT", "SPOT", "AREA", "SUN"]
    custom_options = {
        "POINT": ["Default", "IES"],
        "SPOT": ["Default", "Gobo"],
        "AREA": ["Default", "Scrim", "HDRI", "Gobo"],
        "SUN": ["Default"],
    }

    for light_type in light_types:
        for option in custom_options[light_type]:
            prop_name = f"{light_type.lower()}_{option.lower()}"
            try:
                delattr(bpy.types.Light, prop_name)
            except:
                pass 
    
    # Clean up root folder properties
    for prop in ['gobo_root_folder', 'hdri_root_folder', 'ies_root_folder']:
        try:
            delattr(bpy.types.Light, prop)
        except:
            pass