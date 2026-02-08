import bpy
from .lib import *
from .ui import *
class OBJECT_OT_cableratorsplit(bpy.types.Operator):
  """Convert a multiprofile bezier curve to curves with separate profiles"""
  bl_idname = "object.cableratorsplit"
  bl_label = "Cablerator: Split a Cable"
  bl_options = {"REGISTER", "UNDO"}
  @classmethod
  def poll(cls, context):
      ob = context.object
      if not ob or len(context.selected_objects) == 0:
        return False
      else:
        return ob != None and context.area.type == "VIEW_3D" and ob.type == 'CURVE' and len(ob.data.splines) > 0 and ob.data.splines[0].type == 'BEZIER' and ob.data.bevel_object != None
  def execute(self, context):
    self.profiles_collection = []
    separated_profiles = []
    result = []
    profile_was_used = False
    for obj in context.selected_objects:
      if obj.type == 'CURVE' and obj.data.bevel_object != None:
        super_select(obj, context)
        self.ob = obj
        self.active_curve = get_active_curve()
        profile = self.active_curve['bevel']
        if profile in self.profiles_collection:
          profile_was_used = True
        else:
          profile_was_used = False
          self.profiles_collection.append(profile)
        if not profile_was_used:
          profile_clone = profile.copy()
          profile_clone.data = profile.data.copy()
          context.scene.collection.objects.link(profile_clone)
          profile_clone.location.x += profile_clone.dimensions.x + .1
          super_select(profile_clone, context)
          separated_profiles = separate_curve(profile_clone)
          super_select(profile_clone, context)
          bpy.ops.object.delete(use_global=False, confirm=False)
        for (index, o) in enumerate(separated_profiles):
          curve_clone = self.ob.copy()
          curve_clone.data = self.ob.data.copy()
          context.scene.collection.objects.link(curve_clone)
          if GV.is291: curve_clone.data.bevel_mode = 'OBJECT'
          curve_clone.data.bevel_object = o
          curve_clone.name = self.ob.name + ' ' + f'{index+1:02}'
          result.append(curve_clone)
          o.name = profile.name + ' ' + f'{index+1:02}'
        super_select(self.ob, context)
        bpy.ops.object.delete(use_global=False, confirm=False)
        for curve in result:
          curve.select_set(True)
        context.view_layer.objects.active = result[0]
    return {'FINISHED'}
def register():
    bpy.utils.register_class(OBJECT_OT_cableratorsplit)
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_cableratorsplit)