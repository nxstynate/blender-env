# #### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

from typing import List, Optional, Tuple
import mathutils
import os
import re
from math import pi

import bpy
from bpy.types import Operator
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)
import bpy.utils.previews

from ..modules.poliigon_core.assets import AssetData
from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context
from .. import reporting


class POLIIGON_OT_hdri(Operator):
    bl_idname = "poliigon.poliigon_hdri"
    bl_label = _t("HDRI Import")
    bl_description = _t("Import HDRI")
    bl_options = {"GRAB_CURSOR", "BLOCKING", "REGISTER", "INTERNAL", "UNDO"}

    def _fill_light_size_drop_down(
            self, context) -> List[Tuple[str, str, str]]:
        asset_data = cTB._asset_index.get_asset(self.asset_id)
        asset_type_data = asset_data.get_type_data()

        # Get list of locally available sizes
        asset_files = {}
        asset_type_data.get_files(asset_files)
        asset_files = list(asset_files.keys())

        # Populate dropdown items
        local_exr_sizes = []
        for path_asset in asset_files:
            filename = os.path.basename(path_asset)
            if not filename.endswith(".exr"):
                continue
            match_object = re.search(r"_(\d+K)[_\.]", filename)
            if match_object:
                local_exr_sizes.append(match_object.group(1))
        # Sort by comparing integer size without "K"
        local_exr_sizes.sort(key=lambda s: int(s[:-1]))
        items_size = []
        for size in local_exr_sizes:
            # Tuple: (id, name, description, icon, enum value)
            items_size.append((size, f"{size} EXR", f"{size} EXR"))
        return items_size

    def _fill_bg_size_drop_down(self, context) -> List[Tuple[str, str, str]]:
        asset_data = cTB._asset_index.get_asset(self.asset_id)
        asset_type_data = asset_data.get_type_data()

        # Get list of locally available sizes
        asset_files = {}
        asset_type_data.get_files(asset_files)
        asset_files = list(asset_files.keys())

        # Populate dropdown items
        local_exr_sizes = []
        local_jpg_sizes = []
        for path_asset in asset_files:
            filename = os.path.basename(path_asset)
            is_exr = filename.endswith(".exr")
            is_jpg = filename.lower().endswith(".jpg")
            is_jpg &= "_JPG" in filename
            if not is_exr and not is_jpg:
                continue
            match_object = re.search(r"_(\d+K)[_\.]", filename)
            if not match_object:
                continue
            local_size = match_object.group(1)
            if is_exr:
                local_exr_sizes.append(f"{local_size}_EXR")
            elif is_jpg:
                local_jpg_sizes.append(f"{local_size}_JPG")

        local_sizes = local_exr_sizes + local_jpg_sizes
        # Sort by comparing integer size without "K_JPG" or "K_EXR"
        local_sizes.sort(key=lambda s: int(s[:-5]))
        items_size = []
        for size in local_sizes:
            # Tuple: (id, name, description, icon, enum value)
            label = size.replace("_", " ")
            items_size.append((size, label, label))
        return items_size

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821
    # If do_apply is set True, the sizes are ignored and set internally
    do_apply: BoolProperty(options={"HIDDEN"}, default=False)  # noqa: F821
    size: EnumProperty(
        name=_t("Light Texture"),  # noqa F722
        items=_fill_light_size_drop_down,
        description=_t("Change size of light texture."))  # noqa F722
    # This is not a pure size, but is a string like "4K_JPG"
    size_bg: EnumProperty(
        name=_t("Background Texture"),  # noqa F722
        items=_fill_bg_size_drop_down,
        description=_t("Change size of background texture."))  # noqa F722
    hdr_strength: FloatProperty(
        name=_t("HDR Strength"),  # noqa F722
        description=_t("Strength of Light and Background textures"),  # noqa F722
        soft_min=0.0,
        step=10,
        default=1.0)
    rotation: FloatProperty(
        name=_t("Z-Rotation"),  # noqa: F821
        description=_t("Z-Rotation"),  # noqa: F821
        unit="ROTATION",  # noqa: F821
        soft_min=-2.0 * pi,
        soft_max=2.0 * pi,
        # precision needed here, otherwise Redo Last and node show different values
        precision=3,
        step=10,
        default=0.0)

    def __init__(self, *args, **kwargs):
        """Runs once per operator call before drawing occurs."""
        super().__init__(*args, **kwargs)
        self.exec_count = 0

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    @staticmethod
    def get_imported_hdri(asset_id: int) -> Optional[bpy.types.Image]:
        """Returns the imported HDRI image (if any)."""

        img_hdri = None
        for _img in bpy.data.images:
            try:
                asset_id_img = _img.poliigon_props.asset_id
                if asset_id_img != asset_id:
                    continue
                img_hdri = _img
                break
            except BaseException:
                # skip non-Poliigon images (no props)
                continue
        return img_hdri

    @reporting.handle_operator()
    def execute(self, context):
        asset_data = cTB._asset_index.get_asset(self.asset_id)
        asset_type_data = asset_data.get_type_data()

        asset_name = asset_data.asset_name
        local_convention = asset_data.get_convention(local=True)
        addon_convention = cTB.addon_convention

        cTB.reset_asset_error(asset_name=asset_name)

        name_light = f"{asset_name}_Light"
        name_bg = f"{asset_name}_Background"

        try:
            if "_" not in self.size_bg:
                raise ValueError
            size_bg_eff, filetype_bg = self.size_bg.split("_")
        except Exception:
            msg = ("POLIIGON_OT_hdri: Wrong size_bg format "
                   f"({self.size_bg}), expected '4K_JPG' or '1K_EXR'")
            raise ValueError(msg)

        if self.size == size_bg_eff:
            name_bg = name_light

        cTB.logger.debug("POLIIGON_OT_hdri "
                         f"{asset_name}, {name_light}, {name_bg}")

        existing = self.get_imported_hdri(self.asset_id)

        # Whenever an HDR is loaded, it fully replaces the prior loaded
        # images/resolutions. Thus, if we are "applying" an already imported
        # one, we don't need to worry about resolution selection.

        if not self.do_apply or not existing:
            # Remove existing images to force loading this resolution.
            if name_light in bpy.data.images.keys():
                bpy.data.images.remove(bpy.data.images[name_light])

            if name_bg in bpy.data.images.keys():
                bpy.data.images.remove(bpy.data.images[name_bg])
        elif self.do_apply:
            if name_light in bpy.data.images.keys():
                path_light = bpy.data.images[name_light].filepath
                filename = os.path.basename(path_light)
                match_object = re.search(r"_(\d+K)[_\.]", filename)
                size_light = match_object.group(1) if match_object else cTB.settings["hdri"]
                self.size = size_light
            if name_bg in bpy.data.images.keys():
                path_bg = bpy.data.images[name_bg].filepath
                filename = os.path.basename(path_bg)
                file_type = "JPG" if "_JPG" in filename else "EXR"
                match_object = re.search(r"_(\d+K)[_\.]", filename)
                # TODO(Andreas): should next line use cTB.settings["hdribg"] ?
                size_bg = match_object.group(1) if match_object else cTB.settings["hdri"]
                self.size_bg = f"{size_bg}_{file_type}"
                size_bg_eff = size_bg
                filetype_bg = file_type

        light_exists = name_light in bpy.data.images.keys()
        bg_exists = name_bg in bpy.data.images.keys()
        if not light_exists or not bg_exists:
            if not self.size or self.do_apply:
                # Edge case that shouldn't occur as the resolution should be
                # explicitly set, or just applying a local tex already,
                # but fallback if needed.
                self.size = cTB.settings["hdri"]

            size_light = asset_type_data.get_size(
                self.size,
                local_only=True,
                addon_convention=addon_convention,
                local_convention=local_convention)

            files = {}
            asset_type_data.get_files(files)
            files = list(files.keys())

            files_tex_exr = [_file for _file in files
                             if size_light in os.path.basename(_file) and _file.lower().endswith(".exr")]

            if len(files_tex_exr) == 0:
                # TODO(Andreas): Shouldn't be needed anymore with AssetIndex
                # cTB.f_GetLocalAssets()  # Refresh local assets data structure.
                msg = (f"Unable to locate image {name_light} with size {size_light}, "
                       f"try downloading {asset_name} again.")
                reporting.capture_message(
                    "failed_load_light_hdri", msg, "error")
                msg = _t(
                    "Unable to locate image {0} with size {1}, try downloading {2} again."
                ).format(name_light, size_light, asset_name)
                self.report({"ERROR"}, msg)
                return {"CANCELLED"}
            file_tex_light = files_tex_exr[0]

            if cTB.settings["hdri_use_jpg_bg"] and filetype_bg == "JPG":
                size_bg = asset_type_data.get_size(
                    size_bg_eff,
                    local_only=True,
                    addon_convention=addon_convention,
                    local_convention=local_convention)

                files_tex_jpg = [_file for _file in files
                                 if size_bg in os.path.basename(_file) and _file.lower().endswith(".jpg")]

                if len(files_tex_jpg) == 0:
                    # TODO(Andreas): Shouldn't be needed anymore with AssetIndex
                    # cTB.f_GetLocalAssets()  # Refresh local assets data structure.
                    msg = (f"Unable to locate image {name_bg} with size {size_bg} (JPG), "
                           f"try downloading {asset_name} again.")
                    reporting.capture_message(
                        "failed_load_bg_jpg", msg, "error")
                    msg = _t(
                        "Unable to locate image {0} with size {1} (JPG), try downloading {2} again."
                    ).format(name_bg, size_bg, asset_name)
                    self.report({"ERROR"}, msg)
                    return {"CANCELLED"}
                file_tex_bg = files_tex_jpg[0]
            elif size_light != size_bg_eff:
                size_bg = size_bg_eff
                files_tex_exr = [_file for _file in files
                                 if size_bg_eff in os.path.basename(_file) and _file.lower().endswith(".exr")]
                if len(files_tex_exr) == 0:
                    # TODO(Andreas): Shouldn't be needed anymore with AssetIndex
                    # cTB.f_GetLocalAssets()  # Refresh local assets data structure.
                    msg = (f"Unable to locate image {name_bg} with size {size_bg} (EXR), "
                           f"try downloading {asset_name} again")
                    reporting.capture_message(
                        "failed_load_bg_hdri", msg, "error")
                    msg = _t(
                        "Unable to locate image {0} with size {1} (EXR), try downloading {2} again"
                    ).format(name_bg, size_bg, asset_name)
                    self.report({"ERROR"}, msg)
                    return {"CANCELLED"}
                file_tex_bg = files_tex_exr[0]
            else:
                size_bg = size_light
                file_tex_bg = file_tex_light

        # Reset apply for Redo Last menu to work properly
        self.do_apply = False

        # ...............................................................................................

        node_tex_coord = None
        node_mapping = None

        node_tex_env_light = None
        node_background_light = None

        node_tex_env_bg = None
        node_background_bg = None

        node_mix_shader = None
        node_light_path = None

        node_output_world = None

        if not bpy.context.scene.world:
            bpy.ops.world.new()
            bpy.context.scene.world = bpy.data.worlds[-1]

        context.scene.world.use_nodes = True

        nodes_world = context.scene.world.node_tree.nodes
        links_world = context.scene.world.node_tree.links
        for _node in nodes_world:
            if _node.type == "TEX_COORD":
                if _node.label == "Mapping":
                    node_tex_coord = _node

            elif _node.type == "MAPPING":
                if _node.label == "Mapping":
                    node_mapping = _node

            elif _node.type == "TEX_ENVIRONMENT":
                if _node.label == "Lighting":
                    node_tex_env_light = _node
                elif _node.label == "Background":
                    node_tex_env_bg = _node

            elif _node.type == "BACKGROUND":
                if _node.label == "Lighting":
                    node_background_light = _node
                elif _node.label == "Background":
                    node_background_bg = _node
                elif len(nodes_world) == 2:
                    node_background_light = _node
                    node_background_light.label = "Lighting"
                    node_background_light.location = mathutils.Vector(
                        (-110, 200))

            elif _node.type == "MIX_SHADER":
                node_mix_shader = _node

            elif _node.type == "LIGHT_PATH":
                node_light_path = _node

            elif _node.type == "OUTPUT_WORLD":
                node_output_world = _node

        if node_tex_coord is None:
            node_tex_coord = nodes_world.new("ShaderNodeTexCoord")
            node_tex_coord.label = "Mapping"
            node_tex_coord.location = mathutils.Vector((-1080, 420))

        if node_mapping is None:
            node_mapping = nodes_world.new("ShaderNodeMapping")
            node_mapping.label = "Mapping"
            node_mapping.location = mathutils.Vector((-870, 420))

        if node_tex_env_light is None:
            node_tex_env_light = nodes_world.new("ShaderNodeTexEnvironment")
            node_tex_env_light.label = "Lighting"
            node_tex_env_light.location = mathutils.Vector((-470, 420))

        if node_tex_env_bg is None:
            node_tex_env_bg = nodes_world.new("ShaderNodeTexEnvironment")
            node_tex_env_bg.label = "Background"
            node_tex_env_bg.location = mathutils.Vector((-470, 100))

        if node_background_light is None:
            node_background_light = nodes_world.new("ShaderNodeBackground")
            node_background_light.label = "Lighting"
            node_background_light.location = mathutils.Vector((-110, 200))

        if node_background_bg is None:
            node_background_bg = nodes_world.new("ShaderNodeBackground")
            node_background_bg.label = "Background"
            node_background_bg.location = mathutils.Vector((-110, 70))

        if node_mix_shader is None:
            node_mix_shader = nodes_world.new("ShaderNodeMixShader")
            node_mix_shader.location = mathutils.Vector((110, 300))

        if node_light_path is None:
            node_light_path = nodes_world.new("ShaderNodeLightPath")
            node_light_path.location = mathutils.Vector((-110, 550))

        if node_output_world is None:
            node_output_world = nodes_world.new("ShaderNodeOutputWorld")
            node_output_world.location = mathutils.Vector((370, 300))

        links_world.new(
            node_tex_coord.outputs["Generated"],
            node_mapping.inputs["Vector"])
        links_world.new(
            node_mapping.outputs["Vector"],
            node_tex_env_light.inputs["Vector"])
        links_world.new(
            node_tex_env_light.outputs["Color"],
            node_background_light.inputs["Color"])
        links_world.new(
            node_background_light.outputs[0],
            node_mix_shader.inputs[1])

        links_world.new(
            node_tex_coord.outputs["Generated"],
            node_mapping.inputs["Vector"])
        links_world.new(
            node_mapping.outputs["Vector"],
            node_tex_env_bg.inputs["Vector"])
        links_world.new(
            node_tex_env_bg.outputs["Color"],
            node_background_bg.inputs["Color"])
        links_world.new(
            node_background_bg.outputs[0],
            node_mix_shader.inputs[2])

        links_world.new(
            node_light_path.outputs[0],
            node_mix_shader.inputs[0])

        links_world.new(
            node_mix_shader.outputs[0],
            node_output_world.inputs[0])

        if name_light in bpy.data.images.keys():
            img_light = bpy.data.images[name_light]

        else:
            file_tex_light_norm = os.path.normpath(file_tex_light)
            img_light = bpy.data.images.load(file_tex_light_norm)
            img_light.name = name_light
            img_light.poliigon = "HDRIs;" + asset_name
            self.set_poliigon_props_image(img_light, asset_data)

        if name_bg in bpy.data.images.keys():
            img_bg = bpy.data.images[name_bg]

        else:
            file_tex_bg_norm = os.path.normpath(file_tex_bg)
            img_bg = bpy.data.images.load(file_tex_bg_norm)
            img_bg.name = name_bg
            self.set_poliigon_props_image(img_bg, asset_data)

        if "Rotation" in node_mapping.inputs:
            node_mapping.inputs["Rotation"].default_value[2] = self.rotation
        else:
            node_mapping.rotation[2] = self.rotation

        node_tex_env_light.image = img_light
        node_background_light.inputs["Strength"].default_value = self.hdr_strength

        node_tex_env_bg.image = img_bg
        node_background_bg.inputs["Strength"].default_value = self.hdr_strength

        self.set_poliigon_props_works(context, asset_data)

        cTB.f_GetSceneAssets()

        if self.exec_count == 0:
            cTB.signal_import_asset(asset_id=self.asset_id)
        self.exec_count += 1
        self.report({"INFO"}, _t("HDRI Imported : {0}").format(asset_name))
        return {"FINISHED"}

    def set_poliigon_props_image(
            self, img: bpy.types.Image, asset_data: AssetData) -> None:
        """Sets Poliigon property of an imported image."""

        img.poliigon_props.asset_name = asset_data.asset_name
        img.poliigon_props.asset_id = self.asset_id
        img.poliigon_props.asset_type = asset_data.asset_type.name
        img.poliigon_props.size = self.size
        img.poliigon_props.size_bg = self.size_bg
        img.poliigon_props.hdr_strength = self.hdr_strength
        img.poliigon_props.rotation = self.rotation

    def set_poliigon_props_works(self, context, asset_data: AssetData) -> None:
        """Sets Poliigon property of world."""

        context_world = context.scene.world
        context_world.poliigon_props.asset_name = asset_data.asset_name
        context_world.poliigon_props.asset_id = self.asset_id
        context_world.poliigon_props.asset_type = asset_data.asset_type.name
        context_world.poliigon_props.size = self.size
        context_world.poliigon_props.size_bg = self.size_bg
        context_world.poliigon_props.hdr_strength = self.hdr_strength
        context_world.poliigon_props.rotation = self.rotation
