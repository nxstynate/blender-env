import bpy
from .lib import *
from .ui import *
from .inits import *
class OBJECT_OT_cablerator_helper_apply_hook(bpy.types.Operator):
  """Select curves or hooks in Object Mode"""
  bl_idname = "object.cablerator_helper_apply_hook"
  bl_label = "Cablerator: Apply Hooks to Selected"
  bl_options = {"REGISTER", "UNDO"}
  @classmethod
  def poll(cls, context):
    ob = context.object
    edit_condition = True
    if ob:
      edit_condition = context.object.mode == 'OBJECT'
    else:
      edit_condition = False
    return context.area.type == "VIEW_3D" and edit_condition
  def execute(self, context):
    curves, hooks = filter_selected_hooks().values()
    post_curves = []
    def check_hooks():
      for ob in bpy.data.objects:
          if ob.type == 'CURVE' and ob not in curves:
              for mod in ob.modifiers:
                  if mod.type == 'HOOK':
                    if mod.object in hooks:
                        post_curves.append(ob)
      for curve in post_curves:
        for mod in curve.modifiers:
          if mod.type == 'HOOK' and mod.object in hooks:
            bpy.context.view_layer.objects.active = curve
            if mod.object:
              bpy.ops.object.modifier_apply(modifier=mod.name)
            else:
              curve.modifiers.remove(mod)
    if not len(curves) and not len(hooks):
      self.report({'ERROR'}, 'No curves or hooks found among the selected objects, aborting')
      return {'CANCELLED'}
    check_hooks()
    for curve in curves:
      for mod in curve.modifiers:
        if mod.type == 'HOOK':
          if mod.object not in hooks:
            hooks.append(mod.object)
          bpy.context.view_layer.objects.active = curve
          if mod.object:
            bpy.ops.object.modifier_apply(modifier=mod.name)
          else:
            curve.modifiers.remove(mod)
    check_hooks()
    for hook in hooks:
      if hook and hook.type == 'EMPTY':
        bpy.data.objects.remove(hook, do_unlink=True)
    return {'FINISHED'}
class OBJECT_OT_cablerator_helper_remove_hook(bpy.types.Operator):
  """Select curves or hooks in Object Mode"""
  bl_idname = "object.cablerator_helper_remove_hook"
  bl_label = "Cablerator: Remove Hooks from Selected"
  bl_options = {"REGISTER", "UNDO"}
  @classmethod
  def poll(cls, context):
    ob = context.object
    edit_condition = True
    if ob:
      edit_condition = context.object.mode == 'OBJECT'
    else:
      edit_condition = False
    return context.area.type == "VIEW_3D" and edit_condition
  def execute(self, context):
    curves, hooks = filter_selected_hooks().values()
    post_curves = []
    def check_hooks():
      for ob in bpy.data.objects:
          if ob.type == 'CURVE' and ob not in curves:
              for mod in ob.modifiers:
                  if mod.type == 'HOOK':
                    if mod.object in hooks:
                        post_curves.append(ob)
      for curve in post_curves:
        for mod in curve.modifiers:
          if mod.type == 'HOOK' and mod.object in hooks:
            curve.modifiers.remove(mod)
    if not len(curves) and not len(hooks):
      self.report({'ERROR'}, 'No curves or hooks found among the selected objects, aborting')
      return {'CANCELLED'}
    check_hooks()
    for curve in curves:
      for mod in curve.modifiers:
        if mod.type == 'HOOK':
          if mod.object not in hooks:
            hooks.append(mod.object)
          curve.modifiers.remove(mod)
    check_hooks()
    for hook in hooks:
      if hook and hook.type == 'EMPTY':
        bpy.data.objects.remove(hook, do_unlink=True)
    return {'FINISHED'}
class CBL_OT_OneHookToRuleThemAll(bpy.types.Operator):
  """Select bezier points in Edit mode
This will add a single hook to all of them"""
  bl_idname = "cbl.one_hook"
  bl_label = "Cablerator: Add a Single Hook"
  bl_options = {"REGISTER", "UNDO"}
  @classmethod
  def poll(cls, context):
    ob = context.object
    edit_condition = True
    if ob:
      edit_condition = context.object.mode == 'EDIT'
    else:
      edit_condition = False
    return context.area.type == "VIEW_3D" and edit_condition
  def execute(self, context):
    objs = bpy.context.selected_objects
    points = []
    get_prefs(self, context)
    self.show_curve_length = False
    curves, hooks = filter_selected_hooks().values()
    if not len(curves):
      self.report({'ERROR'}, 'No curves found among the selected objects, aborting')
      return {'CANCELLED'}
    for ob in objs:
        if ob.type == 'CURVE':
            super_select(ob, context)
            bpy.ops.object.hook_add_newob()
            hook = get_selected(context)[0]
            hook.empty_display_size = self.empty_size
            hook.empty_display_type = self.empties
            hook.name = 'Hook for ' + ob.name
            self.ob = ob
            self.points = get_selected_points(self.ob)
            points = get_selected_inner_points(self)
            coords = [list(point['coordinate']) for point in points]
            coords = np.asarray(coords)
            mins = np.abs(coords.min(axis=0))
            maxs = np.abs(coords.max(axis=0))
            hook.empty_display_size = (np.abs(mins - maxs)).max()
    switch_mode('OBJECT')
    super_select(objs, context)
    return {'FINISHED'}
class OBJECT_OT_cablerator_helper_add_hook(bpy.types.Operator):
  """Select bezier points in Edit mode"""
  bl_idname = "object.cablerator_helper_add_hook"
  bl_label = "Cablerator: Add Aligned Hooks"
  bl_options = {"REGISTER", "UNDO"}
  @classmethod
  def poll(cls, context):
    ob = context.object
    edit_condition = True
    if ob:
      edit_condition = context.object.mode == 'EDIT'
    else:
      edit_condition = False
    return context.area.type == "VIEW_3D" and edit_condition
  def execute(self, context):
    objs = bpy.context.selected_objects
    points = []
    get_prefs(self, context)
    self.show_curve_length = False
    curves, hooks = filter_selected_hooks().values()
    if not len(curves):
      self.report({'ERROR'}, 'No curves found among the selected objects, aborting')
      return {'CANCELLED'}
    for ob in objs:
        if ob.type == 'CURVE':
            mw = ob.matrix_world
            mwi = mw.inverted()
            for spline_index, spline in enumerate(ob.data.splines):
                if spline.type == 'BEZIER':
                    for point_index, point in enumerate(spline.bezier_points):
                        if point.select_control_point:
                          mw = ob.matrix_world
                          mwi = mw.inverted()
                          vec = point.handle_right - point.co
                          vec.normalize()
                          if point_index == 0:
                            axi = 'Z'
                          elif point_index == len(spline.bezier_points) - 1:
                            axi = '-Z'
                          else:
                            axi = 'Z' if point.handle_right[2] > point.handle_left[2] else '-Z'
                          points.append({
                            'ob': ob,
                            'point_index': point_index,
                            'spline_index': spline_index,
                            'location': mw @ point.co,
                            'rotation': vec.to_track_quat(axi,'X'),
                            })
    if not len(points):
      self.report({'ERROR'}, 'No selected points found, aborting')
      return {'CANCELLED'}
    if len(hooks) > 0:
      for point in points:
        switch_mode('OBJECT')
        super_select(point['ob'], bpy.context)
        switch_mode('EDIT')
        point['ob'].data.splines[point['spline_index']].bezier_points[point['point_index']].select_control_point = True
        point['ob'].data.splines[point['spline_index']].bezier_points[point['point_index']].select_right_handle = True
        point['ob'].data.splines[point['spline_index']].bezier_points[point['point_index']].select_left_handle = True
      for curve in curves:
        for hook in hooks:
          hook_name = hooks[0].name
          switch_mode('OBJECT')
          super_select(curve, bpy.context)
          hook.select_set(True)
          switch_mode('EDIT')
          bpy.ops.object.hook_add_selob(use_bone=False)
          curve.modifiers[-1].strength = 1 / len(hooks)
          curve.modifiers[-1].name = hook_name
      switch_mode('OBJECT')
      super_select(hooks[0], bpy.context)
      for hook in hooks:
        hook.select_set(True)
      return {'FINISHED'}
    switch_mode('OBJECT')
    for point in points:
      bpy.ops.object.empty_add(type=self.empties, align='WORLD', location=(0, 0, 0))
      empty = bpy.context.view_layer.objects.active
      empty.name = 'Hook for ' + point['ob'].name
      empty_rot = empty.rotation_mode
      empty.rotation_mode = 'QUATERNION'
      empty.rotation_quaternion = point['rotation']
      empty.rotation_mode = 'XYZ'
      temp = [empty.rotation_euler[0],empty.rotation_euler[1],empty.rotation_euler[2]]
      mat = point['ob'].matrix_world @ empty.rotation_euler.to_matrix().to_4x4()
      empty.matrix_world = mat
      empty.location = point['location']
      empty.rotation_mode = empty_rot
      empty.empty_display_size = self.empty_size
      super_select(point['ob'], context)
      hook_name = 'Cable Hook'
      switch_mode('EDIT')
      bpy.ops.curve.select_all(action='DESELECT')
      point['ob'].data.splines[point['spline_index']].bezier_points[point['point_index']].select_control_point = True
      point['ob'].data.splines[point['spline_index']].bezier_points[point['point_index']].select_right_handle = True
      point['ob'].data.splines[point['spline_index']].bezier_points[point['point_index']].select_left_handle = True
      empty.select_set(True)
      bpy.ops.object.hook_add_selob(use_bone=False)
      switch_mode('OBJECT')
      if self.parent_connectors:
        empty.select_set(True)
        context.view_layer.objects.active = point['ob']
        try:
          bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
        except Exception as e:
          self.report({'ERROR'}, str(e))
    return {'FINISHED'}
def register():
    bpy.utils.register_class(OBJECT_OT_cablerator_helper_add_hook)
    bpy.utils.register_class(CBL_OT_OneHookToRuleThemAll)
    bpy.utils.register_class(OBJECT_OT_cablerator_helper_remove_hook)
    bpy.utils.register_class(OBJECT_OT_cablerator_helper_apply_hook)
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_cablerator_helper_add_hook)
    bpy.utils.unregister_class(CBL_OT_OneHookToRuleThemAll)
    bpy.utils.unregister_class(OBJECT_OT_cablerator_helper_remove_hook)
    bpy.utils.unregister_class(OBJECT_OT_cablerator_helper_apply_hook)