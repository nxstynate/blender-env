bl_info = {
    "name": "Carousel",
    "author": "NXSTYNATE",
    "version": (1, 0, 2),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > Carousel",
    "description": "Animate linked collection instances with Z-axis keyframes",
    "category": "Animation",
}

import bpy
import os
from bpy.props import StringProperty, IntProperty, FloatProperty, CollectionProperty, BoolProperty
from bpy.types import Panel, Operator, PropertyGroup, UIList


class CollectionInstanceItem(PropertyGroup):
    """Property group for collection instance items"""
    name: StringProperty(name="Name", default="")
    selected: BoolProperty(name="Selected", default=False)
    object_name: StringProperty(name="Object Name", default="")


class COLLANIM_UL_collection_list(UIList):
    """UI List for displaying collection instances"""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "selected", text="")
            row.label(text=item.name, icon='OUTLINER_COLLECTION')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='OUTLINER_COLLECTION')


class COLLANIM_OT_scan_target_file(Operator):
    """Scan target file for linked collection instances"""
    bl_idname = "collanim.scan_target_file"
    bl_label = "Scan Target File"
    bl_description = "Scan the target file for linked collection instances"
    
    def execute(self, context):
        props = context.scene.collection_animator_props
        target_file = props.target_file_path
        
        if not target_file or not os.path.exists(target_file):
            self.report({'ERROR'}, "Invalid file path")
            return {'CANCELLED'}
        
        try:
            # Save current file state
            current_file = bpy.data.filepath
            
            # Store the target file path to restore it later
            stored_target_path = target_file
            
            # Store collection instances data before switching files
            collection_instances = []
            
            # Open target file in background
            bpy.ops.wm.open_mainfile(filepath=target_file, load_ui=False)
            
            # Find collection instances
            for obj in bpy.data.objects:
                if obj.instance_type == 'COLLECTION' and obj.instance_collection:
                    # Check if it's a linked collection
                    if obj.instance_collection.library:
                        collection_instances.append({
                            'name': f"{obj.name} ({obj.instance_collection.name})",
                            'object_name': obj.name
                        })
            
            # Restore original file
            if current_file:
                bpy.ops.wm.open_mainfile(filepath=current_file, load_ui=False)
            else:
                bpy.ops.wm.read_homefile(load_ui=False)
            
            # Now we're back in the original context, safe to modify properties
            # Get props again after file switch
            props = bpy.context.scene.collection_animator_props
            
            # Restore the target file path
            props.target_file_path = stored_target_path
            
            # Clear existing list
            props.collection_instances.clear()
            
            # Populate the list with found instances
            for instance in collection_instances:
                item = props.collection_instances.add()
                item.name = instance['name']
                item.object_name = instance['object_name']
                item.selected = False
            
            self.report({'INFO'}, f"Found {len(collection_instances)} linked collection instances")
            
        except Exception as e:
            self.report({'ERROR'}, f"Error scanning file: {str(e)}")
            # Try to restore the target path even on error
            try:
                if 'stored_target_path' in locals():
                    bpy.context.scene.collection_animator_props.target_file_path = stored_target_path
            except:
                pass
            return {'CANCELLED'}
        
        return {'FINISHED'}


class COLLANIM_OT_apply_animation(Operator):
    """Apply animation to selected collection instances in the target file"""
    bl_idname = "collanim.apply_animation"
    bl_label = "Apply Animation"
    bl_description = "Apply Z-axis animation to selected collection instances in the target file"
    
    def execute(self, context):
        props = context.scene.collection_animator_props
        target_file = props.target_file_path
        
        if not target_file or not os.path.exists(target_file):
            self.report({'ERROR'}, "Invalid target file path. Please scan the target file first.")
            return {'CANCELLED'}
        
        # Get selected collections and animation parameters before switching files
        selected_collections = [(item.name, item.object_name) for item in props.collection_instances if item.selected]
        
        if not selected_collections:
            self.report({'WARNING'}, "No collections selected")
            return {'CANCELLED'}
        
        # Store animation parameters
        start_frame = props.start_frame
        z_in = props.z_in_frame
        z_out = props.z_out_frame
        hold_duration = props.hold_duration
        frame_offset = props.frame_offset
        overlap = props.overlap
        
        # Save current file path
        current_file = bpy.data.filepath
        
        try:
            # Open target file
            bpy.ops.wm.open_mainfile(filepath=target_file, load_ui=False)
            
            animated_objects = 0
            
            for i, (display_name, object_name) in enumerate(selected_collections):
                # Find the object in the target file
                obj = bpy.data.objects.get(object_name)
                
                if not obj:
                    print(f"Warning: Object '{object_name}' not found in target file")
                    continue
                
                # Calculate frame timing for this collection
                collection_start_frame = start_frame + (i * (frame_offset - overlap))
                
                # Clear existing keyframes for location.z
                if obj.animation_data and obj.animation_data.action:
                    for fcurve in obj.animation_data.action.fcurves:
                        if fcurve.data_path == "location" and fcurve.array_index == 2:
                            obj.animation_data.action.fcurves.remove(fcurve)
                            break
                
                # Set keyframes
                frames_and_values = [
                    (collection_start_frame, z_out),  # Frame 0: Out of frame
                    (collection_start_frame + 1, z_in),  # Frame 1: In frame
                    (collection_start_frame + 1 + hold_duration, z_in),  # Hold
                    (collection_start_frame + 2 + hold_duration, z_out)  # Out of frame
                ]
                
                for frame, z_value in frames_and_values:
                    obj.location[2] = z_value
                    obj.keyframe_insert(data_path="location", index=2, frame=frame)
                
                # Set interpolation to linear
                if obj.animation_data and obj.animation_data.action:
                    for fcurve in obj.animation_data.action.fcurves:
                        if fcurve.data_path == "location" and fcurve.array_index == 2:
                            for keyframe in fcurve.keyframe_points:
                                keyframe.interpolation = 'LINEAR'
                            break
                
                animated_objects += 1
            
            # Save the target file with animations
            bpy.ops.wm.save_mainfile(filepath=target_file)
            
            # Return to original file
            if current_file:
                bpy.ops.wm.open_mainfile(filepath=current_file, load_ui=False)
            else:
                bpy.ops.wm.read_homefile(load_ui=False)
            
            # Restore the target file path after returning
            bpy.context.scene.collection_animator_props.target_file_path = target_file
            
            self.report({'INFO'}, f"Applied animation to {animated_objects} objects in target file and saved")
            
        except Exception as e:
            self.report({'ERROR'}, f"Error applying animation: {str(e)}")
            # Try to return to original file
            if current_file:
                try:
                    bpy.ops.wm.open_mainfile(filepath=current_file, load_ui=False)
                    # Try to restore the target path
                    bpy.context.scene.collection_animator_props.target_file_path = target_file
                except:
                    pass
            return {'CANCELLED'}
        
        return {'FINISHED'}


class CollectionAnimatorProperties(PropertyGroup):
    """Properties for the Carousel"""
    
    target_file_path: StringProperty(
        name="Target File",
        description="Path to the .blend file containing linked collection instances",
        subtype='FILE_PATH'
    )
    
    collection_instances: CollectionProperty(
        type=CollectionInstanceItem,
        name="Collection Instances"
    )
    
    active_collection_index: IntProperty(
        name="Active Collection Index",
        default=0
    )
    
    start_frame: IntProperty(
        name="Start Frame",
        description="Starting frame for animation",
        default=0,
        min=0
    )
    
    z_in_frame: FloatProperty(
        name="Z In-frame Value",
        description="Z position when collection is visible",
        default=0.0
    )
    
    z_out_frame: FloatProperty(
        name="Z Out-of-frame Value",
        description="Z position when collection is hidden",
        default=-2000.0
    )
    
    hold_duration: IntProperty(
        name="Hold Duration",
        description="Number of frames to hold the collection in frame",
        default=1,
        min=1
    )
    
    frame_offset: IntProperty(
        name="Frame Offset",
        description="Frame distance between each collection's animation start",
        default=2,
        min=1
    )
    
    overlap: IntProperty(
        name="Overlap",
        description="Frames of overlap between animations",
        default=0,
        min=0
    )


class COLLANIM_PT_main_panel(Panel):
    """Main panel for Carousel"""
    bl_label = "Carousel"
    bl_idname = "COLLANIM_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Carousel"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.collection_animator_props
        
        # Target file section
        box = layout.box()
        box.label(text="Target File:", icon='FILE_BLEND')
        box.prop(props, "target_file_path", text="")
        box.operator("collanim.scan_target_file", icon='FILE_REFRESH')
        
        # Collection list section
        if props.collection_instances:
            box = layout.box()
            box.label(text="Collection Instances:", icon='OUTLINER_COLLECTION')
            
            row = box.row()
            row.template_list(
                "COLLANIM_UL_collection_list", "",
                props, "collection_instances",
                props, "active_collection_index",
                rows=4
            )
            
            # Select all/none buttons
            col = box.column(align=True)
            row = col.row(align=True)
            row.operator("collanim.select_all_collections", text="All")
            row.operator("collanim.select_none_collections", text="None")
        
        # Animation parameters section
        box = layout.box()
        box.label(text="Animation Parameters:", icon='KEYFRAME')
        
        col = box.column(align=True)
        col.prop(props, "start_frame")
        col.prop(props, "z_in_frame")
        col.prop(props, "z_out_frame")
        col.prop(props, "hold_duration")
        col.prop(props, "frame_offset")
        col.prop(props, "overlap")
        
        # Apply animation button
        layout.separator()
        row = layout.row()
        row.scale_y = 1.5
        row.operator("collanim.apply_animation", icon='PLAY', text="Apply Animation to Target File")
        
        # Warning text
        box = layout.box()
        box.label(text="Note:", icon='INFO')
        box.label(text="Animation will be applied to the target file")
        box.label(text="and the file will be saved automatically.")


class COLLANIM_OT_select_all_collections(Operator):
    """Select all collections in the list"""
    bl_idname = "collanim.select_all_collections" 
    bl_label = "Select All"
    bl_description = "Select all collections in the list"
    
    def execute(self, context):
        props = context.scene.collection_animator_props
        for item in props.collection_instances:
            item.selected = True
        return {'FINISHED'}


class COLLANIM_OT_select_none_collections(Operator):
    """Deselect all collections in the list"""
    bl_idname = "collanim.select_none_collections"
    bl_label = "Select None" 
    bl_description = "Deselect all collections in the list"
    
    def execute(self, context):
        props = context.scene.collection_animator_props
        for item in props.collection_instances:
            item.selected = False
        return {'FINISHED'}


# Registration
classes = (
    CollectionInstanceItem,
    CollectionAnimatorProperties,
    COLLANIM_UL_collection_list,
    COLLANIM_OT_scan_target_file,
    COLLANIM_OT_apply_animation,
    COLLANIM_OT_select_all_collections,
    COLLANIM_OT_select_none_collections,
    COLLANIM_PT_main_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.collection_animator_props = bpy.props.PointerProperty(
        type=CollectionAnimatorProperties
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.collection_animator_props


if __name__ == "__main__":
    register()
