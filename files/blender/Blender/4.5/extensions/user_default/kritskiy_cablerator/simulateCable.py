import bpy
from .lib import *
from .ui import *
from addon_utils import check
class CBL_OT_SimulateCableDialog(bpy.types.Operator):
    """"""
    bl_idname = "cbl.simulate_cable_dialog"
    bl_label = "Cablerator: Simulate Cable Options..."
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return context.area.type == "VIEW_3D" and context.active_object is not None and context.selected_objects
    multiplier: bpy.props.IntProperty(name='Curve Points Multiplier', default=1, min= 1, max = 4)
    res: bpy.props.IntProperty(name='Simulation Resolution', default=8, min=4, max=32)
    end_frame: bpy.props.IntProperty(name='Custom End Frame', default=401, min=1)
    use_end_frame: bpy.props.BoolProperty(
        name="Use Custom End Frame", default=False)
    debug: bpy.props.BoolProperty(name="Debug Mode", default=False)
    recalc: bpy.props.BoolProperty(name="Fit to geometry below", default=False)
    add_expand: bpy.props.IntProperty(name='Expand Length', default=0, min=0, max=100)
    def get_simulated(self):
        selected = get_selected(self.context)
        curves = [ob for ob in selected if ob.type == 'CURVE']
        meshes = [ob for ob in selected if ob.type == 'MESH']
        if not curves:
            raise Exception('No Curve objects selected, aborting')
        elif len(curves) > 1:
            raise Exception(f'Expected to find one curve in selection, but found {len(curves)}, aborting')
        else:
            for spline in curves[0].data.splines:
                if spline.type != 'BEZIER':
                    raise Exception(f'Expected all splines to be Bezier, but found some {spline.type.capitalize()}, aborting')
        return curves[0], meshes
    def clo_get_points_data(self):
        points = dict()
        saw_point = False
        if self.mode == 'EDIT':
            for sindex, spline in enumerate(self.ob.data.splines):
                points[str(sindex)] = list()
                if spline.type != 'BEZIER':
                    self.report(
                        {'ERROR'}, "Curve isn't a Bezier Curve, aborting")
                    return False
                for pindex, point in enumerate(spline.bezier_points):
                    if point.select_control_point:
                        points[str(sindex)].append({
                            'sindex': sindex,
                            'pindex': pindex,
                            'coord': point.co.copy(),
                            'back': point.handle_left.copy(),
                            'front': point.handle_right.copy(),
                        })
            switch_mode('OBJECT')
        elif self.mode == 'OBJECT':
            for sindex, spline in enumerate(self.ob.data.splines):
                points[str(sindex)] = list()
                if spline.type != 'BEZIER':
                    self.report(
                        {'ERROR'}, "Curve isn't a Bezier Curve, aborting")
                    return False
                for pindex, point in enumerate(spline.bezier_points):
                    if pindex == 0 or pindex == len(spline.bezier_points) - 1:
                        points[str(sindex)].append({
                            'sindex': sindex,
                            'pindex': pindex,
                            'coord': point.co.copy(),
                            'back': point.handle_left.copy(),
                            'front': point.handle_right.copy(),
                        })
        if points:
            return points
        else:
            return False
    def remove_vg(self):
        for vg in self.ob.vertex_groups:
            if vg.name == 'CableratorSim':
                self.ob.vertex_groups.remove(vg)
    def clo_create_vert_groups(self):
        self.remove_vg()
        vg = self.ob.vertex_groups.new(name="CableratorSim")
        edge_cases = list()
        for el in self.clo_verts:
            if len(el) == 2:
                vg.add([index for index in el], 1.0, "ADD")
                edge_cases = [el[0] + 1, el[1] - 1]
                vg.add([index for index in edge_cases], 0.5, "ADD")
            else:
                vg.add(el, 1.0, "ADD")
                edge_cases = [el[0] + 1, el[0] - 1]
                for spline in self.spline_mods:
                    if el[0] == spline:
                        edge_cases = [el[0] + 1]
                        break
                    elif el[0] == spline - 1:
                        edge_cases = [el[0] - 1]
                        break
                vg.add([index for index in edge_cases], 0.5, "ADD")
        return edge_cases
    def create_verts_group_map(self):
        verts_group = []
        cur_value = 0
        prev_leng = 0
        spline_mods = [0]
        if self.mode == 'OBJECT':
            for index, spline_len in enumerate(self.verts_len):
                temp = [cur_value,
                        (self.res * (spline_len - 1 + prev_leng)) + index]
                verts_group.append(temp)
                cur_value = temp[1] + 1
                prev_leng += spline_len - 1
        else:
            spline_mod = 0
            for index, spline_len in enumerate(self.verts_len):
                for point in self.points_data[str(index)]:
                    verts_group.append(
                        [point['pindex'] * self.res + spline_mod])
                spline_mod = spline_mod + self.res * \
                    (spline_len - 1) + 1
                spline_mods.append(spline_mod)
        return verts_group, spline_mods
    def clo_convert_to_mesh(self):
        self.ob.data.resolution_u = self.res
        self.ob.data.bevel_object = None
        self.ob.data.bevel_depth = 0
        self.verts_len = [len(spline.bezier_points)
                          for spline in self.ob.data.splines]
        verts_group_map, spline_mods = self.create_verts_group_map()
        bpy.ops.object.convert(target='MESH')
        return verts_group_map, spline_mods
    def clo_add_cloth(self, frame_start, frame_end):
        self.cloth_mod = self.ob.modifiers.new(name='Cloth', type='CLOTH')
        self.cloth_mod.settings.vertex_group_mass = "CableratorSim"
        self.cloth_mod.settings.quality = 10
        self.cloth_mod.settings.shear_stiffness = 1
        self.cloth_mod.settings.compression_stiffness = 1
        self.cloth_mod.settings.tension_stiffness = 1
        self.cloth_mod.collision_settings.use_self_collision = True
        self.cloth_mod.collision_settings.self_friction = 15
        self.cloth_mod.point_cache.frame_start = frame_start
        self.cloth_mod.point_cache.frame_end = frame_end
        self.cloth_mod.collision_settings.self_distance_min = self.extrude_length/2
        self.cloth_mod.settings.shrink_min = self.add_expand / -100
    def get_extrude_length(self):
        ores, mode, depth, bev_object, materials = self.init_curve.values()
        if mode == 'ROUND':
            return depth
        elif mode == 'OBJECT':
            dims = [dim for dim in bev_object.dimensions if dim != 0]
            return sum(dims)/len(dims)
    def clo_add_extrude(self):
      bm = bmesh.new()
      bm.from_mesh(self.ob.data)
      bm.verts.ensure_lookup_table()
      direction = bm.verts[1].co - bm.verts[0].co
      euler_from_direction = direction.to_track_quat('X', 'Z').to_euler()
      mat_rot = Matrix.Rotation(radians(90), 4, 'Z')
      quat = mat_rot.to_quaternion()
      eu = quat.to_euler()
      direction.rotate(eu)
      direction.normalize()
      bm.edges.ensure_lookup_table()
      extruded_edges = bmesh.ops.extrude_edge_only(bm, edges=bm.edges)
      extruded_verts = [ele for ele in extruded_edges['geom']
                        if isinstance(ele, bmesh.types.BMVert)]
      self.extrude_length = self.get_extrude_length()
      if self.extrude_length == 0 or self.extrude_length > 0.01:
        self.extrude_length = 0.01
      bmesh.ops.translate(bm, verts=extruded_verts,
                          vec=direction*self.extrude_length)
      bm.to_mesh(self.ob.data)
      bm.free()
    def clo_bake_cloth(self):
        if GV.after4:
            with self.context.temp_override(
                scene=self.context.scene,
                active_object=self.ob,
                point_cache=self.cloth_mod.point_cache,
                ):
                bpy.ops.ptcache.bake(bake=True)
        else:
            override = {'scene': self.context.scene, 'active_object': self.ob,
                        'point_cache': self.cloth_mod.point_cache}
            bpy.ops.ptcache.bake(override, bake=True)
        self.context.scene.frame_current = 1
        if not self.debug:
            bpy.ops.object.convert(target='MESH')
    def clo_remove_verts(self):
        me = self.ob.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        verts = [vert for vert in bm.verts if vert.index >= len(bm.verts)/2]
        bmesh.ops.delete(bm, geom=verts)
        bm.to_mesh(me)
        bm.free()
    def subdivide(self):
        if self.mode == 'OBJECT':
            switch_mode('EDIT')
            bpy.ops.curve.select_all(action='SELECT')
            bpy.ops.curve.subdivide(number_cuts=(self.multiplier-1))
            switch_mode('OBJECT')
        elif self.mode == 'EDIT':
            splines_n_points_idices = list()
            for spline in self.ob.data.splines:
                points_i = [index for index, point in enumerate(spline.bezier_points)
                            if point.select_control_point]
                splines_n_points_idices.append(points_i)
            bpy.ops.curve.select_all(action='SELECT')
            bpy.ops.curve.subdivide(number_cuts=(self.multiplier-1))
            bpy.ops.curve.select_all(action='DESELECT')
            for s_index, el in enumerate(splines_n_points_idices):
                for p_index in el:
                    self.ob.data.splines[s_index].bezier_points[p_index *
                                                                self.multiplier].select_control_point = True
                    self.ob.data.splines[s_index].bezier_points[p_index *
                                                                self.multiplier].select_left_handle = True
                    self.ob.data.splines[s_index].bezier_points[p_index *
                                                                self.multiplier].select_right_handle = True
    def dissolve_curve(self):
        res = self.res
        self.remove_vg()
        bpy.ops.object.convert(target='CURVE')
        self.restore_bevel()
        for spline in self.ob.data.splines:
            spline.use_smooth = True
        switch_mode('EDIT')
        bpy.ops.curve.select_all(action='SELECT')
        bpy.ops.curve.spline_type_set(type='BEZIER')
        bpy.ops.curve.handle_type_set(type='AUTOMATIC')
        bpy.ops.curve.handle_type_set(type='ALIGNED')
        bpy.ops.curve.select_all(action='DESELECT')
        for splindex, spline in enumerate(self.ob.data.splines):
            points = [el for el in range(
                len(spline.bezier_points)-1) if el % res != 0]
            bpy.ops.curve.select_all(action='DESELECT')
            for index in points:
                self.ob.data.splines[splindex].bezier_points[index].select_left_handle = True
                self.ob.data.splines[splindex].bezier_points[index].select_right_handle = True
                self.ob.data.splines[splindex].bezier_points[index].select_control_point = True
            bpy.ops.curve.dissolve_verts()
        switch_mode('OBJECT')
        return get_active(self.context)
    def restore_bevel(self):
        ores, mode, depth, bev_object, materials = self.init_curve.values()
        self.ob.data.resolution_u = ores
        if mode == 'ROUND':
            if GV.is291:
                self.ob.data.bevel_mode = mode
            self.ob.data.bevel_depth = depth
        elif mode == 'OBJECT':
            if GV.is291:
                self.ob.data.bevel_mode = mode
            self.ob.data.bevel_object = bev_object
    def clo_restore_handles(self):
        for spline in self.points_data:
            for point in self.points_data[spline]:
                for sindex, real_spline in enumerate(self.curve.data.splines):
                    for pindex, real_point in enumerate(real_spline.bezier_points):
                        if (point['coord'] - real_point.co).length_squared < 1e-100:
                            v1 = (point['back'] - point['coord']).normalized()
                            d1 = (real_point.co - real_point.handle_left).length
                            v2 = (point['front'] - point['coord']).normalized()
                            d2 = (real_point.co - real_point.handle_right).length
                            real_point.handle_left = real_point.co + v1 * d1
                            real_point.handle_right = real_point.co + v2 * d2
    def clo_make_colliders(self):
        for ob in self.meshes:
            temp_dict = {"ob": ob}
            mods = [mod for mod in ob.modifiers if mod.type == 'COLLISION']
            if mods:
                collision_mod = mods[0]
                temp_dict['had_mod'] = True
                temp_dict['cloth_friction'] = ob.collision.cloth_friction
            else:
                collision_mod = ob.modifiers.new(
                    name='Collision', type='COLLISION')
                temp_dict['had_mod'] = False
                temp_dict['cloth_friction'] = 60
            temp_dict["mod"] = collision_mod
            ob.collision.cloth_friction = 60
            self.collision_objects.append(temp_dict)
    def clo_remove_colliders(self):
        for el in self.collision_objects:
            if el['had_mod']:
                el['ob'].collision.cloth_friction = el['cloth_friction']
            else:
                el['ob'].modifiers.remove(el['mod'])
    def fit_curve(self):
        self.remove_vg()
        bpy.ops.object.convert(target='CURVE')
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.curve.select_all(action='SELECT')
        dist = 1e10
        temp_restore_points = []
        for spline in self.ob.data.splines:
            temp_points = []
            for index, point in enumerate(spline.points):
                if index == 0 or index == len(spline.points) - 1:
                    temp_points.append(point.co.copy())
                if index < len(spline.points) - 1:
                    next_point = spline.points[index+1]
                    length = (point.co - next_point.co).length
                    if length < dist: dist = length
            temp_restore_points.append(temp_points)
        self.remove_double(distance=dist * 1.2)
        for sindex, restore_p in enumerate(temp_restore_points):
            points = self.ob.data.splines[sindex].points
            points[0].co = restore_p[0]
            points[len(points)-1].co = restore_p[1]
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.mode_set(mode='OBJECT')
        objs = self.context.selected_objects
        TOL = 0.000001
        RES = 8
        NME = 'Fitted_Bezier'
        MINPTS = 7
        bf0 = lambda u: u**3
        bf1 = lambda u: 3*((u**2)*(1-u))
        bf2 = lambda u: 3*(u*((1-u)**2))
        bf3 = lambda u: (1-u)**3
        def splitslice(stackslice):
            """From splice s return a list of two splices
            0: from beginning to mid-element,
            1: from mid-element to end"""
            interval = (stackslice.stop - stackslice.start) >> 1
            remainder = (stackslice.stop - stackslice.start) %  2
            return [ \
                slice(stackslice.start, stackslice.start + interval + remainder, 1), \
                slice(stackslice.start + interval, stackslice.stop, 1)              \
                ]
        def tryfit(plotpoints):
            """plotpoints: numpy array of 3D space points. shape (N, 3)
            return: python list of numpy arrays, shape (4 x 3)
            Cubic Bezier spline control points."""
            dln = len(plotpoints)
            ascol = (dln, 1)
            diff = plotpoints[1:] - plotpoints[:-1]
            slen = np.array([np.sqrt((p**2.0).sum()) for p in diff])
            ssum = np.array([0.0] + [slen[:k].sum() for k in range(1, len(slen)+1)])/slen.sum()
            obmx = np.hstack(                               \
                            (                             \
                                bf0(ssum).reshape(ascol), \
                                bf1(ssum).reshape(ascol), \
                                bf2(ssum).reshape(ascol), \
                                bf3(ssum).reshape(ascol)  \
                            )                             \
                            )
            return np.linalg.lstsq(obmx, plotpoints, -1)
        crv = bpy.data.curves.new(NME + '.Curve', type='CURVE')
        for ob in objs:
            aod = ob.data
            vb = np.array([v.co for v in aod.vertices])
            stack = [slice(0, len(vb), 1)]
            sset = list()
            while bool(stack):
                solution, residue, rank, singular = tryfit(vb[stack[-1]])
                ltol = np.sqrt((residue**2.0).sum())
                if (ltol < TOL) or (len(vb[stack[-1]]) < MINPTS):
                    stack.pop()
                    sset.insert(0, solution)
                else:
                    lslice = stack.pop()
                    stack += splitslice(lslice)
            DLEN = len(sset)
            BINDX = 0
            crv.dimensions = '3D'
            bseg = crv.splines.new('BEZIER')
            bseg.bezier_points.add(DLEN)
            bseg.resolution_u = RES
            while bool(sset):
                dp = sset.pop()
                if not BINDX:
                    bseg.bezier_points[BINDX].handle_left_type = 'FREE'
                    bseg.bezier_points[BINDX].handle_left = Vector(dp[0])
                    bseg.bezier_points[BINDX].co = Vector(dp[0])
                    bseg.bezier_points[BINDX].handle_right = Vector(dp[1])
                    bseg.bezier_points[BINDX].handle_right_type = 'ALIGNED'
                    bseg.bezier_points[BINDX + 1].handle_left = Vector(dp[2])
                    bseg.bezier_points[BINDX + 1].handle_left_type = 'ALIGNED'
                elif bool(sset):
                    bseg.bezier_points[BINDX].co = Vector(dp[0])
                    bseg.bezier_points[BINDX].handle_right_type = 'ALIGNED'
                    bseg.bezier_points[BINDX].handle_right = Vector(dp[1])
                    bseg.bezier_points[BINDX + 1].handle_left = Vector(dp[2])
                    bseg.bezier_points[BINDX + 1].handle_left_type = 'ALIGNED'
                else:
                    bseg.bezier_points[BINDX].co = Vector(dp[0])
                    bseg.bezier_points[BINDX].handle_right = Vector(dp[1])
                    bseg.bezier_points[BINDX].handle_right_type = 'ALIGNED'
                    bseg.bezier_points[BINDX + 1].handle_left = Vector(dp[2])
                    bseg.bezier_points[BINDX + 1].handle_left_type = 'ALIGNED'
                    bseg.bezier_points[BINDX + 1].co = Vector(dp[3])
                    bseg.bezier_points[BINDX + 1].handle_right = Vector(dp[3])
                    bseg.bezier_points[BINDX + 1].handle_right_type = 'FREE'
                BINDX += 1
        temp_name = self.ob.name
        bobj = bpy.data.objects.new(NME, crv)
        bobj.matrix_world = Matrix(bobj.matrix_world @ self.ob.matrix_world)
        self.context.collection.objects.link(bobj)
        bobj.select_set(True)
        super_remove(objs, self.context)
        self.ob = bobj
        self.ob.name = temp_name
        self.restore_bevel()
        for spline in self.ob.data.splines:
            spline.use_smooth = True
        super_select(bobj, self.context)
        for spline in bobj.data.splines:
            points = spline.bezier_points
            points_originals = [
                [point.co.copy() for point in points],
                [point.handle_left.copy() for point in points],
                [point.handle_right.copy() for point in points],
            ]
            points_originals[0].reverse()
            points_originals[1].reverse()
            points_originals[2].reverse()
            for index, point in enumerate(points):
                point.co = points_originals[0][index]
                point.handle_left = points_originals[2][index]
                point.handle_right = points_originals[1][index]
        return bobj
    """From the Simplify Curves+ addon that's not available anymore in 4.2"""
    def remove_double(self, distance = 0.01):
        context = self.context
        selected_Curves = context.selected_objects
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='EDIT')
        bezier_dellist = []
        dellist = []
        for curve in selected_Curves:
            for spline in curve.data.splines:
                if spline.type == 'BEZIER':
                    if len(spline.bezier_points) > 1:
                        for i in range(0, len(spline.bezier_points)):
                            if i == 0:
                                ii = len(spline.bezier_points) - 1
                            else:
                                ii = i - 1
                            dot = spline.bezier_points[i]
                            dot1 = spline.bezier_points[ii]
                            while dot1 in bezier_dellist and i != ii:
                                ii -= 1
                                if ii < 0:
                                    ii = len(spline.bezier_points)-1
                                dot1 = spline.bezier_points[ii]
                            if dot.select_control_point and dot1.select_control_point and (i!=0 or spline.use_cyclic_u):
                                if (dot.co-dot1.co).length < distance:
                                    dot1.handle_right_type = "FREE"
                                    dot1.handle_right = dot.handle_right
                                    dot1.co = (dot.co + dot1.co) / 2
                                    bezier_dellist.append(dot)
                                else:
                                    if dot.handle_left_type == 'VECTOR' and (dot1.handle_right - dot1.co).length < distance:
                                        dot1.handle_right_type = "VECTOR"
                                    if dot1.handle_right_type == 'VECTOR' and (dot.handle_left - dot.co).length < distance:
                                        dot.handle_left_type = "VECTOR"
                else:
                    if len(spline.points) > 1:
                        for i in range(0, len(spline.points)):
                            if i == 0:
                                ii = len(spline.points) - 1
                            else:
                                ii = i - 1
                            dot = spline.points[i];
                            dot1 = spline.points[ii];
                            while dot1 in dellist and i != ii:
                                ii -= 1
                                if ii < 0:
                                    ii = len(spline.points)-1
                                dot1 = spline.points[ii]
                            if dot.select and dot1.select and (i!=0 or spline.use_cyclic_u):
                                if (dot.co-dot1.co).length < distance:
                                    dot1.co = (dot.co + dot1.co) / 2
                                    dellist.append(dot)
        bpy.ops.curve.select_all(action = 'DESELECT')
        for dot in bezier_dellist:
            dot.select_control_point = True
        for dot in dellist:
            dot.select = True
        bezier_count = len(bezier_dellist)
        count = len(dellist)
        bpy.ops.curve.delete(type = 'VERT')
        bpy.ops.curve.select_all(action = 'DESELECT')
        return bezier_count + count
    def main(self):
        self.clo_make_colliders()
        super_select(self.ob, self.context)
        if self.multiplier != 1:
            self.subdivide()
        self.points_data = self.clo_get_points_data()
        if not self.points_data:
            return False
        self.clo_verts, self.spline_mods = self.clo_convert_to_mesh()
        self.clo_create_vert_groups()
        self.clo_add_extrude()
        if self.debug:
            self.clo_add_cloth(1, 401)
        else:
            if self.use_end_frame:
                self.clo_add_cloth(-(self.end_frame - 2), 1)
            else:
                self.clo_add_cloth(-398, 1)
        self.clo_bake_cloth()
        self.clo_remove_verts()
        self.clo_remove_colliders()
        if self.debug:
            return True
        if self.recalc:
            self.curve = self.fit_curve()
            super_select(self.curve, self.context)
        else:
            self.curve = self.dissolve_curve()
        self.clo_restore_handles()
        for mat in self.init_curve['mats']:
            self.curve.data.materials.append(mat)
        self.curve.data.name = self.curve_name
        for curve in bpy.data.curves:
            if curve.users == 0 and not curve.use_fake_user:
                bpy.data.curves.remove(curve, do_unlink=True)
        return True
    def execute(self, context):
        self.context = context
        self.mode = self.context.active_object.mode
        try:
            self.ob, self.meshes = self.get_simulated()
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.collision_objects = list()
        self.curve_name = self.ob.data.name
        self.init_curve = {
            'resolution_u': self.ob.data.resolution_u,
            'bevel_mode': self.ob.data.bevel_mode if GV.is291 else 'OBJECT' if self.ob.data.bevel_object else 'ROUND',
            'bevel_depth': self.ob.data.bevel_depth,
            'bevel_object': self.ob.data.bevel_object,
            'mats': self.ob.data.materials,
        }
        result = self.main()
        if not result:
            return {'CANCELLED'}
        return {'FINISHED'}
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "recalc")
        layout.prop(self, "add_expand")
        layout.prop(self, "multiplier")
        layout.prop(self, "debug")
        if not self.debug:
            layout.prop(self, "use_end_frame")
        if self.use_end_frame:
            layout.prop(self, "end_frame")
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
def register():
    bpy.utils.register_class(CBL_OT_SimulateCableDialog)
def unregister():
    bpy.utils.unregister_class(CBL_OT_SimulateCableDialog)
