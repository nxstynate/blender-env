# INSYDIUM NeXus Add-on for Blender
# Copyright (C) 2026 INSYDIUM LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import sys

import bpy
from bpy.props import StringProperty

from ..handlers import pipeline as pipeline_manager
from ..icons import get_icon
from ..libs import theron
from ..modifiers import MODIFIER_REGISTRY
from ..properties import NEXUS_ENUM_DEFAULTS
from . import bug_report_dialog, cache, particle_console
from .bug_report_dialog import open_bug_report_dialog
from .cache import OPERATOR_CLASSES as _CACHE_OPS
from .cache import open_caching_dialog
from .about_dialog import open_about_dialog
from .curve_presets import (
    curve_preset_classes,
    register_curve_previews,
    unregister_curve_previews,
)
from .generator import (
    NEXUS_OT_generator_new_instance_material,
    NEXUS_OT_generator_resnapshot_freeze,
)
from .gradient_presets import (
    gradient_preset_classes,
    register_gradient_previews,
    unregister_gradient_previews,
)
from .mapping import mapping_classes
from .modifier_presets import modifier_preset_classes
from .particle_console import open_particle_console
from .rate_toggle import NEXUS_OT_toggle_rate_mode
from .splash import NEXUS_OT_splash_reset_handles
from .time_toggle import NEXUS_OT_toggle_time_mode

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "vendor")
try:
    from PyQt6 import QtWidgets  # noqa: E402

    _PYQT6_AVAILABLE = True
except ImportError:
    _PYQT6_AVAILABLE = False

qt_app = None  # The Qt application instance for any spawned Qt dialogs


def _qt_tick():
    """
    Process Qt events when triggered by the Blender timer.
    This is only required on Linux as Blender's own event loop handles and can even interfere with
    Qt on Windows and macOS.
    """
    if qt_app is None:
        return None
    from ..editors.glsl_editor import has_open_editors

    if (
        not has_open_editors()
        and not bug_report_dialog.has_open_window()
        and not particle_console.has_open_window()
        and not cache.has_open_window()
    ):
        return None

    qt_app.processEvents()

    return 0.01


class NEXUS_OT_open_preferences(bpy.types.Operator):
    bl_idname = "nexus.open_preferences"
    bl_label = "Open NeXus Preferences"
    bl_description = "Open Preferences to enter your INSYDIUM license"

    def execute(self, context):
        bpy.ops.screen.userpref_show()
        context.preferences.active_section = "ADDONS"
        pkg = __package__.rsplit(".", 1)[0]
        try:
            bpy.ops.preferences.addon_show(module=pkg)
        except Exception:
            pass
        return {"FINISHED"}


class NEXUS_OT_add_modifier(bpy.types.Operator):
    """Add a NeXus modifier to the scene"""

    bl_idname = "nexus.add_modifier"
    bl_label = "Add NeXus Modifier"
    bl_options = {"REGISTER", "UNDO"}

    modifier_type: StringProperty(
        name="Modifier Type",
        description="Type of modifier to create",
        default="",
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and theron.is_initialized()

    def execute(self, context):
        mod_class = MODIFIER_REGISTRY.get(self.modifier_type)

        if not mod_class:
            self.report({"ERROR"}, f"Unknown modifier type: {self.modifier_type}")
            return {"CANCELLED"}

        obj = mod_class.create_object(context)

        from ..utils.curve import ensure_curve_ownership
        from ..utils.gradient import ensure_gradient_ownership

        ensure_gradient_ownership(obj, mod_class.get_gradient_specs() or None)
        ensure_curve_ownership(obj, mod_class.get_curve_specs() or None)

        from ..handlers.pipeline import ensure_pipeline_for_scene

        ensure_pipeline_for_scene(context.scene)

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        context.view_layer.objects.active = obj

        self.report({"INFO"}, f"Created {mod_class.object_name}")
        return {"FINISHED"}


class NEXUS_OT_reset_modifier(bpy.types.Operator):
    bl_idname = "nexus.reset_modifier"
    bl_label = "Reset Modifier"
    bl_description = "Reset modifier to its default state"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and "nexus_modifier_type" in obj

    def execute(self, context):
        obj = context.object
        mod_type = obj.get("nexus_modifier_type")
        mod_class = MODIFIER_REGISTRY.get(mod_type)

        if not mod_class:
            self.report({"ERROR"}, f"Unknown modifier type: {mod_type}")
            return {"CANCELLED"}

        props = obj.nexus_modifier
        prop_group_rna = props.bl_rna

        from ..libs.modifier_spec import get_modifier_spec

        spec = get_modifier_spec(mod_type)
        if spec is not None:
            modifier_props = spec.build_reset_properties()
        else:
            modifier_props = mod_class.get_modifier_properties()

        for prop_name in modifier_props:
            if prop_name not in prop_group_rna.properties:
                continue

            prop_def = prop_group_rna.properties[prop_name]
            prop_type = prop_def.type

            try:
                if prop_type == "BOOLEAN":
                    if prop_def.is_array:
                        setattr(props, prop_name, prop_def.default_array[:])
                    else:
                        setattr(props, prop_name, prop_def.default)

                elif prop_type == "INT":
                    if prop_def.is_array:
                        setattr(props, prop_name, prop_def.default_array[:])
                    else:
                        setattr(props, prop_name, prop_def.default)

                elif prop_type == "FLOAT":
                    if prop_def.is_array:
                        setattr(props, prop_name, prop_def.default_array[:])
                    else:
                        setattr(props, prop_name, prop_def.default)

                elif prop_type == "STRING":
                    setattr(props, prop_name, prop_def.default)

                elif prop_type == "ENUM":
                    if prop_def.is_enum_flag:
                        setattr(props, prop_name, prop_def.default_flag)
                    elif prop_name in NEXUS_ENUM_DEFAULTS:
                        setattr(props, prop_name, NEXUS_ENUM_DEFAULTS[prop_name])
                    else:
                        default = prop_def.default
                        if isinstance(default, int):
                            try:
                                default = prop_def.enum_items[default].identifier
                            except (IndexError, KeyError):
                                print(
                                    f"NeXus: Could not get enum identifier for "
                                    f"'{prop_name}' at index {default}"
                                )
                                continue
                        setattr(props, prop_name, default)

                elif prop_type == "POINTER":
                    setattr(props, prop_name, None)

                elif prop_type == "COLLECTION":
                    getattr(props, prop_name).clear()

            except Exception as e:
                print(f"NeXus: Could not reset property '{prop_name}': {e}")

        obj.update_tag()
        context.view_layer.depsgraph.update()

        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        self.report({"INFO"}, f"Reset {mod_class.object_name} to defaults")
        return {"FINISHED"}


class NEXUS_OT_open_help(bpy.types.Operator):
    bl_idname = "nexus.open_help"
    bl_label = "Open Help"
    bl_description = "Open the documentation page for this modifier"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and "nexus_modifier_type" in obj

    def execute(self, context):
        obj = context.object
        mod_type = obj.get("nexus_modifier_type")
        mod_class = MODIFIER_REGISTRY.get(mod_type)

        if not mod_class:
            self.report({"ERROR"}, f"Unknown modifier type: {mod_type}")
            return {"CANCELLED"}

        page = mod_class.object_name
        url = f"https://docs.insydium.net/blender/{page}"

        import webbrowser

        webbrowser.open(url)

        return {"FINISHED"}


class NEXUS_OT_hud_drag(bpy.types.Operator):
    bl_idname = "nexus.hud_drag"
    bl_label = "Drag HUD"
    bl_description = "Click and drag to reposition the HUD overlay"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        from ..viewport import hud as hud_module

        bounds = hud_module.hud_bounds
        if bounds is None:
            return {"PASS_THROUGH"}

        mx = event.mouse_region_x
        my = event.mouse_region_y
        x0, y0, x1, y1 = bounds

        if not (x0 <= mx <= x1 and y0 <= my <= y1):
            return {"PASS_THROUGH"}

        hud = context.scene.nexus_pipeline.hud
        self._init_hud_x = hud.hud_pos_x
        self._init_hud_y = hud.hud_pos_y
        self._region_width = context.region.width
        self._region_height = context.region.height

        self._mouse_to_left = mx - x0
        self._mouse_to_bottom = my - y0
        self._hud_w = x1 - x0
        self._hud_h = y1 - y0

        self._pad_x = hud.hud_pos_x * self._region_width - x0
        self._pad_y = hud.hud_pos_y * self._region_height - y0

        context.window.cursor_set("HAND")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        hud = context.scene.nexus_pipeline.hud

        if event.type == "MOUSEMOVE":
            new_bg_x0 = event.mouse_region_x - self._mouse_to_left
            new_bg_y0 = event.mouse_region_y - self._mouse_to_bottom

            rw = self._region_width
            rh = self._region_height
            new_bg_x0 = max(0.0, min(new_bg_x0, rw - self._hud_w))
            new_bg_y0 = max(0.0, min(new_bg_y0, rh - self._hud_h))

            hud.hud_pos_x = (new_bg_x0 + self._pad_x) / rw if rw > 0 else 0.0
            hud.hud_pos_y = (new_bg_y0 + self._pad_y) / rh if rh > 0 else 0.0
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            context.window.cursor_set("DEFAULT")
            return {"FINISHED"}

        if event.type in {"RIGHTMOUSE", "ESC"}:
            hud.hud_pos_x = self._init_hud_x
            hud.hud_pos_y = self._init_hud_y
            context.area.tag_redraw()
            context.window.cursor_set("DEFAULT")
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}


class NEXUS_OT_hud_reset_position(bpy.types.Operator):
    bl_idname = "nexus.hud_reset_position"
    bl_label = "Reset HUD Position"
    bl_description = "Reset the HUD overlay to its default position"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        hud = context.scene.nexus_pipeline.hud
        hud.hud_pos_x = 0.02
        hud.hud_pos_y = 0.05
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
        return {"FINISHED"}


def _get_blender_colors():
    theme = bpy.context.preferences.themes[0]
    ui = theme.user_interface

    def c(arr):
        """Convert Blender's 0–1 float RGBA to a #rrggbb hex string."""
        r, g, b = int(arr[0] * 255), int(arr[1] * 255), int(arr[2] * 255)
        return f"#{r:02x}{g:02x}{b:02x}"

    def lighten(arr, amount=0.08):
        r = min(255, int((arr[0] + amount) * 255))
        g = min(255, int((arr[1] + amount) * 255))
        b = min(255, int((arr[2] + amount) * 255))
        return f"#{r:02x}{g:02x}{b:02x}"

    return {
        "bg": c(ui.wcol_regular.inner),
        "bg_field": c(ui.wcol_text.inner),
        "bg_btn": c(ui.wcol_tool.inner),
        "bg_btn_hover": lighten(ui.wcol_tool.inner),
        "bg_active": c(ui.wcol_regular.inner_sel),
        "accent": c(ui.wcol_menu_item.inner_sel),
        "accent_hover": lighten(ui.wcol_menu_item.inner_sel),
        "text": c(ui.wcol_regular.text),
        "text_label": c(ui.wcol_regular.text),
        "border": c(ui.wcol_regular.outline),
        "window_bg": c(
            theme.view_3d.space.gradients.background_type
            and ui.wcol_regular.inner
            or ui.wcol_regular.inner
        ),
    }


def _get_blender_font_size(base=12):
    prefs = bpy.context.preferences
    scale = prefs.system.ui_scale
    return max(10, round(base * scale))


def _build_qt_stylesheet(colors, pxRatio):
    font_size = int(_get_blender_font_size() / pxRatio)
    return f"""
QWidget {{
    background-color: {colors["bg"]};
    color: {colors["text"]};
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", sans-serif;
    font-size: {font_size}px;
}}
QLineEdit, QTextEdit, QComboBox {{
    background-color: {colors["bg_field"]};
    border: 1px solid {colors["border"]};
    border-radius: 6px;
    padding: 5px 8px;
    color: {colors["text"]};
    selection-background-color: {colors["accent"]};
}}
QLineEdit:focus, QTextEdit:focus {{
    border: 1px solid {colors["accent"]};
}}
QPushButton {{
    background-color: {colors["bg_btn"]};
    border: 1px solid {colors["border"]};
    border-radius: 6px;
    padding: 6px 18px;
    color: {colors["text"]};
}}
QPushButton:hover {{
    background-color: {colors["bg_btn_hover"]};
}}
QPushButton:pressed {{
    background-color: {colors["bg_active"]};
}}
QPushButton:disabled {{
    opacity: 0.4;
}}
QPushButton#submit {{
    background-color: {colors["accent"]};
    color: {colors["text"]};
}}
QPushButton#submit:hover {{
    background-color: {colors["accent_hover"]};
}}
QFrame#separator {{
    background-color: {colors["border"]};
    max-height: 1px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {colors["bg_field"]};
    border: 1px solid {colors["border"]};
    border-radius: 6px;
    selection-background-color: {colors["accent"]};
    padding: 2px;
}}
QLabel#header, QLabel#footer {{
    font-size: {int(font_size * 0.75)}px;
}}
"""


def _ensure_qt_app():
    if not _PYQT6_AVAILABLE:
        return
    global qt_app
    if not qt_app:
        qt_app = QtWidgets.QApplication([])

    pxRatio = qt_app.primaryScreen().devicePixelRatio()

    # Get some Blender theme colours to stay cohesive
    colors = _get_blender_colors()
    qt_app.setStyleSheet(_build_qt_stylesheet(colors, pxRatio))


def _register_bpy_qt_tick():
    """
    Register's a Blender timer tick to trigger Qt event loop, but only on linux. On Windows and
    macOS this is handled by Blender's native event loop. Triggering the Qt loop can interfere with
    this and cause trouble.
    """

    if sys.platform == "linux":
        if not bpy.app.timers.is_registered(_qt_tick):
            bpy.app.timers.register(_qt_tick, first_interval=0.01)


class NEXUS_OT_report_bug(bpy.types.Operator):
    bl_idname = "nexus.report_bug"
    bl_label = "Report a Bug"
    bl_description = "Submit a bug report to INSYDIUM"

    def execute(self, context):
        if not _PYQT6_AVAILABLE:
            self.report({"ERROR"}, "PyQt6 is not available")
            return {"CANCELLED"}

        _ensure_qt_app()
        open_bug_report_dialog()
        _register_bpy_qt_tick()

        return {"FINISHED"}


class NEXUS_OT_open_console(bpy.types.Operator):
    bl_idname = "nexus.open_console"
    bl_label = "Open Particle Console"
    bl_description = "Open the particle data console"

    def execute(self, context):
        if not _PYQT6_AVAILABLE:
            self.report({"ERROR"}, "PyQt6 is not available")
            return {"CANCELLED"}

        _ensure_qt_app()
        open_particle_console()

        # Fetch particle data for display
        pipeline = pipeline_manager.get_pipeline(context.scene)
        if pipeline is None:
            return {"CANCELLED"}
        particle_console.update_particle_data(pipeline)

        _register_bpy_qt_tick()

        return {"FINISHED"}


class NEXUS_OT_open_glsl_editor(bpy.types.Operator):
    bl_idname = "nexus.open_glsl_editor"
    bl_label = "Edit GLSL Script"
    bl_description = "Open the GLSL code editor for this script node"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or "nexus_modifier_type" not in obj:
            return False
        props = obj.nexus_modifier
        items = props.question_items
        idx = props.question_items_index
        if not items or idx < 0 or idx >= len(items):
            return False
        return items[idx].item_type == "SCRIPT"

    def execute(self, context):

        if not _PYQT6_AVAILABLE:
            self.report({"ERROR"}, "PyQt6 is not available")
            return {"CANCELLED"}

        _ensure_qt_app()

        from ..editors.glsl_editor import open_glsl_editor
        from ..editors.glsl_editor.theme import create_theme_from_blender

        colors = _get_blender_colors()

        obj = context.object
        props = obj.nexus_modifier
        item = props.question_items[props.question_items_index]
        item_index = props.question_items_index

        def _collect_user_vars(object_name):
            try:
                target_obj = bpy.data.objects[object_name]
            except KeyError:
                return ()
            items = target_obj.nexus_modifier.question_items

            def _fmt(it):
                vt = it.var_type
                if vt == "FLOAT":
                    return str(it.var_type_flt_val)
                if vt == "INT":
                    return str(it.var_type_int_val)
                if vt == "VEC":
                    v = it.var_type_vec_val
                    return f"({v[0]:.3g}, {v[1]:.3g}, {v[2]:.3g})"
                return ""

            return tuple(
                (it.var_name, it.var_type, it.var_type_write, it.var_type_particle, _fmt(it))
                for it in items
                if it.item_type == "VAR" and it.var_name.strip()
            )

        user_vars = _collect_user_vars(obj.name)

        def refresh_vars_callback(object_name):
            return _collect_user_vars(object_name)

        theme = create_theme_from_blender(colors)

        def save_callback(object_name, idx, source_text):
            try:
                target_obj = bpy.data.objects[object_name]
            except KeyError:
                return False
            target_items = target_obj.nexus_modifier.question_items
            if idx < 0 or idx >= len(target_items):
                return False
            if target_items[idx].item_type != "SCRIPT":
                return False
            target_items[idx].script_source = source_text
            target_obj.update_tag()
            return True

        open_glsl_editor(
            obj.name,
            item_index,
            item.name or "Script",
            item.script_source,
            theme,
            save_callback,
            user_vars=user_vars,
            refresh_vars_callback=refresh_vars_callback,
        )

        _register_bpy_qt_tick()

        return {"FINISHED"}


class NEXUS_OT_cache_build(bpy.types.Operator):
    bl_idname = "nexus.cache_build"
    bl_label = "Build Cache"
    bl_description = "Build the particle cache for all included objects"

    def execute(self, context):
        if not _PYQT6_AVAILABLE:
            self.report({"ERROR"}, "PyQt6 is not available")
            return {"CANCELLED"}

        pipeline = pipeline_manager.get_pipeline(context.scene)
        cache_handle = cache._cache_handle(context)
        if pipeline is None or cache_handle is None:
            return {"CANCELLED"}

        pipeline_manager.sync_all_objects(context.scene)

        _ensure_qt_app()
        directory = context.object.nexus_modifier.ID_NX_CACHE_DIRECTORY
        if not cache.confirm_overwrite_cache(directory):
            return {"CANCELLED"}

        if not theron.build_full_cache_async(pipeline, cache_handle):
            return {"CANCELLED"}

        total = context.scene.frame_end - context.scene.frame_start + 1
        open_caching_dialog(pipeline, cache_handle, total)
        _register_bpy_qt_tick()

        return {"FINISHED"}


class NEXUS_OT_about_dialog(bpy.types.Operator):
    bl_idname = "nexus.about_dialog"
    bl_label = "Open NeXus About"
    bl_description = "Open the NeXus splash screen"

    def execute(self, context):
        if not _PYQT6_AVAILABLE:
            self.report({"ERROR"}, "PyQt6 is not available")
            return {"CANCELLED"}

        _ensure_qt_app()
        open_about_dialog()
        _register_bpy_qt_tick()

        return {"FINISHED"}


def menu_func_report_bug(self, context):

    self.layout.separator()

    insydium_icon = get_icon("insydium")
    self.layout.label(text="INSYDIUM", icon_value=insydium_icon if insydium_icon else 0)

    self.layout.operator(
        NEXUS_OT_report_bug.bl_idname,
        text="Report a Bug...",
    )

    self.layout.operator(
        NEXUS_OT_about_dialog.bl_idname,
        text="About NeXus...",
    )


classes = [
    NEXUS_OT_open_preferences,
    NEXUS_OT_add_modifier,
    NEXUS_OT_reset_modifier,
    NEXUS_OT_open_help,
    NEXUS_OT_splash_reset_handles,
    NEXUS_OT_generator_resnapshot_freeze,
    NEXUS_OT_generator_new_instance_material,
    NEXUS_OT_toggle_time_mode,
    NEXUS_OT_toggle_rate_mode,
    NEXUS_OT_hud_drag,
    NEXUS_OT_hud_reset_position,
    NEXUS_OT_report_bug,
    NEXUS_OT_open_glsl_editor,
    NEXUS_OT_open_console,
    NEXUS_OT_cache_build,
    NEXUS_OT_about_dialog,
    *gradient_preset_classes,
    *curve_preset_classes,
    *modifier_preset_classes,
    *mapping_classes,
    *_CACHE_OPS,
]

_keymaps = []


def register():
    from bpy.utils import register_class

    for cls in classes:
        try:
            register_class(cls)
        except ValueError:
            pass

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
        kmi = km.keymap_items.new("nexus.hud_drag", "LEFTMOUSE", "PRESS")
        _keymaps.append((km, kmi))

    bpy.types.TOPBAR_MT_help.append(menu_func_report_bug)

    register_gradient_previews(__package__.rsplit(".", 1)[0])
    register_curve_previews(__package__.rsplit(".", 1)[0])

    from ..utils.modifier_presets import init_user_presets as _init_modifier_presets

    _init_modifier_presets(__package__.rsplit(".", 1)[0])

    bpy.types.WindowManager.nexus_preset_move_id = StringProperty(default="")
    bpy.types.WindowManager.nexus_preset_move_modtype = StringProperty(default="")


def unregister():

    if _PYQT6_AVAILABLE:
        from ..editors.glsl_editor import close_all_glsl_editors

        close_all_glsl_editors()

    unregister_curve_previews()
    unregister_gradient_previews()

    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()

    bpy.types.TOPBAR_MT_help.remove(menu_func_report_bug)

    if hasattr(bpy.types.WindowManager, "nexus_preset_move_id"):
        del bpy.types.WindowManager.nexus_preset_move_id
    if hasattr(bpy.types.WindowManager, "nexus_preset_move_modtype"):
        del bpy.types.WindowManager.nexus_preset_move_modtype

    from bpy.utils import unregister_class

    for cls in reversed(classes):
        try:
            unregister_class(cls)
        except RuntimeError:
            pass

    # Cleanup Qt
    if _PYQT6_AVAILABLE:
        global qt_app
        if qt_app:
            qt_app.quit()
            qt_app = None
