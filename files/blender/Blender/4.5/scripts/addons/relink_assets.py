bl_info = {
    "name": "Relink Assets",
    "author": "NXSTYNATE",
    "version": (0, 5, 0),
    "blender": (4, 5, 0),
    "location": "View3D > N-Panel > Relink Assets",
    "description": "Scan for missing assets in the current file",
    "category": "Scene",
}

import bpy
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from bpy.types import Panel, Operator, PropertyGroup
from bpy.props import StringProperty, CollectionProperty, BoolProperty

class MissingAssetItem(PropertyGroup):
    """Property group to store missing asset information"""
    name: StringProperty(name="Name")
    type: StringProperty(name="Type")
    path: StringProperty(name="Path")

class MISSING_ASSETS_OT_scan(Operator):
    """Scan for missing assets in the current file"""
    bl_idname = "missing_assets.scan"
    bl_label = "Scan For Missing Assets"
    bl_description = "Scan the current file for missing external assets"
    
    def execute(self, context):
        # Clear previous results
        context.scene.missing_assets_list.clear()
        
        missing_count = 0
        
        # Check for missing images (with filter)
        if context.scene.missing_assets_filter_images:
            for img in bpy.data.images:
                if img.source in {'FILE', 'SEQUENCE', 'MOVIE'}:
                    if not img.has_data:
                        item = context.scene.missing_assets_list.add()
                        item.name = img.name
                        item.type = "Image"
                        item.path = img.filepath if img.filepath else "No path"
                        missing_count += 1
        
        # Check for missing libraries (with filter)
        if context.scene.missing_assets_filter_libraries:
            for lib in bpy.data.libraries:
                if not lib.filepath or not bpy.path.abspath(lib.filepath):
                    item = context.scene.missing_assets_list.add()
                    item.name = lib.name
                    item.type = "Library"
                    item.path = lib.filepath if lib.filepath else "No path"
                    missing_count += 1
        
        # Check for missing sound files (with filter)
        if context.scene.missing_assets_filter_sounds:
            for sound in bpy.data.sounds:
                if sound.filepath and not sound.packed_file:
                    try:
                        # Try to access the sound data to check if file exists
                        sound.filepath
                    except:
                        item = context.scene.missing_assets_list.add()
                        item.name = sound.name
                        item.type = "Sound"
                        item.path = sound.filepath if sound.filepath else "No path"
                        missing_count += 1
        
        # Check for missing cache files (with filter)
        if context.scene.missing_assets_filter_caches:
            for obj in bpy.data.objects:
                # Check modifiers
                for mod in obj.modifiers:
                    # Mesh Cache modifier
                    if mod.type == 'MESH_CACHE' and mod.filepath:
                        try:
                            with open(bpy.path.abspath(mod.filepath), 'r'):
                                pass
                        except:
                            item = context.scene.missing_assets_list.add()
                            item.name = f"{obj.name} - {mod.name}"
                            item.type = "Mesh Cache"
                            item.path = mod.filepath
                            missing_count += 1
                    
                    # Ocean modifier
                    elif mod.type == 'OCEAN' and mod.use_foam and mod.foam_layer_name:
                        if mod.filepath:
                            try:
                                with open(bpy.path.abspath(mod.filepath), 'r'):
                                    pass
                            except:
                                item = context.scene.missing_assets_list.add()
                                item.name = f"{obj.name} - {mod.name}"
                                item.type = "Ocean Cache"
                                item.path = mod.filepath
                                missing_count += 1
        
        # Update the count
        context.scene.missing_assets_count = missing_count
        
        # Don't automatically expand the results
        # context.scene.missing_assets_show_details = True  # Removed this line
        
        if missing_count == 0:
            self.report({'INFO'}, "No missing assets found!")
        else:
            self.report({'WARNING'}, f"Found {missing_count} missing assets")
        
        return {'FINISHED'}

class MISSING_ASSETS_OT_clear_directory(Operator):
    """Clear the directory path"""
    bl_idname = "missing_assets.clear_directory"
    bl_label = "Clear Directory"
    bl_description = "Clear the directory path"
    
    def execute(self, context):
        context.scene.missing_assets_search_directory = ""
        return {'FINISHED'}

class MISSING_ASSETS_OT_remove_missing(Operator):
    """Remove references to missing assets"""
    bl_idname = "missing_assets.remove_missing"
    bl_label = "Remove Missing"
    bl_description = "Remove references to missing assets (only images for safety)"
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)
    
    def execute(self, context):
        removed_count = 0
        
        # Only remove missing images (safest option)
        if context.scene.missing_assets_filter_images:
            images_to_remove = []
            for img in bpy.data.images:
                if img.source in {'FILE', 'SEQUENCE', 'MOVIE'} and not img.has_data:
                    images_to_remove.append(img)
            
            for img in images_to_remove:
                bpy.data.images.remove(img)
                removed_count += 1
        
        self.report({'INFO'}, f"Removed {removed_count} missing image references")
        
        # Update the scan
        bpy.ops.missing_assets.scan()
        
        return {'FINISHED'}

class MISSING_ASSETS_OT_export_report(Operator):
    """Export a report of missing assets"""
    bl_idname = "missing_assets.export_report"
    bl_label = "Export Report"
    bl_description = "Export a text report of all missing assets"
    
    filepath: StringProperty(
        name="File Path",
        description="Path to save the report",
        default="missing_assets_report.txt",
        subtype='FILE_PATH'
    )
    
    filename_ext = ".txt"
    
    filter_glob: StringProperty(
        default="*.txt;*.csv",
        options={'HIDDEN'},
        maxlen=255,
    )
    
    file_format: bpy.props.EnumProperty(
        name="File Format",
        description="Choose the file format",
        items=[
            ('TXT', "Text (.txt)", "Export as text file"),
            ('CSV', "CSV (.csv)", "Export as CSV file"),
        ],
        default='TXT',
    )
    
    def invoke(self, context, event):
        self.filepath = "missing_assets_report.txt"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        # Ensure correct extension
        if self.file_format == 'CSV':
            if not self.filepath.endswith('.csv'):
                self.filepath = os.path.splitext(self.filepath)[0] + '.csv'
        else:
            if not self.filepath.endswith('.txt'):
                self.filepath = os.path.splitext(self.filepath)[0] + '.txt'
        
        try:
            if self.file_format == 'CSV':
                # Export as CSV
                import csv
                with open(self.filepath, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Asset Type', 'Asset Name', 'File Path'])
                    
                    for item in context.scene.missing_assets_list:
                        writer.writerow([item.type, item.name, item.path])
                
                self.report({'INFO'}, f"CSV report saved to {self.filepath}")
            else:
                # Export as TXT
                with open(self.filepath, 'w') as f:
                    f.write("Missing Assets Report\n")
                    f.write("=" * 50 + "\n")
                    f.write(f"Blend File: {bpy.data.filepath}\n")
                    import datetime
                    f.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Total Missing Assets: {context.scene.missing_assets_count}\n")
                    f.write("=" * 50 + "\n\n")
                    
                    # Group by type
                    by_type = {}
                    for item in context.scene.missing_assets_list:
                        if item.type not in by_type:
                            by_type[item.type] = []
                        by_type[item.type].append(item)
                    
                    # Write each type
                    for asset_type, items in by_type.items():
                        f.write(f"\n{asset_type} ({len(items)} items):\n")
                        f.write("-" * 30 + "\n")
                        for item in items:
                            f.write(f"  Name: {item.name}\n")
                            f.write(f"  Path: {item.path}\n")
                            f.write("\n")
                
                self.report({'INFO'}, f"Text report saved to {self.filepath}")
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save report: {str(e)}")
        
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "file_format")

class MISSING_ASSETS_OT_relink(Operator):
    """Relink missing assets by searching in the specified directory"""
    bl_idname = "missing_assets.relink"
    bl_label = "Relink Assets"
    bl_description = "Search for and relink missing assets"
    
    _timer = None
    _current_item = 0
    _items_to_process = []
    _relinked_count = 0
    _search_cache = {}
    _search_complete = False
    _executor = None
    
    @classmethod
    def poll(cls, context):
        # Always allow the operator to be called
        return True
    
    def build_file_cache(self, search_dir):
        """Build a cache of all files in the search directory using parallel processing"""
        file_cache = {}
        
        def scan_directory(root):
            local_cache = {}
            try:
                for filename in os.listdir(root):
                    filepath = os.path.join(root, filename)
                    if os.path.isfile(filepath):
                        # Store both exact and lowercase versions for case-insensitive matching
                        local_cache[filename] = filepath
                        local_cache[filename.lower()] = filepath
            except Exception as e:
                print(f"Error scanning {root}: {e}")
            return local_cache
        
        # Get all subdirectories
        all_dirs = [search_dir]
        for root, dirs, files in os.walk(search_dir):
            for d in dirs:
                all_dirs.append(os.path.join(root, d))
        
        # Use ThreadPoolExecutor for parallel directory scanning
        with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
            future_to_dir = {executor.submit(scan_directory, d): d for d in all_dirs}
            
            for future in as_completed(future_to_dir):
                try:
                    result = future.result()
                    file_cache.update(result)
                except Exception as e:
                    print(f"Error in parallel scan: {e}")
        
        return file_cache
    
    def modal(self, context, event):
        # Check if user wants to cancel
        if context.scene.missing_assets_is_searching and not context.scene.missing_assets_continue_search:
            self.cancel(context)
            return {'CANCELLED'}
        
        if event.type == 'TIMER':
            # Check if cache building is complete
            if not self._search_complete and self._cache_future.done():
                try:
                    self._search_cache = self._cache_future.result()
                    self._search_complete = True
                    context.scene.missing_assets_status = "Searching for assets..."
                    print(f"File cache built: {len(self._search_cache)} files found")
                except Exception as e:
                    self.report({'ERROR'}, f"Error building cache: {str(e)}")
                    self.cancel(context)
                    return {'CANCELLED'}
            
            # Process items only after cache is ready
            if self._search_complete and self._current_item < len(self._items_to_process):
                # Process one item
                item = self._items_to_process[self._current_item]
                context.scene.missing_assets_status = f"Searching for: {item['name']}"
                
                # Try to find and relink the asset
                if self.relink_asset_fast(context, item):
                    self._relinked_count += 1
                
                self._current_item += 1
                
                # Update progress AFTER incrementing (so it reaches 100%)
                context.scene.missing_assets_progress = self._current_item / len(self._items_to_process)
                
                # Force UI update
                for area in context.screen.areas:
                    area.tag_redraw()
                
                return {'RUNNING_MODAL'}
            elif self._search_complete:
                # Finished processing
                self.finish(context)
                return {'FINISHED'}
            else:
                # Still building cache
                return {'RUNNING_MODAL'}
        
        return {'PASS_THROUGH'}
    
    def relink_asset_fast(self, context, item):
        """Fast relink using pre-built cache"""
        # Get the filename from the path
        filename = os.path.basename(item['path'])
        if not filename or filename == "No path":
            return False
        
        # Try exact match first, then case-insensitive
        new_path = self._search_cache.get(filename) or self._search_cache.get(filename.lower())
        
        if not new_path:
            print(f"File not found in cache: {filename}")
            return False
        
        # Relink based on asset type
        if item['type'] == "Image":
            for img in bpy.data.images:
                if img.name == item['name']:
                    old_path = img.filepath
                    img.filepath = new_path
                    try:
                        img.reload()
                        img.update()
                        if img.has_data:
                            print(f"Successfully relinked: {item['name']}")
                            return True
                        else:
                            img.filepath = old_path
                    except Exception as e:
                        print(f"Error relinking {item['name']}: {str(e)}")
                        img.filepath = old_path
                    return False
        
        elif item['type'] == "Library":
            for lib in bpy.data.libraries:
                if lib.name == item['name']:
                    old_path = lib.filepath
                    lib.filepath = new_path
                    try:
                        lib.reload()
                        print(f"Successfully relinked library: {item['name']}")
                        return True
                    except Exception as e:
                        print(f"Error relinking library {item['name']}: {str(e)}")
                        lib.filepath = old_path
                    return False
        
        elif item['type'] == "Sound":
            for sound in bpy.data.sounds:
                if sound.name == item['name']:
                    sound.filepath = new_path
                    sound.update_tag()
                    print(f"Successfully relinked sound: {item['name']}")
                    return True
        
        elif item['type'] == "Mesh Cache":
            obj_mod = item['name'].split(' - ')
            if len(obj_mod) == 2:
                obj_name, mod_name = obj_mod
                if obj_name in bpy.data.objects:
                    obj = bpy.data.objects[obj_name]
                    for mod in obj.modifiers:
                        if mod.name == mod_name and mod.type == 'MESH_CACHE':
                            mod.filepath = new_path
                            obj.update_tag()
                            print(f"Successfully relinked mesh cache: {item['name']}")
                            return True
        
        return False
    
    def execute(self, context):
        # Check if already searching - if so, stop the search
        if context.scene.missing_assets_is_searching:
            context.scene.missing_assets_continue_search = False
            return {'FINISHED'}
        
        # Clear status
        context.scene.missing_assets_status = "Building file cache..."
        
        # Prepare list of items to process with filters
        self._items_to_process = []
        for item in context.scene.missing_assets_list:
            # Apply filters
            if item.type == "Image" and not context.scene.missing_assets_filter_images:
                continue
            if item.type == "Library" and not context.scene.missing_assets_filter_libraries:
                continue
            if item.type == "Sound" and not context.scene.missing_assets_filter_sounds:
                continue
            if item.type in ["Mesh Cache", "Ocean Cache"] and not context.scene.missing_assets_filter_caches:
                continue
                
            self._items_to_process.append({
                'name': item.name,
                'type': item.type,
                'path': item.path
            })
        
        if not self._items_to_process:
            self.report({'INFO'}, "No missing assets to relink (check filters)")
            context.scene.missing_assets_status = "No assets to relink"
            return {'FINISHED'}
        
        if not context.scene.missing_assets_search_directory:
            self.report({'ERROR'}, "Please specify a search directory")
            context.scene.missing_assets_status = "Error: No search directory specified"
            return {'CANCELLED'}
        
        # Set searching flags
        context.scene.missing_assets_is_searching = True
        context.scene.missing_assets_continue_search = True
        context.scene.missing_assets_progress = 0.0
        
        # Reset counters
        self._current_item = 0
        self._relinked_count = 0
        self._search_complete = False
        
        # Start building file cache in background
        search_dir = context.scene.missing_assets_search_directory
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._cache_future = self._executor.submit(self.build_file_cache, search_dir)
        
        # Add timer
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}
    
    def finish(self, context):
        # Remove timer
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        
        # Clear searching flags
        context.scene.missing_assets_is_searching = False
        context.scene.missing_assets_continue_search = False
        context.scene.missing_assets_progress = 0.0
        
        # Update status
        context.scene.missing_assets_status = f"Completed: Relinked {self._relinked_count} assets"
        
        # Report results
        self.report({'INFO'}, f"Relinked {self._relinked_count} assets")
        
        # Force UI update one more time
        for area in context.screen.areas:
            area.tag_redraw()
        
        # Force a scene update before rescanning
        bpy.context.view_layer.update()
        
        # Automatically run scan to update the list
        bpy.ops.missing_assets.scan()
    
    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        
        # Clean up executor
        if self._executor:
            self._executor.shutdown(wait=False)
        
        # Clear searching flags
        context.scene.missing_assets_is_searching = False
        context.scene.missing_assets_continue_search = False
        context.scene.missing_assets_progress = 0.0
        
        context.scene.missing_assets_status = f"Stopped: Relinked {self._relinked_count} assets"
        self.report({'INFO'}, f"Search stopped. Relinked {self._relinked_count} assets before stopping.")

class MISSING_ASSETS_PT_panel(Panel):
    """Panel in the N-Panel for missing assets scanner"""
    bl_label = "Relink Asssets"
    bl_idname = "MISSING_ASSETS_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Relink Assets"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Directory input box
        box = layout.box()
        row = box.row(align=True)
        row.label(text="Search Directory:", icon='FILE_FOLDER')
        
        # Directory path input and clear button
        row = box.row(align=True)
        row.prop(scene, "missing_assets_search_directory", text="")
        row.operator("missing_assets.clear_directory", text="", icon='X', emboss=True)
        
        layout.separator()
        
        # Filter options box
        filter_box = layout.box()
        filter_box.label(text="Filter Options:", icon='FILTER')
        
        row = filter_box.row(align=True)
        row.prop(scene, "missing_assets_filter_images", text="Images")
        row.prop(scene, "missing_assets_filter_libraries", text="Libraries")
        
        row = filter_box.row(align=True)
        row.prop(scene, "missing_assets_filter_sounds", text="Sounds")
        row.prop(scene, "missing_assets_filter_caches", text="Caches")
        
        layout.separator()
        
        # Scan button
        row = layout.row()
        row.scale_y = 1.5
        row.operator("missing_assets.scan", icon='VIEWZOOM')
        
        # Results box with collapsible header
        box = layout.box()
        
        # Header row with expand/collapse toggle
        row = box.row()
        
        # Toggle expand/collapse
        icon = 'DOWNARROW_HLT' if scene.missing_assets_show_details else 'RIGHTARROW'
        row.prop(scene, "missing_assets_show_details", 
                icon=icon, text="", emboss=False)
        
        # Asset count
        if scene.missing_assets_count > 0:
            row.label(text=f"Missing Assets: {scene.missing_assets_count}", icon='ERROR')
        else:
            row.label(text="Missing Assets: 0", icon='CHECKMARK')
        
        # Show detailed list only if expanded
        if scene.missing_assets_show_details:
            if len(scene.missing_assets_list) > 0:
                col = box.column(align=True)
                
                for item in scene.missing_assets_list:
                    # Create a sub-box for each missing asset
                    asset_box = col.box()
                    asset_box.scale_y = 0.8
                    
                    # Asset name and type
                    row = asset_box.row()
                    row.label(text=item.name, icon='DOT')
                    row.label(text=f"[{item.type}]")
                    
                    # Asset path
                    row = asset_box.row()
                    row.scale_y = 0.7
                    row.label(text=f"Path: {item.path}")
                    
                    col.separator(factor=0.5)
            else:
                box.label(text="No scan performed yet or no missing assets found", icon='INFO')
        
        # Relink section - ALWAYS VISIBLE AT THE BOTTOM
        layout.separator()
        
        # Relink button - changes to Stop when searching
        row = layout.row()
        row.scale_y = 1.2
        if scene.missing_assets_is_searching:
            row.operator("missing_assets.relink", text="Stop", icon='CANCEL')
        else:
            row.operator("missing_assets.relink", text="Relink Assets", icon='LINK_BLEND')
        
        # Status box
        status_box = layout.box()
        status_box.scale_y = 0.8
        
        # Show progress bar when searching, otherwise show status text
        if scene.missing_assets_is_searching:
            # Progress bar with percentage and current item
            percent = int(scene.missing_assets_progress * 100)
            status_box.progress(
                factor=scene.missing_assets_progress,
                type="BAR",
                text=f"{scene.missing_assets_status} - {percent}%"
            )
        else:
            # Normal status display
            row = status_box.row()
            row.label(text="Status:", icon='INFO')
            row = status_box.row()
            row.label(text=scene.missing_assets_status)
        
        # Batch operations box
        layout.separator()
        
        batch_box = layout.box()
        batch_box.label(text="Batch Operations:", icon='MODIFIER')
        
        row = batch_box.row(align=True)
        row.operator("missing_assets.remove_missing", icon='X')
        row.operator("missing_assets.export_report", icon='TEXT')

# Registration
classes = [
    MissingAssetItem,
    MISSING_ASSETS_OT_scan,
    MISSING_ASSETS_OT_clear_directory,
    MISSING_ASSETS_OT_remove_missing,
    MISSING_ASSETS_OT_export_report,
    MISSING_ASSETS_OT_relink,
    MISSING_ASSETS_PT_panel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Add properties to scene
    bpy.types.Scene.missing_assets_list = CollectionProperty(type=MissingAssetItem)
    bpy.types.Scene.missing_assets_count = bpy.props.IntProperty(default=0)
    bpy.types.Scene.missing_assets_show_details = bpy.props.BoolProperty(
        name="Show Details",
        description="Show/hide detailed missing assets list",
        default=True
    )
    bpy.types.Scene.missing_assets_search_directory = StringProperty(
        name="Directory",
        description="Directory to search for missing assets",
        default="",
        subtype='DIR_PATH'
    )
    bpy.types.Scene.missing_assets_status = StringProperty(
        name="Status",
        description="Current status of the relink operation",
        default="Ready"
    )
    bpy.types.Scene.missing_assets_is_searching = bpy.props.BoolProperty(
        name="Is Searching",
        description="Whether a search is currently in progress",
        default=False
    )
    bpy.types.Scene.missing_assets_continue_search = bpy.props.BoolProperty(
        name="Continue Search",
        description="Flag to control search continuation",
        default=False
    )
    bpy.types.Scene.missing_assets_progress = bpy.props.FloatProperty(
        name="Progress",
        description="Search progress from 0.0 to 1.0",
        default=0.0,
        min=0.0,
        max=1.0
    )
    
    # Filter properties
    bpy.types.Scene.missing_assets_filter_images = BoolProperty(
        name="Images",
        description="Include images in scan and relink",
        default=True
    )
    bpy.types.Scene.missing_assets_filter_libraries = BoolProperty(
        name="Libraries",
        description="Include libraries in scan and relink",
        default=True
    )
    bpy.types.Scene.missing_assets_filter_sounds = BoolProperty(
        name="Sounds",
        description="Include sounds in scan and relink",
        default=True
    )
    bpy.types.Scene.missing_assets_filter_caches = BoolProperty(
        name="Caches",
        description="Include cache files in scan and relink",
        default=True
    )

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    
    # Remove properties from scene
    del bpy.types.Scene.missing_assets_list
    del bpy.types.Scene.missing_assets_count
    del bpy.types.Scene.missing_assets_show_details
    del bpy.types.Scene.missing_assets_search_directory
    del bpy.types.Scene.missing_assets_status
    del bpy.types.Scene.missing_assets_is_searching
    del bpy.types.Scene.missing_assets_continue_search
    del bpy.types.Scene.missing_assets_progress
    
    # Remove filter properties
    del bpy.types.Scene.missing_assets_filter_images
    del bpy.types.Scene.missing_assets_filter_libraries
    del bpy.types.Scene.missing_assets_filter_sounds
    del bpy.types.Scene.missing_assets_filter_caches

if __name__ == "__main__":
    register()
