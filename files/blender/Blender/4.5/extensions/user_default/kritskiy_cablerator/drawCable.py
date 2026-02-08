import bpy
from .lib import *
from .ui import *
from .inits import *
from .typing import *
class OBJECT_OT_cableratordraw(bpy.types.Operator):
  """Create a curve by drawing it on a surface"""
  bl_idname = "object.cableratordraw"
  bl_label = "Cablerator: Draw a Cable"
  bl_options = {"REGISTER", "UNDO"}
  @classmethod
  def poll(cls, context):
        if not context.area.type == "VIEW_3D": return False
        if context.object:
            return context.object.mode in {'EDIT', 'OBJECT'}
        return True
  def bool_c(self):
    key = 'C'
    edit_curves(self, key)
  def bool_p(self):
    key = 'P'
    if self.bools[key]['status']:
        bpy.ops.curve.select_all(action='DESELECT')
        bpy.ops.wm.tool_set_by_id(name="builtin.pen", cycle=False, space_type='VIEW_3D')
    else: bpy.ops.wm.tool_set_by_id(name="builtin.draw", cycle=False, space_type='VIEW_3D')
  def enum_u(self):
    key = 'U'
    self.context.scene.tool_settings.curve_paint_settings.curve_type = self.enums[key]['items'][self.enums[key]['cur_value']][0]
  def enum_h(self):
    key = 'H'
    edit_curves(self, key)
  def enum_f(self):
    key = 'F'
    self.context.scene.tool_settings.curve_paint_settings.error_threshold = self.enums[key]['items'][self.enums[key]['cur_value']][0]
  def enum_d(self):
    key = 'D'
    self.context.scene.tool_settings.curve_paint_settings.depth_mode = self.enums[key]['items'][self.enums[key]['cur_value']][0]
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
        if event.type == 'MOUSEMOVE':
            handle_hover(self, event)
            if self.poly_finisher:
                if context.scene.tool_settings.curve_paint_settings.curve_type == 'POLY':
                    spline = self.curve.data.splines[-1]
                    spline.points[0].select = False
                    spline.points[-1].select = False
                    bpy.ops.curve.dissolve_verts()
                    spline.points[0].select = True
                    spline.points[-1].select = True
                    bpy.ops.ed.undo_push()
                if self.enums['D']['cur_value'] == 1:
                    get_first_curve_point_on_plane_distance(context)
                self.poly_finisher = False
            if self.left_mouse:
                  self.left_mouse = False
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
                            self.can_type = True
                            self.events[key]['status'] = True
                            self.first_unchanged_value = self.events[key]['cur_value']
                            self.first_value = self.events[key]['cur_value']
                            self.cur_value = self.events[key]['cur_value']
                            edit_curves(self, key)
                    else:
                        self.events[key]['status'] = False
                return {'RUNNING_MODAL'}
        if (event.ctrl or event.oskey) and event.type == 'Y' and event.value == 'PRESS':
            try:
                bpy.ops.ed.redo()
            except Exception as e:
                pass
        elif (event.ctrl or event.oskey) and event.type == 'Z' and event.value == 'PRESS':
            bpy.ops.ed.undo()
            if context.view_layer.objects.active != self.curve:
                bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
                bpy.ops.wm.tool_set_by_id(name=self.active_tool, cycle=False, space_type='VIEW_3D')
                show_hud(self.hud_info)
                return {'CANCELLED'}
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
                        elif key == 'D':
                            self.enum_d()
                        elif key == 'F':
                            self.enum_f()
                        elif key == 'U':
                            self.enum_u()
                        elif 'B' in self.enums and key == 'B':
                            self.enum_b()
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
                        elif 'P' in self.bools and key == 'P':
                            self.bool_p()
                return {'RUNNING_MODAL'}
        if event.type in self.actions.keys() and event.value == "PRESS":
                if self.typing:
                    resolve_typing_numbers(self, event)
                    return {'RUNNING_MODAL'}
                clean_pickers(self)
                clean_events(self)
                for key in self.actions.keys():
                    if event.type == key:
                        if key == 'THREE':
                            loc, normal = main(context, event, self, False)
                            if loc and normal:
                              normal.normalize()
                              context.scene.cursor.location = loc  + normal * self.events['S']['cur_value']
                            else:
                              loc = mouse_to_plane_2000((event.mouse_region_x,event.mouse_region_y), context)
                              if loc:
                                context.scene.cursor.location = loc + Vector((0,0,1)) * self.events['S']['cur_value']
                              pass
                            self.enums['D']['cur_value'] = 1
                            context.scene.tool_settings.curve_paint_settings.depth_mode = 'CURSOR'
                return {'RUNNING_MODAL'}
        if event.type in self.pickers.keys() and event.value == "PRESS":
            if event.alt:
                return {'PASS_THROUGH'}
            clean_pickers(self)
            clean_events(self)
            for key in self.pickers.keys():
                  if event.type == key and self.pickers[key]['usable']:
                      if self.pickers[key]['status']:
                          self.pickers[key]['status'] = False
                          self.pickers[key]['selecting'] = False
                          switch_mode('EDIT')
                      else:
                          self.pickers[key]['status'] = True
                          self.pickers[key]['selecting'] = True
                          switch_mode('OBJECT')
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
        elif event.type == 'MOUSEMOVE':
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
                            if key == 'S':
                                if self.cur_value < 0:
                                    self.cur_value = 0
                                    item['cur_value'] = 0
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
                if GV.is291: self.curve.data.bevel_mode = 'ROUND'
                self.curve.data.bevel_object = None
                self.events['T']['show'] = False
                FontGlobal.column_height = get_column_height(self)
            elif context.view_layer.objects.active.type != 'CURVE':
                self.report({'WARNING'}, f"Profile object should be a Curve, not {context.view_layer.objects.active.type.capitalize()}")
            elif context.view_layer.objects.active.type == 'CURVE' and context.view_layer.objects.active != self.curve:
                self.pickers['A']['status'] = False
                self.pickers['A']['selecting'] = False
                self.pickers['A']['object'] = context.view_layer.objects.active
                if 'B' in self.enums: self.enums['B']['cur_value'] = 0
                if GV.is291: self.curve.data.bevel_mode = 'OBJECT'
                self.curve.data.bevel_object = context.view_layer.objects.active
                self.events['T']['show'] = True
                self.events['T']['cur_value'] = sum(self.pickers['A']['object'].scale)/3
                FontGlobal.column_height = get_column_height(self)
            bpy.ops.object.select_all(action='DESELECT')
            self.curve.select_set(True)
            context.view_layer.objects.active = self.curve
            switch_mode('EDIT')
            bpy.ops.wm.tool_set_by_id(name=self.active_tool, cycle=False, space_type='VIEW_3D')
            return {'RUNNING_MODAL'}
        elif event.type == 'LEFTMOUSE' and event.value == "PRESS":
                if self.text_ui_rect_batch["key"]: return handle_hover_press(self)
                for ev in self.events:
                    if self.events[ev]['status']:
                        self.events[ev]['status'] = not self.events[ev]['status']
                        self.can_type = False
                        return {'RUNNING_MODAL'}
                for key in self.pickers.keys():
                    if self.pickers[key]['status']:
                        self.pickers[key]['status'] = False
                        self.pickers[key]['selecting'] = False
                        self.can_type = False
                        return {'RUNNING_MODAL'}
                self.poly_finisher = True
                self.left_mouse = True
                return {'PASS_THROUGH'}
        elif event.type == 'LEFTMOUSE' and event.value == "RELEASE":
            return {'PASS_THROUGH'}
        elif event.type in self.cancel_buttons_ret and event.shift and event.value == "PRESS":
            self.enums['D']['cur_value'] = 1
            context.scene.tool_settings.curve_paint_settings.depth_mode = 'CURSOR'
            return {'PASS_THROUGH'}
        elif event.type in self.cancel_buttons_ret and event.value == "PRESS":
                if event.type in {"RET","NUMPAD_ENTER"}:
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
                                        self.first_unchanged_value = self.cur_value
                                    else:
                                        self.cur_value = int(self.my_num_str)
                                        item['cur_value'] = self.cur_value
                                        self.first_unchanged_value = self.cur_value
                                except:
                                    pass
                                edit_curves(self, key)
                        return {"RUNNING_MODAL"}
                    elif self.can_type:
                        self.can_type = False
                        clean_events(self)
                        return {"RUNNING_MODAL"}
                for key in self.events:
                    if self.events[key]['status']:
                        self.events[key]['cur_value'] = self.first_unchanged_value
                        if key == 'S':
                            edit_curves(self, key)
                        elif key == 'T':
                            s = self.events[key]['cur_value']
                            if self.pickers['A']['object']: self.pickers['A']['object'].scale = s,s,s
                        self.events[key]['status'] = not self.events[key]['status']
                        return {'RUNNING_MODAL'}
                for key in self.pickers.keys():
                  if self.pickers[key]['status']:
                    self.pickers[key]['status'] = False
                    self.pickers[key]['selecting'] = False
                    switch_mode('EDIT')
                    return {'RUNNING_MODAL'}
                bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
                bpy.ops.wm.tool_set_by_id(name="builtin.select", cycle=False, space_type='VIEW_3D')
                if len(self.curve.data.splines) == 0:
                  switch_mode('OBJECT')
                  bpy.ops.object.delete()
                else:
                  switch_mode('OBJECT')
                  pivot_to_spline_center(self.curve, context)
                  show_hud(self.hud_info)
                return {'FINISHED'}
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
    self.ob = context.object
    self.active_curve = get_active_curve()
    self.title = 'Draw a cable. (Esc to finish)'
    self.right_click = 0
    self.poly_finisher = False
    self.left_mouse = False
    get_prefs(self, context)
    self.hud_info = hide_hud()
    self.show_curve_length = False
    self.button = 'RIGHTMOUSE' if self.right_click == '1' else 'LEFTMOUSE'
    if self.active_curve['width'] == 0 or self.active_curve['width'] == None:
            self.active_curve['width'] = 0.1
    if self.ob and context.object.mode == 'EDIT':
        switch_mode('OBJECT')
    self.active_tool = context.workspace.tools.from_space_view3d_mode("OBJECT", create=False).idname
    curve_name = "Cable"
    curveData = bpy.data.curves.new(curve_name, type='CURVE')
    curveData.dimensions = '3D'
    curveData.dimensions = '2D'
    curveData.dimensions = '3D'
    self.curve = bpy.data.objects.new(curve_name, curveData)
    scn = context.scene
    scn.collection.objects.link(self.curve)
    bpy.ops.object.select_all(action='DESELECT')
    context.view_layer.objects.active = self.curve
    self.curve.select_set(True)
    self.objects = [self.curve]
    curveData.bevel_depth = self.active_curve['width']
    curveData.resolution_u = self.res
    curveData.bevel_resolution = self.bevel_res
    spline = curveData.splines.new('BEZIER')
    switch_mode('EDIT')
    bpy.ops.curve.select_all(action='SELECT')
    bpy.ops.curve.delete(type='VERT')
    self.default_threshold = 0
    bpy.ops.wm.tool_set_by_id(name="builtin.draw", cycle=False, space_type='VIEW_3D')
    context.scene.tool_settings.curve_paint_settings.fit_method = 'SPLIT'
    context.scene.tool_settings.curve_paint_settings.depth_mode = 'SURFACE'
    context.scene.tool_settings.curve_paint_settings.surface_offset = 1
    context.scene.tool_settings.curve_paint_settings.radius_min = 1
    context.scene.tool_settings.curve_paint_settings.radius_max = 1
    context.scene.tool_settings.curve_paint_settings.curve_type = 'BEZIER'
    self.events = {
            'T': {
                  'name': 'Scale Profile (T)',
                  'status': False,
                  'cur_value': 1,
                  'type': 'float',
                  'show': False
            },
            'S': {
                  'name': 'Width (S)',
                  'status': False,
                  'cur_value': self.active_curve['width'],
                  'type': 'float',
                  'show': True
            }
    }
    self.bools = dict()
    if GV.is291:
        self.bools['C'] = {
                'name': 'Fill Caps (C)',
                'status': self.fill_caps,
                'usable': True,
                'show': self.show_fill_caps
        }
        self.curve.data.use_fill_caps = self.fill_caps
    if bpy.app.version >= (3, 2, 0):
        self.use_pen_tool = False
        self.bools['P'] = {
                'name': 'Use Pen Tool (P)',
                'status': self.use_pen_tool,
                'usable': True,
                'show': True
        }
    init_grab_profile(self, context)
    self.enums = {
            'U': {
                  'name': 'Curvature (U)',
                  'status': False,
                  'usable': True,
                  'cur_value': 0,
                  'items': [('BEZIER','Curvy',0),('POLY','Straight',1)],
                  'show': True
            },
            'H': {
                  'name': 'Twist Method (H)',
                  'status': False,
                  'usable': True,
                  'cur_value': self.twist,
                  'items': [('Z_UP','Z-Up',0),('MINIMUM','Minimum',1),('TANGENT','Tangent',2)],
                  'show': True
            },
            'F': {
                  'name': 'Smootheness Preset (F)',
                  'status': False,
                  'usable': True,
                  'cur_value': self.default_threshold,
                  'items': [(8,'So-so (8)',0),(16,'Smooth (16)',1),(32,'Smooooth (32)',2),(4,'Erratic (4)',3)],
                  'show': True
            },
            'D': {
                  'name': 'Pen Depth Mode (D)',
                  'status': False,
                  'usable': True,
                  'cur_value': 0,
                  'items': [('SURFACE','Surface',0),('CURSOR','Cursor',1)],
                  'show': True
            },
    }
    self.bool_functions = {
        'C': self.bool_c,
        'P': self.bool_p,
    }
    self.enum_functions = {
        'U': self.enum_u,
        'H': self.enum_h,
        'F': self.enum_f,
        'D': self.enum_d,
        'B': self.enum_b,
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
    context.scene.tool_settings.curve_paint_settings.error_threshold = self.enums['F']['items'][self.default_threshold][0]
    curveData.twist_mode = self.enums['H']['items'][self.enums['H']['cur_value']][0]
    self.actions = {
            'THREE': {
                  'name': 'Move 3D Cursor to Mouse (3)',
                  'status': True,
                  'show': True,
            },
    }
    self.pickers = {
            'A': {
                  'name': 'Set Profile (A)',
                  'status': False,
                  'selecting': False,
                  'object': self.active_curve['bevel'],
                  'show': True,
                  'usable': True,
                  'vtext': 'Select a curve...'
            }
    }
    if self.active_curve['active']:
            if self.active_curve['bevel']:
                  if GV.is291: self.curve.data.bevel_mode = 'OBJECT'
                  self.curve.data.bevel_object = self.active_curve['bevel']
            elif self.active_curve['bevel'] == None and self.active_curve['active'].data.bevel_depth == 0:
                  self.pickers['A']['object'] = self.active_curve['active']
                  if GV.is291: self.curve.data.bevel_mode = 'OBJECT'
                  self.curve.data.bevel_object = self.active_curve['active']
    if self.pickers['A']['object']:
            self.events['T']['show'] = True
            self.events['T']['cur_value'] = sum(self.pickers['A']['object'].scale)/3
    self.first_mouse_x = event.mouse_x
    self.cur_value = -1
    self.first_value = -1
    self.actual_val = -1
    self.prev_mouse = -1
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
            show_hud(self.hud_info)
            return {'CANCELLED'}
    return {'FINISHED'}
def register():
    bpy.utils.register_class(OBJECT_OT_cableratordraw)
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_cableratordraw)