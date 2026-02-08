from . import properties
from . import light_properties
from .properties import register as register_properties, unregister as unregister_properties
from .light_properties import register as register_light_properties, unregister as unregister_light_properties

def register():
    register_properties()
    register_light_properties()

def unregister():
    unregister_light_properties()
    unregister_properties() 