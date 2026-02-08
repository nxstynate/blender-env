import bpy
from .lib import *
from .ui import *
class OBJECT_OT_cableratorsplitrecable(bpy.types.Operator):
  """Changes the cable curve position"""
  bl_idname = "object.cableratorsplitrecable"
  bl_label = "Cablerator: Rebuild Split Cable"
  bl_options = {"REGISTER", "UNDO"}
  @classmethod
  def poll(cls, context):
      ob = context.object
      if not ob or len(context.selected_objects) == 0:
        return False
      else:
        return ob != None and context.area.type == "VIEW_3D" and ob.type == 'CURVE' and ob.data.splines[0].type
  def execute(self, context):
    self.profiles_collection = []
    self.converted_obs = []
    separated_profiles = []
    profile_was_used = False
    mat = None
    if context.view_layer.objects.active.data.materials:
      mat = context.view_layer.objects.active.data.materials[0]
    for obj in context.selected_objects:
      if obj.type == 'CURVE' and obj.data.bevel_object != None:
        is_bezier = True
        for spline in obj.data.splines:
          if spline.type != 'BEZIER':
            is_bezier = False
        switch_mode('EDIT')
        if not is_bezier:
          bpy.ops.curve.spline_type_set(type='BEZIER')
        bpy.ops.curve.select_all(action='SELECT')
        bpy.ops.curve.handle_type_set(type='ALIGNED')
        switch_mode('OBJECT')
        original_points_distances = []
        original_start_finish_points = []
        super_select(obj, context)
        self.ob = obj
        self.active_curve = get_active_curve()
        for index, spline in enumerate(self.ob.data.splines):
            temp_arr = []
            temp_arr2 = []
            for pindex, point in enumerate(spline.bezier_points):
              temp_arr.append([distance_between(point.handle_left, point.co),distance_between(point.handle_right, point.co)])
              v1 = point.handle_left - point.co
              v2 = point.handle_right - point.co
              v1.normalize()
              v2.normalize()
              temp_arr2.append([v1, v2])
            original_points_distances.append(temp_arr)
            original_start_finish_points.append(temp_arr2)
        res = self.ob.data.resolution_u = self.ob.data.resolution_u
        twist_mode = self.ob.data.twist_mode
        should_separate = len(self.ob.data.splines) > 1
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
          profile_clone.location.x += profile_clone.dimensions.x + .5
          profile_clone.name = profile_clone.name + "_centered"
          super_select(profile_clone, context)
          switch_mode('EDIT')
          bpy.ops.curve.select_all(action='SELECT')
          pivot_to_selection(self, context)
          switch_mode('OBJECT')
        self.used_fill_caps = False
        if GV.is291:
          self.used_fill_caps = self.ob.data.use_fill_caps
          self.ob.data.use_fill_caps = False
        super_select(self.ob, context)
        bpy.ops.object.convert(target='MESH')
        if should_separate:
          switch_mode('EDIT')
          bpy.ops.mesh.separate(type='LOOSE')
          switch_mode('OBJECT')
        self.objs_to_bmesh = context.selected_objects
        for mesh in self.objs_to_bmesh:
          super_select(mesh, context)
          self.mesh = context.view_layer.objects.active
          switch_mode('EDIT')
          bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')
          switch_mode('OBJECT')
          bm = bmesh.new()
          bm.from_mesh(self.mesh.data)
          bm.edges.ensure_lookup_table()
          bm.edges[0].select = True
          bm.to_mesh(self.mesh.data)
          bm.free()
          switch_mode('EDIT')
          bpy.ops.mesh.loop_multi_select(ring=True)
          bm = bmesh.from_edit_mesh(self.mesh.data)
          selected_edges = [edge for edge in bm.edges if edge.select]
          bm.edges.ensure_lookup_table()
          for edge in selected_edges:
            bpy.ops.mesh.select_all(action='DESELECT')
            edge.select = True
            bpy.ops.mesh.loop_multi_select(ring=False)
            bpy.ops.mesh.merge(type='CENTER')
          bpy.ops.mesh.select_all(action='SELECT')
          switch_mode('OBJECT')
          bpy.ops.object.convert(target='CURVE')
        if should_separate:
          for mesh in self.objs_to_bmesh:
            mesh.select_set(True)
          bpy.ops.object.join()
        switch_mode('EDIT')
        bpy.ops.curve.spline_type_set(type='BEZIER')
        bpy.ops.curve.handle_type_set(type='AUTOMATIC')
        bpy.ops.curve.handle_type_set(type='ALIGNED')
        switch_mode('OBJECT')
        self.converted_ob = context.view_layer.objects.active
        self.converted_obs.append(self.converted_ob)
        if self.used_fill_caps: self.converted_ob.data.use_fill_caps = True
        switch_mode('EDIT')
        bpy.ops.curve.select_all(action='DESELECT')
        for spline in self.converted_ob.data.splines:
            count = 0
            for index, point in reversed(list(enumerate(spline.bezier_points))):
                if count != 0:
                    point.select_control_point = True
                count += 1
                if count == res:
                    count = 0
        bpy.ops.curve.dissolve_verts()
        mwi = self.converted_ob.matrix_world.inverted()
        for index, spline in enumerate(self.converted_ob.data.splines):
            for pindex, point in enumerate(spline.bezier_points):
              point.handle_left = point.co + original_start_finish_points[index][pindex][0] * original_points_distances[index][pindex][0]
              point.handle_right = point.co + original_start_finish_points[index][pindex][1] * original_points_distances[index][pindex][1]
        switch_mode('OBJECT')
        if GV.is291: self.converted_ob.data.bevel_mode = 'OBJECT'
        self.converted_ob.data.bevel_object = profile_clone
        self.converted_ob.data.twist_mode = twist_mode
        self.converted_ob.data.resolution_u = res
        bpy.ops.object.shade_smooth()
        if mat:
          self.converted_ob.data.materials.append(mat)
    for ob in self.converted_obs:
      ob.select_set(True)
    return {'FINISHED'}
def register():
    bpy.utils.register_class(OBJECT_OT_cableratorsplitrecable)
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_cableratorsplitrecable)