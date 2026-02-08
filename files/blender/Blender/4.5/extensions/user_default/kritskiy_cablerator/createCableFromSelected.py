import bpy
from .lib import *
from .ui import *
from .inits import *
from .typing import *
from math import radians, degrees
class OBJECT_OT_cablerator_create_cable_from_selected(bpy.types.Operator):
  """Select objects and create cables between them"""
  bl_idname = "object.cablerator_create_cable_from_selected"
  bl_label = "Cablerator: Create a Cable from Selected Objects"
  bl_options = {"REGISTER", "UNDO"}
  @classmethod
  def poll(cls, context):
    if len(context.selected_objects) < 2:
      return False
    ob = context.object
    edit_condition = True
    if ob:
      edit_condition = context.object.mode == 'OBJECT'
    return context.area.type == "VIEW_3D" and edit_condition
  def bool_r(self):
    key = 'R'
  def bool_c(self):
    key = 'C'
    edit_curves(self, key)
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
          clean_pickers(self)
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
                      edit_curves(self, key)
              else:
                  self.events[key]['status'] = False
          return {'RUNNING_MODAL'}
      if event.type in self.bools.keys() and event.value == "PRESS":
          clean_pickers(self)
          clean_events(self)
          for key in self.events.keys():
            self.events[key]['status'] = False
          for key in self.bools.keys():
              if event.type == key:
                  self.bools[key]['status'] = not self.bools[key]['status']
                  if 'C' in self.bools and key == 'C':
                      self.bool_c()
          return {'RUNNING_MODAL'}
      if event.type in self.actions.keys() and event.value == "PRESS":
          clean_pickers(self)
          clean_events(self)
          for key in self.actions.keys():
              if event.type == key:
                  if key == 'N' and self.actions[key]['status']:
                      set_curves_from_selected(self, context, key)
          return {'RUNNING_MODAL'}
      if event.type in self.enums.keys() and event.value == "PRESS":
          clean_pickers(self)
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
      if event.type in self.pickers.keys() and event.value == "PRESS":
        clean_events(self)
        for key in self.pickers.keys():
          if event.type != key:
              self.pickers[key]['status'] = False
              self.pickers[key]['selecting'] = False
        for key in self.pickers.keys():
            if event.type == key and self.pickers[key]['usable']:
                if self.pickers[key]['status']:
                    self.pickers[key]['status'] = False
                    self.pickers[key]['selecting'] = False
                else:
                    self.pickers[key]['status'] = True
                    self.pickers[key]['selecting'] = True
            else:
                self.pickers[key]['status'] = False
        return {'RUNNING_MODAL'}
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
        elif self.events['D']['status']:
          self.events['D']['cur_value'] = normal_round((self.events['D']['cur_value'] + wheel_val*4)*2.5)/2.5
          if self.events['D']['cur_value'] < 0: self.events['D']['cur_value'] = 0
          self.first_value = self.events['D']['cur_value']
          self.first_unchanged_value = self.events['D']['cur_value']
          self.cur_value = self.events['D']['cur_value']
          self.first_mouse_x = event.mouse_x
          self.strength = self.events['D']['cur_value']
          set_curves_from_selected(self, context, 'D')
          self.init_ten = self.events['D']['cur_value']
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
                        self.strength = item['cur_value']
                        self.init_ten = item['cur_value']
                        set_curves_from_selected(self, context, key)
                      else:
                        edit_curves(self, key)
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
                            if key not in {'W','E'}:
                                item['cur_value'] = normal_round((self.cur_value)*20)/20
                            else:
                                item['cur_value'] = normal_round(((self.cur_value)*5)/5)*5
                        else:
                            item['cur_value'] = self.cur_value
                        if item['type'] == 'int':
                            item['cur_value'] = normal_round(item['cur_value'])
                        if key == 'S' or key == 'V':
                            if self.cur_value < 0:
                                self.cur_value = 0
                                item['cur_value'] = 0
                            edit_curves(self, key)
                        elif key == 'D':
                            if self.cur_value < 0:
                                self.cur_value = 0
                                item['cur_value'] = 0
                            self.strength = item['cur_value']
                            self.init_ten = item['cur_value']
                            set_curves_from_selected(self, context, key)
                        elif key == 'F':
                            if self.cur_value < 1:
                                self.cur_value = 1
                                item['cur_value'] = 1
                            edit_curves(self, key)
                        elif key == 'T' and self.pickers['A']['object']:
                            edit_curves(self, key)
      if event.type == self.button and event.value == "PRESS" and self.pickers['A']['status']:
          bpy.ops.object.select_all(action='DESELECT')
          bpy.ops.wm.tool_set_by_id(name="builtin.select", cycle=False, space_type='VIEW_3D')
          return {'PASS_THROUGH'}
      elif event.type == self.button and event.value == "RELEASE" and self.pickers['A']['status']:
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
          FontGlobal.column_width = get_column_width(self, FontGlobal.font_id, FontGlobal.size, FontGlobal.dpi)[0]
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
          FontGlobal.column_width = get_column_width(self, FontGlobal.font_id, FontGlobal.size, FontGlobal.dpi)[0]
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.wm.tool_set_by_id(name=self.active_tool, cycle=False, space_type='VIEW_3D')
        return {'RUNNING_MODAL'}
      elif event.type == 'LEFTMOUSE' and event.value == "PRESS":
          if self.text_ui_rect_batch["key"]: return handle_hover_press(self)
          for key in self.events:
              if self.events[key]['status']:
                  self.events[key]['status'] = not self.events[key]['status']
                  self.can_type = False
                  return {'RUNNING_MODAL'}
          for key in self.pickers.keys():
              if self.pickers[key]['status']:
                  self.pickers[key]['status'] = False
                  self.pickers[key]['selecting'] = False
                  self.can_type = False
                  return {'RUNNING_MODAL'}
          bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
          finish_curve_from_edges(self)
          return {'FINISHED'}
      elif event.type in self.cancel_buttons and event.value == "PRESS":
          for key in self.events:
              if self.events[key]['status']:
                  self.events[key]['cur_value'] = self.first_unchanged_value
                  edit_curves(self, key)
                  if key == 'D':
                    self.strength = self.events[key]['cur_value']
                    set_curves_from_selected(self,context, 'D')
                  elif key == 'T':
                      s = self.events[key]['cur_value']
                      if self.pickers['A']['object']: self.pickers['A']['object'].scale = s,s,s
                  self.events[key]['status'] = not self.events[key]['status']
                  return {'RUNNING_MODAL'}
          for key in self.pickers.keys():
            if self.pickers[key]['status']:
              self.pickers[key]['status'] = False
              self.pickers[key]['selecting'] = False
              return {'RUNNING_MODAL'}
          bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
          remove_cables(self)
          return {'CANCELLED'}
      return {'RUNNING_MODAL'}
  def invoke(self, context, event):
    self.typing = False
    self.can_type = False
    self.my_num_str = ""
    self.context = context
    self.text_ui_rect_batch = {
        "ui_rect": [],
        "items": {},
        "key": None,
        "inside_ui_rect": False,
    }
    self.mesh_objects = context.selected_objects
    self.coord_pairs = []
    for index,ob in enumerate(self.mesh_objects):
      if index != len(self.mesh_objects)-1:
        self.coord_pairs.append([ob.location,self.mesh_objects[index+1].location])
    self.objects, self.strength = curves_from_selected(self, context)
    self.initial_curve_points = []
    self.init_ten = self.strength
    init_curve_points(self)
    set_curves_from_selected(self, context, 'D')
    self.res = 20
    self.bevel_res = 6
    self.twist = 0
    self.width = 0
    self.show_res = True
    self.show_bevel_res = True
    self.show_twist = True
    self.random_tension = .2
    self.active_tool = context.workspace.tools.from_space_view3d_mode("OBJECT", create=False).idname
    self.right_click = 0
    get_prefs(self, context)
    self.show_curve_length = False
    self.button = 'RIGHTMOUSE' if self.right_click == '1' else 'LEFTMOUSE'
    for curve in self.objects:
      curve.data.bevel_depth = self.width
      curve.data.resolution_u = self.res
      curve.data.bevel_resolution = self.bevel_res
    self.title="Create a Cable from Selected Objects."
    self.events = {
        'T': {
            'name': 'Scale Profile (T)',
            'status': False,
            'cur_value': 1,
            'type': 'float',
            'show': False
        },
        'V': {
            'name': 'Bevel Resolution (V)',
            'status': False,
            'cur_value': self.bevel_res,
            'type': 'int',
            'show': self.show_bevel_res
        },
        'F': {
            'name': 'Resolution (F)',
            'status': False,
            'cur_value': self.res,
            'type': 'int',
            'show': self.show_res
        },
        'D': {
            'name': 'Tension (D)',
            'status': False,
            'cur_value': self.strength,
            'type': 'float',
            'show': True
        },
        'S': {
            'name': 'Width (S)',
            'status': False,
            'cur_value': self.width,
            'type': 'float',
            'show': True
        }
    }
    self.bools = {
            'R': {
                'name': 'Remove the Original Meshes (R)',
                'status': False,
                'usable': True,
                'show': True
            },
    }
    if GV.is291:
      self.bools['C'] = {
          'name': 'Fill Caps (C)',
          'status': self.fill_caps,
          'usable': True,
          'show': self.show_fill_caps
      }
      edit_curves(self, 'C')
    init_grab_profile(self, context)
    self.enums = {
        'H': {
            'name': 'Twist Method (H)',
            'status': False,
            'usable': True,
            'cur_value': self.twist,
            'items': [('Z_UP','Z-Up',0),('MINIMUM','Minimum',1),('TANGENT','Tangent',2)],
            'show': self.show_twist
        },
    }
    if self.show_profile_scroll:
        self.enums['B'] = {
            'name': self.enum_scroll_name,
            'status': False,
            'usable': True,
            'cur_value': 0,
            'items': self.profile_scroll_list if self.profile_scroll_switch == 0 else self.profile_scroll_shift_list,
            'show': self.show_grab_profile
        }
    self.bool_functions = {
        'R': self.bool_r,
        'C': self.bool_c,
    }
    self.enum_functions = {
        'H': self.enum_h,
        'B': self.enum_b,
    }
    edit_curves(self, 'H')
    self.actions = {
        'N': {
            'name': 'Randomize Tension (N)',
            'status': True,
            'show': True,
        },
    }
    self.pickers = {
        'A': {
            'name': 'Set Profile (A)',
            'status': False,
            'selecting': False,
            'object': None,
            'show': True,
            'usable': True,
            'vtext': 'Select a curve...'
        }
    }
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
def register():
    bpy.utils.register_class(OBJECT_OT_cablerator_create_cable_from_selected)
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_cablerator_create_cable_from_selected)