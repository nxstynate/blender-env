import bpy
import os
import tempfile
import subprocess
import json
from bpy.props import StringProperty, IntProperty, BoolProperty
import time
import platform
from .. import ADDON_MODULE_NAME
from ..utils import logger
from ..utils.blender_compat import get_cycles_compute_device_type

# Global variable to store render info
_render_info = {
    'filepath': None,
    'temp_dir': None,
    'temp_blend': None,
    'script_path': None
}

class LIGHTW_OT_Render360HDRI(bpy.types.Operator):
    """Save a 360° HDRI image of the current scene, capturing all lighting and world settings at the specified resolution"""
    bl_idname = "lightwrangler.render_360_hdri"
    bl_label = "Render 360 HDRI"

    filepath: StringProperty(subtype='FILE_PATH', default="")
    resolution_x: IntProperty(name="Width", default=2048)  # Default to 2K width
    resolution_y: IntProperty(name="Height", default=1024)  # Default to 2K height
    has_emissive_objects: BoolProperty(default=False, options={'SKIP_SAVE'})
    is_file_selected: BoolProperty(default=False, options={'SKIP_SAVE'})
    
    # Add modal properties
    _timer = None
    _process = None
    _start_time = 0

    def modal(self, context, event):
        if event.type == 'TIMER':
            logger.debug("\n=== MODAL UPDATE ===")
            if not self._process:
                logger.debug("Process not found")
                return {'FINISHED'}
                
            # Check if process is still running
            poll_result = self._process.poll()
            logger.debug(f"Process poll result: {poll_result}")
            
            if poll_result is not None:
                # Process finished
                logger.debug(f"Process finished with return code: {poll_result}")
                try:
                    remaining_stdout, remaining_stderr = self._process.communicate()
                    logger.debug("Successfully communicated with finished process")
                    
                    # Print any remaining output
                    if remaining_stdout:
                        logger.debug("Final stdout output:")
                        for line in remaining_stdout.splitlines():
                            logger.debug(f"Render process: {line.strip()}")
                    else:
                        logger.debug("No stdout output")
                        
                    if remaining_stderr:
                        logger.debug("Final stderr output:")
                        for line in remaining_stderr.splitlines():
                            logger.info(f"Render error: {line.strip()}")
                    else:
                        logger.debug("No stderr output")
                except Exception as e:
                    logger.error(f"Error during final communication: {str(e)}")
                
                # Get info from class variable
                render_info = LIGHTW_OT_Render360HDRI._render_info
                logger.debug(f"Render info: {render_info}")
                
                # Check if output file exists
                if os.path.exists(render_info['filepath']):
                    logger.debug(f"Output file exists: {render_info['filepath']}")
                    logger.debug(f"File size: {os.path.getsize(render_info['filepath'])} bytes")
                else:
                    logger.debug(f"Output file does not exist: {render_info['filepath']}")
                
                # Cleanup
                try:
                    os.remove(render_info['script_path'])
                    logger.debug("Removed script file")
                    os.remove(render_info['temp_blend'])
                    logger.debug("Removed temp blend file")
                    os.rmdir(render_info['temp_dir'])
                    logger.debug("Removed temp directory")
                except Exception as e:
                    logger.error(f"Cleanup failed: {str(e)}")
                
                # Remove timer
                try:
                    context.window_manager.event_timer_remove(self._timer)
                    logger.debug("Removed modal timer")
                except Exception as e:
                    logger.error(f"Failed to remove timer: {str(e)}")
                
                # Clear status text
                context.workspace.status_text_set(None)
                
                # Show completion message
                if self._process.returncode == 0:
                    logger.debug(f"Render completed successfully: {render_info['filepath']}")
                    self.report({'INFO'}, f"HDRI Rendered: {render_info['filepath']}")
                else:
                    logger.debug(f"Render failed with return code: {self._process.returncode}")
                    self.report({'ERROR'}, "HDRI Render failed")
                
                # Clear render info and process
                LIGHTW_OT_Render360HDRI._render_info = {}
                self._process = None
                logger.debug("=== RENDER PROCESS COMPLETE ===\n")
                
                return {'FINISHED'}
            
            # Process still running - read output non-blocking
            logger.debug("Process still running, attempting to read output")
            if platform.system() != 'Windows':
                # Unix systems - use non-blocking IO
                try:
                    while True:
                        line = self._process.stdout.readline()
                        if not line:
                            break
                        logger.debug(f"Render process: {line.strip()}")
                except IOError as e:
                    logger.error(f"IOError reading stdout: {str(e)}")
                
                try:
                    while True:
                        line = self._process.stderr.readline()
                        if not line:
                            break
                        logger.debug(f"Render error: {line.strip()}")
                except IOError as e:
                    logger.error(f"IOError reading stderr: {str(e)}")
            else:
                # Windows - use communicate with timeout
                try:
                    stdout, stderr = self._process.communicate(timeout=0.1)
                    if stdout:
                        logger.debug(f"Render process: {stdout.strip()}")
                    if stderr:
                        logger.info(f"Render error: {stderr.strip()}")
                except subprocess.TimeoutExpired:
                    logger.debug("Windows communicate timeout (expected)")
                except Exception as e:
                    logger.error(f"Windows subprocess error: {str(e)}")
            
            # Update status message
            elapsed_time = int(time.time() - self._start_time)
            context.workspace.status_text_set(f"Rendering HDRI... ({elapsed_time//60}m {elapsed_time%60}s)")
            logger.debug(f"Elapsed time: {elapsed_time} seconds")
            
            return {'PASS_THROUGH'}
        
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        prefs = context.preferences.addons[ADDON_MODULE_NAME].preferences
        default_directory = prefs.last_360_hdri_directory if hasattr(prefs, 'last_360_hdri_directory') and prefs.last_360_hdri_directory else os.path.join(os.path.expanduser("~"), "Pictures")
        
        if not os.path.exists(default_directory):
            default_directory = os.path.expanduser("~")

        resolution_map = {2048: "2K", 4096: "4K", 8192: "8K", 16384: "16K"}
        resolution_suffix = resolution_map.get(self.resolution_x, "2K")
        blend_name = bpy.path.basename(bpy.context.blend_data.filepath)
        project_name = os.path.splitext(blend_name)[0] if bpy.context.blend_data.filepath else "Untitled"
        filename = f"{project_name}_HDRI_{resolution_suffix}.exr"
        self.filepath = os.path.join(default_directory, filename)

        # Check for emissive objects
        self.has_emissive_objects = self.check_emissive_objects(context)

        if self.has_emissive_objects:
            # Show confirmation dialog
            return context.window_manager.invoke_props_dialog(self)
        else:
            # Proceed to file selection
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}

    def draw(self, context):
        if self.has_emissive_objects and not self.is_file_selected:
            layout = self.layout
            row = layout.row()
            row.alignment = 'LEFT'
            row.label(text="Warning: Emissive Objects Detected", icon='ERROR')
            
            layout.separator(factor=1.0)
            
            col = layout.column(align=True)
            col.scale_y = 0.85
            col.label(text="This scene contains emissive objects.")
            col.label(text="Rendering may take up to 20 minutes or longer,")
            col.label(text="depending on your output resolution.")
            col.label(text="The main Blender window will remain responsive.")
            
            layout.separator(factor=0.5)

    def check_emissive_objects(self, context):
        """Check if scene contains any emissive objects"""
        # Check each object in the scene for emissive materials
        for obj in context.scene.objects:
            if (obj.type == 'MESH' and 
                not obj.hide_render and 
                obj.visible_get() and 
                self.is_emission_object(obj)):
                return True  # Emissive object found

        return False  # No emissive objects detected

    def is_emission_object(self, obj):
        """Helper method to check if an object is emissive"""
        if obj.type == 'MESH' and obj.active_material:
            emission_nodes = self.get_emission_nodes(obj)
            for node in emission_nodes:
                if node.type == 'EMISSION' and node.inputs['Strength'].default_value > 0:
                    return True
                elif (node.type == 'BSDF_PRINCIPLED' and 
                      'Emission Strength' in node.inputs and 
                      node.inputs['Emission Strength'].default_value > 0):
                    return True
        return False

    def get_emission_nodes(self, obj):
        """Helper method to get emission nodes from an object"""
        emission_nodes = []
        if obj.active_material:
            for mat_slot in obj.material_slots:
                if mat_slot.material and mat_slot.material.node_tree:
                    emission_nodes.extend(self.get_emission_nodes_from_tree(mat_slot.material.node_tree))
        return emission_nodes

    def get_emission_nodes_from_tree(self, node_tree):
        """Helper method to get emission nodes from a node tree"""
        emission_nodes = []
        if node_tree is None or not hasattr(node_tree, 'nodes'):
            return emission_nodes
        for node in node_tree.nodes:
            if node.type in {'EMISSION', 'BSDF_PRINCIPLED'}:
                if node.type == 'EMISSION' or (node.type == 'BSDF_PRINCIPLED' and 'Emission Strength' in node.inputs):
                    emission_nodes.append(node)
            elif node.type == 'GROUP' and node.node_tree is not None:
                emission_nodes.extend(self.get_emission_nodes_from_tree(node.node_tree))
        return emission_nodes

    def execute(self, context):
        logger.debug("\n=== HDRI RENDER STARTING ===")
        logger.debug(f"Platform: {platform.system()}")
        
        if self.has_emissive_objects and not self.is_file_selected:
            logger.debug("Has emissive objects, showing file selector")
            self.is_file_selected = True
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}

        logger.debug(f"Output filepath: {self.filepath}")
        logger.debug(f"Resolution: {self.resolution_x}x{self.resolution_y}")

        # Get list of objects to render
        objects_to_render = []
        for obj in context.scene.objects:
            should_copy = False
            
            # Check for lights - must be visible
            if (obj.type == 'LIGHT' and 
                not obj.hide_render and obj.visible_get()):
                should_copy = True
                logger.debug(f"Found light to render: {obj.name}")
                
            # Check for emissive meshes - must be visible
            elif (obj.type == 'MESH' and 
                  not obj.hide_render and obj.visible_get()):
                if self.is_emission_object(obj):
                    should_copy = True
                    logger.debug(f"Found emissive mesh to render: {obj.name}")
            
            if should_copy:
                objects_to_render.append(obj.name)

        logger.debug(f"Total objects to render: {len(objects_to_render)}")

        # Create temporary directory
        try:
            temp_dir = tempfile.mkdtemp()
            logger.debug(f"Created temp dir: {temp_dir}")
        except Exception as e:
            logger.error(f"Failed to create temp dir: {str(e)}")
            self.report({'ERROR'}, "Failed to create temporary directory")
            return {'CANCELLED'}
        
        # Save current scene state
        temp_blend = os.path.join(temp_dir, "temp_scene.blend")
        try:
            bpy.ops.wm.save_as_mainfile(filepath=temp_blend, copy=True)
            logger.debug(f"Saved temp blend file: {temp_blend}")
        except Exception as e:
            logger.error(f"Failed to save temp blend: {str(e)}")
            self.report({'ERROR'}, "Failed to save temporary blend file")
            return {'CANCELLED'}
        
        # Generate Python script
        try:
            script_content = self.generate_render_script(
                blend_path=temp_blend,
                output_path=self.filepath,
                resolution_x=self.resolution_x,
                resolution_y=self.resolution_y,
                objects_to_render=objects_to_render
            )
            
            script_path = os.path.join(temp_dir, "render_hdri.py")
            with open(script_path, 'w') as f:
                f.write(script_content)
            logger.debug(f"Created render script: {script_path}")
        except Exception as e:
            logger.error(f"Failed to create render script: {str(e)}")
            self.report({'ERROR'}, "Failed to create render script")
            return {'CANCELLED'}
        
        # Store render info in class variable
        LIGHTW_OT_Render360HDRI._render_info = {
            'filepath': self.filepath,
            'temp_dir': temp_dir,
            'temp_blend': temp_blend,
            'script_path': script_path
        }
        logger.debug("Stored render info in class variable")
        
        # Launch subprocess with non-blocking IO
        try:
            blender_path = bpy.app.binary_path
            logger.debug(f"Using Blender path: {blender_path}")
            
            cmd = [blender_path, "--factory-startup", "-b", temp_blend, "--python", script_path]
            logger.debug(f"Command to execute: {' '.join(cmd)}")
            
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                start_new_session=True
            )
            logger.debug(f"Started subprocess with PID: {self._process.pid}")
            
            # Make pipes non-blocking on Unix systems only
            if platform.system() != 'Windows':
                logger.debug("Setting up non-blocking pipes for Unix")
                import fcntl
                for pipe in [self._process.stdout, self._process.stderr]:
                    fd = pipe.fileno()
                    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            else:
                logger.debug("Windows system - skipping non-blocking pipe setup")
            
        except Exception as e:
            logger.error(f"Failed to start subprocess: {str(e)}")
            self.report({'ERROR'}, "Failed to start render process")
            return {'CANCELLED'}
        
        # Start modal timer
        try:
            self._start_time = time.time()
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.1, window=context.window)
            wm.modal_handler_add(self)
            logger.debug("Started modal timer")
        except Exception as e:
            logger.error(f"Failed to start modal timer: {str(e)}")
            self.report({'ERROR'}, "Failed to start render monitoring")
            return {'CANCELLED'}
        
        context.workspace.status_text_set("Starting HDRI render...")
        logger.debug("=== HDRI RENDER PROCESS STARTED ===\n")
        
        return {'RUNNING_MODAL'}

    def generate_render_script(self, blend_path, output_path, resolution_x, resolution_y, objects_to_render):
        """Generates the Python script that will run in the subprocess"""
        # Convert paths to use forward slashes for cross-platform compatibility
        output_path = output_path.replace('\\', '/')
        blend_path = blend_path.replace('\\', '/')

        script = f'''
import bpy
import math
import os
import sys

# Define logger for script
class Logger:
    def debug(self, msg):
        print(msg)
    def error(self, msg):
        print(f"ERROR: {{msg}}")

logger = Logger()

def get_emission_nodes_from_tree(node_tree):
    emission_nodes = []
    if node_tree is None or not hasattr(node_tree, 'nodes'):
        return emission_nodes
    for node in node_tree.nodes:
        if node.type in {{'EMISSION', 'BSDF_PRINCIPLED'}}:
            if node.type == 'EMISSION' or (node.type == 'BSDF_PRINCIPLED' and 'Emission Strength' in node.inputs):
                emission_nodes.append(node)
        elif node.type == 'GROUP' and node.node_tree is not None:
            emission_nodes.extend(get_emission_nodes_from_tree(node.node_tree))
    return emission_nodes

def get_emission_nodes(obj):
    emission_nodes = []
    if obj.active_material:
        for mat_slot in obj.material_slots:
            if mat_slot.material and mat_slot.material.node_tree:
                emission_nodes.extend(get_emission_nodes_from_tree(mat_slot.material.node_tree))
    return emission_nodes

def main():
    logger.debug("=== Starting HDRI render process ===")
    logger.debug(f"Blender version: {{bpy.app.version_string}}")
    logger.debug(f"Python version: {{sys.version}}")

    # Load the original scene
    original_scene = bpy.context.scene
    objects_to_render = {objects_to_render}  # List of object names to render

    logger.debug(f"Original scene: {{original_scene.name}}")
    logger.debug(f"Objects to render: {{objects_to_render}}")
    
    # Create new scene for HDRI rendering
    hdri_scene = bpy.data.scenes.new("HDRIScene")
    bpy.context.window.scene = hdri_scene
    logger.debug("Created new HDRIScene")
    
    # Copy world settings if they exist
    if original_scene.world:
        hdri_scene.world = original_scene.world.copy()
        logger.debug(f"Copied world settings from {{original_scene.world.name}}")
    
    # Create 360 camera
    cam_data = bpy.data.cameras.new("360Camera")
    cam_obj = bpy.data.objects.new("360Camera", cam_data)
    cam_data.type = 'PANO'
    cam_data.panorama_type = 'EQUIRECTANGULAR'
    cam_data.clip_start = 0.00001
    cam_data.clip_end = 999999
    
    hdri_scene.collection.objects.link(cam_obj)
    hdri_scene.camera = cam_obj
    cam_obj.location = original_scene.cursor.location
    cam_obj.rotation_euler = (math.radians(90), 0, math.radians(-90))
    logger.debug("Created and set up 360 camera")
    
    # Copy only the objects we selected in main operator
    copied_objects = []
    for obj_name in objects_to_render:
        obj = original_scene.objects.get(obj_name)
        if not obj:
            logger.debug(f"Warning: Could not find object {{obj_name}}")
            continue
            
        # Create copy with data
        new_obj = obj.copy()
        if obj.data:
            new_obj.data = obj.data.copy()
            logger.debug(f"Copied data for {{obj.name}}")
            
        # Copy materials for meshes
        if obj.type == 'MESH':
            for i, mat_slot in enumerate(obj.material_slots):
                if mat_slot.material:
                    new_obj.material_slots[i].material = mat_slot.material.copy()
                    logger.debug(f"Copied material {{mat_slot.material.name}} for {{obj.name}}")
        
        # Special handling for lights
        if obj.type == 'LIGHT':
            # Ensure light data is properly copied
            new_obj.data = obj.data.copy()
            logger.debug(f"Copied light data for {{obj.name}}")
            new_obj.data.energy = obj.data.energy
            logger.debug(f"Copied light energy: {{obj.data.energy}}")
            if hasattr(obj.data, 'color'):
                new_obj.data.color = obj.data.color
                logger.debug(f"Copied light color: {{list(obj.data.color)}}")
        
        # Force the object to be visible in the new scene
        new_obj.hide_render = False
        new_obj.hide_viewport = False
        new_obj.visible_camera = True
        
        hdri_scene.collection.objects.link(new_obj)
        copied_objects.append(new_obj)
        logger.debug(f"Linked {{new_obj.name}} to HDRIScene")
    
    logger.debug(f"Copied objects summary:")
    logger.debug(f"Total objects copied: {{len(copied_objects)}}")
    logger.debug(f"Copied objects: {{[obj.name for obj in copied_objects]}}")
    logger.debug(f"Copied lights: {{[obj.name for obj in copied_objects if obj.type == 'LIGHT']}}")
    
    # Setup render settings
    hdri_scene.render.resolution_x = {resolution_x}
    hdri_scene.render.resolution_y = {resolution_y}
    hdri_scene.render.image_settings.file_format = 'OPEN_EXR'
    hdri_scene.render.image_settings.exr_codec = 'PXR24'
    hdri_scene.render.image_settings.color_mode = 'RGB'
    hdri_scene.render.image_settings.color_depth = '32'
    hdri_scene.render.engine = 'CYCLES'
    logger.debug("Set up render settings")
    
    # Cycles settings
    cycles = hdri_scene.cycles
    
    # Enable adaptive sampling if available
    if hasattr(cycles, 'use_adaptive_sampling'):
        cycles.use_adaptive_sampling = True
        logger.debug("Enabled adaptive sampling")
    
    # Basic cycles settings
    cycles.max_bounces = 1
    cycles.diffuse_bounces = 1
    cycles.glossy_bounces = 1
    cycles.transmission_bounces = 1
    cycles.volume_bounces = 0
    logger.debug("Set basic cycles settings")
    
    # Set sampling pattern if available
    if hasattr(cycles, 'sampling_pattern'):
        cycles.sampling_pattern = 'TABULATED_SOBOL'
        logger.debug("Set sampling pattern to TABULATED_SOBOL")
    
    # Determine compute device
    try:
        # Inline compute device type detection for subprocess
        prefs = bpy.context.preferences
        cycles_addon = prefs.addons.get('cycles')
        compute_device_type = None
        if cycles_addon and hasattr(cycles_addon, 'preferences'):
            compute_device_type = cycles_addon.preferences.compute_device_type

        logger.debug(f"Available compute device type: {{compute_device_type}}")

        if {resolution_x} in {{2048, 4096}}:
            if compute_device_type in {{'CUDA', 'OPTIX', 'METAL'}}:
                cycles.device = 'GPU'
                logger.debug(f"Using GPU ({{compute_device_type}}) for rendering")
            else:
                cycles.device = 'CPU'
                logger.debug("Using CPU for rendering (no compatible GPU found)")
        else:
            cycles.device = 'CPU'
            logger.debug("Using CPU for rendering (high resolution)")
    except Exception as e:
        cycles.device = 'CPU'
        logger.debug(f"Using CPU for rendering (error: {{str(e)}}")
    
    # Set samples based on scene content
    has_emissive = any(obj.type == 'MESH' for obj in hdri_scene.objects)
    if has_emissive:
        cycles.samples = 10
        cycles.use_denoising = True
        logger.debug("Set samples=10 and enabled denoising (emissive objects present)")
    else:
        cycles.samples = 1
        cycles.use_denoising = False
        logger.debug("Set samples=1 and disabled denoising (no emissive objects)")
    
    # Additional cycles settings
    # Clamp settings - removed in Blender 5.0
    if hasattr(cycles, 'clamp_direct'):
        cycles.clamp_direct = 0.0
        logger.debug("Set clamp_direct = 0.0")
    if hasattr(cycles, 'clamp_indirect'):
        cycles.clamp_indirect = 10000
        logger.debug("Set clamp_indirect = 10000")

    # Filter glossy - check if exists
    if hasattr(cycles, 'filter_glossy'):
        cycles.filter_glossy = 0.0
        logger.debug("Set filter_glossy = 0.0")

    if hasattr(cycles, 'use_auto_tile'):
        cycles.use_auto_tile = False
    logger.debug("Set additional cycles settings")
    
    # Set output path and render
    hdri_scene.render.filepath = '{output_path}'
    logger.debug(f"Output path set to: {{hdri_scene.render.filepath}}")
    logger.debug(f"Scene name for render: {{hdri_scene.name}}")
    logger.debug(f"Current context scene: {{bpy.context.scene.name}}")

    try:
        logger.debug("Calling bpy.ops.render.render()...")
        result = bpy.ops.render.render(write_still=True, scene=hdri_scene.name)
        logger.debug(f"Render operator returned: {{result}}")
    except Exception as e:
        logger.error(f"Render failed with exception: {{e}}")
        logger.error(f"Exception type: {{type(e).__name__}}")
        import traceback
        logger.error(f"Traceback: {{traceback.format_exc()}}")

    # Verify output file
    if os.path.exists('{output_path}'):
        logger.debug(f"SUCCESS: Output file created at {{'{output_path}'}}")
        logger.debug(f"File size: {{os.path.getsize('{output_path}')}} bytes")
    else:
        logger.error(f"FAILED: Output file NOT created at {{'{output_path}'}}")

    logger.debug("=== HDRI render process complete ===")

if __name__ == "__main__":
    main()
'''
        return script

class LIGHTW_OT_ShowRenderComplete(bpy.types.Operator):
    bl_idname = "lightw.show_render_complete"
    bl_label = "HDRI Render Complete"
    bl_description = "HDRI render completed successfully"
    
    filepath: StringProperty()
    
    def execute(self, context):
        self.report({'INFO'}, f"HDRI Rendered: {self.filepath}")
        return {'FINISHED'}

class LIGHTW_OT_ShowRenderError(bpy.types.Operator):
    bl_idname = "lightw.show_render_error"
    bl_label = "HDRI Render Failed"
    bl_description = "HDRI render failed"
    
    def execute(self, context):
        self.report({'ERROR'}, "HDRI Render failed. Check console for details.")
        return {'FINISHED'}

class LIGHTW_OT_RenderScrimHDRI(bpy.types.Operator):
    """Render the current scrim area light as a square HDRI image"""
    bl_idname = "lightwrangler.render_scrim_hdri"
    bl_label = "Render Scrim HDRI"

    filepath: StringProperty(subtype='FILE_PATH', default="")
    resolution: IntProperty(name="Resolution", default=1024)  # Square resolution
    
    # Add modal properties
    _timer = None
    _process = None
    _start_time = 0

    def modal(self, context, event):
        if event.type == 'TIMER':
            logger.debug("\n=== SCRIM HDRI MODAL UPDATE ===")
            if not self._process:
                logger.debug("Process not found")
                return {'FINISHED'}
                
            # Check if process is still running
            poll_result = self._process.poll()
            logger.debug(f"Process poll result: {poll_result}")
            
            if poll_result is not None:
                # Process finished
                logger.debug(f"Process finished with return code: {poll_result}")
                try:
                    remaining_stdout, remaining_stderr = self._process.communicate()
                    logger.debug("Successfully communicated with finished process")
                    
                    # Print any remaining output
                    if remaining_stdout:
                        logger.debug("Final stdout output:")
                        for line in remaining_stdout.splitlines():
                            logger.debug(f"Scrim render process: {line.strip()}")
                    else:
                        logger.debug("No stdout output")
                        
                    if remaining_stderr:
                        logger.debug("Final stderr output:")
                        for line in remaining_stderr.splitlines():
                            logger.info(f"Scrim render error: {line.strip()}")
                    else:
                        logger.debug("No stderr output")
                except Exception as e:
                    logger.error(f"Error during final communication: {str(e)}")
                
                # Get info from class variable
                render_info = LIGHTW_OT_RenderScrimHDRI._render_info
                logger.debug(f"Render info: {render_info}")
                
                # Check if output file exists
                if os.path.exists(render_info['filepath']):
                    logger.debug(f"Output file exists: {render_info['filepath']}")
                    logger.debug(f"File size: {os.path.getsize(render_info['filepath'])} bytes")
                else:
                    logger.debug(f"Output file does not exist: {render_info['filepath']}")
                
                # Cleanup
                try:
                    os.remove(render_info['script_path'])
                    logger.debug("Removed script file")
                    os.remove(render_info['temp_blend'])
                    logger.debug("Removed temp blend file")
                    os.rmdir(render_info['temp_dir'])
                    logger.debug("Removed temp directory")
                except Exception as e:
                    logger.error(f"Cleanup failed: {str(e)}")
                
                # Remove timer
                try:
                    context.window_manager.event_timer_remove(self._timer)
                    logger.debug("Removed modal timer")
                except Exception as e:
                    logger.error(f"Failed to remove timer: {str(e)}")
                
                # Clear status text
                context.workspace.status_text_set(None)
                
                # Show completion message
                if self._process.returncode == 0:
                    logger.debug(f"Scrim HDRI render completed successfully: {render_info['filepath']}")
                    self.report({'INFO'}, f"Scrim HDRI Rendered: {render_info['filepath']}")
                else:
                    logger.debug(f"Scrim HDRI render failed with return code: {self._process.returncode}")
                    self.report({'ERROR'}, "Scrim HDRI Render failed")
                
                # Clear render info and process
                LIGHTW_OT_RenderScrimHDRI._render_info = {}
                self._process = None
                logger.debug("=== SCRIM HDRI RENDER PROCESS COMPLETE ===\n")
                
                return {'FINISHED'}
            
            # Process still running - read output non-blocking
            logger.debug("Process still running, attempting to read output")
            if platform.system() != 'Windows':
                # Unix systems - use non-blocking IO
                try:
                    while True:
                        line = self._process.stdout.readline()
                        if not line:
                            break
                        logger.debug(f"Scrim render process: {line.strip()}")
                except IOError as e:
                    logger.error(f"IOError reading stdout: {str(e)}")
                
                try:
                    while True:
                        line = self._process.stderr.readline()
                        if not line:
                            break
                        logger.debug(f"Scrim render error: {line.strip()}")
                except IOError as e:
                    logger.error(f"IOError reading stderr: {str(e)}")
            else:
                # Windows - use communicate with timeout
                try:
                    stdout, stderr = self._process.communicate(timeout=0.1)
                    if stdout:
                        logger.debug(f"Scrim render process: {stdout.strip()}")
                    if stderr:
                        logger.info(f"Scrim render error: {stderr.strip()}")
                except subprocess.TimeoutExpired:
                    logger.debug("Windows communicate timeout (expected)")
                except Exception as e:
                    logger.error(f"Windows subprocess error: {str(e)}")
            
            # Update status message
            elapsed_time = int(time.time() - self._start_time)
            context.workspace.status_text_set(f"Rendering Scrim HDRI... ({elapsed_time//60}m {elapsed_time%60}s)")
            logger.debug(f"Elapsed time: {elapsed_time} seconds")
            
            return {'PASS_THROUGH'}
        
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        # Validate that we have a scrim area light selected
        if not self.validate_scrim_light(context):
            return {'CANCELLED'}
            
        prefs = context.preferences.addons[ADDON_MODULE_NAME].preferences
        default_directory = prefs.last_360_hdri_directory if hasattr(prefs, 'last_360_hdri_directory') and prefs.last_360_hdri_directory else os.path.join(os.path.expanduser("~"), "Pictures")
        
        if not os.path.exists(default_directory):
            default_directory = os.path.expanduser("~")

        # Generate filename based on light name and resolution
        light_obj = context.object
        light_name = light_obj.name.replace(" ", "_")
        filename = f"{light_name}_Scrim_HDRI_{self.resolution}.exr"
        self.filepath = os.path.join(default_directory, filename)

        # Proceed to file selection
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def validate_scrim_light(self, context):
        """Validate that the active object is a scrim area light"""
        if not context.object:
            self.report({'ERROR'}, "No active object selected")
            return False
            
        if context.object.type != 'LIGHT':
            self.report({'ERROR'}, "Active object is not a light")
            return False
            
        light_data = context.object.data
        if light_data.type != 'AREA':
            self.report({'ERROR'}, "Selected light is not an area light")
            return False
            
        # Check if it has scrim customization
        last_customization_key = f"last_customization_AREA"
        current_customization = context.object.get(last_customization_key, "Default")
        
        if current_customization != "Scrim":
            self.report({'ERROR'}, "Selected area light does not have Scrim customization applied")
            return False
            
        # Check if light is visible
        if context.object.hide_render or not context.object.visible_get():
            self.report({'ERROR'}, "Selected scrim light is hidden or not visible")
            return False
            
        return True

    def execute(self, context):
        logger.debug("\n=== SCRIM HDRI RENDER STARTING ===")
        logger.debug(f"Platform: {platform.system()}")
        
        # Validate again in execute
        if not self.validate_scrim_light(context):
            return {'CANCELLED'}

        light_obj = context.object
        logger.debug(f"Rendering scrim light: {light_obj.name}")
        logger.debug(f"Output filepath: {self.filepath}")
        logger.debug(f"Resolution: {self.resolution}x{self.resolution}")

        # Create temporary directory
        try:
            temp_dir = tempfile.mkdtemp()
            logger.debug(f"Created temp dir: {temp_dir}")
        except Exception as e:
            logger.error(f"Failed to create temp dir: {str(e)}")
            self.report({'ERROR'}, "Failed to create temporary directory")
            return {'CANCELLED'}
        
        # Save current scene state
        temp_blend = os.path.join(temp_dir, "temp_scrim_scene.blend")
        try:
            bpy.ops.wm.save_as_mainfile(filepath=temp_blend, copy=True)
            logger.debug(f"Saved temp blend file: {temp_blend}")
        except Exception as e:
            logger.error(f"Failed to save temp blend: {str(e)}")
            self.report({'ERROR'}, "Failed to save temporary blend file")
            return {'CANCELLED'}
        
        # Generate Python script
        try:
            logger.debug(f"Generating script with parameters:")
            logger.debug(f"  - blend_path: {temp_blend}")
            logger.debug(f"  - output_path: {self.filepath}")
            logger.debug(f"  - resolution: {self.resolution}")
            logger.debug(f"  - scrim_light_name: {light_obj.name}")
            logger.debug(f"  - scrim_light_name repr: {repr(light_obj.name)}")  # Shows escaped characters
            
            script_content = self.generate_scrim_render_script(
                blend_path=temp_blend,
                output_path=self.filepath,
                resolution=self.resolution,
                scrim_light_name=light_obj.name
            )
            
            logger.debug(f"Script content generated, length: {len(script_content)} characters")
            
            script_path = os.path.join(temp_dir, "render_scrim_hdri.py")
            logger.debug(f"Attempting to write script to: {script_path}")
            
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            logger.debug(f"Successfully wrote script file")
            logger.debug(f"Script file exists: {os.path.exists(script_path)}")
            logger.debug(f"Script file size: {os.path.getsize(script_path)} bytes")
            
        except IOError as e:
            logger.error(f"IOError writing script file: {str(e)}")
            logger.error(f"  - Error type: {type(e).__name__}")
            logger.error(f"  - Error errno: {e.errno if hasattr(e, 'errno') else 'N/A'}")
            self.report({'ERROR'}, f"Failed to write render script: {str(e)}")
            return {'CANCELLED'}
        except Exception as e:
            logger.error(f"Failed to create render script: {str(e)}")
            logger.error(f"  - Error type: {type(e).__name__}")
            logger.error(f"  - Full traceback:")
            import traceback
            logger.error(traceback.format_exc())
            self.report({'ERROR'}, "Failed to create render script")
            return {'CANCELLED'}
        
        # Store render info in class variable
        LIGHTW_OT_RenderScrimHDRI._render_info = {
            'filepath': self.filepath,
            'temp_dir': temp_dir,
            'temp_blend': temp_blend,
            'script_path': script_path
        }
        logger.debug("Stored render info in class variable")
        
        # Launch subprocess with non-blocking IO
        try:
            blender_path = bpy.app.binary_path
            logger.debug(f"Using Blender path: {blender_path}")
            
            cmd = [blender_path, "--factory-startup", "-b", temp_blend, "--python", script_path]
            logger.debug(f"Command to execute: {' '.join(cmd)}")
            
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                start_new_session=True
            )
            logger.debug(f"Started subprocess with PID: {self._process.pid}")
            
            # Make pipes non-blocking on Unix systems only
            if platform.system() != 'Windows':
                logger.debug("Setting up non-blocking pipes for Unix")
                import fcntl
                for pipe in [self._process.stdout, self._process.stderr]:
                    fd = pipe.fileno()
                    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            else:
                logger.debug("Windows system - skipping non-blocking pipe setup")
            
        except Exception as e:
            logger.error(f"Failed to start subprocess: {str(e)}")
            self.report({'ERROR'}, "Failed to start render process")
            return {'CANCELLED'}
        
        # Start modal timer
        try:
            self._start_time = time.time()
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.1, window=context.window)
            wm.modal_handler_add(self)
            logger.debug("Started modal timer")
        except Exception as e:
            logger.error(f"Failed to start modal timer: {str(e)}")
            self.report({'ERROR'}, "Failed to start render monitoring")
            return {'CANCELLED'}
        
        context.workspace.status_text_set("Starting Scrim HDRI render...")
        logger.debug("=== SCRIM HDRI RENDER PROCESS STARTED ===\n")
        
        return {'RUNNING_MODAL'}

    def generate_scrim_render_script(self, blend_path, output_path, resolution, scrim_light_name):
        """Generates the Python script that will run in the subprocess"""
        # Convert paths to use forward slashes for cross-platform compatibility
        output_path = output_path.replace('\\', '/')
        blend_path = blend_path.replace('\\', '/')

        script = f'''
import bpy
import math
import os
import sys
from mathutils import Vector

# Define logger for script
class Logger:
    def debug(self, msg):
        print(msg)
    def error(self, msg):
        print(f"ERROR: {{msg}}")

logger = Logger()

def main():
    logger.debug("=== Starting Scrim HDRI render process ===")
    logger.debug(f"Blender version: {{bpy.app.version_string}}")
    logger.debug(f"Python version: {{sys.version}}")

    # Load the original scene
    original_scene = bpy.context.scene
    scrim_light_name = "{scrim_light_name}"

    logger.debug(f"Original scene: {{original_scene.name}}")
    logger.debug(f"Target scrim light: {{scrim_light_name}}")
    
    # Find the scrim light
    scrim_light_obj = original_scene.objects.get(scrim_light_name)
    if not scrim_light_obj:
        logger.error(f"Could not find scrim light {scrim_light_name}")
        return
    
    logger.debug(f"Found scrim light: {{scrim_light_obj.name}}")
    
    # Create new scene for scrim rendering
    scrim_scene = bpy.data.scenes.new("ScrimRenderScene")
    bpy.context.window.scene = scrim_scene
    logger.debug("Created new ScrimRenderScene")
    
    # Copy scrim light to new scene
    new_scrim = scrim_light_obj.copy()
    new_scrim.data = scrim_light_obj.data.copy()
    
    # Copy node tree for the scrim light
    if scrim_light_obj.data.use_nodes and scrim_light_obj.data.node_tree:
        # Enable nodes on the new light data
        new_scrim.data.use_nodes = True
        
        # Clear existing nodes
        new_scrim.data.node_tree.nodes.clear()
        
        # Copy nodes from original
        for node in scrim_light_obj.data.node_tree.nodes:
            new_node = new_scrim.data.node_tree.nodes.new(type=node.bl_idname)
            
            # Copy node properties
            for attr in dir(node):
                if not attr.startswith('_') and attr not in ['bl_idname', 'type', 'inputs', 'outputs']:
                    try:
                        setattr(new_node, attr, getattr(node, attr))
                    except:
                        pass
            
            # Copy input values
            for i, input_socket in enumerate(node.inputs):
                if i < len(new_node.inputs):
                    try:
                        new_node.inputs[i].default_value = input_socket.default_value
                    except:
                        pass
            
            # Set location
            new_node.location = node.location
            new_node.name = node.name
        
        # Copy links
        for link in scrim_light_obj.data.node_tree.links:
            try:
                from_node = new_scrim.data.node_tree.nodes[link.from_node.name]
                to_node = new_scrim.data.node_tree.nodes[link.to_node.name]
                from_socket = from_node.outputs[link.from_socket.name]
                to_socket = to_node.inputs[link.to_socket.name]
                new_scrim.data.node_tree.links.new(from_socket, to_socket)
            except:
                pass
        
        logger.debug("Copied scrim light node tree")
    
    scrim_scene.collection.objects.link(new_scrim)
    logger.debug(f"Linked scrim light to new scene")
    
    # Get light dimensions
    light_size_x = new_scrim.data.size
    if new_scrim.data.shape == 'RECTANGLE':
        light_size_y = new_scrim.data.size_y
    else:
        light_size_y = light_size_x
    
    logger.debug(f"Light dimensions: {{light_size_x}} x {{light_size_y}}")
    
    # Create orthographic camera
    cam_data = bpy.data.cameras.new("ScrimCamera")
    cam_obj = bpy.data.objects.new("ScrimCamera", cam_data)
    cam_data.type = 'ORTHO'
    cam_data.clip_start = 0.001
    cam_data.clip_end = 1000
    
    # Set orthographic scale to frame the light exactly without padding
    max_dimension = max(light_size_x, light_size_y)
    cam_data.ortho_scale = max_dimension  # No padding - fill entire image
    
    scrim_scene.collection.objects.link(cam_obj)
    scrim_scene.camera = cam_obj
    
    # Position camera in front of the light
    # Calculate safe distance based on light size
    distance = max_dimension * 3
    
    # Get light's forward direction (area lights face along -Z in local space)
    light_forward = new_scrim.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    
    # Position camera in front of light
    cam_obj.location = new_scrim.location + light_forward * distance
    
    # Point camera at the light (same rotation as light but flipped)
    cam_obj.rotation_euler = new_scrim.rotation_euler.copy()
    cam_obj.rotation_euler.x += math.radians(180)  # Flip to face the light
    
    logger.debug(f"Camera positioned at: {{list(cam_obj.location)}}")
    logger.debug(f"Camera rotation: {{[math.degrees(r) for r in cam_obj.rotation_euler]}}")
    logger.debug(f"Orthographic scale: {{cam_data.ortho_scale}}")
    
    # Setup render settings
    scrim_scene.render.resolution_x = {resolution}
    scrim_scene.render.resolution_y = {resolution}  # Square format
    scrim_scene.render.image_settings.file_format = 'OPEN_EXR'
    scrim_scene.render.image_settings.exr_codec = 'PXR24'
    scrim_scene.render.image_settings.color_mode = 'RGB'
    scrim_scene.render.image_settings.color_depth = '32'
    scrim_scene.render.engine = 'CYCLES'
    logger.debug("Set up render settings")
    
    # Cycles settings optimized for light capture
    cycles = scrim_scene.cycles
    
    # Basic cycles settings - minimal bounces since we're capturing direct emission
    cycles.max_bounces = 1
    cycles.diffuse_bounces = 0
    cycles.glossy_bounces = 0
    cycles.transmission_bounces = 0
    cycles.volume_bounces = 0
    logger.debug("Set basic cycles settings")
    
    # Set sampling - minimal since we're capturing direct emission
    cycles.samples = 4  # Low samples for direct light capture
    cycles.use_denoising = False  # No denoising needed for clean light capture
    logger.debug("Set sampling settings")
    
    # Determine compute device
    try:
        # Inline compute device type detection for subprocess
        prefs = bpy.context.preferences
        cycles_addon = prefs.addons.get('cycles')
        compute_device_type = None
        if cycles_addon and hasattr(cycles_addon, 'preferences'):
            compute_device_type = cycles_addon.preferences.compute_device_type

        logger.debug(f"Available compute device type: {{compute_device_type}}")

        if {resolution} <= 2048:
            if compute_device_type in {{'CUDA', 'OPTIX', 'METAL'}}:
                cycles.device = 'GPU'
                logger.debug(f"Using GPU ({{compute_device_type}}) for rendering")
            else:
                cycles.device = 'CPU'
                logger.debug("Using CPU for rendering (no compatible GPU found)")
        else:
            cycles.device = 'CPU'
            logger.debug("Using CPU for rendering (high resolution)")
    except Exception as e:
        cycles.device = 'CPU'
        logger.debug(f"Using CPU for rendering (error: {{str(e)}}")
    
    # Additional cycles settings
    # Clamp settings - removed in Blender 5.0
    if hasattr(cycles, 'clamp_direct'):
        cycles.clamp_direct = 0.0
        logger.debug("Set clamp_direct = 0.0")
    if hasattr(cycles, 'clamp_indirect'):
        cycles.clamp_indirect = 0.0  # No clamping for HDRI capture
        logger.debug("Set clamp_indirect = 0.0")

    # Filter glossy - check if exists
    if hasattr(cycles, 'filter_glossy'):
        cycles.filter_glossy = 0.0
        logger.debug("Set filter_glossy = 0.0")

    if hasattr(cycles, 'use_auto_tile'):
        cycles.use_auto_tile = False
    logger.debug("Set additional cycles settings")
    
    # Set output path and render
    scrim_scene.render.filepath = '{output_path}'
    logger.debug(f"Output path set to: {{scrim_scene.render.filepath}}")
    logger.debug(f"Scene name for render: {{scrim_scene.name}}")
    logger.debug(f"Current context scene: {{bpy.context.scene.name}}")

    try:
        logger.debug("Calling bpy.ops.render.render()...")
        result = bpy.ops.render.render(write_still=True, scene=scrim_scene.name)
        logger.debug(f"Render operator returned: {{result}}")
    except Exception as e:
        logger.error(f"Render failed with exception: {{e}}")
        logger.error(f"Exception type: {{type(e).__name__}}")
        import traceback
        logger.error(f"Traceback: {{traceback.format_exc()}}")

    # Verify output file
    if os.path.exists('{output_path}'):
        logger.debug(f"SUCCESS: Output file created at {{'{output_path}'}}")
        logger.debug(f"File size: {{os.path.getsize('{output_path}')}} bytes")
    else:
        logger.error(f"FAILED: Output file NOT created at {{'{output_path}'}}")

    logger.debug("=== Scrim HDRI render process complete ===")

if __name__ == "__main__":
    main()
'''
        return script

# Registration
classes = (
    LIGHTW_OT_Render360HDRI,
    LIGHTW_OT_ShowRenderComplete,
    LIGHTW_OT_ShowRenderError,
    LIGHTW_OT_RenderScrimHDRI,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)