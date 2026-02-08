bl_info = {
    "name": "ReMatcha",
    "author": "NXSTYNATE",
    "version": (1, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > ReMatcha",
    "description": "Regex-based material replacement tool",
    "category": "Material",
}

import bpy
import re
from bpy.props import (
    StringProperty,
    BoolProperty,
    PointerProperty,
    CollectionProperty,
    IntProperty,
    FloatProperty,
)
from bpy.types import Panel, Operator, PropertyGroup, UIList


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------


def get_material_usage_count(material):
    """Count how many material slots use this material across all objects."""
    count = 0
    for obj in bpy.data.objects:
        if obj.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT", "GPENCIL"}:
            continue
        if not obj.material_slots:
            continue
        for slot in obj.material_slots:
            if slot.material == material:
                count += 1
    return count


def get_material_library_name(material):
    """Get the library filename if material is linked, otherwise return None."""
    if material.library:
        # Extract just the filename from the library path
        lib_path = material.library.filepath
        # Handle both forward and back slashes
        filename = lib_path.replace("\\", "/").split("/")[-1]
        return filename
    return None


def get_material_display_info(material):
    """Get display string with library and usage info."""
    parts = []
    
    # Library info
    lib_name = get_material_library_name(material)
    if lib_name:
        parts.append(f"[{lib_name}]")
    else:
        parts.append("[Local]")
    
    # Usage count
    usage = get_material_usage_count(material)
    parts.append(f"({usage} uses)")
    
    return " ".join(parts)


# -----------------------------------------------------------------------------
# Property Groups
# -----------------------------------------------------------------------------


class REMATCHA_MaterialItem(PropertyGroup):
    """Represents a material found by regex search"""

    name: StringProperty(name="Material Name")
    selected: BoolProperty(name="Selected", default=False)
    material: PointerProperty(type=bpy.types.Material)
    library_name: StringProperty(name="Library", default="")
    usage_count: IntProperty(name="Usage Count", default=0)
    is_linked: BoolProperty(name="Is Linked", default=False)


class REMATCHA_Properties(PropertyGroup):
    """Main properties for the ReMatcha panel"""

    regex_pattern: StringProperty(
        name="Pattern",
        description="Regex pattern to match material names",
        default="",
    )
    target_material: PointerProperty(
        type=bpy.types.Material,
        name="Target Material",
        description="Material to replace selected materials with",
    )
    found_materials: CollectionProperty(type=REMATCHA_MaterialItem)
    found_materials_index: IntProperty(name="Index", default=0)

    # Operation state
    is_running: BoolProperty(default=False)
    progress: FloatProperty(default=0.0, min=0.0, max=1.0)
    status_message: StringProperty(default="")
    last_result: StringProperty(default="")


# -----------------------------------------------------------------------------
# UI List
# -----------------------------------------------------------------------------


class REMATCHA_UL_MaterialList(UIList):
    """UI List for displaying found materials with checkboxes"""

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            
            # Checkbox
            row.prop(item, "selected", text="")
            
            # Get material preview icon if available
            mat = item.material
            if mat and mat.preview and mat.preview.icon_id:
                icon_value = mat.preview.icon_id
            else:
                icon_value = 0
            
            # Material name with icon
            if icon_value:
                row.label(text="", icon_value=icon_value)
            else:
                row.label(text="", icon="MATERIAL")
            
            # Name column
            name_row = row.row()
            name_row.label(text=item.name)
            
            # Library/Local indicator with different styling
            info_row = row.row()
            info_row.alignment = 'RIGHT'
            
            if item.is_linked:
                # Linked material - show library name with link icon
                info_row.label(text=f"{item.library_name}", icon="LINKED")
            else:
                # Local material
                info_row.label(text="Local", icon="FILE_BLEND")
            
            # Usage count
            usage_row = row.row()
            usage_row.alignment = 'RIGHT'
            usage_row.ui_units_x = 3
            usage_row.label(text=f"{item.usage_count}")
            
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.prop(item, "selected", text="")


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------


class REMATCHA_OT_SearchMaterials(Operator):
    """Search for materials matching the regex pattern"""

    bl_idname = "rematcha.search_materials"
    bl_label = "Search Materials"
    bl_description = "Find materials matching the regex pattern"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.rematcha
        pattern = props.regex_pattern

        # Clear previous results
        props.found_materials.clear()
        props.last_result = ""

        if not pattern:
            self.report({"WARNING"}, "Please enter a regex pattern")
            return {"CANCELLED"}

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            self.report({"ERROR"}, f"Invalid regex: {e}")
            return {"CANCELLED"}

        # Search all materials in the blend file
        found_count = 0
        for mat in bpy.data.materials:
            if regex.search(mat.name):
                # Ensure preview is generated for this material
                mat.preview_ensure()
                
                item = props.found_materials.add()
                item.name = mat.name
                item.material = mat
                item.selected = False
                
                # Get library info
                lib_name = get_material_library_name(mat)
                if lib_name:
                    item.library_name = lib_name
                    item.is_linked = True
                else:
                    item.library_name = ""
                    item.is_linked = False
                
                # Get usage count
                item.usage_count = get_material_usage_count(mat)
                
                found_count += 1

        if found_count == 0:
            self.report({"INFO"}, "No materials found matching pattern")
        else:
            self.report({"INFO"}, f"Found {found_count} material(s)")

        return {"FINISHED"}


class REMATCHA_OT_SelectAll(Operator):
    """Select or deselect all found materials"""

    bl_idname = "rematcha.select_all"
    bl_label = "Select All"
    bl_description = "Select all found materials"
    bl_options = {"REGISTER", "UNDO"}

    select: BoolProperty(default=True)

    def execute(self, context):
        props = context.scene.rematcha
        for item in props.found_materials:
            item.selected = self.select
        return {"FINISHED"}


class REMATCHA_OT_SelectLocal(Operator):
    """Select only local (non-linked) materials"""

    bl_idname = "rematcha.select_local"
    bl_label = "Local Only"
    bl_description = "Select only local materials (not linked from library)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.rematcha
        for item in props.found_materials:
            item.selected = not item.is_linked
        return {"FINISHED"}


class REMATCHA_OT_SelectLinked(Operator):
    """Select only linked materials"""

    bl_idname = "rematcha.select_linked"
    bl_label = "Linked Only"
    bl_description = "Select only linked materials from libraries"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.rematcha
        for item in props.found_materials:
            item.selected = item.is_linked
        return {"FINISHED"}


class REMATCHA_OT_ReplaceMaterials(Operator):
    """Replace selected materials with target material"""

    bl_idname = "rematcha.replace_materials"
    bl_label = "Replace Mat"
    bl_description = "Replace all selected materials with the target material"
    bl_options = {"REGISTER", "UNDO"}

    _timer = None
    _materials_to_replace = []
    _current_index = 0
    _replacement_log = []

    @classmethod
    def poll(cls, context):
        props = context.scene.rematcha
        has_selection = any(item.selected for item in props.found_materials)
        has_target = props.target_material is not None
        return has_selection and has_target and not props.is_running

    def modal(self, context, event):
        props = context.scene.rematcha

        if event.type == "TIMER":
            if self._current_index < len(self._materials_to_replace):
                # Process one material per timer tick
                item = self._materials_to_replace[self._current_index]
                mat_to_replace = item.material
                target_mat = props.target_material

                if mat_to_replace and mat_to_replace != target_mat:
                    replaced_count = self._replace_material(mat_to_replace, target_mat)
                    if replaced_count > 0:
                        # Include library info in the log
                        source_info = f"[{item.library_name}]" if item.is_linked else "[Local]"
                        self._replacement_log.append(
                            f"{mat_to_replace.name} {source_info} → {target_mat.name} ({replaced_count} slots)"
                        )

                self._current_index += 1
                props.progress = self._current_index / len(self._materials_to_replace)
                props.status_message = f"Processing {self._current_index}/{len(self._materials_to_replace)}"

                # Force redraw
                for area in context.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
            else:
                # Done
                self._finish(context)
                return {"FINISHED"}

        elif event.type == "ESC":
            self._cancel(context)
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def _replace_material(self, old_mat, new_mat):
        """Replace old_mat with new_mat across all objects. Returns count of replacements."""
        replaced_count = 0

        for obj in bpy.data.objects:
            if obj.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT", "GPENCIL"}:
                continue

            if not obj.material_slots:
                continue

            for slot in obj.material_slots:
                if slot.material == old_mat:
                    slot.material = new_mat
                    replaced_count += 1

        return replaced_count

    def _finish(self, context):
        props = context.scene.rematcha

        # Remove timer
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

        # Build result message
        if self._replacement_log:
            result_lines = ["Replacement complete!", ""]
            result_lines.extend(self._replacement_log)
            result_lines.append("")
            result_lines.append(
                f"Total: {len(self._replacement_log)} material(s) replaced"
            )
            props.last_result = "\n".join(result_lines)
        else:
            props.last_result = "No replacements were made."

        props.is_running = False
        props.progress = 0.0
        props.status_message = ""

        self.report({"INFO"}, f"Replaced {len(self._replacement_log)} material(s)")

        # Force redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

    def _cancel(self, context):
        props = context.scene.rematcha

        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

        props.is_running = False
        props.progress = 0.0
        props.status_message = "Cancelled"

        self.report({"WARNING"}, "Operation cancelled")

    def invoke(self, context, event):
        props = context.scene.rematcha

        # Gather materials to replace
        self._materials_to_replace = [
            item for item in props.found_materials if item.selected
        ]
        self._current_index = 0
        self._replacement_log = []

        if not self._materials_to_replace:
            self.report({"WARNING"}, "No materials selected")
            return {"CANCELLED"}

        if props.target_material is None:
            self.report({"WARNING"}, "No target material selected")
            return {"CANCELLED"}

        # Check if target is in selection
        target_in_selection = any(
            item.material == props.target_material
            for item in self._materials_to_replace
        )
        if target_in_selection:
            self.report(
                {"WARNING"},
                "Target material is in selection - this would have no effect",
            )
            return {"CANCELLED"}

        # Start modal operation
        props.is_running = True
        props.progress = 0.0
        props.status_message = "Starting..."
        props.last_result = ""

        # Add timer for modal operation
        self._timer = context.window_manager.event_timer_add(
            0.01, window=context.window
        )
        context.window_manager.modal_handler_add(self)

        return {"RUNNING_MODAL"}

    def execute(self, context):
        # Fallback if invoked directly
        return self.invoke(context, None)


class REMATCHA_OT_ClearResults(Operator):
    """Clear search results and status"""

    bl_idname = "rematcha.clear_results"
    bl_label = "Clear"
    bl_description = "Clear search results"
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = context.scene.rematcha
        props.found_materials.clear()
        props.last_result = ""
        props.regex_pattern = ""
        props.target_material = None
        return {"FINISHED"}


class REMATCHA_OT_RefreshUsage(Operator):
    """Refresh usage counts for all found materials"""

    bl_idname = "rematcha.refresh_usage"
    bl_label = "Refresh"
    bl_description = "Refresh usage counts for found materials"
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = context.scene.rematcha
        for item in props.found_materials:
            if item.material:
                item.usage_count = get_material_usage_count(item.material)
        self.report({"INFO"}, "Usage counts refreshed")
        return {"FINISHED"}


# -----------------------------------------------------------------------------
# Panel
# -----------------------------------------------------------------------------


class REMATCHA_PT_MainPanel(Panel):
    """Main panel for ReMatcha in the N-Panel"""

    bl_label = "ReMatcha"
    bl_idname = "REMATCHA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ReMatcha"

    def draw(self, context):
        layout = self.layout
        props = context.scene.rematcha

        # Regex search section
        box = layout.box()
        box.label(text="Find Materials", icon="VIEWZOOM")

        row = box.row(align=True)
        row.prop(props, "regex_pattern", text="", icon="SORTBYEXT")
        row.operator("rematcha.search_materials", text="", icon="VIEWZOOM")

        # Found materials list
        if props.found_materials:
            # Header row with column labels
            header = box.row()
            header.label(text=f"Found: {len(props.found_materials)}")
            
            # Column headers
            header_row = box.row(align=True)
            split = header_row.split(factor=0.5)
            split.label(text="Material")
            right = split.row()
            right.label(text="Source")
            right.label(text="Uses")

            box.template_list(
                "REMATCHA_UL_MaterialList",
                "",
                props,
                "found_materials",
                props,
                "found_materials_index",
                rows=6,
            )

            # Selection buttons row
            row = box.row(align=True)
            op = row.operator("rematcha.select_all", text="All")
            op.select = True
            op = row.operator("rematcha.select_all", text="None")
            op.select = False
            row.operator("rematcha.select_local", text="Local")
            row.operator("rematcha.select_linked", text="Linked")
            
            # Refresh button
            row = box.row()
            row.operator("rematcha.refresh_usage", icon="FILE_REFRESH")

        # Target material section
        layout.separator()
        box = layout.box()
        box.label(text="Replace With", icon="MATERIAL")
        
        # Show material picker with preview if a material is selected
        row = box.row(align=True)
        if props.target_material and props.target_material.preview and props.target_material.preview.icon_id:
            row.label(text="", icon_value=props.target_material.preview.icon_id)
        row.prop(props, "target_material", text="")
        
        # Show target material info
        if props.target_material:
            info_row = box.row()
            target_lib = get_material_library_name(props.target_material)
            if target_lib:
                info_row.label(text=f"Source: {target_lib}", icon="LINKED")
            else:
                info_row.label(text="Source: Local", icon="FILE_BLEND")
            
            usage = get_material_usage_count(props.target_material)
            info_row.label(text=f"Uses: {usage}")

        # Count selected
        selected_count = sum(1 for item in props.found_materials if item.selected)
        if selected_count > 0:
            box.label(text=f"{selected_count} material(s) selected for replacement")

        # Progress bar (shown during operation)
        if props.is_running:
            layout.separator()
            box = layout.box()
            box.label(text=props.status_message)
            box.progress(
                factor=props.progress, type="BAR", text=f"{int(props.progress * 100)}%"
            )

        # Replace button
        layout.separator()
        row = layout.row()
        row.scale_y = 1.5
        row.enabled = not props.is_running
        row.operator("rematcha.replace_materials", icon="FILE_REFRESH")

        # Clear button
        row = layout.row()
        row.operator("rematcha.clear_results", icon="X")

        # Results section
        if props.last_result:
            layout.separator()
            box = layout.box()
            box.label(text="Results", icon="INFO")

            # Split result into lines and display
            for line in props.last_result.split("\n"):
                if line.strip():
                    box.label(text=line)


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------

classes = (
    REMATCHA_MaterialItem,
    REMATCHA_Properties,
    REMATCHA_UL_MaterialList,
    REMATCHA_OT_SearchMaterials,
    REMATCHA_OT_SelectAll,
    REMATCHA_OT_SelectLocal,
    REMATCHA_OT_SelectLinked,
    REMATCHA_OT_ReplaceMaterials,
    REMATCHA_OT_ClearResults,
    REMATCHA_OT_RefreshUsage,
    REMATCHA_PT_MainPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rematcha = PointerProperty(type=REMATCHA_Properties)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.rematcha


if __name__ == "__main__":
    register()
