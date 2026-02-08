bl_info = {
    "name": "Camera Keyframe Copier",
    "author": "BlackoutLLC",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > N-Panel > Camera KF",
    "description": "Copy position, rotation, and focal length from multiple target cameras to a source camera as keyframes",
    "category": "Animation",
}

import bpy
from bpy.props import (
    PointerProperty,
    CollectionProperty,
    IntProperty,
    BoolProperty,
    StringProperty,
)
from bpy.types import PropertyGroup, Panel, Operator, UIList


# -----------------------------------------------------------------------------
# Property Groups
# -----------------------------------------------------------------------------

class CKC_TargetCameraItem(PropertyGroup):
    """Property group for a single target camera in the list"""
    camera: PointerProperty(
        name="Camera",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'CAMERA'
    )
    selected: BoolProperty(
        name="Selected",
        default=False
    )


class CKC_Properties(PropertyGroup):
    """Main property group for the addon"""
    source_camera: PointerProperty(
        name="Source Camera",
        description="The camera that will receive the keyframes",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'CAMERA'
    )
    frame_interval: IntProperty(
        name="Frame Interval",
        description="Number of frames between each keyframe",
        default=1,
        min=1,
        max=1000
    )
    target_cameras: CollectionProperty(type=CKC_TargetCameraItem)
    active_target_index: IntProperty(name="Active Target Index", default=0)


# -----------------------------------------------------------------------------
# UI List
# -----------------------------------------------------------------------------

class CKC_UL_TargetCameraList(UIList):
    """UI List for displaying target cameras"""
    bl_idname = "CKC_UL_target_camera_list"
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "selected", text="")
            if item.camera:
                row.label(text=item.camera.name, icon='CAMERA_DATA')
            else:
                row.label(text="(Empty)", icon='CAMERA_DATA')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='CAMERA_DATA')


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------

class CKC_OT_RefreshCameraList(Operator):
    """Refresh the list of available cameras"""
    bl_idname = "ckc.refresh_camera_list"
    bl_label = "Refresh Camera List"
    bl_description = "Refresh the list of available target cameras from the scene"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.ckc_props
        
        # Store currently selected cameras
        selected_cameras = set()
        for item in props.target_cameras:
            if item.selected and item.camera:
                selected_cameras.add(item.camera.name)
        
        # Clear and rebuild the list
        props.target_cameras.clear()
        
        # Add all cameras except the source camera
        for obj in bpy.data.objects:
            if obj.type == 'CAMERA':
                item = props.target_cameras.add()
                item.camera = obj
                item.selected = obj.name in selected_cameras
        
        self.report({'INFO'}, f"Found {len(props.target_cameras)} cameras")
        return {'FINISHED'}


class CKC_OT_SelectAllTargets(Operator):
    """Select all target cameras"""
    bl_idname = "ckc.select_all_targets"
    bl_label = "Select All"
    bl_description = "Select all cameras as targets"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.ckc_props
        for item in props.target_cameras:
            if item.camera and item.camera != props.source_camera:
                item.selected = True
        return {'FINISHED'}


class CKC_OT_DeselectAllTargets(Operator):
    """Deselect all target cameras"""
    bl_idname = "ckc.deselect_all_targets"
    bl_label = "Deselect All"
    bl_description = "Deselect all target cameras"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.ckc_props
        for item in props.target_cameras:
            item.selected = False
        return {'FINISHED'}


class CKC_OT_CopyKeyframes(Operator):
    """Copy keyframes from target cameras to source camera"""
    bl_idname = "ckc.copy_keyframes"
    bl_label = "Copy Keyframes"
    bl_description = "Copy position, rotation, and focal length from selected target cameras to source camera"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.ckc_props
        
        # Validate source camera
        if not props.source_camera:
            self.report({'ERROR'}, "No source camera selected")
            return {'CANCELLED'}
        
        if props.source_camera.type != 'CAMERA':
            self.report({'ERROR'}, "Source must be a camera object")
            return {'CANCELLED'}
        
        # Get selected target cameras (excluding source)
        target_cameras = []
        for item in props.target_cameras:
            if item.selected and item.camera and item.camera != props.source_camera:
                target_cameras.append(item.camera)
        
        if not target_cameras:
            self.report({'ERROR'}, "No target cameras selected")
            return {'CANCELLED'}
        
        source_cam = props.source_camera
        source_cam_data = source_cam.data
        
        # Clear existing keyframes on source camera
        if source_cam.animation_data:
            source_cam.animation_data_clear()
        if source_cam_data.animation_data:
            source_cam_data.animation_data_clear()
        
        # Get starting frame and interval
        current_frame = context.scene.frame_current
        interval = props.frame_interval
        
        # Process each target camera
        for i, target_cam in enumerate(target_cameras):
            frame = current_frame + (i * interval)
            target_cam_data = target_cam.data
            
            # Copy location
            source_cam.location = target_cam.location.copy()
            source_cam.keyframe_insert(data_path="location", frame=frame)
            
            # Copy rotation
            source_cam.rotation_euler = target_cam.rotation_euler.copy()
            source_cam.keyframe_insert(data_path="rotation_euler", frame=frame)
            
            # Copy focal length
            source_cam_data.lens = target_cam_data.lens
            source_cam_data.keyframe_insert(data_path="lens", frame=frame)
        
        # Set all keyframes to linear interpolation (CONSTANT for no interpolation)
        self._set_linear_interpolation(source_cam)
        self._set_linear_interpolation(source_cam_data)
        
        self.report({'INFO'}, f"Created keyframes from {len(target_cameras)} cameras starting at frame {current_frame}")
        return {'FINISHED'}
    
    def _set_linear_interpolation(self, data_block):
        """Set all keyframes to constant interpolation (no interpolation between keys)"""
        if not data_block.animation_data or not data_block.animation_data.action:
            return
        
        for fcurve in data_block.animation_data.action.fcurves:
            for keyframe in fcurve.keyframe_points:
                keyframe.interpolation = 'CONSTANT'


class CKC_OT_MoveTargetUp(Operator):
    """Move selected target camera up in the list"""
    bl_idname = "ckc.move_target_up"
    bl_label = "Move Up"
    bl_description = "Move the active target camera up in the list"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.ckc_props
        index = props.active_target_index
        
        if index > 0:
            props.target_cameras.move(index, index - 1)
            props.active_target_index -= 1
        
        return {'FINISHED'}


class CKC_OT_MoveTargetDown(Operator):
    """Move selected target camera down in the list"""
    bl_idname = "ckc.move_target_down"
    bl_label = "Move Down"
    bl_description = "Move the active target camera down in the list"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.ckc_props
        index = props.active_target_index
        
        if index < len(props.target_cameras) - 1:
            props.target_cameras.move(index, index + 1)
            props.active_target_index += 1
        
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Panel
# -----------------------------------------------------------------------------

class CKC_PT_MainPanel(Panel):
    """Main panel in the N-Panel"""
    bl_label = "Camera Keyframe Copier"
    bl_idname = "CKC_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Camera KF"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.ckc_props
        
        # Source Camera Section
        box = layout.box()
        box.label(text="Source Camera", icon='CAMERA_DATA')
        box.prop(props, "source_camera", text="")
        
        # Frame Settings
        box = layout.box()
        box.label(text="Frame Settings", icon='TIME')
        row = box.row()
        row.prop(props, "frame_interval", text="Interval")
        row.label(text=f"Start: {context.scene.frame_current}")
        
        # Target Cameras Section
        box = layout.box()
        row = box.row()
        row.label(text="Target Cameras", icon='OUTLINER_OB_CAMERA')
        row.operator("ckc.refresh_camera_list", text="", icon='FILE_REFRESH')
        
        # Camera list
        row = box.row()
        row.template_list(
            "CKC_UL_target_camera_list",
            "",
            props,
            "target_cameras",
            props,
            "active_target_index",
            rows=5
        )
        
        # List controls
        col = row.column(align=True)
        col.operator("ckc.move_target_up", text="", icon='TRIA_UP')
        col.operator("ckc.move_target_down", text="", icon='TRIA_DOWN')
        
        # Select/Deselect buttons
        row = box.row(align=True)
        row.operator("ckc.select_all_targets", text="Select All")
        row.operator("ckc.deselect_all_targets", text="Deselect All")
        
        # Count selected
        selected_count = sum(1 for item in props.target_cameras 
                           if item.selected and item.camera and item.camera != props.source_camera)
        box.label(text=f"Selected: {selected_count} cameras")
        
        # Execute Button
        layout.separator()
        row = layout.row()
        row.scale_y = 1.5
        row.operator("ckc.copy_keyframes", text="Copy Keyframes", icon='KEY_HLT')


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------

classes = (
    CKC_TargetCameraItem,
    CKC_Properties,
    CKC_UL_TargetCameraList,
    CKC_OT_RefreshCameraList,
    CKC_OT_SelectAllTargets,
    CKC_OT_DeselectAllTargets,
    CKC_OT_CopyKeyframes,
    CKC_OT_MoveTargetUp,
    CKC_OT_MoveTargetDown,
    CKC_PT_MainPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ckc_props = PointerProperty(type=CKC_Properties)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.ckc_props


if __name__ == "__main__":
    register()
