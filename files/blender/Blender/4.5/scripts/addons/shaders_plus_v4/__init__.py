# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name" : "Shaders Plus v4",
    "author" : "Cody Setchfield (SMOUSE)", 
    "description" : "Enhanced default shaders; Real-Time Caustics, Dispersion, Thin-Film",
    "blender" : (4, 0, 0),
    "version" : (4, 0, 2),
    "location" : "Shader Editor",
    "warning" : "Blender 4.0+",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "Node" 
}


import bpy
import bpy.utils.previews
import os


addon_keymaps = {}
_icons = None


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_MT_3D3C8(bpy.types.Menu):
    bl_idname = "SNA_MT_3D3C8"
    bl_label = "Main Shaders Plus UI"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        layout.menu('SNA_MT_66B50', text='Base BSDF Shaders', icon_value=0)
        layout.separator(factor=1.0)
        layout.menu('SNA_MT_763B5', text='Principled Presets', icon_value=0)
        layout.menu('SNA_MT_D3AD1', text='Diffuse Presets', icon_value=0)
        layout.menu('SNA_MT_3C1F0', text='Glossy Presets', icon_value=0)
        layout.menu('SNA_MT_C3262', text='Glass Presets', icon_value=0)
        layout.menu('SNA_MT_EE7C9', text='Refraction Presets', icon_value=0)
        layout.menu('SNA_MT_5B96D', text='Transparent Presets', icon_value=0)
        layout.menu('SNA_MT_A31A6', text='Sheen Presets', icon_value=0)
        layout.menu('SNA_MT_8F795', text='Toon Presets', icon_value=0)
        layout.separator(factor=1.0)
        layout.menu('SNA_MT_7837C', text='Help & Docs', icon_value=52)


class SNA_MT_7837C(bpy.types.Menu):
    bl_idname = "SNA_MT_7837C"
    bl_label = "Help + Docs"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('wm.url_open', text='Documentation & Tutorials', icon_value=52, emboss=True, depress=False)
        op.url = 'https://bit.ly/shadersplusdocs'
        op = layout.operator('wm.url_open', text='Discord', icon_value=229, emboss=True, depress=False)
        op.url = 'https://bit.ly/SP-smouse-studio-discord'
        op = layout.operator('wm.url_open', text='Report a bug', icon_value=2, emboss=True, depress=False)
        op.url = 'https://bit.ly/shadersplusbugreport'
        layout.separator(factor=1.0)
        op = layout.operator('wm.url_open', text='Say Hi to Jinx!', icon_value=778, emboss=True, depress=False)
        op.url = 'https://bit.ly/jinxsayshi-SP-button'


class SNA_MT_763B5(bpy.types.Menu):
    bl_idname = "SNA_MT_763B5"
    bl_label = "Test"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.loadgroupop_1c98d', text='Principled Plus Base Shader', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Principled Plus Shader'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Principled - Caustics (Simple)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Principled - Caustics (Simple)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Principled - Caustics (Complex)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Principled - Caustics (Complex)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Principled - Caustics (Simple Hotspot)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Principled - Caustics (Simple Hotspot)'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Principled - Dispersion (Default)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Principled - Dispersion (Default)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Principled - Dispersion (Strong)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Principled - Dispersion (Strong)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Principled - Dispersion Falloff', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Principled - Dispersion Falloff'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Principled - Thin Film (Default)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Principled - Thin Film (Default)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Principled - Thin Film (Anodized Chrome)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Principled - Thin Film (Anodized Chrome)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Principled - Thin Film (Pearlescent Car Paint)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Principled - Thin Film (Pearlescent Car Paint)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Principled - Thin Film (Oil Slick)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Principled - Thin Film (Oil Slick)'


class SNA_MT_66B50(bpy.types.Menu):
    bl_idname = "SNA_MT_66B50"
    bl_label = "Test"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.loadgroupop_1c98d', text='Principled Plus', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Principled Plus Shader'
        op = layout.operator('sna.loadgroupop_1c98d', text='Diffuse Plus', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Diffuse Plus Shader'
        op = layout.operator('sna.loadgroupop_1c98d', text='Glossy Plus', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glossy Plus Shader'
        op = layout.operator('sna.loadgroupop_1c98d', text='Glass Plus', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glass Plus Shader'
        op = layout.operator('sna.loadgroupop_1c98d', text='Refraction Plus', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Refraction Plus Shader'
        op = layout.operator('sna.loadgroupop_1c98d', text='Transparent Plus', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Transparent Plus Shader'
        op = layout.operator('sna.loadgroupop_1c98d', text='Sheen Plus', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Sheen Plus Shader'
        op = layout.operator('sna.loadgroupop_1c98d', text='Toon Plus', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Toon Plus Shader'


class SNA_MT_CCD2A(bpy.types.Menu):
    bl_idname = "SNA_MT_CCD2A"
    bl_label = "Test 1"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.loadgroupop_1c98d', text='Caustics Module', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Caustics Module - v2'
        op = layout.operator('sna.loadgroupop_1c98d', text='Dispersion Module', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Dispersion Module - v2'
        op = layout.operator('sna.loadgroupop_1c98d', text='Thin-Film Module', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Thin-Film Module - v2'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Module Combiner', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Module Combiner - v2'


class SNA_MT_D3AD1(bpy.types.Menu):
    bl_idname = "SNA_MT_D3AD1"
    bl_label = "Test"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.loadgroupop_1c98d', text='Diffuse Plus Base Shader', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Diffuse Plus Shader'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Diffuse - ' + 'Thin Film (Default)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Diffuse - ' + 'Thin Film (Default)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Diffuse - ' + 'Thin Film (Stylized 01)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Diffuse - ' + 'Thin Film (Stylized 01)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Diffuse - ' + 'Thin Film (Stylized 02)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Diffuse - ' + 'Thin Film (Stylized 02)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Diffuse - ' + 'Thin Film (Stylized 03)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Diffuse - ' + 'Thin Film (Stylized 03)'


class SNA_MT_C3262(bpy.types.Menu):
    bl_idname = "SNA_MT_C3262"
    bl_label = "Test"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.loadgroupop_1c98d', text='Glass Plus Base Shader', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glass Plus Shader'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Glass - Caustics (Default)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glass - Caustics (Default)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Glass - Caustics (Dispersion)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glass - Caustics (Dispersion)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Glass - Caustics + Dispersion (Medium)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glass - Caustics + Dispersion (Medium)'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Glass - Dispersion (Weak)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glass - Dispersion (Weak)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Glass - Dispersion (Strong)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glass - Dispersion (Strong)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Glass - Dispersion (Falloff)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glass - Dispersion (Falloff)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Glass - Dispersion (Crystal Glass)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glass - Dispersion (Crystal Glass)'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Glass - Thin Film (Default)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glass - Thin Film (Default)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Glass - Thin Film (Camera Lens)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glass - Thin Film (Camera Lens)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Glass - Thin Film (Oily Film)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glass - Thin Film (Oily Film)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Glass - Thin Film (Colorful Gemstone)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glass - Thin Film (Colorful Gemstone)'


class SNA_MT_EE7C9(bpy.types.Menu):
    bl_idname = "SNA_MT_EE7C9"
    bl_label = "Test"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.loadgroupop_1c98d', text='Refraction Plus Base Shader', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Refraction Plus Shader'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Refraction - Dispersion, Chromatic Abberation (Weak)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Refraction - Dispersion, Chromatic Abberation (Weak)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Refraction - Dispersion, Chromatic Abberation (Strong)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Refraction - Dispersion, Chromatic Abberation (Strong)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Refraction - Dispersion, Chromatic Abberation (Strong, Falloff)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Refraction - Dispersion, Chromatic Abberation (Strong, Falloff)'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Refraction - Thin Film (Morphism)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Refraction - Thin Film (Morphism)'


class SNA_MT_5B96D(bpy.types.Menu):
    bl_idname = "SNA_MT_5B96D"
    bl_label = "Test"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.loadgroupop_1c98d', text='Transparent Plus', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Transparent Plus Shader'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Transparent - Thin Film (Weak)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Transparent - Thin Film (Weak)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Transparent - Thin Film (Strong)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Transparent - Thin Film (Strong)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Transparent - Thin Film (Psychedelic)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Transparent - Thin Film (Psychedelic)'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Transparent - (Disable Shadow)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Transparent - (Disable Shadow)'


class SNA_MT_A31A6(bpy.types.Menu):
    bl_idname = "SNA_MT_A31A6"
    bl_label = "Test"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.loadgroupop_1c98d', text='Sheen Plus', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Sheen Plus Shader'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Sheen - Thin Film (Sunset)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Sheen - Thin Film (Sunset)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Sheen - Thin Film (Ice)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Sheen - Thin Film (Ice)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Sheen - Thin Film (Dark Pear)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Sheen - Thin Film (Dark Pear)'


class SNA_MT_8F795(bpy.types.Menu):
    bl_idname = "SNA_MT_8F795"
    bl_label = "Test"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.loadgroupop_1c98d', text='Toon Plus', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Toon Plus Shader'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Toon - Thin Film (Ocean Green)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Toon - Thin Film (Ocean Green)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Toon - Thin Film (Glacier)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Toon - Thin Film (Glacier)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Toon - Thin Film (Sunset Highlight)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Toon - Thin Film (Sunset Highlight)'


class SNA_MT_3C1F0(bpy.types.Menu):
    bl_idname = "SNA_MT_3C1F0"
    bl_label = "Test"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=1)
        layout.operator_context = "INVOKE_DEFAULT"
        op = layout.operator('sna.loadgroupop_1c98d', text='Glossy Plus Base Shader', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glossy Plus Shader'
        layout.separator(factor=1.0)
        op = layout.operator('sna.loadgroupop_1c98d', text='Glossy - Thin Film (Default)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glossy - Thin Film (Default)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Glossy - Thin Film (Heated Metal)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glossy - Thin Film (Heated Metal)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Glossy - Thin Film (Anodized Rainbow)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glossy - Thin Film (Anodized Rainbow)'
        op = layout.operator('sna.loadgroupop_1c98d', text='Glossy - Thin Film (Anodized Gradient)', icon_value=0, emboss=True, depress=False)
        op.sna_group_name = 'Glossy - Thin Film (Anodized Gradient)'


class SNA_AddonPreferences_F7BC4(bpy.types.AddonPreferences):
    bl_idname = 'shaders_plus_v4'
    sna_hide_header: bpy.props.BoolProperty(name='Hide Header', description='Test Desc', default=True)

    def draw(self, context):
        if not (False):
            layout = self.layout 
            split_2FAE0 = layout.split(factor=0.14575643837451935, align=False)
            split_2FAE0.alert = False
            split_2FAE0.enabled = True
            split_2FAE0.active = True
            split_2FAE0.use_property_split = False
            split_2FAE0.use_property_decorate = False
            split_2FAE0.scale_x = 1.0
            split_2FAE0.scale_y = 1.0
            split_2FAE0.alignment = 'Expand'.upper()
            if not True: split_2FAE0.operator_context = "EXEC_DEFAULT"
            split_2FAE0.label(text='Links:', icon_value=0)
            row_DDEA6 = split_2FAE0.row(heading='', align=False)
            row_DDEA6.alert = False
            row_DDEA6.enabled = True
            row_DDEA6.active = True
            row_DDEA6.use_property_split = False
            row_DDEA6.use_property_decorate = False
            row_DDEA6.scale_x = 1.0
            row_DDEA6.scale_y = 1.0
            row_DDEA6.alignment = 'Expand'.upper()
            row_DDEA6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = row_DDEA6.operator('wm.url_open', text='Documentation & Tutorials', icon_value=229, emboss=True, depress=False)
            op.url = 'https://bit.ly/shadersplusdocs'
            op = row_DDEA6.operator('wm.url_open', text='Discord', icon_value=52, emboss=True, depress=False)
            op.url = 'https://bit.ly/SP-smouse-studio-discord'
            split_D208A = layout.split(factor=0.14575600624084473, align=False)
            split_D208A.alert = False
            split_D208A.enabled = True
            split_D208A.active = True
            split_D208A.use_property_split = False
            split_D208A.use_property_decorate = False
            split_D208A.scale_x = 1.0
            split_D208A.scale_y = 1.0
            split_D208A.alignment = 'Expand'.upper()
            if not True: split_D208A.operator_context = "EXEC_DEFAULT"
            split_D208A.label(text='Report:', icon_value=0)
            col_55D35 = split_D208A.column(heading='', align=True)
            col_55D35.alert = True
            col_55D35.enabled = True
            col_55D35.active = True
            col_55D35.use_property_split = False
            col_55D35.use_property_decorate = False
            col_55D35.scale_x = 1.0
            col_55D35.scale_y = 1.0
            col_55D35.alignment = 'Expand'.upper()
            col_55D35.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = col_55D35.operator('wm.url_open', text='Report a Bug', icon_value=2, emboss=True, depress=False)
            op.url = 'https://bit.ly/shadersplusbugreport'
            layout.separator(factor=-2.0930001735687256)
            split_3EAF3 = layout.split(factor=0.14575600624084473, align=True)
            split_3EAF3.alert = False
            split_3EAF3.enabled = True
            split_3EAF3.active = True
            split_3EAF3.use_property_split = False
            split_3EAF3.use_property_decorate = False
            split_3EAF3.scale_x = 1.0
            split_3EAF3.scale_y = 1.584999918937683
            split_3EAF3.alignment = 'Center'.upper()
            if not True: split_3EAF3.operator_context = "EXEC_DEFAULT"
            split_3EAF3.label(text='UI Settings:', icon_value=0)
            row_0F1A1 = split_3EAF3.row(heading='', align=True)
            row_0F1A1.alert = False
            row_0F1A1.enabled = True
            row_0F1A1.active = True
            row_0F1A1.use_property_split = False
            row_0F1A1.use_property_decorate = False
            row_0F1A1.scale_x = 1.0
            row_0F1A1.scale_y = 1.0
            row_0F1A1.alignment = 'Expand'.upper()
            row_0F1A1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            row_0F1A1.prop(bpy.context.scene, 'sna_boolean', text='Node Editor "Right Click"', icon_value=210, emboss=True, toggle=True)
            row_0F1A1.prop(bpy.context.scene, 'sna_boolean_2', text='Node Edtior "Header"', icon_value=49, emboss=True, toggle=True, invert_checkbox=False)


def sna_add_to_node_mt_editor_menus_AAC66(self, context):
    if not ((True if (not bpy.context.scene.sna_boolean_2) else (bpy.context.area.ui_type != 'ShaderNodeTree'))):
        layout = self.layout
        layout.menu('SNA_MT_3D3C8', text='Shaders Plus', icon_value=0)


def sna_add_to_node_mt_context_menu_591BC(self, context):
    if not ((not bpy.context.scene.sna_boolean)):
        layout = self.layout
        layout.menu('SNA_MT_3D3C8', text='Shaders Plus', icon_value=736)


def sna_add_to_node_mt_add_A42E2(self, context):
    if not (False):
        layout = self.layout
        layout.menu('SNA_MT_3D3C8', text='Shaders Plus', icon_value=736)


class SNA_OT_Loadgroupop_1C98D(bpy.types.Operator):
    bl_idname = "sna.loadgroupop_1c98d"
    bl_label = "LoadGroupOp"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_group_name: bpy.props.StringProperty(name='Group Name', description='', default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        with bpy.context.temp_override():
            if (property_exists("bpy.data.node_groups", globals(), locals()) and self.sna_group_name in bpy.data.node_groups):
                pass
            else:
                before_data = list(bpy.data.node_groups)
                bpy.ops.wm.append(directory=os.path.join(os.path.dirname(__file__), 'assets', 'Shaders Plus Shaders v4 - Dev - Serpens v3.blend') + r'\NodeTree', filename=self.sna_group_name, link=False)
                new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
                appended_A08CB = None if not new_data else new_data[0]
            bpy.ops.node.add_node('INVOKE_DEFAULT', use_transform=True, type='ShaderNodeGroup')
            bpy.context.active_node.node_tree = bpy.data.node_groups[self.sna_group_name]
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_boolean = bpy.props.BoolProperty(name='Boolean', description='', default=True)
    bpy.types.Scene.sna_boolean_2 = bpy.props.BoolProperty(name='Boolean 2', description='', default=True)
    bpy.utils.register_class(SNA_MT_3D3C8)
    bpy.utils.register_class(SNA_MT_7837C)
    bpy.utils.register_class(SNA_MT_763B5)
    bpy.utils.register_class(SNA_MT_66B50)
    bpy.utils.register_class(SNA_MT_CCD2A)
    bpy.utils.register_class(SNA_MT_D3AD1)
    bpy.utils.register_class(SNA_MT_C3262)
    bpy.utils.register_class(SNA_MT_EE7C9)
    bpy.utils.register_class(SNA_MT_5B96D)
    bpy.utils.register_class(SNA_MT_A31A6)
    bpy.utils.register_class(SNA_MT_8F795)
    bpy.utils.register_class(SNA_MT_3C1F0)
    bpy.utils.register_class(SNA_AddonPreferences_F7BC4)
    bpy.types.NODE_MT_editor_menus.append(sna_add_to_node_mt_editor_menus_AAC66)
    bpy.types.NODE_MT_context_menu.append(sna_add_to_node_mt_context_menu_591BC)
    bpy.types.NODE_MT_add.append(sna_add_to_node_mt_add_A42E2)
    bpy.utils.register_class(SNA_OT_Loadgroupop_1C98D)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_boolean_2
    del bpy.types.Scene.sna_boolean
    bpy.utils.unregister_class(SNA_MT_3D3C8)
    bpy.utils.unregister_class(SNA_MT_7837C)
    bpy.utils.unregister_class(SNA_MT_763B5)
    bpy.utils.unregister_class(SNA_MT_66B50)
    bpy.utils.unregister_class(SNA_MT_CCD2A)
    bpy.utils.unregister_class(SNA_MT_D3AD1)
    bpy.utils.unregister_class(SNA_MT_C3262)
    bpy.utils.unregister_class(SNA_MT_EE7C9)
    bpy.utils.unregister_class(SNA_MT_5B96D)
    bpy.utils.unregister_class(SNA_MT_A31A6)
    bpy.utils.unregister_class(SNA_MT_8F795)
    bpy.utils.unregister_class(SNA_MT_3C1F0)
    bpy.utils.unregister_class(SNA_AddonPreferences_F7BC4)
    bpy.types.NODE_MT_editor_menus.remove(sna_add_to_node_mt_editor_menus_AAC66)
    bpy.types.NODE_MT_context_menu.remove(sna_add_to_node_mt_context_menu_591BC)
    bpy.types.NODE_MT_add.remove(sna_add_to_node_mt_add_A42E2)
    bpy.utils.unregister_class(SNA_OT_Loadgroupop_1C98D)
