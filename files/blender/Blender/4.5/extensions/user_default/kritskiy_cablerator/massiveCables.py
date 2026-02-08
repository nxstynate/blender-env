import bpy
from .lib import *
from .ui import *
from .inits import *
from .typing import *
from math import radians, degrees
class CBL_OT_MassiveCables(bpy.types.Operator):
  """Select two islands of faces"""
  bl_idname = "cbl.massive_cables"
  bl_label = "Cablerator: Create a Cable Mass"
  bl_options = {'REGISTER', 'UNDO'}
  def bool_r(self):
    key = 'R'
    self.do_subdivide = self.bools['R']['status']
    self.width = self.events['S']['cur_value']
    self.recalc_massive()
    self.def_cable_count = self.events['Z']['cur_value']
    self.cable_count = self.calc_count()
    self.events['Z']['cur_value'] = self.cable_count
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
  def resolve_key_S(self, item):
    if self.cur_value < 0.00005:
        self.cur_value = 0.00005
        item['cur_value'] = 0.00005
    self.width = item['cur_value']
    edit_curves(self, 'S')
  def resolve_key_V(self, item):
    if self.cur_value < 1:
          self.cur_value = 1
          item['cur_value'] = 1
    self.width = item['cur_value']
    edit_curves(self, 'V')
  def resolve_key_D(self, item):
    if self.cur_value < 0:
        self.cur_value = 0
        item['cur_value'] = 0
    self.strength = item['cur_value']
    self.change_curve_tension()
    self.init_ten = item['cur_value']
  def resolve_key_N(self, item):
    if self.cur_value < 0:
        self.cur_value = 0
        item['cur_value'] = 0
    self.randomize_tension = item['cur_value']
    self.change_curve_tension()
    self.init_ten = item['cur_value']
  def resolve_key_F(self, item):
    if self.cur_value < 1:
        self.cur_value = 1
        item['cur_value'] = 1
    edit_curves(self, 'F')
  def resolve_key_T(self, item):
    s = item['cur_value']
    self.pickers['A']['object'].scale = s,s,s
  def resolve_key_Z(self, item):
    if item['cur_value'] > self.max_cable_count:
      self.cur_value = self.max_cable_count
      item['cur_value'] = self.max_cable_count
    elif item['cur_value'] < 1:
      self.cur_value = 1
      item['cur_value'] = 1
    if self.prev_count != item['cur_value']:
      self.prev_count = item['cur_value']
      self.cable_count = item['cur_value']
      self.recalc_massive()
  def join(self, list_of_bmeshes):
      bm = bmesh.new()
      add_vert = bm.verts.new
      add_face = bm.faces.new
      add_edge = bm.edges.new
      for item in list_of_bmeshes:
          bm_to_add, mw = item
          offset = len(bm.verts)
          for v in bm_to_add.verts:
              add_vert(mw @ v.co)
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
  def get_islands(self, bm):
      def walk_island(vert):
          vert.tag = True
          yield(vert)
          linked_verts = [e.other_vert(vert) for e in vert.link_edges
                  if not e.other_vert(vert).tag]
          for v in linked_verts:
              if v.tag:
                  continue
              yield from walk_island(v)
      def get_islands(bm, verts=[]):
          def tag(verts, switch):
              for v in verts:
                  v.tag = switch
          tag(bm.verts, True)
          tag(verts, False)
          ret = {"islands" : []}
          verts = set(verts)
          while verts:
              v = verts.pop()
              verts.add(v)
              island = set(walk_island(v))
              ret["islands"].append(list(island))
              tag(island, False)
              verts -= island
          return ret
      islands = [island for island in get_islands(bm, verts=bm.verts)["islands"]]
      faces = []
      indices = []
      for verts in islands:
          faces = []
          faces = set(sum((list(vert.link_faces) for vert in verts), []))
          f_indices = list(set([face.index for face in faces]))
          indices.append(f_indices)
      return indices
  def remove_unselected(self, bm):
      delete_faces = [f for f in bm.faces if not f.select]
      bmesh.ops.delete(bm, geom=delete_faces, context="FACES")
      return bm
  def create_obj(self, bm):
      mesh = bpy.data.meshes.new("mesh")
      obj = bpy.data.objects.new("MyObject", mesh)
      self.context.scene.collection.objects.link(obj)
      bm.to_mesh(obj.data)
      obj.data.update()
  def subdivide(self):
    def tri_area( co1, co2, co3 ):
        return (co2 - co1).cross( co3 - co1 ).length / 2.0
    if self.do_subdivide:
      for bm in self.bms:
        inset_faces = bmesh.ops.inset_region(bm, faces = bm.faces, thickness=self.width * .66, use_boundary=True)
        bmesh.ops.delete(bm, geom=inset_faces['faces'], context="FACES")
        bmesh.ops.split_edges(bm, edges=bm.edges)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.faces.ensure_lookup_table()
        for face in bm.faces:
          face_area = tri_area( *(v.co for v in face.verts) )
        upper_length = self.width * 2.4 + (self.width * 2.4) * 0.25
        lower_length = self.width * 2.4 - (self.width * 2.4) * 0.25
        for i in range(20):
            subdivide = []
            bm.faces.ensure_lookup_table()
            if len(bm.faces) >= 512:
              break
            for edge in bm.edges:
                if edge.calc_length() > upper_length:
                    subdivide.append(edge)
            if not subdivide:
              break
            bmesh.ops.subdivide_edges(bm, edges=subdivide, cuts=1)
            bmesh.ops.triangulate(bm, faces=bm.faces)
            dissolve_verts = []
            for vert in bm.verts:
                if len(vert.link_edges) < 5:
                    if not vert.is_boundary:
                        dissolve_verts.append(vert)
            bmesh.ops.dissolve_verts(bm, verts=dissolve_verts)
            bmesh.ops.triangulate(bm, faces=bm.faces)
            lock_verts = set(vert for vert in bm.verts if vert.is_boundary)
            collapse = []
            for edge in bm.edges:
                if edge.calc_length() < lower_length and not edge.is_boundary:
                    verts = set(edge.verts)
                    if verts & lock_verts:
                        continue
                    collapse.append(edge)
                    lock_verts |= verts
            bmesh.ops.collapse(bm, edges=collapse)
            bmesh.ops.beautify_fill(bm, faces=bm.faces, method="ANGLE")
        bmesh.ops.join_triangles(bm, faces=bm.faces, angle_face_threshold=3.14, angle_shape_threshold=3.14)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.00005)
    def flatten(S):
        if S == []:
            return S
        if isinstance(S[0], list):
            return flatten(S[0]) + flatten(S[1:])
        return S[:1] + flatten(S[1:])
    if self.two_objs:
      f1 = self.get_islands(self.bms[0])
      f2 = self.get_islands(self.bms[1])
      if not f1 or not f2:
        return False
      return [flatten(f1), flatten(f2)]
    else:
      return self.get_islands(self.bms[0])
  def clear(self):
      for bm in self.bms:
        try:
            bm.clear()
            bm.free()
        except Exception as e:
            pass
      try:
          self.bm.clear()
          self.bm.free()
      except Exception as e:
          pass
  def cancel_massive(self):
    super_remove(self.objects, self.context)
    switch_mode('EDIT')
  def finish(self):
    if self.events['G']['cur_value'] != 0:
      set_active(self.objects[0], self.context)
      switch_mode('EDIT')
      bpy.ops.curve.select_all(action='SELECT')
      bpy.ops.curve.subdivide(number_cuts=self.events['G']['cur_value'])
      switch_mode('OBJECT')
    for ob in self.objects:
      for spline in ob.data.splines:
        for pindex, point in enumerate(spline.bezier_points):
          if pindex == 0 or pindex == len(spline.bezier_points) - 1:
            point.select_right_handle = False
            point.select_left_handle = False
            point.select_control_point = False
    super_select(self.objects[0], self.context)
  def change_curve_tension(self):
    normal_multiplier = self.strength
    random_multipier = self.randomize_tension
    for i in range(len(self.points)):
      spline = self.objects[0].data.splines[i]
      p1 = spline.bezier_points[0]
      p2 = spline.bezier_points[1]
      normal1 = self.points[i]['p1']['normal']
      normal2 = self.points[i]['p2']['normal']
      p1_ran = self.points[i]['p1']['ran']
      p2_ran = self.points[i]['p2']['ran']
      p1.handle_right = p1.co + normal1 * (normal_multiplier + p1_ran * random_multipier)
      p1.handle_left = p1.co - normal1
      p2.handle_right = p2.co - normal2
      p2.handle_left = p2.co + normal2 * (normal_multiplier + p2_ran * random_multipier)
  def create_massive(self):
      if self.two_objs:
        self.bms[0].faces.ensure_lookup_table()
        self.bms[1].faces.ensure_lookup_table()
      else:
        self.bms[0].faces.ensure_lookup_table()
      if len(self.objects):
        super_remove(self.objects, self.context)
        self.objects = list()
      faces1 = self.use_faces[0]
      faces2 = self.use_faces[1]
      num_of_random = self.cable_count
      normal_multiplier = self.strength
      random_multipier = self.randomize_tension
      my_rand1 = sample(range(len(faces1)), num_of_random)
      my_rand2 = sample(range(len(faces2)), num_of_random)
      curve_name = "Cable Mass"
      curveData = bpy.data.curves.new(curve_name, type='CURVE')
      curveData.dimensions = '3D'
      curveData.resolution_u = self.res
      curveData.bevel_resolution = self.bevel_res
      curveData.bevel_depth = self.width
      if hasattr(self, 'pickers') and self.pickers['A']['object']:
        if GV.is291: curveData.bevel_mode = 'OBJECT'
        curveData.bevel_object = self.pickers['A']['object']
      curve = bpy.data.objects.new(curve_name, curveData)
      scn = bpy.context.scene
      scn.collection.objects.link(curve)
      self.objects = [curve]
      self.points = list()
      for i in range(num_of_random):
        findex1 = faces1[my_rand1[i]]
        findex2 = faces2[my_rand2[i]]
        if self.two_objs:
          center1 = self.bms[0].faces[findex1].calc_center_median()
          normal1 = self.bms[0].faces[findex1].normal
          center2 = self.bms[1].faces[findex2].calc_center_median()
          normal2 = self.bms[1].faces[findex2].normal
        else:
          center1 = self.bms[0].faces[findex1].calc_center_median()
          normal1 = self.bms[0].faces[findex1].normal
          center2 = self.bms[0].faces[findex2].calc_center_median()
          normal2 = self.bms[0].faces[findex2].normal
        spline = curveData.splines.new('BEZIER')
        spline.bezier_points.add(1)
        p1 = spline.bezier_points[0]
        p2 = spline.bezier_points[1]
        p1.handle_right_type = 'ALIGNED'
        p2.handle_right_type = 'ALIGNED'
        p1.handle_left_type = 'ALIGNED'
        p2.handle_left_type = 'ALIGNED'
        p1.co = center1
        p1_ran = uniform(0, 1)
        p1.handle_right = p1.co + normal1 * (normal_multiplier + p1_ran * random_multipier)
        p1.handle_left = p1.co - normal1
        p2.co = center2
        p2_ran = uniform(0, 1)
        p2.handle_right = p2.co - normal2
        p2.handle_left = p2.co + normal2 * (normal_multiplier + p2_ran * random_multipier)
        self.points.append({
          'p1': {
            'co': p1.co.copy(),
            'ran': p1_ran,
            'normal': normal1.copy()
          },
          'p2': {
            'co': p2.co.copy(),
            'ran': p2_ran,
            'normal': normal2.copy()
          },
          })
  def calc_count(self):
    counts = {len(self.use_faces[0]),len(self.use_faces[1]),self.def_cable_count}
    return min(counts)
  def calc_max_count(self):
    c1 = len(self.use_faces[0])
    c2 = len(self.use_faces[1])
    if c1 > c2:
      return c2
    else:
      return c1
  def recalc_massive(self):
    for bm in self.bms:
      try:
          bm.clear()
          bm.free()
      except Exception as e:
          pass
    self.def_cable_count = self.cable_count
    if self.two_objs:
      self.bm1_copy = self.bm1.copy()
      self.bm2_copy = self.bm2.copy()
      self.bms = [self.bm1_copy, self.bm2_copy]
    else:
      self.bm_copy = self.bm.copy()
      self.bms = [self.bm_copy]
    self.use_faces = self.subdivide()
    self.cable_count = self.calc_count()
    self.max_cable_count = self.calc_max_count()
    self.create_massive()
  @classmethod
  def poll(cls, context):
      return context.active_object is not None and context.object.mode == 'EDIT'
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
            clean_pickers(self)
            self.first_mouse_x = event.mouse_x
            for key in self.events.keys():
                if event.type == key:
                    if self.events[key]['status']:
                        self.events[key]['status'] = False
                        self.can_type = False
                        if key == 'S':
                          self.width = self.events[key]['cur_value']
                          self.recalc_massive()
                          self.def_cable_count = self.events['Z']['cur_value']
                          self.cable_count = self.calc_count()
                          self.events['Z']['cur_value'] = self.cable_count
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
                    elif key == 'R':
                      self.bool_r()
            return {'RUNNING_MODAL'}
        if event.type in self.actions.keys() and event.value == "PRESS":
            clean_pickers(self)
            clean_events(self)
            for key in self.actions.keys():
                if event.type == key:
                    if key == 'Q' and self.actions[key]['status']:
                        self.recalc_massive()
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
                        self.last_key = key
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
                          self.resolve_key_S(item)
                        elif key == 'V':
                          self.resolve_key_V(item)
                        elif key == 'D':
                          self.resolve_key_D(item)
                        elif key == 'N':
                          self.resolve_key_N(item)
                        elif key == 'F':
                          self.resolve_key_F(item)
                        elif key == 'T' and self.pickers['A']['object']:
                          self.resolve_key_T(item)
                        elif key == 'Z':
                          self.resolve_key_Z(item)
            else:
                if self.last_key == 'S':
                  self.width = self.events['S']['cur_value']
                  self.recalc_massive()
                  self.def_cable_count = self.events['Z']['cur_value']
                  self.cable_count = self.calc_count()
                  self.events['Z']['cur_value'] = self.cable_count
                self.can_type = False
                clean_events(self)
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
          wheel_val = 0.1 if event.type == 'WHEELUPMOUSE' else -0.1
          if self.events['S']['status']:
            item = self.events['S']
            item['cur_value'] = normal_round((item['cur_value'] + wheel_val)*10)/10
            if item['cur_value'] < 0.00005: item['cur_value'] = 0.00005
            self.first_value = item['cur_value']
            self.first_unchanged_value = item['cur_value']
            self.cur_value = item['cur_value']
            self.first_mouse_x = event.mouse_x
            self.resolve_key_S(item)
          elif self.events['G']['status']:
            item = self.events['G']
            item['cur_value'] += int(wheel_val*10)
            if item['cur_value'] < 0: item['cur_value'] = 0
            self.first_value = item['cur_value']
            self.first_unchanged_value = item['cur_value']
            self.cur_value = item['cur_value']
            self.first_mouse_x = event.mouse_x
          elif self.events['D']['status']:
            item = self.events['D']
            item['cur_value'] = normal_round((item['cur_value'] + wheel_val*4)*2.5)/2.5
            if item['cur_value'] < 0: item['cur_value'] = 0
            self.first_value = item['cur_value']
            self.first_unchanged_value = item['cur_value']
            self.cur_value = item['cur_value']
            self.first_mouse_x = event.mouse_x
            self.resolve_key_D(item)
          elif self.events['N']['status']:
            item = self.events['N']
            item['cur_value'] = normal_round((item['cur_value'] + wheel_val*4)*2.5)/2.5
            if item['cur_value'] < 0.001: item['cur_value'] = 0.001
            self.first_value = item['cur_value']
            self.first_unchanged_value = item['cur_value']
            self.cur_value = item['cur_value']
            self.first_mouse_x = event.mouse_x
            self.resolve_key_N(item)
          elif self.events['F']['status']:
            item = self.events['F']
            item['cur_value'] += int(wheel_val*10)
            if item['cur_value'] < 1: item['cur_value'] = 1
            self.first_value = item['cur_value']
            self.first_unchanged_value = item['cur_value']
            self.cur_value = item['cur_value']
            self.first_mouse_x = event.mouse_x
            self.resolve_key_F(item)
          elif self.events['Z']['status']:
            item = self.events['Z']
            item['cur_value'] += int(wheel_val*10)
            if item['cur_value'] > self.max_cable_count:
              self.cur_value = self.max_cable_count
              item['cur_value'] = self.max_cable_count
            elif item['cur_value'] < 1:
              self.cur_value = 1
              item['cur_value'] = 1
            self.first_value = item['cur_value']
            self.first_unchanged_value = item['cur_value']
            self.cur_value = item['cur_value']
            self.first_mouse_x = event.mouse_x
            self.cable_count = item['cur_value']
            self.resolve_key_Z(item)
          elif self.events['V']['status']:
            item = self.events['V']
            item['cur_value'] += int(wheel_val*10)
            if item['cur_value'] < 0: item['cur_value'] = 0
            self.first_value = item['cur_value']
            self.first_unchanged_value = item['cur_value']
            self.cur_value = item['cur_value']
            self.first_mouse_x = event.mouse_x
            self.resolve_key_V(item)
          elif self.events['T']['status'] and self.pickers['A']['object']:
            item = self.events['T']
            item['cur_value'] = normal_round((item['cur_value'] + wheel_val)*10)/10
            if item['cur_value'] < 0: item['cur_value'] = 0
            self.first_value = item['cur_value']
            self.first_unchanged_value = item['cur_value']
            self.cur_value = item['cur_value']
            self.first_mouse_x = event.mouse_x
            self.resolve_key_T(item)
          else:
            return {'PASS_THROUGH'}
        elif event.type == 'MOUSEMOVE':
            handle_hover(self, event)
            if self.typing: return {'RUNNING_MODAL'}
            for key in self.events.keys():
                item = self.events[key]
                if item['status']:
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
                          self.resolve_key_S(item)
                        elif key == 'V':
                          self.resolve_key_V(item)
                        elif key == 'D':
                          self.resolve_key_D(item)
                        elif key == 'N':
                          self.resolve_key_N(item)
                        elif key == 'F':
                          self.resolve_key_F(item)
                        elif key == 'T' and self.pickers['A']['object']:
                          self.resolve_key_T(item)
                        elif key == 'Z':
                          self.resolve_key_Z(item)
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
                    if key == 'S':
                      self.width = self.events[key]['cur_value']
                      self.recalc_massive()
                      self.def_cable_count = self.events['Z']['cur_value']
                      self.cable_count = self.calc_count()
                      self.events['Z']['cur_value'] = self.cable_count
                    self.can_type = False
                    return {'RUNNING_MODAL'}
            for key in self.pickers.keys():
                if self.pickers[key]['status']:
                    self.pickers[key]['status'] = False
                    self.pickers[key]['selecting'] = False
                    self.can_type = False
                    return {'RUNNING_MODAL'}
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self.clear()
            self.finish()
            return {'FINISHED'}
        elif event.type in self.cancel_buttons and event.value == "PRESS":
            for key in self.events:
                if self.events[key]['status']:
                    self.events[key]['cur_value'] = self.first_unchanged_value
                    edit_curves(self, key)
                    if key == 'D':
                      self.strength = self.events[key]['cur_value']
                      self.change_curve_tension()
                    elif key == 'N':
                      self.strength = self.events[key]['cur_value']
                      self.change_curve_tension()
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
            self.clear()
            self.cancel_massive()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
      except Exception as e:
        traceback.print_exc()
        self.report({'ERROR'}, str(e))
        self.clear()
        self.cancel_massive()
        return {'CANCELLED'}
  def invoke(self, context, event):
    self.typing = False
    self.can_type = False
    self.my_num_str = ""
    self.last_key = ''
    self.text_ui_rect_batch = {
          "ui_rect": [],
          "items": {},
          "key": None,
          "inside_ui_rect": False,
      }
    self.bms = list()
    self.objects = list()
    self.res = 20
    self.bevel_res = 6
    self.twist = 0
    self.width = 0
    self.show_res = True
    self.show_bevel_res = True
    self.show_twist = True
    self.randomize_tension = 2.5
    self.active_tool = context.workspace.tools.from_space_view3d_mode("OBJECT", create=False).idname
    self.right_click = 0
    self.do_subdivide = True
    self.prev_count = -1
    get_prefs(self, context)
    self.strength = 1.5
    switch_mode('OBJECT')
    self.context = context
    self.obs = context.selected_objects
    if len(self.obs) > 2 or not self.obs:
        self.report({'ERROR'}, 'Expected to have up to two objects selected, aborting')
        switch_mode('EDIT')
        return {'CANCELLED'}
    self.two_objs = len(self.obs) == 2
    if self.two_objs:
        self.bm1 = bmesh.new()
        self.bm1.from_mesh(self.obs[0].data)
        self.bm1 = self.remove_unselected(self.bm1)
        for v in self.bm1.verts:
            v.co = self.obs[0].matrix_world @ v.co
        self.bm2 = bmesh.new()
        self.bm2.from_mesh(self.obs[1].data)
        self.bm2 = self.remove_unselected(self.bm2)
        for v in self.bm2.verts:
            v.co = self.obs[1].matrix_world @ v.co
        edges = set()
        for edge in self.bm1.edges:
          edges.add(edge.calc_length())
        for edge in self.bm2.edges:
          edges.add(edge.calc_length())
    else:
        self.bm = bmesh.new()
        self.bm.from_mesh(self.obs[0].data)
        self.bm = self.remove_unselected(self.bm)
        for v in self.bm.verts:
            v.co = self.obs[0].matrix_world @ v.co
        edges = set()
        for edge in self.bm.edges:
          edges.add(edge.calc_length())
    try:
      min_edge = min(edges)
    except Exception as e:
      self.report({'ERROR'}, 'No faces were selected? Aboring')
      switch_mode('EDIT')
      return {'CANCELLED'}
    if min_edge < 0.05 and self.do_subdivide:
      self.report({'INFO'}, 'Note that the resulting edges are too small, unexpected results may occur')
    if min_edge < self.width: self.width = min_edge
    if not self.two_objs:
      self.islands = self.get_islands(self.bm)
      if len(self.islands) != 2:
          self.report({'ERROR'}, f'Expected to have exactly 2 face islands selected, found {len(self.islands)}, aborting')
          self.clear()
          switch_mode('EDIT')
          return {'CANCELLED'}
    if self.two_objs:
      self.bm1.normal_update()
      self.bm2.normal_update()
      self.bm1_copy = self.bm1.copy()
      self.bm2_copy = self.bm2.copy()
      self.bms = [self.bm1_copy, self.bm2_copy]
    else:
      self.bm.normal_update()
      self.bm_copy = self.bm.copy()
      self.bms = [self.bm_copy]
    self.use_faces = self.subdivide()
    if not self.use_faces:
      self.report({'ERROR'}, f'One of the selected objects doesn\'t have any faces selected, aborting')
      self.clear()
      switch_mode('EDIT')
      return {'CANCELLED'}
    self.def_cable_count = 10
    self.cable_count = self.calc_count()
    self.max_cable_count = self.calc_max_count()
    self.create_massive()
    self.show_curve_length = False
    self.button = 'RIGHTMOUSE' if self.right_click == '1' else 'LEFTMOUSE'
    self.title="Create a Mass of Cables."
    self.actions = {
        'Q': {
            'name': 'Randomize (Q)',
            'status': True,
            'show': True,
        },
    }
    self.events = {
        'T': {
            'name': 'Scale Profile (T)',
            'status': False,
            'cur_value': 1,
            'type': 'float',
            'show': False
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
        'N': {
            'name': 'Randomize Tension (N)',
            'status': False,
            'cur_value': self.randomize_tension,
            'type': 'float',
            'show': True
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
        },
        'Z': {
            'name': 'Cables Count (Z)',
            'status': False,
            'cur_value': self.cable_count,
            'type': 'int',
            'show': True
        },
    }
    self.prev_count = self.cable_count
    self.bools = {
      'R': {
          'name': 'Random Face Points (R)',
          'status': True,
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
        self.clear()
        return {'CANCELLED'}
def register():
    bpy.utils.register_class(CBL_OT_MassiveCables)
def unregister():
    bpy.utils.unregister_class(CBL_OT_MassiveCables)