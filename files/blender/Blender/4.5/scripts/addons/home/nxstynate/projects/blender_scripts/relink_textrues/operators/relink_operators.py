import bpy
import os

class CheckMissingTexturesOperator(bpy.types.Operator):
    bl_idname = "relink.check_missing_textures"
    bl_label = "Check Missing Textures"
    bl_description = "Checks the current Blender file for missing image textures."

    def execute(self, context):
        scene = context.scene
        props = scene.relink_textures_props

        missing_count = 0
        missing_list = []

        for image in bpy.data.images:
            if image.source == 'FILE' and not image.has_data:
                missing_count += 1
                missing_list.append(image.name)

        props.missing_textures_count = missing_count
        props.missing_textures_list = ", ".join(missing_list)
        props.feedback_message = f"Found {missing_count} missing textures."

        self.report({'INFO'}, props.feedback_message)
        return {'FINISHED'}

class RelinkMissingTexturesOperator(bpy.types.Operator):
    bl_idname = "relink.relink_missing_textures"
    bl_label = "Relink Missing Textures"
    bl_description = "Scans a specified folder and relinks missing textures."

    def execute(self, context):
        scene = context.scene
        props = scene.relink_textures_props

        search_path = props.search_path
        if not search_path or not os.path.isdir(search_path):
            self.report({'ERROR'}, "Please select a valid search directory.")
            return {'CANCELLED'}

        props.feedback_message = "Starting relink process..."
        props.progress_value = 0.0

        missing_images = [img for img in bpy.data.images if img.source == 'FILE' and not img.has_data]
        total_missing = len(missing_images)

        if total_missing == 0:
            props.feedback_message = "No missing textures to relink."
            self.report({'INFO'}, props.feedback_message)
            return {'FINISHED'}

        relinked_count = 0
        for i, image in enumerate(missing_images):
            original_filename = os.path.basename(image.filepath_raw)
            found = False
            for root, _, files in os.walk(search_path):
                props.feedback_message = f"Searching: {root}"
                context.window.tag_redraw()
                if original_filename in files:
                    new_filepath = os.path.join(root, original_filename)
                    try:
                        image.filepath = new_filepath
                        image.reload()
                        relinked_count += 1
                        found = True
                        props.feedback_message = f"Relinked: {original_filename}"
                        break
                    except Exception as e:
                        self.report({'WARNING'}, f"Failed to relink {original_filename}: {e}")
            
            if not found:
                props.feedback_message = f"Could not find: {original_filename}"

            props.progress_value = (i + 1) / total_missing * 100
            context.window.tag_redraw()

        props.feedback_message = f"Relinking complete. Relinked {relinked_count} of {total_missing} missing textures."
        props.missing_textures_count = total_missing - relinked_count
        
        # Update the missing_textures_list after relinking
        updated_missing_list = [img.name for img in bpy.data.images if img.source == 'FILE' and not img.has_data]
        props.missing_textures_list = ", ".join(updated_missing_list)

        self.report({'INFO'}, props.feedback_message)
        return {'FINISHED'}
