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

import bpy

from ..modules.poliigon_core.api_remote_control_params import (
    KEY_TAB_IMPORTED,
    KEY_TAB_MY_ASSETS,
    KEY_TAB_ONLINE)
from ..modules.poliigon_core.multilingual import _t


def _draw_unlimited_icon(cTB, *, row: bpy.types.UILayout) -> None:
    icon_value = cTB.ui_icons["LOGO_unlimited"].icon_id
    op_icon = row.operator(
        "poliigon.poliigon_setting", text="", emboss=True, icon_value=icon_value)
    op_icon.mode = "show_user"
    # TODO(Andreas): Tooltip???
    op_icon.tooltip = _t("Switch to your account details")


def _draw_asset_balance(cTB, *, row: bpy.types.UILayout) -> None:
    if cTB.is_unlimited_user():
        _draw_unlimited_icon(cTB, row=row)
        return

    # Asset balance
    credits = cTB.get_user_credits()
    balance_icon = cTB.ui_icons["ICON_asset_balance"].icon_id
    if cTB.is_paused_subscription() and credits <= 0:
        balance_icon = cTB.ui_icons["ICON_subscription_paused"].icon_id

    op_credits = row.operator(
        "poliigon.poliigon_setting",
        text=str(credits),
        icon_value=balance_icon  # TODO: use new asset icon
    )
    op_credits.tooltip = _t(
        "Your asset balance shows how many assets you can\n"
        "purchase. Free assets and downloading assets you\n"
        "already own doesn’t affect your balance")
    op_credits.mode = "show_user"


def _add_asset_tab(cTB,
                   row: bpy.types.UILayout,
                   *,
                   tab: str,
                   mode: str,
                   icon: str = "NONE",
                   icon_value: int = 0,
                   tooltip: str = ""
                   ) -> None:
    no_user = not cTB.settings["show_user"]
    no_settings = not cTB.settings["show_settings"]
    no_user_or_settings = no_user and no_settings

    col = row.column(align=True)
    is_tab_active = cTB.settings["area"] == tab
    op = col.operator(
        "poliigon.poliigon_setting",
        text="",
        icon=icon,
        icon_value=icon_value,
        depress=is_tab_active and no_user_or_settings,
    )
    op.mode = mode
    op.tooltip = tooltip


# @timer
def build_areas(cTB):
    cTB.logger_ui.debug("build_areas")
    cTB.initial_view_screen()

    row = cTB.vBase.row(align=True)
    row.scale_x = 1.1
    row.scale_y = 1.1

    _add_asset_tab(
        cTB,
        row,
        tab=KEY_TAB_ONLINE,
        mode="area_poliigon",
        icon="HOME",
        tooltip=_t("Show Poliigon Assets"))
    _add_asset_tab(
        cTB,
        row,
        tab=KEY_TAB_MY_ASSETS,
        mode="area_my_assets",
        icon_value=cTB.ui_icons["ICON_myassets"].icon_id,
        tooltip=_t("Show My Assets"))
    _add_asset_tab(
        cTB,
        row,
        tab=KEY_TAB_IMPORTED,
        mode="area_imported",
        icon="OUTLINER_OB_GROUP_INSTANCE",
        tooltip=_t("Show Imported Assets"))

    op = row.operator(
        "poliigon.poliigon_setting",
        text="",
        icon_value=cTB.ui_icons["ICON_poliigon"].icon_id,
        depress=cTB.settings["show_user"],
    )
    op.mode = "my_account"
    op.tooltip = _t("Show Your Account Details")

    row.separator()

    row_prefs = row.row(align=True)
    row_prefs.alignment = "RIGHT"

    _draw_asset_balance(cTB, row=row_prefs)

    _ = row_prefs.operator(
        "poliigon.open_preferences",
        text="",
        icon="PREFERENCES",
    ).set_focus = "all"

    cTB.vBase.separator()
