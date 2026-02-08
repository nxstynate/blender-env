import bpy
from .lib import *
from .ui import *
from .inits import *
from .typing import *
from math import radians, degrees
class OBJECT_OT_cablerator_connector(bpy.types.Operator):
  """Select a Mesh and a Curve end points in Edit Mode to move the object to these points.
  Mesh will be oriented by Z axis"""
  bl_idname = "object.cablerator_connector"
  bl_label = "Cablerator: Assign Connector"
  bl_options = {"REGISTER", "UNDO"}
  @classmethod
  def poll(cls, context):
    if len(context.selected_objects) == 0:
      return False
    ob = context.object
    edit_condition = True
    if ob:
      edit_condition = context.object.mode == 'EDIT'
    return context.area.type == "VIEW_3D" and edit_condition
  def bool_r(self):
    key = 'R'
  def bool_a(self):
    key = 'A'
    self.flip = self.bools[key]['status']
    reposition_clones(self)
  def bool_h(self):
    key = 'H'
  def modal(self, context, event):
      context.area.tag_redraw()
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
          self.first_mouse_x = event.mouse_x
          for key in self.events.keys():
              if event.type == key:
                  if self.events[key]['status']:
                      self.events[key]['status'] = False
                      self.can_type = False
                  else:
                      self.events[key]['status'] = True
                      self.can_type = True
                      self.first_value = self.events[key]['cur_value']
                      self.first_unchanged_value = self.events[key]['cur_value']
                      self.cur_value = self.events[key]['cur_value']
              else:
                  self.events[key]['status'] = False
          return {'RUNNING_MODAL'}
      if event.type in self.bools.keys() and event.value == "PRESS":
          for key in self.events.keys():
            self.events[key]['status'] = False
          for key in self.bools.keys():
              if event.type == key:
                  if key == 'A' and self.bools[key]['usable']:
                      self.bool_a()
                  elif key == 'R':
                      self.bool_r()
                  elif key == 'H':
                      self.bool_h()
          return {'RUNNING_MODAL'}
      if 'NDOF' in event.type or event.type in self.navigation or event.alt:
          return {'PASS_THROUGH'}
      if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
        wheel_val = 0.1 if event.type == 'WHEELUPMOUSE' else -0.1
        if self.events['S']['status']:
          self.events['S']['cur_value'] = normal_round((self.events['S']['cur_value'] + wheel_val)*10)/10
          self.first_value = self.events['S']['cur_value']
          self.first_unchanged_value = self.events['S']['cur_value']
          self.cur_value = self.events['S']['cur_value']
          self.first_mouse_x = event.mouse_x
          self.offset_point = self.events['S']['cur_value']
          edit_connector_spline(self)
        elif self.events['D']['status']:
          self.events['D']['cur_value'] = normal_round((self.events['D']['cur_value'] + wheel_val)*10)/10
          self.first_value = self.events['D']['cur_value']
          self.first_unchanged_value = self.events['D']['cur_value']
          self.cur_value = self.events['D']['cur_value']
          self.first_mouse_x = event.mouse_x
          self.offset = self.events['D']['cur_value']
          reposition_clones(self)
        elif self.events['T']['status']:
          self.events['T']['cur_value'] = normal_round((self.events['T']['cur_value'] + wheel_val)*10)/10
          self.first_value = self.events['T']['cur_value']
          self.first_unchanged_value = self.events['T']['cur_value']
          self.cur_value = self.events['T']['cur_value']
          self.first_mouse_x = event.mouse_x
          scale_clones(self)
        else:
          return {'PASS_THROUGH'}
      elif event.type in SIGNES.keys() and event.value == "PRESS":
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
                    if key == 'D':
                        self.offset = item['cur_value']
                        reposition_clones(self)
                    elif key == 'S':
                        self.offset_point = item['cur_value']
                        edit_connector_spline(self)
                    elif key == 'T':
                        scale_clones(self)
          else:
              self.can_type = False
              clean_events(self)
      elif event.type == 'MOUSEMOVE':
          handle_hover(self, event)
          if self.typing: return {'RUNNING_MODAL'}
          for key in self.events.keys():
              item = self.events[key]
              if item['status']:
                  if self.is_shift:
                      delta = 1200
                  else:
                      delta = 120
                  if item['type'] != 'int':
                    delta /= calc_mousemove_delta(item['cur_value'])
                  if event.mouse_x != self.first_mouse_x:
                        self.delta_offset = (event.mouse_x - self.first_mouse_x) / delta
                        self.first_mouse_x = event.mouse_x
                        self.cur_value += self.delta_offset
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
                            item['cur_value'] = normal_round((self.cur_value)*20)/20
                        else:
                            item['cur_value'] = self.cur_value
                        if item['type'] == 'int':
                            item['cur_value'] = normal_round(item['cur_value'])
                        if key == 'D':
                            self.offset = item['cur_value']
                            reposition_clones(self)
                        elif key == 'S':
                            self.offset_point = item['cur_value']
                            edit_connector_spline(self)
                        elif key == 'T':
                            scale_clones(self)
      elif event.type == 'LEFTMOUSE' and event.value == "PRESS":
          if self.text_ui_rect_batch["key"]: return handle_hover_press(self)
          for ev in self.events:
              if self.events[ev]['status']:
                  self.events[ev]['status'] = not self.events[ev]['status']
                  self.can_type = False
                  return {'RUNNING_MODAL'}
          bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
          finish_clones(self)
          return {'FINISHED'}
      elif event.type in self.cancel_buttons and event.value == "PRESS":
          for key in self.events:
              if self.events[key]['status']:
                  self.events[key]['cur_value'] = self.first_unchanged_value
                  if key == 'D':
                      self.offset = self.events[key]['cur_value']
                      reposition_clones(self)
                  elif key == 'S':
                      self.offset_point = self.events[key]['cur_value']
                      edit_connector_spline(self)
                  elif key == 'T':
                      scale_clones(self)
                  self.events[key]['status'] = not self.events[key]['status']
                  return {'RUNNING_MODAL'}
          bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
          finish_clones(self)
          return {'CANCELLED'}
      return {'RUNNING_MODAL'}
  def invoke(self, context, event):
    self.typing = False
    self.can_type = False
    self.my_num_str = ""
    self.text_ui_rect_batch = {
        "ui_rect": [],
        "items": {},
        "key": None,
        "inside_ui_rect": False,
    }
    try:
      self.objects = geo_sort_objects(context.selected_objects)
    except Exception as e:
      self.report({'ERROR'}, str(e))
      return {'CANCELLED'}
    self.connector = self.objects['ob']
    self.curves = self.objects['curves']
    self.context = context
    for curve in self.curves:
      curve.data.use_path = False
    self.flip = False
    self.offset = 0
    self.offset_point = 0
    self.rotate = 0
    self.finished = False
    self.prev_rotation = 0
    self.rotation_deg = 0
    self.prev_sign = 0
    self.prev_mouse = -1
    self.actual_val = 0
    self.curve_length = -1
    self.show_curve_length = False
    self.connector_data = None
    self.parent_connectors = True
    self.scale = sum(self.objects['ob'].scale) / len(self.objects['ob'].scale)
    self.title="Assign conectors to points."
    self.events = {
        'T': {
            'name': 'Scale Connector (T)',
            'status': False,
            'cur_value': self.scale,
            'type': 'float',
            'show': True
        },
        'D': {
            'name': 'Offset Connector (D)',
            'status': False,
            'cur_value': self.offset,
            'type': 'float',
            'show': True
        },
        'S': {
            'name': 'Offset Point (S)',
            'status': False,
            'cur_value': self.offset_point,
            'type': 'float',
            'show': True
        },
    }
    self.bools = {
        'R': {
            'name': 'Remove the Original Mesh (R)',
            'status': False,
            'usable': True,
            'show': True
        },
        'H': {
            'name': 'Hook Point to Connector (H)',
            'status': True,
            'usable': True,
            'show': True
        },
        'A': {
            'name': 'Flip Direction (A)',
            'status': self.flip,
            'usable': True,
            'show': True
        },
    }
    self.bool_functions = {
        'R': self.bool_r,
        'H': self.bool_h,
        'A': self.bool_a,
    }
    get_prefs(self, context)
    self.show_curve_length = False
    self.selected_points = []
    for curve in self.curves:
      found_points = {
        'ob': curve,
        'points': get_selected_points(curve)
        }
      if len(found_points) == 0:
        self.report({'ERROR'}, 'No valid points found in '+curve.name+', aborting')
        return {'CANCELLED'}
      self.selected_points.append(found_points)
    switch_mode('OBJECT')
    self.clones = clone_connectors(self.selected_points, self)
    position_clones(self)
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
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    else:
        self.report({'WARNING'}, "Active space must be a View3d")
        bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
        return {'CANCELLED'}
    return {'FINISHED'}
def register():
    bpy.utils.register_class(OBJECT_OT_cablerator_connector)
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_cablerator_connector)