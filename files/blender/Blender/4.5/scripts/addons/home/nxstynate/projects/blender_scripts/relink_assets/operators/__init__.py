from . import relink_operator
from . import check_textures_operator

def register():
    relink_operator.register()
    check_textures_operator.register()

def unregister():
    relink_operator.unregister()
    check_textures_operator.unregister()