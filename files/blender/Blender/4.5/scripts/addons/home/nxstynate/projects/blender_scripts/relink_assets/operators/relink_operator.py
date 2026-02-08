
import bpy
import os

class RelinkOperator(bpy.types.Operator):
    """Recursively finds and relinks missing texture files."""
    bl_idname = "object.relink_textures"
    bl_label = "Relink Missing Textures"

    _timer = None
    _missing_textures = []
    _texture_map = {}
    _total_textures = 0
    _processed_textures = 0

    def modal(self, context, event):
        props = context.scene.relink_assets_props

        if event.type == 'TIMER':
            if not self._missing_textures:
                self.finish(context)
                return {'FINISHED'}

            texture = self._missing_textures.pop(0)
            self._processed_textures += 1
            
            if texture.image:
                filename = os.path.basename(texture.image.filepath)
                props.feedback_message = f"Searching for: {filename}"

                if filename in self._texture_map:
                    new_path = self._texture_map[filename]
                    texture.image.filepath = new_path
                    texture.image.reload()
                    props.feedback_message = f"Relinked: {filename}"
                else:
                    props.feedback_message = f"Not found: {filename}"
            
            props.progress = int((self._processed_textures / self._total_textures) * 100)
            return {'PASS_THROUGH'}

        elif event.type == 'ESC':
            self.cancel(context)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        props = context.scene.relink_assets_props
        search_path = bpy.path.abspath(props.search_path)

        if not os.path.isdir(search_path):
            self.report({'ERROR'}, "Please select a valid search directory.")
            return {'CANCELLED'}

        self._missing_textures = []
        for image in bpy.data.images:
            if image.source == 'FILE' and not os.path.exists(image.filepath):
                self._missing_textures.append(image)

        self._total_textures = len(self._missing_textures)
        self._processed_textures = 0
        props.progress = 0

        self._texture_map = {}
        for dirpath, _, filenames in os.walk(search_path):
            for filename in filenames:
                self._texture_map[filename] = os.path.join(dirpath, filename)
        
        if not self._missing_textures:
            props.feedback_message = "No missing textures found."
            return {'FINISHED'}

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def finish(self, context):
        props = context.scene.relink_assets_props
        props.feedback_message = f"Relinked {self._total_textures - len(self._missing_textures)} of {self._total_textures} missing textures."
        props.progress = 100
        self.cancel(context)

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)


def register():
    bpy.utils.register_class(RelinkOperator)

def unregister():
    bpy.utils.unregister_class(RelinkOperator)
