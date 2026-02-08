from . import operators
from . import hdri_operators
from . import light_operators
from . import render_operators
from .operators import register as register_operators, unregister as unregister_operators
from .hdri_operators import register as register_hdri, unregister as unregister_hdri
from .light_operators import register as register_light, unregister as unregister_light
from .render_operators import register as register_render, unregister as unregister_render
from .operators import LIGHTW_OT_InteractiveOperator
from .hdri_operators import LIGHTW_OT_HDRIRotate

def register():
    register_operators()
    register_hdri()
    register_light()
    register_render()

def unregister():
    unregister_render()
    unregister_light()
    unregister_hdri()
    unregister_operators() 