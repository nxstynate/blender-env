import bpy
from .lib import *
from .ui import *
from .inits import *
from .typing import *
class OBJECT_OT_cablerator(bpy.types.Operator):
    """Create a curve by setting start and finish points"""
    bl_idname = "object.cablerator"
    bl_label = "Cablerator: Create a Cable"
    bl_options = {"REGISTER", "UNDO"}
    use_bevel: bpy.props.BoolProperty(name="Use Bevel", default=False)
    use_method: bpy.props.IntProperty(name="Twist Method", default=-1)
    use_length: bpy.props.FloatProperty(name="Desired Length", default=-1)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ui_vertices = []
        self.vertices = []
    @classmethod
    def poll(cls, context):
        return context.area.type == "VIEW_3D"
    def bool_x(self):
        if self.curve:
            self.curve.show_wire = self.bools['X']['status']
    def bool_c(self):
        if self.curve:
            self.curve.data.use_fill_caps = self.bools['C']['status']
    def enum_h(self):
        edit_curve(self.curve, self.enums['H']['items'][self.enums['H']['cur_value']][0], self.curve_obj, self, 'H')
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
                if self.curve:
                    if GV.is291: self.curve.data.bevel_mode = 'OBJECT' if self.enums[key]['cur_value'] > 0 else 'ROUND'
                    self.curve.data.bevel_object = bpy.data.objects[self.enums[key]['items'][self.enums[key]['cur_value']][0]] if self.enums[key]['cur_value'] > 0 else None
            else:
                data = bpy.data.curves[self.enums[key]['items'][self.enums[key]['cur_value']][0]] if self.enums[key]['cur_value'] > 0 else None
                if self.enums[key]['cur_value'] > 0:
                    if not self.temp_curve:
                        self.temp_curve = bpy.data.objects.new(self.enums[key]['items'][self.enums[key]['cur_value']][1], data)
                        if self.curve:
                            self.temp_curve.location = self.curve.matrix_world.decompose()[0]
                        bpy.context.scene.collection.objects.link(self.temp_curve)
                    else:
                        if self.curve:
                            self.temp_curve.location = self.curve.matrix_world.decompose()[0]
                        self.temp_curve.data = data
                        self.temp_curve.name = self.enums[key]['items'][self.enums[key]['cur_value']][1]
                self.pickers['A']['object'] = self.temp_curve if self.enums[key]['cur_value'] > 0 else None
                if self.curve:
                    if GV.is291: self.curve.data.bevel_mode = 'OBJECT' if self.enums[key]['cur_value'] > 0 else 'ROUND'
                    self.curve.data.bevel_object = self.temp_curve if self.enums[key]['cur_value'] > 0 else None
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
            event_type=event.type
            self.first_mouse_x = event.mouse_x
            for key in self.events.keys():
                if event.type == 'W' and self.is_shift: event_type = 'sW'
                if event.type == 'E' and self.is_shift: event_type= 'sE'
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
                else:
                    self.events[key]['status'] = False
            return {'RUNNING_MODAL'}
        if event.type in self.bools.keys() and event.value == "PRESS":
            clean_pickers(self)
            clean_events(self)
            for key in self.bools.keys():
                if event.type == key:
                    self.bools[key]['status'] = not self.bools[key]['status']
                    if key == 'X':
                        self.bool_x()
                    elif 'C' in self.bools and key == 'C':
                        self.bool_c()
            return {'RUNNING_MODAL'}
        if event.type in self.actions.keys() and event.value == "PRESS":
            clean_pickers(self)
            clean_events(self)
            for key in self.actions.keys():
                if event.type == key:
                    if key == 'Q' and self.actions[key]['status']:
                        bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
                        if self._draw_handler3d:
                            self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler3d, 'WINDOW')
                        add_point(self.curve, context, self.events['G']['cur_value'])
                        bpy.ops.object.cablerator('INVOKE_DEFAULT', use_bevel=self.pickers['A']['status'], use_method = self.enums['H']['cur_value'], use_length = self.curve_length)
                        clean_temp(self)
                        return {'FINISHED'}
            return {'RUNNING_MODAL'}
        if event.type in self.enums.keys() and event.value == "PRESS":
            clean_pickers(self)
            clean_events(self)
            for key in self.enums.keys():
                if event.type == key:
                    change_enum_curvalue(self, key)
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
            if self.curve:
                self.curve.data.bevel_depth = self.events['S']['cur_value']
          elif self.events['sW']['status']:
            self.events['sW']['cur_value'] = normal_round((self.events['sW']['cur_value'] + wheel_val)*10)/10
            if self.events['sW']['cur_value'] < 0: self.events['sW']['cur_value'] = 0
            self.first_value = self.events['sW']['cur_value']
            self.first_unchanged_value = self.events['sW']['cur_value']
            self.cur_value = self.events['sW']['cur_value']
            self.first_mouse_x = event.mouse_x
            if self.curve:
                edit_curve(self.curve, self.events['sW']['cur_value'], self.curve_obj, self, 'sW')
          elif self.events['sE']['status']:
            self.events['sE']['cur_value'] = normal_round((self.events['sE']['cur_value'] + wheel_val)*10)/10
            if self.events['sE']['cur_value'] < 0: self.events['sE']['cur_value'] = 0
            self.first_value = self.events['sE']['cur_value']
            self.first_unchanged_value = self.events['sE']['cur_value']
            self.cur_value = self.events['sE']['cur_value']
            self.first_mouse_x = event.mouse_x
            if self.curve:
                edit_curve(self.curve, self.events['sE']['cur_value'], self.curve_obj, self, 'sE')
          elif self.events['D']['status']:
            self.events['D']['cur_value'] = normal_round((self.events['D']['cur_value'] + wheel_val*4)*2.5)/2.5
            if self.events['D']['cur_value'] < 0.01: self.events['D']['cur_value'] = 0.01
            self.first_value = self.events['D']['cur_value']
            self.first_unchanged_value = self.events['D']['cur_value']
            self.cur_value = self.events['D']['cur_value']
            self.first_mouse_x = event.mouse_x
            if self.curve:
               edit_curve(self.curve, self.events['D']['cur_value'], self.curve_obj, self, 'D')
               self.init_ten = self.events['D']['cur_value']
          elif self.events['F']['status']:
            self.events['F']['cur_value'] += int(wheel_val*10)
            if self.events['F']['cur_value'] < 1: self.events['F']['cur_value'] = 1
            self.first_value = self.events['F']['cur_value']
            self.first_unchanged_value = self.events['F']['cur_value']
            self.cur_value = self.events['F']['cur_value']
            self.first_mouse_x = event.mouse_x
            if self.curve:
                edit_curve(self.curve, self.events['F']['cur_value'], self.curve_obj, self, 'F')
          elif self.events['G']['status']:
            self.events['G']['cur_value'] += int(wheel_val*10)
            if self.events['G']['cur_value'] < 0: self.events['G']['cur_value'] = 0
            self.first_value = self.events['G']['cur_value']
            self.first_unchanged_value = self.events['G']['cur_value']
            self.cur_value = self.events['G']['cur_value']
            self.first_mouse_x = event.mouse_x
          elif self.events['V']['status']:
            self.events['V']['cur_value'] += int(wheel_val*10)
            if self.events['V']['cur_value'] < 0: self.events['V']['cur_value'] = 0
            self.first_value = self.events['V']['cur_value']
            self.first_unchanged_value = self.events['V']['cur_value']
            self.cur_value = self.events['V']['cur_value']
            self.first_mouse_x = event.mouse_x
            if self.curve:
                edit_curve(self.curve, self.events['V']['cur_value'], self.curve_obj, self, 'V')
          elif self.events['W']['status']:
            self.events['W']['cur_value'] = normal_round((self.events['W']['cur_value'] + wheel_val*50)*.2)/.2
            if self.events['W']['cur_value'] < 0: self.events['W']['cur_value'] = 0
            self.first_value = self.events['W']['cur_value']
            self.first_unchanged_value = self.events['W']['cur_value']
            self.cur_value = self.events['W']['cur_value']
            self.first_mouse_x = event.mouse_x
            if self.curve:
                edit_curve(self.curve, self.events['W']['cur_value'], self.curve_obj, self, 'W')
          elif self.events['E']['status']:
            self.events['E']['cur_value'] = normal_round((self.events['E']['cur_value'] + wheel_val*50)*.2)/.2
            if self.events['E']['cur_value'] < 0: self.events['E']['cur_value'] = 0
            self.first_value = self.events['E']['cur_value']
            self.first_unchanged_value = self.events['E']['cur_value']
            self.cur_value = self.events['E']['cur_value']
            self.first_mouse_x = event.mouse_x
            if self.curve:
                edit_curve(self.curve, self.events['E']['cur_value'], self.curve_obj, self, 'E')
          elif self.events['T']['status'] and self.pickers['A']['object']:
             self.events['T']['cur_value'] = normal_round((self.events['T']['cur_value'] + wheel_val)*10)/10
             if self.events['T']['cur_value'] < 0: self.events['T']['cur_value'] = 0
             self.first_value = self.events['T']['cur_value']
             self.first_unchanged_value = self.events['T']['cur_value']
             self.cur_value = self.events['T']['cur_value']
             self.first_mouse_x = event.mouse_x
             s = self.events['T']['cur_value']
             if self.curve:
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
                        if self.curve:
                            edit_curve(self.curve, item['cur_value'], self.curve_obj, self, key)
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
                        delta = 1200 if key not in {'W','E'} else 25
                    else:
                        delta = 120 if key not in {'W','E'} else 5
                    if item['type'] != 'int' and key not in {'W','E'}:
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
                        if key == 'S':
                            if self.cur_value < 0:
                                self.cur_value = 0
                                item['cur_value'] = 0
                            if self.curve:
                                edit_curve(self.curve, item['cur_value'], self.curve_obj, self, key)
                        elif key == 'D':
                            if self.cur_value < 0.0001:
                                self.cur_value = 0.0001
                                item['cur_value'] = 0.0001
                            if self.curve:
                                edit_curve(self.curve, item['cur_value'], self.curve_obj, self, key)
                                self.init_ten = item['cur_value']
                        elif key == 'G':
                            if self.cur_value < 0:
                                self.cur_value = 0
                                item['cur_value'] = 0
                        elif key == 'F':
                            if self.cur_value < 1:
                                self.cur_value = 1
                                item['cur_value'] = 1
                            if self.curve:
                                edit_curve(self.curve, item['cur_value'], self.curve_obj, self, key)
                        elif key == 'V':
                            if self.cur_value < 0:
                                self.cur_value = 0
                                item['cur_value'] = 0
                            if self.curve:
                                edit_curve(self.curve, item['cur_value'], self.curve_obj, self, key)
                        elif key == 'W' or key == 'E':
                            if self.curve:
                                edit_curve(self.curve, item['cur_value'], self.curve_obj, self, key)
                        elif key == 'T' and self.pickers['A']['object']:
                            if self.curve:
                                edit_curve(self.curve, item['cur_value'], self.curve_obj, self, key)
                        elif key == 'sW' or key == 'sE':
                            if self.curve:
                                edit_curve(self.curve, item['cur_value'], self.curve_obj, self, key)
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
            if self.curve:
                if GV.is291: self.curve.data.bevel_mode = 'ROUND'
                self.curve.data.bevel_object = None
            self.events['T']['show'] = False
            FontGlobal.column_height = get_column_height(self)
            FontGlobal.column_width = get_column_width(self, FontGlobal.font_id, FontGlobal.size, FontGlobal.dpi)[0]
          elif context.view_layer.objects.active.type != 'CURVE':
            self.report({'WARNING'}, f"Profile object should be a Curve, not {context.view_layer.objects.active.type.capitalize()}")
          elif context.view_layer.objects.active.type == 'CURVE' and context.view_layer.objects.active != self.curve:
            self.pickers['A']['status'] = False
            self.pickers['A']['selecting'] = False
            self.pickers['A']['object'] = context.view_layer.objects.active
            if 'B' in self.enums: self.enums['B']['cur_value'] = 0
            if self.curve:
                if GV.is291: self.curve.data.bevel_mode = 'OBJECT'
                self.curve.data.bevel_object = context.view_layer.objects.active
            self.events['T']['show'] = True
            self.events['T']['cur_value'] = sum(self.pickers['A']['object'].scale)/3
            FontGlobal.column_height = get_column_height(self)
            FontGlobal.column_width = get_column_width(self, FontGlobal.font_id, FontGlobal.size, FontGlobal.dpi)[0]
          bpy.ops.object.select_all(action='DESELECT')
          if self.curve:
            self.curve.select_set(True)
            context.view_layer.objects.active = self.curve
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
            if self.finished:
                bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
                if self._draw_handler3d:
                    self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler3d, 'WINDOW')
                add_point(self.curve, context, self.events['G']['cur_value'])
                if self.show_join_points and self.bools['J']['status']:
                    join_new_cable(self)
                clean_temp(self)
                return {'FINISHED'}
            if self.mouse_click < 2:
                self.mouse_click += 1
                self.curve_obj['point' + str(self.mouse_click)] = main(context, event, self, True)
                if self.curve_obj['point' + str(self.mouse_click)][1] == None:
                    self.report({'ERROR'}, "Point wasn't registered, aborting")
                    bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
                    if self._draw_handler3d:
                        self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler3d, 'WINDOW')
                    if self.temp_curve:
                        bpy.data.objects.remove(self.temp_curve, do_unlink=True)
                        remove_userless_curves()
                    return {'CANCELLED'}
                else:
                    self.status['point' + str(self.mouse_click)]['status'] = True
                if self.mouse_click == 2:
                    if self._draw_handler3d:
                        self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler3d, 'WINDOW')
                    finish_clicks(self)
            elif self.mouse_click == 2:
                if self._draw_handler3d:
                    self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler3d, 'WINDOW')
                finish_clicks(self)
        elif event.type in self.cancel_buttons and event.value == "PRESS":
            for key in self.events:
                if self.events[key]['status']:
                    self.events[key]['cur_value'] = self.first_unchanged_value
                    if key == 'S':
                        self.curve.data.bevel_depth = self.events[key]['cur_value']
                    elif key == 'D':
                        edit_curve(self.curve, self.events[key]['cur_value'], self.curve_obj, self, key)
                    elif key == 'G':
                        if self.cur_value < 0:
                            self.cur_value = 0
                            self.events[key]['cur_value'] = 0
                    elif key == 'F':
                        edit_curve(self.curve, self.events[key]['cur_value'], self.curve_obj, self, key)
                    elif key == 'W' or key == 'E':
                        edit_curve(self.curve, self.events[key]['cur_value'], self.curve_obj, self, key)
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
            if self._draw_handler3d:
                self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler3d, 'WINDOW')
            if self.finished:
                bpy.data.objects.remove(self.curve, do_unlink=True)
            if self.temp_curve:
                bpy.data.objects.remove(self.temp_curve, do_unlink=True)
                remove_userless_curves()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
    def create_batch3d(self):
        self.shader3d = create_3d_shader()
        self.batch3d = batch_for_shader(self.shader3d, 'POINTS', {"pos": self.vertices})
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
        selected_points = init_points()
        if len(selected_points) > 2:
            self.report({'ERROR'}, "Expected to find maximum 2 curve points selected, found " + str(len(selected_points)))
            return {'CANCELLED'}
        self.context = context
        self.mouse_click = 0
        self.curve_obj = {
            'point1': [],
            'point2': [],
            'created_from_init1': False,
            'created_from_init2': False,
            'ob1': None,
            'ob2': None,
        }
        self.additional_data = {
            'point1': [],
            'point2': [],
        }
        self.title="Create a cable."
        self.active_tool = context.workspace.tools.from_space_view3d_mode("OBJECT", create=False).idname
        self.prev_show = True
        self.subdivisions = 1
        self.show_subdivisions = True
        self.res = 20
        self.bevel_res = 6
        self.show_res = True
        self.strength = 1
        self.init_tens = -1
        self.curve_length = -1
        self.twist = 0
        self.show_twist = True
        self.show_wire = True
        self.show_tilt = False
        self.show_offset = False
        self.bevel = 0.1
        self.curve = None
        self.finished = False
        self.active_curve = get_active_curve()
        self.show_curve_length = False
        self.random_tension = .2
        self.right_click = 0
        get_prefs(self, context)
        temp_res = self.res
        temp_bevel_res = self.bevel_res
        self.button = 'RIGHTMOUSE' if self.right_click == '1' else 'LEFTMOUSE'
        if self.active_curve['width'] == 0 or self.active_curve['width'] == None:
            self.active_curve['width'] = 0.1
        if self.active_curve['res'] != None:
            self.res = self.active_curve['res']
        if self.active_curve['bevel_res'] != None:
            self.bevel_res = self.active_curve['bevel_res']
        self.init_handles = dict()
        self.init_points = dict()
        self.events = {
            'T': {
                'name': 'Scale Profile (T)',
                'status': False,
                'cur_value': 1,
                'type': 'float',
                'show': False
            },
            'sE': {
                'name': 'Offset Point 2 (⇧E)',
                'status': False,
                'cur_value': 0,
                'type': 'float',
                'show': self.show_offset
            },
            'sW': {
                'name': 'Offset Point 1 (⇧W)',
                'status': False,
                'cur_value': 0,
                'type': 'float',
                'show': self.show_offset
            },
            'E': {
                'name': 'Tilt Point 2 (E)',
                'status': False,
                'cur_value': 0,
                'type': 'float',
                'show': self.show_tilt
            },
            'W': {
                'name': 'Tilt Point 1 (W)',
                'status': False,
                'cur_value': 0,
                'type': 'float',
                'show': self.show_tilt
            },
            'G': {
                'name': 'Add Points (G)',
                'status': False,
                'cur_value': self.subdivisions,
                'type': 'int',
                'show': self.show_subdivisions
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
                'cur_value': self.active_curve['width'],
                'type': 'float',
                'show': True
            }
        }
        init_grab_profile(self, context)
        self.enums = {
            'H': {
                'name': 'Twist Method (H)',
                'status': False,
                'usable': True,
                'cur_value': self.twist,
                'items': [('Z_UP','Z-Up',0),('MINIMUM','Minimum',1),('TANGENT','Tangent',2)],
                'show': self.show_twist
            }
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
        self.bools = {
                'X': {
                    'name': 'Show Wire (X)',
                    'status': False,
                    'usable': True,
                    'show': self.show_wire
                },
        }
        if GV.is291:
          self.bools['C'] = {
              'name': 'Fill Caps (C)',
              'status': self.fill_caps,
              'usable': True,
              'show': self.show_fill_caps
          }
        self.bool_functions = {
            'X': self.bool_x,
            'C': self.bool_c,
        }
        self.enum_functions = {
            'H': self.enum_h,
            'B': self.enum_b,
        }
        self.status = {
            'point2': {
                'name': 'Point 2',
                'status': False
            },
            'point1': {
                'name': 'Point 1',
                'status': False
            },
        }
        self.actions = {
            'Q': {
                'name': 'Create Another (Q)',
                'status': False,
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
            if self.active_curve['bevel'] == None and self.active_curve['active'].data.bevel_depth == 0:
                self.pickers['A']['object'] = self.active_curve['active']
                self.res = temp_res;
                self.bevel_res = temp_bevel_res
                self.events['F']['cur_value'] = self.res
                self.events['V']['cur_value'] = self.bevel_res
        if self.pickers['A']['object']:
            self.events['T']['show'] = True
            self.events['T']['cur_value'] = sum(self.pickers['A']['object'].scale)/3
        if len(selected_points) >= 1:
            self.curve_obj['point1'] = (selected_points[0]['co'], selected_points[0]['start'])
            self.curve_obj['created_from_init1'] = True
            self.curve_obj['ob1'] = selected_points[0]['object']
            self.additional_data['point1'] = [
                selected_points[0]['tilt'],
                selected_points[0]['radius'],
            ]
            self.events['W']['cur_value'] = math.degrees(selected_points[0]['tilt'])
            self.status['point1']['status'] = True
            self.mouse_click = 1
        if len(selected_points) == 2:
            self.curve_obj['point2'] = (selected_points[1]['co'], selected_points[1]['finish'])
            self.curve_obj['created_from_init2'] = True
            self.curve_obj['ob2'] = selected_points[1]['object']
            self.additional_data['point2'] = [
                selected_points[1]['tilt'],
                selected_points[1]['radius'],
            ]
            self.events['E']['cur_value'] = math.degrees(selected_points[1]['tilt'])
            self.status['point2']['status'] = True
            self.mouse_click = 2
        self.show_join_points = False
        if self.curve_obj['created_from_init1']:
            self.show_join_points = True
            self.bools['J'] = {
                'name': 'Join With Selected Points (J)',
                'status': True,
                'show': True,
                'usable': True,
            }
            if GV.is291:
                key_order = ('J', 'C', 'X')
            else:
                key_order = ('J', 'X')
            self.bools = dict((k, self.bools[k]) for k in key_order)
        self.first_mouse_x = event.mouse_x
        self.cur_value = -1
        self.first_value = -1
        self.first_unchanged_value = -1
        self.is_shift = False
        self.is_ctrl = False
        self.reg = get_view(context, event.mouse_x, event.mouse_y)
        init_font_settings(self)
        if self.mouse_click == 2:
            finish_clicks(self)
        if context.space_data.type == 'VIEW_3D':
            self.init_area = context.area
            self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, (self, context), 'WINDOW', 'POST_PIXEL')
            self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_add(draw_callback_3d, (self, context), 'WINDOW', 'POST_VIEW')
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            if self._draw_handler3d:
                self._draw_handler3d = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler3d, 'WINDOW')
            return {'CANCELLED'}
def menu_func(self, context):
    self.layout.operator_context = 'INVOKE_DEFAULT'
    myop = self.layout.operator("object.cablerator")
    myop.use_bevel=False
    myop.use_method=-1
    myop.use_length=-1
def register():
    bpy.utils.register_class(OBJECT_OT_cablerator)
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_cablerator)
