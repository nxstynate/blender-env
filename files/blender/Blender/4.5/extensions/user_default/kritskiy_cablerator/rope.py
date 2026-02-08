import bpy
from .lib import *
from .ui import *
from .inits import *
from .typing import *
class CBL_OT_Rope(bpy.types.Operator):
    """Select objects and draw planes to create simple rope"""
    bl_idname = "cbl.rope"
    bl_label = "Cablerator: Rope"
    bl_options = {"REGISTER", "UNDO"}
    offset: bpy.props.FloatProperty(name="Curve Offset", default=0.08)
    c_width: bpy.props.FloatProperty(name="Curve Width", default=-1)
    def resolve_S_key(self, item):
        if self.cur_value < 0:
            self.cur_value = 0
            item['cur_value'] = 0
        self.c_width = item['cur_value']
        for obj in self.ropes:
            obj['obj'].data.bevel_depth = item['cur_value']
    def resolve_D_key(self, item):
        self.offset = item['cur_value']
        for obj in self.ropes:
            self.set_offset(obj)
    def resolve_T_key(self, item):
        s = item['cur_value']
        self.pickers['A']['object'].scale = s,s,s
    def point_from_view(self, coord, multiplier=1.1):
        view_vector = region_2d_to_vector_3d(self.region, self.rv3d, coord)
        ray_origin = region_2d_to_origin_3d(self.region, self.rv3d, coord)
        point_location = ray_origin + view_vector * multiplier
        return point_location
    def create_empty(self, name, loc):
        empty = bpy.data.objects.new(name, None)
        self.scene.collection.objects.link(empty)
        empty.location = loc
    def get_furthest_point_length(self, coord):
        ray_origin = region_2d_to_origin_3d(self.region, self.rv3d, coord)
        points = [(index, (ray_origin - corner).length_squared) for index, corner in enumerate(self.bboxes)]
        furthest_point = max(points, key=lambda x: int(x[1]))
        closest_point = min(points, key=lambda x: int(x[1]))
        return ((self.bboxes[closest_point[0]] - ray_origin).length * .1, (self.bboxes[furthest_point[0]] - ray_origin).length * 1.1)
    def create_plane(self):
        points_0 = self.get_furthest_point_length(self.mouse_path[0])
        points_1 = self.get_furthest_point_length(self.mouse_path[1])
        point1 = self.point_from_view(self.mouse_path[0], points_0[0])
        point2 = self.point_from_view(self.mouse_path[1], points_1[0])
        point3 = self.point_from_view(self.mouse_path[1], points_1[1])
        point4 = self.point_from_view(self.mouse_path[0], points_0[1])
        bm = bmesh.new()
        bm.verts.new(point1)
        bm.verts.new(point2)
        bm.verts.new(point3)
        bm.verts.new(point4)
        bm.faces.new(bm.verts)
        bm.normal_update()
        if self.debug:
            mesh_data = bpy.data.meshes.new("plane")
            bm.to_mesh(mesh_data)
            plane = bpy.data.objects.new("A", mesh_data)
            self.context.collection.objects.link(plane)
        self.planes.append(bm)
        self.create_intersection(bm, True)
    def clear(self):
        for mesh in bpy.data.meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        for bm in self.planes:
            try:
                bm.clear()
                bm.free()
            except Exception as e:
                pass
        for bm in self.bms:
            try:
                bm.clear()
                bm.free()
            except Exception as e:
                pass
        for bm in self.bm_intersections:
            try:
                bm.clear()
                bm.free()
            except Exception as e:
                pass
    def cancel_all(self):
        if self.ropes:
            obs = [ob['obj'] for ob in self.ropes]
            super_select(obs, self.context)
        else:
            super_select(self.obs, self.context)
    def cancel_ins(self):
        self.clear()
        if self._line_handle:
            self._line_handle = bpy.types.SpaceView3D.draw_handler_remove(self._line_handle, 'WINDOW')
        if self._draw_handler:
            self._draw_handler = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
    def finish(self):
        if self.ropes:
            obs = [ob['obj'] for ob in self.ropes]
            super_select(obs, self.context)
        else:
            super_select(self.obs, self.context)
    @classmethod
    def poll(cls, context):
        return context.selected_objects and context.object
    def create_batch3d(self):
        self.shader3d = create_3d_shader()
        self.batch3d = batch_for_shader(self.shader3d, 'LINES', {"pos": self.vertices})
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vertices = []
        self.mouse_path = [[-10, -10], [-10, -10]]
        self.create_batch3d()
    def modal(self, context, event):
        try:
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
            if (event.type == 'Z' and event.value == "PRESS") and self.is_ctrl:
                delete = self.ropes.pop()
                super_remove(delete['obj'], context)
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
            if event.type in self.actions.keys() and event.value == "PRESS":
                clean_pickers(self)
                clean_events(self)
                for key in self.actions.keys():
                    if event.type == key:
                        if key == 'R' and self.ropes:
                            self.define_bmeshes()
                            self.actions['R']['status'] = self.ropes
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
            if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
                wheel_val = 0.1 if event.type == 'WHEELUPMOUSE' else -0.1
                if self.events['S']['status']:
                    item = self.events['S']
                    item['cur_value'] = normal_round((item['cur_value'] + wheel_val)*10)/10
                    if item['cur_value'] < 0:
                        item['cur_value'] = 0
                    self.first_value = item['cur_value']
                    self.first_unchanged_value = item['cur_value']
                    self.cur_value = item['cur_value']
                    self.first_mouse_x = event.mouse_x
                    self.resolve_S_key(item)
                elif self.events['D']['status']:
                    item = self.events['D']
                    item['cur_value'] = normal_round((item['cur_value'] + wheel_val)*10)/10
                    self.first_value = item['cur_value']
                    self.first_unchanged_value = item['cur_value']
                    self.cur_value = item['cur_value']
                    self.first_mouse_x = event.mouse_x
                    self.resolve_D_key(item)
                elif self.events['T']['status'] and self.pickers['A']['object']:
                    item = self.events['T']
                    item['cur_value'] = normal_round((item['cur_value'] + wheel_val)*10)/10
                    if item['cur_value'] < 0: item['cur_value'] = 0
                    self.first_value = item['cur_value']
                    self.first_unchanged_value = item['cur_value']
                    self.cur_value = item['cur_value']
                    self.first_mouse_x = event.mouse_x
                    self.resolve_T_key(item)
                else:
                    return {'PASS_THROUGH'}
            elif event.type == 'MOUSEMOVE':
                if self.typing: return {'RUNNING_MODAL'}
                if self.mouse_pressed:
                    self.mouse_path[1] = [event.mouse_region_x, event.mouse_region_y]
                for key in self.events.keys():
                    if self.events[key]['status']:
                        item = self.events[key]
                        if self.is_shift:
                            delta = 1200 if key != 'Z' else 200
                        else:
                            delta = 120 if key != 'Z' else 20
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
                            elif key == 'T' and self.pickers['A']['object']:
                                self.resolve_T_key(item)
            if event.type == self.button and event.value == "PRESS" and self.pickers['A']['status']:
                bpy.ops.object.select_all(action='DESELECT')
                bpy.ops.wm.tool_set_by_id(name="builtin.select", cycle=False, space_type='VIEW_3D')
                return {'PASS_THROUGH'}
            elif event.type == self.button and event.value == "RELEASE" and self.pickers['A']['status']:
                is_rope_selected = [rope['obj'] for rope in self.ropes if context.view_layer.objects.active == rope['obj']]
                if len(context.selected_objects) == 0:
                    self.pickers['A']['status'] = False
                    self.pickers['A']['selecting'] = False
                    self.pickers['A']['object'] = None
                    for rope in self.ropes:
                        if GV.is291: rope['obj'].data.bevel_mode = 'ROUND'
                        rope['obj'].data.bevel_object = None
                    self.events['T']['show'] = False
                    FontGlobal.column_height = get_column_height(self)
                    FontGlobal.column_width = get_column_width(self, FontGlobal.font_id, FontGlobal.size, FontGlobal.dpi)[0]
                elif context.view_layer.objects.active.type != 'CURVE':
                    self.report({'WARNING'}, f"Profile object should be a Curve, not {context.view_layer.objects.active.type.capitalize()}")
                elif context.view_layer.objects.active.type == 'CURVE' and not is_rope_selected:
                    self.pickers['A']['status'] = False
                    self.pickers['A']['selecting'] = False
                    self.pickers['A']['object'] = context.view_layer.objects.active
                    for rope in self.ropes:
                        if GV.is291: rope['obj'].data.bevel_mode = 'OBJECT'
                        rope['obj'].data.bevel_object = context.view_layer.objects.active
                    self.events['T']['show'] = True
                    self.events['T']['cur_value'] = sum(self.pickers['A']['object'].scale)/3
                    FontGlobal.column_height = get_column_height(self)
                    FontGlobal.column_width = get_column_width(self, FontGlobal.font_id, FontGlobal.size, FontGlobal.dpi)[0]
                bpy.ops.object.select_all(action='DESELECT')
                super_select(self.obs, context)
                bpy.ops.wm.tool_set_by_id(name=self.active_tool, cycle=False, space_type='VIEW_3D')
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE':
                if event.value == "PRESS":
                    for key in self.events:
                        if self.events[key]['status']:
                            self.events[key]['status'] = not self.events[key]['status']
                            return {'RUNNING_MODAL'}
                    for key in self.pickers.keys():
                        if self.pickers[key]['status']:
                            self.pickers[key]['status'] = False
                            self.pickers[key]['selecting'] = False
                            return {'RUNNING_MODAL'}
                    self.mouse_pressed = True
                    self.mouse_path[0] = [event.mouse_region_x, event.mouse_region_y]
                    self.mouse_path[1] = [event.mouse_region_x, event.mouse_region_y]
                    return {'RUNNING_MODAL'}
                    self.cancel_ins()
                    self.finish()
                    return {'FINISHED'}
                elif event.value == 'RELEASE':
                    self.mouse_pressed = False
                    if (Vector(self.mouse_path[1]) - Vector(self.mouse_path[0])).length > 5:
                        self.create_plane()
                    else:
                        pass
                    self.mouse_path = [[-10, -10], [-10, -10]]
                    return {'RUNNING_MODAL'}
            elif event.type in self.cancel_buttons_ret and event.value == "PRESS":
                if event.type in {"RET","NUMPAD_ENTER"} and event.value == "PRESS":
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
                                elif key == 'T' and self.pickers['A']['object']:
                                    self.resolve_T_key(item)
                        return {"RUNNING_MODAL"}
                    else:
                        if self.can_type:
                            self.can_type = False
                            clean_events(self)
                            return {"RUNNING_MODAL"}
                for key in self.events:
                    if self.events[key]['status']:
                        self.events[key]['cur_value'] = self.first_unchanged_value
                        if key == 'S':
                            for obj in self.ropes:
                                obj['obj'].data.bevel_depth = self.events['S']['cur_value']
                        elif key == 'D':
                            self.offset = self.events['D']['cur_value']
                            for obj in self.ropes:
                                self.set_offset(obj)
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
                self.cancel_ins()
                self.cancel_all()
                return {'FINISHED'}
            return {'RUNNING_MODAL'}
        except Exception as e:
            traceback.print_exc()
            self.report({'ERROR'}, str(e))
            self.cancel_ins()
            self.finish()
            return {'FINISHED'}
    def get_plane_mw(self, bm):
        bm.faces.ensure_lookup_table()
        face = bm.faces[0]
        n = face.normal.copy()
        t = face.calc_tangent_edge_pair().normalized()
        c = face.calc_center_median().copy()
        return (Matrix.Translation(c) @ Matrix((t.cross(n).normalized(), t, n)).to_4x4().inverted(),
                c,
                n)
    def define_bmeshes(self):
        self.obs = self.context.selected_objects + [ob['obj'] for ob in self.ropes]
        super_select(self.obs,self.context)
        self.ropes = []
        self.bms = []
        self.bboxes = [ob.matrix_world @ Vector(corner) for ob in self.obs for corner in ob.bound_box if ob.type in {'MESH', 'CURVE'}]
        for ob in self.obs:
            ob_eval = ob.evaluated_get(self.depsgraph)
            mesh = bpy.data.meshes.new_from_object(ob_eval)
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.transform(bm, matrix=ob.matrix_world, verts=bm.verts)
            self.bms.append(bm)
    def set_offset(self, rope):
        ob, normals, points = rope.values()
        for index, point in enumerate(ob.data.splines[0].points):
            point.co = (normals[index]['coord'] + normals[index]['normal'] * self.offset).to_4d()
    def create_intersection(self, plane_bm, batch=False):
        plane_bm.faces.ensure_lookup_table()
        plane_point = plane_bm.faces[0].calc_center_median()
        plane_no = plane_bm.faces[0].normal
        plane_mw = self.get_plane_mw(plane_bm)[0]
        plane_tree = BVHTree.FromBMesh(plane_bm, epsilon=0.0)
        points = []
        missed_overlaps = 0
        for bm in self.bms:
            bm_tree = BVHTree.FromBMesh(bm, epsilon=0.0)
            overlap = bm_tree.overlap(plane_tree)
            if not overlap:
                missed_overlaps += 1
                continue
            sorted_faces_idx = sorted([el[0] for el in overlap])
            edges_idx = set()
            bm.faces.ensure_lookup_table()
            for curve_face in sorted_faces_idx:
                for edge in bm.faces[curve_face].edges:
                    edges_idx.add(edge.index)
            edges_idx = sorted(list(edges_idx))
            bm.edges.ensure_lookup_table()
            for index in edges_idx:
                p1 = bm.edges[index].verts[0].co
                p2 = bm.edges[index].verts[1].co
                intersection = ilp(p1, p2, plane_point, plane_no)
                if not intersection:
                    continue
                point_line, perc = ipl(intersection, p1, p2)
                if perc >= 0 and perc <= 1:
                    points.append(intersection)
        if missed_overlaps == len(self.bms):
            return
        local_points = [(plane_mw.inverted() @ v).to_2d() for v in points]
        convex_points = convex_hull_2d(local_points)
        export_points = [v for index, v in enumerate(points) if index in convex_points]
        bm = bmesh.new()
        for index, v in enumerate(points):
            if index in convex_points:
                bm.verts.new(v)
        f = bmesh.ops.contextual_create(bm, geom=bm.verts)
        bm.faces.ensure_lookup_table()
        for i, v in enumerate(bm.faces[0].verts):
            v.index = i
        bm.verts.sort()
        bm.normal_update()
        bmesh.ops.delete(bm, geom=bm.faces, context="FACES_KEEP_BOUNDARY")
        mesh_data = bpy.data.meshes.new("rope")
        bm.to_mesh(mesh_data)
        obj = bpy.data.objects.new(f"rope {(len(self.ropes)+1):02}", mesh_data)
        self.context.scene.collection.objects.link(obj)
        super_select(obj, self.context)
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
        normals = [{'normal': (v.co.copy()).normalized(), 'coord': v.co.copy()} for index, v in enumerate(obj.data.vertices)]
        bpy.ops.object.convert(target='CURVE')
        obj.data.bevel_depth = self.events['S']['cur_value']
        if self.pickers['A']['object']:
            if GV.is291: obj.data.bevel_mode = 'OBJECT'
            obj.data.bevel_object = self.pickers['A']['object']
        bpy.ops.object.shade_smooth()
        first_point = set_first_polyspline_point(obj)
        mesh_index = 0
        for mindex, mesh_point in enumerate(normals):
            if (obj.data.splines[0].points[0].co.to_3d() - mesh_point['coord']).length_squared < 0.001:
                mesh_index = mindex
        new_normals = normals[mesh_index:] + normals[:mesh_index]
        new_rope = {
            "obj": obj,
            "normals": new_normals,
            "points": [point.co.copy() for point in obj.data.splines[0].points]
        }
        self.ropes.append(new_rope)
        self.set_offset(new_rope)
        super_select(self.obs, self.context)
    def verts_to_lines(self, verts):
        new_arr = []
        verts.ensure_lookup_table()
        for index, item in enumerate(verts):
            next_item = verts[0] if index == len(verts) - 1 else verts[index + 1]
            new_arr.append(item.co)
            new_arr.append(next_item.co)
        return new_arr
    def invoke(self, context, event):
        self.typing = False
        self.can_type = False
        self.my_num_str = ""
        self.last_typed_key = ''
        self.active_tool = context.workspace.tools.from_space_view3d_mode("OBJECT", create=False).idname
        self.right_click = 0
        self.active_curve = get_active_curve()
        self.ropes = []
        if self.c_width == -1:
            self.c_width = context.preferences.addons[__package__].preferences.width
        self.insulate_obj = None
        self.debug = False
        self.context = context
        self.depsgraph = context.evaluated_depsgraph_get()
        switch_mode('OBJECT')
        self.mouse_pressed = False
        self.planes = []
        self.bm_intersections = []
        self.obs = context.selected_objects
        self.scene = context.scene
        self.area = context.area
        self.region = self.area.regions[-1]
        self.space = self.area.spaces.active
        self.rv3d = self.space.region_3d
        self.segments_num = 10
        get_prefs(self, context)
        for ob in self.obs:
            if ob.type not in {'MESH', 'CURVE'}:
                self.report({'ERROR'}, f"Unexpected object type — {ob.type} — found in the selection, aborting. The function requires curves or meshes to be selected")
        self.define_bmeshes()
        self.show_curve_length = False
        self.button = 'RIGHTMOUSE' if self.right_click == '1' else 'LEFTMOUSE'
        self.title = "Create Rope (Beta)"
        self.empty = ["Draw a lines to define a simple rope", "Esc/Enter to Finish"]
        self.events = {
            'T': {
                'name': 'Scale Profile (T)',
                'status': False,
                'cur_value': 1,
                'type': 'float',
                'show': False
            },
            'D': {
                'name': 'Offset (D)',
                'status': False,
                'cur_value': self.offset,
                'type': 'float',
                'show': True
            },
            'S': {
                'name': 'Width (S)',
                'status': False,
                'cur_value': self.c_width,
                'type': 'float',
                'show': True
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
        self.actions = {
            'R': {
                'name': 'Apply Existing Ropes (R)',
                'status': self.ropes,
                'show': True,
            },
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
            self._line_handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_line, (self, context), 'WINDOW', 'POST_PIXEL')
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            self.cancel_ins()
            self.finish()
            return {'CANCELLED'}
def register():
    bpy.utils.register_class(CBL_OT_Rope)
def unregister():
    bpy.utils.unregister_class(CBL_OT_Rope)
