import bpy
import bpy.utils.previews
import os
import rna_keymap_ui
import addon_utils
from .lib import *
from ast import literal_eval as make_tuple
icons_dict = None
addon_keymaps = []
maps = [
    'object.cablerator',
    'object.cableratordraw',
    'cbl.massive_cables',
    'object.cablerator_create_cable_from_edge',
    'object.cablerator_create_cable_from_selected',
    'object.cablerator_edit_cable',
    'object.cableratorconnect',
    'object.cablerator_connector',
    'object.cablerator_segment',
    'object.cablerator_geocable',
    'object.cableratorsplit',
    'object.cableratorsplitrecable',
    'cbl.simulate_cable_dialog',
    'cbl.insulate',
    'cbl.rope',
    ]
def check_for_updates():
    addon_date = tuple(bpy.context.preferences.addons[__package__].preferences.update_date)
    init_path = os.path.join(get_addon_directory(),'__init__.py')
    with open(init_path, 'r') as f:
        file_content = f.read()
    version_pattern = r'"version":\s(.*),'
    match = re.search(version_pattern, file_content)
    if match:
        addon_version = make_tuple(match.group(1))
        pass
    else:
        addon_version = (-1, -1, -1)
        pass
    cur_date = tuple(datetime.today().timetuple()[:3])
    if cur_date > addon_date:
        bpy.context.preferences.addons[__package__].preferences.should_update = check_for_update(addon_version)
        bpy.context.preferences.addons[__package__].preferences.update_date = cur_date
    else:
        pass
def check_for_update(cur_version):
    url = 'https://bitbucket.org/kritskiy/docs/raw/HEAD/cablerator/version.txt'
    try:
        response = requests.get(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"}, timeout=3)
        data_json = response.json()
        response_version = (data_json['major'], data_json['second'], data_json['minor'])
        if response_version > cur_version:
            return f"Cablerator {'.'.join(str(i) for i in response_version)} update is available!"
        else:
            return ''
    except Exception as ex:
        return 'network_error'
def message_exist(self, context):
    self.layout.label(text="Assets File doesn't exist in this location")
def message_type(self, context):
    self.layout.label(text="Wrong file type selected, expected a '.blend' file")
def check_file_name(self, context):
    f = context.preferences.addons[__package__].preferences.ext_assets_filepath
    if f == '':
        context.preferences.addons[__package__].preferences.ext_assets_filepath = get_path_to_blend()
    elif not file_exists(f):
        context.window_manager.popup_menu(message_exist, title="Error", icon='ERROR')
    elif not f.endswith('.blend'):
        context.window_manager.popup_menu(message_type, title="Error", icon='ERROR')
class createCablePrefs(bpy.types.AddonPreferences):
    bl_idname = __package__
    tabs: bpy.props.EnumProperty(name="Preferences", items=[('PREFS','Preferences',''),('KEYS','Hotkeys','')], default="PREFS")
    leave_rmb: bpy.props.BoolProperty(name="Leave Right Mouse Button for Blender and don't use it in modals", default=False)
    use_warp: bpy.props.BoolProperty(name="Use Mouse Warp in modals", default=True)
    warp_delta: bpy.props.IntProperty(name="Warp delta (in Pixels)", min=10, default=80)
    font_size: bpy.props.IntProperty(name="Font Size", min=8, default=13)
    width: bpy.props.FloatProperty(name="Default Cable Width", min=0, default=0.1)
    res: bpy.props.IntProperty(name="Curve Resolution", min=1, default=20)
    bevel_res: bpy.props.IntProperty(name="Bevel Resolution", min=0, default=6)
    subdivisions: bpy.props.IntProperty(name="Subdivide Cable in the end", min=0, default=1)
    twist: bpy.props.EnumProperty(name="Twist Mode", items=[('0','Z-Up',''),('1','Minimum',''),('2','Tangent','')], default='0')
    show_tilt: bpy.props.BoolProperty(name="Show Points Tilt in Modal", default=False)
    show_offset: bpy.props.BoolProperty(name="Show Points Offset in Modal", default=False)
    show_length: bpy.props.BoolProperty(name="Show Cable Length in Modal", default=False)
    show_res: bpy.props.BoolProperty(name="Show Resolution in Modal", default=False)
    show_bevel_res: bpy.props.BoolProperty(name="Show Bevel Resolution in Modal", default=False)
    show_subdivisions: bpy.props.BoolProperty(name="Show Subdivisions in Modal", default=True)
    fill_caps: bpy.props.BoolProperty(name="Fill Caps by Default", default=False)
    show_fill_caps: bpy.props.BoolProperty(name="Show Fill Caps in Modal", default=True)
    show_twist: bpy.props.BoolProperty(name="Show Twist Mode in Modal", default=True)
    show_wire: bpy.props.BoolProperty(name="Show Toggle Wire in Modal", default=True)
    parent_connectors: bpy.props.BoolProperty(name="Parent Connectors, Segments and Hooks to Curves", default=True)
    empties: bpy.props.EnumProperty(name="Hook Display Type", items=[('PLAIN_AXES','Plain Axes',''),
                                                                    ('ARROWS','Arrows',''),
                                                                    ('SINGLE_ARROW','Single Arrow',''),
                                                                    ('CIRCLE','Circle',''),
                                                                    ('CUBE','Cube',''),
                                                                    ('SPHERE','Sphere',''),
                                                                    ('CONE','Cone','')], default='CUBE')
    empty_size: bpy.props.FloatProperty(name="Hook Object Size", min=0.01, default=0.5)
    circle_points: bpy.props.IntProperty(name="Default Circle Points Number", min=3, default=12)
    circle_rad: bpy.props.FloatProperty(name="Circle Radius", min=0.001, default=0.1)
    show_grab_profile: bpy.props.BoolProperty(name="Show Grab Profile in Modal", default=True)
    ext_assets_filepath: bpy.props.StringProperty(
            name="Grab Profiles From",
            subtype='FILE_PATH',
            default=get_path_to_blend(),
            update=check_file_name
        )
    should_update: bpy.props.StringProperty(
            name="Should Update",
            default=""
        )
    update_date: bpy.props.IntVectorProperty(name="Update Check Date", default=(-1, -1, -1))
    def draw(self, context):
        layout = self.layout
        if self.should_update != '':
            box = layout.box()
            if self.should_update == "network_error":
                box.label(text="Can't connect to the internet and check for version", icon='ERROR')
            else:
                box.label(text=self.should_update, icon='ERROR')
        if GV.is42:
            if not bpy.app.online_access:
                box = layout.box()
                box.label(text="No network access granted, can't check for an update", icon='ERROR')
        r = layout.row()
        r.prop(self, "tabs", expand=True)
        column_main = layout.column()
        if self.tabs == "PREFS":
            box = column_main.box()
            box.label(text="General preferences:")
            box.prop(self, 'leave_rmb')
            row = box.split(factor=0.5)
            row.separator()
            row.prop(self, 'font_size')
            box = column_main.box()
            box.label(text="Modal-specific preferences:")
            row = box.split(factor=0.5)
            row.separator()
            row.prop(self, 'width')
            row = box.row()
            row.prop(self, "show_res")
            row.prop(self, 'res')
            row = box.row()
            row.prop(self, "show_bevel_res")
            row.prop(self, 'bevel_res')
            row = box.row()
            row.prop(self, "show_subdivisions")
            row.prop(self, 'subdivisions')
            if bpy.app.version >= (2, 91, 0):
                row = box.row()
                row.prop(self, 'show_fill_caps')
                row.prop(self, "fill_caps")
            box.prop(self, "show_wire")
            box.prop(self, 'show_tilt')
            box.prop(self, 'show_offset')
            box.prop(self, 'show_length')
            box.prop(self, 'show_grab_profile')
            box.prop(self, 'ext_assets_filepath')
            box.prop(self, 'show_twist')
            column = box.column(align=True)
            r = column.split(factor=0.25)
            r.label(text="Default Twist Mode:")
            row3 = r.row(align=True)
            row3.prop(self, 'twist', expand=True)
            box.prop(self, 'parent_connectors')
            box.separator()
            row = box.row()
            r = row.split(factor=0.33)
            r.prop(self, "empty_size")
            r.prop(self, 'empties')
            box.separator()
            column = box.column(align=True)
            r = column.split(factor=0.25)
            r.label(text="Add Circle options:")
            row = r.row(align=True)
            r = row.split(factor=0.5)
            r.prop(self, "circle_points")
            r.prop(self, 'circle_rad')
        elif self.tabs == "KEYS":
            column = column_main.column()
            wm = bpy.context.window_manager
            kc = wm.keyconfigs.user
            km = kc.keymaps['3D View']
            column.label(text="Cablerator Menu:")
            kmi = get_hotkey_entry_item(km, 'wm.call_menu', 'VIEW3D_MT_cablerator', 'name')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            column.label(text=" Main functions:")
            for keymap in maps:
                kmi = get_hotkey_entry_item(km, keymap, 'none', 'none')
                if kmi:
                    column.context_pointer_set("keymap", km)
                    rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
                else:
                    column.label(text="No hotkey entry found")
            column.label(text="Hooks:")
            km = kc.keymaps['Curve']
            kmi = get_hotkey_entry_item(km, 'object.cablerator_helper_add_hook', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            km = kc.keymaps['Curve']
            kmi = get_hotkey_entry_item(km, 'cbl.one_hook', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            km = kc.keymaps['3D View']
            kmi = get_hotkey_entry_item(km, 'object.cablerator_helper_apply_hook', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            kmi = get_hotkey_entry_item(km, 'object.cablerator_helper_remove_hook', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            column.label(text="Helpers:")
            km = kc.keymaps['Curve']
            kmi = get_hotkey_entry_item(km, 'object.cablerator_helper_add_point', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            kmi = get_hotkey_entry_item(km, 'cbl.cut_cable', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            km = kc.keymaps['3D View']
            kmi = get_hotkey_entry_item(km, 'cbl.drop_cable', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            kmi = get_hotkey_entry_item(km, 'cbl.convert_between', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            km = kc.keymaps['Curve']
            kmi = get_hotkey_entry_item(km, 'object.cablerator_helper_switch_handle', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            kmi = get_hotkey_entry_item(km, 'object.cablerator_helper_unrotate', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            km = kc.keymaps['3D View']
            kmi = get_hotkey_entry_item(km, 'object.cablerator_helper_find_profile', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            kmi = get_hotkey_entry_item(km, 'object.cablerator_create_profile_bundle', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            kmi = get_hotkey_entry_item(km, 'object.cablerator_helper_single_vert', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            kmi = get_hotkey_entry_item(km, 'object.cablerator_helper_add_circle', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
            kmi = get_hotkey_entry_item(km, 'cbl.apply_mirror', 'none', 'none')
            if kmi:
                column.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, column, 0)
            else:
                column.label(text="No hotkey entry found")
        column_main = layout.column()
        column_main.separator()
        box = column_main.box()
        box.scale_y = 1
        box.label(text="Explore more tools for Blender and Photoshop:")
        row = box.row()
        row.operator("wm.url_open",text="Gumroad").url = "https://gumroad.com/kritskiy"
        row.operator("wm.url_open",text="BlenderMarket").url = "https://blendermarket.com/creators/sergey-kritskiy"
        row.operator("wm.url_open",text="Cubebrush").url = "https://cubebrush.co/kritskiy"
        row.operator("wm.url_open",text="Artstation").url = "https://www.artstation.com/sergeykritskiy"
        box.label(text="Follow me for updates:")
        row = box.row()
        row.operator("wm.url_open",text="Discord").url = "https://discord.gg/RTJydTg"
        row.operator("wm.url_open",text="Youtube").url = "https://www.youtube.com/user/tyrtyrtyr/"
        row.operator("wm.url_open",text="Twitter").url = "https://twitter.com/ebanchiki"
class VIEW3D_MT_cablerator_hooks(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_cablerator_hooks"
    bl_label = "Hooks"
    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'
        layout.operator("object.cablerator_helper_add_hook", text="Add Aligned Hooks")
        layout.operator("cbl.one_hook", text="Add a Single Hook")
        layout.operator("object.cablerator_helper_apply_hook", text="Apply Hooks to Selected")
        layout.operator("object.cablerator_helper_remove_hook", text="Remove Hooks from Selected")
class VIEW3D_MT_cablerator_helper(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_cablerator_helper"
    bl_label = "Helpers"
    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'
        layout.operator("object.cablerator_helper_add_point", text="Add/Remove a Bezier Point at Mouse Cursor...", icon="CURVE_BEZCURVE")
        layout.operator("cbl.cut_cable", text="Cut Bezier Curve", icon_value=icons_dict["cut_icon"].icon_id)
        layout.separator()
        layout.operator("object.cablerator_helper_unrotate", text="Reset Points Orientation")
        layout.operator("object.cablerator_helper_switch_handle", text="Switch Points Handles Auto <-> Aligned")
        layout.separator()
        layout.operator("object.cablerator_helper_add_circle", text="Add Polycurve Circle at 3D Cursor...", icon="MESH_CIRCLE")
        layout.operator("object.cablerator_create_profile_bundle", text="Create a Multi-Profile...", icon_value=icons_dict["multiprofile_icon"].icon_id)
        layout.operator("object.cablerator_helper_find_profile", text="Find Selected Curves Profiles", icon="VIEWZOOM")
        layout.separator()
        layout.operator("object.cablerator_helper_single_vert", text="Add Single Vert at 3D Cursor", icon="DOT")
        layout.operator("cbl.drop_cable", text="Drop the Cable", icon="CON_FLOOR")
        layout.operator("cbl.apply_mirror", text="Apply Symmetry", icon="MOD_MIRROR")
        layout.operator("cbl.convert_between", text="Convert between Mesh <-> Curve", icon="MESH_CUBE")
class VIEW3D_MT_cablerator_geohelper(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_cablerator_geohelper"
    bl_label = "GeoNodes Helpers"
    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'
        layout.operator("cbl.convert_curve_to_gn", text="Convert Curve to Geo Nodes Object", icon="GEOMETRY_NODES")
        layout.operator("cbl.convert_to_multicable", text="Convert Curve to Geo Nodes Multi-Cable", icon="GEOMETRY_NODES")
        layout.separator()
        layout.operator("cbl.convert_gn_to_curves", text="Convert Geo Nodes to Cable", icon="GEOMETRY_NODES")
class VIEW3D_MT_cablerator(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_cablerator"
    bl_label = "Cablerator"
    def draw(self, context):
        global icons_dict
        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'
        column_ops = layout
        myop = column_ops.operator("object.cablerator", text="Create Cable", icon_value=icons_dict["create_cable_icon"].icon_id)
        myop.use_bevel=False
        myop.use_method=-1
        myop.use_length=-1
        column_ops.operator("object.cableratordraw", text="Draw Cable", icon_value=icons_dict["draw_cable_icon"].icon_id)
        column_ops.operator("cbl.massive_cables", text="Create a Mass from Selected Faces", icon_value=icons_dict["create_massive_icon"].icon_id)
        column_ops.operator("object.cablerator_create_cable_from_edge", text="Create from Edges", icon_value=icons_dict["create_from_edges_icon"].icon_id)
        column_ops.operator("object.cablerator_create_cable_from_selected", text="Create from Selected Objects", icon_value=icons_dict["create_from_objs_icon"].icon_id)
        column_ops.separator()
        column_ops.operator("object.cablerator_edit_cable", text="Edit Cable", icon_value=icons_dict["edit_cable_icon"].icon_id)
        column_ops.operator("object.cableratorconnect", text="Merge End Points", icon_value=icons_dict["merge_points_icon"].icon_id)
        column_ops.separator()
        column_ops.operator("object.cablerator_connector", text="Add Connectors", icon_value=icons_dict["add_connectors_icon"].icon_id)
        column_ops.operator("object.cablerator_segment", text="Add or Edit Segment", icon_value=icons_dict["add_segment_icon"].icon_id).duplicate = False
        column_ops.operator("object.cablerator_geocable", text="Convert Curve to Mesh Cable", icon_value=icons_dict["add_mesh_icon"].icon_id)
        column_ops.separator()
        column_ops.operator("object.cableratorsplit", text="Split Cable by Profiles", icon_value=icons_dict["split_cable_icon"].icon_id)
        column_ops.operator("object.cableratorsplitrecable", text="Rebuild Split Cable", icon_value=icons_dict["split_rebuild_icon"].icon_id)
        column_ops.separator()
        column_ops.operator("cbl.simulate_cable_dialog", text="Simulate Cable...", icon_value=icons_dict["simulate_icon"].icon_id)
        column_ops.separator()
        column_ops.operator("cbl.insulate", text="Insulate", icon_value=icons_dict["insulate_icon"].icon_id)
        column_ops.operator("cbl.rope", text="Rope", icon_value=icons_dict["rope_icon"].icon_id)
        column_ops.separator()
        column_ops.menu(VIEW3D_MT_cablerator_hooks.bl_idname, icon="HOOK")
        column_ops.menu(VIEW3D_MT_cablerator_helper.bl_idname, icon_value=icons_dict["misc_icon"].icon_id)
        column_ops.menu(VIEW3D_MT_cablerator_geohelper.bl_idname, icon="GEOMETRY_NODES")
def cablerator_menu(self, context):
    global icons_dict
    self.layout.menu("VIEW3D_MT_cablerator", icon_value=icons_dict["create_cable_icon"].icon_id)
def register():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        if "3D View" not in kc.keymaps:
            km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
        else:
            km = kc.keymaps["3D View"]
        kmi = km.keymap_items.new("wm.call_menu", "C", "PRESS", alt=True, shift=True)
        kmi.properties.name ="VIEW3D_MT_cablerator"
        kmi.active = True
        for keymap in maps:
            kmi = km.keymap_items.new(keymap, "NONE", "PRESS")
            kmi.active = False
        kmi = km.keymap_items.new("object.cablerator_helper_find_profile", "NONE", "PRESS")
        kmi.active = False
        kmi = km.keymap_items.new("object.cablerator_create_profile_bundle", "NONE", "PRESS")
        kmi.active = False
        kmi = km.keymap_items.new("object.cablerator_helper_add_circle", "NONE", "PRESS")
        kmi.active = False
        kmi = km.keymap_items.new("object.cablerator_helper_single_vert", "NONE", "PRESS")
        kmi.active = False
        kmi = km.keymap_items.new("object.cablerator_helper_apply_hook", "NONE", "PRESS")
        kmi.active = False
        kmi = km.keymap_items.new("object.cablerator_helper_remove_hook", "NONE", "PRESS")
        kmi.active = False
        kmi = km.keymap_items.new("cbl.drop_cable", "NONE", "PRESS")
        kmi.active = False
        kmi = km.keymap_items.new("cbl.apply_mirror", "NONE", "PRESS")
        kmi.active = False
        kmi = km.keymap_items.new("cbl.convert_between", "NONE", "PRESS")
        kmi.active = False
        addon_keymaps.append((km, kmi))
        if "Curve" not in kc.keymaps:
            km = kc.keymaps.new(name="Curve", space_type="EMPTY")
        else:
            km = kc.keymaps["Curve"]
        kmi = km.keymap_items.new("object.cablerator_helper_add_hook", "NONE", "PRESS")
        kmi.active = False
        kmi = km.keymap_items.new("cbl.one_hook", "NONE", "PRESS")
        kmi.active = False
        kmi = km.keymap_items.new("object.cablerator_helper_switch_handle", "V", "PRESS", alt=True)
        kmi.active = False
        kmi = km.keymap_items.new("object.cablerator_helper_unrotate", "NONE", "PRESS")
        kmi.active = False
        kmi = km.keymap_items.new("object.cablerator_helper_add_point", "NONE", "PRESS")
        kmi.active = False
        kmi = km.keymap_items.new("cbl.cut_cable", "NONE", "PRESS")
        kmi.active = False
        addon_keymaps.append((km, kmi))
    global icons_dict
    icons_dict = bpy.utils.previews.new()
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    icons_dict.load("create_cable_icon", os.path.join(icons_dir, "create_cable.png"), 'IMAGE')
    icons_dict.load("add_connectors_icon", os.path.join(icons_dir, "add_connectors.png"), 'IMAGE')
    icons_dict.load("add_mesh_icon", os.path.join(icons_dir, "add_mesh.png"), 'IMAGE')
    icons_dict.load("add_segment_icon", os.path.join(icons_dir, "add_segment.png"), 'IMAGE')
    icons_dict.load("create_from_edges_icon", os.path.join(icons_dir, "create_from_edges.png"), 'IMAGE')
    icons_dict.load("create_from_objs_icon", os.path.join(icons_dir, "create_from_objs.png"), 'IMAGE')
    icons_dict.load("create_massive_icon", os.path.join(icons_dir, "create_massive.png"), 'IMAGE')
    icons_dict.load("cut_icon", os.path.join(icons_dir, "cut.png"), 'IMAGE')
    icons_dict.load("draw_cable_icon", os.path.join(icons_dir, "draw_cable.png"), 'IMAGE')
    icons_dict.load("edit_cable_icon", os.path.join(icons_dir, "edit_cable.png"), 'IMAGE')
    icons_dict.load("insulate_icon", os.path.join(icons_dir, "insulate.png"), 'IMAGE')
    icons_dict.load("rope_icon", os.path.join(icons_dir, "rope.png"), 'IMAGE')
    icons_dict.load("merge_points_icon", os.path.join(icons_dir, "merge_points.png"), 'IMAGE')
    icons_dict.load("misc_icon", os.path.join(icons_dir, "misc.png"), 'IMAGE')
    icons_dict.load("multiprofile_icon", os.path.join(icons_dir, "multiprofile.png"), 'IMAGE')
    icons_dict.load("simulate_icon", os.path.join(icons_dir, "simulate.png"), 'IMAGE')
    icons_dict.load("split_cable_icon", os.path.join(icons_dir, "split_cable.png"), 'IMAGE')
    icons_dict.load("split_rebuild_icon", os.path.join(icons_dir, "split_rebuild.png"), 'IMAGE')
    bpy.utils.register_class(createCablePrefs)
    bpy.utils.register_class(VIEW3D_MT_cablerator)
    bpy.utils.register_class(VIEW3D_MT_cablerator_helper)
    bpy.utils.register_class(VIEW3D_MT_cablerator_geohelper)
    bpy.utils.register_class(VIEW3D_MT_cablerator_hooks)
    bpy.types.VIEW3D_MT_add.append(cablerator_menu)
    bpy.types.VIEW3D_MT_curve_add.append(cablerator_menu)
    check_for_updates()
def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    global icons_dict
    bpy.utils.previews.remove(icons_dict)
    bpy.utils.unregister_class(createCablePrefs)
    bpy.utils.unregister_class(VIEW3D_MT_cablerator)
    bpy.utils.unregister_class(VIEW3D_MT_cablerator_helper)
    bpy.utils.unregister_class(VIEW3D_MT_cablerator_geohelper)
    bpy.utils.unregister_class(VIEW3D_MT_cablerator_hooks)
    bpy.types.VIEW3D_MT_add.remove(cablerator_menu)
    bpy.types.VIEW3D_MT_curve_add.remove(cablerator_menu)