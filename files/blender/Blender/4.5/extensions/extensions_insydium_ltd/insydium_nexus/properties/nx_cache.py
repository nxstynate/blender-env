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
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from ..libs.modifier_spec import ModifierPropertySpec, PropertyDescriptor


def _default_cache_dir() -> str:
    dir_name = None
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        dir_name = os.path.join(base, "INSYDIUM", "NeXus", "Cache")
    elif sys.platform == "darwin":
        dir_name = os.path.expanduser("~/Library/Caches/INSYDIUM/NeXus")
    else:
        xdg = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
        dir_name = os.path.join(xdg, "INSYDIUM", "NeXus")

    return dir_name


_DEFAULT_CACHE_DIR = _default_cache_dir()

_CACHE_FORMAT_ITEMS = [
    ("ID_NX_CACHE_FORMAT_NEXUS", "NeXus", "Native NeXus format", 0),
    ("ID_NX_CACHE_FORMAT_ALEMBIC", "Alembic", "Alembic format", 1),
]

_CACHE_VOXEL_FORMAT_ITEMS = [
    ("ID_NX_CACHE_VOXEL_FORMAT_NEXUS", "NeXus", "Native NeXus format", 0),
    ("ID_NX_CACHE_VOXEL_FORMAT_VDB", "OpenVDB", "OpenVDB format", 1),
]

_CACHE_MODE_ITEMS = [
    ("ID_NX_CACHE_MODE_OFF", "Off", "Disable caching", 0),
    ("ID_NX_CACHE_MODE_PLAYBACK", "Playback", "Read cached data during playback", 1),
    ("ID_NX_CACHE_MODE_RECORD", "Record", "Record simulation data to cache", 2),
]

_CACHE_RECORD_DATA_ITEMS = [
    (
        "ID_NX_CACHE_RECORD_DATA_BASIC",
        "Basic",
        "Record position, velocity and basic particle data",
        0,
    ),
    ("ID_NX_CACHE_RECORD_DATA_ALL", "All", "Record all available particle data", 1),
    ("ID_NX_CACHE_RECORD_DATA_CUSTOM", "Custom", "Select specific data channels to record", 2),
]

_CACHE_EFX_CHANNELS = [
    ("SMOKE", "Smoke", True, "smoke"),
    ("TEMP", "Temperature", True, "temperature"),
    ("FUEL", "Fuel", False, "fuel"),
    ("VELOCITY", "Velocity", False, "vel"),
    ("COLOUR", "Colour", False, "Cd"),
]

_CACHE_RECORD_PROPS = [
    ("VELOCITY", "Velocity", True),
    ("COLOR", "Color", False),
    ("MASS", "Mass", False),
    ("FUEL", "Fuel", False),
    ("ROTATION", "Rotation", False),
    ("TIME", "Time", False),
    ("DISPLAY", "Display", False),
    ("GROUP", "Group", False),
    ("TEMPERATURE", "Temperature", False),
    ("SMOKE", "Smoke", False),
    ("SCALE", "Scale", False),
    ("LIFE", "Life", False),
    ("ID", "ID", False),
    ("RADIUS", "Radius", False),
    ("DISTANCE", "Distance", False),
]


def _get_cache_format_items(self, context):
    return _CACHE_FORMAT_ITEMS


def _get_cache_voxel_format_items(self, context):
    return _CACHE_VOXEL_FORMAT_ITEMS


def _get_cache_mode_items(self, context):
    return _CACHE_MODE_ITEMS


def _get_cache_record_data_items(self, context):
    return _CACHE_RECORD_DATA_ITEMS


def _get_cache_directory():
    try:
        pkg = __package__.rsplit(".", 1)[0]
        return bpy.context.preferences.addons[pkg].preferences.cache_directory
    except Exception:
        return _DEFAULT_CACHE_DIR


_CACHE_ENUM_DEFAULTS = {
    "ID_NX_CACHE_FORMAT": "ID_NX_CACHE_FORMAT_NEXUS",
    "ID_NX_CACHE_VOXEL_FORMAT": "ID_NX_CACHE_VOXEL_FORMAT_NEXUS",
    "ID_NX_CACHE_MODE": "ID_NX_CACHE_MODE_OFF",
    "ID_NX_CACHE_RECORD_DATA": "ID_NX_CACHE_RECORD_DATA_BASIC",
}

SPEC = ModifierPropertySpec(
    modifier_type="NX_CACHE",
    enum_defaults=_CACHE_ENUM_DEFAULTS,
    descriptors=(
        PropertyDescriptor(
            name="ID_NX_CACHE_FORMAT",
            prop=EnumProperty(
                name="Format",
                description="File format used for cache data",
                items=_get_cache_format_items,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_CACHE_SCALE",
            prop=FloatProperty(
                name="Scale",
                description="Unit scale applied when reading/writing cache files",
                default=1.0,
                min=0.0,
                soft_max=100.0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_CACHE_VOXEL_FORMAT",
            prop=EnumProperty(
                name="EFX Format",
                description="File format used for EFX voxel cache data",
                items=_get_cache_voxel_format_items,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_CACHE_VOXEL_SCALE",
            prop=FloatProperty(
                name="EFX Scale",
                description="Unit scale applied when reading/writing EFX voxel cache files",
                default=1.0,
                min=0.0,
                soft_max=100.0,
            ),
        ),
        *(
            descriptor
            for key, label, default_on, default_name in _CACHE_EFX_CHANNELS
            for descriptor in (
                PropertyDescriptor(
                    name=f"ID_NX_CACHE_VOXEL_CHANNEL_{key}",
                    prop=BoolProperty(
                        name=label,
                        description=f"Include {label.lower()} channel in the EFX cache",
                        default=default_on,
                    ),
                ),
                PropertyDescriptor(
                    name=f"ID_NX_CACHE_VOXEL_CHANNEL_{key}_NAME",
                    prop=StringProperty(
                        name="Channel Name",
                        description=f"Grid/channel name for {label.lower()}",
                        default=default_name,
                    ),
                ),
            )
        ),
        PropertyDescriptor(
            name="ID_NX_CACHE_DIRECTORY",
            prop=StringProperty(
                name="Directory",
                description="Directory where cache files are written",
                default=_get_cache_directory(),
                subtype="DIR_PATH",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_CACHE_COMPRESS",
            prop=BoolProperty(
                name="Compress Cache",
                description="Compress cache data to reduce disk usage",
                default=True,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_CACHE_MEMORY_USE_LIMIT",
            prop=IntProperty(
                name="Memory Limit (MB)",
                description="Maximum memory the cache may use in megabytes",
                default=100,
                min=0,
                soft_max=65536,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_CACHE_MODE",
            prop=EnumProperty(
                name="Cache Mode",
                description="Caching mode",
                items=_get_cache_mode_items,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_CACHE_RECORD_DATA",
            prop=EnumProperty(
                name="Record Particle Data",
                description="Which particle data channels to record",
                items=_get_cache_record_data_items,
            ),
        ),
        *(
            PropertyDescriptor(
                name=f"ID_NX_CACHE_RECORD_PROP_{key}",
                prop=BoolProperty(
                    name=label,
                    description=f"Include {label} data in the cache",
                    default=default_on,
                ),
                theron_id="ID_NX_CACHE_PARTICLE_DATA_SMOKE"
                if key == "SMOKE"
                else f"ID_NX_CACHE_PARTICLE_DATA_{key}",
                condition=lambda props: (
                    props.ID_NX_CACHE_RECORD_DATA == "ID_NX_CACHE_RECORD_DATA_CUSTOM"
                ),
            )
            for key, label, default_on in _CACHE_RECORD_PROPS
        ),
        PropertyDescriptor(
            name="cache_info_frames",
            prop=StringProperty(
                name="Cached Frames",
                description="Number of frames currently stored in the cache",
                default="",
                options={"SKIP_SAVE"},
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="cache_info_memory",
            prop=StringProperty(
                name="Memory Used",
                description="Cache memory currently resident in RAM",
                default="",
                options={"SKIP_SAVE"},
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="cache_info_disk_space",
            prop=StringProperty(
                name="Disk Space Used",
                description="Compressed cache size on disk",
                default="",
                options={"SKIP_SAVE"},
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="cache_info_uncompressed",
            prop=StringProperty(
                name="Uncompressed Size",
                description="Total cache size before compression",
                default="",
                options={"SKIP_SAVE"},
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="cache_info_compression_ratio",
            prop=StringProperty(
                name="Compression Ratio",
                description="Ratio of uncompressed size to compressed disk size",
                default="",
                options={"SKIP_SAVE"},
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="cache_info_elapsed",
            prop=StringProperty(
                name="Time to Complete",
                description="Elapsed or estimated time for the last build",
                default="",
                options={"SKIP_SAVE"},
            ),
            no_sync=True,
        ),
    ),
)


class NexusCacheSourceItem(bpy.types.PropertyGroup):
    obj: PointerProperty(name="Object", type=bpy.types.Object)
    locked: BoolProperty(name="Locked", default=False)
    enabled: BoolProperty(name="Enabled", default=True)


class NEXUS_UL_cache_sources(bpy.types.UIList):
    bl_idname = "NEXUS_UL_cache_sources"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        from ..icons import get_icon

        if self.layout_type not in {"DEFAULT", "COMPACT"} or item.obj is None:
            return

        row = layout.row(align=True)

        lock_icon = get_icon("nx_cache_locked" if item.locked else "nx_cache_unlocked")
        op = row.operator(
            "nexus.cache_source_toggle_lock", text="", icon_value=lock_icon, emboss=False
        )
        op.index = index

        mod_type = item.obj.get("nexus_modifier_type", "").lower()
        icon_val = get_icon(mod_type)
        name_sub = row.row(align=True)
        name_sub.enabled = item.enabled
        name_sub.label(text=item.obj.name, icon_value=icon_val if icon_val > 0 else 0)

        enable_sub = row.row(align=True)
        enable_sub.ui_units_x = 1.0
        enable_sub.prop(
            item,
            "enabled",
            text="",
            emboss=False,
            icon_value=get_icon("nx_enable") if item.enabled else get_icon("nx_disable"),
        )
