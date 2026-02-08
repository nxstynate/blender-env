import bpy
from .lib import *
from .ui import *
from .inits import *
from .typing import *
class OBJECT_OT_cablerator_geocable(bpy.types.Operator):
  """Select an object and paths in Object mode"""
  bl_idname = "object.cablerator_geocable"
  bl_label = "Cablerator: Convert to Mesh Cable"
  bl_options = {"REGISTER", "UNDO"}
  @classmethod
  def poll(cls, context):
    return context.area.type == "VIEW_3D" and len(context.selected_objects) > 1 and context.object.mode == 'OBJECT'
  def resolve_e_key(self, item):
    for clone in self.clones:
      for mod in clone.modifiers:
        if mod.type == 'ARRAY':
          mod.constant_offset_displace[2] = item['cur_value'] + self.init_dimension
          if not self.zero_mesh:
            self.events['D']['cur_value'] = mod.relative_offset_displace[2] = mod.constant_offset_displace[2] / self.init_dimension
  def resolve_f_key(self, item):
    for clone in self.clones:
      clone.matrix_world = local_mw_rotate('Z', clone.matrix_world, item['cur_value'])
  def resolve_s_key(self, item, event):
    if item['cur_value'] < 0:
      self.cur_value = 0
      self.first_mouse_x = event.mouse_x
      item['cur_value'] = 0
    for curve in self.objects['curves']:
      curve.data.bevel_depth = item['cur_value']
  def resolve_w_key(self, item):
    for clone in self.clones:
      for mod in clone.modifiers:
        if mod.type == 'DISPLACE':
          mod.strength = item['cur_value']
  def resolve_d_key(self, item):
    for clone in self.clones:
      for mod in clone.modifiers:
        if mod.type == 'ARRAY':
          mod.relative_offset_displace[2] = item['cur_value']
          self.events['E']['cur_value'] = self.init_dimension * item['cur_value'] - self.init_dimension
          mod.constant_offset_displace[2] = self.init_dimension * item['cur_value']
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
                  if key == 'E':
                    for clone in self.clones:
                      for mod in clone.modifiers:
                        if mod.type == 'ARRAY':
                          mod.use_relative_offset = False
                          mod.use_constant_offset = True
                  elif 'D' in self.events and key == 'D' and not self.zero_mesh:
                    for clone in self.clones:
                      for mod in clone.modifiers:
                        if mod.type == 'ARRAY':
                          mod.use_relative_offset = True
                          mod.use_constant_offset = False
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
        if self.events['E']['status']:
          item = self.events['E']
          item['cur_value'] = normal_round((item['cur_value'] + wheel_val)*10)/10
          self.first_value = item['cur_value']
          self.first_unchanged_value = item['cur_value']
          self.cur_value = item['cur_value']
          self.first_mouse_x = event.mouse_x
          self.resolve_e_key(item)
        elif 'D' in self.events and self.events['D']['status'] and not self.zero_mesh:
          item = self.events['D']
          item['cur_value'] = normal_round((item['cur_value'] + wheel_val)*10)/10
          self.first_value = item['cur_value']
          self.first_unchanged_value = item['cur_value']
          self.cur_value = item['cur_value']
          self.first_mouse_x = event.mouse_x
          self.resolve_d_key(item)
        elif 'W' in self.events and self.events['W']['status']:
          item = self.events['W']
          item['cur_value'] = normal_round((item['cur_value'] + wheel_val)*10)/10
          self.first_value = item['cur_value']
          self.first_unchanged_value = item['cur_value']
          self.cur_value = item['cur_value']
          self.first_mouse_x = event.mouse_x
          self.resolve_w_key(item)
        elif self.events['F']['status']:
          item = self.events['F']
          item['cur_value'] = int(normal_round((item['cur_value'] + wheel_val*50)*.2)/.2)
          self.first_value = item['cur_value']
          self.first_unchanged_value = item['cur_value']
          self.cur_value = item['cur_value']
          self.first_mouse_x = event.mouse_x
          self.resolve_f_key(item)
        elif self.events['S']['status']:
          item = self.events['S']
          item['cur_value'] = normal_round((item['cur_value'] + wheel_val)*10)/10
          if item['cur_value'] < 0: item['cur_value'] = 0
          self.first_value = item['cur_value']
          self.first_unchanged_value = item['cur_value']
          self.cur_value = item['cur_value']
          self.first_mouse_x = event.mouse_x
          self.resolve_s_key(item, event)
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
                      if key == 'E':
                        self.resolve_e_key(item)
                      elif key == 'D' and not self.zero_mesh:
                        self.resolve_d_key(item)
                      elif key == 'F':
                        self.resolve_f_key(item)
                      elif key == 'S':
                        self.resolve_s_key(item, event)
                      elif 'W' in self.events and key =='W':
                        self.resolve_w_key(item)
          else:
              self.can_type = False
              clean_events(self)
      elif event.type == 'MOUSEMOVE':
          if self.typing: return {'RUNNING_MODAL'}
          for key in self.events.keys():
              item = self.events[key]
              if item['status']:
                  if self.is_shift:
                      delta = 1200 if key != 'F' else 50
                  else:
                      delta = 120 if key != 'F' else 10
                  if item['type'] != 'int' and key not in {'F','D','E'}:
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
                      if key == 'E':
                        self.resolve_e_key(item)
                      elif key == 'D' and not self.zero_mesh:
                        self.resolve_d_key(item)
                      elif key == 'F':
                        self.resolve_f_key(item)
                      elif key == 'S':
                        self.resolve_s_key(item, event)
                      elif 'W' in self.events and key =='W':
                        self.resolve_w_key(item)
      elif event.type == 'LEFTMOUSE' and event.value == "PRESS":
          for ev in self.events:
              if self.events[ev]['status']:
                  self.events[ev]['status'] = not self.events[ev]['status']
                  return {'RUNNING_MODAL'}
          bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
          self.finish_geo_cables()
          return {'FINISHED'}
      elif event.type in self.cancel_buttons and event.value == "PRESS":
          for key in self.events:
              if self.events[key]['status']:
                  self.events[key]['cur_value'] = self.first_unchanged_value
                  if key == 'E':
                    for clone in self.clones:
                      for mod in clone.modifiers:
                        if mod.type == 'ARRAY':
                          mod.constant_offset_displace[2] = self.events[key]['cur_value'] + self.init_dimension
                          if not self.zero_mesh:
                            self.events['D']['cur_value'] = mod.relative_offset_displace[2] = self.events[key]['cur_value'] / self.init_dimension
                  elif key == 'D' and not self.zero_mesh:
                    for clone in self.clones:
                      for mod in clone.modifiers:
                        if mod.type == 'ARRAY':
                          mod.relative_offset_displace[2] = self.events[key]['cur_value']
                          self.events['E']['cur_value'] = self.init_dimension * self.events[key]['cur_value'] - self.init_dimension
                          mod.constant_offset_displace[2] = self.init_dimension * self.events[key]['cur_value']
                  elif key == 'F':
                      for clone in self.clones:
                        clone.rotation_euler[2] = radians(self.events[key]['cur_value'])
                  elif 'W' in self.events and key == 'W':
                      for clone in self.clones:
                         for mod in clone.modifiers:
                           if mod.type == 'DISPLACE':
                             mod.strength = self.events[key]['cur_value']
                  elif key == 'S':
                    for curve in self.objects['curves']:
                      curve.data.bevel_depth = self.events[key]['cur_value']
                  self.events[key]['status'] = not self.events[key]['status']
                  return {'RUNNING_MODAL'}
          bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
          self.finish_geo_cables()
          return {'FINISHED'}
      return {'RUNNING_MODAL'}
  def finish_geo_cables(self):
    for index, curve in enumerate(self.objects['curves']):
      bpy.ops.object.select_all(action='DESELECT')
      self.clones[index].select_set(True)
      curve.select_set(True)
      bpy.context.view_layer.objects.active = self.clones[index]
      if self.parent_connectors:
        try:
          bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
        except Exception as e:
          self.report({'ERROR'}, str(e))
    bpy.ops.object.select_all(action='DESELECT')
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
    self.ob = context.view_layer.objects.active
    self.clones = []
    try:
      self.objects = geo_sort_objects(context.selected_objects, self.ob)
    except Exception as e:
      self.report({'ERROR'}, str(e))
      return {'CANCELLED'}
    if self.objects['ob'].data.users != 1 and self.objects['ob'].scale != Vector((1,1,1)):
      self.report({'ERROR'}, 'Seleted mesh object has multiple users and has unapplied scale. Please select an unique or unscaled object. Aborting')
      return {'CANCELLED'}
    elif self.objects['ob'].data.users == 1 and self.objects['ob'].scale != Vector((1,1,1)):
      bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for curve in self.objects['curves']:
      curve.data.use_path = False
    mesh_cable, m_arr, m_curve, m_displ_o, m_arr_caps, existing_array, solid_mod = is_mesh_cable(self.objects['ob'])
    self.zero_mesh = False
    self.init_dimension = get_dimensions(self.objects['ob'])[2]
    remove_ob_clone = False
    for index, curve in enumerate(self.objects['curves']):
      profile_clone = self.objects['ob'].copy()
      scn = context.scene
      profile_clone.data = self.objects['ob'].data
      scn.collection.objects.link(profile_clone)
      profile_clone.name = self.objects['ob'].name + '_' + ('%02d' % (index + 1))
      profile_clone.location = curve.location
      profile_clone.rotation_euler = curve.rotation_euler
      context.view_layer.objects.active = profile_clone
      if not m_displ_o and profile_clone.type == 'MESH':
        m_displ = profile_clone.modifiers.new(name='Displace',type='DISPLACE')
        m_displ.strength = 0
        m_displ.direction = 'Z'
        m_displ.show_expanded = False
      else:
        m_displ = m_displ_o
      while profile_clone.modifiers.find('Displace') > 0:
        bpy.ops.object.modifier_move_up(modifier='Displace')
      if not mesh_cable:
        m_arr = profile_clone.modifiers.new(name='Array',type='ARRAY')
        m_arr.fit_type = 'FIT_CURVE'
        m_arr.constant_offset_displace[2] = profile_clone.dimensions[2]
        m_arr.relative_offset_displace[2] = 1
        m_arr.relative_offset_displace[1] = 0
        m_arr.relative_offset_displace[0] = 0
        m_arr.constant_offset_displace[2] = 0
        m_arr.constant_offset_displace[1] = 0
        m_arr.constant_offset_displace[0] = 0
        if existing_array:
          m_arr.relative_offset_displace[2] = 0
          if 'use_relative_offset' in existing_array:
            m_arr.use_relative_offset = True
            m_arr.relative_offset_displace[2] = existing_array['use_relative_offset']
          if 'use_constant_offset' in existing_array:
            m_arr.use_relative_offset = True
            if self.init_dimension != 0:
              m_arr.relative_offset_displace[2] += existing_array['use_constant_offset'] / self.init_dimension
          if 'use_object_offset' in existing_array:
            m_arr.use_object_offset = True
            remove_ob_clone = True
            offset_object_clone = duplicate_object(existing_array['use_object_offset'])
            m_arr.offset_object = offset_object_clone
            offset_object_clone.location = curve.location
        if self.objects['cap_start']:
          m_arr.start_cap = self.objects['cap_start']
          self.objects['cap_start'].hide_viewport = True
          self.objects['cap_start'].hide_render = True
        if self.objects['cap_end']:
          m_arr.end_cap = self.objects['cap_end']
          self.objects['cap_end'].hide_viewport = True
          self.objects['cap_end'].hide_render = True
        if bpy.app.version >= (2, 82, 0):
            m_weld = profile_clone.modifiers.new(name='Weld',type='WELD')
            m_weld.show_expanded = False
            weld_index = profile_clone.modifiers.find('Weld')
            counter = 0
            if solid_mod:
              while profile_clone.modifiers.find(solid_mod.name) != weld_index:
                counter = counter + 1
                if counter > 50: break
                bpy.ops.object.modifier_move_down(modifier=solid_mod.name)
        m_curve = profile_clone.modifiers.new(name='Curve',type='CURVE')
        m_curve.deform_axis = 'POS_Z'
      else:
        for mod in profile_clone.modifiers:
          if mod.type == 'ARRAY':
            m_arr = mod
            if 'use_object_offset' in existing_array:
              offset_object_clone = duplicate_object(existing_array['use_object_offset'])
              m_arr.offset_object = offset_object_clone
              offset_object_clone.location = curve.location
          elif mod.type == 'CURVE':
            m_curve = mod
      m_arr.curve = curve
      m_curve.object = curve
      if len(m_arr_caps):
        m_arr.start_cap = m_arr_caps[0]
        m_arr.end_cap = m_arr_caps[1]
      self.clones.append(profile_clone)
    if remove_ob_clone:
      super_remove(existing_array['use_object_offset'], context)
    objs = bpy.data.objects
    if self.init_dimension == 0:
      self.zero_mesh = True
      for clone in self.clones:
        for mod in clone.modifiers:
          if mod.type == 'ARRAY':
            mod.use_relative_offset = False
            mod.use_constant_offset = True
            mod.constant_offset_displace[2] = 0.5
    else:
      if not mesh_cable:
        for clone in self.clones:
          for mod in clone.modifiers:
            if mod.type == 'ARRAY':
              if mod.use_relative_offset:
                mod.constant_offset_displace[2] = mod.relative_offset_displace[2] * self.init_dimension
              else:
                mod.constant_offset_displace[2] = self.init_dimension
    if not mesh_cable:
      objs.remove(self.objects['ob'], do_unlink=True)
    else:
      self.objects['ob'].select_set(False)
    self.context = context
    self.finished = False
    self.prev_rotation = 0
    self.rotation_deg = 0
    self.prev_sign = 0
    self.prev_mouse = -1
    self.actual_val = 0
    self.curve_length = -1
    self.show_curve_length = False
    self.title="Create Mesh Cable."
    self.events = {
        'F': {
            'name': 'Tilt Cable (F)',
            'status': False,
            'cur_value': 0,
            'type': 'int',
            'show': True
        },
        'E': {
            'name': 'Constant Clones Offset (E)',
            'status': False,
            'cur_value': self.init_dimension * m_arr.relative_offset_displace[2] - self.init_dimension,
            'type': 'float',
            'show': True
        },
        'S': {
            'name': 'Original Curve Width (S)',
            'status': False,
            'cur_value': self.objects['curves'][0].data.bevel_depth,
            'type': 'float',
            'show': True
        },
    }
    if self.clones[0].type == 'MESH':
      self.events['W'] = {
          'name': 'Offset Cable (W)',
          'status': False,
          'cur_value': m_displ.strength,
          'type': 'float',
          'show': True
      }
      key_order = ('F', 'W', 'E', 'S')
      self.events = dict((k, self.events[k]) for k in key_order)
    if not self.zero_mesh:
      self.events['D'] = {
            'name': 'Relative Clones Offset (D)',
            'status': False,
            'cur_value': m_arr.relative_offset_displace[2],
            'type': 'float',
            'show': True
        }
      key_order = ('F', 'W', 'E', 'D', 'S') if self.clones[0].type == 'MESH' else  ('F', 'E', 'D', 'S')
      self.events = dict((k, self.events[k]) for k in key_order)
    else:
      self.events['E']['cur_value'] = .5
    self.parent_connectors = True
    get_prefs(self, context)
    self.show_curve_length = False
    self.first_mouse_x = event.mouse_x
    self.cur_value = -1
    self.first_unchanged_value = -1
    self.first_value = -1
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
    bpy.utils.register_class(OBJECT_OT_cablerator_geocable)
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_cablerator_geocable)