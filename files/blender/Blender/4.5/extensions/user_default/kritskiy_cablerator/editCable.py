import bpy
from .lib import *
from .ui import *
from .inits import *
from .typing import *
from math import radians, degrees
class OBJECT_OT_cablerator_edit_cable(bpy.types.Operator):
  """Edit cable width and other params"""
  bl_idname = "object.cablerator_edit_cable"
  bl_label = "Cablerator: Edit Cable"
  bl_options = {"REGISTER","UNDO"}
  @classmethod
  def poll(cls, context):
    if len(context.selected_objects) == 0:
      return False
    ob = context.object
    edit_condition = True
    if ob:
      edit_condition = ob.type == 'CURVE'
    return context.area.type == "VIEW_3D" and edit_condition
  def bool_x(self):
    key = 'X'
    for ob in self.objects:
        ob.show_wire = self.bools[key]['status']
  def bool_c(self):
    key = 'C'
    for ob in self.objects:
        ob.data.use_fill_caps = self.bools[key]['status']
  def enum_h(self):
    key = 'H'
    edit_curves(self, key)
  def enum_b(self):
    key = 'B'
    if self.is_shift:
        if self.profile_scroll_switch == 0:
            self.enums[key]['items'] = self.profile_scroll_shift_list
            self.profile_scroll_switch = 1
            self.enums[key]['cur_value'] = 0
            self.enums[key]['name'] = 'Grab Profile (Ext) (B)'
            FontGlobal.column_height = get_column_height(self)
            FontGlobal.column_width = get_column_width(self, FontGlobal.font_id, FontGlobal.size, FontGlobal.dpi)[0]
        else:
            self.enums[key]['items'] = self.profile_scroll_list
            self.profile_scroll_switch = 0
            self.enums[key]['cur_value'] = 0
            self.enums[key]['name'] = 'Grab Profile (Act) (B)'
            FontGlobal.column_height = get_column_height(self)
            FontGlobal.column_width = get_column_width(self, FontGlobal.font_id, FontGlobal.size, FontGlobal.dpi)[0]
    try:
        if self.profile_scroll_switch == 0:
            self.pickers['A']['object'] = bpy.data.objects[self.enums[key]['items'][self.enums[key]['cur_value']][0]] if self.enums[key]['cur_value'] > 0 else None
            if self.objects:
              for ob in self.objects:
                if GV.is291: ob.data.bevel_mode = 'OBJECT' if self.enums[key]['cur_value'] > 0 else 'ROUND'
                ob.data.bevel_object = bpy.data.objects[self.enums[key]['items'][self.enums[key]['cur_value']][0]] if self.enums[key]['cur_value'] > 0 else None
        else:
            data = bpy.data.curves[self.enums[key]['items'][self.enums[key]['cur_value']][0]] if self.enums[key]['cur_value'] > 0 else None
            if self.enums[key]['cur_value'] > 0:
                if not self.temp_curve:
                    self.temp_curve = bpy.data.objects.new(self.enums[key]['items'][self.enums[key]['cur_value']][1], data)
                    for ob in self.objects:
                        self.temp_curve.location = ob.matrix_world.decompose()[0]
                    bpy.context.scene.collection.objects.link(self.temp_curve)
                else:
                    for ob in self.objects:
                        self.temp_curve.location = ob.matrix_world.decompose()[0]
                    self.temp_curve.data = data
                    self.temp_curve.name = self.enums[key]['items'][self.enums[key]['cur_value']][1]
            self.pickers['A']['object'] = self.temp_curve if self.enums[key]['cur_value'] > 0 else None
            for ob in self.objects:
                if GV.is291: ob.data.bevel_mode = 'OBJECT' if self.enums[key]['cur_value'] > 0 else 'ROUND'
                ob.data.bevel_object = self.temp_curve if self.enums[key]['cur_value'] > 0 else None
    except Exception as e:
        self.report({'ERROR'}, str(e))
        pass
  def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.ui_vertices = []
      self.vertices = []
  def update_global_points(self):
    self.global_points = list()
    for ob in self.objects:
      mw = ob.matrix_world
      for sindex, spline in enumerate(ob.data.splines):
        for pindex, point in enumerate(spline.bezier_points):
          if pindex == 0 or pindex == len(spline.bezier_points) - 1:
            if pindex == 0:
              direction_point = point.handle_right.copy()
            else:
              direction_point = point.handle_left.copy()
            self.global_points.append({
              'ob': ob,
              'sindex': sindex,
              'pindex': pindex,
              'mw': mw,
              'co': point.co.copy(),
              'right': point.handle_right.copy(),
              'right_len': (point.handle_right - point.co).length,
              'left_len': (point.handle_left - point.co).length,
              'left': point.handle_left.copy(),
              'global_co': mw @ point.co.copy(),
            })
  def update_2d_points(self):
    region = self.context.region
    rv3d = self.context.region_data
    self.points_2d = [view3d_utils.location_3d_to_region_2d(region, rv3d, point['global_co']) for point in self.global_points]
  def get_selected_edit_point(self, event):
      size = len(self.points_2d)
      kd = mathutils.kdtree.KDTree(size)
      for i, point in enumerate(self.points_2d):
          if point:
              kd.insert(point.to_3d(), i)
      kd.balance()
      co, index, dist = kd.find((event.mouse_region_x, event.mouse_region_y, 0))
      return self.global_points[index]
  def move_selected_edit_point(self):
    selected_point = self.selected_point
    point = selected_point['ob'].data.splines[selected_point['sindex']].bezier_points[selected_point['pindex']]
    self.vertices = []
    self.vertices.append(selected_point['mw'] @ point.co)
    self.create_batch3d()
    if self.scene_raycast:
      location, normal, face_index, obj = self.scene_raycast
      if self.is_ctrl:
        object_eval = obj.evaluated_get(self.depsgraph)
        location = obj.matrix_world @ object_eval.data.polygons[face_index].center
      point.co = selected_point['mw'].inverted() @ location
      if selected_point['pindex'] == 0:
        point.handle_right = selected_point['mw'].inverted() @ (location + normal * selected_point['right_len'])
        point.handle_left = selected_point['mw'].inverted() @ (location - normal * selected_point['left_len'])
      else:
        point.handle_right = selected_point['mw'].inverted() @ (location - normal * selected_point['right_len'])
        point.handle_left = selected_point['mw'].inverted() @ (location + normal * selected_point['left_len'])
  def set_select_point(self, event):
    self.update_global_points()
    self.update_2d_points()
    self.selected_point = self.get_selected_edit_point(event)
  def modal(self, context, event):
    try:
      context.area.tag_redraw()
      if event.type in SIGNES.keys() and event.value == "PRESS":
          resolve_typing_signes(self, event)
      elif event.type in NUMBERS.keys() and event.value == "PRESS":
          resolve_typing_numbers(self, event)
      elif event.type == "BACK_SPACE" and event.value == "PRESS":
          resolve_typing_backspace(self, event)
      elif event.type in {"NUMPAD_PERIOD","PERIOD"} and event.value == "PRESS":
          resolve_typing_dot(self, event)
      elif event.type in {"RET","NUMPAD_ENTER"} and event.value == "PRESS":
          if self.typing:
              self.typing = False
              self.first_mouse_x = event.mouse_x
              resolve_typing_enter(self, event)
              for key in self.events.keys():
                  item = self.events[key]
                  if item['status']:
                      try:
                          if item['type'] != 'int':
                              self.cur_value = float(self.my_num_str)
                              item['cur_value'] = self.cur_value
                          else:
                              self.cur_value = int(self.my_num_str)
                              item['cur_value'] = self.cur_value
                      except:
                          pass
                      if key == 'W':
                        self.point.co = self.init_point_co + self.point_vec * self.events['W']['cur_value']
                        if self.selected_point['pindex'] == 0:
                          self.point.handle_right = self.point.co + self.point_vec * self.point_dist
                        else:
                          self.point.handle_left = self.point.co + self.point_vec * self.point_dist
                      elif key == 'I':
                        self.tilt_points(self.points_distribution)
                      else:
                        edit_curves(self, key)
          else:
              self.can_type = False
              clean_events(self)
      if self.pickers['D']['status']:
        self.selected_point['ob'].hide_set(True)
        scene_raycast(self, event, True)
        self.selected_point['ob'].hide_set(False)
        self.selected_point['ob'].select_set(True)
        self.move_selected_edit_point()
      if event.type in {'LEFT_SHIFT', 'RIGHT_SHIFT'}:
          if event.value == 'PRESS':
              self.is_shift = True
              self.first_value = self.cur_value
              self.first_mouse_x = event.mouse_x
          elif event.value == 'RELEASE':
              self.is_shift = False
              self.first_value = self.cur_value
              self.first_mouse_x = event.mouse_x
      if event.type in {'LEFT_CTRL', 'RIGHT_CTRL', 'OSKEY'}:
          if event.value == 'PRESS':
              self.is_ctrl = True
              self.first_value = self.cur_value
              self.first_mouse_x = event.mouse_x
          elif event.value == 'RELEASE':
              self.is_ctrl = False
              self.first_value = self.cur_value
              self.first_mouse_x = event.mouse_x
      if event.type in self.events.keys() and event.value == "PRESS":
          clean_pickers(self, True)
          event_type=event.type
          self.first_mouse_x = event.mouse_x
          for key in self.events.keys():
              if event.type == 'W':
                if self.is_shift:
                  event_type = 'W'
                  self.set_select_point(event)
                  self.point = self.selected_point['ob'].data.splines[self.selected_point['sindex']].bezier_points[self.selected_point['pindex']]
                  self.init_point_co = self.point.co.copy()
                  if self.selected_point['pindex'] == 0:
                    self.point_vec = (self.point.handle_right.copy() - self.point.co.copy()).normalized()
                    self.point_dist = self.selected_point['right_len']
                  else:
                    self.point_vec = (self.point.handle_left.copy() - self.point.co.copy()).normalized()
                    self.point_dist = self.selected_point['left_len']
                  self.events['W']['cur_value'] = 0
                else: event_type = 'whatevs'
              if event_type == key:
                  if self.events[key]['status']:
                      self.events[key]['status'] = False
                      self.can_type = False
                  else:
                      self.can_type = True
                      self.events[key]['status'] = True
                      self.first_value = self.events[key]['cur_value']
                      self.first_unchanged_value = self.events[key]['cur_value']
                      self.cur_value = self.events[key]['cur_value']
                      edit_curves(self, key)
              else:
                  self.events[key]['status'] = False
          return {'RUNNING_MODAL'}
      if event.type in self.enums.keys() and event.value == "PRESS":
          clean_pickers(self, True)
          clean_events(self)
          for key in self.enums.keys():
              if event.type == key:
                  if self.enums[key]['cur_value'] == len(self.enums[key]['items']) - 1:
                      self.enums[key]['cur_value'] = 0
                  else:
                      self.enums[key]['cur_value'] += 1
                  if key == 'H':
                      self.enum_h()
                  elif 'B' in self.enums and key == 'B':
                      self.enum_b()
          return {'RUNNING_MODAL'}
      if event.type in self.bools.keys() and event.value == "PRESS":
          clean_pickers(self, True)
          clean_events(self)
          for key in self.bools.keys():
              if event.type == key:
                  self.bools[key]['status'] = not self.bools[key]['status']
                  if key == 'X':
                      self.bool_x()
                  elif 'C' in self.bools and key == 'C':
                      self.bool_c()
          return {'RUNNING_MODAL'}
      if event.type in self.pickers.keys() and event.value == "PRESS":
        clean_pickers(self, True)
        clean_events(self)
        for key in self.pickers.keys():
            if event.type == key and self.pickers[key]['usable']:
                if self.pickers[key]['status']:
                    self.pickers[key]['status'] = False
                    self.pickers[key]['selecting'] = False
                else:
                    if key == 'A':
                      if self.active.data.bevel_object:
                        for ob in self.objects:
                          if GV.is291 and self.active.data.bevel_object: ob.data.bevel_mode = 'OBJECT'
                          ob.data.bevel_object = self.active.data.bevel_object
                    elif key == 'D':
                      bpy.ops.ed.undo_push(message="")
                      self.set_select_point(event)
                      self.point = self.selected_point['ob'].data.splines[self.selected_point['sindex']].bezier_points[self.selected_point['pindex']]
                      self.init_point_co = self.point.co.copy()
                      self.init_handle_right = self.point.handle_right.copy()
                      self.init_handle_left = self.point.handle_left.copy()
                    self.pickers[key]['status'] = True
                    self.pickers[key]['selecting'] = True
            else:
                self.pickers[key]['status'] = False
      if 'NDOF' in event.type or event.type in self.navigation or event.alt:
          return {'PASS_THROUGH'}
      if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
        wheel_val = 0.1 if event.type == 'WHEELUPMOUSE' else -0.1
        if self.events['S']['status']:
          self.events['S']['cur_value'] = normal_round((self.events['S']['cur_value'] + wheel_val)*10)/10
          if self.events['S']['cur_value'] < 0: self.events['S']['cur_value'] = 0
          self.first_value = self.events['S']['cur_value']
          self.first_unchanged_value = self.events['S']['cur_value']
          self.cur_value = self.events['S']['cur_value']
          self.first_mouse_x = event.mouse_x
          edit_curves(self, 'S')
        elif self.events['F']['status']:
          self.events['F']['cur_value'] += int(wheel_val*10)
          if self.events['F']['cur_value'] < 1: self.events['F']['cur_value'] = 1
          self.first_value = self.events['F']['cur_value']
          self.first_unchanged_value = self.events['F']['cur_value']
          self.cur_value = self.events['F']['cur_value']
          self.first_mouse_x = event.mouse_x
          edit_curves(self, 'F')
        elif self.events['V']['status']:
          self.events['V']['cur_value'] += int(wheel_val*10)
          if self.events['V']['cur_value'] < 0: self.events['V']['cur_value'] = 0
          self.first_value = self.events['V']['cur_value']
          self.first_unchanged_value = self.events['V']['cur_value']
          self.cur_value = self.events['V']['cur_value']
          self.first_mouse_x = event.mouse_x
          edit_curves(self, 'V')
        elif self.events['T']['status'] and self.pickers['A']['object']:
           self.events['T']['cur_value'] = normal_round((self.events['T']['cur_value'] + wheel_val)*10)/10
           if self.events['T']['cur_value'] < 0: self.events['T']['cur_value'] = 0
           self.first_value = self.events['T']['cur_value']
           self.first_unchanged_value = self.events['T']['cur_value']
           self.cur_value = self.events['T']['cur_value']
           self.first_mouse_x = event.mouse_x
           s = self.events['T']['cur_value']
           self.pickers['A']['object'].scale = s,s,s
        elif self.events['I']['status']:
          self.events['I']['cur_value'] =  int(normal_round((self.events['I']['cur_value'] + wheel_val*50)*.2)/.2)
          self.first_value = self.events['I']['cur_value']
          self.first_unchanged_value = self.events['I']['cur_value']
          self.cur_value = self.events['I']['cur_value']
          self.first_mouse_x = event.mouse_x
          self.tilt_points(self.points_distribution)
        elif 'W' in self.events and self.events['W']['status']:
          self.events['W']['cur_value'] = normal_round((self.events['W']['cur_value'] + wheel_val)*10)/10
          self.first_value = self.events['W']['cur_value']
          self.first_unchanged_value = self.events['W']['cur_value']
          self.cur_value = self.events['W']['cur_value']
          self.first_mouse_x = event.mouse_x
          self.point.co = self.init_point_co + self.point_vec * self.events['W']['cur_value']
          if self.selected_point['pindex'] == 0:
            self.point.handle_right = self.point.co + self.point_vec * self.point_dist
          else:
            self.point.handle_left = self.point.co + self.point_vec * self.point_dist
        else:
          return {'PASS_THROUGH'}
      if event.type == 'MOUSEMOVE':
          handle_hover(self, event)
          if self.typing: return {'RUNNING_MODAL'}
          for key in self.events.keys():
              item = self.events[key]
              if item['status']:
                  if self.is_shift:
                      delta = 1200 if key != 'I' else 20
                  else:
                      delta = 120 if key != 'I' else 5
                  if item['type'] != 'int' and key != 'I':
                      delta /= calc_mousemove_delta(item['cur_value'])
                  if event.mouse_x != self.first_mouse_x:
                      self.delta_offset = (event.mouse_x - self.first_mouse_x) / delta
                      self.first_mouse_x = event.mouse_x
                      if key != 'I':
                        self.cur_value += self.delta_offset
                      else:
                        if self.is_ctrl:
                          self.cur_value += self.delta_offset * 15
                        else:
                          self.cur_value += self.delta_offset * 5
                      if not event.is_tablet:
                            if self.region.x + self.warp_delta > event.mouse_x:
                                left_coord = self.region.x + self.region.width - self.warp_delta
                                context.window.cursor_warp(left_coord, event.mouse_y)
                                self.first_mouse_x = left_coord
                            elif self.region.x + self.region.width - self.warp_delta < event.mouse_x:
                                right_coord = self.region.x + self.warp_delta
                                context.window.cursor_warp(right_coord, event.mouse_y)
                                self.first_mouse_x = right_coord
                      if self.is_ctrl:
                          if key != 'I':
                              item['cur_value'] = normal_round((self.cur_value)*20)/20
                          elif key == 'I':
                              item['cur_value'] = normal_round(self.cur_value/15)*15
                      else:
                        if key != 'I':
                          item['cur_value'] = self.cur_value
                        else:
                          item['cur_value'] = normal_round(self.cur_value/5)*5
                      if item['type'] == 'int':
                          item['cur_value'] = normal_round(item['cur_value'])
                      if key == 'S' or key == 'V':
                          if self.cur_value < 0:
                              self.cur_value = 0
                              item['cur_value'] = 0
                          edit_curves(self, key)
                      elif key == 'F':
                          if self.cur_value < 1:
                              self.cur_value = 1
                              item['cur_value'] = 1
                          edit_curves(self, key)
                      elif key == 'T' and self.pickers['A']['object']:
                          edit_curves(self, key)
                      elif key == 'I':
                          self.tilt_points(self.points_distribution)
                      elif key == 'W':
                          self.point.co = self.init_point_co + self.point_vec * self.events['W']['cur_value']
                          if self.selected_point['pindex'] == 0:
                            self.point.handle_right = self.point.co + self.point_vec * self.point_dist
                          else:
                            self.point.handle_left = self.point.co + self.point_vec * self.point_dist
      if event.type == self.button and event.value == "PRESS":
          if self.pickers['A']['status']:
              bpy.ops.object.select_all(action='DESELECT')
              bpy.ops.wm.tool_set_by_id(name="builtin.select", cycle=False, space_type='VIEW_3D')
              return {'PASS_THROUGH'}
          if self.pickers['D']['status']:
              return {'PASS_THROUGH'}
      if event.type == self.button and event.value == "RELEASE":
        if self.pickers['A']['status']:
          if len(context.selected_objects) == 0:
            self.pickers['A']['status'] = False
            self.pickers['A']['selecting'] = False
            self.pickers['A']['object'] = None
            if 'B' in self.enums: self.enums['B']['cur_value'] = 0
            for curve in self.objects:
              if GV.is291: curve.data.bevel_mode = 'ROUND'
              curve.data.bevel_object = None
            self.events['T']['show'] = False
            FontGlobal.column_height = get_column_height(self)
          elif context.view_layer.objects.active.type != 'CURVE':
            self.report({'WARNING'}, f"Profile object should be a Curve, not {context.view_layer.objects.active.type.capitalize()}")
          elif context.view_layer.objects.active.type == 'CURVE' and context.view_layer.objects.active not in self.objects:
            self.pickers['A']['status'] = False
            self.pickers['A']['selecting'] = False
            self.pickers['A']['object'] = context.view_layer.objects.active
            if 'B' in self.enums: self.enums['B']['cur_value'] = 0
            for curve in self.objects:
              if GV.is291: curve.data.bevel_mode = 'OBJECT'
              curve.data.bevel_object = context.view_layer.objects.active
            self.events['T']['show'] = True
            self.events['T']['cur_value'] = sum(self.pickers['A']['object'].scale)/3
            FontGlobal.column_height = get_column_height(self)
          bpy.ops.object.select_all(action='DESELECT')
          for ob in self.objects:
            ob.select_set(True)
          context.view_layer.objects.active = self.ob
        elif self.pickers['D']['status']:
          self.pickers['D']['status'] = False
          self.pickers['D']['selecting'] = False
          del self.shader3d
          self.vertices = []
        bpy.ops.wm.tool_set_by_id(name=self.active_tool, cycle=False, space_type='VIEW_3D')
        return {'RUNNING_MODAL'}
      if event.type == 'LEFTMOUSE' and event.value == "PRESS":
          if self.text_ui_rect_batch["key"]: return handle_hover_press(self)
          for ev in self.events:
              if self.events[ev]['status']:
                  self.events[ev]['status'] = not self.events[ev]['status']
                  self.can_type = False
                  return {'RUNNING_MODAL'}
          for ev in self.pickers:
              if self.pickers[ev]['status']:
                  self.pickers[ev]['status'] = False
                  self.pickers[ev]['selecting'] = False
                  self.can_type = False
                  return {'RUNNING_MODAL'}
          switch_mode('OBJECT')
          if self._draw_handler:
            self._draw_handler = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
          if self._draw_handler3d:
            self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler3d, 'WINDOW')
          return {'FINISHED'}
      if event.type in self.cancel_buttons and event.value == "PRESS":
          for key in self.events:
              if self.events[key]['status']:
                  self.events[key]['cur_value'] = self.first_unchanged_value
                  if key == 'T':
                    s = self.events[key]['cur_value']
                    if self.pickers['A']['object']: self.pickers['A']['object'].scale = s,s,s
                  elif key == 'I':
                    self.tilt_points(self.points_distribution)
                  elif 'W' in self.events and key == 'W':
                    self.point.co = self.init_point_co + self.point_vec * self.events['W']['cur_value']
                    if self.selected_point['pindex'] == 0:
                      self.point.handle_right = self.point.co + self.point_vec * self.point_dist
                    else:
                      self.point.handle_left = self.point.co + self.point_vec * self.point_dist
                  else:
                    edit_curves(self, key)
                  self.events[key]['status'] = not self.events[key]['status']
                  return {'RUNNING_MODAL'}
          for key in self.pickers.keys():
            if self.pickers[key]['status']:
              self.pickers[key]['status'] = False
              self.pickers[key]['selecting'] = False
              if key == 'D':
                del self.shader3d
                self.vertices = []
                self.point.co = self.init_point_co
                self.point.handle_right = self.init_handle_right
                self.point.handle_left = self.init_handle_left
              return {'RUNNING_MODAL'}
          if self._draw_handler:
            self._draw_handler = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
          if self._draw_handler3d:
            self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler3d, 'WINDOW')
          return {'CANCELLED'}
      return {'RUNNING_MODAL'}
    except Exception as e:
      traceback.print_exc()
      self.report({'ERROR'}, str(e))
      if self._draw_handler:
        self._draw_handler = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
      if self._draw_handler3d:
        self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler3d, 'WINDOW')
      return {'CANCELLED'}
  def get_tilt(self):
    spline = self.active.data.splines[0]
    if spline.type == 'BEZIER':
      return int(degrees(spline.bezier_points[-1].tilt - spline.bezier_points[0].tilt))
    elif spline.type == 'POLY':
      return int(degrees(spline.points[-1].tilt - spline.points[0].tilt))
    else:
      return 0
  def get_all_points_distribution(self):
    def get_points_distribution(index, ob):
        super_select(ob, self.context)
        original_length = ob.data.splines[index].calc_length()
        length = original_length
        lengths = list()
        if length == 0: return None
        clone = duplicate_object(ob)
        super_select(clone, self.context)
        switch_mode('EDIT')
        bpy.ops.curve.select_all(action='DESELECT')
        orig_points_length = len(ob.data.splines[index].bezier_points) if ob.data.splines[index].type == 'BEZIER' else  len(ob.data.splines[index].points)
        temp_length = 0
        segments_length = length
        if clone.data.splines[index].type == 'BEZIER':
          for point in reversed(clone.data.splines[index].bezier_points):
              if orig_points_length == 2: break
              point.select_control_point = True
              bpy.ops.curve.delete(type='VERT')
              segments_length = clone.data.splines[index].calc_length()
              lengths.append(length - segments_length)
              length = segments_length
              orig_points_length -= 1
        elif clone.data.splines[index].type == 'POLY':
          for point in reversed(clone.data.splines[index].points):
              if orig_points_length == 2: break
              point.select = True
              bpy.ops.curve.delete(type='VERT')
              segments_length = clone.data.splines[index].calc_length()
              lengths.append(length - segments_length)
              length = segments_length
              orig_points_length -= 1
        lengths.append(segments_length)
        switch_mode('OBJECT')
        super_remove(clone, self.context)
        super_select(ob, self.context)
        distribution = [el / original_length for el in reversed(lengths)]
        distribution.append(0)
        return distribution
    dist_points = dict()
    for ob in self.objects:
        dist_points[ob.name] = dict()
        for index, spline in enumerate(ob.data.splines):
            try:
              pass
            except Exception as e:
              pass
            if spline.type == 'BEZIER':
              if len(spline.bezier_points) == 1: continue
            if spline.type == 'POLY':
              if len(spline.points) == 1: continue
            points_distr_temp = get_points_distribution(index, ob)
            if points_distr_temp:
              dist_points[ob.name][str(index)] = points_distr_temp
    super_select(self.objects, self.context)
    set_active(self.active, self.context)
    return dist_points
  def tilt_points(self, distrib):
      for ob_name in distrib:
          for sindex in distrib[ob_name]:
            ob = bpy.data.objects[ob_name]
            spline_index = int(sindex)
            tilt_value = 0
            if ob.data.splines[spline_index].type == 'BEZIER':
              zero_point_tilt = ob.data.splines[spline_index].bezier_points[0].tilt
              len_points = len(ob.data.splines[spline_index].bezier_points)
              for index, point in enumerate(ob.data.splines[spline_index].bezier_points):
                  point.tilt = radians(tilt_value * self.events['I']['cur_value']) + zero_point_tilt
                  tilt_value += distrib[ob_name][sindex][index]
            elif ob.data.splines[spline_index].type == 'POLY':
              zero_point_tilt = ob.data.splines[spline_index].points[0].tilt
              len_points = len(ob.data.splines[spline_index].points)
              for index, point in enumerate(ob.data.splines[spline_index].points):
                  point.tilt = radians(tilt_value * self.events['I']['cur_value']) + zero_point_tilt
                  tilt_value += distrib[ob_name][sindex][index]
  def create_batch3d(self):
        self.shader3d = create_3d_shader()
        self.batch3d = batch_for_shader(self.shader3d, 'POINTS', {"pos": self.vertices})
  def invoke(self, context, event):
    try:
      self.typing = False
      self.can_type = False
      self.my_num_str = ""
      self.text_ui_rect_batch = {
          "ui_rect": [],
          "items": {},
          "key": None,
          "inside_ui_rect": False,
      }
      self.objects = context.selected_objects
      self.active = context.view_layer.objects.active
      self.is_object_mode = context.object.mode == 'OBJECT'
      self.selected_points = []
      self.context = context
      self.scene_raycast = None
      self.depsgraph = context.evaluated_depsgraph_get()
      self.active_tool = context.workspace.tools.from_space_view3d_mode("OBJECT", create=False).idname
      if len(self.objects) == 0:
        self.report({'ERROR'}, "No objects selected, aborting")
        return {'CANCELLED'}
      for ob in self.objects:
        if ob.type != 'CURVE':
          self.report({'ERROR'}, f"'{ob.name}' is not a Curve object: expected all selected objects to be curves, aborting")
          return {'CANCELLED'}
        elif not self.is_object_mode:
          temp = get_selected_points(ob)
          for item in temp:
            item['object'] = ob
          self.selected_points.append(temp)
      self.selected_points = [points for obj in self.selected_points for points in obj]
      if not self.is_object_mode:
        switch_mode('OBJECT')
      self.points_distribution = self.get_all_points_distribution()
      self.ob = context.view_layer.objects.active
      if self.ob.data.twist_mode == 'Z_UP':
        twist = 0
      elif self.ob.data.twist_mode == 'MINIMUM':
        twist = 1
      elif self.ob.data.twist_mode == 'TANGENT':
        twist = 2
      self.show_offset = False
      self.title="Edit Cable."
      self.show_wire = True
      self.wire_status = self.active.show_wire
      for ob in self.objects:
        ob.show_wire = self.wire_status
      self.right_click = 0
      get_prefs(self, context)
      self.show_curve_length = False
      self.twist = twist
      self.button = 'RIGHTMOUSE' if self.right_click == '1' else 'LEFTMOUSE'
      self.events = {
          'T': {
              'name': 'Scale Profile (T)',
              'status': False,
              'cur_value': 1,
              'type': 'float',
              'show': False
          },
          'I': {
              'name': 'Tilt Cable (I)',
              'status': False,
              'cur_value': self.get_tilt(),
              'type': 'int',
              'show': True
          },
          'V': {
              'name': 'Bevel Resolution (V)',
              'status': False,
              'cur_value': self.ob.data.bevel_resolution,
              'type': 'int',
              'show': True
          },
          'F': {
              'name': 'Resolution (F)',
              'status': False,
              'cur_value': self.ob.data.resolution_u,
              'type': 'int',
              'show': True
          },
          'S': {
              'name': 'Width (S)',
              'status': False,
              'cur_value': self.ob.data.bevel_depth,
              'type': 'float',
              'show': True
          },
          'W': {
              'name': 'Offset Closest Point (⇧W)',
              'status': False,
              'cur_value': 0,
              'type': 'float',
              'show': self.show_offset
          }
      }
      self.bools = {
              'X': {
                  'name': 'Show Wire (X)',
                  'status': self.wire_status,
                  'usable': True,
                  'show': self.show_wire
              },
            }
      if GV.is291:
        self.fill_caps = self.ob.data.use_fill_caps
        self.bools['C'] = {
            'name': 'Fill Caps (C)',
            'status': self.fill_caps,
            'usable': True,
            'show': self.show_fill_caps
        }
      init_grab_profile(self, context)
      self.enums = {
          'H': {
              'name': 'Twist Method (H)',
              'status': False,
              'usable': True,
              'cur_value': self.twist,
              'items': [('Z_UP','Z-Up',0),('MINIMUM','Minimum',1),('TANGENT','Tangent',2)],
              'show': True
          },
      }
      if self.show_profile_scroll:
          self.enums['B']= {
              'name': self.enum_scroll_name,
              'status': False,
              'usable': True,
              'cur_value': 0,
              'items': self.profile_scroll_list if self.profile_scroll_switch == 0 else self.profile_scroll_shift_list,
              'show': self.show_grab_profile
          }
      self.bool_functions = {
          'X': self.bool_x,
          'C': self.bool_c,
      }
      self.enum_functions = {
          'H': self.enum_h,
          'B': self.enum_b,
      }
      self.pickers = {
          'A': {
              'name': 'Set Bevel Object (A)',
              'status': False,
              'selecting': False,
              'object': self.ob.data.bevel_object,
              'show': True,
              'usable': True,
              'vtext': 'Select a curve...'
          },
          'D': {
              'name': 'Move a Point (D)',
              'status': False,
              'selecting': False,
              'object': True,
              'show':  True,
              'usable': True,
              'vtext': 'Moving the Point...'
          }
      }
      if self.pickers['A']['object']:
          self.events['T']['show'] = True
          self.events['T']['cur_value'] = sum(self.pickers['A']['object'].scale)/3
      self.first_mouse_x = event.mouse_x
      self.cur_value = -1
      self.first_value = -1
      self.first_unchanged_value = -1
      self.is_shift = False
      self.is_ctrl = False
      self.reg = get_view(context, event.mouse_x, event.mouse_y)
      init_font_settings(self)
      if context.space_data.type == 'VIEW_3D':
          self.init_area = context.area
          self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, (self, context), 'WINDOW', 'POST_PIXEL')
          self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_add(draw_callback_3d, (self, context), 'WINDOW', 'POST_VIEW')
          context.window_manager.modal_handler_add(self)
          return {'RUNNING_MODAL'}
      else:
          self.report({'WARNING'}, "Active space must be a View3d")
          if self._draw_handler:
            self._draw_handler = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
          if self._draw_handler3d:
            self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler3d, 'WINDOW')
          return {'CANCELLED'}
    except Exception as e:
      traceback.print_exc()
      self.report({'ERROR'}, str(e))
      if self._draw_handler:
        self._draw_handler = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
      if self._draw_handler3d:
        self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler3d, 'WINDOW')
      return {'CANCELLED'}
def register():
    bpy.utils.register_class(OBJECT_OT_cablerator_edit_cable)
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_cablerator_edit_cable)