from time import process_time
import bpy
from .lib import *
from .ui import *
class OBJECT_OT_cableratorconnect(bpy.types.Operator):
  """Select two end points of a cable"""
  bl_idname = "object.cableratorconnect"
  bl_label = "Cablerator: Merge End Points"
  bl_options = {"REGISTER", "UNDO"}
  @classmethod
  def poll(cls, context):
      edit_condition = len(context.selected_objects) > 0
      return context.area.type == "VIEW_3D" and edit_condition
  def get_points(self):
    points = list()
    for sindex, spline in enumerate(self.ob.data.splines):
        if spline.type == 'BEZIER':
          for pindex, point in enumerate(spline.bezier_points):
            if self.mode == 'EDIT':
              if not point.select_control_point:
                continue
            if pindex == 0 or pindex == len(spline.bezier_points)-1:
              points.append({
              'co': point.co.copy(),
              'pindex': pindex,
              'sindex': sindex,
              })
        elif spline.type == 'POLY':
          for pindex, point in enumerate(spline.points):
            if self.mode == 'EDIT':
              if not point.select:
                continue
            if pindex == 0 or pindex == len(spline.points)-1:
              points.append({
              'co': point.co.copy(),
              'pindex': pindex,
              'sindex': sindex,
              })
    return points
  def get_intersections(self):
    final_arr = dict()
    if self.mode == 'EDIT':
      pairs = list()
      for index, point in enumerate(self.points):
          dist = 1.e+10
          for kindex, point_i in enumerate(self.points):
              if point is not point_i:
                  if (point_i['co'] - point['co']).length < dist:
                      dist = (point_i['co'] - point['co']).length
                      pair = [index, kindex]
          pairs.append(pair)
      pairs = [list(el) for el in set(frozenset(el) for el in pairs)]
      for index, pair in enumerate(pairs):
          final_arr[str(index)] = list()
          for el in pair:
              final_arr[str(index)].append([self.points[el]['sindex'],self.points[el]['pindex']])
    else:
      intersections = list()
      for point in self.points:
        for another_point in self.points:
          if (point['co'] - another_point['co']).length_squared < 1.e-10:
            if point['sindex'] != another_point['sindex'] and point['pindex'] != another_point['pindex']:
              intersections.append([[point['sindex'], point['pindex']], [another_point['sindex'], another_point['pindex']]])
      if not intersections:
        return list()
      d = dict()
      for i, intersection in enumerate(intersections):
          for k,el in enumerate(intersection):
              if f"{el}" not in d:
                  d[f"{el}"] = f"{str(i)}x{str(k)}"
      for arr in d:
          s,p = d[arr].split('x')
          if s not in final_arr:
              final_arr[s] = list()
          final_arr[s].append(ast.literal_eval(arr))
    return final_arr
  def intersections_to_points(self):
    point_pairs = []
    mw = self.ob.matrix_world
    for index in self.intersections:
      p1, p2 = self.intersections[index]
      if self.ob.data.splines[p1[0]].type == 'BEZIER':
        points = [
        [self.ob.data.splines[p1[0]].bezier_points[p1[1]],p1],
        [self.ob.data.splines[p2[0]].bezier_points[p2[1]],p2]
        ]
      elif self.ob.data.splines[p1[0]].type == 'POLY':
        points = [
        [self.ob.data.splines[p1[0]].points[p1[1]],p1],
        [self.ob.data.splines[p2[0]].points[p2[1]],p2]
        ]
      points_pair = list()
      for point in points:
        if self.ob.data.splines[p1[0]].type == 'BEZIER':
          points_pair.append({
                          'p1': mw @ point[0].co.copy(),
                          'p2': mw @ point[0].handle_right.copy() if point[1][1] == 0 else mw @ point[0].handle_left.copy(),
                          'spline': point[1][0],
                          'index': point[1][1],
                          'updated': False,
                          'orientation': 'right' if point[1][1] == 0 else 'left',
                          'type': self.ob.data.splines[p1[0]].type
                      })
        elif self.ob.data.splines[p1[0]].type == 'POLY':
          points_pair.append({
                          'p1': mw @ point[0].co.copy(),
                          'p2': mw @ point[0].co.copy(),
                          'spline': point[1][0],
                          'index': point[1][1],
                          'updated': False,
                          'orientation': 'right' if point[1][1] == 0 else 'left',
                          'type': self.ob.data.splines[p1[0]].type
                      })
      point_pairs.append(points_pair)
    return point_pairs
  def update_indices(self):
    cur_sindex = -1
    mw = self.ob.matrix_world
    for pair_point in self.points_to_merge:
      for point in pair_point:
        for sindex, real_spline in enumerate(self.ob.data.splines):
          s_points = real_spline.bezier_points if point['type'] == 'BEZIER' else real_spline.points
          for pindex, real_point in enumerate(s_points):
            if not point['updated'] and cur_sindex != sindex and (point['p1'] - mw @ real_point.co).length_squared < 1.e-4:
              point['spline'] = sindex
              point['index'] = pindex
              point['updated'] = True
              cur_sindex = sindex
    for pair_point in self.points_to_merge:
      for point in pair_point:
        point['updated'] = False
  def execute(self, context):
    obs = context.selected_objects
    self.mode = context.object.mode
    for ob in obs:
      if ob.type != 'CURVE':
        self.report({'ERROR'}, f'Expected selected object to be a Curve object, not {ob.type.capitalize()}, aborting')
        return {'CANCELLED'}
    if len(obs) > 1:
      bpy.ops.object.mode_set(mode='OBJECT')
      aob_name = context.view_layer.objects.active.name
      dups = list()
      for ob in obs:
          dups.append(duplicate_object(ob))
      super_remove(obs, context)
      super_select(dups, context)
      bpy.ops.object.join()
      context.view_layer.objects.active.name = aob_name
      bpy.ops.object.mode_set(mode='EDIT')
    self.ob = context.view_layer.objects.active
    self.active_curve = get_active_curve()
    self.points = self.get_points()
    self.intersections = self.get_intersections()
    self.points_to_merge = self.intersections_to_points()
    if self.mode == 'OBJECT': switch_mode('EDIT')
    for pair_points in self.points_to_merge:
      self.points = pair_points.copy()
      if len(pair_points) != 2:
        self.report({'ERROR'}, 'This function expects 2 end points')
        return {'CANCELLED'}
      bpy.ops.curve.select_all(action='DESELECT')
      for point in pair_points:
        try:
          if point['type'] == 'BEZIER':
            self.ob.data.splines[point['spline']].bezier_points[point['index']].select_control_point = True
          else:
            self.ob.data.splines[point['spline']].points[point['index']].select = True
        except:
          self.report({'ERROR'}, f"failed to select point: {point}, splines length: {len(self.ob.data.splines)}")
          return {'CANCELLED'}
      try:
        bpy.ops.curve.make_segment()
      except:
        self.report({'ERROR'},"Can't connect points! (maybe different spline types?)")
        return {'CANCELLED'}
      self.new_points = get_selected_inner_points(self)
      index = -1
      deleted_index = -1
      rest_index = -1
      condition = self.new_points[0]['index'] > self.new_points[1]['index']
      remove_index = int(not self.new_points[0]['index'] > self.new_points[1]['index'])
      stay_index = int(not remove_index)
      cycle_segment = False
      if abs(self.new_points[0]['index'] - self.new_points[1]['index']) == 1:
        cycle_segment = True
      if self.new_points[0]['type'] == 'BEZIER':
        directions = {
          'left': pair_points[0]['p2'] if pair_points[0]['orientation'] == 'left' else pair_points[1]['p2'],
          'right': pair_points[0]['p2'] if pair_points[0]['orientation'] == 'right' else pair_points[1]['p2'],
        }
        self.new_points[stay_index]['point'].select_control_point = False
        self.new_points[stay_index]['point'].select_right_handle = False
        self.new_points[stay_index]['point'].select_left_handle = False
        index = self.new_points[stay_index]['index']
        spline_type = 'BEZIER'
      else:
        self.new_points[stay_index]['point'].select = False
        index = self.new_points[stay_index]['index']
        index = self.new_points[stay_index]['index']
        spline_type = 'POLY'
      bpy.ops.curve.delete(type='VERT')
      mw = self.ob.matrix_world
      mwi = self.ob.matrix_world.inverted()
      if spline_type == 'BEZIER':
        self.new_point = self.ob.data.splines[self.new_points[0]['spline']].bezier_points[index]
        self.new_point.co = (self.new_points[0]['coordinate'] + self.new_points[1]['coordinate'])/2
        offset1 = self.new_points[0]['coordinate'] - self.new_point.co
        offset2 = self.new_points[1]['coordinate'] - self.new_point.co
        self.new_point.handle_left = mwi @ directions['left']
        self.new_point.handle_right = mwi @ directions['right']
      else:
        self.new_point = self.ob.data.splines[self.new_points[0]['spline']].points[index]
        self.new_point.co = (self.new_points[0]['coordinate'] + self.new_points[1]['coordinate'])/2
      self.update_indices()
    return {'FINISHED'}
def register():
    bpy.utils.register_class(OBJECT_OT_cableratorconnect)
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_cableratorconnect)