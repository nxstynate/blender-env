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

from ..modules.poliigon_core.multilingual import _t
from .utils_dlg import (
    get_ui_scale,
    wrapped_label)
from ..toolbox import c_Toolbox


ERR_CREDS_FORMAT = _t("Invalid email format/password length.")
# TODO(Andreas): Currently not sure about this error
ERR_LOGIN_TIMEOUT = _t("Login with website timed out, please try again")


def _draw_welcome_or_error(cTB: c_Toolbox, layout: bpy.types.UILayout) -> None:
    if cTB.user_invalidated() and not cTB.login_in_progress:
        layout.separator()

        if cTB.last_login_error == ERR_LOGIN_TIMEOUT:
            wrapped_label(
                cTB,
                cTB.width_draw_ui,
                cTB.last_login_error,
                layout,
                icon="ERROR"
            )
        else:
            wrapped_label(
                cTB,
                cTB.width_draw_ui,
                _t("Warning : You have been logged out as this account was "
                   "signed in on another device."),
                layout,
                icon="ERROR"
            )

    else:
        wrapped_label(
            cTB,
            cTB.width_draw_ui,
            _t("Welcome to the Poliigon Addon!"),
            layout
        )

    layout.separator()


def _draw_share_addon_errors(cTB: c_Toolbox,
                             layout: bpy.types.UILayout,
                             enabled: bool = True) -> None:
    # Show terms of service, optin/out.
    row_opt = layout.row()
    row_opt.alignment = "LEFT"
    row_opt.enabled = enabled
    # __spec__.parent since __package__ got deprecated
    # Since this module moved into dialogs,
    # we need to split off .dialogs
    spec_parent = __spec__.parent
    spec_parent = spec_parent.split(".")[0]
    prefs = bpy.context.preferences.addons.get(spec_parent, None)
    row_opt.prop(prefs.preferences, "reporting_opt_in", text="")
    twidth = cTB.width_draw_ui - 42 * get_ui_scale(cTB)
    wrapped_label(cTB, twidth, _t("Share addon errors / usage"), row_opt)


def _draw_switch_email_login(col: bpy.types.UILayout,
                             enabled: bool = True) -> None:
    row_login_email = col.row()
    row_login_email.enabled = enabled
    op_login_email = row_login_email.operator("poliigon.poliigon_user",
                                              text=_t("Login via email"),
                                              emboss=False)
    op_login_email.mode = "login_switch_to_email"
    op_login_email.tooltip = _t("Login via email")


def _draw_browser_login(cTB: c_Toolbox, col: bpy.types.UILayout) -> None:
    if cTB.login_in_progress:
        _draw_share_addon_errors(cTB, col, enabled=False)

        row_buttons = col.row(align=True)
        row_buttons.scale_y = 1.25

        col1 = row_buttons.column(align=True)
        op_login_website = col1.operator("poliigon.poliigon_user",
                                         text=_t("Opening browser..."),
                                         depress=True)
        op_login_website.mode = "none"
        op_login_website.tooltip = _t("Complete login via opened webpage")
        col1.enabled = False

        col2 = row_buttons.column(align=True)
        op_login_cancel = col2.operator("poliigon.poliigon_user",
                                        text="",
                                        icon="X")
        op_login_cancel.mode = "login_cancel"
        op_login_cancel.tooltip = _t("Cancel Log In")

        col.separator()

        _draw_switch_email_login(col, enabled=False)
    else:
        _draw_share_addon_errors(cTB, col)

        row_button = col.row()
        row_button.scale_y = 1.25

        op_login_website = row_button.operator("poliigon.poliigon_user",
                                               text=_t("Login via Browser"))
        op_login_website.mode = "login_with_website"
        op_login_website.tooltip = _t("Login via Browser")

        col.separator()

        _draw_switch_email_login(col)


def _draw_email_login(cTB: c_Toolbox, col: bpy.types.UILayout) -> None:
    vProps = bpy.context.window_manager.poliigon_props

    col.label(text="Email")

    row = col.row(align=True)
    row.prop(vProps, "vEmail")

    col_x = row.column(align=True)
    op = col_x.operator("poliigon.poliigon_setting",
                        text="",
                        icon="X")
    op.tooltip = _t("Clear Email")
    op.mode = "clear_email"

    error_credentials = False
    has_login_error = cTB.last_login_error is not None
    error_login = has_login_error and cTB.last_login_error != ERR_LOGIN_TIMEOUT
    if error_login and "@" not in vProps.vEmail:
        error_credentials = True

        col.separator()
        wrapped_label(
            cTB,
            cTB.width_draw_ui - 40 * get_ui_scale(cTB),
            _t("Email format is invalid e.g. john@example.org"),
            col,
            icon="ERROR")
    col.separator()

    col.label(text=_t("Password"))

    row = col.row(align=True)

    if cTB.settings["show_pass"]:
        row.prop(vProps, "vPassShow")
        vPass = vProps.vPassShow

    else:
        row.prop(vProps, "vPassHide")
        vPass = vProps.vPassHide

    col_x = row.column(align=True)

    op = col_x.operator("poliigon.poliigon_setting",
                        text="",
                        icon="X")
    op.tooltip = _t("Clear Password")
    op.mode = "clear_pass"

    if error_login and len(vPass) < 6:
        error_credentials = True

        col.separator()
        wrapped_label(
            cTB,
            cTB.width_draw_ui - 40 * get_ui_scale(cTB),
            _t("Password should be at least 6 characters."),
            col,
            icon="ERROR")
    col.separator()

    _draw_share_addon_errors(cTB, col)

    enable_login_button = len(vProps.vEmail) > 0 and len(vPass) > 0

    row = col.row()
    row.scale_y = 1.25

    if cTB.login_in_progress:
        op_login = row.operator("poliigon.poliigon_setting",
                                text=_t("Logging In..."),
                                depress=enable_login_button)
        op_login.mode = "none"
        op_login.tooltip = _t("Logging In...")
        row.enabled = False
    else:
        op_login = row.operator("poliigon.poliigon_user",
                                text=_t("Login via email"))
        op_login.mode = "login"
        op_login.tooltip = _t("Login via email")

        row.enabled = enable_login_button

    if cTB.last_login_error == ERR_CREDS_FORMAT:
        # Will draw above with more specific messages if condition true, like
        # invalid email format or password length.
        pass
    elif error_login and not error_credentials:
        col.separator()

        wrapped_label(
            cTB,
            cTB.width_draw_ui - 40 * get_ui_scale(cTB),
            cTB.last_login_error,
            col,
            icon="ERROR",
        )

    col.separator()

    op_forgot = col.operator("poliigon.poliigon_link",
                             text=_t("Forgot Password?"),
                             emboss=False)
    op_forgot.mode = "forgot"
    op_forgot.tooltip = _t("Reset your Poliigon password")

    op_login_website = col.operator("poliigon.poliigon_user",
                                    text=_t("Login via Browser"),
                                    emboss=False)
    op_login_website.mode = "login_switch_to_browser"
    op_login_website.tooltip = _t("Login via Browser")


def _draw_login(cTB, layout: bpy.types.UILayout) -> None:
    spc = 1.0 / cTB.width_draw_ui

    box = layout.box()
    row = box.row()
    row.separator(factor=spc)
    col = row.column()
    row.separator(factor=spc)

    twidth = cTB.width_draw_ui - 42 * get_ui_scale(cTB)
    wrapped_label(cTB, twidth, _t("Login"), col)
    col.separator()

    if cTB.login_mode_browser:
        _draw_browser_login(cTB, col)

    else:
        _draw_email_login(cTB, col)


def _draw_signup(cTB, layout: bpy.types.UILayout) -> None:
    wrapped_label(
        cTB,
        cTB.width_draw_ui,
        _t("Don't have an account?"),
        layout,
    )
    op_signup = layout.operator("poliigon.poliigon_link",
                                text=_t("Sign Up"))
    op_signup.mode = "signup"
    op_signup.tooltip = _t("Create a Poliigon account")


def _draw_legal(layout: bpy.types.UILayout) -> None:
    row = layout.row()
    col = row.column(align=True)

    op_terms = col.operator("poliigon.poliigon_link",
                            text=_t("Terms & Conditions"),
                            emboss=False)
    op_terms.tooltip = _t("View the terms and conditions page")
    op_terms.mode = "terms"

    op_privacy = col.operator("poliigon.poliigon_link",
                              text=_t("Privacy Policy"),
                              emboss=False)
    op_privacy.tooltip = _t("View the Privacy Policy ")
    op_privacy.mode = "privacy"


# @timer
def build_login(cTB):
    cTB.logger_ui.debug("build_login")

    if cTB.last_login_error is not None:
        cTB.login_in_progress = 0

    _draw_welcome_or_error(cTB, cTB.vBase)
    _draw_login(cTB, cTB.vBase)
    cTB.vBase.separator()
    _draw_signup(cTB, cTB.vBase)
    cTB.vBase.separator()
    _draw_legal(cTB.vBase)
