import bpy
import sys
from .lib import *
from .ui import *
from .inits import *
from .typing import *
from mathutils.geometry import intersect_line_plane as ilp
import numpy as np
class OBJECT_OT_cablerator_helper_add_point(bpy.types.Operator):
    """Click on a bezier path
X to dissolve the closes point"""
    bl_idname = "object.cablerator_helper_add_point"
    bl_label = "Cablerator: Add/Remove a Bezier Point at Mouse Cursor"
    bl_options = {"REGISTER", "UNDO"}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vert = [-10, -10, -10]
    def create_batch3d(self):
        self.shader3d = create_3d_shader()
        self.batch3d = batch_for_shader(self.shader3d, 'POINTS', {"pos": self.vertices})
    def get_first_2d_point(self):
        region = self.context.region
        rv3d = self.context.region_data
        for index in range(int(len(self.global_co) / 10)):
            self.first_2d_point = view3d_utils.location_3d_to_region_2d(region, rv3d, self.global_co[index])
            if self.first_2d_point:
                break
        if not self.first_2d_point:
            self.report({'ERROR'}, f"Can't find a 2d point, maybe camera too close to the curve?")
    def is_2d_point_same(self):
        if (self.prev_2d_point - self.first_2d_point).length_squared > 0.000001:
            return False
        else:
            return True
    def update_2d_points(self):
        region = self.context.region
        rv3d = self.context.region_data
        self.points_2d = [view3d_utils.location_3d_to_region_2d(region, rv3d, point) for point in self.global_co]
    def find_closest_point_kd(self, event):
        size = len(self.points_2d)
        kd = mathutils.kdtree.KDTree(size)
        for i, point in enumerate(self.points_2d):
            if point:
                kd.insert(Vector((point[0], point[1], 0)), i)
        kd.balance()
        co, index, dist = kd.find((event.mouse_region_x, event.mouse_region_y, 0))
        self.vert = co
        return (0, index)
    def find_closest_point(self, event):
        region = self.context.region
        rv3d = self.context.region_data
        picked_point = None
        picked_point_length = 100000
        mouse_vec = Vector((event.mouse_region_x, event.mouse_region_y))
        t1 = time.time()
        for index, cu_point in enumerate(self.global_co):
            point_pos_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, cu_point)
            if not point_pos_2d:
                continue
            the_length = (point_pos_2d - mouse_vec).length_squared
            if picked_point_length > the_length:
                picked_point_length = the_length
                picked_point = index
        return (picked_point_length, picked_point)
    def find_closest_bezier_point(self, event):
        region = self.context.region
        rv3d = self.context.region_data
        picked_point = None
        picked_spline = None
        picked_point_length = 100000
        mouse_vec = Vector((event.mouse_region_x, event.mouse_region_y))
        for sindex, spline in enumerate(self.ob.data.splines):
            for index, point in enumerate(spline.bezier_points):
                point_pos_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, self.mw @ point.co)
                if not point_pos_2d:
                    continue
                the_length = (point_pos_2d - mouse_vec).length_squared
                if picked_point_length > the_length:
                    picked_point_length = the_length
                    picked_point = index
                    picked_spline = sindex
        return (picked_point, picked_spline)
    def get_points_data(self):
        switch_mode('OBJECT')
        clone_curve = duplicate_object(self.context.active_object, False)
        clone_curve.name = 'TEMP curve clone'
        clone_curve.data.bevel_depth = 0
        clone_curve.data.bevel_object = None
        clone_curve.data.resolution_u = 100
        super_select(clone_curve, self.context)
        bpy.ops.object.convert(target='MESH')
        mw = clone_curve.matrix_world
        t1 = time.time()
        clone_curve.data.transform(mw)
        self.global_co = [vert.co for vert in clone_curve.data.vertices]
        t1 = time.time()
        bpy.data.objects.remove(clone_curve, do_unlink=True)
        super_select(self.ob, self.context)
        self.update_2d_points()
        self.get_first_2d_point()
        switch_mode('EDIT')
    def remove_bezier_point(self, pindex, sindex):
        bpy.ops.curve.select_all(action='DESELECT')
        self.ob.data.splines[sindex].bezier_points[pindex].select_control_point = True
        bpy.ops.curve.dissolve_verts()
    def select_bezier_point(self, pindex, sindex):
        bpy.ops.curve.select_all(action='DESELECT')
        self.ob.data.splines[sindex].bezier_points[pindex].select_control_point = True
        self.ob.data.splines[sindex].bezier_points[pindex].select_right_handle = True
        self.ob.data.splines[sindex].bezier_points[pindex].select_left_handle = True
    @classmethod
    def poll(cls, context):
        ob = context.object
        edit_condition = False
        if ob and ob.type == 'CURVE':
            edit_condition = True
        return context.area.type == "VIEW_3D" and edit_condition and context.selected_objects
    def modal(self, context, event):
        try:
            context.area.tag_redraw()
            if event.type == 'MOUSEMOVE':
                t1 = time.time()
                self.get_first_2d_point()
                if self.is_2d_point_same():
                    pass
                else:
                    self.update_2d_points()
                    self.get_first_2d_point()
                    self.prev_2d_point = self.first_2d_point.copy()
            self.count += 1
            if self.count % self.skip_frames == 0:
                self.find_closest_point_kd(event)
            if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} or event.alt:
                return {'PASS_THROUGH'}
            elif (event.ctrl or event.oskey) and event.type == 'Z' and event.value == 'PRESS':
                if len(self.items):
                    bpy.ops.ed.undo()
                    self.ob = context.view_layer.objects.active
                    switch_mode('EDIT')
                    self.items.pop()
                    self.get_points_data()
                else:
                    pass
            elif event.type == 'G':
                self.g = True
                index, sindex = self.find_closest_bezier_point(event)
                self.select_bezier_point(index, sindex)
                bpy.ops.ed.undo_push(message="Move a Bezier Point")
                return {'PASS_THROUGH'}
            elif event.type == 'S':
                self.g = True
                index, sindex = self.find_closest_bezier_point(event)
                self.select_bezier_point(index, sindex)
                bpy.ops.ed.undo_push(message="Move Bezier Point Handles")
                return {'PASS_THROUGH'}
            elif event.type == 'R':
                self.g = True
                index, sindex = self.find_closest_bezier_point(event)
                self.select_bezier_point(index, sindex)
                bpy.ops.ed.undo_push(message="Rotate a Bezier Point")
                return {'PASS_THROUGH'}
            elif event.type == 'X' and event.value == "RELEASE":
                index, sindex = self.find_closest_bezier_point(event)
                self.remove_bezier_point(index, sindex)
                self.get_points_data()
                bpy.ops.ed.undo_push(message="Remove a Bezier Point")
                pass
            elif event.type == 'LEFTMOUSE' and event.value == "RELEASE":
                if self.g:
                    self.g = False
                    self.get_points_data()
                    return {'RUNNING_MODAL'}
                picked_point_length, picked_point_index = self.find_closest_point_kd(event)
                t, spline, pindex = get_t(self.ob, picked_point_index)
                if t < 0.02 or t > 0.98:
                    self.report({'WARNING'}, "Can't add point at the beginning or end of the curve")
                    return {'RUNNING_MODAL'}
                create_new_bezier_point(t, self.ob, spline, pindex)
                self.items.append([spline, pindex + 1])
                self.get_points_data()
                bpy.ops.ed.undo_push(message="Add a Bezier Point")
            elif event.type in self.cancel_buttons and event.value == "PRESS":
                if self.g:
                    self.g = False
                    self.get_points_data()
                    return {'RUNNING_MODAL'}
                bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
                if self._draw_handler_circle:
                    self._draw_handler_circle = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler_circle, 'WINDOW')
                return {'CANCELLED'}
            return {'RUNNING_MODAL'}
        except Exception as e:
            traceback.print_exc()
            self.report({'ERROR'}, str(e))
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            if self._draw_handler_circle:
                self._draw_handler_circle = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler_circle, 'WINDOW')
            return {'CANCELLED'}
    def invoke(self, context, event):
        self.g = False
        self.count = -1
        self.title = 'Add/Remove Bezier points (Esc to finish)'
        self.empty = ["(X) to dissolve a point"]
        if sys.platform == 'darwin':
            self.empty.append('Cmd+Z to Undo')
        else:
            self.empty.append('Ctrl+Z to Undo')
        self.items = []
        self.context = context
        self.ob = context.view_layer.objects.active
        self.mw = self.ob.matrix_world
        switch_mode('OBJECT')
        super_select(context.view_layer.objects.active, context)
        switch_mode('EDIT')
        bpy.ops.ed.undo_push(message="Add a Bezier Point")
        self.get_points_data()
        self.get_first_2d_point()
        self.prev_2d_point = self.first_2d_point.copy()
        self.skip_frames = int(linear(len(self.global_co), 1000, 30000, 1, 8, True))
        get_prefs(self, context)
        self.show_curve_length = False
        self.reg = get_view(context, event.mouse_x, event.mouse_y)
        init_font_settings(self)
        if context.space_data.type == 'VIEW_3D':
            self.init_area = context.area
            self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, (self, context), 'WINDOW', 'POST_PIXEL')
            self._draw_handler_circle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_circle, (self, context), 'WINDOW', 'POST_PIXEL')
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            if self._draw_handler_circle:
                self._draw_handler_circle = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler_circle, 'WINDOW')
            return {'CANCELLED'}
class OBJECT_OT_cablerator_helper_add_circle(bpy.types.Operator):
    """Create a poly curve circle at 3D Cursor location"""
    bl_idname = "object.cablerator_helper_add_circle"
    bl_label = "Cablerator: Add Polycurve Circle at 3D Cursor Location"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        return context.area.type == "VIEW_3D"
    def resolve_S_key(self, item):
        if self.cur_value < 0.001:
            self.cur_value = 0.001
            item['cur_value'] = 0.001
        build_circle(self.curve, self.events['D']['cur_value'], self.events['S']['cur_value'])
    def resolve_D_key(self, item):
        if self.cur_value < 3:
            self.cur_value = 3
            item['cur_value'] = 3
        if item['cur_value'] != self.prev_points_value:
            build_circle(self.curve, self.events['D']['cur_value'], self.events['S']['cur_value'])
            self.prev_points_value = item['cur_value']
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
        if 'NDOF' in event.type or event.type in self.navigation or event.alt:
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
                        if key == 'S':
                            self.resolve_S_key(item)
                        elif key == 'D':
                            self.resolve_D_key(item)
            else:
                self.can_type = False
                clean_events(self)
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            wheel_val = 0.1 if event.type == 'WHEELUPMOUSE' else -0.1
            if self.events['S']['status']:
                self.events['S']['cur_value'] = normal_round((self.events['S']['cur_value'] + wheel_val)*10)/10
                if self.events['S']['cur_value'] < 0.01:
                    self.events['S']['cur_value'] = 0.01
                self.first_value = self.events['S']['cur_value']
                self.first_unchanged_value = self.events['S']['cur_value']
                self.cur_value = self.events['S']['cur_value']
                self.first_mouse_x = event.mouse_x
                build_circle(self.curve, self.events['D']['cur_value'], self.events['S']['cur_value'])
            elif self.events['D']['status']:
                self.events['D']['cur_value'] += int(wheel_val*10)
                if self.events['D']['cur_value'] < 3:
                    self.events['D']['cur_value'] = 3
                self.first_value = self.events['D']['cur_value']
                self.first_unchanged_value = self.events['D']['cur_value']
                self.cur_value = self.events['D']['cur_value']
                self.first_mouse_x = event.mouse_x
                build_circle(self.curve, self.events['D']['cur_value'], self.events['S']['cur_value'])
            else:
                return {'PASS_THROUGH'}
        elif event.type == 'MOUSEMOVE':
            if self.typing: return {'RUNNING_MODAL'}
            for key in self.events.keys():
                item = self.events[key]
                if item['status']:
                    if self.is_shift:
                        delta = 1200
                    else:
                        delta = 60
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
                        if key == 'S':
                            self.resolve_S_key(item)
                        elif key == 'D':
                            self.resolve_D_key(item)
        if event.type == 'LEFTMOUSE' and event.value == "PRESS":
            for ev in self.events:
                if self.events[ev]['status']:
                    self.events[ev]['status'] = not self.events[ev]['status']
                    return {'RUNNING_MODAL'}
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            return {'FINISHED'}
        if event.type in self.cancel_buttons and event.value == "PRESS":
            for key in self.events:
                if self.events[key]['status']:
                    self.events[key]['cur_value'] = self.first_unchanged_value
                    build_circle(self.curve, self.events['D']['cur_value'], self.events['S']['cur_value'])
                    self.events[key]['status'] = not self.events[key]['status']
                    return {'RUNNING_MODAL'}
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            bpy.data.objects.remove(self.curve, do_unlink=True)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        self.typing = False
        self.can_type = False
        self.my_num_str = ""
        self.active_curve = get_active_curve()
        self.title = 'Add Polycurve Circle'
        self.circle_points = 12
        self.prev_points_value = 12
        self.width = .1
        get_prefs(self, context)
        self.show_curve_length = False
        if self.active_curve['width'] != 0 and self.active_curve['width'] != None:
            self.width = self.active_curve['width']
        self.events = {
            'D': {
                'name': 'Points Number (D)',
                'status': False,
                'cur_value': self.circle_points,
                'type': 'int',
                'show': True
            },
            'S': {
                'name': 'Radius (S)',
                'status': False,
                'cur_value': self.width,
                'type': 'float',
                'show': True
            },
        }
        self.curve = create_circle(self.events['D']['cur_value'], self.events['S']['cur_value'])
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
class OBJECT_OT_cablerator_helper_single_vert(bpy.types.Operator):
    """Add a single vert at the 3D Cursor location"""
    bl_idname = "object.cablerator_helper_single_vert"
    bl_label = "Cablerator: Add Single Vert at 3D Cursor"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        ob = context.object
        edit_condition = True
        if ob:
            edit_condition = context.object.mode == 'OBJECT'
        return context.area.type == "VIEW_3D" and edit_condition
    def execute(self, context):
        scene = context.scene
        cursor_pos = scene.cursor.location.copy()
        if anything_selected():
            deselect_all()
        mesh = bpy.data.meshes.new("mesh")
        obj = bpy.data.objects.new("Cablerator Vert", mesh)
        scene.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        mesh_data = obj.data
        bm = bmesh.new()
        bm.verts.new((0, 0, 0))
        for vert in bm.verts:
            vert.select = True
        bm.to_mesh(mesh_data)
        bm.free()
        obj.location = cursor_pos
        switch_mode('EDIT')
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
        switch_mode('OBJECT')
        return {'FINISHED'}
class OBJECT_OT_cablerator_helper_find_profile(bpy.types.Operator):
    """Select bezier curves in Object mode
Select nothing to find unused profiles"""
    bl_idname = "object.cablerator_helper_find_profile"
    bl_label = "Cablerator: Find Selected Curves Profiles"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        return context.area.type == "VIEW_3D"
    def invoke(self, context, event):
        objs = bpy.context.selected_objects
        curves = []
        profiles = []
        if not len(objs):
            temp_profiles = []
            for ob in bpy.data.objects:
                if ob.type == 'CURVE' and ob.data.bevel_depth == 0 and not ob.data.bevel_object:
                    temp_profiles.append(ob)
            for ob in bpy.data.objects:
                if ob.type == 'CURVE' and ob.data.bevel_object in temp_profiles:
                    temp_profiles.pop(temp_profiles.index(ob.data.bevel_object))
            if len(temp_profiles):
                context.view_layer.objects.active = temp_profiles[0]
                for curve in temp_profiles:
                    curve.select_set(True)
            else:
                self.report({'WARNING'}, "No unused profiles found")
            return {'FINISHED'}
        if GV.is291:
            for ob in objs:
                if ob.type == 'CURVE':
                    if ob.data.bevel_object and ob.data.bevel_mode == 'OBJECT':
                        curves.append(ob.data.bevel_object)
                    elif ob.data.bevel_depth == 0 and ob.data.bevel_mode == 'ROUND':
                        profiles.append(ob)
        else:
            for ob in objs:
                if ob.type == 'CURVE':
                    if ob.data.bevel_object:
                        curves.append(ob.data.bevel_object)
                    elif ob.data.bevel_depth == 0:
                        profiles.append(ob)
        if not len(curves) and not len(profiles):
            self.report({'WARNING'}, "Selected objects don't have curve profiles or aren't profiles themselves")
            return {'CANCELLED'}
        if not event.shift:
            deselect_all()
        messages = list()
        for profile in profiles:
            for ob in bpy.data.objects:
                if ob.type == 'CURVE' and ob not in curves:
                    if ob.data.bevel_object == profile:
                        if ob.name in context.view_layer.objects:
                            ob.select_set(True)
                        else:
                            messages.append(f"Found an object {ob.name} with this profile that's not a part of the current view layer, not selecting")
        for curve in curves:
            curve.select_set(True)
        if len(context.selected_objects):
            context.view_layer.objects.active = context.selected_objects[0]
        else:
            messages.append("Selected objects don't have curve profiles or aren't profiles themselves")
            self.report({'WARNING'}, "; ".join(messages))
            return {'CANCELLED'}
        return {'FINISHED'}
class OBJECT_OT_cablerator_helper_switch_handle(bpy.types.Operator):
    """Select bezier points in edit mode"""
    bl_idname = "object.cablerator_helper_switch_handle"
    bl_label = "Cablerator: Switch Bezier Points Handles Auto <> Aligned"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        ob = context.object
        edit_condition = True
        if ob:
            edit_condition = context.object.mode == 'EDIT'
        else:
            edit_condition = False
        return context.area.type == "VIEW_3D" and edit_condition
    def execute(self, context):
        objs = bpy.context.selected_objects
        for ob in objs:
            if ob.type == 'CURVE':
                for spline in ob.data.splines:
                    if spline.type == 'BEZIER':
                        for point in spline.bezier_points:
                            if point.select_control_point:
                                if point.handle_left_type == 'AUTO' and point.handle_right_type == 'AUTO':
                                    point.handle_right_type = point.handle_left_type = 'ALIGNED'
                                else:
                                    point.handle_right_type = point.handle_left_type = 'AUTO'
        return {'FINISHED'}
class OBJECT_OT_cablerator_helper_unrotate(bpy.types.Operator):
    """Select bezier points in edit mode"""
    bl_idname = "object.cablerator_helper_unrotate"
    bl_label = "Cablerator: Reset Points Rotation"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        ob = context.object
        edit_condition = True
        if ob:
            edit_condition = context.object.mode == 'EDIT'
        else:
            edit_condition = False
        return context.area.type == "VIEW_3D" and edit_condition
    def execute(self, context):
        objs = context.selected_objects
        points = []
        for ob in objs:
            if ob.type != 'CURVE':
                continue
            mw = ob.matrix_world
            for spline in ob.data.splines:
                if spline.type != 'BEZIER':
                    continue
                for p in spline.bezier_points:
                    if not p.select_control_point:
                        continue
                    direction = p.handle_right.copy() - p.co.copy()
                    direction_inv = p.handle_left.copy() - p.co.copy()
                    strength = direction.length
                    strength_inv = direction_inv.length
                    quat = direction.to_track_quat('X', 'Z')
                    euler_from_direction = quat.to_euler()
                    norm_eul = Euler((0.0, 0.0, 0.0), 'XYZ')
                    for index, val in enumerate(euler_from_direction):
                        norm_eul[index] = radians((normal_round(degrees(val) / 45)*45))
                    vec = Vector((1.0, 0.0, 0.0))
                    vec.rotate(norm_eul)
                    p.handle_right = p.co.copy() + vec * strength
                    p.handle_left = p.co.copy() - vec * strength_inv
        return {'FINISHED'}
class OBJECT_OT_cablerator_create_profile_bundle(bpy.types.Operator):
    """Select an existing profile in Object Mode"""
    bl_idname = "object.cablerator_create_profile_bundle"
    bl_label = "Cablerator: Create a Multi-Profile"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if not context.selected_objects:
            return False
        if context.area.type != "VIEW_3D":
            return False
        ob = context.object
        if not ob or ob.type != 'CURVE':
            return False
        return context.object.mode == 'OBJECT'
    def rotate(self, origin, point, angle):
        ox, oy = origin
        px, py = point
        qx = ox + cos(angle) * (px - ox) - sin(angle) * (py - oy)
        qy = oy + sin(angle) * (px - ox) + cos(angle) * (py - oy)
        return qx, qy
    def remove_excessive_splines(self, data, remove_from):
        remove_splines = len(data.splines)
        for index in reversed(range(remove_from, remove_splines)):
            data.splines.remove(data.splines[index])
    def get_spline_pivot(self):
        if self.orig_type == "POLY":
            points = Vector((0, 0, 0, 0))
        else:
            points = Vector((0, 0, 0))
        for point in self.orig_points:
            points += point.co
        return points/len(self.orig_points)
    def rotate_points(self, num):
        for i in range(num-1):
            if self.orig_type == "POLY":
                spline = self.curve.data.splines.new('POLY')
                spline.points.add(len(self.orig_points)-1)
                spline.use_cyclic_u = True
                for index, point in enumerate(spline.points):
                    point.co = Vector((self.rotate(Vector((0, 0)), self.orig_points[index].co.to_2d(), radians(360 / num * (i+1))))).to_4d()
            elif self.orig_type == "BEZIER":
                spline = self.curve.data.splines.new('BEZIER')
                spline.bezier_points.add(len(self.orig_points)-1)
                spline.use_cyclic_u = True
                for index, point in enumerate(spline.bezier_points):
                    point.co = Vector((self.rotate(Vector((0, 0)), self.orig_points[index].co.to_2d(), radians(360 / num * (i+1))))).to_3d()
                    point.handle_left = Vector((self.rotate(Vector((0, 0)), self.orig_points[index].handle_left.to_2d(), radians(360 / num * (i+1))))).to_3d()
                    point.handle_right = Vector((self.rotate(Vector((0, 0)), self.orig_points[index].handle_right.to_2d(), radians(360 / num * (i+1))))).to_3d()
    def set_offset(self, dist, num):
        vec_orig = Vector((dist - self.spline_pivot[0], 0))
        if self.orig_type == "POLY":
            for point in self.orig_points:
                point.co += vec_orig.to_4d()
            self.spline_pivot += vec_orig.to_4d()
        else:
            for point in self.orig_points:
                point.co += vec_orig.to_3d()
                point.handle_left += vec_orig.to_3d()
                point.handle_right += vec_orig.to_3d()
            self.spline_pivot += vec_orig.to_3d()
    def edit_multiprofile(self):
        self.remove_excessive_splines(self.curve.data, 1)
        self.set_offset(self.events['S']['cur_value'],
                        self.events['D']['cur_value'])
        self.rotate_points(self.events['D']['cur_value'])
    def get_dimension_offset(self):
        points = [point.co.x for point in self.orig_points]
        return abs(max(points) - min(points))
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
                else:
                    self.events[key]['status'] = False
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
                        if key == 'S':
                            self.edit_multiprofile()
                        elif key == 'D':
                            if self.cur_value < 1:
                                self.cur_value = 1
                                item['cur_value'] = 1
                            self.edit_multiprofile()
            else:
                self.can_type = False
                clean_events(self)
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            wheel_val = 0.1 if event.type == 'WHEELUPMOUSE' else -0.1
            if self.events['S']['status']:
                self.events['S']['cur_value'] = normal_round((self.events['S']['cur_value'] + wheel_val)*10)/10
                self.first_value = self.events['S']['cur_value']
                self.first_unchanged_value = self.events['S']['cur_value']
                self.cur_value = self.events['S']['cur_value']
                self.first_mouse_x = event.mouse_x
                self.edit_multiprofile()
            elif self.events['D']['status']:
                self.events['D']['cur_value'] += int(wheel_val*10)
                if self.events['D']['cur_value'] < 1:
                    self.events['D']['cur_value'] = 1
                self.first_value = self.events['D']['cur_value']
                self.first_unchanged_value = self.events['D']['cur_value']
                self.cur_value = self.events['D']['cur_value']
                self.first_mouse_x = event.mouse_x
                self.edit_multiprofile()
            else:
                return {'PASS_THROUGH'}
        elif event.type == 'MOUSEMOVE':
            if self.typing: return {'RUNNING_MODAL'}
            for key in self.events.keys():
                if self.events[key]['status']:
                    item = self.events[key]
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
                        if key == 'S':
                            self.edit_multiprofile()
                        elif key == 'D':
                            if self.cur_value < 1:
                                self.cur_value = 1
                                item['cur_value'] = 1
                            self.edit_multiprofile()
        if event.type == self.button and event.value == "PRESS" and self.pickers['A']['status']:
            bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.wm.tool_set_by_id(name="builtin.select", cycle=False, space_type='VIEW_3D')
            return {'PASS_THROUGH'}
        elif event.type == self.button and event.value == "RELEASE" and self.pickers['A']['status']:
            if len(context.selected_objects) == 0:
                self.pickers['A']['status'] = False
                self.pickers['A']['selecting'] = False
                self.pickers['A']['object'] = None
            elif context.view_layer.objects.active.type != 'CURVE':
                self.report({'WARNING'}, f"Profile should be assigned to a Curve object, not {context.view_layer.objects.active.type.capitalize()}")
            elif context.view_layer.objects.active.type == 'CURVE' and context.view_layer.objects.active is not self.curve:
                self.pickers['A']['status'] = False
                self.pickers['A']['selecting'] = False
                self.pickers['A']['object'] = context.view_layer.objects.active
                if GV.is291:
                    context.view_layer.objects.active.data.bevel_mode = 'OBJECT'
                context.view_layer.objects.active.data.bevel_object = self.curve
            bpy.ops.object.select_all(action='DESELECT')
            return {'RUNNING_MODAL'}
        elif event.type == 'LEFTMOUSE' and event.value == "PRESS":
            for key in self.events:
                if self.events[key]['status']:
                    self.events[key]['status'] = not self.events[key]['status']
                    return {'RUNNING_MODAL'}
            for key in self.pickers.keys():
                if self.pickers[key]['status']:
                    self.pickers[key]['status'] = False
                    self.pickers[key]['selecting'] = False
                    return {'RUNNING_MODAL'}
            remove_userless_curves()
            self.curve.data.name = self.original_data_name
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            return {'FINISHED'}
        elif event.type in self.cancel_buttons and event.value == "PRESS":
            for key in self.events:
                if self.events[key]['status']:
                    self.events[key]['cur_value'] = self.first_unchanged_value
                    self.edit_multiprofile()
                    self.events[key]['status'] = not self.events[key]['status']
                    return {'RUNNING_MODAL'}
            for key in self.pickers.keys():
                if self.pickers[key]['status']:
                    self.pickers[key]['status'] = False
                    self.pickers[key]['selecting'] = False
                    return {'RUNNING_MODAL'}
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self.curve.data = self.original_data
            remove_userless_curves()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        self.typing = False
        self.can_type = False
        self.my_num_str = ""
        self.right_click = 0
        get_prefs(self, context)
        self.show_curve_length = False
        self.button = 'RIGHTMOUSE' if self.right_click == '1' else 'LEFTMOUSE'
        self.curve = bpy.context.object
        if not self.curve:
            self.report({"ERROR"}, f"No selected curve found")
            return {"CANCELLED"}
        self.original_data = self.curve.data
        self.original_data_name = self.curve.data.name
        self.curve.data = self.original_data.copy()
        self.default_clones = 5 if len(self.curve.data.splines) < 2 else len(self.curve.data.splines)
        self.orig_spline = self.curve.data.splines[0]
        if self.orig_spline.type == 'POLY':
            self.orig_points = self.orig_spline.points
        elif self.orig_spline.type == 'BEZIER':
            self.orig_points = self.orig_spline.bezier_points
        else:
            self.report({"ERROR"}, f"The spline should be Poly or Bezier but found {self.orig_spline.type.capotalize()}")
            return {"CANCELLED"}
        self.orig_type = self.orig_spline.type
        self.remove_excessive_splines(self.curve.data, 1)
        self.spline_pivot = self.get_spline_pivot()
        self.dim_offset = self.get_dimension_offset()
        self.init_offset = self.spline_pivot.x
        if self.spline_pivot.x < self.dim_offset:
            self.init_offset = self.dim_offset
        self.set_offset(self.init_offset, self.default_clones)
        self.rotate_points(self.default_clones)
        self.title = "Create a Multi-Profile (using X-axis)"
        self.events = {
            'D': {
                'name': 'Clones Number (D)',
                'status': False,
                'cur_value': self.default_clones,
                'type': 'int',
                'show': True
            },
            'S': {
                'name': 'Offset (S)',
                'status': False,
                'cur_value': self.init_offset,
                'type': 'float',
                'show': True
            }
        }
        self.pickers = {
            'A': {
                'name': 'Set as a Profile (A)',
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
class CBL_OT_CutCable(bpy.types.Operator):
    """Separate the active curve by splines or cut using the selected points"""
    bl_idname = "cbl.cut_cable"
    bl_label = "Cablerator: Cut Cable"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return context.active_object is not None
    def get_curves(self):
        objs = get_selected(self.context)
        points = dict()
        saw_point = False
        for ob in objs:
            if ob.type != 'CURVE':
                raise Exception(f'Found a {ob.type.capitalize()} object in selection, expected all objects to be Curves. Aborting')
                return False
        for ob in objs:
            points[ob.name] = list()
            for sindex, spline in enumerate(ob.data.splines):
                if spline.type == 'BEZIER':
                    for pindex, point in enumerate(spline.bezier_points):
                        if (pindex != 0 and pindex != len(spline.bezier_points)-1) and point.select_control_point:
                            saw_point = True
                            points[ob.name].append({
                                'sindex': sindex,
                                'pindex': pindex,
                                'type': spline.type
                            })
                elif spline.type == 'POLY':
                    for pindex, point in enumerate(spline.points):
                        if (pindex != 0 and pindex != len(spline.points)-1) and point.select:
                            saw_point = True
                            points[ob.name].append({
                                'sindex': sindex,
                                'pindex': pindex,
                                'type': spline.type
                            })
                else:
                    raise Exception(f'Found a {spline.type.capitalize()} spline in the "{ob.name}" curve, expected all splines to be Bezier. Aborting')
                    return False
        if not saw_point:
            raise Exception(f'No selected points found, aborting')
            return False
        return points
    def cut(self):
        for ob_name in self.points_data:
            ob = bpy.data.objects[ob_name]
            for point in reversed(self.points_data[ob_name]):
                bpy.ops.curve.select_all(action='DESELECT')
                sindex, pindex, s_type = point.values()
                if s_type == 'BEZIER':
                    cur_len = len(ob.data.splines[sindex].bezier_points)
                elif s_type == 'POLY':
                    cur_len = len(ob.data.splines[sindex].points)
                for select_index in range(pindex, cur_len):
                    if s_type == 'BEZIER':
                        ob.data.splines[sindex].bezier_points[select_index].select_control_point = True
                        ob.data.splines[sindex].bezier_points[select_index].select_right_handle = True
                        ob.data.splines[sindex].bezier_points[select_index].select_left_handle = True
                    elif s_type == 'POLY':
                        ob.data.splines[sindex].points[select_index].select = True
                bpy.ops.curve.separate()
    def cut_splines(self):
        objs = get_selected(self.context)
        switch_mode("EDIT")
        bpy.ops.curve.select_all(action='DESELECT')
        for ob in objs:
            if ob.type != 'CURVE':
                raise Exception(f'Found a {ob.type.capitalize()} object in selection, expected all objects to be Curves. Aborting')
                return False
        for ob in objs:
            spl_len = len(ob.data.splines)
            for sindex in reversed(range(spl_len)):
                if len(ob.data.splines) == 1:
                    continue
                spline = ob.data.splines[sindex]
                if spline.type == 'BEZIER':
                    for point in spline.bezier_points:
                        point.select_control_point = True
                        point.select_left_handle = True
                        point.select_right_handle = True
                elif spline.type == 'POLY':
                    for point in spline.points:
                        point.select = True
                bpy.ops.curve.separate()
        switch_mode("OBJECT")
    def execute(self, context):
        self.context = context
        if context.active_object.mode == 'EDIT':
            try:
                self.points_data = self.get_curves()
            except Exception as e:
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}
            self.cut()
            switch_mode("OBJECT")
            switch_mode("EDIT")
            bpy.ops.curve.select_all(action='DESELECT')
            switch_mode("OBJECT")
        else:
            self.cut_splines()
        return {'FINISHED'}
class CBL_OT_DropCable(bpy.types.Operator):
    """Click: Drop cable to a surface
Select points in Edit Mode to lock them in place"""
    bl_idname = "cbl.drop_cable"
    bl_label = "Cablerator: Drop the Cable"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return context.area.type == "VIEW_3D" and context.selected_objects
    def scene_vertical_raycast(self, context=bpy.context, ray_origin=Vector((0,0,0)), view_vector=Vector((0,0,-1))):
        return context.scene.ray_cast(context.view_layer.depsgraph, ray_origin, view_vector)
    def get_lower_co(self, co):
        co_offset = co.copy()
        co_offset.z -= .1
        return co_offset
    def get_delta(self, ob):
        delta = sum(ob.dimensions) / 6
        theminnistY = 0
        mins = np.empty(0)
        for spline in ob.data.splines:
            if spline.type == 'BEZIER':
                count = len(spline.bezier_points)
                co = np.empty(count * 3, dtype=np.float64)
                spline.bezier_points.foreach_get('co', co)
                co = co[1::3]
                minY = np.amin(co)
                mins = np.append(mins, minY)
            elif spline.type == 'POLY':
                count = len(spline.points)
                co = np.empty(count * 4, dtype=np.float64)
                spline.points.foreach_get('co', co)
                co = co[1::4]
                minY = np.amin(co)
                mins = np.append(mins, minY)
        theminnistY = np.amin(mins)
        if theminnistY != 0:
            delta = -theminnistY
        return delta
    def select_bezier_point(self, point, select=True):
        point.select_right_handle = select
        point.select_left_handle = select
        point.select_control_point = select
    def project_point(self, ob, mw, mwi, point, spline_type):
        if spline_type == 'BEZIER': self.select_bezier_point(point, select=True)
        if ob.data.bevel_object and ob.data.bevel_mode == 'OBJECT':
            delta = self.get_delta(ob.data.bevel_object)
        elif ob.data.bevel_mode == 'ROUND':
            delta = ob.data.bevel_depth
        else:
            delta = 0
        point_co = point.co.to_3d() if spline_type == 'POLY' else point.co
        point_global_co = mw @ point_co
        result, location, normal, index, hit_ob, hit_ob_mw = self.scene_vertical_raycast(self.context, point_global_co)
        if not result:
            point_global_co_offset = self.get_lower_co(point_global_co)
            location = ilp(point_global_co, point_global_co_offset, Vector((0,0,0)), Vector((0,0,1)))
            normal = Vector((0,0,1))
        location += normal * delta
        if spline_type == 'BEZIER':
            left_global_co = mw @ point.handle_left
            left_global_co_offset = self.get_lower_co(left_global_co)
            right_global_co = mw @ point.handle_right
            right_global_co_offset = self.get_lower_co(right_global_co)
            location_point = ilp(point_global_co, self.get_lower_co(point_global_co), location, normal)
            location_left = ilp(left_global_co, left_global_co_offset, location, normal)
            location_right = ilp(right_global_co, right_global_co_offset, location, normal)
            left_len = (point.handle_left - point.co).length
            right_len = (point.handle_right - point.co).length
            point.co = mwi @ location_point
            point.handle_left = mwi @ location_left
            point.handle_right = mwi @ location_right
            left_vec = (point.handle_left - point.co).normalized()
            point.handle_left = point.co + left_vec * left_len
            right_vec = (point.handle_right - point.co).normalized()
            point.handle_right = point.co + right_vec * right_len
        else:
            point.co = (mwi @ location).to_4d()
        if spline_type == 'BEZIER': self.select_bezier_point(point, select=False)
    def invoke(self, context, event):
        self.scene = context.scene
        self.context = context
        self.objs = [
            ob for ob in context.selected_objects if ob.type == 'CURVE']
        if not self.objs:
            self.report({"ERROR"}, 'No selected curves found, aborting')
            return {"CANCELLED"}
        for ob in self.objs:
            if_poly = any(spline.type not in {'BEZIER', 'POLY'} for spline in ob.data.splines)
            if if_poly:
                self.report(
                    {"ERROR"},
                    'A non-bezier or non-poly spline found among the objects: this function only works with Bezier or Poly splines',
                )
                return {"CANCELLED"}
            ob.hide_set(True)
            for ob in self.objs:
                if ob.type == 'CURVE':
                    mw = ob.matrix_world
                    mwi = mw.inverted()
                    for sindex, spline in enumerate(ob.data.splines):
                        if spline.type == 'POLY':
                            for pindex, point in enumerate(spline.points):
                                if context.object.mode == 'EDIT' and point.select: continue
                                self.project_point(ob, mw, mwi, point, spline.type)
                        elif spline.type == 'BEZIER':
                            for pindex, point in enumerate(spline.bezier_points):
                                if context.object.mode == 'EDIT' and point.select_control_point: continue
                                self.project_point(ob, mw, mwi, point, spline.type)
            if context.object.mode == 'EDIT':
                switch_mode('OBJECT')
            ob.hide_set(False)
            ob.select_set(True)
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
            bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='MEDIAN')
        return {'FINISHED'}
class CBL_OT_ConvertBetween(bpy.types.Operator):
    """Convert a Curve to a Mesh or a Mesh to a Curve"""
    bl_idname = "cbl.convert_between"
    bl_label = "Cablerator: Convert Between Curve and Mesh"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return context.area.type == "VIEW_3D" and context.selected_objects and context.object.mode == 'OBJECT'
    def invoke(self, context, event):
        self.scene = context.scene
        self.context = context
        self.objs = context.selected_objects
        for ob in self.objs:
            super_select(ob, context)
            if ob.type == 'MESH':
                bpy.ops.object.convert(target='CURVE')
            else:
                bpy.ops.object.convert(target='MESH')
                if not GV.is41:
                    ob.data.use_auto_smooth = True
                    ob.data.auto_smooth_angle = 0.541052
                else:
                    add_auto_smooth_mod(self.context, ob, smooth_angle=0.541052)
                for poly in ob.data.polygons:
                    poly.use_smooth = True
        super_select(self.objs, context)
        return {'FINISHED'}
class CBL_OT_ApplyMirror(bpy.types.Operator):
    """Select a curve with Mirror modifier"""
    bl_idname = "cbl.apply_mirror"
    bl_label = "Cablerator: Apply Mirror"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        return context.object
    def get_mods_data(self, objs):
        mods_data = []
        for ob in objs:
            if ob.type == 'CURVE':
                for mod in ob.modifiers:
                    if mod.type == 'MIRROR':
                        my_ob = dict()
                        my_ob['object'] = ob
                        my_ob['axis'] = list(mod.use_axis)
                        my_ob['mod'] = mod
                        my_ob['mirror_object'] = mod.mirror_object
                        mods_data.append(my_ob)
        return mods_data
    def main(self, ob):
      for mod in reversed(ob.modifiers):
        if mod.type != 'MIRROR': continue
        for index, axis in enumerate(mod.use_axis):
          if axis:
            if mod.mirror_object:
              mod.use_axis[index] = False
              temp_mw = mod.mirror_object.matrix_world.copy()
              temp_mwi = temp_mw.inverted().copy()
              mod.mirror_object.matrix_world @= temp_mwi
              dup = duplicate_object(ob)
              self.copies.add(ob)
              self.copies.add(dup)
              super_select(dup, self.context)
              mw = dup.matrix_world.copy()
              dup.matrix_world = temp_mwi @ mw
              vx = Vector([v*-1 for v in dup.matrix_world[index].copy().to_3d()]).to_4d()
              x = (dup.location[index] - mod.mirror_object.location[index]) * 2
              vx.w = dup.matrix_world[index].w - x
              mod_mw = dup.matrix_world
              dup.matrix_world[index] = vx.copy()
              dup.matrix_world = temp_mw @ mod_mw
              mod.mirror_object.matrix_world @= temp_mw
            else:
              mod.use_axis[index] = False
              dup = duplicate_object(ob)
              self.copies.add(ob)
              self.copies.add(dup)
              super_select(dup, self.context)
              for v in dup.matrix_world:
                v[index] *= -1
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            self.main(dup)
    def execute(self, context):
        self.objs = context.selected_objects
        self.copies = set()
        self.context = context
        for ob in self.objs:
          if ob.type != 'CURVE': continue
          self.main(ob)
        self.copies = list(self.copies)
        if self.copies:
          super_select(self.copies, self.context)
          bpy.ops.object.join()
          self.result = context.object
          for mod in self.result.modifiers:
            if mod.type == 'MIRROR':
              self.result.modifiers.remove(mod)
        return {'FINISHED'}
        mods_data = self.get_mods_data(objs)
        for mod_data in mods_data:
            super_select(mod_data['object'], context)
            if mod_data['mirror_object']:
                pass
            else:
                for index, axis in enumerate(mod_data['axis']):
                    if axis:
                        mod_data['mod'].use_axis[index] = False
                        dup = duplicate_object(mod_data['object'])
                        super_select(dup, context)
                        mw = dup.matrix_world.copy()
                        v_axis = Vector([v*-1 for v in dup.matrix_world[index].copy().to_3d()]).to_4d()
                        v_axis.w = dup.matrix_world[index].w
                        dup.matrix_world[index] = v_axis.copy()
                        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        return {'CANCELLED'}
        temp_cube = bpy.data.objects["Cube"]
        temp_mw = temp_cube.matrix_world.copy()
        temp_mwi = temp_mw.inverted().copy()
        temp_cube.matrix_world @= temp_mwi
        for ob in objs:
            super_select(ob, context)
            dup = duplicate_object(ob)
            super_select(dup, context)
            mw = dup.matrix_world.copy()
            dup.matrix_world = temp_mwi @ mw
            vx = Vector([v*-1 for v in dup.matrix_world[0].copy().to_3d()]).to_4d()
            x = (dup.location[0] - temp_cube.location[0]) * 2
            vx.w = dup.matrix_world[0].w - x
            mod_mw = dup.matrix_world
            dup.matrix_world[0] = vx.copy()
            dup.matrix_world = temp_mw @ mod_mw
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        temp_cube.matrix_world @= temp_mw
        return {'FINISHED'}
def register():
    bpy.utils.register_class(OBJECT_OT_cablerator_helper_unrotate)
    bpy.utils.register_class(OBJECT_OT_cablerator_helper_switch_handle)
    bpy.utils.register_class(OBJECT_OT_cablerator_helper_find_profile)
    bpy.utils.register_class(OBJECT_OT_cablerator_helper_add_point)
    bpy.utils.register_class(OBJECT_OT_cablerator_helper_single_vert)
    bpy.utils.register_class(OBJECT_OT_cablerator_helper_add_circle)
    bpy.utils.register_class(OBJECT_OT_cablerator_create_profile_bundle)
    bpy.utils.register_class(CBL_OT_CutCable)
    bpy.utils.register_class(CBL_OT_DropCable)
    bpy.utils.register_class(CBL_OT_ConvertBetween)
    bpy.utils.register_class(CBL_OT_ApplyMirror)
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_cablerator_helper_unrotate)
    bpy.utils.unregister_class(OBJECT_OT_cablerator_helper_switch_handle)
    bpy.utils.unregister_class(OBJECT_OT_cablerator_helper_find_profile)
    bpy.utils.unregister_class(OBJECT_OT_cablerator_helper_add_point)
    bpy.utils.unregister_class(OBJECT_OT_cablerator_helper_single_vert)
    bpy.utils.unregister_class(OBJECT_OT_cablerator_helper_add_circle)
    bpy.utils.unregister_class(OBJECT_OT_cablerator_create_profile_bundle)
    bpy.utils.unregister_class(CBL_OT_CutCable)
    bpy.utils.unregister_class(CBL_OT_DropCable)
    bpy.utils.unregister_class(CBL_OT_ConvertBetween)
    bpy.utils.unregister_class(CBL_OT_ApplyMirror)
