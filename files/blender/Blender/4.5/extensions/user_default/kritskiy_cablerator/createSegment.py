import bpy
from .lib import *
from .ui import *
from .inits import *
from .typing import *
class OBJECT_OT_cablerator_segment(bpy.types.Operator):
  """Select a Mesh and a Curve or a Segment mesh in Object Mode"""
  bl_idname = "object.cablerator_segment"
  bl_label = "Cablerator: Add Segment"
  bl_options = {"REGISTER", "UNDO"}
  duplicate: bpy.props.BoolProperty(name="From Duplicate", default=False)
  @classmethod
  def poll(cls, context):
    if len(context.selected_objects) < 1:
      return False
    ob = context.object
    edit_condition = True
    if ob:
      edit_condition = context.object.mode == 'OBJECT'
    return context.area.type == "VIEW_3D"
  def resolve_event_D(self, item):
    self.displ_mod.strength = item['cur_value']
  def resolve_event_F(self, item):
    self.segment.matrix_world = local_mw_rotate('Z', self.segment.matrix_world, item['cur_value'])
  def resolve_event_S(self, item):
    self.arr_mod.constant_offset_displace[2] = item['cur_value']
  def resolve_event_C(self, item):
    if self.cur_value < 1:
        self.cur_value = 1
        item['cur_value'] = 1
    self.arr_mod.count = item['cur_value']
  def resolve_event_T(self, item):
      s = item['cur_value']
      self.segment.scale = s,s,s
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
                      self.first_unchanged_value = self.events[key]['cur_value']
                      self.first_value = self.events[key]['cur_value']
                      self.cur_value = self.events[key]['cur_value']
              else:
                  self.events[key]['status'] = False
          return {'RUNNING_MODAL'}
      if 'NDOF' in event.type or event.type in self.navigation or event.alt:
            return {'PASS_THROUGH'}
      if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
        wheel_val = 0.1 if event.type == 'WHEELUPMOUSE' else -0.1
        if self.events['D']['status']:
          item = self.events['D']
          item['cur_value'] = normal_round((item['cur_value'] + wheel_val*4)*2.5)/2.5
          self.first_value = item['cur_value']
          self.first_unchanged_value = item['cur_value']
          self.cur_value = item['cur_value']
          self.first_mouse_x = event.mouse_x
          self.resolve_event_D(item)
        elif 'C' in self.events and self.events['C']['status']:
          item = self.events['C']
          self.events['C']['cur_value'] += int(wheel_val*10)
          if item['cur_value'] < 1: item['cur_value'] = 1
          self.first_value = item['cur_value']
          self.first_unchanged_value = item['cur_value']
          self.cur_value = item['cur_value']
          self.first_mouse_x = event.mouse_x
          self.resolve_event_C(item)
        elif self.events['F']['status']:
          item = self.events['F']
          item['cur_value'] =  int(normal_round((item['cur_value'] + wheel_val*50)*.2)/.2)
          self.first_value = item['cur_value']
          self.first_unchanged_value = item['cur_value']
          self.cur_value = item['cur_value']
          self.first_mouse_x = event.mouse_x
          self.resolve_event_F(item)
        elif self.events['T']['status']:
           self.events['T']['cur_value'] = normal_round((self.events['T']['cur_value'] + wheel_val)*10)/10
           if self.events['T']['cur_value'] < 0: self.events['T']['cur_value'] = 0
           self.first_value = self.events['T']['cur_value']
           self.first_unchanged_value = self.events['T']['cur_value']
           self.cur_value = self.events['T']['cur_value']
           self.first_mouse_x = event.mouse_x
           self.resolve_event_T(item)
        elif 'S' in self.events and self.events['S']['status']:
          item = self.events['s']
          item['cur_value'] = normal_round((item['cur_value'] + wheel_val)*10)/10
          self.first_value = item['cur_value']
          self.first_unchanged_value = item['cur_value']
          self.cur_value = item['cur_value']
          self.first_mouse_x = event.mouse_x
          self.resolve_event_S(item)
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
                            self.resolve_event_D(item)
                      elif key == 'F':
                            self.resolve_event_F(item)
                      elif key == 'S':
                            self.resolve_event_S(item)
                      elif key == 'C':
                            self.resolve_event_C(item)
                      elif key == 'T':
                            self.resolve_event_T(item)
          else:
              self.can_type = False
              clean_events(self)
      elif event.type == 'MOUSEMOVE':
          if self.typing: return {'RUNNING_MODAL'}
          for key in self.events.keys():
              item = self.events[key]
              if item['status']:
                  if self.is_shift:
                      delta = 1200 if key != 'F' else 25
                  else:
                      delta = 120 if key != 'F' else 5
                  if item['type'] != 'int' and key not in {'F','D'}:
                      delta /= calc_mousemove_delta(item['cur_value'])
                  if event.mouse_x != self.first_mouse_x:
                        self.delta_offset = (event.mouse_x - self.first_mouse_x) / delta
                        self.first_mouse_x = event.mouse_x
                        if key != 'F':
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
                            if key != 'F':
                                item['cur_value'] = normal_round((self.cur_value)*20)/20
                            elif key == 'F':
                                item['cur_value'] = normal_round(self.cur_value/15)*15
                        else:
                            if key != 'F':
                                item['cur_value'] = self.cur_value
                            else:
                                item['cur_value'] = normal_round(self.cur_value/5)*5
                        if item['type'] == 'int':
                            item['cur_value'] = normal_round(item['cur_value'])
                        if key == 'D':
                            self.resolve_event_D(item)
                        elif key == 'F':
                            self.resolve_event_F(item)
                        elif key == 'S':
                            self.resolve_event_S(item)
                        elif key == 'C':
                            self.resolve_event_C(item)
                        elif key == 'T':
                            self.resolve_event_T(item)
      if event.type in self.actions.keys() and event.value == "PRESS":
          for key in self.events.keys():
            self.events[key]['status'] = False
          for key in self.actions.keys():
              if event.type == key:
                  if key == 'Q':
                      new_obj = self.segment.copy()
                      new_obj.data = self.segment.data
                      new_obj.animation_data_clear()
                      context.scene.collection.objects.link(new_obj)
                      self.segment.select_set(False)
                      context.view_layer.objects.active = self.ob
                      bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
                      bpy.ops.object.cablerator_segment('INVOKE_DEFAULT', duplicate=True)
                      return {'FINISHED'}
                  elif key == 'A':
                    if self.arr_mod:
                      self.segment.modifiers.remove(self.arr_mod)
                      del self.events['S']
                      del self.events['C']
                      self.arr_mod = None
                      FontGlobal.column_height = get_column_height(self)
                      FontGlobal.column_width = get_column_width(self, FontGlobal.font_id, FontGlobal.size, FontGlobal.dpi)[0]
                      self.actions['A']['name'] = 'Add Array (A)'
                    else:
                      mod_index = self.segment.modifiers.find(self.curve_mod.name)
                      self.arr_mod = self.segment.modifiers.new(name='Array',type='ARRAY')
                      self.arr_mod.use_relative_offset = False
                      self.arr_mod.use_constant_offset = True
                      self.arr_mod.constant_offset_displace[0] = 0
                      self.arr_mod.constant_offset_displace[1] = 0
                      self.arr_mod.constant_offset_displace[2] = get_real_dimensions(self.segment)[2]
                      self.arr_mod.count = 2
                      if mod_index == -1:
                        self.report({'ERROR'}, 'Somehow didn\'t find the curve mod? Something went terribly wrong, aborting')
                        return {'CANCELLED'}
                      context.view_layer.objects.active = self.segment
                      count = 0
                      while self.segment.modifiers.find(self.arr_mod.name) != mod_index:
                          bpy.ops.object.modifier_move_up(modifier=self.arr_mod.name)
                          count += 1
                          if count > 10:
                            break
                      context.view_layer.objects.active = self.ob
                      self.events['S'] = {
                          'name': 'Constant Offset Array Element (S)',
                          'status': False,
                          'cur_value': self.arr_mod.constant_offset_displace[2],
                          'type': 'float',
                          'show': True
                      }
                      self.events['C'] = {
                          'name': 'Array Count (C)',
                          'status': False,
                          'cur_value': self.arr_mod.count,
                          'type': 'int',
                          'show': True
                      }
                      key_order = ('S', 'C', 'D', 'F')
                      self.events = dict((k, self.events[k]) for k in key_order)
                      self.actions['A']['name'] = 'Remove Array (A)'
                      FontGlobal.column_height = get_column_height(self)
                      FontGlobal.column_width = get_column_width(self, FontGlobal.font_id, FontGlobal.size, FontGlobal.dpi)[0]
          return {'RUNNING_MODAL'}
      elif event.type == 'LEFTMOUSE' and event.value == "PRESS":
          for ev in self.events:
              if self.events[ev]['status']:
                  self.events[ev]['status'] = not self.events[ev]['status']
                  return {'RUNNING_MODAL'}
          bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
          return {'FINISHED'}
      elif event.type in self.cancel_buttons and event.value == "PRESS":
          for key in self.events:
              if self.events[key]['status']:
                  self.events[key]['cur_value'] = self.first_unchanged_value
                  if key == 'D':
                      self.displ_mod.strength = self.events[key]['cur_value']
                  elif key == 'F':
                      self.segment.rotation_euler[2] = radians(self.events[key]['cur_value'])
                  elif key == 'S':
                      self.arr_mod.constant_offset_displace[2] = self.events[key]['cur_value']
                  elif key == 'C':
                      self.arr_mod.count = self.events[key]['cur_value']
                  elif key == 'T':
                      s = self.events[key]['cur_value']
                      self.segment.scale = s,s,s
                  self.events[key]['status'] = not self.events[key]['status']
                  return {'RUNNING_MODAL'}
          bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
          bpy.ops.ed.undo()
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
    mods = [x for x in context.selected_objects[0].modifiers if x.type == 'CURVE' or x.type == 'DISPLACE']
    curve_mod = next((mod for mod in mods if mod.type == 'CURVE'), None)
    if len(context.selected_objects) == 1:
      if context.selected_objects[0].type != 'MESH' or len(mods) != 2 or not curve_mod:
        self.report({'ERROR'}, 'Wrong object selected for Segment editing, aborting. To create a segment select a mesh and a curve.')
        return {'CANCELLED'}
      self.ob = curve_mod.object
      self.ob.data.use_path = False
      self.segment = context.selected_objects[0]
    elif len(context.selected_objects) != 2:
      self.report({'ERROR'}, str(len(context.selected_objects)) + ' objects selected: expected 2 (a Mesh and a Curve). Aborting')
      return {'CANCELLED'}
    else:
      for obj in context.selected_objects:
        if obj.type == 'CURVE':
          self.ob = obj
          self.ob.data.use_path = False
        elif obj.type == 'MESH':
          self.segment = obj
        else:
          self.report({'ERROR'}, f"Unexpected object found: {obj.type}, aborting")
          return {'CANCELLED'}
      if mods == 2 and curve_mod.object != self.ob:
        new_obj = self.segment.copy()
        new_obj.data = self.segment.data
        new_obj.animation_data_clear()
        self.segment.users_collection[0].objects.link(new_obj)
        if new_obj.parent:
          new_obj.parent = None
        self.segment.select_set(False)
        context.view_layer.objects.active = self.ob
        mods = [x for x in self.segment.modifiers if x.type == 'CURVE' or x.type == 'DISPLACE']
        curve_mod = next((mod for mod in mods if mod.type == 'CURVE'), None)
        curve_mod.ob = self.ob
        self.segment = new_obj
    self.context = context
    self.parent_connectors = True
    if __package__ in context.preferences.addons:
        if context.preferences.addons[__package__].preferences is not None:
            FontGlobal.size = context.preferences.addons[__package__].preferences.font_size
            self.parent_connectors = context.preferences.addons[__package__].preferences.parent_connectors
    self.displ_mod, self.curve_mod, self.arr_mod = set_segment(self)
    self.finished = False
    self.prev_rotation = 0
    self.rotation_deg = 0
    self.prev_sign = 0
    self.prev_mouse = -1
    self.actual_val = 0
    self.curve_length = -1
    self.show_curve_length = False
    self.right_click = 0
    get_prefs(self, context)
    self.button = 'RIGHTMOUSE' if self.right_click == '1' else 'LEFTMOUSE'
    self.title="Add segments to a curve."
    self.events = {
        'T': {
              'name': 'Scale Segment (T)',
              'status': False,
              'cur_value': 1,
              'type': 'float',
              'show': True
          },
        'F': {
            'name': 'Tilt Segment (F)',
            'status': False,
            'cur_value': normal_round(degrees(self.segment.rotation_euler[2])),
            'type': 'int',
            'show': True
        },
        'D': {
            'name': 'Offset Segment (D)',
            'status': self.duplicate,
            'cur_value': self.displ_mod.strength,
            'type': 'float',
            'show': True
        },
    }
    self.actions = {
        'Q': {
            'name': 'Duplicate (Q)',
            'status': True,
            'show': True,
        },
    }
    if self.arr_mod:
      self.actions['A'] = {
          'name': 'Remove Array (A)',
          'status': True,
          'show': True,
          'usable': True,
      }
      key_order = ('Q', 'A')
      self.actions = dict((k, self.actions[k]) for k in key_order)
      self.events['S'] = {
          'name': 'Constant Offset Array Element (S)',
          'status': False,
          'cur_value': self.arr_mod.constant_offset_displace[2],
          'type': 'float',
          'show': True
      }
      self.events['C'] = {
          'name': 'Array Count (C)',
          'status': False,
          'cur_value': self.arr_mod.count,
          'type': 'int',
          'show': True
      }
      key_order = ('S', 'C', 'D', 'F')
      self.events = dict((k, self.events[k]) for k in key_order)
    else:
      self.actions['A'] = {
          'name': 'Add Array (A)',
          'status': True,
          'show': True,
          'usable': True,
      }
      key_order = ('Q', 'A')
      self.actions = dict((k, self.actions[k]) for k in key_order)
    self.first_mouse_x = event.mouse_x
    self.cur_value = -1 if not self.duplicate else self.displ_mod.strength
    self.first_unchanged_value = -1 if not self.duplicate else self.displ_mod.strength
    self.first_value = -1 if not self.duplicate else self.displ_mod.strength
    self.is_shift = False
    self.is_ctrl = False
    self.reg = get_view(context, event.mouse_x, event.mouse_y)
    if not FontGlobal.size:
        FontGlobal.size = 13
    temp = get_column_width(self, FontGlobal.font_id, FontGlobal.size, FontGlobal.dpi)
    FontGlobal.LN = get_line(FontGlobal.font_id, FontGlobal.size, FontGlobal.dpi)
    FontGlobal.column_width = temp[0]
    FontGlobal.add_width = temp[1]
    FontGlobal.column_height = get_column_height(self)
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
    bpy.utils.register_class(OBJECT_OT_cablerator_segment)
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_cablerator_segment)