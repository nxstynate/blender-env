import bpy
from .lib import *
from .ui import *
from .inits import *
from .typing import *
class CBL_OT_Insulate(bpy.types.Operator):
    """Select objects and draw 2 planes to create insulation"""
    bl_idname = "cbl.insulate"
    bl_label = "Cablerator: Insulate"
    bl_options = {"REGISTER", "UNDO"}
    solidify_width: bpy.props.FloatProperty(name="Solidify Width", default=0.08)
    def join(self, list_of_bmeshes):
        bm = bmesh.new()
        add_vert = bm.verts.new
        add_face = bm.faces.new
        add_edge = bm.edges.new
        for bm_to_add in list_of_bmeshes:
            offset = len(bm.verts)
            for v in bm_to_add.verts:
                add_vert(v.co)
            bm.verts.index_update()
            bm.verts.ensure_lookup_table()
            if bm_to_add.faces:
                for face in bm_to_add.faces:
                    add_face(tuple(bm.verts[i.index+offset] for i in face.verts))
                bm.faces.index_update()
            if bm_to_add.edges:
                for edge in bm_to_add.edges:
                    edge_seq = tuple(bm.verts[i.index+offset] for i in edge.verts)
                    try:
                        add_edge(edge_seq)
                    except ValueError:
                        pass
                bm.edges.index_update()
        return bm
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
        return ((self.bboxes[closest_point[0]] - ray_origin).length * .7, (self.bboxes[furthest_point[0]] - ray_origin).length * 1.1)
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
        if len(self.planes) == 2:
            self.create_segments()
    def create_segments(self):
        def two_closest_points(co, points):
            lengths = [((el.co - co).length_squared, index) for index, el in enumerate(points)]
            lengths.sort(key=lambda el: el[0])
            lengths = lengths[:2]
            return lengths
        self.planes[0].faces.ensure_lookup_table()
        c_a = self.planes[0].faces[0].calc_center_median().copy()
        normal_a = self.planes[0].faces[0].normal.copy()
        self.planes[1].faces.ensure_lookup_table()
        c_b = self.planes[1].faces[0].calc_center_median().copy()
        normal_b = self.planes[1].faces[0].normal.copy()
        center_point = (c_a + c_b) / 2
        vec_center_a = center_point - c_a
        vec_center_b = center_point - c_b
        angle_a = normal_a.angle(vec_center_a)
        angle_b = normal_b.angle(vec_center_b)
        points_order = [None, None]
        if angle_a > pi/2:
            normal_a = -normal_a
            points_order[0] = (1, 0, 3, 2)
        else:
            points_order[0] = (0, 1, 2, 3)
        if angle_b > pi/2:
            normal_b = -normal_b
            points_order[1] = (0, 1, 2, 3)
        else:
            points_order[1] = (1, 0, 3, 2)
        self.planes[0].verts.ensure_lookup_table()
        self.planes[1].verts.ensure_lookup_table()
        two_points_0 = two_closest_points(self.planes[0].verts[0].co, self.planes[1].verts)
        two_points_1 = two_closest_points(self.planes[0].verts[1].co, self.planes[1].verts)
        two_points_2 = two_closest_points(self.planes[0].verts[2].co, self.planes[1].verts)
        two_points_3 = two_closest_points(self.planes[0].verts[3].co, self.planes[1].verts)
        if two_points_0[0][1] == two_points_1[0][1]:
            if two_points_0[1][0] > two_points_1[1][0]:
                pass
            else:
                pass
        else:
            pass
        verts_coords = list()
        for point_index in range(4):
            num = self.segments_num + 2
            self.planes[0].verts.ensure_lookup_table()
            self.planes[1].verts.ensure_lookup_table()
            p1 = self.planes[0].verts[points_order[0][point_index]].co
            p2 = self.planes[1].verts[points_order[1][point_index]].co
            vec_points = (p2 - p1).normalized()
            dir_cent_vert_a = (p1 - c_a).normalized()
            dir_cent_vert_b = (p2 - c_b).normalized()
            points_distance = (p2 - p1).length
            handle1 = p1 + normal_a * (points_distance/3) * 0.3 + dir_cent_vert_a * 0.3
            handle2 = p2 + normal_b * (points_distance/3) * 0.3 + dir_cent_vert_b * 0.3
            coords = interpolate_bezier(p1, handle1, handle2, p2, num)
            verts_coords.append(coords)
        for index in range(1, num-1):
            bm = bmesh.new()
            bm.verts.new(verts_coords[0][index])
            bm.verts.new(verts_coords[1][index])
            bm.verts.new(verts_coords[2][index])
            bm.verts.new(verts_coords[3][index])
            bm.faces.new(bm.verts)
            bm.normal_update()
            if self.debug:
                mesh_data = bpy.data.meshes.new("plane")
                bm.to_mesh(mesh_data)
                obj = bpy.data.objects.new("_plane", mesh_data)
                self.context.collection.objects.link(obj)
            self.create_intersection(bm)
        cover_bm = self.join(self.bm_intersections)
        median_edge_len = median([edge.calc_length() for edge in cover_bm.edges])
        for index in range(2):
            subdivide = list()
            for edge in cover_bm.edges:
                if edge.calc_length() > median_edge_len:
                    subdivide.append(edge)
            bmesh.ops.subdivide_edges(cover_bm, edges=subdivide, cuts=1)
        bmesh.ops.bridge_loops(cover_bm,edges=cover_bm.edges)
        bmesh.ops.join_triangles(cover_bm, faces=cover_bm.faces, angle_face_threshold=1, angle_shape_threshold=1)
        bmesh.ops.remove_doubles(cover_bm, verts=cover_bm.verts, dist=0.0001)
        mesh_data = bpy.data.meshes.new("InsulateMesh")
        cover_bm.to_mesh(mesh_data)
        cover_bm.free()
        self.insulate_obj = bpy.data.objects.new("Insulate", mesh_data)
        self.context.scene.collection.objects.link(self.insulate_obj)
        for f in self.insulate_obj.data.polygons:
            f.use_smooth = True
        self.solidify_mod = self.insulate_obj.modifiers.new(name='Solidify',type='SOLIDIFY')
        self.solidify_mod.solidify_mode = 'EXTRUDE'
        self.solidify_mod.offset = 1
        self.solidify_mod.thickness = self.solidify_width
        if not GV.is41:
            self.insulate_obj.data.use_auto_smooth = True
            self.insulate_obj.data.auto_smooth_angle = 1.22173
        else:
            add_auto_smooth_mod(self.context, self.insulate_obj, smooth_angle=1.0472)
    def resolve_S_key(self, item):
        if self.cur_value < 0:
            self.cur_value = 0
            item['cur_value'] = 0
        if self.solidify_mod:
            self.solidify_width = item['cur_value']
            self.solidify_mod.thickness = self.solidify_width
    def resolve_D_key(self, item):
        if self.cur_value < 1:
            self.cur_value = 1
            item['cur_value'] = 1
        self.segments_num = item['cur_value']
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
        if self.insulate_obj:
           bpy.data.objects.remove(self.insulate_obj, do_unlink=True)
        super_select(self.obs, self.context)
    def cancel_ins(self):
        self.clear()
        if self._line_handle:
            self._line_handle = bpy.types.SpaceView3D.draw_handler_remove(self._line_handle, 'WINDOW')
        if self._draw_handler:
            self._draw_handler = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
        if self._draw_handler_3d:
            self._draw_handler_3d = bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler_3d, 'WINDOW')
    def rebuild_insulate(self):
        super_remove(self.insulate_obj, self.context)
        self.insulate_obj = None
        for mesh in bpy.data.meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        for bm in self.bm_intersections[2:]:
            try:
                bm.clear()
                bm.free()
            except Exception as e:
                pass
        self.bm_intersections = self.bm_intersections[:2]
        self.create_segments()
    def finish(self):
        if self.insulate_obj:
            super_select(self.insulate_obj, self.context)
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
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
            if event.type in self.events.keys() and event.value == "PRESS":
                self.first_mouse_x = event.mouse_x
                for key in self.events.keys():
                    if event.type == key:
                        if self.events[key]['status']:
                            self.events[key]['status'] = False
                            self.can_type = False
                            if key == 'D':
                                if self.insulate_obj:
                                    self.rebuild_insulate()
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
                clean_events(self)
                for key in self.actions.keys():
                    if event.type == key:
                        if key == 'Q' and self.actions[key]['status']:
                            self.cancel_ins()
                            self.finish()
                            super_select(self.obs, self.context)
                            bpy.ops.cbl.insulate('INVOKE_DEFAULT', solidify_width=self.events['S']['cur_value'])
                            return {'FINISHED'}
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
                    if self.insulate_obj:
                        self.rebuild_insulate()
                    clean_events(self)
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
                    item['cur_value'] += int(wheel_val*10)
                    if item['cur_value'] < 1:
                        item['cur_value'] = 1
                    self.first_value = item['cur_value']
                    self.first_unchanged_value = item['cur_value']
                    self.cur_value = item['cur_value']
                    self.first_mouse_x = event.mouse_x
                    self.resolve_D_key(item)
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
            if event.type == 'LEFTMOUSE':
                if event.value == "PRESS":
                    for key in self.events:
                        if self.events[key]['status']:
                            self.events[key]['status'] = not self.events[key]['status']
                            if key == 'D':
                                if self.insulate_obj:
                                    self.rebuild_insulate()
                            return {'RUNNING_MODAL'}
                    if len(self.planes) < 2:
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
            elif event.type in self.cancel_buttons and event.value == "PRESS":
                for key in self.events:
                    if self.events[key]['status']:
                        self.events[key]['cur_value'] = self.first_unchanged_value
                        if key == 'S':
                            if self.solidify_mod:
                                self.solidify_width = self.events[key]['cur_value']
                                self.solidify_mod.thickness = self.solidify_width
                        self.events[key]['status'] = not self.events[key]['status']
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
        for ob in self.obs:
            ob_eval = ob.evaluated_get(self.depsgraph)
            mesh = bpy.data.meshes.new_from_object(ob_eval)
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.transform(bm, matrix=ob.matrix_world, verts=bm.verts)
            self.bms.append(bm)
    def create_intersection(self, plane_bm, batch=False):
        plane_bm.faces.ensure_lookup_table()
        plane_point = plane_bm.faces[0].calc_center_median()
        plane_no = plane_bm.faces[0].normal
        plane_mw = self.get_plane_mw(plane_bm)[0]
        plane_tree = BVHTree.FromBMesh(plane_bm, epsilon=0.0)
        points = list()
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
                else:
                    pass
        if missed_overlaps == len(self.bms):
            self.report({'ERROR'}, f"No sections found when trying to create insulations for selected objects (maybe there's a hole?), aborting")
            self.cancel_ins()
            self.cancel_all()
            pass
        local_points = [(plane_mw.inverted() @ v).to_2d() for v in points]
        convex_points = convex_hull_2d(local_points)
        export_points = [v for index, v in enumerate(points) if index in convex_points]
        bm = bmesh.new()
        for index, v in enumerate(points):
            if index in convex_points:
                bm.verts.new(v)
        f = bmesh.ops.contextual_create(bm, geom=bm.verts)
        for i, v in enumerate(f['faces'][0].verts):
            v.index = i
        bm.verts.sort()
        bm.normal_update()
        bmesh.ops.delete(bm, geom=bm.faces, context="FACES_KEEP_BOUNDARY")
        if batch:
            lines = self.verts_to_lines(bm.verts)
            for el in lines:
                self.vertices.append(el)
            self.create_batch3d()
        if self.debug:
            mesh_data = bpy.data.meshes.new("intersections")
            bm.to_mesh(mesh_data)
            obj = bpy.data.objects.new("intersections", mesh_data)
            self.context.scene.collection.objects.link(obj)
        self.bm_intersections.append(bm)
        return
        plane.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.convert(target='CURVE')
        obj.data.bevel_depth = 0.12
        bpy.ops.object.shade_smooth()
        for mesh in bpy.data.meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        plane.select_set(True)
        obj.select_set(False)
        bpy.context.view_layer.objects.active = plane
    def verts_to_lines(self, verts):
        new_arr = list()
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
        self.active_tool = context.workspace.tools.from_space_view3d_mode("OBJECT", create=False).idname
        self.right_click = 0
        self.insulate_obj = None
        self.solidify_mod = None
        self.debug = False
        self.context = context
        self.depsgraph = context.evaluated_depsgraph_get()
        switch_mode('OBJECT')
        self.obs = context.selected_objects
        self.bms = list()
        self.mouse_pressed = False
        self.planes = list()
        self.bm_intersections = list()
        self.bboxes = [ob.matrix_world @ Vector(corner) for ob in self.obs for corner in ob.bound_box if ob.type in {'MESH', 'CURVE'}]
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
        self.title = "Create Insulation"
        self.empty = ["Draw 2 lines to define the insulation"]
        self.actions = {
            'Q': {
                'name': 'Create Another (Q)',
                'status': True,
                'show': True,
            },
        }
        self.events = {
            'S': {
                'name': 'Width (S)',
                'status': False,
                'cur_value': self.solidify_width,
                'type': 'float',
                'show': True
            },
            'D': {
                'name': 'Number of Segments (D)',
                'status': False,
                'cur_value': self.segments_num,
                'type': 'int',
                'show': True
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
            self._draw_handler_3d = bpy.types.SpaceView3D.draw_handler_add(draw_callback_3d, (self, context), 'WINDOW', 'POST_VIEW')
            self._line_handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_line, (self, context), 'WINDOW', 'POST_PIXEL')
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            self.cancel_ins()
            self.finish()
            return {'CANCELLED'}
def register():
    bpy.utils.register_class(CBL_OT_Insulate)
def unregister():
    bpy.utils.unregister_class(CBL_OT_Insulate)
