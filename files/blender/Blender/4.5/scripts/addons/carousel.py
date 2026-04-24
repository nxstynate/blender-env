bl_info = {
    "name": "Collection Instance Carousel",
    "author": "Nate",
    "version": (2, 1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Carousel",
    "description": "Carousel-animate collection instances for rendering option stills",
    "category": "Animation",
}

import bpy
import os
from bpy.props import (
    StringProperty,
    IntProperty,
    FloatProperty,
    CollectionProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
)
from bpy.types import Panel, Operator, PropertyGroup, UIList


# -----------------------------------------------------------------------------
# Core animation logic (mode-agnostic, takes a list of object names + params)
# -----------------------------------------------------------------------------

def _clear_location_action(obj):
    """Remove ALL location fcurves so reruns start clean."""
    if not (obj.animation_data and obj.animation_data.action):
        return
    action = obj.animation_data.action
    fcurves_to_remove = [fc for fc in action.fcurves if fc.data_path == "location"]
    for fc in fcurves_to_remove:
        action.fcurves.remove(fc)


def _insert_z_key(obj, frame, z_value, interpolation='CONSTANT'):
    obj.location[2] = z_value
    obj.keyframe_insert(data_path="location", index=2, frame=frame)
    # Set interpolation on the keyframe we just inserted
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            if fc.data_path == "location" and fc.array_index == 2:
                for kp in fc.keyframe_points:
                    if kp.co.x == frame:
                        kp.interpolation = interpolation
                break


def apply_carousel_keyframes(object_names, z_in, z_out, start_frame, hold=1, interpolation='CONSTANT'):
    """Carousel mode: each option visible for `hold` consecutive frames.

    Option i occupies frames [start_frame + i*hold, start_frame + i*hold + hold - 1].

    Keys per object:
      - z_out at (first_visible - 1)
      - z_in  at first_visible
      - z_in  at last_visible
      - z_out at (last_visible + 1)

    With CONSTANT interpolation the object sits cleanly at z_in for the whole window.
    When hold == 1, the two z_in keys collapse to a single frame — same behavior as before.
    """
    animated = 0

    for i, name in enumerate(object_names):
        obj = bpy.data.objects.get(name)
        if not obj:
            print(f"[Carousel] Object not found: {name}")
            continue

        _clear_location_action(obj)

        first_visible = start_frame + i * hold
        last_visible = first_visible + hold - 1

        # Hidden before
        _insert_z_key(obj, first_visible - 1, z_out, interpolation)
        # Visible window (two keys when hold > 1, one key when hold == 1)
        _insert_z_key(obj, first_visible, z_in, interpolation)
        if hold > 1:
            _insert_z_key(obj, last_visible, z_in, interpolation)
        # Hidden after
        _insert_z_key(obj, last_visible + 1, z_out, interpolation)

        animated += 1

    return animated


# -----------------------------------------------------------------------------
# Scanning
# -----------------------------------------------------------------------------

def scan_current_scene_for_instances():
    """Return list of dicts describing collection instances in the active scene."""
    results = []
    for obj in bpy.context.scene.objects:
        if obj.instance_type == 'COLLECTION' and obj.instance_collection:
            coll = obj.instance_collection
            label = f"{obj.name} ({coll.name})"
            if coll.library:
                label += " [linked]"
            results.append({'name': label, 'object_name': obj.name})
    return results


# -----------------------------------------------------------------------------
# Property groups
# -----------------------------------------------------------------------------

class CollectionInstanceItem(PropertyGroup):
    name: StringProperty(name="Name", default="")
    selected: BoolProperty(name="Selected", default=False)
    object_name: StringProperty(name="Object Name", default="")


class CarouselProperties(PropertyGroup):

    mode: EnumProperty(
        name="Mode",
        description="Work on the current file or an external .blend file",
        items=[
            ('CURRENT', "Current File", "Animate collection instances in the active scene"),
            ('EXTERNAL', "External File", "Open, modify, and save an external .blend file"),
        ],
        default='CURRENT',
    )

    target_file_path: StringProperty(
        name="Target File",
        description="Path to the .blend file containing linked collection instances",
        subtype='FILE_PATH',
    )

    collection_instances: CollectionProperty(type=CollectionInstanceItem)
    active_collection_index: IntProperty(default=0)

    start_frame: IntProperty(
        name="Start Frame",
        description="First frame where option 1 is visible",
        default=0,
    )

    z_in_frame: FloatProperty(
        name="Z In",
        description="Z position when option is visible",
        default=0.0,
    )

    z_out_frame: FloatProperty(
        name="Z Out",
        description="Z position when option is hidden (offscreen)",
        default=-2000.0,
    )

    hold: IntProperty(
        name="Hold",
        description="Frames each option stays visible before handing off to the next",
        default=1, min=1,
    )


# -----------------------------------------------------------------------------
# UI List
# -----------------------------------------------------------------------------

class COLLANIM_UL_collection_list(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "selected", text="")
            # Show the frame this option starts on — helps you see the schedule at a glance
            props = context.scene.carousel_props
            if item.selected:
                selected_indices = [i for i, it in enumerate(props.collection_instances) if it.selected]
                try:
                    slot = selected_indices.index(index)
                    start = props.start_frame + slot * props.hold
                    if props.hold == 1:
                        row.label(text=f"f{start}")
                    else:
                        row.label(text=f"f{start}–{start + props.hold - 1}")
                except ValueError:
                    pass
            row.label(text=item.name, icon='OUTLINER_COLLECTION')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='OUTLINER_COLLECTION')


# -----------------------------------------------------------------------------
# Operators — shared helpers
# -----------------------------------------------------------------------------

def _populate_list_from_scan(props, scan_results):
    props.collection_instances.clear()
    for instance in scan_results:
        item = props.collection_instances.add()
        item.name = instance['name']
        item.object_name = instance['object_name']
        item.selected = False


def _check_unsaved_changes(operator):
    """Return True if safe to proceed, False (with error reported) otherwise."""
    if bpy.data.is_dirty:
        operator.report(
            {'ERROR'},
            "Current file has unsaved changes. Save (Ctrl+S) before using External File mode."
        )
        return False
    return True


# -----------------------------------------------------------------------------
# Operators — scan
# -----------------------------------------------------------------------------

class COLLANIM_OT_scan(Operator):
    """Scan for collection instances (current file or external)"""
    bl_idname = "carousel.scan"
    bl_label = "Scan for Instances"
    bl_description = "Scan the current scene or target file for collection instances"

    def execute(self, context):
        props = context.scene.carousel_props

        if props.mode == 'CURRENT':
            results = scan_current_scene_for_instances()
            _populate_list_from_scan(props, results)
            self.report({'INFO'}, f"Found {len(results)} collection instances in current scene")
            return {'FINISHED'}

        # EXTERNAL mode
        target_file = bpy.path.abspath(props.target_file_path)
        if not target_file or not os.path.exists(target_file):
            self.report({'ERROR'}, "Invalid target file path")
            return {'CANCELLED'}

        if not _check_unsaved_changes(self):
            return {'CANCELLED'}

        current_file = bpy.data.filepath
        stored_target = props.target_file_path

        try:
            bpy.ops.wm.open_mainfile(filepath=target_file, load_ui=False)
            scan_results = scan_current_scene_for_instances()

            if current_file:
                bpy.ops.wm.open_mainfile(filepath=current_file, load_ui=False)
            else:
                bpy.ops.wm.read_homefile(load_ui=False)

            props = bpy.context.scene.carousel_props
            props.target_file_path = stored_target
            _populate_list_from_scan(props, scan_results)
            self.report({'INFO'}, f"Found {len(scan_results)} collection instances in target file")

        except Exception as e:
            self.report({'ERROR'}, f"Error scanning file: {e}")
            try:
                bpy.context.scene.carousel_props.target_file_path = stored_target
            except Exception:
                pass
            return {'CANCELLED'}

        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Operators — apply
# -----------------------------------------------------------------------------

def _do_apply(props):
    """Apply carousel keyframes. Returns count animated."""
    selected = [item.object_name for item in props.collection_instances if item.selected]
    if not selected:
        return 0

    return apply_carousel_keyframes(
        selected,
        z_in=props.z_in_frame,
        z_out=props.z_out_frame,
        start_frame=props.start_frame,
        hold=props.hold,
        interpolation='CONSTANT',
    )


class COLLANIM_OT_apply(Operator):
    """Apply animation to selected collection instances"""
    bl_idname = "carousel.apply"
    bl_label = "Apply Animation"
    bl_description = "Apply animation to selected collection instances"

    def execute(self, context):
        props = context.scene.carousel_props

        selected = [item.object_name for item in props.collection_instances if item.selected]
        if not selected:
            self.report({'WARNING'}, "No collection instances selected")
            return {'CANCELLED'}

        if props.mode == 'CURRENT':
            count = _do_apply(props)
            self.report({'INFO'}, f"Animated {count} objects in current scene")
            return {'FINISHED'}

        # EXTERNAL mode
        target_file = bpy.path.abspath(props.target_file_path)
        if not target_file or not os.path.exists(target_file):
            self.report({'ERROR'}, "Invalid target file path. Scan first.")
            return {'CANCELLED'}

        if not _check_unsaved_changes(self):
            return {'CANCELLED'}

        current_file = bpy.data.filepath

        # Snapshot all props before switching files — property group dies on file load
        snapshot = {
            'selected': selected,
            'start_frame': props.start_frame,
            'z_in': props.z_in_frame,
            'z_out': props.z_out_frame,
            'hold': props.hold,
            'target_file': target_file,
        }

        try:
            bpy.ops.wm.open_mainfile(filepath=target_file, load_ui=False)

            count = apply_carousel_keyframes(
                snapshot['selected'],
                z_in=snapshot['z_in'],
                z_out=snapshot['z_out'],
                start_frame=snapshot['start_frame'],
                hold=snapshot['hold'],
                interpolation='CONSTANT',
            )

            bpy.ops.wm.save_mainfile(filepath=snapshot['target_file'])

            if current_file:
                bpy.ops.wm.open_mainfile(filepath=current_file, load_ui=False)
            else:
                bpy.ops.wm.read_homefile(load_ui=False)

            bpy.context.scene.carousel_props.target_file_path = snapshot['target_file']
            self.report({'INFO'}, f"Animated {count} objects in target file and saved")

        except Exception as e:
            self.report({'ERROR'}, f"Error applying animation: {e}")
            if current_file:
                try:
                    bpy.ops.wm.open_mainfile(filepath=current_file, load_ui=False)
                    bpy.context.scene.carousel_props.target_file_path = snapshot['target_file']
                except Exception:
                    pass
            return {'CANCELLED'}

        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Operators — selection helpers
# -----------------------------------------------------------------------------

class COLLANIM_OT_select_all(Operator):
    bl_idname = "carousel.select_all"
    bl_label = "All"
    bl_description = "Select all collection instances"

    def execute(self, context):
        for item in context.scene.carousel_props.collection_instances:
            item.selected = True
        return {'FINISHED'}


class COLLANIM_OT_select_none(Operator):
    bl_idname = "carousel.select_none"
    bl_label = "None"
    bl_description = "Deselect all collection instances"

    def execute(self, context):
        for item in context.scene.carousel_props.collection_instances:
            item.selected = False
        return {'FINISHED'}


class COLLANIM_OT_select_invert(Operator):
    bl_idname = "carousel.select_invert"
    bl_label = "Invert"
    bl_description = "Invert selection"

    def execute(self, context):
        for item in context.scene.carousel_props.collection_instances:
            item.selected = not item.selected
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Panel
# -----------------------------------------------------------------------------

class COLLANIM_PT_main_panel(Panel):
    bl_label = "Collection Instance Carousel"
    bl_idname = "COLLANIM_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Carousel"

    def draw(self, context):
        layout = self.layout
        props = context.scene.carousel_props

        # Mode selector
        row = layout.row()
        row.prop(props, "mode", expand=True)

        # Target file (only in external mode)
        if props.mode == 'EXTERNAL':
            box = layout.box()
            box.label(text="Target File:", icon='FILE_BLEND')
            box.prop(props, "target_file_path", text="")

        # Scan button
        layout.operator("carousel.scan", icon='FILE_REFRESH')

        # Instance list
        if props.collection_instances:
            box = layout.box()
            selected_count = sum(1 for i in props.collection_instances if i.selected)
            box.label(
                text=f"Instances ({selected_count}/{len(props.collection_instances)} selected):",
                icon='OUTLINER_COLLECTION',
            )

            row = box.row()
            row.template_list(
                "COLLANIM_UL_collection_list", "",
                props, "collection_instances",
                props, "active_collection_index",
                rows=6,
            )

            row = box.row(align=True)
            row.operator("carousel.select_all")
            row.operator("carousel.select_none")
            row.operator("carousel.select_invert")

        # Animation params
        box = layout.box()
        box.label(text="Animation:", icon='KEYFRAME')

        col = box.column(align=True)
        col.prop(props, "start_frame")
        col.prop(props, "hold")
        col.prop(props, "z_in_frame")
        col.prop(props, "z_out_frame")

        # Frame range readout
        selected_count = sum(1 for i in props.collection_instances if i.selected)
        if selected_count > 0:
            info_box = layout.box()
            last_frame = props.start_frame + selected_count * props.hold - 1
            total_frames = selected_count * props.hold
            if props.hold == 1:
                info_box.label(
                    text=f"{selected_count} options → frames {props.start_frame}–{last_frame}",
                    icon='TIME',
                )
            else:
                info_box.label(
                    text=f"{selected_count} options × {props.hold} frames = {total_frames} total",
                    icon='TIME',
                )
                info_box.label(
                    text=f"Frames {props.start_frame}–{last_frame}",
                )

        # Apply
        layout.separator()
        row = layout.row()
        row.scale_y = 1.5
        label = "Apply to Target File" if props.mode == 'EXTERNAL' else "Apply to Current Scene"
        row.operator("carousel.apply", icon='PLAY', text=label)

        if props.mode == 'EXTERNAL':
            note = layout.box()
            note.label(text="External mode will save the target file.", icon='INFO')
            note.label(text="Save your current file first.")


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------

classes = (
    CollectionInstanceItem,
    CarouselProperties,
    COLLANIM_UL_collection_list,
    COLLANIM_OT_scan,
    COLLANIM_OT_apply,
    COLLANIM_OT_select_all,
    COLLANIM_OT_select_none,
    COLLANIM_OT_select_invert,
    COLLANIM_PT_main_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.carousel_props = PointerProperty(type=CarouselProperties)


def unregister():
    del bpy.types.Scene.carousel_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
