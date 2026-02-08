bl_info = {
    "name": "Inject Collections",
    "author": "NXSTYNATE",
    "version": (0, 5, 1),
    "blender": (4, 5, 0),
    "description": "Injects / pushes collections from a source file into target files.",
    "category": "Object",
}

import bpy
import os
import re
from bpy.props import StringProperty, CollectionProperty, IntProperty, BoolProperty
from bpy.types import Operator, Panel, PropertyGroup, UIList

# Data items
class CollectionItem(PropertyGroup):
    name: StringProperty(name="Collection Name")

class SubdirItem(PropertyGroup):
    name: StringProperty(name="Subdirectory Name")

class BlendFileItem(PropertyGroup):
    name: StringProperty(name="File Name")
    path: StringProperty(name="File Path", subtype='FILE_PATH')

class MatchItem(PropertyGroup):
    collection_name: StringProperty(name="Collection")
    subdir_name: StringProperty(name="Directory")
    matched: BoolProperty(name="Matched", default=False)

class LogItem(PropertyGroup):
    message: StringProperty(name="Message")

# UILists
class BATCH_UL_collections(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name)

class BATCH_UL_subdirectories(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name)

class BATCH_UL_targets(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.name)
        dir_up3 = os.path.dirname(os.path.dirname(os.path.dirname(item.path)))
        row.label(text=os.path.basename(dir_up3))
        row.label(text=item.path)

class BATCH_UL_matches(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "matched", text="")
        row.label(text=item.collection_name)
        row.label(text=item.subdir_name)

class BATCH_UL_logs(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.message)

# Operators
class BATCH_OT_source_file(Operator):
    bl_idname = "batch.collection_source_file"
    bl_label = "Source File"
    bl_description = "Select the source .blend file containing collections to inject"
    filepath: StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        sc = context.scene
        sc.collection_list.clear()
        sc.source_file = self.filepath
        with bpy.data.libraries.load(self.filepath, link=False) as (data_from, data_to):
            for cn in data_from.collections:
                itm = sc.collection_list.add()
                itm.name = cn
        return {'FINISHED'}

class BATCH_OT_root_directory(Operator):
    bl_idname = "batch.root_directory"
    bl_label = "Root Directory"
    bl_description = "Select the root directory containing target project folders"
    filepath: StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        sc = context.scene
        sc.subdir_list.clear()
        sc.root_dir = self.filepath
        for nm in sorted(os.listdir(sc.root_dir) if sc.root_dir else []):
            full = os.path.join(sc.root_dir, nm)
            if os.path.isdir(full):
                itm = sc.subdir_list.add()
                itm.name = nm
        return {'FINISHED'}

class BATCH_OT_search_targets(Operator):
    bl_idname = "batch.search_targets"
    bl_label = "Search Target Files"
    bl_description = "Search for .blend files matching the query in Root Directory"
    def execute(self, context):
        sc = context.scene
        sc.target_list.clear()
        q = sc.target_query
        rd = sc.root_dir
        for dp, _, fs in os.walk(rd) if rd else []:
            for f in fs:
                if f.lower().endswith('.blend') and q in f:
                    itm = sc.target_list.add()
                    itm.name = f
                    itm.path = os.path.join(dp, f)
        return {'FINISHED'}

class BATCH_OT_find_matches(Operator):
    bl_idname = "batch.find_matches"
    bl_label = "Find Matches"
    bl_description = "Match collections to subdirectories"
    def execute(self, context):
        sc = context.scene
        sc.match_list.clear()
        for coll in sc.collection_list:
            matched_name = ''
            for sub in sc.subdir_list:
                if sc.use_regex and re.match(rf"{re.escape(sub.name)}", coll.name):
                    matched_name = sub.name
                    break
                elif coll.name.startswith(sub.name):
                    matched_name = sub.name
                    break
            itm = sc.match_list.add()
            itm.collection_name = coll.name
            itm.subdir_name = matched_name
            itm.matched = bool(matched_name)
        return {'FINISHED'}

class BATCH_OT_select_all_matches(Operator):
    bl_idname = "batch.select_all_matches"
    bl_label = "Select All Matches"
    bl_description = "Mark all matches as true"
    def execute(self, context):
        for itm in context.scene.match_list:
            itm.matched = True
        return {'FINISHED'}

class BATCH_OT_clear_all_matches(Operator):
    bl_idname = "batch.clear_all_matches"
    bl_label = "Clear All Matches"
    bl_description = "Unmark all matches"
    def execute(self, context):
        for itm in context.scene.match_list:
            itm.matched = False
        return {'FINISHED'}

class BATCH_OT_inject_collections(Operator):
    bl_idname = "batch.inject_collections"
    bl_label = "Inject Collections"
    bl_description = "Inject matched collections into target files as linked collections"

    def execute(self, context):
        import subprocess, sys, tempfile
        sc = context.scene
        sc.log_list.clear()
        
        try:
            source = sc.source_file
            matches = [m for m in sc.match_list if m.matched]
            targets = sc.target_list
            total = len(targets)
            wm = context.window_manager
            wm.progress_begin(0, total)
            
            # Create a mapping of subdirectory names to their matched collections
            subdir_to_collections = {}
            for match in matches:
                if match.subdir_name and match.matched:  # Only include matches that have a subdirectory
                    if match.subdir_name not in subdir_to_collections:
                        subdir_to_collections[match.subdir_name] = []
                    subdir_to_collections[match.subdir_name].append(match.collection_name)
            
            # Fix Blender executable path for Windows
            blender_exec = sys.executable
            if sys.platform == 'win32':
                # Use os.path.expanduser to properly expand the home directory
                blender_exec = os.path.expanduser('~/programs/Blender4.5/blender.exe')
                # Check if the executable exists, otherwise fall back to sys.executable
                if not os.path.exists(blender_exec):
                    blender_exec = sys.executable
            
            # Process each target file
            for idx, target in enumerate(targets):
                try:
                    target_path = target.path
                    
                    # Normalize the target path for comparison
                    normalized_target = os.path.normpath(target_path).replace('\\', '/')
                    normalized_root = os.path.normpath(sc.root_dir).replace('\\', '/')
                    
                    # Find which root subdirectory this target file belongs to
                    target_collections = []
                    target_subdir = None
                    
                    # Check each subdirectory to see if the target file is within it
                    for subdir_name in subdir_to_collections.keys():
                        subdir_full_path = os.path.join(sc.root_dir, subdir_name)
                        normalized_subdir = os.path.normpath(subdir_full_path).replace('\\', '/')
                        
                        # Check if the target file is within this subdirectory
                        if normalized_target.startswith(normalized_subdir + '/') or normalized_target.startswith(normalized_subdir):
                            target_subdir = subdir_name
                            target_collections = subdir_to_collections[subdir_name]
                            break
                    
                    # Skip this target if no collections should be injected
                    if not target_collections:
                        msg = f"No matching collections for {os.path.basename(target_path)} - not in any matched subdirectory"
                        sc.log_list.add().message = msg
                        wm.progress_update(idx + 1)
                        continue
                    
                    # Create proper Python script content with collection instances
                    script_lines = [
                        "import bpy",
                        "import os",
                        f"source_file = r'{source}'",
                        f"collections_to_link = {repr(target_collections)}",
                        "",
                        "# Get the filename for the designated collection",
                        "current_filename = os.path.basename(bpy.data.filepath)",
                        "designated_collection_name = f'.\\\\{current_filename}'",
                        "",
                        "# Find the designated collection",
                        "designated_collection = bpy.data.collections.get(designated_collection_name)",
                        "if designated_collection:",
                        "    target_collection = designated_collection",
                        "else:",
                        "    target_collection = bpy.context.scene.collection",
                        "",
                        "# Load and link collections",
                        "with bpy.data.libraries.load(source_file, link=True) as (data_from, data_to):",
                        "    # Filter collections that exist in source",
                        "    available_collections = [c for c in collections_to_link if c in data_from.collections]",
                        "    data_to.collections = available_collections",
                        "",
                        "# Create collection instances",
                        "linked_count = 0",
                        "for coll in bpy.data.collections:",
                        "    if coll.library and coll.name in collections_to_link:",
                        "        # Check if instance already exists in the target collection",
                        "        instance_exists = False",
                        "        for obj in target_collection.objects:",
                        "            if obj.instance_type == 'COLLECTION' and obj.instance_collection == coll:",
                        "                instance_exists = True",
                        "                break",
                        "        ",
                        "        if not instance_exists:",
                        "            try:",
                        "                # Create a collection instance (empty that instances the collection)",
                        "                instance = bpy.data.objects.new(name=coll.name, object_data=None)",
                        "                instance.instance_type = 'COLLECTION'",
                        "                instance.instance_collection = coll",
                        "                # Link the instance to the target collection",
                        "                target_collection.objects.link(instance)",
                        "                linked_count += 1",
                        "            except Exception as e:",
                        "                pass",
                        "",
                        "# Save the file",
                        "bpy.ops.wm.save_mainfile()",
                        "print(f'Successfully created {linked_count} collection instances')",
                    ]
                    
                    log_prefix = "[Dry Run]" if sc.dry_run else ""
                    
                    if sc.dry_run:
                        msg = f"{log_prefix} Would inject {target_collections} into {os.path.basename(target_path)} [{target_subdir}]"
                        sc.log_list.add().message = msg
                    else:
                        # Create a temporary Python script file
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_script:
                            temp_script_path = temp_script.name
                            temp_script.write('\n'.join(script_lines))
                        
                        try:
                            # Run external Blender process with better error capture
                            cmd = [blender_exec, '--background', target_path, '--python', temp_script_path]
                            
                            # Capture output for debugging
                            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                            
                            # Check for success
                            if "Successfully created" in result.stdout:
                                # Extract number of linked collection instances
                                import re
                                match = re.search(r'Successfully created (\d+) collection instances', result.stdout)
                                if match:
                                    count = match.group(1)
                                    msg = f"✓ Created {count} collection instances in {os.path.basename(target_path)} [{target_subdir}]"
                                else:
                                    msg = f"✓ Completed linking to {os.path.basename(target_path)} [{target_subdir}]"
                            else:
                                msg = f"Completed linking to {os.path.basename(target_path)} [{target_subdir}] (check file to verify)"
                                
                        except subprocess.CalledProcessError as e:
                            msg = f"✗ Error linking into {os.path.basename(target_path)} [{target_subdir}]: {e}"
                        finally:
                            # Clean up temporary script file
                            try:
                                os.unlink(temp_script_path)
                            except:
                                pass
                        
                        sc.log_list.add().message = msg
                        
                except Exception as e:
                    sc.log_list.add().message = f"ERROR: {str(e)}"
                
                wm.progress_update(idx + 1)
            
            wm.progress_end()
            sc.log_list.add().message = "Injection process completed!"
            
        except Exception as e:
            sc.log_list.add().message = f"ERROR: {str(e)}"
            return {'CANCELLED'}
            
        return {'FINISHED'}

# Panel
class BATCH_PT_panel(Panel):
    bl_label = "Inject Collections"
    bl_idname = "BATCH_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Inject Collections'

    def draw(self, context):
        layout = self.layout
        sc = context.scene
        # Source
        box = layout.box()
        icon = 'TRIA_DOWN' if sc.show_source_section else 'TRIA_RIGHT'
        row = box.row()
        row.prop(sc, "show_source_section", emboss=False, icon=icon, text="Select Source File")
        if sc.show_source_section:
            box.operator('batch.collection_source_file', text="Load Source .blend")
            box.label(text=sc.source_file and f"Source: {os.path.basename(sc.source_file)}" or "Source: None")
            if sc.source_file: box.label(text=sc.source_file)
            b = box.box(); b.template_list("BATCH_UL_collections", "", sc, "collection_list", sc, "collection_index", rows=5)
        # Root
        box = layout.box()
        icon = 'TRIA_DOWN' if sc.show_root_section else 'TRIA_RIGHT'
        row = box.row()
        row.prop(sc, "show_root_section", emboss=False, icon=icon, text="Select Root Directory")
        if sc.show_root_section:
            box.operator('batch.root_directory', text="Load Root Directory")
            box.label(text=sc.root_dir and f"Root: {sc.root_dir}" or "Root: None")
            b = box.box(); b.template_list("BATCH_UL_subdirectories", "", sc, "subdir_list", sc, "subdir_index", rows=5)
        # Search
        box = layout.box()
        icon = 'TRIA_DOWN' if sc.show_search_section else 'TRIA_RIGHT'
        row = box.row()
        row.prop(sc, "show_search_section", emboss=False, icon=icon, text="Search Target Files")
        if sc.show_search_section:
            box.prop(sc, "target_query", text="Query")
            box.operator('batch.search_targets', text="Search")
            inner = box.box()
            inner.label(text="Targets:")
            hr = inner.row(align=True); hr.label(text="Filename"); hr.label(text="Directory"); hr.label(text="Full Path"); inner.separator()
            inner.template_list("BATCH_UL_targets", "", sc, "target_list", sc, "target_index", rows=5)
        # Matches
        box = layout.box()
        icon = 'TRIA_DOWN' if sc.show_matches_section else 'TRIA_RIGHT'
        row = box.row()
        row.prop(sc, "show_matches_section", emboss=False, icon=icon, text="Find Matches")
        if sc.show_matches_section:
            total = len(sc.collection_list); matched = sum(1 for m in sc.match_list if m.matched); inner_label = box.label; inner_label(text=f"Summary: {matched}/{total} matched")
            box.prop(sc, "use_regex", text="Use Regex Matching")
            box.operator('batch.find_matches', text="Find Matches")
            inner = box.box(); inner.label(text="Matches:")
            hr = inner.row(align=True); hr.label(text=" "); hr.label(text="Source Collections"); hr.label(text="Target Directories"); inner.separator()
            inner.template_list("BATCH_UL_matches", "", sc, "match_list", sc, "match_index", rows=5)
        # Inject
        box = layout.box()
        icon = 'TRIA_DOWN' if sc.show_inject_section else 'TRIA_RIGHT'
        row = box.row()
        row.prop(sc, "show_inject_section", emboss=False, icon=icon, text="Inject Collections")
        if sc.show_inject_section:
            ctl = box.row(align=True); ctl.prop(sc, "dry_run", text="Dry Run"); ctl.operator('batch.inject_collections', text="Inject Collections")
            log_box = box.box(); log_box.label(text="Log:"); log_box.template_list("BATCH_UL_logs", "", sc, "log_list", sc, "log_index", rows=5)

# Registration
classes = [
    CollectionItem, SubdirItem, BlendFileItem, MatchItem, LogItem,
    BATCH_UL_collections, BATCH_UL_subdirectories, BATCH_UL_targets, BATCH_UL_matches, BATCH_UL_logs,
    BATCH_OT_source_file, BATCH_OT_root_directory, BATCH_OT_search_targets, BATCH_OT_find_matches,
    BATCH_OT_select_all_matches, BATCH_OT_clear_all_matches, BATCH_OT_inject_collections,
    BATCH_PT_panel
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    sc = bpy.types.Scene
    sc.collection_list = CollectionProperty(type=CollectionItem)
    sc.collection_index = IntProperty(default=0)
    sc.source_file = StringProperty(subtype='FILE_PATH', default="")
    sc.subdir_list = CollectionProperty(type=SubdirItem)
    sc.subdir_index = IntProperty(default=0)
    sc.root_dir = StringProperty(subtype='DIR_PATH', default="")
    sc.target_query = StringProperty(default="")
    sc.target_list = CollectionProperty(type=BlendFileItem)
    sc.target_index = IntProperty(default=0)
    sc.match_list = CollectionProperty(type=MatchItem)
    sc.match_index = IntProperty(default=0)
    sc.log_list = CollectionProperty(type=LogItem)
    sc.log_index = IntProperty(default=0)
    sc.show_source_section = BoolProperty(default=True)
    sc.show_root_section = BoolProperty(default=True)
    sc.show_search_section = BoolProperty(default=True)
    sc.show_matches_section = BoolProperty(default=True)
    sc.use_regex = BoolProperty(name="Use Regex Matching", default=False)
    sc.show_inject_section = BoolProperty(default=True)
    sc.dry_run = BoolProperty(name="Dry Run", default=False)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    sc = bpy.types.Scene
    del sc.dry_run
    del sc.show_inject_section
    del sc.use_regex
    del sc.show_matches_section
    del sc.show_search_section
    del sc.show_root_section
    del sc.show_source_section
    del sc.match_index
    del sc.match_list
    del sc.log_index
    del sc.log_list
    del sc.target_index
    del sc.target_list
    del sc.target_query
    del sc.root_dir
    del sc.subdir_index
    del sc.subdir_list
    del sc.source_file
    del sc.collection_index
    del sc.collection_list

if __name__ == "__main__":
    register()
