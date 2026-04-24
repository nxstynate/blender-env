bl_info = {
    "name": "BigBrother",
    "author": "Nate Lewis",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > BigBrother",
    "description": "Bulk edit Principled BSDF properties across all materials on selected objects",
    "category": "Material",
}

import bpy
from bpy.props import (
    BoolProperty,
    FloatProperty,
    FloatVectorProperty,
    EnumProperty,
    IntProperty,
)


# ---------------------------------------------------------------------------
# Property group – holds the editable values and per-parameter enable toggles
# ---------------------------------------------------------------------------

class BulkMatProperties(bpy.types.PropertyGroup):
    # --- toggles ---
    use_base_color: BoolProperty(name="Base Color", default=False)
    use_metallic: BoolProperty(name="Metallic", default=False)
    use_roughness: BoolProperty(name="Roughness", default=False)
    use_ior: BoolProperty(name="IOR", default=False)
    use_alpha: BoolProperty(name="Alpha", default=False)
    use_specular: BoolProperty(name="Specular IOR Level", default=False)
    use_coat: BoolProperty(name="Coat Weight", default=False)
    use_coat_roughness: BoolProperty(name="Coat Roughness", default=False)
    use_sheen: BoolProperty(name="Sheen Weight", default=False)
    use_emission_color: BoolProperty(name="Emission Color", default=False)
    use_emission_strength: BoolProperty(name="Emission Strength", default=False)
    use_transmission: BoolProperty(name="Transmission Weight", default=False)
    use_anisotropic: BoolProperty(name="Anisotropic", default=False)
    use_anisotropic_rotation: BoolProperty(name="Anisotropic Rotation", default=False)
    use_subsurface: BoolProperty(name="Subsurface Weight", default=False)
    use_normal_strength: BoolProperty(name="Normal Map Strength", default=False)
    use_blend_mode: BoolProperty(name="Blend Mode", default=False)

    # --- values ---
    base_color: FloatVectorProperty(
        name="Base Color", subtype='COLOR',
        default=(0.8, 0.8, 0.8, 1.0), size=4, min=0.0, max=1.0,
    )
    metallic: FloatProperty(name="Metallic", default=0.0, min=0.0, max=1.0)
    roughness: FloatProperty(name="Roughness", default=1.0, min=0.0, max=1.0)
    ior: FloatProperty(name="IOR", default=1.45, min=0.0, max=100.0)
    alpha: FloatProperty(name="Alpha", default=1.0, min=0.0, max=1.0)
    specular: FloatProperty(name="Specular IOR Level", default=0.5, min=0.0, max=1.0)
    coat: FloatProperty(name="Coat Weight", default=0.0, min=0.0, max=1.0)
    coat_roughness: FloatProperty(name="Coat Roughness", default=0.03, min=0.0, max=1.0)
    sheen: FloatProperty(name="Sheen Weight", default=0.0, min=0.0, max=1.0)
    emission_color: FloatVectorProperty(
        name="Emission Color", subtype='COLOR',
        default=(1.0, 1.0, 1.0, 1.0), size=4, min=0.0, max=1.0,
    )
    emission_strength: FloatProperty(name="Emission Strength", default=0.0, min=0.0)
    transmission: FloatProperty(name="Transmission Weight", default=0.0, min=0.0, max=1.0)
    anisotropic: FloatProperty(name="Anisotropic", default=0.0, min=0.0, max=1.0)
    anisotropic_rotation: FloatProperty(name="Anisotropic Rotation", default=0.0, min=0.0, max=1.0)
    subsurface: FloatProperty(name="Subsurface Weight", default=0.0, min=0.0, max=1.0)
    normal_strength: FloatProperty(name="Normal Map Strength", default=1.0, min=0.0, max=10.0)

    blend_mode: EnumProperty(
        name="Blend Mode",
        items=[
            ('OPAQUE', "Opaque", ""),
            ('CLIP', "Alpha Clip", ""),
            ('HASHED', "Alpha Hashed", ""),
            ('BLEND', "Alpha Blend", ""),
        ],
        default='OPAQUE',
    )


# ---------------------------------------------------------------------------
# Mapping from our property names to Principled BSDF input socket names
# Blender 4.x renamed some sockets – we try both names for compatibility.
# ---------------------------------------------------------------------------

PARAM_SOCKET_MAP = {
    "base_color":           ["Base Color"],
    "metallic":             ["Metallic"],
    "roughness":            ["Roughness"],
    "ior":                  ["IOR"],
    "alpha":                ["Alpha"],
    "specular":             ["Specular IOR Level", "Specular"],
    "coat":                 ["Coat Weight", "Clearcoat"],
    "coat_roughness":       ["Coat Roughness", "Clearcoat Roughness"],
    "sheen":                ["Sheen Weight", "Sheen"],
    "emission_color":       ["Emission Color"],
    "emission_strength":    ["Emission Strength"],
    "transmission":         ["Transmission Weight", "Transmission"],
    "anisotropic":          ["Anisotropic"],
    "anisotropic_rotation": ["Anisotropic Rotation"],
    "subsurface":           ["Subsurface Weight", "Subsurface"],
}


def _find_input(node, names):
    """Return the first matching input socket by name, or None."""
    for n in names:
        inp = node.inputs.get(n)
        if inp is not None:
            return inp
    return None


# ---------------------------------------------------------------------------
# Collect unique materials from selected objects
# ---------------------------------------------------------------------------

def _get_selected_materials(context):
    """Return a set of unique materials from all selected mesh objects."""
    mats = set()
    for obj in context.selected_objects:
        if obj.type != 'MESH' or not obj.data.materials:
            continue
        for mat in obj.data.materials:
            if mat is not None:
                mats.add(mat)
    return mats


def _get_principled_nodes(mat):
    """Yield all Principled BSDF nodes in a material's node tree."""
    if mat.use_nodes and mat.node_tree:
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                yield node


# ---------------------------------------------------------------------------
# Operator: Apply bulk changes
# ---------------------------------------------------------------------------

class BULKMAT_OT_apply(bpy.types.Operator):
    bl_idname = "bulkmat.apply"
    bl_label = "Apply to Selected"
    bl_description = "Apply checked material properties to all materials on selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.bulk_mat_props
        mats = _get_selected_materials(context)

        if not mats:
            self.report({'WARNING'}, "No materials found on selected objects")
            return {'CANCELLED'}

        changed_mats = 0
        changed_params = 0

        for mat in mats:
            mat_touched = False
            for node in _get_principled_nodes(mat):
                # --- socket-based parameters ---
                for prop_name, socket_names in PARAM_SOCKET_MAP.items():
                    toggle_attr = f"use_{prop_name}"
                    if not getattr(props, toggle_attr, False):
                        continue
                    inp = _find_input(node, socket_names)
                    if inp is None:
                        continue

                    value = getattr(props, prop_name)
                    # Color sockets expect a 4-component value
                    if prop_name in ("base_color", "emission_color"):
                        inp.default_value = tuple(value)
                    else:
                        inp.default_value = value
                    mat_touched = True
                    changed_params += 1

                # --- Normal Map strength (special case: node inside node) ---
                if props.use_normal_strength:
                    # Walk links to find a Normal Map node connected to Normal input
                    normal_input = _find_input(node, ["Normal"])
                    if normal_input and normal_input.is_linked:
                        linked_node = normal_input.links[0].from_node
                        if linked_node.type == 'NORMAL_MAP':
                            linked_node.inputs["Strength"].default_value = props.normal_strength
                            mat_touched = True
                            changed_params += 1

            # --- blend mode (material-level, not node-level) ---
            if props.use_blend_mode:
                # Blender 4.x uses mat.surface_render_method / mat.use_transparency_overlap
                # Blender 3.x uses mat.blend_method
                if hasattr(mat, 'blend_method'):
                    mat.blend_method = props.blend_mode
                    mat_touched = True
                    changed_params += 1

            if mat_touched:
                changed_mats += 1

        self.report({'INFO'}, f"Updated {changed_params} properties across {changed_mats} materials")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: Read values from active object's active material
# ---------------------------------------------------------------------------

class BULKMAT_OT_read_active(bpy.types.Operator):
    bl_idname = "bulkmat.read_active"
    bl_label = "Read from Active"
    bl_description = "Load values from the active object's active material into the panel"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not obj.active_material:
            self.report({'WARNING'}, "No active material on active object")
            return {'CANCELLED'}

        mat = obj.active_material
        props = context.scene.bulk_mat_props

        for node in _get_principled_nodes(mat):
            for prop_name, socket_names in PARAM_SOCKET_MAP.items():
                inp = _find_input(node, socket_names)
                if inp is None:
                    continue
                val = inp.default_value
                if prop_name in ("base_color", "emission_color"):
                    setattr(props, prop_name, tuple(val))
                else:
                    setattr(props, prop_name, val)

            # Normal map strength
            normal_input = _find_input(node, ["Normal"])
            if normal_input and normal_input.is_linked:
                linked_node = normal_input.links[0].from_node
                if linked_node.type == 'NORMAL_MAP':
                    props.normal_strength = linked_node.inputs["Strength"].default_value

            # Blend mode
            if hasattr(mat, 'blend_method'):
                props.blend_mode = mat.blend_method

            break  # only read the first principled node

        self.report({'INFO'}, f"Loaded values from '{mat.name}'")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: Toggle all checkboxes
# ---------------------------------------------------------------------------

class BULKMAT_OT_toggle_all(bpy.types.Operator):
    bl_idname = "bulkmat.toggle_all"
    bl_label = "Toggle All"
    bl_description = "Check or uncheck all parameter toggles"
    bl_options = {'REGISTER', 'UNDO'}

    enable: BoolProperty(default=True)

    def execute(self, context):
        props = context.scene.bulk_mat_props
        for attr in dir(props):
            if attr.startswith("use_"):
                setattr(props, attr, self.enable)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class BULKMAT_PT_main(bpy.types.Panel):
    bl_label = "BigBrother"
    bl_idname = "BULKMAT_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "BigBrother"

    def draw(self, context):
        layout = self.layout
        props = context.scene.bulk_mat_props

        # --- Info row ---
        mats = _get_selected_materials(context)
        sel_count = len(context.selected_objects)
        layout.label(text=f"{sel_count} objects selected  •  {len(mats)} unique materials")

        layout.separator()

        # --- Utility buttons ---
        row = layout.row(align=True)
        row.operator("bulkmat.read_active", icon='EYEDROPPER')
        sub = row.row(align=True)
        op_on = sub.operator("bulkmat.toggle_all", text="All On")
        op_on.enable = True
        op_off = sub.operator("bulkmat.toggle_all", text="All Off")
        op_off.enable = False

        layout.separator()

        # --- Parameter rows ---
        # Each row: [checkbox] [value slider/color]
        params = [
            ("use_base_color",           "base_color",           "Base Color"),
            ("use_metallic",             "metallic",             "Metallic"),
            ("use_roughness",            "roughness",            "Roughness"),
            ("use_ior",                  "ior",                  "IOR"),
            ("use_alpha",                "alpha",                "Alpha"),
            ("use_specular",             "specular",             "Specular IOR Level"),
            ("use_coat",                 "coat",                 "Coat Weight"),
            ("use_coat_roughness",       "coat_roughness",       "Coat Roughness"),
            ("use_sheen",                "sheen",                "Sheen Weight"),
            ("use_transmission",         "transmission",         "Transmission Weight"),
            ("use_anisotropic",          "anisotropic",          "Anisotropic"),
            ("use_anisotropic_rotation", "anisotropic_rotation", "Anisotropic Rotation"),
            ("use_subsurface",           "subsurface",           "Subsurface Weight"),
            ("use_emission_color",       "emission_color",       "Emission Color"),
            ("use_emission_strength",    "emission_strength",    "Emission Strength"),
            ("use_normal_strength",      "normal_strength",      "Normal Map Strength"),
        ]

        for toggle, value, label in params:
            row = layout.row(align=True)
            row.prop(props, toggle, text="")
            sub = row.row(align=True)
            sub.enabled = getattr(props, toggle)
            sub.prop(props, value, text=label)

        # Blend mode
        layout.separator()
        row = layout.row(align=True)
        row.prop(props, "use_blend_mode", text="")
        sub = row.row(align=True)
        sub.enabled = props.use_blend_mode
        sub.prop(props, "blend_mode", text="Blend Mode")

        layout.separator()

        # --- Apply button ---
        row = layout.row()
        row.scale_y = 1.5
        row.operator("bulkmat.apply", icon='CHECKMARK')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    BulkMatProperties,
    BULKMAT_OT_apply,
    BULKMAT_OT_read_active,
    BULKMAT_OT_toggle_all,
    BULKMAT_PT_main,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bulk_mat_props = bpy.props.PointerProperty(type=BulkMatProperties)


def unregister():
    del bpy.types.Scene.bulk_mat_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
