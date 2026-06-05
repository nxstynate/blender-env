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

from bpy.props import (
    EnumProperty,
    FloatProperty,
    IntProperty,
)

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nexus_time import nexus_time_property
from ..libs.theron_sync import SyncType, Transform


def _on_radius_top_update(self, context):
    obj = self.id_data
    if obj.get("nexus_modifier_type") != "NX_SPLASH":
        return
    from ..utils.splash_data import scale_top_ring_handles, store_splash_prev_values

    prev = obj.get("_nx_splash_prev_radius_top")
    if prev is not None and prev > 1e-6:
        scale = self.ID_NX_SPLASH_RADIUS_TOP / prev
        if abs(scale - 1.0) > 1e-8:
            scale_top_ring_handles(obj, scale)
    store_splash_prev_values(obj, self)


def _on_radius_bottom_update(self, context):
    obj = self.id_data
    if obj.get("nexus_modifier_type") != "NX_SPLASH":
        return
    from ..utils.splash_data import scale_bottom_ring_handles, store_splash_prev_values

    prev = obj.get("_nx_splash_prev_radius_bottom")
    if prev is not None and prev > 1e-6:
        scale = self.ID_NX_SPLASH_RADIUS_BOTTOM / prev
        if abs(scale - 1.0) > 1e-8:
            scale_bottom_ring_handles(obj, scale)
    store_splash_prev_values(obj, self)


def _on_height_update(self, context):
    obj = self.id_data
    if obj.get("nexus_modifier_type") != "NX_SPLASH":
        return
    from ..utils.splash_data import scale_height_handles, store_splash_prev_values

    prev = obj.get("_nx_splash_prev_height")
    if prev is not None and prev > 1e-6:
        scale = self.ID_NX_SPLASH_HEIGHT / prev
        if abs(scale - 1.0) > 1e-8:
            scale_height_handles(obj, scale)
    store_splash_prev_values(obj, self)


def _on_handle_count_update(self, context):
    obj = self.id_data
    if obj.get("nexus_modifier_type") != "NX_SPLASH":
        return
    from ..utils.splash_data import resample_handles, store_splash_prev_values

    old_count = obj.get("_nx_splash_prev_handle_count")
    new_count = self.ID_NX_SPLASH_HANDLE_COUNT
    if old_count is not None and old_count != new_count:
        resample_handles(obj, old_count, new_count)
    store_splash_prev_values(obj, self)


NX_SPLASH_UI_CONFIG = {}


def get_splash_ui_config():
    return NX_SPLASH_UI_CONFIG


SPEC = ModifierPropertySpec(
    modifier_type="NX_SPLASH",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_SPLASH_RADIUS_BOTTOM",
            prop=FloatProperty(
                name="Bottom Radius",
                description="Bottom radius of the splash cone",
                default=0.25,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
                update=_on_radius_bottom_update,
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_SPLASH_HEIGHT",
            prop=FloatProperty(
                name="Height",
                description="Height of the splash cone",
                default=0.75,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
                update=_on_height_update,
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_SPLASH_RADIUS_TOP",
            prop=FloatProperty(
                name="Top Radius",
                description="Top radius of the splash cone",
                default=1.0,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
                update=_on_radius_top_update,
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_SPLASH_HANDLE_COUNT",
            prop=IntProperty(
                name="Handle Num",
                description="Number of handles around the splash cone",
                default=8,
                min=3,
                soft_max=32,
                max=2048,
                update=_on_handle_count_update,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_SPLASH_STR",
            prop=FloatProperty(
                name="Strength",
                description="Strength of the splash effect",
                default=100.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_SPLASH_START_TIME",
            prop=nexus_time_property(
                "ID_NX_SPLASH_START_TIME",
                name="Start Time",
                description="Time at which the splash begins",
                default=0.0,
            ),
            sync_type=SyncType.TIME,
        ),
        PropertyDescriptor(
            name="ID_NX_SPLASH_DURATION",
            prop=nexus_time_property(
                "ID_NX_SPLASH_DURATION",
                name="Duration",
                description="Duration of the splash effect",
                default=1.0,
                min=0.0,
            ),
            sync_type=SyncType.TIME,
        ),
        PropertyDescriptor(
            name="ID_NX_SPLASH_DISTANCE",
            prop=FloatProperty(
                name="Distance",
                description="Distance threshold for splash activation",
                default=0.2,
                min=0.0,
                soft_max=1.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
        ),
    ),
)
