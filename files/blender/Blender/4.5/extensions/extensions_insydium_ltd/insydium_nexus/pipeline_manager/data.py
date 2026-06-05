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

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)


def _update_viewport_redraw(self, context):
    if context is None or context.screen is None:
        return
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


def _switch_properties_to_physics():
    """Switch all visible Properties Editors to Physics tab."""
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "PROPERTIES":
                    area.spaces.active.context = "PHYSICS"
    except (AttributeError, ReferenceError, TypeError):
        pass


def _on_folder_enabled_update(self, context):
    """Cascade disable/restore children when a folder is toggled."""
    scene = context.scene
    if not hasattr(scene, "nexus_pipeline"):
        return
    pipeline = scene.nexus_pipeline

    from .utils import (
        cascade_disable_children,
        restore_enabled_children,
    )

    for item in pipeline.modifier_order:
        if item.is_folder and item.folder_id == self.folder_id:
            if self.folder_enabled:
                restore_enabled_children(pipeline, item)
            else:
                cascade_disable_children(pipeline, item)
            break


def _on_index_changed(self, context):
    """Handle index change by deferring selection to avoid nested depsgraph updates."""
    scene = context.scene
    pipeline = scene.nexus_pipeline

    if not (0 <= pipeline.modifier_order_index < len(pipeline.modifier_order)):
        return

    item = pipeline.modifier_order[pipeline.modifier_order_index]

    if item.is_folder:
        return

    obj = item.modifier

    if obj is None:
        return

    try:
        if obj.name not in bpy.data.objects:
            return
    except ReferenceError:
        return

    obj_name = obj.name

    def _deferred_select():
        target = bpy.data.objects.get(obj_name)
        if target is None:
            return None
        try:
            bpy.ops.object.select_all(action="DESELECT")
            target.select_set(True)
            bpy.context.view_layer.objects.active = target
        except (RuntimeError, ReferenceError):
            pass
        bpy.app.timers.register(_switch_properties_to_physics, first_interval=0.05)
        return None

    bpy.app.timers.register(_deferred_select, first_interval=0)


class NexusPipelineItem(bpy.types.PropertyGroup):
    """Single item in the pipeline order list."""

    modifier: PointerProperty(
        name="Modifier",
        type=bpy.types.Object,
        description="Reference to NeXus modifier object",
    )

    parent_modifier: PointerProperty(
        name="Parent Modifier",
        type=bpy.types.Object,
        description="Parent modifier in hierarchy",
    )

    collapsed: BoolProperty(
        name="Collapsed",
        default=False,
    )

    is_folder: BoolProperty(
        name="Is Folder",
        default=False,
    )

    folder_id: StringProperty(
        name="Folder ID",
        default="",
    )

    folder_name: StringProperty(
        name="Folder Name",
        default="Folder",
        update=_update_viewport_redraw,
    )

    folder_enabled: BoolProperty(
        name="Folder Enabled",
        default=True,
        update=_on_folder_enabled_update,
    )

    folder_color: FloatVectorProperty(
        name="Folder Color",
        subtype="COLOR",
        size=3,
        default=(0.8, 0.8, 0.8),
        min=0.0,
        max=1.0,
        update=_update_viewport_redraw,
    )

    parent_folder_id: StringProperty(
        name="Parent Folder ID",
        default="",
    )

    cascade_disabled_keys: StringProperty(
        name="Disabled Children Keys",
        default="",
        options={"HIDDEN"},
    )


class NexusHUDSettings(bpy.types.PropertyGroup):
    """HUD overlay settings for the 3D viewport."""

    hud_enabled: BoolProperty(
        name="Enable HUD",
        default=False,
        description="Show the viewport HUD overlay",
        update=_update_viewport_redraw,
    )

    hud_show_particle_count: BoolProperty(
        name="Particle Count",
        default=True,
        description="Display the total particle count",
        update=_update_viewport_redraw,
    )

    hud_show_vram_usage: BoolProperty(
        name="VRAM Usage",
        default=True,
        description="Display GPU VRAM usage (used / total, percentage)",
        update=_update_viewport_redraw,
    )

    hud_show_release_info: BoolProperty(
        name="Release Info",
        default=True,
        description="Display add-on version and build date",
        update=_update_viewport_redraw,
    )

    hud_show_device_name: BoolProperty(
        name="Show GPU Name",
        default=True,
        description="Display the name of the active GPU",
        update=_update_viewport_redraw,
    )

    hud_show_frame_time: BoolProperty(
        name="Frame Time",
        default=True,
        description="Display NeXus pipeline frame time in milliseconds",
        update=_update_viewport_redraw,
    )

    hud_spark_particle_count: BoolProperty(
        name="Sparkline",
        default=True,
        description="Show sparkline graph for particle count",
        update=_update_viewport_redraw,
    )

    hud_spark_vram_pct: BoolProperty(
        name="Sparkline",
        default=False,
        description="Show sparkline graph for VRAM usage",
        update=_update_viewport_redraw,
    )

    hud_spark_frame_time: BoolProperty(
        name="Sparkline",
        default=True,
        description="Show sparkline graph for frame time",
        update=_update_viewport_redraw,
    )

    hud_pos_x: FloatProperty(
        name="HUD X",
        default=0.02,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Horizontal position as fraction of viewport width",
    )

    hud_pos_y: FloatProperty(
        name="HUD Y",
        default=0.05,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Vertical position as fraction of viewport height",
    )

    hud_font_size: IntProperty(
        name="Font Size",
        default=14,
        min=8,
        max=48,
        description="HUD text size",
    )

    hud_opacity: FloatProperty(
        name="Opacity",
        default=0.25,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="HUD background opacity",
    )

    hud_text_color: FloatVectorProperty(
        name="Text Color",
        subtype="COLOR",
        size=3,
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        description="HUD text colour",
        update=_update_viewport_redraw,
    )

    hud_bg_color: FloatVectorProperty(
        name="Background Color",
        subtype="COLOR",
        size=3,
        default=(0.0, 0.0, 0.0),
        min=0.0,
        max=1.0,
        description="HUD background colour",
        update=_update_viewport_redraw,
    )


class NexusDocumentSettings(bpy.types.PropertyGroup):
    """NeXus Global Document settings."""

    substeps: IntProperty(
        name="Substeps",
        default=1,
        min=1,
        max=100,
        description="Substeps per frame",
    )


class NexusPipelineSettings(bpy.types.PropertyGroup):
    """Scene-level pipeline settings."""

    modifier_order: CollectionProperty(
        type=NexusPipelineItem,
        name="Modifier Order",
        description="Ordered list of NeXus modifiers",
    )

    modifier_order_index: IntProperty(
        name="Active Index", default=0, min=0, update=_on_index_changed
    )

    sidebar_tab: EnumProperty(
        name="Tab",
        items=[
            ("HIERARCHY", "Hierarchy", "Modifier pipeline hierarchy"),
            ("HUD", "HUD", "Viewport HUD settings"),
            ("DOCUMENT", "Document", "Document settings"),
        ],
        default="HIERARCHY",
    )

    hud: PointerProperty(type=NexusHUDSettings)
    global_opts: PointerProperty(type=NexusDocumentSettings)


classes = [
    NexusPipelineItem,
    NexusHUDSettings,
    NexusDocumentSettings,
    NexusPipelineSettings,
]


def register():
    from bpy.utils import register_class

    for cls in classes:
        try:
            register_class(cls)
        except ValueError:
            pass

    bpy.types.Scene.nexus_pipeline = PointerProperty(type=NexusPipelineSettings)


def unregister():
    del bpy.types.Scene.nexus_pipeline

    from bpy.utils import unregister_class

    for cls in reversed(classes):
        try:
            unregister_class(cls)
        except RuntimeError:
            pass
