import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_circle_2d
import bpy.utils.previews
from .lib import *
if GV.before32: import bgl
def hide_hud():
    space_data = bpy.context.space_data
    sidebar = space_data.show_region_ui
    redo = space_data.show_region_hud
    if redo:
        space_data.show_region_hud = False
    return redo
def show_hud(hud_info):
    redo = hud_info
    space_data = bpy.context.space_data
    if redo:
        space_data.show_region_hud = True
class FontGlobal:
    size = 13
    font_id = 0
    ui_scale = bpy.context.preferences.system.ui_scale
    dpi = normal_round(72 * bpy.context.preferences.system.ui_scale)
    hidden_modules = False
def get_view(context, x, y):
    scene = context.scene
    area = context.area
    region = area.regions[-1]
    space = area.spaces.active
    rv3d = space.region_3d
    return region
    if (x >= region.x and
        y >= region.y and
        x < region.width + region.x and
        y < region.height + region.y):
        return region
    for area in context.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        for region in area.regions:
            if region.type == 'WINDOW':
                if (x >= region.x and
                    y >= region.y and
                    x < region.width + region.x and
                    y < region.height + region.y):
                    return region
    return None
def get_column_height(self):
    count = 2 if self.show_curve_length else 1
    if hasattr(self, 'bools'):
        for k, v in self.bools.items():
            if not v['show']:
                if k != 'A':
                    FontGlobal.hidden_modules = True
                continue
            count += 1
    if hasattr(self, 'events'):
        for k, v in self.events.items():
            if not v['show']:
                FontGlobal.hidden_modules = True
                continue
            count += 1
    if hasattr(self, 'status'):
        for k, v in self.status.items():
            count += 1
    if hasattr(self, 'enums'):
        for k, v in self.enums.items():
            if not v['show']:
                FontGlobal.hidden_modules = True
                continue
            count += 1
    if hasattr(self, 'actions'):
        for k, v in self.actions.items():
            if not v['show']:
                FontGlobal.hidden_modules = True
                continue
            count += 1
    if hasattr(self, 'empty'):
        for item in self.empty:
            count += 1
    if hasattr(self, 'pickers'):
        for k, v in self.pickers.items():
            if not v['show']:
                FontGlobal.hidden_modules = True
                continue
            count += 1
    return count * FontGlobal.LN
def get_column_width(self,font_id,size, dpi):
    line_width = -1
    min_width = -1
    add_width = 0
    if GV.after4:
        blf.size(font_id, size * FontGlobal.ui_scale)
    else:
        blf.size(font_id, size, dpi)
    if hasattr(self, 'bools'):
        for k, v in self.bools.items():
            if not v['show']:
                continue
            line_width = blf.dimensions(font_id, v['name'] + ": ")[0]
            if line_width > min_width:
                min_width = line_width
        bools_text = ['Yes', 'No', 'Set', 'Not Set']
        for text in bools_text:
            line_width = blf.dimensions(font_id, text)[0]
            if line_width > add_width:
                add_width = line_width
    if hasattr(self, 'actions'):
        for k, v in self.actions.items():
            if not v['show']:
                continue
            line_width = blf.dimensions(font_id, v['name'] + ": ")[0]
            if line_width > min_width:
                min_width = line_width
    if hasattr(self, 'pickers'):
        for k, v in self.pickers.items():
            if not v['show']:
                continue
            line_width = blf.dimensions(font_id, v['name'] + ": ")[0]
            if line_width > min_width:
                min_width = line_width
            line_width = blf.dimensions(font_id, "Select an object...")[0]
            if line_width > add_width:
                add_width = line_width
    if hasattr(self, 'events'):
        for k, v in self.events.items():
            if not v['show']:
                continue
            line_width = blf.dimensions(font_id, v['name'] + ": ")[0]
            if line_width > min_width:
                min_width = line_width
            line_width = blf.dimensions(font_id, "100.000")[0]
            if line_width > add_width:
                add_width = line_width
    if hasattr(self, 'status'):
        for k, v in self.status.items():
            line_width = blf.dimensions(font_id, v['name'] + ": ")[0]
            if line_width > min_width:
                min_width = line_width
    if hasattr(self, 'enums'):
        for k, v in self.enums.items():
            if not v['show']:
                continue
            line_width = blf.dimensions(font_id, v['name'] + ": ")[0]
            if line_width > min_width:
                min_width = line_width
            for enum_item in v['items']:
                try:
                    line_width = blf.dimensions(font_id, enum_item[1])[0]
                    if line_width > add_width:
                        add_width = line_width
                except Exception as e:
                    self.report({'ERROR'}, str(e))
                    pass
    if hasattr(self, 'title'):
        line_width = blf.dimensions(font_id, self.title)[0]
        if line_width > (min_width + add_width):
            add_width = line_width - min_width
    if hasattr(self, 'empty'):
        for item in self.empty:
            line_width = blf.dimensions(font_id, item)[0]
            if line_width > (min_width + add_width):
                add_width = line_width - min_width
    return (min_width, add_width)
def get_space(font_id,size, dpi):
    if GV.after4:
        blf.size(font_id, size * FontGlobal.ui_scale)
    else:
        blf.size(font_id, size, dpi)
    return blf.dimensions(font_id, ' ')[0]
def get_line(font_id,size, dpi):
    if GV.after4:
        blf.size(font_id, size * FontGlobal.ui_scale)
    else:
        blf.size(font_id, size, dpi)
    return blf.dimensions(font_id, 'M')[1] * 2
def draw_text(text, size, x, y, font_id, dpi, color=(1, 1, 1, 1)):
    if GV.after4:
        blf.size(font_id, size * FontGlobal.ui_scale)
    else:
        blf.size(font_id, size, dpi)
    blf.color(0, *color)
    blf.position(font_id, x, y, 0)
    blf.draw(font_id, text)
def handle_hover(self, event):
    saw_hover = False
    if self.text_ui_rect_batch["ui_rect"] and not self.can_type:
        mx, my = event.mouse_region_x, event.mouse_region_y
        if is_point_in_rect(mx, my, self.text_ui_rect_batch["ui_rect"]):
            self.text_ui_rect_batch["inside_ui_rect"] = True
            for key, v in self.text_ui_rect_batch["items"].items():
                if is_point_in_rect(mx, my, v):
                    self.text_ui_rect_batch["key"] = key
                    saw_hover = True
            if not saw_hover:
                self.text_ui_rect_batch["key"] = None
            self.text_ui_rect_batch["inside_ui_rect"] = False
        else: self.text_ui_rect_batch["key"] = None
def handle_hover_press(self):
    hover_key = self.text_ui_rect_batch["key"]
    bool_keys = self.bools.keys() if hasattr(self, 'bools') else []
    enum_keys = self.enums.keys() if hasattr(self, 'enums') else []
    if hover_key in bool_keys:
        self.bools[hover_key]['status'] = not self.bools[hover_key]['status']
        self.bool_functions[hover_key]()
    elif hover_key in enum_keys:
        change_enum_curvalue(self, hover_key)
        self.enum_functions[hover_key]()
    return {'RUNNING_MODAL'}
def change_enum_curvalue(self, key):
    if self.enums[key]['cur_value'] == len(self.enums[key]['items']) - 1:
        self.enums[key]['cur_value'] = 0
    else:
        self.enums[key]['cur_value'] += 1
def gen_ui_coords(item):
    rect_pos_x, rect_pos_y, rect_size = item
    return [
        (rect_pos_x, rect_pos_y - 5),
        (rect_pos_x + FontGlobal.column_width + FontGlobal.add_width, rect_pos_y - 5),
        (rect_pos_x + FontGlobal.column_width + FontGlobal.add_width, rect_pos_y + rect_size + (2 if bpy.context.preferences.system.ui_scale <= 1 else 10)),
        (rect_pos_x, rect_pos_y + rect_size + (2 if bpy.context.preferences.system.ui_scale <= 1 else 10)),
    ]
def draw_callback_px(self, context):
    if hasattr(self, 'init_area'):
        if bpy.context.area != self.init_area:
            return
    blf.enable(0, blf.SHADOW)
    blf.shadow_offset(0, 2, -2)
    blf.shadow(0, 3, 0, 0, 0, 1)
    if GV.before32:
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE_MINUS_SRC_ALPHA)
    else:
        gpu.state.blend_set('ALPHA_PREMULT')
    font_id = FontGlobal.font_id
    size = FontGlobal.size
    dpi = FontGlobal.dpi
    LN = FontGlobal.LN
    column_width = FontGlobal.column_width
    add_width = FontGlobal.add_width
    height = FontGlobal.column_height
    pos_x = self.reg.width / 4 - column_width
    pos_x = max(pos_x, 125)
    pos_y = self.reg.height / 3
    pos_y = max(pos_y, 5)
    count = 0
    bottom_add = LN * 1.5 if FontGlobal.hidden_modules else LN * .5
    vertices = (
        (pos_x - 10, pos_y - bottom_add),
        (pos_x + column_width + add_width + 10, pos_y - bottom_add),
        (pos_x + column_width + add_width + 10, pos_y + height),
        (pos_x - 10, pos_y + height)
    )
    self.ui_vertices = vertices
    self.ui_shader = create_2d_shader()
    self.ui_batch = batch_for_shader(self.ui_shader, 'TRI_FAN', {"pos": self.ui_vertices})
    self.ui_shader.bind()
    self.ui_shader.uniform_float("color", (0.12, 0.12, 0.12, .75))
    self.ui_batch.draw(self.ui_shader)
    if not hasattr(self, "text_ui_rect_batch"): self.text_ui_rect_batch = {
            "ui_rect": [],
            "items": {},
            "key": None,
            "inside_ui_rect": False,
        }
    self.text_ui_rect_batch["ui_rect"] = vertices
    if self.text_ui_rect_batch["key"]:
        key = self.text_ui_rect_batch["key"]
        rect_vertices = self.text_ui_rect_batch["items"][key]
        rect_shader = gpu.shader.from_builtin('UNIFORM_COLOR' if GV.after4 else '2D_UNIFORM_COLOR')
        ui_batch = batch_for_shader(rect_shader, 'TRI_FAN', {"pos": rect_vertices})
        if GV.before32:
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE_MINUS_SRC_ALPHA)
            rect_shader.bind()
            rect_shader.uniform_float("color", (0,0,0, .5))
            ui_batch.draw(rect_shader)
        else:
            gpu.state.blend_set('ALPHA')
            rect_shader.bind()
            rect_shader.uniform_float("color", (0,0,0, .5))
            ui_batch.draw(rect_shader)
            gpu.state.blend_set('NONE')
    if hasattr(self, 'actions'):
        for k, v in self.actions.items():
            if not v['show']:
                continue
            draw_text(v['name'],size, pos_x, pos_y +  LN * count, font_id, dpi, (1, 1, 1, 1 if v['status'] else 0.5))
            count += 1
    if hasattr(self, 'pickers'):
        for k, v in self.pickers.items():
            if not v['show']:
                continue
            if v['selecting']:
                v_text = v['vtext']
                v_color = (.25, .25, 1, 1)
            elif v['object']:
                v_text = 'Set'
                v_color = (1, 1, 1, 1)
            else:
                v_text = 'Not Set'
                v_color = (1, 1, 1, .5)
            draw_text(v['name'] + ": ",size, pos_x, pos_y +  LN * count, font_id, dpi)
            draw_text(v_text,size, pos_x + column_width, pos_y + LN * count, font_id, dpi, v_color)
            count += 1
    if hasattr(self, 'enums'):
        for k, v in self.enums.items():
            if not v['show']:
                continue
            draw_text(v['name'] + ": ",size, pos_x, pos_y +  LN * count, font_id, dpi)
            draw_text(v['items'][v['cur_value']][1],size, pos_x + column_width, pos_y +  LN * count, font_id, dpi, (1, 1, 1, 1))
            self.text_ui_rect_batch["items"][k] = gen_ui_coords([pos_x, pos_y +  LN * count, size])
            count += 1
    if hasattr(self, 'bools'):
        for k, v in self.bools.items():
            if not v['show']:
                continue
            if v['usable'] == True:
                v_text = "Yes" if v['status'] else "No"
            else:
                v_text = 'N/A'
            draw_text(v['name'] + ": ",size, pos_x, pos_y +  LN * count, font_id, dpi)
            draw_text(v_text, size, pos_x + column_width, pos_y + LN * count, font_id, dpi, (0.25, 1, 0.25, 1) if v['status'] else (1, 1, 1, 0.5))
            self.text_ui_rect_batch["items"][k] = gen_ui_coords([pos_x, pos_y +  LN * count, size])
            count += 1
    if hasattr(self, 'events'):
        for k, v in self.events.items():
            if v['type'] == 'float':
                v_text = "%.3f" % (v['cur_value'])
            elif v['type'] == 'int':
                v_text = str(v['cur_value'])
            if self.typing and v['status']:
                v_text = f"{self.my_num_str}|"
            if not v['show']:
                if v['status']:
                    draw_text(v['name'] + ": ",size, pos_x, pos_y - LN, font_id, dpi)
                    draw_text(v_text,size, pos_x + column_width, pos_y - LN, font_id, dpi, (1, 1, 1, 1 if v['status'] else 0.5))
                continue
            if (k == 'D') and self.show_curve_length:
                if self.curve_length == -1:
                    curve_length = 'Not Set'
                else:
                    curve_length = "%.3f" % (self.curve_length)
                draw_text('Cable Length: ', size, pos_x, pos_y +  LN * count, font_id, dpi, (1, 1, 1, 0.5))
                draw_text(curve_length, size, pos_x + column_width, pos_y +  LN * count, font_id, dpi, (1, 1, 1, 0.5))
                count += 1
            draw_text(v['name'] + ": ",size, pos_x, pos_y +  LN * count, font_id, dpi)
            draw_text(v_text,size, pos_x + column_width, pos_y +  LN * count, font_id, dpi, (1, 1, 1, 1 if v['status'] else 0.5))
            count += 1
    if hasattr(self, 'status'):
        for k, v in self.status.items():
            v_text = "Set" if v['status'] else "Not Set"
            draw_text(v['name'] + ": ",size, pos_x, pos_y +  LN * count, font_id, dpi)
            draw_text(v_text,size, pos_x + column_width, pos_y + LN * count, font_id, dpi, (.25, 1, .25, 1) if v['status'] else (1, .25, .25, 1))
            count += 1
    if hasattr(self, 'empty'):
        for item in self.empty:
            draw_text(item,size, pos_x, pos_y +  LN * count, font_id, dpi)
            count += 1
    draw_text(self.title,size, pos_x, pos_y +  LN * count, font_id, dpi)
    count += 1
def draw_callback_3d(self, context):
    if hasattr(self,"shader3d"):
        self.shader3d.bind()
        self.shader3d.uniform_float("color", (1, 1, 1, 1))
        self.batch3d.draw(self.shader3d)
def def_circle(self, num_segments=12, r=4):
    cx, cy, cz = self.vert
    theta = 2 * math.pi / num_segments
    c = math.cos(theta)
    s = math.sin(theta)
    x = r
    y = 0
    vector_list = []
    for i in range (num_segments+1):
        vector_list.append(Vector((x + cx, y + cy)))
        t = x
        x = c * x - s * y
        y = s * t + c * y
    return vector_list
def draw_callback_circle(self,context):
    width = 1
    num_segments = 14
    rad = 4 if FontGlobal.dpi < 100 else 7
    if GV.before32:
        bgl.glLineWidth(width)
    else:
        gpu.state.line_width_set(width)
    shader = create_2d_shader()
    batch = batch_for_shader(shader,'LINE_STRIP', {"pos": def_circle(self, num_segments, rad-1)})
    shader.bind()
    shader.uniform_float("color", (0, 0, 0, .6))
    batch.draw(shader)
    shader = create_2d_shader()
    batch = batch_for_shader(shader,'LINE_STRIP', {"pos": def_circle(self, num_segments, rad+1)})
    shader.bind()
    shader.uniform_float("color", (0, 0, 0, .6))
    batch.draw(shader)
    shader = create_2d_shader()
    batch = batch_for_shader(shader,'LINE_STRIP', {"pos": def_circle(self, num_segments, rad)})
    shader.bind()
    shader.uniform_float("color", (1, 1, 1, 1))
    batch.draw(shader)
def draw_callback_3d_circle(self, context):
    self.shader3d.bind()
    draw_circle_2d(self.vertices[0], (1, 1, 1, 1), 1, 8)
    self.shader3d.uniform_float("color", (1, 1, 1, 1))
    self.batch3d.draw(self.shader3d)
def draw_callback_line(self, context):
    shader = create_2d_shader()
    if GV.before32:
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glLineWidth(2)
    else:
        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(2.0)
    batch = batch_for_shader(shader, 'LINES', {"pos": self.mouse_path})
    shader.bind()
    shader.uniform_float("color", (1, 1, 1, 1))
    batch.draw(shader)
def create_3d_shader():
    return gpu.shader.from_builtin('UNIFORM_COLOR' if GV.after4 else '3D_UNIFORM_COLOR')
def create_2d_shader():
    return gpu.shader.from_builtin('UNIFORM_COLOR' if GV.after4 else '2D_UNIFORM_COLOR')