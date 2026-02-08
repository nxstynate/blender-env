# #### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import platform

from bpy.types import Panel
import bpy

from .modules.poliigon_core.assets import AssetType
from .modules.poliigon_core.api_remote_control_params import (
    KEY_TAB_IMPORTED,
    KEY_TAB_MY_ASSETS,
    KEY_TAB_ONLINE)
from .modules.poliigon_core.multilingual import _t
from .dialogs.dlg_account import build_user
from .dialogs.dlg_add_node_groups import (
    append_poliigon_groups_node_add,
    POLIIGON_MT_add_node_groups)
from .dialogs.dlg_area_categories import build_categories
from .dialogs.dlg_area_notifications import notification_banner
from .dialogs.dlg_area_tabs import build_areas
from .dialogs.dlg_assets import build_assets
from .dialogs.dlg_init_library import build_library
from .dialogs.dlg_login import build_login
from .dialogs.utils_dlg import (
    check_dpi,
    get_ui_scale)
from .toolbox import get_context
from .toolbox_settings import save_settings
from . import reporting


def _determine_draw_width() -> None:
    for vA in bpy.context.screen.areas:
        if vA.type != "VIEW_3D":
            continue

        for vR in vA.regions:
            if vR.type != "UI":
                continue

            panel_padding = 15 * get_ui_scale(cTB)  # Left padding.
            sidebar_width = 15 * get_ui_scale(cTB)  # Tabname width.

            # Mac blender 3.x up seems to be reported wider than
            # reality; it does not seem affected by UI scale or HDPI.
            ex_pad = "mac" in platform.platform()
            ex_pad = ex_pad or "darwin" in platform.platform()
            ex_pad = ex_pad and bpy.app.version >= (3, 0)
            if ex_pad:
                sidebar_width += 17 * get_ui_scale(cTB)
            w_draw = vR.width - panel_padding - sidebar_width
            if w_draw < 1:
                # To avoid div by zero errors below
                w_draw = 1
            if w_draw != cTB.width_draw_ui:
                cTB.width_draw_ui = w_draw
                check_dpi(cTB)


def _imported_tab_check_assets(area: str, props_wm) -> None:
    if area != KEY_TAB_IMPORTED:
        return

    category_list = cTB.settings["category"][area]
    query_key = cTB.get_accumulated_query_cache_key(
        tab=KEY_TAB_IMPORTED,
        search=props_wm.search_imported,
        category_list=category_list)

    if query_key not in cTB._asset_index.cached_queries:
        return
    if len(cTB._asset_index.cached_queries[query_key]) > 0:
        return
    cTB.f_GetSceneAssets()


def _get_assets_upon_changed_search(area: str) -> None:
    if cTB.vSearch[area] == cTB.vLastSearch[area]:
        return

    cTB.vPage[area] = 0
    cTB.vPages[area] = 0

    cTB.f_GetAssets()

    cTB.vLastSearch[area] = cTB.vSearch[area]


def _build_search(cTB, props_wm, area: str) -> None:
    row = cTB.vBase.row()
    row_aligned = row.row(align=True)

    # NEED SEPARATE PROPS FOR SPECIFIC DESCRIPTIONS
    row_aligned.prop(
        props_wm, f"search_{area}", icon="VIEWZOOM")

    if area == KEY_TAB_ONLINE and len(props_wm.search_poliigon):
        search_show_x = 1
    elif area == KEY_TAB_MY_ASSETS and len(props_wm.search_my_assets):
        search_show_x = 1
    elif area == KEY_TAB_IMPORTED and len(props_wm.search_imported):
        search_show_x = 1
    else:
        search_show_x = 0

    if search_show_x:
        op = row_aligned.operator(
            "poliigon.poliigon_setting",
            text="",
            icon="X",
        )
        op.tooltip = _t("Clear Search")
        op.mode = f"clear_search_{cTB.settings['area']}"


def build_ui(ui, context):
    """Primary draw function used to build the main panel."""

    cTB.logger_ui.debug("build_ui")

    # Flag in request's meta data for Mixpanel
    cTB._api._mp_relevant = True

    cTB.vUI = ui
    cTB.vContext = context

    area = cTB.settings["area"]
    props_wm = bpy.context.window_manager.poliigon_props
    cTB.vSearch[KEY_TAB_ONLINE] = props_wm.search_poliigon
    cTB.vSearch[KEY_TAB_MY_ASSETS] = props_wm.search_my_assets
    cTB.vSearch[KEY_TAB_IMPORTED] = props_wm.search_imported

    _imported_tab_check_assets(area, props_wm)

    _determine_draw_width()

    _get_assets_upon_changed_search(area)

    layout = ui.layout
    layout.alignment = "CENTER"

    row_base = layout.row()

    cTB.vBase = row_base.column()

    cTB.interval_check_update()

    if cTB.f_add_survey_notification_once(cTB):
        save_settings(cTB)

    notification_banner(cTB, cTB.vBase)

    if not cTB.is_logged_in() or cTB.user is None:
        build_login(cTB)
        return

    # Here we really need to check settings and not simply get primary path
    # from addon-core, to get around addon-core providing a default path we
    # are not interested in.
    primary_lib_path = cTB.settings_config.get(
        "library", "primary", fallback=None)
    if primary_lib_path in [None, ""]:
        build_library(cTB)
        return

    cTB.vBase.separator()

    cTB.logger_ui.debug("build_ui -> build_areas")
    build_areas(cTB)

    if cTB.settings["show_user"]:
        build_user(cTB)
        return

    _build_search(cTB, props_wm, area)

    cTB.vActiveCat = cTB.settings["category"][area]
    cTB.vAssetType = cTB.vActiveCat[0]

    cTB.logger_ui.debug("build_ui -> build_categories")
    build_categories(cTB)

    cTB.logger_ui.debug("build_ui -> build_assets")
    build_assets(cTB)


# TODO(Andreas): Function not in use (only called from operator
#                poliigon.poliigon_active in mode "info", which is not used)
def f_AssetInfo(cTB, asset_id: int):
    """Dynamic menu popup call populated based on info on this asset."""

    cTB.logger_ui.debug(f"f_AssetInfo asset_id={asset_id}")

    @reporting.handle_draw()
    def asset_info_draw(self, context):
        """Called as part of the popup in operators for info mode."""

        asset_data = cTB._asset_index.get_asset(asset_id)
        asset_type_data = asset_data.get_type_data()
        asset_name = asset_data.asset_name
        asset_type = asset_data.asset_type

        vLayout = self.layout
        vLayout.alignment = "CENTER"

        column = vLayout.column(align=True)

        with cTB.lock_thumbs:
            column.template_icon(icon_value=cTB.thumbs[asset_name].icon_id,
                                 scale=10)

        row = column.row(align=False)

        row.label(text=asset_name)

        op = row.operator(
            "poliigon.poliigon_asset_options", text="", icon="FILE_FOLDER"
        )
        op.asset_id = asset_id
        op.mode = "dir"
        op.tooltip = _t("Open {0} Folder(s)").format(asset_name)

        op = row.operator(
            "poliigon.poliigon_link",
            text="",
            icon_value=cTB.ui_icons["ICON_poliigon"].icon_id,
        )
        op.mode = str(asset_id)
        op.asset_id = asset_id
        op.tooltip = _t("View on Poliigon.com")

        column.separator()

        if asset_type == AssetType.MODEL:
            column.label(text=_t("Models :"))

            column.separator()

        column.label(text=_t("Maps :"))

        vGrid = column.box().grid_flow(
            row_major=1, columns=4, even_columns=0, even_rows=0, align=False
        )

        tex_maps = asset_type_data.get_maps()
        # TODO(Andreas): need maps for all sizes
        for _tex_map in tex_maps:
            path = _tex_map.get_path()
            vGrid.label(text=path)

        column.separator()

        column.label(text=_t("Map Sizes :"))

        asset_sizes = asset_type_data.get_size_list()
        column.box().label(text="   ".join(asset_sizes))

        column.separator()

    bpy.context.window_manager.popover(asset_info_draw, ui_units_x=15)


class POLIIGON_PT_toolbox(Panel):
    bl_idname = "POLIIGON_PT_toolbox"
    bl_label = "Poliigon"
    bl_category = "Poliigon"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    @reporting.handle_draw()
    def draw(self, context):
        build_ui(self, context)


classes = (
    POLIIGON_PT_toolbox,
    POLIIGON_MT_add_node_groups
)


cTB = None


def register(addon_version: str):
    global cTB

    cTB = get_context(addon_version)

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.NODE_MT_add.append(append_poliigon_groups_node_add)


def unregister():
    bpy.types.NODE_MT_add.remove(append_poliigon_groups_node_add)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
