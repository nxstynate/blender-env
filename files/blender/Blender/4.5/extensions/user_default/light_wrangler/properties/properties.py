import bpy
from bpy.props import EnumProperty, PointerProperty, BoolProperty, CollectionProperty, StringProperty, FloatProperty, IntProperty
from .. import ADDON_MODULE_NAME

class EmissionState(bpy.types.PropertyGroup):
    """Store emission node state"""
    node_name: StringProperty()
    node_type: StringProperty()
    strength: FloatProperty()
    material_name: StringProperty()
    material_slot_index: IntProperty(default=-1)

class LightState(bpy.types.PropertyGroup):
    """Store light state for isolation"""
    name: StringProperty()
    hide_viewport: BoolProperty()
    emission_states: CollectionProperty(type=EmissionState)

class WorldState(bpy.types.PropertyGroup):
    """Store world node state"""
    name: StringProperty()
    mute: BoolProperty()

class LightWranglerProperties(bpy.types.PropertyGroup):
    """Properties for the Light Wrangler add-on"""
    last_mode: EnumProperty(
        items=[
            ('REFLECT', "Reflect", "Position light by reflection angle"),
            ('DIRECT', "Direct", "Position light directly on surface"),
            ('ORBIT', "Orbit", "Orbit light around target point")
        ],
        name="Last Mode",
        description="Last used light positioning mode",
        default='REFLECT'
    )
    
    @property
    def show_help_default(self):
        """Get the default show_help value from addon preferences"""
        try:
            prefs = bpy.context.preferences.addons[ADDON_MODULE_NAME].preferences
            return prefs.show_help_by_default
        except:
            return True
    
    show_help: BoolProperty(
        name="Show Help",
        description="Whether to show the help panel by default",
        get=lambda self: self.get("show_help", self.show_help_default),
        set=lambda self, value: self.__setitem__("show_help", value)
    )

    is_isolated: BoolProperty(
        name="Is Isolated",
        description="Whether lights are currently isolated",
        default=False
    )

    is_interactive_mode_active: BoolProperty(
        name="Interactive Mode Active",
        description="Whether the interactive operator is currently running",
        default=False
    )

    original_states: CollectionProperty(type=LightState)
    original_world_states: CollectionProperty(type=WorldState)

# Registration
classes = (
    EmissionState,
    LightState,
    WorldState,
    LightWranglerProperties,
)

def register():
    from ..utils import logger
    logger.start_section("Property Classes")
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            logger.log_registration(cls.__name__)
        except Exception as e:
            logger.log_registration(cls.__name__, False, str(e))
    
    try:
        bpy.types.Scene.lightwrangler_props = PointerProperty(type=LightWranglerProperties)
        logger.debug("Registered lightwrangler_props on Scene")
    except Exception as e:
        logger.error(f"Failed to register lightwrangler_props: {e}")
    
    # Add last used folder properties to Scene
    bpy.types.Scene.last_gobo_folder = StringProperty(
        name="Last Gobo Folder",
        description="Last used gobo folder for new lights",
        subtype='DIR_PATH',
        default=""
    )
    
    bpy.types.Scene.last_hdri_folder = StringProperty(
        name="Last HDRI Folder",
        description="Last used HDRI folder for new lights",
        subtype='DIR_PATH',
        default=""
    )
    
    bpy.types.Scene.last_ies_folder = StringProperty(
        name="Last IES Folder",
        description="Last used IES folder for new lights",
        subtype='DIR_PATH',
        default=""
    )
    
    logger.end_section()

def unregister():
    from ..utils import logger
    logger.start_section("Property Classes")
    
    # Clean up last used folder properties
    for prop in ['last_gobo_folder', 'last_hdri_folder', 'last_ies_folder']:
        try:
            delattr(bpy.types.Scene, prop)
        except:
            pass
    
    try:
        del bpy.types.Scene.lightwrangler_props
        logger.debug("Unregistered lightwrangler_props from Scene")
    except Exception as e:
        logger.error(f"Failed to unregister lightwrangler_props: {e}")
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
            logger.log_unregistration(cls.__name__)
        except Exception as e:
            logger.log_unregistration(cls.__name__, False, str(e))
    
    logger.end_section() 