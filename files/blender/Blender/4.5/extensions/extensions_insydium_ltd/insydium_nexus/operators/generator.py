# INSYDIUM NeXus Add-on for Blender
# Copyright (C) 2026 INSYDIUM LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import bpy


class NEXUS_OT_generator_new_instance_material(bpy.types.Operator):
    bl_idname = "nexus.generator_new_instance_material"
    bl_label = "New Instance Material"
    bl_description = (
        "Create a starter material wired to the NX_Generator_Attrs node group "
        "and assign it to the active layer"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.get("nexus_modifier_type") != "NX_GENERATOR":
            return False
        props = obj.nexus_modifier
        idx = props.generator_layers_index
        return 0 <= idx < len(props.generator_layers)

    def execute(self, context):
        from ..modifiers.nx_generator_realgeo import create_starter_material

        obj = context.object
        props = obj.nexus_modifier
        layer = props.generator_layers[props.generator_layers_index]
        viewport_color = tuple(float(c) for c in layer.custom_color)
        layer.instance_material = create_starter_material(viewport_color)
        obj.update_tag()
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
        return {"FINISHED"}


class NEXUS_OT_generator_resnapshot_freeze(bpy.types.Operator):
    bl_idname = "nexus.generator_resnapshot_freeze"
    bl_label = "Re-snapshot Freeze"
    bl_description = "Capture the source mesh at the current frame for this layer"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.get("nexus_modifier_type") != "NX_GENERATOR":
            return False
        props = obj.nexus_modifier
        idx = props.generator_layers_index
        layers = props.generator_layers
        if not (0 <= idx < len(layers)):
            return False
        return layers[idx].freeze_animation and layers[idx].obj is not None

    def execute(self, context):
        from ..viewport.generators.cache import capture_frozen_mesh

        obj = context.object
        props = obj.nexus_modifier
        layer = props.generator_layers[props.generator_layers_index]
        scene = context.scene
        depsgraph = context.evaluated_depsgraph_get()
        layer.frozen_frame = int(scene.frame_current)
        if not capture_frozen_mesh(layer.obj, layer.frozen_frame, depsgraph):
            self.report({"WARNING"}, "Could not capture mesh at the current frame")
            return {"CANCELLED"}
        # Propagate frozen_frame to the eval'd PropertyGroup before next draw.
        obj.update_tag()
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
        return {"FINISHED"}
