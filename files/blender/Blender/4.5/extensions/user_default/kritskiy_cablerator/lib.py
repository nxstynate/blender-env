import bpy
import math
import mathutils
from bpy_extras import view3d_utils
from mathutils import Vector, Matrix, Euler
from mathutils.geometry import intersect_line_plane
from math import radians, degrees, sin, cos, pi
import traceback
import bmesh
import os
import re
from random import random, sample, uniform
import time
from datetime import datetime
import requests
import numpy as np
import ast
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_line_plane as ilp
from mathutils.geometry import intersect_point_line as ipl
from mathutils.geometry import convex_hull_2d, distance_point_to_plane
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_vector_3d, region_2d_to_origin_3d
from mathutils.geometry import interpolate_bezier
from statistics import median
import json
import uuid
def is_point_in_rect(x, y, rect):
    p1, p2, p3, p4 = rect
    x1, y1 = p1
    x2, y2 = p3
    return x1 <= x <= x2 and y1 <= y <= y2
def find_lowest_point(points, mw):
  mins = [[index, (mw @ point.co).z] for index, point in enumerate(points)]
  mins = sorted(mins, key=lambda x: x[1])
  return mins[0][0]
def set_first_polyspline_point(ob):
  for spline in ob.data.splines:
    if spline.type != 'POLY': continue
    point_index = find_lowest_point(spline.points, ob.matrix_world)
    original_points = []
    for index, point in enumerate(spline.points):
        original_points.append({
            "co": point.co.copy(),
            "index": index,
            "tilt": point.tilt,
            "radius": point.radius,
        })
    if not point_index: continue
    new_points = original_points[point_index:] + original_points[:point_index]
    for index, point in enumerate(spline.points):
        point.select = False
        point.co = new_points[index]["co"]
        point.tilt = new_points[index]["tilt"]
        point.radius = new_points[index]["radius"]
    spline.points[0].select = True
    return point_index
def get_hotkey_entry_item(km, kmi_name, kmi_value, properties):
    for i, km_item in enumerate(km.keymap_items):
        if km.keymap_items.keys()[i] == kmi_name:
            if properties == 'name':
                if km.keymap_items[i].properties.name == kmi_value:
                    return km_item
            elif properties == 'tab':
                if km.keymap_items[i].properties.tab == kmi_value:
                    return km_item
            elif properties == 'none':
                return km_item
    return None
class GV:
  is291 = bpy.app.version >= (2, 91, 0)
  before32 = bpy.app.version < (3, 2, 0)
  after4 = bpy.app.version >= (4, 0, 0)
  is41 = bpy.app.version >= (4, 1, 0)
  is42 = bpy.app.version >= (4, 2, 0)
def switch_mode(mode):
    try:
      bpy.ops.object.mode_set(mode=mode)
    except:
      pass
def add_auto_smooth_mod(context, ob, smooth_angle=0.523599):
  with bpy.context.temp_override(object=ob):
    mod = next((mod for mod in ob.modifiers if (mod.type == 'NODES') and mod.name.startswith('Smooth by Angle') != -1),None)
    if not mod:
        bpy.ops.object.modifier_add_node_group(asset_library_type='ESSENTIALS', asset_library_identifier="", relative_asset_identifier="geometry_nodes/smooth_by_angle.blend/NodeTree/Smooth by Angle")
        mod = next((mod for mod in ob.modifiers if (mod.type == 'NODES') and mod.name.startswith('Smooth by Angle') != -1),None)
    mod['Input_1'] = smooth_angle
    mod.node_group.interface_update(context)
  return mod
def delete_curve_points(ob, points, dissolve=False):
    bpy.ops.curve.select_all(action='DESELECT')
    for sindex, pindex in points:
        spline = ob.data.splines[sindex]
        if spline.type == "POLY":
            spline.points[pindex].select = True
        elif spline.type == "BEZIER":
            spline.bezier_points[pindex].select_control_point = True
        else: return False
    bpy.ops.curve.dissolve_verts() if dissolve else bpy.ops.curve.delete(type='VERT')
def normal_round(n):
    if n - math.floor(n) < 0.5:
        return math.floor(n)
    return math.ceil(n)
def vector_round(v):
  return Vector((normal_round(v[0]),normal_round(v[1]),normal_round(v[2])))
def get_dimensions(ob):
  if ob.type == 'CURVE': return (0,0,0)
  me = ob.data
  coords = np.empty(3 * len(me.vertices))
  me.vertices.foreach_get("co", coords)
  x, y, z = coords.reshape((-1, 3)).T
  mesh_dim = [
          x.max() - x.min(),
          y.max() - y.min(),
          z.max() - z.min()
          ]
  for mod in ob.modifiers:
    if mod.type == 'SCREW':
      mesh_dim[2] += mod.screw_offset
  return mesh_dim
def get_selected_points(ob):
    all_points = []
    saw_point = False
    mw = ob.matrix_world
    for index, spline in enumerate(ob.data.splines):
        if spline.type == 'BEZIER':
          for pindex, point in enumerate(spline.bezier_points):
            if point.select_control_point and (pindex == 0 or pindex == len(spline.bezier_points)-1):
              saw_point = True
              point.handle_left_type = 'ALIGNED'
              point.handle_right_type = 'ALIGNED'
              all_points.append({
                    'p1': mw @ point.co.copy(),
                    'p2': mw @ point.handle_right.copy() if pindex == 0 else mw @ point.handle_left.copy(),
                    'type': spline.type,
                    'spline': index,
                    'index': pindex,
                    'orientation': 'right' if pindex == 0 else 'left',
                })
        elif spline.type == 'POLY':
          for pindex, point in enumerate(spline.points):
            if point.select and (pindex == 0 or pindex == len(spline.points)-1):
              saw_point = True
              all_points.append({
                    'p1': mw @ point.co.copy().to_3d(),
                    'p2': mw @ spline.points[pindex+1].co.copy().to_3d() if pindex == 0 else mw @ spline.points[pindex-1].co.copy().to_3d(),
                    'type': spline.type,
                    'spline': index,
                    'index': pindex,
                })
    if saw_point:
      return all_points
    else:
      return list()
def get_selected_inner_points(self):
    all_points = []
    saw_point = False
    count = 0
    prev_coord = None
    used_index = None
    mw = self.ob.matrix_world
    mwi = self.ob.matrix_world.inverted()
    for index, spline in enumerate(self.ob.data.splines):
        if spline.type == 'BEZIER':
          for pindex, point in enumerate(spline.bezier_points):
            if point.select_control_point:
              saw_point = True
              correct_point = None
              if not used_index:
                for point_index, prev_point in enumerate(self.points):
                  if mwi @ point.co.copy() == prev_point['p1']:
                    correct_point = prev_point['p2']
                    used_index = point_index
              else:
                correct_point = self.points[0 if used_index == 1 else 0]['p2']
                used_index = 0 if used_index == 1 else 0
              all_points.append({
                    'point': point,
                    'coordinate': point.co.copy(),
                    'handle_right': point.handle_right.copy(),
                    'handle_left': point.handle_left.copy(),
                    'correct_point': correct_point,
                    'type': spline.type,
                    'spline': index,
                    'index': pindex
                })
              count += 1
        elif spline.type == 'POLY':
          for pindex, point in enumerate(spline.points):
            if point.select:
              saw_point = True
              all_points.append({
                    'point': point,
                    'coordinate': point.co.copy(),
                    'type': spline.type,
                    'spline': index,
                    'index': pindex
                })
    if saw_point:
      return all_points
    else:
      return list()
def modifiers_by_type(obj, typename):
    return [x for x in obj.modifiers if x.type == typename]
def distance_between(v1, v2):
    return pow(pow(v2[0] - v1[0], 2) + pow(v2[1] - v1[1], 2) + pow(v2[2] - v1[2], 2),0.5)
def get_active_curve():
    ob = bpy.context.view_layer.objects.active
    if ob == None or ob.type != 'CURVE':
        return {'width': None, 'bevel': None, 'length': None, 'active': None, 'res': None, 'bevel_res': None}
    elif ob.type == 'CURVE':
        if len(ob.data.splines) == 0:
          length = 0
        else:
          length = ob.data.splines[0].calc_length()
        return {'width': ob.data.bevel_depth, 'bevel': ob.data.bevel_object, 'length': length, 'active': ob, 'res': ob.data.resolution_u, 'bevel_res': ob.data.bevel_resolution}
def scene_raycast(self, event, batch):
  scene = self.context.scene
  area = self.context.area
  region = area.regions[-1]
  space = area.spaces.active
  rv3d = space.region_3d
  coord = event.mouse_region_x, event.mouse_region_y
  view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
  ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
  success_scene, location_scene, normal_scene, face_index_scene, obj, matrix = scene.ray_cast(self.context.view_layer.depsgraph if GV.is291 else self.context.view_layer, ray_origin, view_vector)
  if success_scene:
    self.scene_raycast = [location_scene, normal_scene, face_index_scene, obj]
  else:
    self.scene_raycast = None
def main(context, event, self, batch):
    scene = context.scene
    area = context.area
    region = area.regions[-1]
    space = area.spaces.active
    rv3d = space.region_3d
    coord = event.mouse_region_x, event.mouse_region_y
    view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    ray_target = ray_origin + view_vector
    def visible_objects_and_duplis():
      """Loop over (object, matrix) pairs (mesh only)"""
      depsgraph = context.evaluated_depsgraph_get()
      for dup in depsgraph.object_instances:
        if dup.is_instance:
          obj = dup.instance_object
          if obj.display_type not in ['WIRE', 'BOUNDS']:
            yield (obj, dup.matrix_world.copy())
        else:
          obj = dup.object
          if obj.display_type not in ['WIRE', 'BOUNDS']:
            yield (obj, obj.matrix_world.copy())
    def obj_ray_cast(obj, matrix):
        """Wrapper for ray casting that moves the ray into object space"""
        matrix_inv = matrix.inverted()
        ray_origin_obj = matrix_inv @ ray_origin
        ray_target_obj = matrix_inv @ ray_target
        ray_direction_obj = ray_target_obj - ray_origin_obj
        success, location, normal, face_index = obj.ray_cast(ray_origin_obj, ray_direction_obj)
        if success:
            return location, normal, face_index
        else:
            return None, None, None
    best_length_squared = -1.0
    best_obj = None
    normal = None
    hit_world = None
    use_hit = None
    use_normal = None
    best_normal = None
    my_face = None
    to_hide = [ob for ob in bpy.context.view_layer.objects
        if not ob.hide_get() and (ob.display_type == 'WIRE' or ob.display_type == 'BOUNDS')]
    success_scene = location_scene = normal_scene = face_index_scene = obj = matrix = None
    if bpy.context.space_data.local_view:
        best_obj = None
        best_matrix = None
        best_normal = None
        best_face_index = None
        best_hit = None
        for obj, matrix in [[ob, ob.matrix_world.copy()] for ob in bpy.context.view_layer.objects if ob.visible_get(view_layer=None)]:
            if obj.type == 'MESH':
                hit, normal, face_index = obj_ray_cast(obj, matrix)
                if hit is not None:
                    hit_world = matrix @ hit
                    length_squared = (hit_world - ray_origin).length_squared
                    if best_obj is None or length_squared < best_length_squared:
                        best_length_squared = length_squared
                        best_obj = obj
                        best_matrix = matrix
                        best_normal = normal @ matrix.inverted()
                        best_face_index = face_index
                        best_hit = hit_world
        success_scene, location_scene, normal_scene, face_index_scene, obj, matrix = [True, best_hit, best_normal, best_face_index, best_obj, best_matrix]
    else:
        for ob in to_hide: ob.hide_set(True)
        success_scene, location_scene, normal_scene, face_index_scene, obj, matrix = scene.ray_cast(context.view_layer.depsgraph if GV.is291 else context.view_layer, ray_origin, view_vector)
        for ob in to_hide: ob.hide_set(False)
    if success_scene:
      hit = matrix.inverted() @ location_scene
      use_hit = hit
      use_normal = normal_scene
      normal = normal_scene @ matrix
      face_index = face_index_scene
      obj_hit = obj
      best_obj = obj
      matrix_hit = matrix
      normal_scene = normal_scene
      depsgraph = context.evaluated_depsgraph_get()
      object_eval = obj_hit.evaluated_get(depsgraph)
      mesh_data = object_eval.to_mesh()
      center2 = matrix @ mesh_data.polygons[face_index].center.copy()
    else:
      hit = None
      normal = None
      face_index = None
      obj_hit = None
      best_obj = None
      matrix_hit = None
      normal_scene = None
      f_center = None
      center = None
      real_center = None
      my_face_center = None
    bobj = ''
    if best_obj is not None:
        bobj = best_obj.name
    if self.is_ctrl:
      try:
        vert = center2
      except:
        vert = None
    else:
      vert = None
    if batch:
      if vert:
        self.vertices.append(vert)
        self.create_batch3d()
        return (vert, use_normal)
      else:
        if location_scene:
          self.vertices.append(location_scene)
          self.create_batch3d()
        return (location_scene, use_normal)
    else:
      if vert:
        return (vert, use_normal)
      else:
        return (location_scene, use_normal)
def get_all_selected_points_of_several_objects(objs):
    all_points = []
    saw_point = False
    for obj in objs:
      mwi = obj.matrix_world
      for index, spline in enumerate(obj.data.splines):
        if spline.type == 'POLY':
          for pindex, point in enumerate(spline.points):
              if point.select:
                  if pindex == 0:
                    saw_point = True
                    all_points.append({
                          'index': pindex,
                          'coord': mwi @ point.co.copy().to_3d(),
                          'back': None,
                          'front': mwi @ spline.points[pindex+1].co.copy().to_3d(),
                          'tilt': point.tilt,
                          'radius': point.radius,
                          'object': obj,
                      })
                  elif pindex == len(spline.points)-1:
                    saw_point = True
                    all_points.append({
                          'index': pindex,
                          'coord': mwi @ point.co.copy().to_3d(),
                          'back': mwi @ spline.points[pindex-1].co.copy().to_3d(),
                          'front': None,
                          'tilt': point.tilt,
                          'radius': point.radius,
                          'object': obj,
                      })
                  else:
                    point.select = False
        elif spline.type == 'BEZIER':
          for pindex, point in enumerate(spline.bezier_points):
              if point.select_control_point:
                  if pindex == 0:
                    saw_point = True
                    all_points.append({
                          'index': pindex,
                          'coord': mwi @ point.co.copy(),
                          'back': None,
                          'front': mwi @ point.handle_right.copy(),
                          'tilt': point.tilt,
                          'radius': point.radius,
                          'object': obj,
                      })
                  elif pindex == len(spline.bezier_points)-1:
                    saw_point = True
                    all_points.append({
                          'index': pindex,
                          'coord': mwi @ point.co.copy(),
                          'back': mwi @ point.handle_left.copy(),
                          'front': None,
                          'tilt': point.tilt,
                          'radius': point.radius,
                          'object': obj,
                      })
                  else:
                    point.select_control_point = False
    if saw_point:
      return all_points
    else:
      raise 'No points were found'
def deselect_all():
    switch_mode('OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
def anything_selected():
  ob = bpy.context.view_layer.objects.active
  objs = bpy.context.selected_objects
  if ob == None:
    return False
  elif len(objs) == 0:
    return False
  else:
    return True
def init_points():
  ob = bpy.context.view_layer.objects.active
  objs = bpy.context.selected_objects
  if ob == None:
    return []
  elif len(objs) == 0:
    return []
  mode = bpy.context.active_object.mode
  if mode == 'EDIT':
    if ob.type != 'CURVE':
      switch_mode('OBJECT')
      return []
    else:
      try:
        points = get_all_selected_points_of_several_objects(objs)
        return convert_points_to_coords(points)
      except Exception as e:
        traceback.print_exc()
        return []
  else:
    return []
def convert_points_to_coords(points):
  coords = []
  for point in points:
    if point['index'] == 0:
      vec = point['front'] - point['coord']
    else:
      vec = point['back'] - point['coord']
    vec.normalize()
    vec *= 2
    coords.append({
        'co': point['coord'].copy(),
        'start': point['coord'].copy() - vec,
        'finish': point['coord'].copy() + vec,
        'radius': point['radius'],
        'tilt': point['tilt'],
        'object': point['object']
      })
  return coords
def edit_curve(curve, val, curve_obj, self, key):
    if not self.finished:
      return
    if key == 'S':
      if val < 0:
        val = 0
        self.events[key]['cur_value'] = 0
        self.cur_value = 0
      curve.data.bevel_depth = val
    elif key == 'D':
      if val < 0.0001:
        val = 0.0001
        self.events[key]['cur_value'] = 0.0001
        self.cur_value = 0.0001
      spline = curve.data.splines[0]
      spline.bezier_points[0].handle_right = spline.bezier_points[0].co + self.init_handles['v1'] * val * self.init_handles['d1']
      spline.bezier_points[0].handle_left = spline.bezier_points[0].co - self.init_handles['v1'] * (val * .66) * self.init_handles['d1']
      spline.bezier_points[1].handle_left = spline.bezier_points[1].co + self.init_handles['v2'] * val * self.init_handles['d2']
      spline.bezier_points[1].handle_right = spline.bezier_points[1].co - self.init_handles['v2'] * (val * .66) * self.init_handles['d2']
      self.curve_length = self.curve.data.splines[0].calc_length()
    elif key == 'F':
      if val < 1:
        val = 1
        self.events[key]['cur_value'] = 1
        self.cur_value = 1
      curve.data.resolution_u = val
    elif key == 'G':
      if val < 0:
        val = 0
        self.events[key]['cur_value'] = 0
        self.cur_value = 0
    elif key == 'V':
      if val < 0:
        val = 0
        self.events[key]['cur_value'] = 0
        self.cur_value = 0
      curve.data.bevel_resolution = val
    elif key == 'H':
      curve.data.twist_mode = val
    elif key == 'E':
      curve.data.splines[0].bezier_points[0].tilt = radians(val)
    elif key == 'W':
      curve.data.splines[0].bezier_points[1].tilt = radians(val)
    elif key == 'sW':
      spline = curve.data.splines[0]
      spline.bezier_points[0].co = self.curve.matrix_world.inverted() @ self.init_points['p1'] + self.init_handles['v1'] * val
      spline.bezier_points[0].handle_right = spline.bezier_points[0].co + self.init_handles['v1'] * self.init_handles['d1'] * self.events['D']['cur_value']
    elif key == 'sE':
      spline = curve.data.splines[0]
      spline.bezier_points[1].co = self.curve.matrix_world.inverted() @ self.init_points['p2'] + self.init_handles['v2'] * val
      spline.bezier_points[1].handle_left = spline.bezier_points[1].co + self.init_handles['v2'] * self.init_handles['d2'] * self.events['D']['cur_value']
    elif key == 'T':
      self.pickers['A']['object'].scale = val,val,val
def edit_curves(self, key):
  for ob in self.objects:
    if key == 'H':
      ob.data.twist_mode = self.enums['H']['items'][self.enums['H']['cur_value']][0]
    elif key == 'F':
      if self.events[key]['cur_value'] < 1:
        self.events[key]['cur_value'] = 1
        self.cur_value = 1
      ob.data.resolution_u = self.events['F']['cur_value']
    elif key == 'S':
      if self.events[key]['cur_value'] < 0:
        self.events[key]['cur_value'] = 0
        self.cur_value = 0
      ob.data.bevel_depth = self.events['S']['cur_value']
    elif key == 'V':
      if self.events[key]['cur_value'] < 1:
        self.events[key]['cur_value'] = 1
        self.cur_value = 1
      ob.data.bevel_resolution = self.events['V']['cur_value']
    elif key == 'C':
      ob.data.use_fill_caps = self.bools['C']['status']
    elif key == 'T' and 'A' in self.pickers and self.pickers['A']['object']:
      s = self.events[key]['cur_value']
      self.pickers['A']['object'].scale = s,s,s
def print_attr(item):
    for attr in dir(item):
        pass
def get_extrude_length(self):
  ores, mode, depth, bev_object = self.init_curve_values.values()
  if mode == 'ROUND':
      return depth
  elif mode == 'OBJECT':
      dims = [dim for dim in bev_object.dimensions if dim != 0]
      return sum(dims)/len(dims)
def normalize_point(point, strength, multiplier, invert):
  sign = 1 if invert else -1
  return [point[0], point[0] - (strength * point[1] * multiplier * sign)]
def build_curve(coords, strength, bevel, use_profile, profile, multiplier, pdata, res, twist, wire, use_as_profile, tilt1, tilt2, bevel_res):
    curve_name = "cable"
    curveData = bpy.data.curves.new(curve_name, type='CURVE')
    curveData.dimensions = '3D'
    curve = bpy.data.objects.new(curve_name, curveData)
    scn = bpy.context.scene
    scn.collection.objects.link(curve)
    spline = curveData.splines.new('BEZIER')
    spline.bezier_points.add(1)
    try:
        a = spline.bezier_points[0]
        b = spline.bezier_points[1]
        spline.bezier_points[0].co = coords['point1'][0]
        spline.bezier_points[0].handle_left = coords['point1'][1]
        spline.bezier_points[0].handle_right = coords['point1'][1]
        spline.bezier_points[0].handle_right_type = 'ALIGNED'
        spline.bezier_points[0].handle_left_type = 'ALIGNED'
        if coords['created_from_init1'] and coords['created_from_init2']:
          spline.bezier_points[0].tilt = radians(tilt1)
          spline.bezier_points[0].radius = pdata['point1'][1]
          spline.bezier_points[1].tilt = radians(tilt2)
          spline.bezier_points[1].radius = pdata['point2'][1]
        elif coords['created_from_init1']:
          spline.bezier_points[0].tilt = radians(tilt1)
          spline.bezier_points[0].radius = pdata['point1'][1]
          spline.bezier_points[1].tilt = radians(tilt2)
          spline.bezier_points[1].radius = pdata['point1'][1]
        spline.bezier_points[1].co = coords['point2'][0]
        spline.bezier_points[1].handle_left = coords['point2'][1]
        spline.bezier_points[1].handle_right = coords['point2'][1]
        spline.bezier_points[1].handle_right_type = 'ALIGNED'
        spline.bezier_points[1].handle_left_type = 'ALIGNED'
        curve.data.bevel_depth = bevel
        curve.data.resolution_u = res
        curve.data.bevel_resolution = bevel_res
        curve.data.twist_mode = twist
        curve.data.twist_smooth = 8
    except:
        traceback.print_exc()
    if GV.is291 and profile: curve.data.bevel_mode = 'OBJECT'
    curve.data.bevel_object = profile
    curve.show_wire = wire
    return curve
def linear(X, A, B, C, D, cut=False):
    Y = (X - A) / (B - A) * (D - C) + C
    if cut:
      if Y > D: Y = D
      if Y < C: Y = C
    return Y
def get_active(context=bpy.context):
  return context.view_layer.objects.active
def set_active(ob, context=bpy.context):
  context.view_layer.objects.active = ob
def get_selected(context=bpy.context):
  return context.selected_objects
def super_select(obj, context=bpy.context, active=None, deselect=True):
  if deselect:
    for ob in bpy.data.objects:
        ob.select_set(False)
  if type(obj) == list:
    for ob in obj:
        ob.select_set(True)
    context.view_layer.objects.active = active or obj[0]
  elif type(obj) == bpy.types.Object:
    obj.select_set(True)
    context.view_layer.objects.active = active or obj
  else:
    pass
def super_remove(obj, context=bpy.context):
  if type(obj) == list:
    for ob in obj:
        bpy.data.objects.remove(ob, do_unlink=True)
  elif type(obj) == bpy.types.Object:
    bpy.data.objects.remove(obj, do_unlink=True)
def set_active(ob, context=bpy.context):
  context.view_layer.objects.active = ob
def add_point(ob, context, num):
    ob.show_wire = False
    if num == 0:
      return False
    bpy.ops.object.select_all(action='DESELECT')
    context.view_layer.objects.active = ob
    ob.select_set(True)
    switch_mode('EDIT')
    bpy.ops.curve.select_all(action='SELECT')
    bpy.ops.curve.subdivide(number_cuts=num)
    switch_mode('OBJECT')
def separate_curve(curve):
  switch_mode('EDIT')
  bpy.ops.curve.select_all(action='DESELECT')
  for spline in reversed(curve.data.splines):
    if spline.type == 'BEZIER':
      spline.bezier_points[0].select_control_point = True
    elif spline.type == 'POLY':
      spline.points[0].select = True
    bpy.ops.curve.select_linked()
    bpy.ops.curve.separate()
  switch_mode('OBJECT')
  return [o for o in bpy.context.selected_objects if o != curve]
def finish_clicks(self):
  p1 = Vector(self.curve_obj['point1'][0])
  p2 = Vector(self.curve_obj['point2'][0])
  self.strength = (p2 - p1).length / 2
  self.events['D']['cur_value'] = 1
  if anything_selected():
    deselect_all()
  if not self.curve_obj['created_from_init1']:
    self.curve_obj['point1'] = normalize_point(self.curve_obj['point1'], self.strength, self.events['D']['cur_value'], False)
  if not self.curve_obj['created_from_init2']:
      self.curve_obj['point2'] = normalize_point(self.curve_obj['point2'], self.strength, self.events['D']['cur_value'], True)
  self.curve = build_curve(self.curve_obj,self.strength,self.events['S']['cur_value'],None,self.pickers['A']['object'],self.events['D']['cur_value'], self.additional_data,self.events['F']['cur_value'], self.enums['H']['items'][self.enums['H']['cur_value']][0],self.bools['X']['status'], None, self.events['W']['cur_value'],self.events['E']['cur_value'],self.events['V']['cur_value'])
  spline = self.curve.data.splines[0]
  v1 = spline.bezier_points[0].handle_right - spline.bezier_points[0].co
  v1.normalize()
  v2 = spline.bezier_points[1].handle_left - spline.bezier_points[1].co
  v2.normalize()
  spline.bezier_points[0].handle_right = spline.bezier_points[0].co + v1 * self.strength * self.events['D']['cur_value']
  spline.bezier_points[1].handle_left = spline.bezier_points[1].co - v2 * self.strength * self.events['D']['cur_value']
  if 'C' in self.bools: self.curve.data.use_fill_caps = self.bools['C']['status']
  self.curve_length = self.curve.data.splines[0].calc_length()
  self.init_handles = {
    'st': self.strength,
    'v1': v1,
    'v2': v2,
    'd1': distance_between( spline.bezier_points[0].co, spline.bezier_points[0].handle_right) / self.strength,
    'd2': distance_between( spline.bezier_points[1].co, spline.bezier_points[1].handle_left) / self.strength,
  }
  self.init_points = {
    'p1': spline.bezier_points[0].co.copy(),
    'p2': spline.bezier_points[1].co.copy(),
  }
  if self.events['sW']['cur_value'] != 0:
    spline.bezier_points[0].co = self.curve.matrix_world.inverted() @ self.init_points['p1'] + self.init_handles['v1'] * self.events['sW']['cur_value']
    spline.bezier_points[0].handle_right = spline.bezier_points[0].co + self.init_handles['v1'] * self.init_handles['d1'] * self.events['D']['cur_value']
  if self.events['sE']['cur_value'] != 0:
    spline.bezier_points[1].co = self.curve.matrix_world.inverted() @ self.init_points['p2'] + self.init_handles['v2'] * self.events['sE']['cur_value']
    spline.bezier_points[1].handle_left = spline.bezier_points[1].co + self.init_handles['v2'] * self.init_handles['d2'] * self.events['D']['cur_value']
  self.events['D']['cur_value'] = self.strength
  self.init_ten = self.strength
  self.finished = True
  self.actions['Q']['status'] = True
  pivot_to_spline_center(self.curve, self.context)
def curves_from_selected(self, context):
  curves = []
  strength = 21474836
  for index, pair in enumerate(self.coord_pairs):
    curve_name = "cable_" + str(index)
    curveData = bpy.data.curves.new(curve_name, type='CURVE')
    curveData.dimensions = '3D'
    curve = bpy.data.objects.new(curve_name, curveData)
    scn = context.scene
    scn.collection.objects.link(curve)
    spline = curveData.splines.new('BEZIER')
    spline.bezier_points.add(1)
    vec = pair[1] - pair[0]
    vec.normalize()
    vec_dist = distance_between(pair[0], pair[1])
    if strength > vec_dist:
      strength = vec_dist
    spline.bezier_points[0].co = pair[0]
    spline.bezier_points[0].handle_right_type = 'ALIGNED'
    spline.bezier_points[0].handle_left_type = 'ALIGNED'
    spline.bezier_points[0].handle_left = pair[0] - vec * vec_dist/5
    spline.bezier_points[0].handle_right = pair[0] + vec * vec_dist/5
    spline.bezier_points[1].co = pair[1]
    spline.bezier_points[1].handle_right_type = 'ALIGNED'
    spline.bezier_points[1].handle_left_type = 'ALIGNED'
    spline.bezier_points[1].handle_left = pair[1] - vec * vec_dist/5
    spline.bezier_points[1].handle_right = pair[1] + vec * vec_dist/5
    curves.append(curve)
  return [curves, strength]
def remove_cables(self):
  for ob in self.objects:
    bpy.data.curves.remove(ob.data, do_unlink=True)
def init_curve_points(self):
  self.initial_curve_points = []
  for curve in self.objects:
    points = curve.data.splines[0].bezier_points
    self.initial_curve_points.append([
      points[0].handle_left.copy(),
      points[0].handle_right.copy(),
      points[1].handle_left.copy(),
      points[1].handle_right.copy()
      ])
def set_curves_from_selected(self, context, key):
  vec = Vector((0,0,-1))
  for index, curve in enumerate(self.objects):
    if key == 'N':
      ten_delta = .5 - random()
      self.events['D']['cur_value'] = self.strength = self.init_ten + self.init_ten * ten_delta * self.random_tension * 2
    points = curve.data.splines[0].bezier_points
    points[0].handle_left = self.initial_curve_points[index][0] - vec * self.strength
    points[0].handle_right = self.initial_curve_points[index][1] + vec * self.strength
    points[1].handle_left = self.initial_curve_points[index][2] + vec * self.strength
    points[1].handle_right = self.initial_curve_points[index][3] - vec * self.strength
def new_bezier_point(p0, p0hr, p1hl, p1, t):
    t1 = p0 + (p0hr - p0) * t
    t2 = p0hr + (p1hl - p0hr) * t
    t3 = p1hl + (p1 - p1hl) * t
    p2hl = t1 + (t2 - t1) * t
    p2hr = t2 + (t3 - t2) * t
    p2 = p2hl + (p2hr - p2hl) * t
    return [t1, p2hl, p2, p2hr, t3]
def create_new_bezier_point(t, ob, spline, pindex):
  bpy.ops.curve.select_all(action='DESELECT')
  p0 = ob.data.splines[spline].bezier_points[pindex]
  p1 = ob.data.splines[spline].bezier_points[pindex + 1]
  p0.select_control_point = True
  p1.select_control_point = True
  p0co = p0.co
  p0hr = p0.handle_right
  p1co = p1.co
  p1hl = p1.handle_left
  new_data = new_bezier_point(p0co, p0hr, p1hl, p1co, t)
  bpy.ops.curve.subdivide(1)
  p2 = ob.data.splines[spline].bezier_points[pindex+1]
  p0 = ob.data.splines[spline].bezier_points[pindex]
  p1 = ob.data.splines[spline].bezier_points[pindex+2]
  p0.handle_right_type = 'ALIGNED'
  p0.handle_right = new_data[0]
  p1.handle_left_type = 'ALIGNED'
  p1.handle_left = new_data[4]
  p2.co = new_data[2]
  p2.handle_left_type = 'ALIGNED'
  p2.handle_right_type = 'ALIGNED'
  p2.handle_left = new_data[1]
  p2.handle_right = new_data[3]
  bpy.ops.curve.select_all(action='DESELECT')
  p2.select_right_handle = True
  p2.select_left_handle = True
  p2.select_control_point = True
def duplicate_object(ob, link=False):
    ob_copy = ob.copy()
    if ob.type != 'EMPTY':
      if link:
          ob_copy.data = ob.data
      else:
          ob_copy.data = ob.data.copy()
    ob.users_collection[0].objects.link(ob_copy)
    return ob_copy
def clone_connectors(curves, self):
  clones = []
  clone_name =self.connector.name
  for curve in curves:
    for index, point in enumerate(curve['points']):
      connector_clone = self.connector.copy()
      scn = bpy.context.scene
      if index == 0:
        self.connector_data = self.connector.data
      connector_clone.data = self.connector_data
      scn.collection.objects.link(connector_clone)
      connector_clone.name = clone_name + '_' + ('%02d' % (index + 1))
      if connector_clone.parent:
        connector_clone.parent = None
      vec = point['p2'] - point['p1']
      vecflip = point['p1'] - point['p2']
      vec.normalize()
      clones.append({'obj': connector_clone, 'point': point, 'vec': vec, 'vecflip': vecflip, 'parent': curve['ob']})
  return clones
def apply_curve_error(self, key, val):
  bpy.ops.curve.draw(error_threshold=0.140555, wait_for_input=False)
def set_segment(self):
  self.context.view_layer.objects.active = self.segment
  if self.segment.parent != self.ob:
    self.segment.location = self.ob.location
    self.segment.rotation_euler = self.ob.rotation_euler
  curve_found = False
  curve_mod = None
  displ_found = False
  displ_mod = None
  arr_found = False
  arr_mod = None
  for mod in self.segment.modifiers:
    if mod.type == 'DISPLACE':
      displ_found = True
      displ_mod = mod
    elif mod.type == 'CURVE':
      curve_found = True
      curve_mod = mod
    elif mod.type == 'ARRAY':
      arr_found = True
      arr_mod = mod
  if not displ_found:
    displ_mod = self.segment.modifiers.new(name='Displace',type='DISPLACE')
    displ_mod.strength = 0
  if not curve_found:
    curve_mod = self.segment.modifiers.new(name='Curve',type='CURVE')
  if arr_found:
    arr_mod.use_relative_offset = False
    arr_mod.use_constant_offset = True
    arr_mod.relative_offset_displace[0] = 0
    arr_mod.relative_offset_displace[1] = 0
  displ_mod.direction = 'Z'
  displ_mod.show_expanded = False
  curve_mod.deform_axis = 'POS_Z'
  curve_mod.object = self.ob
  curve_mod.show_expanded = False
  count = 0
  while self.segment.modifiers.find('Curve') != 0:
    count += 1
    bpy.ops.object.modifier_move_up(modifier='Curve')
    if count > 10: break
  count = 0
  if arr_found:
    while self.segment.modifiers.find('Array') != 0:
      count += 1
      bpy.ops.object.modifier_move_up(modifier='Array')
      if count > 10: break
  count = 0
  while self.segment.modifiers.find('Displace') != 0:
    count += 1
    bpy.ops.object.modifier_move_up(modifier='Displace')
    if count > 10: break
  if self.segment.parent != self.ob and self.parent_connectors:
    self.context.view_layer.objects.active = self.ob
    try:
      mw_copy = self.segment.matrix_world.copy()
      self.segment.parent = self.ob
      self.segment.matrix_world = mw_copy
    except Exception as e:
      self.report({'ERROR'}, str(e))
  return (displ_mod, curve_mod, arr_mod)
def position_clones(self):
  for ob in bpy.data.objects:
        ob.select_set(False)
  for clone in self.clones:
    bpy.context.view_layer.objects.active = clone['obj']
    clone['obj'].select_set(True)
    clone['r_mode'] = clone['obj'].rotation_mode
    clone['obj'].rotation_mode = 'QUATERNION'
    clone['obj'].rotation_quaternion = clone['vec'].to_track_quat('Z','Y') if not self.flip else clone['vecflip'].to_track_quat('Z','Y')
    clone['obj'].location = clone['point']['p1']
    clone['loc'] = clone['point']['p1']
    clone['obj'].data.update()
    clone['mat'] = clone['obj'].matrix_world.copy()
    for ob in bpy.data.objects:
        ob.select_set(False)
def pivot_to_selection(self, context):
  cur_location = context.scene.cursor.location.copy()
  bpy.ops.view3d.snap_cursor_to_selected()
  bpy.ops.object.mode_set(mode='OBJECT')
  bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
  context.scene.cursor.location = cur_location
def reposition_clones(self):
  for clone in self.clones:
    clone['obj'].rotation_mode = 'QUATERNION'
    clone['obj'].location = clone['loc'] + clone['vec'] * self.offset
    clone['obj'].rotation_quaternion = clone['vec'].to_track_quat('Z','Y') if not self.flip else clone['vecflip'].to_track_quat('Z','Y')
def scale_clones(self):
  for clone in self.clones:
    clone['obj'].scale = self.events['T']['cur_value'],self.events['T']['cur_value'],self.events['T']['cur_value']
def edit_connector_spline(self):
  for curve in self.selected_points:
    mwi = curve['ob'].matrix_world.inverted()
    for point in curve['points']:
      if point['type'] == 'POLY':
        vec = point['p2'] - point['p1']
        vec.normalize()
        p = point['p1'] + vec * self.offset_point
        curve['ob'].data.splines[point['spline']].points[point['index']].co = (mwi @ p).to_4d()
      elif point['type'] == 'BEZIER':
        vec = point['p2'] - point['p1']
        vec.normalize()
        p = point['p1'] + vec * self.offset_point
        curve['ob'].data.splines[point['spline']].bezier_points[point['index']].co = mwi @ p
def filter_selected_hooks():
  objs = bpy.context.selected_objects
  found_objs = {
    'curves': [],
    'hooks': []
  }
  for ob in objs:
    if ob.type == 'CURVE':
      found_objs['curves'].append(ob)
    elif ob.type == 'EMPTY' or ob.type == 'MESH':
      found_objs['hooks'].append(ob)
  return found_objs
def scale_matrix(vec=Vector((1,1,1))):
    m = Matrix()
    m[0][0] *= vec.x
    m[0][1] *= vec.x
    m[0][2] *= vec.x
    m[0][3] *= vec.x
    m[1][0] *= vec.y
    m[1][1] *= vec.y
    m[1][2] *= vec.y
    m[1][3] *= vec.y
    m[2][0] *= vec.z
    m[2][1] *= vec.z
    m[2][2] *= vec.z
    m[2][3] *= vec.z
    return m
def local_mw_rotate(axis, mw, angle):
    dec = mw.decompose()
    scale_mat = scale_matrix(dec[2])
    mw_t = Matrix.Translation(dec[0])
    angle = radians(angle)
    rotmat = Matrix.Rotation(angle, 4, axis)
    localZ = Vector((mw[0][2],mw[1][2],mw[2][2])).normalized()
    globalX = Vector((0,1,0)).cross(localZ).normalized()
    globalY = localZ.cross(globalX).normalized()
    unrotated_matrix = Matrix((globalX, globalY, localZ)).to_4x4()
    unrotated_inverted = unrotated_matrix.inverted()
    return mw_t @ unrotated_inverted @ rotmat @ scale_mat
def finish_clones(self):
  for index, clone in enumerate(self.clones):
    if self.bools['H']['status']:
      super_select(clone['parent'], self.context)
      spline_index = clone['point']['spline'] + 1
      hook_name = f'Hook Start spline {spline_index}' if clone['point']['index'] == 0 else f'Hook End spline {spline_index}'
      for mod in clone['parent'].modifiers:
        if mod.name == hook_name:
          clone['parent'].modifiers.remove(mod)
      hook = clone['parent'].modifiers.new(name = hook_name, type = 'HOOK')
      hook.object = clone['obj']
      hook.show_in_editmode = True
      switch_mode('EDIT')
      bpy.ops.curve.select_all(action='DESELECT')
      if clone['parent'].data.splines[clone['point']['spline']].type == 'BEZIER':
        clone['parent'].data.splines[clone['point']['spline']].bezier_points[clone['point']['index']].select_control_point = True
        clone['parent'].data.splines[clone['point']['spline']].bezier_points[clone['point']['index']].select_right_handle = True
        clone['parent'].data.splines[clone['point']['spline']].bezier_points[clone['point']['index']].select_left_handle = True
        bpy.ops.object.hook_assign(modifier = hook_name)
      switch_mode('OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = clone['obj']
    clone['obj'].select_set(True)
    clone['obj'].rotation_mode = clone['r_mode']
    if self.parent_connectors:
      clone['parent'].select_set(True)
      bpy.context.view_layer.objects.active = clone['parent']
      try:
        bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
      except Exception as e:
        self.report({'ERROR'}, str(e))
  bpy.ops.object.select_all(action='DESELECT')
  for clone in self.clones:
    clone['obj'].select_set(True)
    bpy.context.view_layer.objects.active = clone['obj']
  if self.bools['R']['status']:
    bpy.data.objects.remove(self.connector, do_unlink=True)
def creat_map(ob):
    arr = []
    last_value = 0
    count = 0
    for index, spline in enumerate(ob.data.splines):
        temp = []
        for pindex, point in enumerate(spline.bezier_points):
            temp.append(pindex * 100 + index + count * 100)
        arr.append(temp)
        count += len(arr[-1]) - 1
    return arr
def get_t(ob, search_index):
    t = -1
    search_t = -32000000
    spline_i = 0
    p_i = 0
    map = creat_map(ob)
    for sindex, spline in enumerate(map):
        for pindex, point in enumerate(spline):
            if search_index >= point:
                search_t = point
                t = (search_index - search_t)/100
                spline_i = sindex
                p_i = pindex
    return t, spline_i, p_i
def rotate_connector(self, val_deg, deg):
  if self.prev_mouse != val_deg:
      self.prev_mouse = val_deg
      for clone in self.clones:
        clone['obj'].rotation_mode = 'XYZ'
        if self.actual_val < 0:
          self.prev_sign = -1
          clone['obj'].rotation_euler.rotate_axis("Z", radians(-15))
        elif self.actual_val > 0:
          self.prev_sign = 1
          clone['obj'].rotation_euler.rotate_axis("Z", radians(15))
        else:
          clone['obj'].rotation_euler.rotate_axis("Z", radians(15*self.prev_sign))
        self.events['F']['cur_value'] = degrees(clone['obj'].rotation_euler[2])
def calc_mousemove_delta(value):
  if abs(value) < 0.01: return 0.02
  elif abs(value) < 0.1: return 0.08
  elif abs(value) < 0.3: return 0.2
  elif abs(value) < 0.6: return 0.4
  elif abs(value) > 3: return 2
  elif abs(value) > 7: return 4
  else: return 1
def is_mesh_cable(ob):
  curve_found = False
  curve_mod = None
  arr_found = False
  arr_mod = None
  displ_found = False
  displ_mod = None
  solid_found = False
  solid_mod = None
  caps = list()
  existing_array = dict()
  for mod in ob.modifiers:
    if mod.type == 'ARRAY':
      arr_found = True
      arr_mod = mod
      caps.append(arr_mod.start_cap)
      caps.append(arr_mod.end_cap)
      if arr_mod.use_relative_offset and arr_mod.relative_offset_displace[2] != 0:
        existing_array['use_relative_offset'] = arr_mod.relative_offset_displace[2]
      if arr_mod.use_constant_offset and arr_mod.constant_offset_displace[2] != 0:
        existing_array['use_constant_offset'] = arr_mod.constant_offset_displace[2]
      if arr_mod.use_object_offset and arr_mod.offset_object != None:
        existing_array['use_object_offset'] = arr_mod.offset_object
    elif mod.type == 'CURVE':
      curve_found = True
      curve_mod = mod
    elif mod.type == 'DISPLACE':
      displ_found = True
      displ_mod = mod
    elif mod.type == 'SOLIDIFY':
      solid_found = True
      solid_mod = mod
  if arr_found and curve_found:
    return (True, arr_mod, curve_mod, displ_mod, caps, existing_array, solid_mod)
  if arr_found:
    ob.modifiers.remove(arr_mod)
  if curve_found:
    ob.modifiers.remove(curve_mod)
  if displ_found:
    ob.modifiers.remove(displ_mod)
  return (False, None, None, None, caps, existing_array, solid_mod)
def geo_sort_objects(objs, aob=None):
  saw_curve = 0
  saw_geo = 0
  parsed_objects = {
  'curves': [],
  'ob': None,
  'cap_start': None,
  'cap_end': None
  }
  for ob in objs:
    if ob.type == 'CURVE':
      saw_curve += 1
      parsed_objects['curves'].append(ob)
    elif ob.type == 'MESH':
      if ob.name.endswith('_pos') or ob.name.find('DecapObjA') != -1:
        parsed_objects['cap_end'] = ob
      elif ob.name.endswith('_neg') or ob.name.find('DecapObjB') != -1:
        parsed_objects['cap_start'] = ob
      else:
        saw_geo += 1
        parsed_objects['ob'] = ob
  if saw_curve > 0 and saw_geo == 0 and len(objs) > 1:
    parsed_objects = {
    'curves': [],
    'ob': None,
    'cap_start': None,
    'cap_end': None
    }
    if aob:
      for ob in objs:
        if ob != aob:
          parsed_objects['curves'].append(ob)
        else:
          parsed_objects['ob'] = ob
  elif saw_curve == 0:
    raise Exception('No Curves were selected, aborting')
  elif saw_geo == 0:
    raise Exception('No Meshes were selected, aborting')
  elif saw_geo > 1:
    raise Exception('Please select only one Mesh object (' +str(saw_geo)+ ' were selected), aborting')
  return parsed_objects
def pivot_to_spline_center(ob, context):
  super_select(ob, context)
  cursor_location = context.scene.cursor.location.copy()
  centers = []
  for spline in ob.data.splines:
    if spline.type == 'BEZIER' and len(spline.bezier_points):
      points = sum((point.co for point in spline.bezier_points), Vector());
      centers.append(points/len(spline.bezier_points))
    elif spline.type == 'POLY':
      points = sum((point.co for point in spline.points), Vector().to_4d());
      centers.append(points/len(spline.points))
  try:
    center = (sum(centers, Vector())/len(centers))
    context.scene.cursor.location = center
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
    context.scene.cursor.location = cursor_location
  except:
    pass
def check_edges(ob, context):
  switch_mode('OBJECT')
  super_select(ob, context)
  edges = [x.select for x in ob.data.edges]
  switch_mode('EDIT')
  return True in edges
def create_cable_from_edge(ob, context):
  bpy.ops.mesh.duplicate()
  bpy.ops.mesh.separate(type='SELECTED')
  switch_mode('OBJECT')
  if len(context.selected_objects) < 2:
      return False
  new_cable = context.selected_objects[1]
  new_cable.name = ob.name + " cable"
  super_select(new_cable, context)
  bpy.ops.object.convert(target='CURVE')
  switch_mode('EDIT')
  bpy.ops.curve.select_all(action='SELECT')
  bpy.ops.curve.spline_type_set(type='BEZIER')
  bpy.ops.curve.handle_type_set(type='AUTOMATIC')
  bpy.ops.curve.handle_type_set(type='ALIGNED')
  switch_mode('OBJECT')
  bpy.ops.object.shade_smooth()
  return new_cable
def mouse_to_plane_2000(coord, context):
  area = context.area
  region = area.regions[-1]
  space = area.spaces.active
  rv3d = space.region_3d
  view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
  ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
  origin = Vector((0,0,0))
  vs = [Vector((0,0,1)),Vector((1,0,0)),Vector((0,1,0))]
  for index, v in enumerate(vs):
    intersection = intersect_line_plane(ray_origin, ray_origin + view_vector, origin, v)
    if abs(v.dot(view_vector)) > 1.5e-06:
      return intersection
  return origin
def get_first_curve_point_on_plane_distance(context):
  area = context.area
  region = area.regions[-1]
  space = area.spaces.active
  rv3d = space.region_3d
  if rv3d.view_perspective != 'ORTHO':
    return
  viewport_region = context.region
  viewport_region_data = context.space_data.region_3d
  viewport_matrix = viewport_region_data.view_matrix.inverted()
  vmd = viewport_matrix.decompose()
  viewport_origin = vmd[0]
  view_vector = viewport_region_data.view_matrix[2].to_3d()
  vp_vec_direction = (viewport_origin-view_vector).normalized()
  mw = context.view_layer.objects.active.matrix_world
  data = context.view_layer.objects.active.data
  spline = data.splines[len(data.splines)-1]
  if spline.type == 'POLY':
    point = mw @ spline.points[0].co.to_3d()
  elif spline.type == 'BEZIER':
    point = mw @ spline.bezier_points[0].co
  dist_to_plane = distance_point_to_plane(point, context.scene.cursor.location, -view_vector)
  if dist_to_plane < 1e-4:
    return
  if spline.type == 'BEZIER':
    for point in spline.bezier_points:
      point.co += view_vector * dist_to_plane
      point.handle_left += view_vector * dist_to_plane
      point.handle_right += view_vector * dist_to_plane
  elif spline.type == 'POLY':
    for point in spline.points:
      point.co += (view_vector * dist_to_plane).to_4d()
def mouse_to_plane(mouse_pos, context):
  viewport_region = context.region
  viewport_region_data = context.space_data.region_3d
  viewport_matrix = viewport_region_data.view_matrix.inverted()
  ray_start = viewport_matrix.to_translation()
  ray_depth = viewport_matrix @ Vector((0,0,-100000))
  ray_end = view3d_utils.region_2d_to_location_3d(viewport_region, viewport_region_data, mouse_pos, ray_depth )
  point_1 = Vector((0,0,0))
  point_2 = Vector((0,1,0))
  point_3 = Vector((1,0,0))
  position_on_grid = mathutils.geometry.intersect_ray_tri(point_1,point_2,point_3,ray_end,ray_start,False )
  return position_on_grid
def create_empty(name='Whatever', loc=Vector((0,0,0))):
    empty = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(empty)
    empty.location = loc
def create_mesh_datablock(self, context):
    new_meshes = []
    remove_meshes_data = []
    self.primo_verts = list()
    for (index, ob) in enumerate(self.mesh_objects):
        switch_mode('OBJECT')
        temp_dup = duplicate_object(ob)
        super_select(temp_dup, context)
        switch_mode('EDIT')
        bpy.ops.mesh.subdivide(number_cuts=1)
        mw = temp_dup.matrix_world
        me = temp_dup.data
        bm = bmesh.from_edit_mesh(me)
        for v in bm.verts:
            if v.select:
                self.primo_verts.append([mw @ v.co, mw @ v.normal, mw.inverted()])
        switch_mode('OBJECT')
        super_remove(temp_dup, context)
        super_select(ob, context)
        switch_mode('EDIT')
        bpy.ops.mesh.duplicate()
        bpy.ops.mesh.separate(type='SELECTED')
        switch_mode('OBJECT')
        if len(context.selected_objects) < 2:
            return False
        new_cable_mesh = context.selected_objects[1]
        new_cable_mesh.name = ob.name + ' cable ' + str(index + 1)
        super_select(new_cable_mesh, context)
        remove_meshes_data.append(new_cable_mesh.data)
        new_meshes.append(new_cable_mesh)
    context.view_layer.objects.active = new_meshes[0]
    for mesh in new_meshes:
      mesh.select_set(True)
    if len(new_meshes) > 1:
        bpy.ops.object.join()
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    switch_mode('EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.subdivide(number_cuts=1)
    switch_mode('OBJECT')
    for mesh_data in remove_meshes_data:
      if mesh_data.users == 0:
        bpy.data.meshes.remove(mesh_data, do_unlink=True)
    result_cable_mesh = context.view_layer.objects.active
    return [result_cable_mesh.data, result_cable_mesh.matrix_world.copy(), result_cable_mesh.name, result_cable_mesh.users_collection[0]]
def create_mesh_from_datablock(block):
    ob_mesh, ob_mw, ob_name, ob_col = block
    ob = bpy.data.objects.new(ob_name, ob_mesh)
    ob_col.objects.link(ob)
    ob.matrix_world = ob_mw
    return ob
def create_cables_from_edge(self, context):
  super_select(self.cable_mesh, context)
  bpy.ops.object.convert(target='CURVE')
  lens = [len(spline.points) for spline in self.cable_mesh.data.splines]
  bpy.ops.object.convert(target='MESH')
  self.vert_normals = list()
  mw = self.cable_mesh.matrix_world
  mwi = self.cable_mesh.matrix_world.inverted()
  for vert in self.cable_mesh.data.vertices:
    for pindex, primo_vert in enumerate(self.primo_verts):
      if (mw @ vert.co - primo_vert[0]).length_squared < 1e-10:
        self.vert_normals.append((primo_vert[2] @ primo_vert[1]).normalized())
  new_arr = list()
  for l in reversed(lens):
      new_arr.append(self.vert_normals[-l:])
      del self.vert_normals[-l:]
  self.vert_normals = [el for sub in new_arr for el in sub]
  verts = [vert.co.to_4d() for vert in self.cable_mesh.data.vertices]
  bpy.ops.object.convert(target='CURVE')
  switch_mode('EDIT')
  bpy.ops.curve.select_all(action='SELECT')
  bpy.ops.curve.spline_type_set(type='BEZIER')
  bpy.ops.curve.handle_type_set(type='AUTOMATIC')
  bpy.ops.curve.handle_type_set(type='ALIGNED')
  normals_to_remove = list()
  add_spline_len = 0
  if self.from_centers:
      bpy.ops.curve.select_all(action='DESELECT')
      for spline in self.cable_mesh.data.splines:
          if len(spline.bezier_points) > 3:
              for index, point in enumerate(spline.bezier_points[1:-1]):
                  i = index + 1
                  if i % 2 == 0:
                      spline.bezier_points[i].select_control_point = True
                      normals_to_remove.append(i + add_spline_len)
          elif len(spline.bezier_points) == 3:
              spline.bezier_points[1].select_control_point = True
              normals_to_remove.append(1 + add_spline_len)
          add_spline_len += len(spline.bezier_points)
      bpy.ops.curve.dissolve_verts()
  else:
    bpy.ops.curve.select_all(action='DESELECT')
    for spline in self.cable_mesh.data.splines:
        if len(spline.bezier_points) > 3:
            for index, point in enumerate(spline.bezier_points):
                if index % 2 == 1:
                    spline.bezier_points[index].select_control_point = True
                    normals_to_remove.append(index + add_spline_len)
        elif len(spline.bezier_points) == 3:
            spline.bezier_points[1].select_control_point = True
            normals_to_remove.append(1 + add_spline_len)
        add_spline_len += len(spline.bezier_points)
    bpy.ops.curve.dissolve_verts()
    bpy.ops.curve.select_all(action='SELECT')
    bpy.ops.curve.handle_type_set(type='AUTOMATIC')
    bpy.ops.curve.handle_type_set(type='ALIGNED')
  for normal in reversed(normals_to_remove):
    del self.vert_normals[normal]
  switch_mode('OBJECT')
  bpy.ops.object.shade_smooth()
  self.cable_mesh.data.resolution_u = self.res
  self.cable_mesh.data.bevel_resolution = self.bevel_res
  self.cable_mesh.data.bevel_depth = self.width
  if GV.is291: self.cable_mesh.data.use_fill_caps = self.fill_caps
  self.init_points = dict()
  for sindex, spline in enumerate(self.cable_mesh.data.splines):
    self.init_points[str(sindex)] = dict()
    for pindex, point in enumerate(spline.bezier_points):
      self.init_points[str(sindex)][str(pindex)] = [
        point.co.copy(),
        point.handle_left.copy(),
        point.handle_right.copy(),
        ]
  return context.view_layer.objects.active
def offset_cable(self, context):
  count = 0
  for sindex, spline in enumerate(self.cable_mesh.data.splines):
    for pindex, point in enumerate(spline.bezier_points):
      point.co = self.init_points[str(sindex)][str(pindex)][0] + self.vert_normals[count] * self.events['O']['cur_value']
      point.handle_left = self.init_points[str(sindex)][str(pindex)][1] + self.vert_normals[count] * self.events['O']['cur_value']
      point.handle_right = self.init_points[str(sindex)][str(pindex)][2] + self.vert_normals[count] * self.events['O']['cur_value']
      count += 1
def finish_curve_from_edges(self):
  if self.bools['R']['status']:
    for ob in self.mesh_objects:
      bpy.data.objects.remove(ob, do_unlink=True)
def join_new_cable(self):
  def get_merge_points():
    points = []
    for index, spline in enumerate(new_cable.data.splines):
      if spline.type == 'BEZIER':
        for pindex, point in enumerate(spline.bezier_points):
          points.append({
            'co': point.co.copy(),
            'spline': index,
            'index': pindex
            })
    intersecting_points = []
    for index1, point1 in enumerate(points):
      for point2 in points:
        if vector_round(point1['co']*10000) == vector_round(point2['co']*10000) and (point1['index'] != point2['index'] or point1['spline'] != point2['spline']):
          intersecting_points.append({
            'index_p1': point1['index'],
            'spline_p1': point1['spline'],
            'index_p2': point2['index'],
            'spline_p2': point2['spline'],
            })
    return intersecting_points
  def merge(s):
    switch_mode('EDIT')
    bpy.ops.curve.select_all(action='DESELECT')
    new_cable.data.splines[s['spline_p1']].bezier_points[s['index_p1']].select_control_point = True
    new_cable.data.splines[s['spline_p2']].bezier_points[s['index_p2']].select_control_point = True
    bpy.ops.object.cableratorconnect('INVOKE_DEFAULT')
  if self.curve_obj['created_from_init1']:
    self.curve_obj['ob1'].select_set(True)
  if self.curve_obj['created_from_init2']:
    self.curve_obj['ob2'].select_set(True)
  self.context.view_layer.objects.active = self.curve_obj['ob1']
  bpy.ops.object.join()
  new_cable = self.context.view_layer.objects.active
  while True:
    points = get_merge_points()
    if not points:
      break
    merge(points[0])
  switch_mode('OBJECT')
def build_circle(curve, points_num, rad):
    switch_mode('EDIT')
    bpy.ops.curve.select_all(action='SELECT')
    bpy.ops.curve.delete(type='VERT')
    spline = curve.data.splines.new('POLY')
    spline.points.add(points_num - 1)
    spline.use_cyclic_u = True
    for index in range(points_num):
        angle = 360 / points_num * (points_num - index) + 360 / points_num / 2
        x = cos(radians(angle)) * rad
        y = sin(radians(angle)) * rad
        spline.points[index].co = Vector((x, y, 0, 0))
    switch_mode('OBJECT')
def create_circle(points_num, rad):
    objs = bpy.context.selected_objects
    if len(objs):
        switch_mode('OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
    curve_name = "Circle"
    curveData = bpy.data.curves.new(curve_name, type='CURVE')
    curveData.dimensions = '3D'
    curve = bpy.data.objects.new(curve_name, curveData)
    scn = bpy.context.scene
    scn.collection.objects.link(curve)
    bpy.context.view_layer.objects.active = curve
    curve.select_set(True)
    curve.location = bpy.context.scene.cursor.location.copy()
    build_circle(curve, points_num, rad)
    return curve
def get_scene_curves():
    if GV.is291:
        arr = list()
        for ob in bpy.data.objects:
          if ob.type == 'CURVE':
            if (ob.data.bevel_mode == 'ROUND' and ob.data.bevel_depth == 0) or (ob.data.bevel_mode == 'OBJECT' and ob.data.bevel_object == None):
              if ob.parent and ob.parent.type == 'MESH':
                continue
              else:
                arr.append(ob)
    else:
        arr = [ob for ob in bpy.data.objects
            if ob.type == 'CURVE'
            and (ob.data.bevel_depth == 0
            or ob.data.bevel_object == None)]
    return arr
def convert_curve_to_enum(curves):
    arr = [('None','None',0)]
    for index, curve in enumerate(curves):
        arr.append((curve.name, curve.name,index+1))
    return arr
def get_addon_directory():
  script_file = os.path.realpath(__file__)
  directory = os.path.dirname(script_file)
  return directory
def file_exists(filepath):
    return os.path.exists(filepath)
def import_data(path_to_blend, data_type, prefix='mesh'):
    with bpy.data.libraries.load(path_to_blend) as (data_from, data_to):
        if data_type == 'curves':
            data_to.curves = data_from.curves
        elif data_type == 'meshes':
            data_to.meshes = [name for name in data_from.meshes if name.startswith(prefix)]
    if data_type == 'curves':
        return [ob.name for ob in data_to.curves]
    elif data_type == 'meshes':
        return [ob.name for ob in data_to.meshes]
def get_datablock_names(arr_original):
    a = [re.sub(r'\.\d{3}','',el) for el in arr_original]
    a_copy = a[:]
    elements = [('None','None',0)]
    seen = {}
    dupes = []
    for index, x in enumerate(a):
        name = ''
        if x not in seen:
            seen[x] = 1
            name = x
        else:
            if seen[x] == 1:
                dupes.append(x)
            seen[x] += 1
            name = x + f' {str(seen[x])}'
        elements.append((arr_original[index], name, index+1))
    return elements
def remove_userless_curves():
    for curve in bpy.data.curves:
        if curve.users == 0 and not curve.use_fake_user:
            bpy.data.curves.remove(curve, do_unlink=True)
def get_path_to_blend():
  return os.path.join(get_addon_directory(),'elements.blend')
def get_external_curves(context):
    if __package__ in context.preferences.addons:
      if context.preferences.addons[__package__].preferences is not None:
        path_to_blend = context.preferences.addons[__package__].preferences.ext_assets_filepath
    else:
      path_to_blend = get_path_to_blend()
    if not file_exists(path_to_blend):
        raise ValueError("file doesn't exist")
        return list()
    imported_names = import_data(path_to_blend, 'curves')
    enums = get_datablock_names(imported_names)
    return enums
def clean_temp(self):
  if 'B' in self.enums:
      remove_userless_curves()
      if self.profile_scroll_switch == 0:
        if self.temp_curve:
          bpy.data.objects.remove(self.temp_curve, do_unlink=True)
      else:
        if self.temp_curve and self.enums['B']['cur_value'] == 0:
          bpy.data.objects.remove(self.temp_curve, do_unlink=True)
def init_grab_profile(self, context):
  scene_curves = get_scene_curves()
  try:
      external_curves = get_external_curves(context)
  except Exception as e:
      external_curves = [('None','None',0)]
  self.temp_curve = None
  self.profile_scroll_list = convert_curve_to_enum(scene_curves)
  self.saw_profile_scroll_list = True if len(scene_curves) > 0 else False
  self.profile_scroll_shift_list = external_curves
  self.saw_profile_scroll_shift_list = True if len(external_curves) > 1 else False
  self.profile_scroll_switch = 0
  self.show_profile_scroll = True
  if self.saw_profile_scroll_list:
      self.enum_scroll_name = 'Grab Profile (Act) (B)'
  elif self.saw_profile_scroll_shift_list:
      self.enum_scroll_name = 'Grab Profile (Ext) (B)'
      self.profile_scroll_switch = 1
  else:
      self.show_profile_scroll = False
def get_real_dimensions(ob):
  me = ob.data
  coords = np.empty(3 * len(me.vertices))
  me.vertices.foreach_get("co", coords)
  x, y, z = coords.reshape((-1, 3)).T
  return (
          x.max() - x.min(),
          y.max() - y.min(),
          z.max() - z.min()
          )