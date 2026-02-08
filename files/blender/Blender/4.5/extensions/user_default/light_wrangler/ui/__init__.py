from . import ui
from . import light_customization
from . import render_panels
from .ui import register as register_ui, unregister as unregister_ui
from .light_customization import register as register_customization, unregister as unregister_customization
from .render_panels import register as register_render_panels, unregister as unregister_render_panels

def register():
    register_ui()
    register_customization()
    register_render_panels()

def unregister():
    unregister_render_panels()
    unregister_customization()
    unregister_ui() 