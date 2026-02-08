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


ADDON_NAME = "poliigon-addon-blender"

SUPPORTED_CONVENTION = 1

URLS_BLENDER = {
    "survey": "https://www.surveymonkey.com/r/p4b-addon-ui-01",
    "survey_subscribed": "https://www.surveymonkey.com/r/p4b-addon-ui-02",
    "survey_free": "https://www.surveymonkey.com/r/p4b-addon-ui-03",
    "p4b": "https://poliigon.com/blender",
    "changelog": "https://poliigon.com/blender",
    "unlimited": "https://help.poliigon.com/en/articles/10003983-unlimited-plans",
}

ICONS = [  # tuples: (name, filename, type)
    ("ICON_poliigon", "poliigon_logo.png", "IMAGE"),
    ("ICON_asset_balance", "asset_balance.png", "IMAGE"),
    ("ICON_myassets", "my_assets.png", "IMAGE"),
    ("ICON_new", "poliigon_new.png", "IMAGE"),
    ("GET_preview", "get_preview.png", "IMAGE"),
    ("NO_preview", "icon_nopreview.png", "IMAGE"),
    ("NOTIFY", "poliigon_notify.png", "IMAGE"),
    ("NEW_RELEASE", "poliigon_new.png", "IMAGE"),
    ("ICON_working", "icon_working.gif", "MOVIE"),
    ("ICON_dots", "icon_dots.png", "IMAGE"),
    ("ICON_acquired_check", "acquired_checkmark.png", "IMAGE"),
    ("ICON_subscription_paused", "subscription_paused.png", "IMAGE"),
    ("ICON_unlimited_local", "icon_unlimited_local.png", "IMAGE"),
    ("LOGO_unlimited", "logo_unlimited.png", "IMAGE"),
]

# TODO(Andreas): Not quite sure, why we do not need these in addon-core,
#                nor why these are different from SIZES
HDRI_RESOLUTIONS = ["1K", "2K", "3K", "4K", "6K", "8K", "16K"]


# Default asset ID 1000000 means fetch all IDs.
# 1000000 to be expected outside of valid range.
# Did not use -1 to leave the negative ID range for side imports.
ASSET_ID_ALL = 1000000

# -6 on label width:
# Needed to reduce a bit to avoid truncation on OSX 1x and 2x screens.
POPUP_WIDTH = 250
POPUP_WIDTH_LABEL = POPUP_WIDTH - 6
POPUP_WIDTH_NARROW = 200
POPUP_WIDTH_LABEL_NARROW = POPUP_WIDTH_NARROW - 6
POPUP_WIDTH_WIDE = 400
POPUP_WIDTH_LABEL_WIDE = POPUP_WIDTH_WIDE - 6
