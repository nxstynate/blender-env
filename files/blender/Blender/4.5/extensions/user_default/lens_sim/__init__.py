'''
    Lens Sim
    Copyright (C) 2024 Håvard Krutå Dalen
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program. If not, see <https://www.gnu.org/licenses/>.
'''

import bpy
import bpy_extras
import os
import mathutils
import webbrowser
#import re
#import math
import shutil

# open_file(path):
import platform
import subprocess

import math
import numpy as np

from bl_ui.space_toolsystem_common import ToolSelectPanelHelper

#import bpy
from bpy.types import Panel, EnumProperty, WindowManager
import bpy.utils.previews




#
# global parameters
#

LensSim_Version = "(1, 0, 0)"

LensSim_MaxLenses = 15
LensSim_RackFocusLUTSize = 40

LensSim_CameraExists = False
LensSim_Camera = None
LensSim_LensMesh = None
#LensSim_LensDirtMesh = None
LensSim_DofEmptyParent = None
#LensSim_DofEmpty = None
LensSim_LensMaterial = None

LensSim_LensMaterialName = "LensSimMaterial"
LensSim_LensDirtName = "LensDirtSurface"
LensSim_LensDirtMaterialName = "LensSimDirtMaterial"
LensSim_DofEmptyName = "LensSim_Focus_Empty"
LensSim_CollectionName = "LensSim_Collection"
LensSim_CameraName = "LensSim_Camera"
LensSim_LensMeshName = "LensVisualize"


LensSim_ViewportModeLock = False
LensSim_IsRendering = False

LensSim_QuestionIcon = "QUESTION" #"INFO" #"HELP"

#
#
#LensSim_DataFolder = "\\LensSim_Data"
LensSim_DataFolder = os.path.join("LensSim_Data")
#
#

#LensSim_LensesFolder = "\\lenses"
#LensSim_CameraFolder = "\\camera"
#LensSim_TextureFolder = "\\textures"
#LensSim_BokehFolder = "\\bokeh"
#LensSim_LensesFolder = os.path.join(LensSim_DataFolder, "lenses")
#LensSim_CameraFolder = os.path.join(LensSim_DataFolder, "camera")
#LensSim_TextureFolder = os.path.join(LensSim_DataFolder, "textures")
#LensSim_BokehFolder = os.path.join(LensSim_TextureFolder, "bokeh")

LensSim_LensesFolder = os.path.join("lenses")
LensSim_CameraFolder = os.path.join("camera")
LensSim_TextureFolder = os.path.join("textures")
LensSim_BokehFolder = os.path.join(LensSim_TextureFolder, "bokeh")

## FIX
LensSim_CameraFile = os.path.join("camera.blend")

LensSim_FavoritesFileName = "_favorites.txt"

#LensSim_CameraName = "LensSimCamera"
#LensSim_LensMeshName = "LensSimLens"


# folder structure
#LensSim_LensesFolder    = LensSim_DataFolder + LensSim_LensesFolder
#LensSim_CameraFolder    = LensSim_DataFolder + LensSim_CameraFolder
#LensSim_TextureFolder   = LensSim_DataFolder + LensSim_TextureFolder
#LensSim_BokehFolder     = LensSim_TextureFolder + LensSim_BokehFolder

LensSim_LensesFolder    = os.path.join(LensSim_DataFolder, LensSim_LensesFolder)
LensSim_CameraFolder    = os.path.join(LensSim_DataFolder, LensSim_CameraFolder)
LensSim_TextureFolder   = os.path.join(LensSim_DataFolder, LensSim_TextureFolder)
LensSim_BokehFolder     = os.path.join(LensSim_DataFolder, LensSim_BokehFolder)


LensSim_NodeTraceStart = "TraceLensStart"
LensSim_NodeTraceEnd = "TraceLensEnd"
LensSim_NodeTraceFocusStart = "TraceFocusStart"
LensSim_NodeTraceFocusEnd = "TraceFocusEnd"
LensSim_NodeSchematicStart = "SchematicStart"
LensSim_NodeSchematicEnd = "SchematicEnd"

LensSim_BaseName = "LensSim_"
LensSim_NodeAperture = LensSim_BaseName + "Aperture"
LensSim_NodeSphericalLens = LensSim_BaseName + "SphericalLens"
LensSim_NodeCylindricalLens = LensSim_BaseName + "CylindricalLens"
LensSim_NodeAsphericalLens = LensSim_BaseName + "AsphericalLens"
LensSim_NodeSchematic = LensSim_BaseName + "Schematic"

LensSim_CameraCollection = "LensSimCollection"

LensSim_DefaultCamera = "85mm f1.5 Canon Serenar.txt"

LensSim_CalcButtonFactor = 0.8


#
# functions
#



def open_file(path):
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":  # macOS
        subprocess.run(["open", path])
    elif platform.system() == "Linux":  # Linux
        subprocess.run(["xdg-open", path])
    else:
        raise OSError("Unsupported operating system.")
        

def get_selected_objects():
    selected_objects = bpy.context.selected_objects
    return selected_objects

def is_camera(obj):
    return obj.type == 'CAMERA'

def is_LensSimCamera(camera):
    global LensSim_LensMaterial
    global LensSim_Camera
    global LensSim_LensMesh
    #global LensSim_DofEmpty
    global LensSim_DofEmptyParent
    global LensSim_CameraExists
    
    LensSim_Camera_old = LensSim_Camera
    
    try:
        # Check each child object of the camera
        for child in camera.children:
            # Check if the child is a mesh object
            if child.type == 'MESH':
                for mat in child.data.materials:
                    if mat.name.startswith( LensSim_LensMaterialName ):
                        for childd in child.children:
                            if childd.type == 'EMPTY':
                                
                                # dof parent node
                                LensSim_DofEmptyParent = childd
                                
                                #for childdd in childd.children:
                                    #if childdd.type == 'EMPTY':

                                        #if childdd.name.startswith( LensSim_DofEmptyName ):
                                            
                                            #LensSim_DofEmpty = childdd
                                LensSim_LensMaterial = mat
                                LensSim_LensMesh = child
                                LensSim_Camera = camera
                                LensSim_CameraExists = True
                                
                                if LensSim_Camera_old != LensSim_Camera:
                                    on_camera_change()
                                
                                return True
    except:
        pass

    LensSim_LensMaterial = None
    #LensSim_DofEmpty = None
    LensSim_DofEmptyParent = None
    LensSim_LensMesh = None
    LensSim_CameraExists = False
    
    if LensSim_Camera_old != LensSim_Camera:
        on_camera_change()
    
    return False

def camera_exists():
    global LensSim_CameraExists
    global LensSim_Camera
    
    props = bpy.context.scene.my_addon_props
    pinned = getattr(props, "pin_camera" )

    
    if pinned:
        
        if is_LensSimCamera(LensSim_Camera):
            LensSim_CameraExists = True
            return True
        
        '''
        camera_exists = True

        # if material exists
        try:
            material_name = LensSim_LensMaterial.name
        except:
            LensSim_CameraExists = False
            camera_exists = False
        
        try:
            test = LensSim_LensMesh.hide_render
        except:
            LensSim_CameraExists = False
            camera_exists = False

        # if camera exists
        try:
            camera_name = LensSim_Camera.name
        except:
            LensSim_CameraExists = False
            camera_exists = False
        
        #if camera_exists:
            if is_LensSimCamera(LensSim_Camera):
                return True
        '''
    camera = None
    
    selection = get_selected_objects()
    for obj in selection:
        if is_camera(obj):
            camera = obj
            break
    
    if camera == None:
        LensSim_CameraExists = False
        return False
    else:
        if is_LensSimCamera(camera):
            LensSim_CameraExists = True
            return True
        else:
            LensSim_CameraExists = False
            return False
        

    '''
    #return False
    if LensSim_LensMaterialName in bpy.data.materials:
        LensSim_CameraExists = True
        return True
    else:
        LensSim_CameraExists = False
        return False
    '''
    
def get_script_folder_path():
    
    script_path = os.path.realpath(__file__)
    script_path_folder = os.path.dirname(script_path)

    if script_path_folder.endswith(".blend"):
        script_path_folder = os.path.dirname(script_path_folder)

    return script_path_folder

def get_lenses_path():
    
    script_path_folder = get_script_folder_path()

    #lenses_path = script_path_folder + LensSim_LensesFolder
    lenses_path = os.path.join(script_path_folder, LensSim_LensesFolder)

    #return lenses_path
    return lenses_path

def get_bokeh_path():
    
    script_path_folder = get_script_folder_path()

    #bokeh_path = script_path_folder + LensSim_BokehFolder
    bokeh_path = os.path.join(script_path_folder, LensSim_BokehFolder)

    #return bokeh_path
    
    return bokeh_path

def get_main_material():

    if LensSim_LensMaterial == None:
        return LensSim_LensMaterial
    return LensSim_LensMaterial
    '''
    if camera_exists():
        #return bpy.data.materials[LensSim_LensMaterialName]
        return LensSim_LensMaterial
    else:
        return False
    '''

def get_lens_camera_node():
    
    #main_material = get_main_material()
    main_material = LensSim_LensMaterial

    if not main_material:
        return
    
    camera_node = None
    
    try:
        camera_node = main_material.node_tree.nodes["LensSim"]
    except:
        is_LensSimCamera(LensSim_Camera)
    
    return camera_node

def get_lens_node():
    #main_material = get_main_material()
    main_material = LensSim_LensMaterial
    
    if not main_material:
        return
    
    #camera_node = get_lens_camera_node()
    #lens = camera_node.node_tree.nodes["Lens"]

    lens = main_material.node_tree.nodes["Lens"]

    return lens

def lens_enum_sort(e):
    split = e[0].split("mm f")
    if len(split) == 2:
        return int( split[0] )
    else:
        return 0































def round_float( value ):
    return round( value, 7)

def build_lens_system():

    #schematic = bpy.context.scene.my_addon_props.lens_schematic
    material = get_lens_camera_node()
    if material == None:
        return
    
    schematic = material.inputs["schematic enable"].default_value

    if schematic:
        delete_lens()
        delete_lens_focus()
        
        delete_lens_schematics()
        build_lens()
        build_lens_schematics()
        delete_lens()
        #delete_lens_focus()
        update_lens_rays()
        
    else:
        delete_lens_schematics()
        delete_lens()
        delete_lens_focus()
        build_lens()
        mute_lens_rays()

    build_lens_mesh()
    lens_dirt_surface_update()

def delete_lens_schematics():
    
    lens_data = get_lens_data(False)
    lens_node = get_lens_node()
    
    main_material = get_main_material()
    if not main_material:
        return
    
    lens_node_tree = main_material.node_tree
    

    focus_name = "LensSchematic#"    

    # delete nodes
    check_nodes = []
    for x in range(1,LensSim_MaxLenses+1,1):
        check_nodes.append( focus_name.replace("#", str(x) ) )
        
    for blastName in check_nodes:
        if blastName in lens_node_tree.nodes:
            blastNode = lens_node_tree.nodes[ blastName ]
            lens_node_tree.nodes.remove( blastNode )



def build_lens_schematics():
    
    lens_data = get_lens_data(False)
    lens_node = get_lens_node()
    
    main_material = get_main_material()
    if not main_material:
        return
    
    lens_node_tree = main_material.node_tree
    

    focus_name = "LensSchematic#"    

    '''
    # delete nodes
    check_nodes = []
    for x in range(1,LensSim_MaxLenses+1,1):
        check_nodes.append( focus_name.replace("#", str(x) ) )
        
    for blastName in check_nodes:
        if blastName in lens_node_tree.nodes:
            blastNode = lens_node_tree.nodes[ blastName ]
            lens_node_tree.nodes.remove( blastNode )
   '''     
    
    
    
    #
    # lens nodes
    #
    
    node_separation = 150.0
    #imgtx2.width = 200
    
    lenses = lens_data[0]

    
    lens_name = focus_name

    #LensSim_NodeTraceFocusStart = "TraceFocusStart"
    #LensSim_NodeTraceFocusEnd = "TraceFocusEnd"

    prew_node = lens_node_tree.nodes[ LensSim_NodeSchematicStart ]
    data_connections = len( prew_node.outputs )

    # create focus trace nodes
    for x in range(1,lenses+1,1):
        
        node_idx = x
        
        input_idx0 = node_idx*2 - 1
        input_idx1 = node_idx*2
        
        
        # add lens node
        # node group to add
        node_group = bpy.data.node_groups.get(LensSim_NodeSchematic)
        if node_group is None:
            raise ValueError(f"Node group not found.")

        # create and place node
        new_node = lens_node_tree.nodes.new(type='ShaderNodeGroup')
        
        new_node.node_tree = node_group
        new_node.location = prew_node.location
        new_node.location[0] += node_separation
        new_node.name = lens_name.replace("#", str(x) )
        new_node.label = LensSim_NodeSphericalLens[ len(LensSim_BaseName):]

        # connect nodes    
        links = lens_node_tree.links
        for i in range(0,data_connections,1):
            links.new( prew_node.outputs[i], new_node.inputs[i] )

        group_input = lens_node
        #links.new( group_input.outputs["ior" + str(node_idx)], new_node.inputs["ior"] )
        links.new( group_input.outputs["d" + str(input_idx0)], new_node.inputs["d0"] )
        links.new( group_input.outputs["d" + str(input_idx1)], new_node.inputs["d1"] )
        links.new( group_input.outputs["r" + str(input_idx0)], new_node.inputs["r0"] )
        links.new( group_input.outputs["r" + str(input_idx1)], new_node.inputs["r1"] )
        links.new( group_input.outputs["dia" + str(input_idx0)], new_node.inputs["dia0"] )
        links.new( group_input.outputs["dia" + str(input_idx1)], new_node.inputs["dia1"] )

        links.new( group_input.outputs["t" + str(node_idx)], new_node.inputs["t"] )
    
        new_node.inputs["idx"].default_value = node_idx

        prew_node = new_node


    last_node = lens_node_tree.nodes[ LensSim_NodeSchematicEnd ]
    data_connections = len( last_node.inputs )
    
    # connect nodes    
    links = lens_node_tree.links
    outputs = len(prew_node.outputs)
    #|print(outputs)
    for x in range(0,data_connections,1):
        if x < outputs:
            links.new( prew_node.outputs[x], last_node.inputs[x] )

    # connect as output
    node0 = lens_node_tree.nodes["SchematicMaterial"]
    node1 = lens_node_tree.nodes["Shader Out"]
    links.new( node0.outputs[0], node1.inputs[0] )


def delete_lens():
    
    lens_data = get_lens_data(False)
    
    lens_node = get_lens_node()
    
    main_material = get_main_material()
    if not main_material:
        return
    
    lens_node_tree = main_material.node_tree
    

    lens_name = "Lens#"
    #focus_name = "LensFocus#"
    #focus_r0_convert_name = "r0_convert#"
    #focus_r1_convert_name = "r1_convert#"
    
    aperture_name = "Aperture"
    aperture_dist_name = "ApertureDist"

    #rack_focus_name = "RackFocus#"

    # delete nodes
    check_nodes = []
    for x in range(1,LensSim_MaxLenses+1,1):
        check_nodes.append( lens_name.replace("#", str(x) ) )
        #check_nodes.append( focus_name.replace("#", str(x) ) )
        #check_nodes.append( focus_r0_convert_name.replace("#", str(x) ) )
        #check_nodes.append( focus_r1_convert_name.replace("#", str(x) ) )
        #check_nodes.append( rack_focus_name.replace("#", str(x) ) )
    check_nodes.append( aperture_name )
    check_nodes.append( aperture_dist_name )
        
    for blastName in check_nodes:
        if blastName in lens_node_tree.nodes:
            blastNode = lens_node_tree.nodes[ blastName ]
            lens_node_tree.nodes.remove( blastNode )

def delete_lens_focus():
    
    lens_data = get_lens_data(False)
    
    lens_node = get_lens_node()
    
    main_material = get_main_material()
    if not main_material:
        return
    
    lens_node_tree = main_material.node_tree
    

    #lens_name = "Lens#"
    focus_name = "LensFocus#"
    focus_r0_convert_name = "r0_convert#"
    focus_r1_convert_name = "r1_convert#"
    
    #aperture_name = "Aperture"
    #aperture_dist_name = "ApertureDist"

    #rack_focus_name = "RackFocus#"

    # delete nodes
    check_nodes = []
    for x in range(1,LensSim_MaxLenses+1,1):
        #check_nodes.append( lens_name.replace("#", str(x) ) )
        check_nodes.append( focus_name.replace("#", str(x) ) )
        check_nodes.append( focus_r0_convert_name.replace("#", str(x) ) )
        check_nodes.append( focus_r1_convert_name.replace("#", str(x) ) )
        #check_nodes.append( rack_focus_name.replace("#", str(x) ) )
    #check_nodes.append( aperture_name )
    #check_nodes.append( aperture_dist_name )
        
    for blastName in check_nodes:
        if blastName in lens_node_tree.nodes:
            blastNode = lens_node_tree.nodes[ blastName ]
            lens_node_tree.nodes.remove( blastNode )
            
            
            
      
def add_lens_node( prew_node, lens_name, lens_node_tree, lens_node, node_separation, x, node_idx ):
    
    lens_type = lens_node.inputs["t" + str(node_idx)].default_value
    
    node_group = bpy.data.node_groups.get(LensSim_NodeSphericalLens)

    if lens_type == 1 or lens_type == 2:
        node_group = bpy.data.node_groups.get(LensSim_NodeCylindricalLens)
        
    if node_group is None:
        raise ValueError(f"Node group not found.")

    # create and place node
    new_node = lens_node_tree.nodes.new(type='ShaderNodeGroup')
    
    new_node.node_tree = node_group
    new_node.location = prew_node.location
    new_node.location[0] += node_separation
    new_node.name = lens_name.replace("#", str(x) )
    
    new_node.label = LensSim_NodeSphericalLens[ len(LensSim_BaseName):]

    if lens_type == 1 or lens_type == 2:
        new_node.label = LensSim_NodeCylindricalLens[ len(LensSim_BaseName):]
        new_node.inputs["axis"].default_value = lens_type - 1
    
    return new_node
            
def build_lens():

    lens_data = get_lens_data(False)
    
    lens_node = get_lens_node()
    
    main_material = get_main_material()
    if not main_material:
        return
    
    lens_node_tree = main_material.node_tree
    

    lens_name = "Lens#"
    focus_name = "LensFocus#"
    focus_r0_convert_name = "r0_convert#"
    focus_r1_convert_name = "r1_convert#"
    
    aperture_name = "Aperture"
    aperture_dist_name = "ApertureDist"
    
    rack_focus_name = "RackFocus"

    '''
    # delete nodes
    check_nodes = []
    for x in range(1,LensSim_MaxLenses+1,1):
        check_nodes.append( lens_name.replace("#", str(x) ) )
        check_nodes.append( focus_name.replace("#", str(x) ) )
        check_nodes.append( focus_r0_convert_name.replace("#", str(x) ) )
        check_nodes.append( focus_r1_convert_name.replace("#", str(x) ) )
    check_nodes.append( aperture_name )
    check_nodes.append( aperture_dist_name )
        
    for blastName in check_nodes:
        if blastName in lens_node_tree.nodes:
            blastNode = lens_node_tree.nodes[ blastName ]
            lens_node_tree.nodes.remove( blastNode )
    '''     
    
    
    
    #
    # lens nodes
    #
    
    
    prew_node = lens_node_tree.nodes[ LensSim_NodeTraceStart ]

    node_separation = 150.0
    node_separationy_math_nodes01 = 175.0
    node_separationy_math_nodes02 = 35.0
    #imgtx2.width = 200
    
    lenses = lens_data[0]

    data_connections = len( prew_node.outputs )

    aperture_idx = lens_node.inputs.get( "aperture idx" ).default_value

    
    # create lens nodes
    for x in range(1,lenses+1,1):
        
        node_idx = lenses - x +1
        
        input_idx0 = node_idx*2 
        input_idx1 = node_idx*2 -1
        
        
        
        # add aperture
        if node_idx == aperture_idx:

            node_group = bpy.data.node_groups.get(LensSim_NodeAperture)
            if node_group is None:
                raise ValueError(f"Node group not found.")
                    # create and place node
            
            new_node = lens_node_tree.nodes.new(type='ShaderNodeGroup')
            
            new_node.node_tree = node_group
            new_node.location = prew_node.location
            new_node.location[0] += node_separation
            new_node.name = aperture_name
            new_node.label = LensSim_NodeAperture[ len(LensSim_BaseName):]
            
            # connect nodes    
            links = lens_node_tree.links
            for i in range(0,data_connections,1):
                links.new( prew_node.outputs[i], new_node.inputs[i] )

            group_input = lens_node
            links.new( group_input.outputs["aperture r"], new_node.inputs["r"] )
            
            #links.new( group_input.outputs["aperture d"], new_node.inputs["d"] )
            #links.new( group_input.outputs["aperture d"], new_node.inputs["d"] )
            
            #add math node
            math_node = lens_node_tree.nodes.new(type='ShaderNodeMath')
            math_node.operation = 'SUBTRACT'
            math_node.location[0] = new_node.location[0]
            math_node.location[1] = new_node.location[1] - node_separationy_math_nodes01
            math_node.name = aperture_dist_name
            math_node.label = math_node.name
            math_node.hide = True
            
            # connect nodes
            links.new( math_node.outputs[0], new_node.inputs["d"] )
            links.new( group_input.outputs["d" + str(input_idx0)], math_node.inputs[0] ) # NEEDS FIX! ??? check this value
            links.new( group_input.outputs["aperture d"], math_node.inputs[1] )
            
            prew_node = new_node
        
        
        
        # add lens node
        # node group to add
        
        new_node = add_lens_node(prew_node, lens_name, lens_node_tree, lens_node, node_separation, x, node_idx )

        

        # connect nodes    
        links = lens_node_tree.links
        for i in range(0,data_connections,1):
            links.new( prew_node.outputs[i], new_node.inputs[i] )

        group_input = lens_node
        links.new( group_input.outputs["ior" + str(node_idx)], new_node.inputs["ior"] )
        links.new( group_input.outputs["V" + str(node_idx)], new_node.inputs["V"] )
        links.new( group_input.outputs["r" + str(input_idx0)], new_node.inputs["r0"] )
        links.new( group_input.outputs["r" + str(input_idx1)], new_node.inputs["r1"] )
        links.new( group_input.outputs["d" + str(input_idx0)], new_node.inputs["d0"] )
        links.new( group_input.outputs["d" + str(input_idx1)], new_node.inputs["d1"] )
        links.new( group_input.outputs["dia" + str(input_idx0)], new_node.inputs["dia0"] )
        links.new( group_input.outputs["dia" + str(input_idx1)], new_node.inputs["dia1"] )
        
        
        #
        # rack focus
        #
        
        if node_idx == lens_data[7]:
            new_node.inputs["enable rack focus"].default_value = 1

        
        prew_node = new_node



    last_node = lens_node_tree.nodes[ LensSim_NodeTraceEnd ]
    data_connections = len( last_node.inputs )
    
    # connect nodes    
    links = lens_node_tree.links
    for x in range(0,data_connections,1):
        links.new( prew_node.outputs[x], last_node.inputs[x] )




    #
    # focus nodes
    #

    lens_name = focus_name

    #LensSim_NodeTraceFocusStart = "TraceFocusStart"
    #LensSim_NodeTraceFocusEnd = "TraceFocusEnd"

    prew_node = lens_node_tree.nodes[ LensSim_NodeTraceFocusStart ]
    data_connections = len( prew_node.outputs )

    # create focus trace nodes
    for x in range(1,lenses+1,1):
        
        node_idx = x
        
        input_idx0 = node_idx*2 - 1
        input_idx1 = node_idx*2
        
        
        # add lens node
        # node group to add
        
        # add lens node
        # node group to add
        new_node = add_lens_node(prew_node, lens_name, lens_node_tree, lens_node, node_separation, x, node_idx )

        
        # connect nodes    
        links = lens_node_tree.links
        for i in range(0,data_connections,1):
            links.new( prew_node.outputs[i], new_node.inputs[i] )

        group_input = lens_node
        links.new( group_input.outputs["ior" + str(node_idx)], new_node.inputs["ior"] )
        if x != 1:
            links.new( group_input.outputs["d" + str(input_idx0-1)], new_node.inputs["d0"] )
        
        links.new( group_input.outputs["d" + str(input_idx1-1)], new_node.inputs["d1"] )
        #links.new( group_input.outputs["clamp" + str(input_idx0)], new_node.inputs["clamp0"] )
        #links.new( group_input.outputs["clamp" + str(input_idx1)], new_node.inputs["clamp1"] )
        
        
        
        #add math nodes to convert r0 and r1
        math_node = lens_node_tree.nodes.new(type='ShaderNodeMath')
        math_node.operation = 'MULTIPLY'
        math_node.location[0] = new_node.location[0]
        math_node.location[1] = new_node.location[1] - node_separationy_math_nodes01
        math_node.name = focus_r0_convert_name.replace("#", str(x) )
        math_node.label = math_node.name
        math_node.hide = True
        math_node.inputs[1].default_value = -1
        
        links.new( group_input.outputs["r" + str(input_idx0)], math_node.inputs[0] )
        links.new( math_node.outputs[0], new_node.inputs["r0"] )
        
        math_node = lens_node_tree.nodes.new(type='ShaderNodeMath')
        math_node.operation = 'MULTIPLY'
        math_node.location[0] = new_node.location[0]
        math_node.location[1] = new_node.location[1] - node_separationy_math_nodes01 - node_separationy_math_nodes02
        math_node.name = focus_r1_convert_name.replace("#", str(x) )
        math_node.label = math_node.name
        math_node.hide = True
        math_node.inputs[1].default_value = -1
        
        links.new( group_input.outputs["r" + str(input_idx1)], math_node.inputs[0] )
        links.new( math_node.outputs[0], new_node.inputs["r1"] )
        
        
        #
        # rack focus
        #
        
        if node_idx == lens_data[7]+1 and lens_data[7] != 0:
            new_node.inputs["enable rack focus"].default_value = 1
        
        prew_node = new_node



    last_node = lens_node_tree.nodes[ LensSim_NodeTraceFocusEnd ]
    data_connections = len( last_node.inputs )
    
    # connect nodes    
    links = lens_node_tree.links
    for x in range(0,data_connections,1):
        links.new( prew_node.outputs[x], last_node.inputs[x] )




    # connect as output
    node0 = lens_node_tree.nodes["LensMaterial"]
    node1 = lens_node_tree.nodes["Shader Out"]
    links.new( node0.outputs[0], node1.inputs[0] )



















def get_lens_visualize_mesh():

    # delete old mesh
    # Check each child object of the camera
    for child in LensSim_Camera.children:
        # Check if the child is a mesh object
        if child.type == 'MESH':
            #if child.name.startswith( LensSim_LensMeshName ):
            #print( child )
            for mat in child.data.materials:
                
                if mat.name.startswith( LensSim_LensMaterialName ):
                    
                    for childd in child.children:
                        if childd.name.startswith( LensSim_LensMeshName ):
                            return childd
    return None






def get_lens_dirt_surface():

    # delete old mesh
    # Check each child object of the camera
    for child in LensSim_Camera.children:
        # Check if the child is a mesh object
        if child.type == 'MESH':
            #if child.name.startswith( LensSim_LensMeshName ):
            #print( child )
            for mat in child.data.materials:
                
                if mat.name.startswith( LensSim_LensMaterialName ):
                    
                    for childd in child.children:
                        if childd.type == 'MESH':

                            for mat in childd.data.materials:
                                
                                if mat.name.startswith( LensSim_LensDirtMaterialName ):
                                    #LensMesh = childd
                                    return childd
    return None

def get_lens_dirt_surface_material():
    
    obj = get_lens_dirt_surface()

    if obj == None:
        return None

    for mat in obj.data.materials:
        if mat.name.startswith( LensSim_LensDirtMaterialName ):
            return mat
    return None

def create_lens_dirt_surface():
    

    node = get_lens_camera_node()
    if node == None:
        return


    # remove if turned off
    if not node.inputs["lens dirt object enable"].default_value:
        try:
            object = get_lens_dirt_surface()
            bpy.data.objects.remove( object , do_unlink=True)
            return
        except:
            pass
        return
    
    
    # get lens mesh for parent
    LensMesh = None

    # delete old mesh
    # Check each child object of the camera
    for child in LensSim_Camera.children:
        # Check if the child is a mesh object
        if child.type == 'MESH':
            #if child.name.startswith( LensSim_LensMeshName ):
            #print( child )
            for mat in child.data.materials:
                
                if mat.name.startswith( LensSim_LensMaterialName ):
                    LensMesh = child

    if LensMesh == None:
        return
        
        
    distance_offset = node.inputs["lens dirt object distance"].default_value
    diameter_padding = 0.02
    
    lens_surface_name = LensSim_LensDirtName
    lens_surface_material_name = LensSim_LensDirtMaterialName


        
        
        
    lens_data = get_lens_data(False)
    
    # Define parameters
    global_scale = node.inputs["global scale"].default_value
    
    radius = lens_data[2][0] * global_scale
    diameter = lens_data[6][0] * global_scale
    lens_length = lens_data[1] * global_scale
    
    
    
    # add offsets
    radius += distance_offset
    diameter += distance_offset + diameter_padding
    
    divisions = 32   # Number of divisions for the surface
    
    
    lens_obj = get_lens_dirt_surface()
    lens_mesh = None
    build_from_scratch = True
    
    if lens_obj == None:
        # Create a new mesh and object if it doesn't exist
        lens_mesh = bpy.data.meshes.new(lens_surface_name)
        lens_obj = bpy.data.objects.new(lens_surface_name, lens_mesh)
        
        # Link the object to the scene
        bpy.context.collection.objects.link(lens_obj)
    else:
        #lens_obj = LensMesh
        lens_mesh = lens_obj.data
        # Clear the existing mesh
        lens_mesh.clear_geometry()
        build_from_scratch = False
    


    scale = node.inputs["lens dirt object scale"].default_value
    lens_obj.scale[0] = scale
    lens_obj.scale[1] = scale
    lens_obj.scale[2] = scale

    # Replace 'ChildObject' and 'ParentObject' with the names of your objects
    #child_object_name = 'ChildObject'
    #parent_object_name = 'ParentObject'

    # Get the objects
    child_object = lens_obj
    parent_object = LensMesh

    if build_from_scratch:

        if child_object and parent_object:
            # Parent the child object to the parent object
            child_object.parent = parent_object
            
            # Clear existing collections in the child object
            for collection in child_object.users_collection:
                collection.objects.unlink(child_object)
            
            # Copy collections from the parent object to the child object
            for collection in parent_object.users_collection:
                if child_object.name not in collection.objects:
                    collection.objects.link(child_object)



    # set transformations
    lens_obj.location = (0,0, -lens_length - distance_offset )
    lens_obj.rotation_euler = (math.radians(180), 0, 0)

    # Create the vertices and faces for one side of the lens surface
    vertices = []
    faces = []

    # Cutoff distance (half of the diameter)
    cutoff_radius = diameter / 2

    # Calculate the maximum polar angle for the cutoff
    cutoff_angle = math.asin(cutoff_radius / radius)

    # Create vertices
    for i in range(divisions + 1):
        # Polar angle from 0 to cutoff_angle
        polar_angle = cutoff_angle * (i / divisions)
        
        x = radius * math.sin(polar_angle)  # Horizontal distance from z-axis
        z = radius * math.cos(polar_angle)  # Height from the center

        # Add the center point at the top (apex of the spherical cap)
        if i == 0:
            vertex = (0, 0, radius - radius)  # Center vertex at the top of the sphere
            vertices.append(vertex)
        else:
            # Create a circular ring around the center for each level of the surface
            for j in range(divisions):
                theta = 2 * math.pi * j / divisions  # Azimuthal angle (around the z-axis)
                x_ring = x * math.cos(theta)
                y_ring = x * math.sin(theta)
                
                vertex = (x_ring, y_ring, z - radius)
                vertices.append(vertex)

    # Create faces for the surface using the generated vertices
    for i in range(1, divisions + 1):
        for j in range(divisions):
            next_j = (j + 1) % divisions
            if i == 1:
                # Faces that connect the center vertex to the first ring
                faces.append([j + 1, next_j + 1, 0])
            else:
                # Faces that connect rings
                start_idx = (i - 2) * divisions + 1  # Start index of the previous ring
                cur_idx = (i - 1) * divisions + 1    # Start index of the current ring
                # Reverse the order of vertices for consistent face normals
                faces.append([start_idx + next_j, start_idx + j, cur_idx + j, cur_idx + next_j])
    
    # Create the mesh from vertices and faces
    lens_mesh.from_pydata(vertices, [], faces)
    lens_mesh.update()

    # Set UVs
    # Create a UV map
    uv_layer = lens_mesh.uv_layers.new(name="UVMap")
    for poly in lens_mesh.polygons:
        for loop_index in poly.loop_indices:
            loop = lens_mesh.loops[loop_index]
            vertex = vertices[loop.vertex_index]

            # Calculate UV coordinates
            #u = 0.5 + math.atan2(vertex[1], vertex[0]) / (2 * math.pi)  # Circular mapping
            #v = (vertex[2] + radius) / (2 * radius)  # Map height to [0, 1]
            
            u = (vertex[0] * (1.0/diameter) + 0.5)
            v = (vertex[1] * (1.0/diameter) + 0.5)
            
            # Assign the UV coordinates to the UV layer
            uv_layer.data[loop.index].uv = (u, v)

    # Smooth shading
    for poly in lens_mesh.polygons:
        poly.use_smooth = True


    if build_from_scratch:

        # Add a material (create if not exists)
        material_name = lens_surface_material_name
        if material_name in bpy.data.materials:
            mat = bpy.data.materials[material_name]
        else:
            mat = bpy.data.materials.new(name=material_name)

        # Assign material to the object
        if len(lens_obj.data.materials) == 0:
            lens_obj.data.materials.append(mat)
        else:
            lens_obj.data.materials[0] = mat

        '''
        # Set some basic material properties (you can adjust these as needed)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1)  # Light grey color
            bsdf.inputs['Roughness'].default_value = 0.2  # Slightly shiny surface
        '''

        # Enable 'Use Nodes'
        mat.use_nodes = True
        nodes = mat.node_tree.nodes

        # Clear existing nodes
        for node in nodes:
            nodes.remove(node)

        # Create necessary nodes
        output_node = nodes.new(type='ShaderNodeOutputMaterial')
        #output_node = mat.node_tree.nodes.get("Material Output")
        bsdf_node = nodes.new(type='ShaderNodeBsdfPrincipled')
        #bsdf_node = mat.node_tree.nodes.get("Principled BSDF")
        texture_node = nodes.new(type='ShaderNodeTexImage')  # Change to your desired texture node type
        rgb_curves_node = nodes.new(type='ShaderNodeRGBCurve')
        mix_node01 = nodes.new(type='ShaderNodeMix')
        mix_node02 = nodes.new(type='ShaderNodeMix')
        map_range_node = nodes.new(type='ShaderNodeMapRange')
        mix_shader_node = nodes.new(type='ShaderNodeMixShader')
        geometry_node = nodes.new(type='ShaderNodeNewGeometry')
        
        texture_coordinate_node = nodes.new(type='ShaderNodeTexCoord')
        mapping_node = nodes.new(type='ShaderNodeMapping')
        
        mix_node01.name = "AdditiveOpacity"
        mix_node02.name = "SubtractOpacity"
        
        # Set node locations for alignment
        texture_coordinate_node.location    = (-300, 0)
        mapping_node.location               = (-150, 0)
        texture_node.location               = (0, 0)
        
        rgb_curves_node.location            = (300, 0)
        mix_node01.location                 = (600, -100)
        geometry_node.location              = (600, 300)
        bsdf_node.location                  = (900, 0)
        
        mix_node02.location                 = (900, 300)
        map_range_node.location             = (1200, 300)
        
        mix_shader_node.location            = (1500, 0)
        output_node.location                = (1700, 0)
        
        
        
        # Connect nodes
        links = mat.node_tree.links
        links.new(texture_node.outputs['Color'], rgb_curves_node.inputs["Color"])
        links.new(rgb_curves_node.outputs[0], bsdf_node.inputs['Base Color'])
        
        links.new(rgb_curves_node.outputs[0], mix_node01.inputs['B'])
        links.new(mix_node01.outputs[0], bsdf_node.inputs['Alpha'])
        
        links.new(geometry_node.outputs["Incoming"], bsdf_node.inputs['Normal'])

        links.new(rgb_curves_node.outputs[0], map_range_node.inputs['Value'])
        links.new(mix_node02.outputs[0], map_range_node.inputs['To Max'])

        links.new(map_range_node.outputs[0], mix_shader_node.inputs[0])
        links.new(bsdf_node.outputs['BSDF'], mix_shader_node.inputs[2])
        links.new(mix_shader_node.outputs[0], output_node.inputs['Surface'])

        links.new(texture_coordinate_node.outputs["UV"], mapping_node.inputs[0])
        links.new(mapping_node.outputs[0], texture_node.inputs[0])

        # Set properties of nodes
        bsdf_node.inputs['Transmission Weight'].default_value = 1.0
        bsdf_node.inputs['Roughness'].default_value = 0.2
        bsdf_node.inputs['Specular Tint'].default_value = (0,0,0,1)

        mix_node02.inputs["A"].default_value = 1.0
        mix_node02.inputs["B"].default_value = 0.0
        
        map_range_node.inputs["To Min"].default_value = 1.0

        mix_node01.inputs[0].default_value = 1.0
        mix_node02.inputs[0].default_value = 1.0
        
        mapping_node.vector_type = 'TEXTURE'



        # set viewport visibility
        #lens_obj = bpy.data.objects[plane_obj.name]
        lens_obj.display_type = "BOUNDS"
        lens_obj.display_bounds_type = "CAPSULE"
        lens_obj.display.show_shadows = False
        lens_obj.visible_diffuse = False
        lens_obj.visible_glossy = False
        lens_obj.visible_transmission = False
        lens_obj.visible_volume_scatter = False
        lens_obj.visible_shadow = False
        lens_obj.hide_select = True


def lens_dirt_surface_update():
    
    camera = LensSim_Camera
    
    create_lens_dirt_surface()

    is_LensSimCamera(camera)



































def get_installed_lenses(self, context):

    #context.scene.my_addon_props.auto_import = "85mm f1.5 Canon Serenar.txt"

    favorite_lenses = get_favorites()

    lenses_path = get_lenses_path()
    
    items = []
    if os.path.exists(lenses_path):
        for file in os.listdir(lenses_path):
            if file.endswith(".txt"):
                
                label = (file[:-4]).strip()
                
                if label == LensSim_FavoritesFileName[:-4]:
                    continue
                
                if label in favorite_lenses:
                    items.append((file, label, "", "FUND", len(items)))
                else:
                    items.append((file, label, "", "BLANK1", len(items)))
                
                #items.append((file, label, ""))
                
    items.sort( reverse=True, key=lens_enum_sort )
    return items



   
def update_bokeh_enum(self, context):

    #context.scene.my_addon_props.auto_import = "85mm f1.5 Canon Serenar.txt"

    bokeh_path = get_bokeh_path()
    items = []
    if os.path.exists(bokeh_path):
        for file in os.listdir(bokeh_path):
            #if file.endswith(".txt"):
            label = file[:-4]
            #if LensSim_LensEnumOverride != None:

            items.append((file, label, ""))
            
    #items.sort( reverse=True, key=lens_enum_sort )
    return items


def average_pixel_value( texture, gamma ):

    # Ensure the image is loaded and has valid pixel data
    #if texture_node and texture_node.has_data:

    # Get the pixel data
    pixels = np.array(texture.pixels[:])  # Copy the pixel data to a numpy array

    # The image pixels are stored in a flat array in RGBA format
    # If you want to consider only the RGB values (ignoring Alpha)
    # Reshape the array to be (width * height, 4) where 4 represents R, G, B, A

    pixels = pixels.reshape((-1, 4))
    
    pixels[:, :3] = pow(pixels[:, :3],gamma)
    
    
    '''
    # Separate RGB and Alpha channels
    rgb = pixels[:, :3]
    alpha = pixels[:, 3]

    # Apply brightness and contrast
    rgb = ((rgb - 0.5) * (contrast + 1.0)) + 0.5  # Adjust contrast
    rgb = rgb + brightness  # Apply brightness

    # Apply gamma correction (gamma > 1 makes image darker, gamma < 1 makes image brighter)
    rgb = np.power(rgb, gamma)

    # Clip values to be in the range [0, 1] to prevent overflows
    rgb = np.clip(rgb, 0, 1)

    # Compute the average RGB values
    avg_rgb = np.mean(rgb, axis=0)

    #avg_rgb += brightness
    
    '''
    #pixels = pixels.ravel()
    
    # Compute the average RGB values
    avg_rgb = np.mean(pixels[:, :3], axis=0)
    
    #print( avg_rgb )
    
    # If you want to include Alpha in the average, you can use:
    # avg_rgba = np.mean(pixels, axis=0)
    
    #print( texture.colorspace_settings.name )
    
    return avg_rgb


def white_color_sum( image_data, vector_input, gamma ):

    reference_value = 0.7854 # surface area of a circle inside a square

    pixel_avg_value = average_pixel_value( image_data, gamma )

    if np.isnan( pixel_avg_value[0] ) or np.isnan( pixel_avg_value[1] ) or np.isnan( pixel_avg_value[2] ):

        vector_input.default_value[0] = reference_value
        vector_input.default_value[1] = reference_value
        vector_input.default_value[2] = reference_value
    
    else:
        vector_input.default_value[0] = reference_value / pixel_avg_value[0]
        vector_input.default_value[1] = reference_value / pixel_avg_value[1]
        vector_input.default_value[2] = reference_value / pixel_avg_value[2]


def unit_intensity_sum( image_data, vector_input, gamma ):

    reference_value = 0.7854 # surface area of a circle inside a square

    pixel_avg_value = average_pixel_value( image_data, gamma )

    if np.isnan( pixel_avg_value[0] ) or np.isnan( pixel_avg_value[1] ) or np.isnan( pixel_avg_value[2] ):

        vector_input.default_value[0] = reference_value
        vector_input.default_value[1] = reference_value
        vector_input.default_value[2] = reference_value
    
    else:
        
        intensity_sum = ( pixel_avg_value[0] + pixel_avg_value[1] + pixel_avg_value[2] ) / 3.0
        
        vector_input.default_value[0] = reference_value / intensity_sum
        vector_input.default_value[1] = reference_value / intensity_sum
        vector_input.default_value[2] = reference_value / intensity_sum

def sync_bokeh_ui():

    try:
        name = LensSim_LensMaterial.name
    except:
        return

    image = bpy.context.scene.my_thumbnails
    
    texture = None
    
    try:
        texture = LensSim_LensMaterial.node_tree.nodes["BokehImage"].image.name
    except:
        return
    
    try:
        if image != texture:
            bpy.context.scene.my_thumbnails = texture
    except:
        return

def on_bokeh_enum_change(self, context):
    
    image_name = bpy.context.scene.my_thumbnails
    
    image_path = get_bokeh_path() + "\\" + image_name
    
    texture_node = LensSim_LensMaterial.node_tree.nodes["BokehImage"]
    
    # set relative
    #image_path = bpy.path.relpath( image_path )
    
    #print( image_path )
    
    # append image
    if image_name in bpy.data.images:

        texture_node.image = bpy.data.images[ image_name ]
    else:
        new_image = bpy.data.images.load( image_path )
        texture_node.image = new_image

    math_node = LensSim_LensMaterial.node_tree.nodes["BokehImageMultiplier"].inputs[1]
    
    gamma = 1.0
    
    white_color_sum( bpy.data.images[ image_name ], math_node, gamma )
  
    #bpy.data.materials["LensSimMaterial"].node_tree.nodes["BokehImageMultiplier"].inputs[1].default_value[0]
    
def get_current_lens():

    main_material = get_main_material()
    nodes = main_material.node_tree.nodes
    
    link_parm = ""
    
    for x in range(20):
        link_node_name = "LensFile"+str(x)
        if link_node_name in nodes:
            link_node = main_material.node_tree.nodes[ link_node_name ]

            link_parm = link_parm + link_node.label

        else:
            break
        
    return link_parm + ".txt"

def set_current_lens( name ):

    main_material = get_main_material()
    nodes = main_material.node_tree.nodes

    # max label length
    #1234567890 1234567890 1234567890 1234567890 123456780 1234567890 1234

    lens_name = name

    lens_name = lens_name.replace(".txt", "")

    letter_idx = 0
    path_length = len( lens_name )

    max_node_label_length = 60

    for x in range(20):
        link_node_name = "LensFile"+str(x)
        if link_node_name in nodes:
            link_node = main_material.node_tree.nodes[ link_node_name ]
            
            link_node.label = ""
            label = ""
            
            for l in lens_name:
                if len(label) < max_node_label_length:
                    
                    if letter_idx < path_length:
                        label = label + lens_name[ letter_idx ]
                        letter_idx += 1
            
            link_node.label = label
        else:
            break
        

def on_lens_enum_change(self, context):
    
    # create lens if not already created
    current_lens = get_current_lens()
    
    props = context.scene.my_addon_props
    if props.lenses_enum != current_lens:
        
        # import lens
        operator = bpy.ops.object.import_lens('INVOKE_DEFAULT')
    



def get_lens_data( use_global_scale ):

    lens_camera_node = get_lens_camera_node()
    if lens_camera_node == None:
        return

    lenses_path = get_lenses_path()
    lens_node = get_lens_node()    

    
    r = []
    d = []
    ior = []
    t = []
    dia = []

    unit_scale = lens_node.inputs.get( "unit scale" ).default_value
    if use_global_scale:
        unit_scale *= lens_camera_node.inputs.get( "global scale" ).default_value

    for x in range(1,(LensSim_MaxLenses*2) + 1):
        r.append( lens_node.inputs.get( "r" + str(x) ).default_value * unit_scale )
        d.append( lens_node.inputs.get( "d" + str(x) ).default_value * unit_scale )
        diav = lens_node.inputs.get( "dia" + str(x) ).default_value * unit_scale
        if diav == 0.0:
            diav = 100000.0
        dia.append( diav )
    for x in range(1,LensSim_MaxLenses + 1):
        get_ior = lens_node.inputs.get( "ior" + str(x) ).default_value
        if get_ior == 0.0:
            ior.append( 1.0 )
        else:
            ior.append( get_ior )
        t.append( lens_node.inputs.get( "t" + str(x) ).default_value )

    lenses = 0
    lens_length = 0.0
    for x in range(0,len(r),1):
        lens_length += d[x]
        if r[x] != 0.0:
            lenses += 1
        else:
            break
    lenses = int( lenses/2 )
    
    rack_focus_idx = lens_node.inputs.get( "rack focus idx" ).default_value
    rack_focus = lens_camera_node.inputs.get( "rack focus" ).default_value * 0.001

    if rack_focus_idx > 0:
        lens_length += rack_focus
        
        d_idx = (rack_focus_idx*2)-1
        d[d_idx] += rack_focus
    
    return [ lenses, lens_length, r, d, ior, t, dia, rack_focus_idx, rack_focus ]


def lens_data_override_rack_focus( lens_data, rack_focus ):

    rack_focus_idx = lens_data[7]

    if rack_focus_idx > 0:
        
        d_idx = (rack_focus_idx*2)-1

        lens_data[1] -= lens_data[8] # lens length
        lens_data[3][d_idx] -= lens_data[8] # lens d
        
        lens_data[1] += rack_focus
        lens_data[3][d_idx] += rack_focus
        
    return lens_data

def lens_data_copy( lens_data ):
    copy = []
    for i in lens_data:

        if isinstance(i, float):
            copy.append( float(i) )
        elif isinstance(i, int):
            copy.append( int(i) )
        else:
            arr = []
            for x in i:
                if isinstance(x, float):
                    arr.append( float(x) )
                if isinstance(x, int):
                    arr.append( int(x) )
            copy.append( arr )
    
    return copy
        
'''
def get_animation_data( prop, prop_name, context, self):

    # Check if the property is found
    if prop is not None:
        # Access the animation data of the scene
        anim_data = context.scene.animation_data

        if anim_data and anim_data.action:
            # Access the fcurves from the action
            for fcurve in anim_data.action.fcurves:
                if fcurve.data_path.endswith(prop_name):
                    print("Found FCurve for property:", prop_name)
                    for keyframe_point in fcurve.keyframe_points:
                        print("Keyframe frame:", keyframe_point.co[0], "Value:", keyframe_point.co[1])
        else:
            print("No animation data found for this property.")
    else:
        print("Property not found.")



def copy_animation_data(source_property, target_node, target_input_name):
    """
    Copies animation data from a source property to a specified node input property.

    :param source_property: Name of the source property (e.g., "fstop").
    :param target_node: The target node object (e.g., a ShaderNode).
    :param target_input_name: Name of the input on the target node (e.g., "F-Stop").
    """
    # Access source property animation data from the scene
    source_anim_data = bpy.context.scene.animation_data

    if source_anim_data and source_anim_data.action:
        source_fcurves = [fcurve for fcurve in source_anim_data.action.fcurves if fcurve.data_path.endswith(source_property)]

        if source_fcurves:
            node_tree = target_node.id_data
            
            if node_tree:
                # Ensure the node tree has animation data
                if not node_tree.animation_data:
                    node_tree.animation_data_create()
                
                # Create a new action for the node tree if it doesn't have one
                if not node_tree.animation_data.action:
                    node_tree.animation_data.action = bpy.data.actions.new(name="NodeTreeAction")
                
                node_tree_action = node_tree.animation_data.action
                
                # Find the input index from the input name
                input_index = None
                for i, input in enumerate(target_node.inputs):
                    if input.name == target_input_name:
                        input_index = i
                        break
                
                if input_index is None:
                    print(f"Input '{target_input_name}' not found on node '{target_node.name}'.")
                    return
                
                # Prepare the data path for the target input
                data_path = f'nodes["{target_node.name}"].inputs[{input_index}].default_value'
                
                # Check if the F-Curve already exists in the node tree action
                existing_fcurve = None
                for fcurve in node_tree_action.fcurves:
                    if fcurve.data_path == data_path:
                        existing_fcurve = fcurve
                        break
                
                # If the F-Curve exists, clear its keyframes
                if existing_fcurve:
                    existing_fcurve.keyframe_points.clear()
                    new_fcurve = existing_fcurve
                else:
                    # Create a new F-Curve if it doesn't exist
                    new_fcurve = node_tree_action.fcurves.new(data_path=data_path, index=0)
                
                # Copy keyframes
                for source_fcurve in source_fcurves:
                    for keyframe_point in source_fcurve.keyframe_points:
                        new_fcurve.keyframe_points.insert(keyframe_point.co[0], keyframe_point.co[1])
                    
                    print(f"Copied animation from {source_property} to {data_path}.")
            else:
                print("Target node tree not found.")
        else:
            print("Source property has no animation data.")
    else:
        print("Source property animation data not found.")
'''


def focusing_screen_update(self, context):
    
    main_material = get_main_material()
    if not main_material:
        return
    
    main_material_tree = main_material.node_tree
    
    focusing_screen0 = context.scene.my_addon_props.focusing_screen0
    focusing_screen1 = context.scene.my_addon_props.focusing_screen1

    if focusing_screen0 != False:
        main_material_tree.nodes["LensSim"].inputs["focusing screen"].default_value = False
        context.scene.my_addon_props.focusing_screen0 = False
    if focusing_screen1 != True:
        main_material_tree.nodes["LensSim"].inputs["focusing screen"].default_value = True
        context.scene.my_addon_props.focusing_screen1 = True


def focus_empty_visibility( state ):
    
    dof_object = get_dof_empty_object()
    
    if dof_object != None:
        if state == "0":
            dof_object.hide_viewport = False
        else:
            dof_object.hide_viewport = True


def internal_rotation_update(self, context):
    
    main_material = get_main_material()
    if not main_material:
        return
    
    main_material_tree = main_material.node_tree
    

    internal_rotation0 = context.scene.my_addon_props.internal_rotation0
    internal_rotation1 = context.scene.my_addon_props.internal_rotation1

    #if main_material_tree.nodes["LensSim"].inputs["focus mode"].default_value == -1:
    #    context.scene.my_addon_props.focus_object = get_custom_dof_object()

    if internal_rotation0 != 0:
        main_material_tree.nodes["LensSim"].inputs["lens internal rotation 90d"].default_value = int( internal_rotation0 )
        context.scene.my_addon_props.internal_rotation0 = 0

    if internal_rotation1 != 1:
        main_material_tree.nodes["LensSim"].inputs["lens internal rotation 90d"].default_value = int( internal_rotation1 )
        context.scene.my_addon_props.internal_rotation1 = 1

def use_focus_object_update(self, context):
    
    main_material = get_main_material()
    if not main_material:
        return
    
    main_material_tree = main_material.node_tree
    
    focus_mode00 = context.scene.my_addon_props.focus_mode00
    focus_mode0 = context.scene.my_addon_props.focus_mode0
    focus_mode1 = context.scene.my_addon_props.focus_mode1
    focus_mode2 = context.scene.my_addon_props.focus_mode2

    #if main_material_tree.nodes["LensSim"].inputs["focus mode"].default_value == -1:
    #    context.scene.my_addon_props.focus_object = get_custom_dof_object()

    if focus_mode00 != "-1":
        main_material_tree.nodes["LensSim"].inputs["focus mode"].default_value = int( focus_mode00 )
        focus_empty_visibility(focus_mode00)
        context.scene.my_addon_props.focus_mode00 = "-1"
    if focus_mode0 != "0":
        main_material_tree.nodes["LensSim"].inputs["focus mode"].default_value = int( focus_mode0 )
        focus_empty_visibility(focus_mode0)
        context.scene.my_addon_props.focus_mode0 = "0"
    if focus_mode1 != "1":
        main_material_tree.nodes["LensSim"].inputs["focus mode"].default_value = int( focus_mode1 )
        focus_empty_visibility(focus_mode1)
        context.scene.my_addon_props.focus_mode1 = "1"
    if focus_mode2 != "2":
        main_material_tree.nodes["LensSim"].inputs["focus mode"].default_value = int( focus_mode2 )
        focus_empty_visibility(focus_mode2)
        context.scene.my_addon_props.focus_mode2 = "2"

    if main_material_tree.nodes["LensSim"].inputs["focus mode"].default_value == -1:
        context.scene.my_addon_props.focus_object = get_custom_dof_object()
    
def update_sensor_mode(self, context):
    
    main_material = get_main_material()
    if not main_material:
        return
    
    main_material_tree = main_material.node_tree
    

    sensor_mode0 = context.scene.my_addon_props.sensor_mode0
    sensor_mode1 = context.scene.my_addon_props.sensor_mode1
    sensor_mode2 = context.scene.my_addon_props.sensor_mode2

    if sensor_mode0 != "0":
        main_material_tree.nodes["LensSim"].inputs["sensor mode"].default_value = int( sensor_mode0 )
        context.scene.my_addon_props.sensor_mode0 = "0"
    if sensor_mode1 != "1":
        main_material_tree.nodes["LensSim"].inputs["sensor mode"].default_value = int( sensor_mode1 )
        context.scene.my_addon_props.sensor_mode1 = "1"
    if sensor_mode2 != "2":
        main_material_tree.nodes["LensSim"].inputs["sensor mode"].default_value = int( sensor_mode2 )
        context.scene.my_addon_props.sensor_mode2 = "2"


def focus_empty_attach_update(self, context):

    main_material = get_main_material()
    if not main_material:
        return
    
    main_material_tree = main_material.node_tree
    
    links = main_material_tree.links

    focus_empty_attach0 = context.scene.my_addon_props.focus_empty_attach0
    focus_empty_attach1 = context.scene.my_addon_props.focus_empty_attach1
    
    if focus_empty_attach0 != False:
        main_material_tree.nodes["LensSim"].inputs["focus object attached"].default_value = focus_empty_attach0
        context.scene.my_addon_props.focus_empty_attach0 = False
    if focus_empty_attach1 != True:
        main_material_tree.nodes["LensSim"].inputs["focus object attached"].default_value = focus_empty_attach1
        context.scene.my_addon_props.focus_empty_attach1 = True


def bokeh_image_mode_update(self, context):
    
    main_material = get_main_material()
    if not main_material:
        return
    
    main_material_tree = main_material.node_tree
    

    links = main_material_tree.links

    bokeh_image_mode0 = context.scene.my_addon_props.bokeh_image_mode0
    bokeh_image_mode1 = context.scene.my_addon_props.bokeh_image_mode1
    bokeh_image_mode2 = context.scene.my_addon_props.bokeh_image_mode2

    if bokeh_image_mode0 != "0":
        main_material_tree.nodes["LensSim"].inputs["bokeh image mode"].default_value = int( bokeh_image_mode0 )
        context.scene.my_addon_props.bokeh_image_mode0 = "0"
    if bokeh_image_mode1 != "1":
        main_material_tree.nodes["LensSim"].inputs["bokeh image mode"].default_value = int( bokeh_image_mode1 )
        context.scene.my_addon_props.bokeh_image_mode1 = "1"
    if bokeh_image_mode2 != "2":
        main_material_tree.nodes["LensSim"].inputs["bokeh image mode"].default_value = int( bokeh_image_mode2 )
        context.scene.my_addon_props.bokeh_image_mode2 = "2"


def lens_dirt_image_mode_update(self, context):
    
    main_material = get_main_material()
    if not main_material:
        return
    
    main_material_tree = main_material.node_tree
    
    links = main_material_tree.links

    lens_dirt_image_mode0 = context.scene.my_addon_props.lens_dirt_image_mode0
    lens_dirt_image_mode1 = context.scene.my_addon_props.lens_dirt_image_mode1
    lens_dirt_image_mode2 = context.scene.my_addon_props.lens_dirt_image_mode2

    if lens_dirt_image_mode0 != "0":
        main_material_tree.nodes["LensSim"].inputs["lens dirt image mode"].default_value = int( lens_dirt_image_mode0 )
        context.scene.my_addon_props.lens_dirt_image_mode0 = "0"
    if lens_dirt_image_mode1 != "1":
        main_material_tree.nodes["LensSim"].inputs["lens dirt image mode"].default_value = int( lens_dirt_image_mode1 )
        context.scene.my_addon_props.lens_dirt_image_mode1 = "1"
    if lens_dirt_image_mode2 != "2":
        main_material_tree.nodes["LensSim"].inputs["lens dirt image mode"].default_value = int( lens_dirt_image_mode2 )
        context.scene.my_addon_props.lens_dirt_image_mode2 = "2"



#
# vec3 math
#

def vec3( a,b,c ):
    return np.array([a,b,c])

def vec3_length( x ):
    return np.sqrt(x.dot(x))

def vec3_normalize(v):
    norm=np.linalg.norm(v)
    if norm==0:
        norm=np.finfo(v.dtype).eps
    return v/norm

def vec3_dot( a,b ):
    return np.dot(a, b)

def vec3_cross( a,b ):
    return np.cross(a, b)

#
# Ray Tracing
#

def rayPlaneIntersect( ray_origin, ray_direction, plane_normal, plane_point):

    denominator = vec3_dot(ray_direction, plane_normal)
    intersect_point = vec3(0, 0, 0)

    #print( ray_direction )

    # Check if the ray is parallel to the plane
    if (abs(denominator) > 0.0001):
        t = vec3_dot(plane_point - ray_origin, plane_normal) / denominator
        intersect_point = ray_origin + t * ray_direction
    
    return intersect_point

def _refract( incident, _normal, eta, inside ):

    _eta = eta
    if _eta == 0.0:
        _eta = 1.0
    Normal = _normal
    if inside:
        Normal = -Normal
    else:
        _eta = 1.0/_eta
    
    k = 1.0 - _eta * _eta * (1.0 - vec3_dot(Normal, incident) * vec3_dot(Normal, incident))
    if k < 0.0:
        return vec3(0,0,0) # or genDType(0.0)
    else:
        return _eta * incident - (_eta * vec3_dot(Normal, incident) + np.sqrt(k)) * Normal
    

def lineSphereIntersect( p0, p1, center, radius, surface_n, hit_idx, inside ):
    #p1 = p0+p1; // ?
    
    #print( "test: " + str( p0 ) +", "+ str(p1) +", "+ str(center) +", "+ str(radius) )
    
    intersections = vec3(0,0,0);
    d = p1 # Direction vector of the line
    f = p0 - center

    a = vec3_dot(d, d)
    b = 2 * vec3_dot(f, d)
    c = vec3_dot(f, f) - radius * radius

    discriminant = b * b - 4 * a * c

    #print( "test: " + str( d ) +", "+ str(f) +", "+ str(a) +", "+ str(b) +", "+ str(c) )

    if discriminant < 0:
        # No intersection
        return 0, p0, p1
    else:
        discriminant = np.sqrt(discriminant)

        #print( "test: " + str( b ) +", "+ str(a) +", " +str(discriminant) )

        t1 = (-b - discriminant) / (2.0 * a)
        t2 = (-b + discriminant) / (2.0 * a)

        if hit_idx == 0:
            p0 = p0 + t1 * d # first hit
        if hit_idx == 1:
            p0 = p0 + t2 * d # second hit

        surface_n = vec3_normalize( p0-center )
        
        if hit_idx == 1:
            surface_n = -surface_n
        if inside == 1:
            surface_n = -surface_n

        return 1, p0, surface_n


def lineCylinderIntersect( origin, direction, cylinderCenter, cylinderAxis, cylinderRadius, surface_n, hit_idx, inside ):
    
    ray = direction # Direction of the ray
    if hit_idx == 1:
        ray = -direction
    
    # Calculate the parameters for the quadratic equation    
    
    val1 = vec3_dot(ray, cylinderAxis) * cylinderAxis
    val2 = vec3_dot(origin - cylinderCenter, cylinderAxis) * cylinderAxis
    val3 = origin - cylinderCenter - val2
    
    a = vec3_dot(ray - val1, ray - val1)
    b = 2.0 * vec3_dot(ray - val1, val3)
    c = vec3_dot(val3, val3) - cylinderRadius * cylinderRadius

    # Calculate the discriminant
    discriminant = b * b - 4 * a * c

    intersectionPoint = vec3(0,0,0)
    _normal = vec3(0,0,0)

    # If the discriminant is non-negative, there is an intersection
    if discriminant >= 0:
        t1 = (-b + np.sqrt(discriminant)) / (2 * a)
        t2 = (-b - np.sqrt(discriminant)) / (2 * a)
        
        # Choose the smallest positive t value
        t = min(t1, t2)
        
        # Calculate the intersection point
        intersectionPoint = origin + t * ray
        
        # Calculate the normal at the intersection point
        cylinderToPoint = intersectionPoint - cylinderCenter
        _normal = vec3_normalize(cylinderToPoint - vec3_dot(cylinderToPoint, cylinderAxis) * cylinderAxis)
        
        origin = intersectionPoint
        surface_n = _normal
        
        if hit_idx == 1:
            surface_n = -surface_n
        if inside == 1:
            surface_n = -surface_n
        
        return 1, origin, surface_n

    return 0, origin, origin


def ray_lens( trace_backwards, inside, _ray_p, _ray_n, ior, lens_p, lens_r, type, cam_up, cam_side ):
    
    # lens_idx: 0 = left side, 1 = right side (from the schematic view)
    # trace_backwards: 0 = from left to right, 1 = from right to left
    
    #print( "tests: " + str( _ray_p ) +", "+ str(_ray_n) +", "+ str(ior) +", "+ str(lens_p) +", "+ str(lens_r) )
    
    surface_n = vec3(0,0,0)
    hit_idx = 0
    hit = 0
    

    cylinder_axis = cam_up
    if type == 2:
        cylinder_axis = cam_side
    
    if trace_backwards == 0 and lens_r < 0:
        hit_idx = 1
    if trace_backwards == 1 and lens_r > 0:
        hit_idx = 1
    
    '''
    # works but also not...
    if lens_r > 100.0:
        #cam_n = vec3_cross( cam_up, cam_side )
        cam_n = vec3(1.0,0.0,0.0)

        _ray_p = rayPlaneIntersect(_ray_p, _ray_n, cam_n, lens_p - (vec3(lens_r*cam_n[0],0.0,0.0)) )
        surface_n = cam_n
        if hit_idx == 1:
            surface_n = -surface_n
        if inside == 1:
            surface_n = -surface_n
        hit = 1

    else:
    '''
            
    if type == 0:
        hit, _ray_p, surface_n = lineSphereIntersect( _ray_p, _ray_n, lens_p, lens_r, surface_n, hit_idx, inside )
    if type != 0:
        hit, _ray_p, surface_n = lineCylinderIntersect( _ray_p, _ray_n, lens_p, cylinder_axis, lens_r, surface_n, hit_idx, inside )

    #print( "surface n: " + str( surface_n ) + ", ray_p: " + str( _ray_p ) + ", ray_n: " + str( _ray_n ) )

    if hit:
        #_ray_n = vec3_normalize(vec3(_ray_n[0],_ray_n[1],_ray_n[2]))

        _ray_n = _refract( _ray_n, surface_n, ior, inside )

        return 1, _ray_p, _ray_n

    return 0, _ray_p, _ray_n



def lens_trace( ray_p, ray_n, trace_backwards, lens_data, isolate_lens ):
    
    #return [ lenses, lens_length, r, d, ior, type, clamp ]
    
    lenses = 0
    _d = 0.0
    r1 = 0.0
    r2 = 0.0
    d1 = 0.0
    d2 = 0.0
    dia1 = 0.0
    dia2 = 0.0
    type = 0
    ior = 0.0
    _ray_p = vec3(0.0,0.0,0.0)
    _ray_n = vec3(0.0,0.0,0.0)
    
    upv = vec3(0.0,0.0,1.0)
    sidev = vec3(0.0,1.0,0.0)

    hit = 0

    rays = [ray_p]
    
    lenses = lens_data[0]

    
    if trace_backwards:

        _d = 0.0

        _ray_p = ray_p
        _ray_n = ray_n
        
        for lens in range(0,lenses,1):
            
            idx = (lenses*2) - (lens*2) -1
            
            r1 = lens_data[2][idx]
            r2 = lens_data[2][idx-1]
            
            d1 = lens_data[3][idx]
            d2 = lens_data[3][idx-1]
            
            dia1 = lens_data[6][idx]
            dia2 = lens_data[6][idx-1]
            
            idx = lenses - lens-1
            type = lens_data[5][idx]
            ior = lens_data[4][idx]
            
            ignore = True
            if isolate_lens == 0 or lenses - isolate_lens == lens:
                ignore = False
                
            _d -= d1
            if not ignore:
                hit, _ray_p, _ray_n = ray_lens( 1, 0, _ray_p, _ray_n, ior, vec3(_d + r1,0.0,0.0), r1, type, upv, sidev )
                if _ray_p[1] > dia1/2:
                    hit = 0
                if not hit:
                    break
                rays.append(_ray_p)

            _d -= d2
            if not ignore:
                hit, _ray_p, _ray_n = ray_lens( 1, 1, _ray_p, _ray_n, ior, vec3(_d + r2,0.0,0.0), r2, type, upv, sidev )
                if _ray_p[1] > dia2/2:
                    hit = 0
                if not hit:
                    break
                rays.append(_ray_p)

    else:
            
        _d = -lens_data[1]

        _ray_p = ray_p
        _ray_n = ray_n
        
        for lens in range(0,lenses,1):
            
            r1 = lens_data[2][lens*2]
            r2 = lens_data[2][(lens*2)+1]
            
            d1 = lens_data[3][lens*2]
            d2 = lens_data[3][(lens*2)+1]
            
            dia1 = lens_data[6][lens*2]
            dia2 = lens_data[6][(lens*2)+1]
            
            type = lens_data[5][lens]
            ior = lens_data[4][lens]
            
            if ior == 0:
                break
            if r1 == 0:
                break
            if r2 == 0:
                break
            
            ignore = True
            if isolate_lens == 0 or isolate_lens - 1 == lens:
                ignore = False
            
            if not ignore:
                hit, _ray_p, _ray_n = ray_lens( 0, 0, _ray_p, _ray_n, ior, vec3(_d + r1,0.0,0.0), r1, type, upv, sidev )
                if abs(_ray_p[1]) > dia1/2:
                    hit = 0
                if not hit:
                    break
                rays.append(_ray_p)
            _d += d1
            
            if not ignore:
                hit, _ray_p, _ray_n = ray_lens( 0, 1, _ray_p, _ray_n, ior, vec3(_d + r2,0.0,0.0), r2, type, upv, sidev )
                if abs(_ray_p[1]) > dia2/2:
                    hit = 0
                if not hit:
                    break
                rays.append(_ray_p)
            _d += d2
        
    if hit:
        rays.append(_ray_p + _ray_n)
            
    return _ray_p, _ray_n, rays



def update_lens_rays():
    
    material = get_lens_camera_node()
    if material == None:
        return
    
    lens_node = get_lens_node()
    
    main_material = get_main_material()
    if not main_material:
        return
    
    lens_node_tree = main_material.node_tree
    #lens_node_tree = lens_node.node_tree

    lens_data = get_lens_data(False)
    
    #isolate_lens_node = lens_node_tree.nodes["isolate lens"]
    #isolate_lens_node.outputs[0].default_value = min( context.scene.my_addon_props.lens_schematic_isolate_lens, lens_data[0] )
    
    rays = material.inputs["cast rays"].default_value

    if rays:
        build_lens_rays()
    else:
        mute_lens_rays()

def mute_lens_rays():

    '''
    lens_node = get_lens_node()
    main_material = get_main_material()
    if not main_material:
        return
    
    lens_node_tree = main_material.node_tree
    #lens_node_tree = lens_node.node_tree
    
    draw_rays_grp = lens_node_tree.nodes["draw_rays"]
    draw_rays_grp.mute = True
    draw_rays_mix = lens_node_tree.nodes["draw_rays_mix"]
    draw_rays_mix.mute = True
    '''
    
    lens_node = get_lens_node()
    
    main_material = get_main_material()
    lens_node_tree = main_material.node_tree
    
    line_node_name = "ray#"
    
    line_node_idx = 0
    
    # delete extra nodes
    node_overflow = True
    while node_overflow:
        
        new_node_name = line_node_name.replace("#", str(line_node_idx))
        if new_node_name in lens_node_tree.nodes:
            removeNode = lens_node_tree.nodes[new_node_name]
            lens_node_tree.nodes.remove(removeNode)
        else:
            node_overflow = False
        
        line_node_idx += 1



def apply_rays(ray_list, draw_baseray):
    
    if draw_baseray:
        ray_list.append( [ vec3(-1.0,0.0,0.0), vec3(1.0,0.0,0.0)] )
    
    lens_node = get_lens_node()
    
    main_material = get_main_material()
    if not main_material:
        return
    
    lens_node_tree = main_material.node_tree
    #lens_node_tree = lens_node.node_tree
    
    lens_data = get_lens_data(False)
    ray_x_offset =  lens_data[1] * 0.5
    
    line_draw_grp = bpy.data.node_groups["LensSim_SDF_Lines"]
    
    rays_start = lens_node_tree.nodes["rays_draw_start"]
    rays_end = lens_node_tree.nodes["rays_draw_end"]
    

    line_node_name = "ray#"
    
    prew_node = rays_start

    node_separation = 25.0
    
    line_node_idx = 0
    links = lens_node_tree.links
    
    # LensSim_SDF_Lines node max supported draw lines 
    ray_draw_bundle_max_lines = 5
    
    rays_draw = []
    ray_draw_bundle = []
    ray_draw_bundle_count = 0
    
    for ray_bundle in ray_list:
        for ray_idx in range(0,len(ray_bundle)-1,1):
            ray_draw_bundle.append( ray_bundle[ray_idx] )
            ray_draw_bundle.append( ray_bundle[ray_idx+1] )
    
            ray_draw_bundle_count += 1
            if ray_draw_bundle_count == ray_draw_bundle_max_lines:
                rays_draw.append(ray_draw_bundle)
                ray_draw_bundle = []
                ray_draw_bundle_count = 0
      
    # append last rays
    rays = len(ray_draw_bundle)
    if rays > 0:
        
        # fill the ray_draw_bundle to fit he node group inputs 
        if rays < ray_draw_bundle_max_lines * 2:
            for x in range( (ray_draw_bundle_max_lines * 2) - rays ):
                ray_draw_bundle.append( vec3(1000.0,1000.0,0.0) )
        
        rays_draw.append(ray_draw_bundle)
    

    for ray_bundle in rays_draw:
        
        new_node_name = line_node_name.replace("#", str(line_node_idx))
            
        # if node exist
        if not new_node_name in lens_node_tree.nodes:
            #removeNode = lens_node_tree.nodes[new_node_name]
            #lens_node_tree.nodes.remove(removeNode)
        
            new_node = lens_node_tree.nodes.new(type='ShaderNodeGroup')
            new_node.node_tree = line_draw_grp
            
            new_node.location = prew_node.location
            new_node.location[0] += node_separation

            new_node.name = new_node_name
            
            # connect nodes    
            if line_node_idx > 0:
                links.new( prew_node.outputs[0], new_node.inputs[0] )
            links.new( rays_start.outputs[0], new_node.inputs[1] )
        
        else:
            new_node = lens_node_tree.nodes[new_node_name]
        
        # set input values
        for ray_idx in range(len(ray_bundle)):
            new_node.inputs[ ray_idx + 2 ].default_value[ 0 ] = ray_bundle[ray_idx][0] + ray_x_offset
            new_node.inputs[ ray_idx + 2 ].default_value[ 1 ] = ray_bundle[ray_idx][1]
        
        '''
        # does not work...
        for ray_idx in range(len(ray_bundle)):
            
            # set values
            values = [  [ray_idx + 2, 0, ray_bundle[ray_idx][0] + ray_x_offset ] ,
                        [ray_idx + 2, 1, ray_bundle[ray_idx][1] ] ]
            treshold = 0.001
            
            for input in values:
                node_val = new_node.inputs[ input[0] ].default_value[ input[1] ]
                ray_val = input[2]
                
                if node_val < ray_val-treshold or node_val > ray_val+treshold:
                    new_node.inputs[ input[0] ].default_value[ input[1] ] = ray_val
        '''

        prew_node = new_node
        
        line_node_idx += 1
        
    links.new( new_node.outputs[0], rays_end.inputs[0] )
    

    # delete extra nodes
    node_overflow = True
    while node_overflow:
        
        new_node_name = line_node_name.replace("#", str(line_node_idx))
        if new_node_name in lens_node_tree.nodes:
            removeNode = lens_node_tree.nodes[new_node_name]
            lens_node_tree.nodes.remove(removeNode)
        else:
            node_overflow = False
        
        line_node_idx += 1


    
def build_lens_rays():

    
    #return [ lenses, lens_length, r, d, ior, type, clamp ]
    
    material = get_lens_camera_node()
    if material == None:
        return
    
    lens_node = get_lens_node()
    
    main_material = get_main_material()
    if not main_material:
        return
    
    lens_node_tree = main_material.node_tree
    #lens_node_tree = lens_node.node_tree

    
    #draw_rays_grp_tree = draw_rays_grp.node_tree
    
    
    lens_data = get_lens_data(False)
    
    #isolate_lens_node = lens_node_tree.nodes["isolate lens"]
    #isolate_lens_node.outputs[0].default_value = min( context.scene.my_addon_props.lens_schematic_isolate_lens, lens_data[0] )
    
    trace_backwards = material.inputs["cast rays dir"].default_value
    isolate_lens = material.inputs["isolate lens"].default_value
    
    ray_traces = 4
        
    if lens_data[0] > 6:
        ray_traces = 2
        
    if lens_data[0] > 9:
        ray_traces = 1
    
    if isolate_lens:
        ray_traces = 5
    
    ray_list = []

    for i in range(0,ray_traces,1):
        
        ray_h = (lens_data[6][0]/2.0)/(ray_traces+1) * (i + 1)
        ray_p = vec3(-2.0, ray_h ,0.0)
        ray_n = vec3(1.0,0.0,0.0)
    
        lenses = lens_data[0]
    
        if trace_backwards:
            ray_p[0] = -ray_p[0]

            dia = lens_data[6][(lenses*2)-1]
            if dia == 100000.0:
                dia = lens_data[6][(lenses*2)-2]
            if dia == 0.0:
                dia = 100000.0
            ray_h = (dia/2.0)/(ray_traces+1) * (i + 1)
            ray_p[1] = ray_h
            ray_n = -ray_n
        
        if isolate_lens > 0:
            #isolate_lens = min(isolate_lens, lens_data[0])
            
            if isolate_lens > lens_data[0]:
                mute_lens_rays()
                return
            
            dia = lens_data[6][(isolate_lens-1)*2]
            if dia == 100000.0:
                dia = lens_data[6][(lenses*2)-2]
            if dia == 0.0:
                dia = 100000.0
            ray_p[1] = (dia/2.0)/(ray_traces+1) * (i + 1)
            
            #if trace_backwards:
                
    
        rays = []        
        ray_p, ray_n, rays = lens_trace( ray_p, ray_n, trace_backwards, lens_data, isolate_lens )
        
        ray_list.append(rays)
    
    
    #ray_list = [ [vec3(1.0,0.002,0.0), vec3(-1.0,0.002,0.0)], [vec3(1.0,0.004,0.0), vec3(-1.0,0.004,0.0)] ]
    
    draw_baseray = True
    
    apply_rays(ray_list, draw_baseray)

  
    

def rotate(origin, point, angle):
    
    angle = math.radians( angle )
    
    ox, oy, oz = origin
    px, py, pz = point

    qx = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
    qy = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)
    return qx, qy, pz


def find_angle_from_height(r, h):
    # Check if h is within the bounds of the circle (0 <= h <= r)
    if h < 0 or h > r:
        #raise ValueError("Height must be between 0 and the radius.")
        return 0
    # Calculate the angle in radians
    angle_rad = math.asin(h / r)
    
    # Convert the angle to degrees
    angle_deg = math.degrees(angle_rad)
    
    return angle_deg

def distribute_points(r, a, s):
    
    s *= 100.0
    
    r *= 2.0
    
    # Calculate the step angle corresponding to the desired spacing    
    theta_step = s / r
    
    # Calculate the number of intervals (points - 1)
    n = math.floor(a / theta_step)
    
    # Recalculate the actual angle step to evenly distribute points
    actual_step = a / n
    
    # Generate the angles from 0 to max angle a
    angles = [i * actual_step for i in range(n + 1)]  # n+1 points, including 0 and max angle a
    
    return angles

def calculate_distance(point1, point2):
    """
    Calculate the Euclidean distance between two points in 3D space.
    
    Args:
    point1 (tuple): Coordinates of the first point (x1, y1, z1).
    point2 (tuple): Coordinates of the second point (x2, y2, z2).
    
    Returns:
    float: The distance between the two points.
    """
    x1, y1, z1 = point1
    x2, y2, z2 = point2
    distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)
    return distance

def draw_line( p0, p1, resolution, vertices ):

    dist = calculate_distance( p0, p1 )
    points = int( dist / resolution )

    if points > 2:
        for x in range( points ):
            if x != 0 and x != points-1:
                t = float(x) / float(points-1)
                px = lerp( p0[0], p1[0], t )
                py = lerp( p0[1], p1[1], t )
                pz = lerp( p0[2], p1[2], t )
                vertices.append( ( px ,py, pz ) )
    else:
        px = lerp( p0[0], p1[0], 0.5 )
        py = lerp( p0[1], p1[1], 0.5 )
        pz = lerp( p0[2], p1[2], 0.5 )
        vertices.append( ( px ,py, pz ) )


def build_lens_mesh():

    node = get_lens_camera_node()
    if node == None:
        return

    build_lens = node.inputs["lens geo enable"].default_value

    #print( build_lens )

    LensMesh = None

    objects_to_delete = []

    # delete old mesh
    # Check each child object of the camera
    for child in LensSim_Camera.children:
        # Check if the child is a mesh object
        if child.type == 'MESH':
            #if child.name.startswith( LensSim_LensMeshName ):
            #print( child )
            for mat in child.data.materials:
                
                if mat.name.startswith( LensSim_LensMaterialName ):
                    
                    LensMesh = child
                    
                    delete_object = None
                    
                    for childd in child.children:
                        if childd.name.startswith( LensSim_LensMeshName ):
                            objects_to_delete.append( childd )


    for object_to_delete in objects_to_delete:
        bpy.data.objects.remove(object_to_delete, do_unlink=True)

    if not build_lens:
        return

    if LensMesh == None:
        return


    lens_data = get_lens_data(True)
    #return [ lenses, lens_length, r, d, ior, t, dia, rack_focus_idx, rack_focus ]

    lenses = lens_data[0]
    
    vertices = []
    edges = []
    
    d = 0.0
    
    for lens_idx in range(lenses):
        
        idx = lens_idx * 2
        
        r0 = lens_data[2][idx]
        r1 = lens_data[2][idx+1]
        
        if lens_data[5][lens_idx] == 2:
            r0 = 100000.0
            r1 = 100000.0

            
        d0 = 0.0
        if lens_idx > 0:
            d0 = lens_data[3][idx-1]
        d1 = lens_data[3][idx]
        

        dia0 = lens_data[6][idx]
        dia1 = lens_data[6][idx+1]
        
        if dia0 == 0.0 or dia0 > 99999:
            dia0 = dia1
        if dia1 == 0.0 or dia1 > 99999:
            dia1 = dia0
            
        
        vertices_l0 = []
        vertices_l1 = []
        
        resolution = 0.0005
        

        d -= d0
        l0d = d
        
        d -= d1
        l1d = d
        
        #print( "r0: " + str(r0) + " dia0: " + str(dia0))
        #print( "r1: " + str(r1) + " dia1: " + str(dia1))
        
        angle = find_angle_from_height( abs(r0), dia0 * 0.5 )
        if angle == 0:
            continue
        for a in distribute_points( abs(r0), abs(angle), resolution ):
            v = ( 0, 0, 0 )
            if r0 < 0:
                a *= -1.0
            v = rotate( (-r0,0,0), v, a )
            #if v[1] < dia0 * 0.5:
            vertices_l0.append( (v[0] + l0d, v[1], v[2]) )

        angle = find_angle_from_height( abs(r1), dia1 * 0.5 )
        if angle == 0:
            continue
        for a in distribute_points( abs(r1), abs(angle), resolution ):
            v = ( 0, 0, 0 )
            if r1 < 0:
                a *= -1.0
            v = rotate( (-r1,0,0), v, a )
            #if v[1] < dia0 * 0.5:
            vertices_l1.append( (v[0] + l1d, v[1], v[2]) )
        vertices_l1.reverse()
        
        # build bridge
        p0 = vertices_l0[ len(vertices_l0)-1 ]
        p1 = vertices_l1[ 0 ]
        
        vertices_bridge = []


        # if straight
        if dia0 == dia1:
            draw_line( p0, p1, resolution, vertices_bridge )
        
        elif dia0 > dia1:
            v0 = ( p0[0], p0[1], p0[2] )
            v1 = ( p1[0], p0[1], p0[2] )
            draw_line( v0, v1, resolution, vertices_bridge )
            
            vertices_bridge.append( v1 )
            
            v0 = ( p1[0], p0[1], p0[2] )
            v1 = ( p1[0], p1[1], p1[2] )
            draw_line( v0, v1, resolution, vertices_bridge )
        
        elif dia0 < dia1:
            v0 = ( p0[0], p0[1], p0[2] )
            v1 = ( p0[0], p1[1], p0[2] )
            draw_line( v0, v1, resolution, vertices_bridge )
            
            vertices_bridge.append( v1 )
            
            v0 = ( p0[0], p1[1], p0[2] )
            v1 = ( p1[0], p1[1], p1[2] )
            draw_line( v0, v1, resolution, vertices_bridge )
        
        
        segments = [ vertices_l0, vertices_bridge, vertices_l1 ]
        
        points = []
        
        for segment in segments:
            # add to vertices
            for p in segment:
                points.append( p )
        
        points_old = points[:]
        points_old.reverse()
        for p in points_old:
            points.append( ( p[0],-p[1],p[2] ) )
        
        
        # draw lines
        line_start = len( vertices )-1
        
        for p in points:
            vertices.append( p )
        
        line_end = len(vertices)-1
        
        for line in range(line_start+1, line_end):
            edges.append( ( line, line+1) )
        

            
            
    for x in range(len(vertices)):
        v = vertices[x]
        vertices[x] = (v[2], v[1], -v[0] - lens_data[1] )
        
        # schematic lineup
        #vertices[x] = (-v[0] - (lens_data[1]*0.5) , v[1], v[2] )

    '''
    vertices = [(1, 1, 1)]
    faces = [(0, 1, 2, 3)]
    edges = [(0, 1)]
    '''
    
    faces = []
    #edges = []

    # Create a new mesh and object
    mesh_data = bpy.data.meshes.new("custom_mesh")
    mesh_data.from_pydata(vertices, edges, faces)
    mesh_data.update()

    #LensSim_LensMeshName

    # Create an object using the mesh
    new_object = bpy.data.objects.new( LensSim_LensMeshName , mesh_data)

    scn = bpy.context.scene

    #bpy.ops.object.select_all(action='DESELECT')
    

    # create new collection
    #tmp_collection = bpy.data.collections.new("LensSimCameraTMPCollection")
    #scn.collection.children.link(tmp_collection)
    
    #tmp_collection.objects.link( new_object )
    
    # disable in render
    new_object.visible_camera = False
    new_object.visible_diffuse = False
    new_object.visible_glossy = False
    new_object.visible_transmission = False
    new_object.visible_volume_scatter = False
    new_object.visible_shadow = False
    
    new_object.parent = LensMesh

    # disable selection etc
    new_object.hide_select = True
    #new_object.hide_viewport = True
    new_object.hide_render = True

    # fix collections
    objects = [ new_object ]
    cam_obj = LensMesh
    
    for col in LensMesh.users_collection:
        col.objects.link( new_object )
        
    '''
    # add collections that is part of the camera collection
    for object in objects:
        for cam_col in cam_obj.users_collection:
            add_collection = False
            for col in object.users_collection:
                if col != cam_col:
                    add_collection = True
            if add_collection:
                cam_col.objects.link( object )
                print( "test" )
    '''
    '''
    # remove collections that is not part of the camera collection
    for object in objects:
        
        for col in object.users_collection:
            remove_collection = True
            for cam_col in cam_obj.users_collection:
                if col == cam_col:
                    remove_collection = False
            if remove_collection:
                
                # quick fix for error when col does not has object in it...
                if col in object.users_collection:
                    col.objects.unlink( object )
    '''
    
    #bpy.data.collections.remove(tmp_collection)
       
    
#
# UI
#


def focus_layout(layout, context):
    
    material = get_lens_camera_node()
    if material == None:
        return
    
    props = context.scene.my_addon_props
    main_material = get_main_material()
    lens_node = get_lens_node()
    props = context.scene.my_addon_props
    
    if not main_material:
        return
    


    focus_mode = material.inputs["focus mode"].default_value
    focusing_screen = material.inputs["focusing screen"].default_value
    
    focus_screen_button = ""
    if focusing_screen:
        focus_screen_button = "focusing_screen0"
    else:
        focus_screen_button = "focusing_screen1"
        
        
    if focus_mode == -1: #"focus object":
        
        split = layout.split(factor=0.5)
        #row = layout.row(align=True)
        split.prop(props, "focus_mode00", text="", icon="DRIVER_DISTANCE")

        row = split.row(align=True)
        row.prop(props, "focus_object", text="")
        row.prop(props, focus_screen_button, text="", invert_checkbox=True, icon="CON_CAMERASOLVER", emboss=True)

        #layout.prop(props, "focus_object", text="")


    elif focus_mode == 0: #"focus object":
        row = layout.row(align=True)
        row.prop(props, "focus_mode0", text="", icon="DRIVER_DISTANCE")
        
        focus_object_attached = material.inputs["focus object attached"].default_value
        
        if focus_object_attached:
            #row.prop(material.inputs["focus object attached"], "default_value", text="", invert_checkbox=True, icon="LINKED", emboss=True)
            row.prop(props, "focus_empty_attach1", text="", invert_checkbox=True, icon="LINKED", emboss=True)
        else:
            #row.prop(material.inputs["focus object attached"], "default_value", text="", invert_checkbox=True, icon="UNLINKED", emboss=False)
            row.prop(props, "focus_empty_attach0", text="", invert_checkbox=True, icon="UNLINKED", emboss=False)
        row.operator("object.select_camera_focus_object_button", text="", icon="RESTRICT_SELECT_OFF", emboss=True, depress=False)


        row.prop(props, focus_screen_button, text="", invert_checkbox=True, icon="CON_CAMERASOLVER", emboss=True)



        #(data, property, text, text_ctxt, translate, icon, placeholder, expand, slider, toggle, icon_only, event, full_event, emboss, index, icon_value, invert_checkbox)
        
        #layout.prop(props, "select_camera_focus_object_button")
        # select_camera_focus_object_button
    
    elif focus_mode == 1: #"distance":
        split = layout.split(factor=0.5)
        split.prop(props, "focus_mode1", text="", icon="DRIVER_DISTANCE")
        #split.prop(props, "focus_dist", text="")
        #split.prop(distance_node.outputs[0], "default_value", text="")
        row = split.row(align=True)
        row.prop(material.inputs["focus dist"], "default_value", text="")
        row.prop(props, focus_screen_button, text="", invert_checkbox=True, icon="CON_CAMERASOLVER", emboss=True)
        
        #material.inputs["focus mode"].default_value = 1
        
    elif focus_mode == 2: #"sensor position":
        
        if lens_node.inputs["rack focus idx"].default_value == 0:
            split = layout.split(factor=0.55)
            split.prop(props, "focus_mode2", text="", icon="DRIVER_DISTANCE")
            #split.prop(props, "sensor_pos", text="")
            #split.prop(material.inputs["sensor pos"], "default_value", text="Sensor Pos")
            row = split.row(align=True)
            row.prop(material.inputs["sensor pos"], "default_value", text="Sensor Pos")
            row.prop(props, focus_screen_button, text="", invert_checkbox=True, icon="CON_CAMERASOLVER", emboss=True)
        else:
            row = layout.row(align=True)
            row.prop(props, "focus_mode2", text="", icon="DRIVER_DISTANCE")
            row.prop(props, focus_screen_button, text="", invert_checkbox=True, icon="CON_CAMERASOLVER", emboss=True)
            #split.prop(props, "sensor_pos", text="")
            split = layout.split(factor=0.55)
            split.prop(material.inputs["sensor pos"], "default_value", text="Sensor Pos")
            split.prop(material.inputs["rack focus"], "default_value", text="Rack Focus")
            
    #layout.prop(material.inputs["focusing screen"], "default_value", text="Focusing Screen", icon="CON_CAMERASOLVER")



def sensor_layout(layout, context):
    
    material = get_lens_camera_node()
    if material == None:
        return
    
    props = context.scene.my_addon_props
    main_material = get_main_material()
    lens_node = get_lens_node()
    
    if not main_material:
        return

    sensor_mode = material.inputs["sensor mode"].default_value

    row = layout.row(align=True)

    if sensor_mode == 0: #"focus object":
        row.prop(props, "sensor_mode0", text="", icon="RENDER_STILL")
    
    if sensor_mode == 1:

        split = row.split(factor=0.55)
        split.prop(props, "sensor_mode1", text="", icon="RENDER_STILL")
        split.prop(material.inputs["focal length"], "default_value", text="")
      
    if sensor_mode == 2:
        split = row.split(factor=0.55)
        split.prop(props, "sensor_mode2", text="", icon="RENDER_STILL")
        split.prop(material.inputs["viewfinder scale"], "default_value", text="")


    internal_rotation_layout(row, context, False)

    if not if_favorite():
        row.prop(props, "favorite", text="", icon="HEART", emboss=False, icon_only=True, invert_checkbox=True)   
    else:
        row.prop(props, "favorite", text="", icon="FUND", emboss=False, icon_only=True, invert_checkbox=False)
    

def bokeh_image_mode_layout(layout, context):
    
    material = get_lens_camera_node()
    if material == None:
        return
    
    props = context.scene.my_addon_props
    main_material = get_main_material()
    lens_node = get_lens_node()
    
    if not main_material:
        return
    

    bokeh_image_mode = material.inputs["bokeh image mode"].default_value
    
    if bokeh_image_mode == 0: #"focus object":
        layout.prop(props, "bokeh_image_mode0", text="")
    if bokeh_image_mode == 1: #"focus object":
        layout.prop(props, "bokeh_image_mode1", text="")
    if bokeh_image_mode == 2: #"focus object":
        layout.prop(props, "bokeh_image_mode2", text="")


def lens_dirt_image_mode_layout(layout, context):
    
    material = get_lens_camera_node()
    if material == None:
        return
    
    props = context.scene.my_addon_props
    main_material = get_main_material()
    lens_node = get_lens_node()
    
    if not main_material:
        return
    
    lens_dirt_image_mode = material.inputs["lens dirt image mode"].default_value
    
    if lens_dirt_image_mode == 0: #"focus object":
        layout.prop(props, "lens_dirt_image_mode0", text="")
    if lens_dirt_image_mode == 1: #"focus object":
        layout.prop(props, "lens_dirt_image_mode1", text="")
    if lens_dirt_image_mode == 2: #"focus object":
        layout.prop(props, "lens_dirt_image_mode2", text="")


def internal_rotation_layout(layout, context, emboss):
    
    material = get_lens_camera_node()
    if material == None:
        return
    
    props = context.scene.my_addon_props
    main_material = get_main_material()
    lens_node = get_lens_node()
    
    if not main_material:
        return
    
    internal_rotation_state = material.inputs["lens internal rotation 90d"].default_value

    '''
    if internal_rotation_state:
        layout.prop(props, "internal_rotation1", text="", emboss=emboss, icon_only=True, icon="SPLIT_VERTICAL")
    else:
        layout.prop(props, "internal_rotation0", text="", emboss=emboss, icon_only=True, icon="SPLIT_HORIZONTAL")  
    '''
    if internal_rotation_state:
        layout.prop(props, "internal_rotation1", text="", emboss=emboss, icon_only=True, icon="SPLIT_VERTICAL")
    else:
        layout.prop(props, "internal_rotation0", text="", emboss=emboss, icon_only=True, icon="SEQ_PREVIEW") 


def on_link_parm_change(self, context):

    props = context.scene.my_addon_props
    
    set_link_parm( getattr(props, "lens_link") )

def set_link_parm( link_path ):
    
    main_material = get_main_material()
    nodes = main_material.node_tree.nodes

    # max label length
    #1234567890 1234567890 1234567890 1234567890 123456780 1234567890 1234

    letter_idx = 0
    path_length = len( link_path )

    max_node_label_length = 60

    for x in range(20):
        link_node_name = "LinkPath"+str(x)
        if link_node_name in nodes:
            link_node = main_material.node_tree.nodes[ link_node_name ]
            
            link_node.label = ""
            label = ""
            
            for l in link_path:
                if len(label) < max_node_label_length:
                    
                    if letter_idx < path_length:
                        label = label + link_path[ letter_idx ]
                        letter_idx += 1
            
            link_node.label = label
        else:
            break

def get_link_parm():
    
    main_material = get_main_material()
    nodes = main_material.node_tree.nodes
    
    link_parm = ""
    
    for x in range(20):
        link_node_name = "LinkPath"+str(x)
        if link_node_name in nodes:
            link_node = main_material.node_tree.nodes[ link_node_name ]

            link_parm = link_parm + link_node.label

        else:
            break
        
    return link_parm

def sync_ui_parameters():
    sync_lens_parm()
    sync_bokeh_ui()
    
def sync_lens_parm():
    link = get_link_parm()
    props = bpy.context.scene.my_addon_props
    setattr(props, "lens_link", link)






def on_camera_change():
    
    #print("test")
    
    # update focus object
    try:
        bpy.context.scene.my_addon_props.focus_object = get_custom_dof_object()
    except:
        pass

def get_favorite_file():
    
    path = get_lenses_path()
    file_path = os.path.join(path, LensSim_FavoritesFileName)

    return file_path

def get_favorites():
    
    file_path = get_favorite_file()

    favorite_lenses = []
    
    try:
        with open(file_path, 'r') as file:
            favorite_lenses = [line.strip() for line in file.readlines()]
    except:
        return []
    
    return favorite_lenses
    

def if_favorite():
    
    favorite_lenses = get_favorites()
    
    current_lens = get_current_lens()[:-4]
    
    if current_lens in favorite_lenses:
        return True
    
    return False

def favorite_set( self, context ):
    
    lens_name = get_current_lens()[:-4]
    file_path = get_favorite_file()

    set_favorite = True
    if if_favorite():
        set_favorite = False

    lens_line = f"{lens_name}\n"

    # Create the file if it doesn't exist
    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            if set_favorite:
                f.write(lens_line)
        return
    
    # Read the file and update the content
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    if set_favorite:
        # Check if the lens_name already exists, if not, add it
        if lens_line not in lines:
            lines.append(lens_line)
    else:
        # Remove the lens_name line if it exists
        lines = [line for line in lines if line.strip() != lens_line.strip()]
    
    # Write the updated content back to the file
    with open(file_path, 'w') as f:
        f.writelines(lines)

    return


from bl_ui import properties_data_camera

class MyPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_MainPanel"
    bl_category = "Lens Sim"
    bl_label = ""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    


    def draw_header(self, context):
        
        layout = self.layout
        props = context.scene.my_addon_props
        
        #text = LensSim_Camera.name
        camera_exists()
        re_apply_event_handlers( False )
        
        if not LensSim_CameraExists:
        
            layout.label(text="Lens Sim Camera not selected")

        else:
        
            try:
                layout.label( text = LensSim_Camera.name )
            except:
                return
            
            props = context.scene.my_addon_props
            pinned = getattr(props, "pin_camera" )
            
            if pinned:
                layout.prop(props, "pin_camera", icon_only=True, emboss=False, icon="PINNED")
            else:
                layout.prop(props, "pin_camera", icon_only=True, emboss=False, icon="UNPINNED")
        

        #layout.operator("object.re_register_event_handlers_button", icon="MODIFIER_OFF", emboss=False, depress=False)
        #expected (operator, text, text_ctxt, translate, icon, emboss, depress, icon_value, search_weight)
        
    def draw(self, context):
   
        layout = self.layout
        
        props = context.scene.my_addon_props

        material = get_lens_camera_node()

        #if not camera_exists():
            #return False
        
        #if not camera_exists():
        #if not LensSim_CameraExists:
        if not LensSim_CameraExists:
        
            #layout.label(text="Lens Sim Camera not found.")
            #layout.operator("object.import_camera")
            
            layout.operator("object.create_camera_button", icon="IMPORT")


            selected_objects = bpy.context.selected_objects

            row = layout.row()
            row.enabled = False
            
            for obj in selected_objects:
                if obj.type == 'CAMERA':
                    if not is_LensSimCamera(obj):
                        row.enabled = True
                break
            row.operator("object.convert_camera_button", icon="MOD_BUILD")
            
        else:
            
            
            version = ""
            
            try:
                version = LensSim_LensMaterial.node_tree.nodes["Version"].label
            except:
                pass
            
            if version != LensSim_Version:
                row = layout.box()
                row.alert = True
                row.label(text="Addon and lens versions do not match. Errors might occur.")

            #split = layout.split(factor=0.1)
            #split.operator("object.open_lens_path",icon="FILE_FOLDER", text="")
            #split.prop(props, "lenses_enum", text="")


            row = layout.row(align=True)

            search_lenses = props.search_lenses_enable

            if search_lenses:
                
                #row = layout.row(align=True)
                #row.prop(props, "lenses_enum", text="", icon="VIEW_CAMERA_UNSELECTED")
                #row = layout.row(align=True)
                row.prop(props, "search_lenses", text="", icon="VIEWZOOM", icon_only=False)
                row.prop(props, "search_lenses_enable", text="", icon="X", icon_only=True, invert_checkbox=True)
                
            else:

                row.prop(props, "lenses_enum", text="", icon="VIEW_CAMERA_UNSELECTED")

                #row.prop(props, "favorite", text="", icon="HEART", icon_only=True)
                #row.prop(props, "favorite", text="", icon="FUND", icon_only=True)
                
                #(data, property, text, text_ctxt, translate, icon, placeholder, expand, slider, toggle, icon_only, event, full_event, emboss, index, icon_value, invert_checkbox)
                    
                #row.prop(props, "search_lenses_enable", text="", icon="VIEWZOOM", icon_only=True)
                
                # lens thumbnails test
                #row.template_icon_view(context.scene, "my_lens_thumbnails", show_labels=True, scale=1.0)
                #layout.prop(context.scene, "my_lens_thumbnails", text="Select Lens", icon="VIEW_CAMERA")
                # Just a way to access which one is selected
                #row = layout.row()
                #row.label(text="You selected: " + bpy.context.scene.my_lens_thumbnails)
                
                
                row.prop(props, "search_lenses", text="", icon="VIEWZOOM", icon_only=True)
                
            
            current_lens = get_current_lens()
            lens_enum = context.scene.my_addon_props.lenses_enum
            
            if current_lens != lens_enum:
                
                current_lens = get_current_lens()
    
                lenses = get_installed_lenses(None, context)
                found = False
                for lens in lenses:
                    if current_lens == lens[0]:
                        found = True
                
                box = layout.box()
                box.alert = True
                row = box.row(align=True)

                if found:
                    row.label(text="Warning: Selected lens is out of sync.")
                    row.operator("object.resync_selected_lens_button", text="", icon="FILE_REFRESH")
                else:
                    row.label(text="Warning: Selected lens not found.")
            
            '''
            web_link = context.scene.my_addon_props.lens_link
            if web_link == "":
                layout.prop(props, "lenses_enum", text="", icon="VIEW_CAMERA_UNSELECTED")
                #INTERNET_OFFLINE
            else:
                split = layout.split( factor=0.9 )
                split.prop(props, "lenses_enum", text="", icon="VIEW_CAMERA_UNSELECTED")
                split.operator("object.open_lens_link_button", text="", icon="INTERNET", emboss=False)
            '''
            
            #(operator, text, text_ctxt, translate, icon, emboss, depress, icon_value, search_weight)
            
            #sensor_mode = bpy.context.scene.my_addon_props.sensor_mode
            
            sensor_layout(layout, context)
            
            #layout.operator("object.open_lens_link_button", text="", icon="INTERNET", emboss=True)

            #layout.prop( bpy.data.materials["LensSimMaterial"].node_tree.nodes["LensSim"].inputs[60], "default_value", description="Enable")

            layout.separator()
            
            apply_to_all = context.scene.my_addon_props.disable_all
            
            button_text = "              Disable Lens"
            if material.inputs["viewport preview enable"].default_value:
                button_text = button_text.replace("Disable", "Enable")
                
            if apply_to_all:
                button_text = button_text.replace("Lens", "Lenses")
                
            row = layout.row(align=True)
            if material.inputs["viewport preview enable"].default_value:
                row.alert = True
                row.prop(material.inputs["viewport preview enable"], "default_value", text=button_text, toggle=True, icon_only=False, icon="RESTRICT_RENDER_ON", invert_checkbox=True)
                #row.alert = True
            else:
                row.prop(material.inputs["viewport preview enable"], "default_value", text=button_text, toggle=True, icon_only=False, icon="RESTRICT_RENDER_OFF")
                row.alert = False
            
            '''
            if apply_to_all:
                row.prop(props, "disable_all", icon="LINKED", emboss=True, icon_only=True, invert_checkbox=True )
            else:
                row.prop(props, "disable_all", icon="UNLINKED", emboss=True, icon_only=True )
            '''
            
            force_lens_dof_render = context.scene.my_addon_props.force_lens_dof_render
            
            if force_lens_dof_render:
                row.prop(props, "force_lens_dof_render", icon="DRIVER_DISTANCE", emboss=True, icon_only=True, invert_checkbox=True )
            else:
                #row.prop(props, "force_lens_dof_render", icon="IPO_LINEAR", emboss=True, icon_only=True )
                row.prop(props, "force_lens_dof_render", icon="RESTRICT_INSTANCED_ON", emboss=True, icon_only=True )
                
            
            force_lens_render = context.scene.my_addon_props.force_lens_render
            
            if force_lens_render:
                row.prop(props, "force_lens_render", icon="VIEW_CAMERA", emboss=True, icon_only=True, invert_checkbox=True )
            else:
                row.prop(props, "force_lens_render", icon="VIEW_CAMERA_UNSELECTED", emboss=True, icon_only=True )
            
            
            
            
            
            
            
            row.prop(props, "help_disable_lens", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
            #expand=False,  emboss=True,
            
            if context.scene.my_addon_props.help_disable_lens:
                text  = 'Due to the nature of Lens Sim the camera has to be set to Orthographic to work, this button will disable the lens simulation and convert it to a normal blender camera that represents the lens '
                text += 'as closely as possible.'
                draw_text_box(layout, text, None )

            if LensSim_IsRendering and LensSim_ViewportModeLock:
                row.enabled = False
            else:
                row.enabled = True
            
            #layout.prop(material.inputs["viewport preview enable"].data, "default_value", text="Disable Lens", toggle=True, icon_only=False, icon="RESTRICT_RENDER_OFF")
            
            #layout.prop(props, "show_advanced_options", icon="SETTINGS" )
            #OPTIONS
            #TOOL_SETTINGS
            #SETTINGS
            #layout.prop(props, "lens_schematic", icon="LIGHT_DATA" )

            #layout.prop(material.inputs["schematic enable"], "default_value", text="Schematic", toggle=True, icon_only=False, icon="LIGHT_DATA")
            
            #split = layout.split(factor=0.9)
            #split.prop(material.inputs["schematic enable"], "default_value", text="          Schematic", toggle=True, icon_only=False, icon="LIGHT_DATA")
            #split.operator("object.open_lens_link_button", text="", icon="INTERNET", emboss=True)
            #layout.prop(material.inputs["camera object scale"], "default_value", text="Camera Scale")


            row = layout.row(align=True)
            row.prop(material.inputs["schematic enable"], "default_value", text="       Render Schematics", toggle=True, icon_only=False, icon="LIGHT_DATA")
            web_link = context.scene.my_addon_props.lens_link
            if web_link == "":
                row.operator("object.open_lens_link_button", text="", icon="INTERNET_OFFLINE", emboss=True, depress=False)
            else:
                row.operator("object.open_lens_link_button", text="", icon="INTERNET", emboss=True, depress=False)
            #split = layout.split(factor=0.1)
            #split.operator("object.open_lens_link_button", text="", icon="INTERNET", emboss=True)
            #split.prop(material.inputs["schematic enable"], "default_value", text="Schematic", toggle=True, icon_only=False, icon="LIGHT_DATA")
            
            row.prop(props, "help_schematic", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
            #expand=False,  emboss=True,
            
            if context.scene.my_addon_props.help_schematic:
                text  = 'Renders the schematic diagram of the current lens. -n -n '
                text += 'The aperture is shown in red, sensor in green. Each metric tile is 1x1cm big. '
                draw_text_box(layout, text, None )
            
            lens_schematic = material.inputs["schematic enable"].default_value
            if lens_schematic:
                
                #box = layout.box()
                split = layout.split(factor=0.55)
                split.prop(material.inputs["schematic scale"], "default_value", text="Scale")
                
                #layout.prop(props, "lens_schematic_isolate_lens" )
                split.prop(material.inputs["isolate lens"], "default_value", text="Isolate Lens")
                
                rays = material.inputs["cast rays"].default_value
                '''
                if rays:
                    
                    row = layout.row(align=True)
                    #split.prop(props, "lens_schematic_rays_enable",icon="GIZMO" )
                    
                    row.prop(material.inputs["cast rays"], "default_value", text="Rays", toggle=True, icon_only=False, icon="GIZMO")
                    
                    dir = material.inputs["cast rays dir"].default_value
                    
                    if dir:
                        #split.prop(props, "lens_schematic_rays_reverse_dir", text="", icon="BACK")
                        row.prop(material.inputs["cast rays dir"], "default_value", toggle=True, icon_only=True, icon="BACK")
                    else:
                        #split.prop(props, "lens_schematic_rays_reverse_dir", text="", icon="FORWARD")
                        row.prop(material.inputs["cast rays dir"], "default_value", toggle=True, icon_only=True, icon="FORWARD")

                else:
                    #layout.prop(props, "lens_schematic_rays_enable",icon="GIZMO" )
                    layout.prop(material.inputs["cast rays"], "default_value", text="Rays", toggle=True, icon_only=False, icon="GIZMO")
                '''
                dir = material.inputs["cast rays dir"].default_value
                
                row = layout.row(align=True)
                row.prop(material.inputs["cast rays"], "default_value", text="Rays", toggle=True, icon_only=False, icon="GIZMO")
                
                if dir:
                    row.prop(material.inputs["cast rays dir"], "default_value", text="", toggle=True, icon_only=True, icon="BACK")
                else:
                    row.prop(material.inputs["cast rays dir"], "default_value", text="", toggle=True, icon_only=True, icon="FORWARD")
                

                #box = layout.box()
            
            row = layout.row(align=True)
            row.prop(material.inputs["camera object scale"], "default_value", text="Camera Scale")
            row.prop(props, "help_camera_scale", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
            #expand=False,  emboss=True,            
            if context.scene.my_addon_props.help_camera_scale:
                text  = 'Scales the camera and sensor mesh to avoid scene intersections with the ray portal plane. Will not affect the rendered image. -n -n '
                text += 'Note; Setting this value too small will result in floating point issues when camera is not at the center of the scene. Recommended size > 0.15'
                draw_text_box(layout, text, None )
            
            
            
            #show_advance = context.scene.my_addon_props.show_advanced_options
            #if not show_advance:


            #layout = self.layout
            #props = context.scene.my_addon_props
            
            layout.separator()
            
            '''
            row = layout.row(align=True)
            row.prop(material.inputs["f stop"], "default_value", text="F-Stop")
            row.prop(props, "help_f_stop", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

            if context.scene.my_addon_props.help_f_stop:
                text  = 'Controls the aperture opening, minimum value is clamped by the lens F Number.'
                draw_text_box(layout, text, None )
            '''
            
            row = layout.row(align=True)
            
            f_factor = material.inputs["f stop factor override enable"].default_value
            
            if f_factor == False:
                row.prop(material.inputs["f stop"], "default_value", text="F-Stop")
            else:
                row.prop(material.inputs["f stop factor override"], "default_value", text="Aperture Factor")
            
            row.prop(material.inputs["f stop factor override enable"], "default_value", icon="NORMALIZE_FCURVES", emboss=True, icon_only=True)
            
            row.prop(props, "help_f_stop", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

            if context.scene.my_addon_props.help_f_stop:
                text  = 'Controls the aperture opening, minimum value is clamped by the lens F Number. -n -n'
                draw_text_box(layout, text, [["NORMALIZE_FCURVES" , "Aperture opening is scaled by a factor"]] )
            
            
            

            focus_layout(layout, context)

            layout.separator()

            row = layout.row(align=True)
            row.prop(material.inputs["chromatic aberration"], "default_value", text="Chromatic Aberration")
            
            #if material.inputs["chromatic aberration disable color"].default_value:
            #    row.prop(material.inputs["chromatic aberration disable color"], "default_value", text="", icon="SHADING_RENDERED")
            #else:
            #    row.prop(material.inputs["chromatic aberration disable color"], "default_value", text="", icon="SHADING_WIRE")
                
            if material.inputs["chromatic aberration disable color"].default_value:
                row.prop(material.inputs["chromatic aberration disable color"], "default_value", text="", icon="COLORSET_08_VEC")
            else:
                row.prop(material.inputs["chromatic aberration disable color"], "default_value", text="", icon="COLORSET_13_VEC")

            row.prop(props, "help_chromatic_aberration", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
            
            if context.scene.my_addon_props.help_chromatic_aberration:
                # Create a row to hold both the label and the icon
                text  = 'A value of 1.0 is the natural chromatic aberration amount for the lens. '
                text += 'The slider is not locked and can be set to negative values. -n -n '
                text += 'To calculate the Chromatic Aberration a random wavelength color on the visible light spectrum is sampled and '
                text += 'refracted based on the ior and abbe value(how much color diffraction the lens has) of each lens. '
                text += 'We get proper wavelength folding through as each wavelength gets refracted slightly different to each other. '
                text += 'Due to this each lens gets its own unique characteristics. -n '
                draw_text_box(layout, text, [["COLORSET_13_VEC", "Disable wavelength colors"]] )
                
                #box = layout.box()
                #box.scale_y = 0.5
                #box.label(text="disables colors", icon="COLORSET_13_VEC")
                
                #for line in wrapped_lines:
                    #box.label(text=line)
                
                #row.label(text="", icon='INFO')
                #row.label(text="sadf")



        # do we need this?
        #layout.prop(props, "auto_import", text="Auto Import")
        #layout.operator("object.import_lens") 



class AdvancedSettingsPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_AdvancedSettingsPanel" # sub panel id
    bl_label = "Advanced Settings"
    bl_parent_id = "VIEW3D_PT_LensSim_MainPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {"DEFAULT_CLOSED"}
    
    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True
        
    def draw(self, context):

        layout = self.layout
        props = context.scene.my_addon_props

class AdvancedSettingsCameraPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_AdvancedSettingsCameraPanel" # sub panel id
    bl_label = "Camera"
    bl_parent_id = "VIEW3D_PT_LensSim_AdvancedSettingsPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    #bl_options = {"DEFAULT_CLOSED"}
    
    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True
    
    def draw_header_preset(self, context):
        layout = self.layout
        props = context.scene.my_addon_props
        
        layout.operator("object.reset_camera_ctrl_button", text="", icon="TRASH")
    
    def draw(self, context):

        layout = self.layout
        #props = context.scene.my_addon_props
        
        #layout.operator("object.reset_camera_ctrl_button", text="Reset Settings", icon="TRASH")
        
        #layout.props("reset_camera_ctrl_button" )

class AperturePanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_AperturePanel" # sub panel id
    bl_label = "Aperture"
    bl_parent_id = "VIEW3D_PT_LensSim_AdvancedSettingsCameraPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True

    def draw(self, context):

        layout = self.layout
        props = context.scene.my_addon_props
        
        material = get_lens_camera_node()
        if material == None:
            return
        
        #layout.prop(props, "fstop" )
        #layout.prop(material.inputs["f stop"], "default_value", text="f-stop")

        #layout.prop(props, "aperture_auto_exposure" )
        
        #layout.prop(props, "aperture_ray_guiding" )
        row = layout.row(align=True)
        row.prop(material.inputs["aperture auto exposure"], "default_value", text="Compensate Exposure")
        row.prop(props, "help_compensate_exposure", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_compensate_exposure:
            text  = 'Automatically adjusts the exposure to account for changes in aperture, ensuring consistent brightness.'
            draw_text_box(layout, text, None )
            
        row = layout.row(align=True)
        row.prop(material.inputs["aperture ray guiding"], "default_value", text="Ray Guiding")
        row.prop(props, "help_ray_guiding", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_ray_guiding:
            text  = 'Will guide rays towards the aperture opening to minimize the loss of rays not getting through the lens.'
            draw_text_box(layout, text, None )
        
        
        #
        # Use Image
        #
        
        row = layout.row(align=True)
        row.prop(material.inputs["aperture custom image"], "default_value", text="Aperture Image", toggle=True, icon="IMAGE_DATA" )
        row.prop(props, "help_aperture_image", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

        if context.scene.my_addon_props.help_aperture_image:
            text  = 'Will replace the shape of the aperture opening, by default the shape is a perfect circle reaching the edges of the squared image with a area covering 0.7854% of the image. '
            text += '-n -n A color value of {0.0,0.0,0.0} will block all light, {1.0,1.0,1.0} will let all light through. -n -n '
            text += 'Note; If the aperture shape is much smaller than the image, the f-stop will effectively be stopped down. Also, rays will miss the opening and result in slower render times.  '
            draw_text_box(layout, text, None )
            #layout.separator()

        if material.inputs["aperture custom image"].default_value:

            image_texture_node = LensSim_LensMaterial.node_tree.nodes["BokehTextureCustom"]

            layout.template_ID( image_texture_node, "image", open="image.open")
            # draw image
            if image_texture_node.image:
                # Optional: You can draw the actual image preview
                image_name = image_texture_node.image.name
                # Draw the texture preview in the panel
                layout.template_ID_preview( image_texture_node , "image", hide_buttons=True)
                # (data, property, new, open, unlink, rows, cols, filter, hide_buttons)

                # color space
                #layout.prop(image_texture_node.image.colorspace_settings, "name", text="" )

                bokeh_image_mode_layout(layout, context)
                layout.prop(material.inputs["aperture custom image gamma"], "default_value", text="Gamma" )

                layout.separator()
                
                row = layout.row()
                row.label(text="Multiply")
                row.prop(material.inputs["aperture custom image mult"], "default_value", text="" )
                #row = layout.row()
                #row.operator("object.bokeh_image_calc_white_color_sum", text="White Color Sum")
                #row.operator("object.bokeh_image_calc_unit_intensity_sum", text="Inensity Sum")

                layout.prop(material.inputs["aperture custom image rotation"], "default_value", text="Rotation" )


class CameraObjectPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_CameraObjectPanel" # sub panel id
    bl_label = "Object"
    bl_parent_id = "VIEW3D_PT_LensSim_AdvancedSettingsCameraPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True
    
    def draw(self, context):
        
        layout = self.layout
        props = context.scene.my_addon_props

        material = get_lens_camera_node()
        if material == None:
            return

        #row = layout.row(align=True)
        #row.prop(material.inputs["camera object scale"], "default_value", text="Camera Scale")
        #row.prop(material.inputs["camera object scale even"], "default_value", text="", icon="CON_SAMEVOL")
        
        #layout.prop(material.inputs["lens geo enable"], "default_value", text="Draw Lens In 3D View", icon="OUTLINER_DATA_MESH", toggle=True)
        layout.prop(material.inputs["lens geo enable"], "default_value", text="Draw Lens In 3D View")
        
        row = layout.row(align=True)
        row.prop(material.inputs["lens mesh distance"], "default_value", text="Lens Mesh Distance")
        row.prop(props, "help_lens_mesh_distance", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

        if context.scene.my_addon_props.help_lens_mesh_distance:
            text  = 'The distance from the camera to the ray portal plane, might resolve some floating point issues if adjusted further away from camera.'
            draw_text_box(layout, text, None )
        
        layout.separator()
        
        row = layout.row(align=True)
        row.prop(material.inputs["lens internal rotation"], "default_value", text="Lens Rotation")
        internal_rotation_layout(row, context, True)
        row.prop(props, "help_internal_rotation", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

        if context.scene.my_addon_props.help_internal_rotation:
            text  = 'Rotate the lens. -n Usefull when shooting in a portrait orientation to avoid rotating the camera. -n '
            draw_text_box(layout, text, [["SPLIT_HORIZONTAL", "Rotate by 90 degrees"]] )
        
        #(data, property, text, text_ctxt, translate, icon, placeholder, expand, slider, toggle, icon_only, event, full_event, emboss, index, icon_value, invert_checkbox)
        
        layout.separator()

        main_row = layout.row(align=True)
        row1 = main_row.row(align=True)
        row1.label(text="Passepartout")
        row1.prop(LensSim_Camera.data, "show_passepartout", text="")
    
        row2 = main_row.row(align=True)
        row2.prop(LensSim_Camera.data, "passepartout_alpha")
        if not LensSim_Camera.data.show_passepartout:
            row2.enabled = False

        row = layout.row()
        row.label(text="Clip Start")
        #row.prop(LensSim_Camera.data, "clip_end", text="")
        row2 = row.row(align=True)
        row2.prop(material.inputs["clip start"], "default_value", text="")
        row2.prop(props, "help_clipping", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

        row = layout.row()
        row.label(text="End")
        row2 = row.row(align=True)
        row2.prop(LensSim_Camera.data, "clip_end", text="")
        row2.prop(props, "help_clipping", icon="BLANK1", emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_clipping:
            text  = 'The ray must first hit the ray portal plane before clipping starts, so everything in between the camera and '
            text += 'ray portal plane will always be rendered.'
            draw_text_box(layout, text, None )
        
        layout.separator()
        
        main_row = layout.row(align=True)
        row1 = main_row.row(align=True)
        row1.label(text="Censor Display Shape")
        row1.prop(LensSim_LensMesh, "display_bounds_type", text="")


class SensorPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_SensorPanel" # sub panel id
    bl_label = "Sensor"
    bl_parent_id = "VIEW3D_PT_LensSim_AdvancedSettingsCameraPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True
    
    def draw(self, context):
        
        layout = self.layout
        props = context.scene.my_addon_props

        material = get_lens_camera_node()
        if material == None:
            return
        
        layout.prop(material.inputs["flip"], "default_value", text="Flip")
        
        layout.prop(material.inputs["unsqueeze"], "default_value", text="Unsqueeze")
        layout.prop(material.inputs["squeeze factor add"], "default_value", text="Squeeze Factor Add")
        layout.prop(material.inputs["squeeze factor override"], "default_value", text="Squeeze Factor Override")
        
        layout.separator()
        
        row = layout.row(align=True)
        row.prop(material.inputs["monitor mode"], "default_value", text="Monitor Mode")
        row.prop(props, "help_monitor_mode", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_monitor_mode:
            text  = 'Will enable rendering the lens without the use of a orthographic camera setup, the ray portal plane will act as a monitor.'
            draw_text_box(layout, text, None )
        
        #layout.operator("object.export_lens")



class LensDirtPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_LensDirtPanel" # sub panel id
    bl_label = "Lens Dirt"
    bl_parent_id = "VIEW3D_PT_LensSim_AdvancedSettingsCameraPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True
    
    def draw(self, context):

        layout = self.layout
        props = context.scene.my_addon_props
        
        material = get_lens_camera_node()
        if material == None:
            return
        
        #layout.prop(props, "fstop" )
        #layout.prop(material.inputs["f stop"], "default_value", text="f-stop")

        #layout.prop(props, "aperture_auto_exposure" )
        #layout.prop(props, "aperture_ray_guiding" )
        #layout.prop(material.inputs["aperture auto exposure"], "default_value", text="Compensate Exposure")
        #layout.prop(material.inputs["aperture ray guiding"], "default_value", text="Ray Guiding")
        
        
        #
        # Use Image
        #
        
        row = layout.row(align=True)
        row.prop(material.inputs["lens dirt object enable"], "default_value", text="Lens Dirt, Type 1", toggle=True, icon="IMAGE_DATA" )
        row.prop(props, "help_lens_dirt_image_new", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_lens_dirt_image_new:
            text  = 'Will add a mesh in front of the lens, blocking and scattering light. -n -n '
            text += 'A color value of {0.0,0.0,0.0} will be fully transparent, a color value greater than {0.0,0.0,0.0} will block and scatter light. -n -n '
            text += 'Note; This feature might not work with all emulation methods. '
            draw_text_box(layout, text, None )
            #layout.separator()
        
        lens_surface_enabled = material.inputs["lens dirt object enable"].default_value
        
        if lens_surface_enabled:
            
            mat = get_lens_dirt_surface_material()
            
            if mat != None:
            
                image_texture_node = mat.node_tree.nodes["Image Texture"]
                
                
                box = layout.box()
                box.template_ID( image_texture_node, "image", open="image.open")
                
                if image_texture_node.image:
                    
                    box.template_ID_preview( image_texture_node , "image", hide_buttons=True)
                    #box = layout.box()
                    box.label(text="Image RGB Curves:")
                    box.template_curve_mapping( mat.node_tree.nodes["RGB Curves"] , "mapping")
                    
                    box01 = box
                    box01.label(text="Mapping:")
                    row01 = box01.row()
                    row01.prop( mat.node_tree.nodes["Mapping"].inputs["Location"] , "default_value", text="Location" )
                    row01 = box01.row()
                    row01.prop( mat.node_tree.nodes["Mapping"].inputs["Rotation"] , "default_value", text="Rotation" )
                    row01 = box01.row()
                    row01.prop( mat.node_tree.nodes["Mapping"].inputs["Scale"] , "default_value", text="Scale" )

                    layout.separator()
                    
                    row = box.row()
                    
                    box01 = row.box()
                    box01.label(text="Light Scatter")
                    box01.prop( mat.node_tree.nodes["AdditiveOpacity"].inputs["Factor"] , "default_value", text="Amount" )
                    box01.separator()
                    box01.prop( mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"] , "default_value", text="Roughness" )
                
                    box02 = row.box()
                    box02.label(text="Light Block")
                    box02.prop( mat.node_tree.nodes["SubtractOpacity"].inputs["Factor"] , "default_value", text="Amount" )
                    box02.separator()
                    box02.prop( mat.node_tree.nodes["Map Range"].inputs["From Min"] , "default_value", text="From Min" )
                    box02.prop( mat.node_tree.nodes["Map Range"].inputs["From Max"] , "default_value", text="From Max" )
            
                    row = box.row(align=True)
                    row.prop( material.inputs["lens dirt object distance"], "default_value", text="Mesh Distance" )
                    row.prop(props, "help_lens_dirt_mesh_distance", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
                    
                    if context.scene.my_addon_props.help_lens_dirt_mesh_distance:
                        text  = 'Distance from the last lens element to the lens dirt mesh. -n -n '
                        text += 'A bigger distance will result in a sharper lens dirt effect, but will also be less realistic. '
                        text += 'Increasing the distance can fix some issues with emulation effects due to rays not hitting the dirt mesh. '
                        draw_text_box(box, text, None )
                        #layout.separator()
                    
                    row = box.row(align=True)
                    row.prop( material.inputs["lens dirt object scale"], "default_value", text="Mesh Scale" )
                    row.prop(props, "help_lens_dirt_mesh_scale", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
                    
                    if context.scene.my_addon_props.help_lens_dirt_mesh_scale:
                        text  = 'Scale of the lens dirt mesh. -n -n '
                        text += 'A larger scale can fix some issues with the lens dirt surface being too small. '
                        draw_text_box(box, text, None )
            
            
        #layout.separator()
        
        
        
        
        
        row = layout.row(align=True)
        row.prop(material.inputs["lens dirt image"], "default_value", text="Lens Dirt, Type 2", toggle=True, icon="IMAGE_DATA" )
        row.prop(props, "help_lens_dirt_image", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

        if context.scene.my_addon_props.help_lens_dirt_image:
            text  = 'Will add a image at the front lens surface, the image will only block light, not scatter light. '
            text += '-n -n A color value of {0.0,0.0,0.0} will block all light, {1.0,1.0,1.0} will let all light through. '
            draw_text_box(layout, text, None )
            #layout.separator()

        if material.inputs["lens dirt image"].default_value:

            image_texture_node = LensSim_LensMaterial.node_tree.nodes["LensDirtImage"]

            layout.template_ID( image_texture_node, "image", open="image.open")
            # draw image
            if image_texture_node.image:
                # Optional: You can draw the actual image preview
                image_name = image_texture_node.image.name
                # Draw the texture preview in the panel
                layout.template_ID_preview( image_texture_node , "image", hide_buttons=True)
                # (data, property, new, open, unlink, rows, cols, filter, hide_buttons)

                # color space
                #layout.prop(image_texture_node.image.colorspace_settings, "name", text="" )


                lens_dirt_image_mode_layout(layout, context)
                
                row = layout.row(align=True)
                row.prop(material.inputs["lens dirt image gamma"], "default_value", text="Gamma" )
                row.prop(props, "help_lens_dirt_image_gamma", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

                if context.scene.my_addon_props.help_lens_dirt_image_gamma:
                    text  = 'Changes the gamma of the imput image. -n -n '
                    text += 'Note; When changed the color correction will be recalculated, this calculation is quite slow on larger images. '
                    draw_text_box(layout, text, None )
                
                
                layout.separator()
                
                row = layout.row()
                row.label(text="Multiply")
                row.prop(material.inputs["lens dirt image mult"], "default_value", text="" )
                #row = layout.row()
                #row.operator("object.bokeh_image_calc_white_color_sum", text="White Color Sum")
                #row.operator("object.bokeh_image_calc_unit_intensity_sum", text="Inensity Sum")

                layout.prop(material.inputs["lens dirt image rotation"], "default_value", text="Rotation" )
                #layout.prop(material.inputs["lens dirt image opacity"], "default_value", text="Opacity" )
                layout.prop(material.inputs["lens dirt image opacity"], "default_value", text="Opacity" )




class SplitDiopterPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_SplitDiopterPanel" # sub panel id
    bl_label = "Split Diopter"
    bl_parent_id = "VIEW3D_PT_LensSim_AdvancedSettingsCameraPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True

    def draw(self, context):
        layout = self.layout
        props = context.scene.my_addon_props
        material = get_lens_camera_node()
        if material == None:
            return
        
        main_material = get_main_material()
        
        #layout.prop(props, "chromatic_aberration_type", text="" )
        
        row = layout.row()
        row.prop(material.inputs["enable diopter 02"], "default_value", text="Diopter 01", toggle=True)
        roww = row.row(align=True)
        roww.prop(material.inputs["enable diopter 01"], "default_value", text="Diopter 02", toggle=True)
        roww.prop(props, "help_diopter", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

        if context.scene.my_addon_props.help_diopter:
            text  = 'Adds a extra lens element in front of the lens that changes the focus distance of the lens. The lens element is '
            text += 'cut in half, enabling you to focus at two places at the same time. '
            draw_text_box(layout, text, None )


        row = layout.row()
        row01 = row.row()
        row01.prop(material.inputs["diopter focal length 02"], "default_value", text="Focal Length")
        if material.inputs["enable diopter 02"].default_value != 1:
            row01.enabled = False
        
        row02 = row.row(align=True)
        row02.prop(material.inputs["diopter focal length 01"], "default_value", text="Focal Length")
        row02.prop(props, "help_diopter", icon="BLANK1", emboss=True, icon_only=True )
        if material.inputs["enable diopter 01"].default_value != 1:
            row02.enabled = False
        
        row = layout.row()
        row01 = row.row()
        row01.prop(material.inputs["diopter offset 02"], "default_value", text="Offset")
        if material.inputs["enable diopter 02"].default_value != 1:
            row01.enabled = False
        
        row02 = row.row(align=True)
        row02.prop(material.inputs["diopter offset 01"], "default_value", text="Offset")
        row02.prop(props, "help_diopter", icon="BLANK1", emboss=True, icon_only=True )
            
        if material.inputs["enable diopter 01"].default_value != 1:
            row02.enabled = False

        layout.separator()
        row = layout.row()
        rotate = row.prop(material.inputs["diopter rotate"], "default_value", text="Rotation")
        #if material.inputs["enable diopter 01"].default_value + material.inputs["enable diopter 02"].default_value == 0:
            #row.enabled = False
        
        row = layout.row(align=True)
        row.prop(material.inputs["diopter distance"], "default_value", text="Distance", toggle=True)
        row.prop(props, "help_diopter_distance", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        #if material.inputs["enable diopter 01"].default_value + material.inputs["enable diopter 02"].default_value == 0:
            #row.enabled = False
            
        if context.scene.my_addon_props.help_diopter_distance:
            text  = 'Distance from the last lens element to the diopter. Will increase the sharpness of the split. '
            draw_text_box(layout, text, None )

class TiltShiftPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_TiltShiftPanel" # sub panel id
    bl_label = "Tilt Shift"
    bl_parent_id = "VIEW3D_PT_LensSim_AdvancedSettingsCameraPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True

    def draw(self, context):

        layout = self.layout
        props = context.scene.my_addon_props
        #layout.prop(props, "global_scale")

        material = get_lens_camera_node()
        if material == None:
            return
        
        row = layout.row(align=True)
        row.label(text="Tilt")
        row.prop(material.inputs["tilt shift angle x"], "default_value", text="X")
        row.prop(material.inputs["tilt shift angle y"], "default_value", text="Y")
        row.prop(props, "help_tilt", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        row = layout.row(align=True)
        row.label(text="Pivot")
        row.prop(material.inputs["tilt shift pivot x"], "default_value", text="X")
        row.prop(material.inputs["tilt shift pivot y"], "default_value", text="Y")  
        row.prop(props, "help_tilt", icon="BLANK1", emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_tilt:
            text  = 'Will tilt the sensor at its Pivot position.'
            draw_text_box(layout, text, None )
            
        layout.separator()

        row = layout.row(align=True)
        row.label(text="Shift")
        row.prop(material.inputs["tilt shift offset x"], "default_value", text="X")
        row.prop(material.inputs["tilt shift offset y"], "default_value", text="Y")
        row.prop(props, "help_offset", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_offset:
            text  = 'Will offset the sensor position. '
            draw_text_box(layout, text, None )



class EmulationPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_EmulationPanel" # sub panel id
    bl_label = "Emulation"
    bl_parent_id = "VIEW3D_PT_LensSim_AdvancedSettingsCameraPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True
    
    def draw(self, context):
        
        layout = self.layout
        props = context.scene.my_addon_props

        material = get_lens_camera_node()
        if material == None:
            return
        
        #layout.prop(material.inputs["flip"], "default_value", text="flip")
        #layout.prop(material.inputs["unsqueeze"], "default_value", text="unsqueeze")
        #layout.prop(material.inputs["monitor mode"], "default_value", text="monitor mode")
        
        #layout.operator("object.export_lens")


'''
class FocusPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_FocusPanel" # sub panel id
    bl_label = "Focus"
    bl_parent_id = "VIEW3D_PT_LensSim_AdvancedSettingsCameraPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True

    def draw(self, context):

        layout = self.layout
        props = context.scene.my_addon_props
        material = get_lens_camera_node()
        
        
        
        #focus_layout(layout, context)
        layout.prop(material.inputs["focusing screen"], "default_value", text="Focusing Screen")
'''

class ChromaticAberrationPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_ChromaticAberrationPanel" # sub panel id
    bl_label = "Chromatic Aberration"
    bl_parent_id = "VIEW3D_PT_LensSim_EmulationPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True

    def draw(self, context):
        layout = self.layout
        props = context.scene.my_addon_props
        material = get_lens_camera_node()
        if material == None:
            return
        
        main_material = get_main_material()
        
        #layout.prop(props, "chromatic_aberration_type", text="" )
        row = layout.row(align=True)
        row.prop(material.inputs["chromatic aberration type"], "default_value", text="Custom Ramp", toggle=True)
        row.prop(props, "help_custom_ramp", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

        if context.scene.my_addon_props.help_custom_ramp:
            text  = 'Replaces the default wavelength colors when sampling the Chromatic Aberration. Using a Custom '
            text += 'Ramp will also replace the Abbe Value(used to calculate dispersion) with a uniform value. '
            draw_text_box(layout, text, None )
            #layout.separator()

        #layout.operator("object.export_lens")
        
        chromatic_aberration_type = material.inputs["chromatic aberration type"].default_value
        

        if chromatic_aberration_type:
            
            
            layout.separator()
            layout.operator("object.custom_color_ramp_reset_button", icon="TRASH")
            row = layout.row(align=True)
            row.label(text="Presets:")
            row.operator("object.custom_color_ramp_preset01")
            row.operator("object.custom_color_ramp_preset02")
            row.operator("object.custom_color_ramp_preset03")
            row.operator("object.custom_color_ramp_preset04")
            
            
            layout.separator()
            
            layout.template_color_ramp( main_material.node_tree.nodes["Custom Chromatic Aberration Color Ramp"] , "color_ramp", expand=True)
            
            
            layout.separator()
            row = layout.row()
            row.label(text="Multiply")
            row.prop(material.inputs["custom color ramp mult"], "default_value", text="")
            row = layout.row(align=True)
            split = row.split()
            split.operator("object.custom_color_ramp_white_color_sum_button")
            split.operator("object.custom_color_ramp_intensity_sum_button")
            row.prop(props, "help_custom_ramp_color_correction", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

            if context.scene.my_addon_props.help_custom_ramp_color_correction:
                text  = 'White Color Sum; Will replace the Multiply value so that the Color Ramp will average to a white color, this will '
                text += 'keep the exposure and color tint of the render. -n -n '
                text += 'Intesity Sum; Will replace the Multiply value so that the image exposure will not be changed, this will keep the '
                text += 'color tint of the Color Ramp. '
                draw_text_box(layout, text, None )
            
            
            layout.separator()
            row = layout.row(align=True)
            row.label(text="Wavelength Diffraction Spread:")
            row.prop(props, "help_custom_ramp_wavelength_diffraction_spread", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

            if context.scene.my_addon_props.help_custom_ramp_wavelength_diffraction_spread:
                text  = 'Photons along the visible wavelength spectrum does not spread evenly when diffracted, this curve controls the spread of the colors in the Color Ramp. '
                draw_text_box(layout, text, None )

            layout.template_curve_mapping( main_material.node_tree.nodes["Custom Chromatic Aberration Float Curve"] , "mapping")



class BloomGlarePanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_BloomGlarePanel" # sub panel id
    bl_label = "Bloom/Glare"
    bl_parent_id = "VIEW3D_PT_LensSim_EmulationPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True

    def draw(self, context):

        layout = self.layout
        props = context.scene.my_addon_props
        
        material = get_lens_camera_node()
        if material == None:
            return
        
        #layout.prop(props, "global_scale")
        '''
        layout.prop(props, "bloom_amount")
        layout.prop(props, "bloom_size")
        layout.separator()
        layout.prop(props, "glare_amount")
        layout.prop(props, "glare_size")
        layout.prop(props, "glare_rotate")
        layout.prop(props, "glare_streaks")
        '''
        
        row = layout.row(align=True)
        row.prop(material.inputs["bloom amount"], "default_value", text="Bloom Amount")
        row.prop(props, "help_bloom", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        row = layout.row(align=True)
        row.prop(material.inputs["bloom size"], "default_value", text="Bloom Size")
        row.prop(props, "help_bloom", icon="BLANK1", emboss=True, icon_only=True )

        if context.scene.my_addon_props.help_bloom:
            text  = 'Will offset a factor of rays in the x.y position.'
            draw_text_box(layout, text, None )
        
        layout.separator()
        row = layout.row(align=True)
        row.prop(material.inputs["glare amount"], "default_value", text="Glare Amount")
        row.prop(props, "help_glare", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        row = layout.row(align=True)
        row.prop(material.inputs["glare size"], "default_value", text="Glare Size")
        row.prop(props, "help_glare", icon="BLANK1", emboss=True, icon_only=True )
        row = layout.row(align=True)
        row.prop(material.inputs["glare rotate"], "default_value", text="Glare Rotate")
        row.prop(props, "help_glare", icon="BLANK1", emboss=True, icon_only=True )
        row = layout.row(align=True)
        row.prop(material.inputs["glare streaks"], "default_value", text="Glare Streaks")
        row.prop(props, "help_glare", icon="BLANK1", emboss=True, icon_only=True )

        if context.scene.my_addon_props.help_glare:
            text  = 'Will offset a factor of rays in the x.y position in a star shape pattern.'
            draw_text_box(layout, text, None )

        
class DistortionPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_DistortionPanel" # sub panel id
    bl_label = "Distortion"
    bl_parent_id = "VIEW3D_PT_LensSim_EmulationPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True

    def draw(self, context):

        layout = self.layout
        props = context.scene.my_addon_props
        #layout.prop(props, "global_scale")

        material = get_lens_camera_node()
        if material == None:
            return
        
        layout.prop(material.inputs["distortion amount"], "default_value", text="Amount")
        layout.prop(material.inputs["distortion exponent"], "default_value", text="Exponent")  



class AnamorphEmulatorPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_AnamorphEmulatorPanel" # sub panel id
    bl_label = "Anamorph/Bokeh"
    bl_parent_id = "VIEW3D_PT_LensSim_EmulationPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True

    def draw(self, context):

        layout = self.layout
        props = context.scene.my_addon_props
        #layout.prop(props, "global_scale")

        material = get_lens_camera_node()
        if material == None:
            return
        
        row = layout.row(align=True)
        row.prop(material.inputs["anamorph emulator squeeze factor"], "default_value", text="Squeeze Factor")
        row.prop(props, "help_squeeze_factor", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_squeeze_factor:
            text  = 'Emulates an anamorphic lens element squeezing the image in the x axis. '
            draw_text_box(layout, text, None )
        
        #layout.separator()
        
        row = layout.row(align=True)
        row.prop(material.inputs["anamorph emulator bokeh aspect ratio reliable"], "default_value", text="Bokeh Aspect")
        row.prop(props, "help_bokeh_aspect", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_bokeh_aspect:
            text  = 'Compensates the Squeeze Factor by squeezing the bokeh in the x axis. '
            draw_text_box(layout, text, None )
            

        row = layout.row(align=True)
        row.prop(material.inputs["anamorph emulator bokeh aspect ratio"], "default_value", text="Bokeh Aspect (Wierd)")
        row.prop(props, "help_bokeh_aspect_wierd", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_bokeh_aspect_wierd:
            text  = 'Compensates the Squeeze Factor by squeezing the bokeh. -n '
            text += 'Everything behind the focus plane will be squeezed in the x axis, everything in front of the '
            text += 'focus plane will be squeezed in the y axis. Artifacts will occur. '
            draw_text_box(layout, text, None )
        
        
        layout.separator()
        
        row = layout.row(align=True)
        row.prop(material.inputs["bokeh swirliness"], "default_value", text="Bokeh Swirliness")
        row.prop(props, "help_bokeh_swirliness", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_bokeh_swirliness:
            text  = 'Scales the bokeh shape towards the center of the image, creating a swirling effect. '
            draw_text_box(layout, text, None )

        row = layout.row(align=True)
        row.prop(material.inputs["bokeh swirliness min dist"], "default_value", text="From Min")
        row.prop(material.inputs["bokeh swirliness max dist"], "default_value", text="From Max")
        row.prop(props, "help_bokeh_swirliness_min_max", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        row = layout.row(align=True)
        row.prop(material.inputs["bokeh swirliness min amount"], "default_value", text="Min Amount")
        row.prop(props, "help_bokeh_swirliness_min_max", icon="BLANK1", emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_bokeh_swirliness_min_max:
            text  = 'Creates a transition between Min Amount and Bokeh Swirliness, From Min and From Max sets the blend distance. '
            draw_text_box(layout, text, None )

        layout.separator()

        row = layout.row(align=True)
        row.prop(material.inputs["dof factor"], "default_value", text="Dof Factor")
        row.prop(props, "help_dof_factor", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_dof_factor:
            text  = 'Scales the bokeh shape, creating more depth of field. '
            draw_text_box(layout, text, None )


class ExperimentalPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_ExperimentalPanel" # sub panel id
    bl_label = "Controversial"
    bl_parent_id = "VIEW3D_PT_LensSim_EmulationPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True

    def draw(self, context):

        layout = self.layout
        props = context.scene.my_addon_props
        #layout.prop(props, "global_scale")

        material = get_lens_camera_node()
        if material == None:
            return
        
        #layout.prop(material.inputs["global scale"], "default_value", text="Global Scale")
        row = layout.row(align=True)
        row.label(text="Ray Portal Scale")
        row.prop(material.inputs["ray portal plane scale x"], "default_value", text="X")
        row.prop(material.inputs["ray portal plane scale y"], "default_value", text="Y")
        
        if material.inputs["ray portal plane scale y is x"].default_value:
            row.prop(material.inputs["ray portal plane scale y is x"], "default_value", text="", icon="LINKED", invert_checkbox=True)
        else:
            row.prop(material.inputs["ray portal plane scale y is x"], "default_value", text="", icon="UNLINKED")
        
        
        row.prop(props, "help_lens_scale", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_lens_scale:
            text  = 'Will scale the ray portal plane object in the x.y axis. '
            text += 'This will widen the focal length.'
            draw_text_box(layout, text, None )
        
        
        row = layout.row(align=True)
        row.prop(material.inputs["global scale"], "default_value", text="Global Scale")
        
        row.prop(props, "help_global_scale", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_global_scale:
            text  = 'Scales the whole lens. -n '
            text += 'When scale > 1.0 the scene will become smaller relative to the camera. '
            text += 'At scale < 1.0 the scene will become larger relative to the camera. -n -n '
            text += 'Note; The slight change in focal length is due to the focus breathing since the camera has to focus '
            text += 'closer or further when the camera size changes. '
            draw_text_box(layout, text, None )
        
        layout.separator()
        
        row = layout.row(align=True)
        row.prop(material.inputs["change focal length"], "default_value", text="Focal Length Add")
        row.prop(props, "help_focal_length_add", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_focal_length_add:
            text  = 'Scales the outgoing ray vector in the x.y axis, creating a larger field of view. '
            draw_text_box(layout, text, None )
        


class BlurEmulatorPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_BlurEmulatorPanel" # sub panel id
    bl_label = "Blur"
    bl_parent_id = "VIEW3D_PT_LensSim_EmulationPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True

    def draw(self, context):

        layout = self.layout
        props = context.scene.my_addon_props
        #layout.prop(props, "global_scale")

        material = get_lens_camera_node()
        if material == None:
            return
        
        layout.prop(material.inputs["radial blur angle"], "default_value", text="Radial Blur Angle")
        layout.prop(material.inputs["radial blur power"], "default_value", text="Radial Blur Exponent")
        #layout.separator()
        
        #layout.prop(material.inputs["anamorph emulator bokeh aspect ratio reliable"], "default_value", text="Bokeh Aspect")
        
        #row = layout.split(factor=LensSim_CalcButtonFactor)
        #row.prop(material.inputs["anamorph emulator bokeh aspect ratio reliable"], "default_value", text="Bokeh Aspect")
        #row.prop(material.inputs["anamorph emulator bokeh aspect ratio reliable swirly"], "default_value", text="Swirly",toggle=True, icon_only=True)
        
        #layout.separator()
        #layout.label(text="Alternative versions:")
        #layout.prop(material.inputs["anamorph emulator bokeh aspect ratio"], "default_value", text="Bokeh Aspect (Wierd)")
        #layout.separator()
        
        #layout.prop(material.inputs["bokeh swirliness"], "default_value", text="Bokeh Swirliness")

        #(data, property, text, text_ctxt, translate, icon, placeholder, expand, slider, toggle, icon_only, event, full_event, emboss, index, icon_value, invert_checkbox)








#
# Create lens Panel
#

def reset_camera_properties(self, context, ignore_list):
    
    material = get_lens_camera_node()
    if material == None:
        return
    
    main_material = get_main_material()
    lens_node_grp = bpy.data.node_groups["LensSim_LensCTRL"]

    for parm in lens_node_grp.interface.items_tree:
        try:
            type = parm.in_out
            if type == "INPUT":
                
                ignore = False
                
                if len(ignore_list) > 0:
                    ignore = False

                    if parm.name.endswith(" state"):
                        ignore = True

                    else:
                        for ignore_name in ignore_list:
                            if ignore_name.endswith("*"):
                                if parm.name.startswith( ignore_name[:-1] ):
                                    ignore = True
                            else:
                                if parm.name == ignore_name:
                                    ignore = True
                if not ignore:
                    
                    # we ignore " state" to force a update
                    if not parm.name.endswith(" state"):
                        default = parm.default_value
                        material.inputs[ parm.name ].default_value = default

        except:
            continue


    material = get_main_material()
    
    # reset focus object
    if not "focus object" in ignore_list:
        remove_focus_object()
    
    # clear image textures
    for node in material.node_tree.nodes:
        if node.type == 'TEX_IMAGE':
            if node.name != "BokehImage":
                node.image = None

    # clear previous image names labels
    material.node_tree.nodes["BokehImageCustomName"].label = ""
    material.node_tree.nodes["LensDirtImageName"].label = ""

    use_focus_object_update(self, context)

    color_ramp = main_material.node_tree.nodes["Custom Chromatic Aberration Color Ramp"].color_ramp
    reset_color_ramp(color_ramp)
    
    float_curve = main_material.node_tree.nodes["Custom Chromatic Aberration Float Curve"].mapping
    reset_float_curve(float_curve)

    sync_material_parms()

    #viewport_mode()
    #update_material_parms()


def reset_lens_properties():

    # reset link parameter
    props = bpy.context.scene.my_addon_props
    setattr(props, "lens_link", "")
    setattr(props, "new_lens_name", "MyNewLens")

    material = get_lens_node()

    lens_node_grp = bpy.data.node_groups["LensSim_LensData"]

    for parm in lens_node_grp.interface.items_tree:
        
        try:
            type = parm.in_out
            if type == "INPUT":
                default = parm.default_value
                material.inputs[ parm.name ].default_value = default
        except:
            continue

def color_ramp_sample_avg( color_ramp ):
    
    samples = 200

    avg_colors = [0.0,0.0,0.0]

    for i in range(0,samples,1):
        position = i/(samples-1)
        color = color_ramp.evaluate(position)

        avg_colors[0] += color[0] / samples
        avg_colors[1] += color[1] / samples
        avg_colors[2] += color[2] / samples

    return avg_colors


class CustomColorRampPreset01Button(bpy.types.Operator):
    bl_idname = "object.custom_color_ramp_preset01"
    bl_label = "Color Spectrum"
    bl_description=""
    
    def execute(self, context):

        # reset color ramp
        main_material = get_main_material()
        color_ramp = main_material.node_tree.nodes["Custom Chromatic Aberration Color Ramp"].color_ramp
        reset_color_ramp(color_ramp)
        
        color_ramp.elements[0].position = 0.0
        color_ramp.elements[0].color = (0.1,0.0,0.0,1.0)
        
        color_ramp.elements[1].position = 0.066667
        color_ramp.elements[1].color = (0.2,0.0,0.0,1.0)
        
        color_ramp.elements.new(2)
        color_ramp.elements[2].position = 0.133333
        color_ramp.elements[2].color = (0.4,0.0,0.0,1.0)
        
        color_ramp.elements.new(3)
        color_ramp.elements[3].position = 0.2
        color_ramp.elements[3].color = (0.6,0.0,0.0,1.0)
        
        color_ramp.elements.new(4)
        color_ramp.elements[4].position = 0.266667
        color_ramp.elements[4].color = (0.6,0.0,0.0,1.0)
        
        color_ramp.elements.new(5)
        color_ramp.elements[5].position = 0.333333
        color_ramp.elements[5].color = (0.8,0.0,0.0,1.0)
        
        color_ramp.elements.new(6)
        color_ramp.elements[6].position = 0.4
        color_ramp.elements[6].color = (0.8,0.6,0.0,1.0)
        
        color_ramp.elements.new(7)
        color_ramp.elements[7].position = 0.466667
        color_ramp.elements[7].color = (0.5,1.0,0.0,1.0)
        
        color_ramp.elements.new(8)
        color_ramp.elements[8].position = 0.533333
        color_ramp.elements[8].color = (0.25,1.0,0.0,1.0)
        
        color_ramp.elements.new(9)
        color_ramp.elements[9].position = 0.6
        color_ramp.elements[9].color = (0.0,1.0,0.0,1.0)
        
        color_ramp.elements.new(10)
        color_ramp.elements[10].position = 0.666667
        color_ramp.elements[10].color = (0.0,1.0,0.9,1.0)
        
        color_ramp.elements.new(11)
        color_ramp.elements[11].position = 0.733333
        color_ramp.elements[11].color = (0.0,0.2,1.0,1.0)
        
        color_ramp.elements.new(12)
        color_ramp.elements[12].position = 0.8
        color_ramp.elements[12].color = (0.05,0.0,1.0,1.0)
        
        color_ramp.elements.new(13)
        color_ramp.elements[13].position = 0.866667
        color_ramp.elements[13].color = (0.0,0.0,0.9,1.0)
        
        color_ramp.elements.new(14)
        color_ramp.elements[14].position = 0.933333
        color_ramp.elements[14].color = (0.2,0.0,0.5,1.0)
        
        color_ramp.elements.new(15)
        color_ramp.elements[15].position = 1.0
        color_ramp.elements[15].color = (0.2,0.0,0.5,1.0)
        
        bpy.ops.object.custom_color_ramp_white_color_sum_button('INVOKE_DEFAULT')
        
        return {'FINISHED'}
    
class CustomColorRampPreset02Button(bpy.types.Operator):
    bl_idname = "object.custom_color_ramp_preset02"
    bl_label = "Yellow Blue"
    bl_description=""
    
    def execute(self, context):

        # reset color ramp
        main_material = get_main_material()
        color_ramp = main_material.node_tree.nodes["Custom Chromatic Aberration Color Ramp"].color_ramp
        reset_color_ramp(color_ramp)

        color_ramp.elements[0].color = (1.0,1.0,0.0,1.0)
        color_ramp.elements[1].color = (0.0,0.0,1.0,1.0)
        
        bpy.ops.object.custom_color_ramp_white_color_sum_button('INVOKE_DEFAULT')
        '''
        # Ensure there are only two elements, one at position 0.0 and one at 1.0
        if len(color_ramp.elements) < 2:
            color_ramp.elements.new(1)
        else:
            while len(color_ramp.elements) > 2:
                color_ramp.elements.remove(color_ramp.elements[-1])  # Remove the last element

        # Reset the first element to be at position 0.0 with black color
        color_ramp.elements[0].position = 0.0
        color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)  # RGBA for black

        # Reset the second element to be at position 1.0 with white color
        color_ramp.elements[1].position = 1.0
        color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)  # RGBA for white
        
        color_ramp.color_mode = "RGB"
        color_ramp.interpolation = "LINEAR"
        '''
        return {'FINISHED'}
    
class CustomColorRampPreset03Button(bpy.types.Operator):
    bl_idname = "object.custom_color_ramp_preset03"
    bl_label = "Magenta Green"
    bl_description=""
    
    def execute(self, context):

        # reset color ramp
        main_material = get_main_material()
        color_ramp = main_material.node_tree.nodes["Custom Chromatic Aberration Color Ramp"].color_ramp
        reset_color_ramp(color_ramp)
        
        color_ramp.elements[0].color = (1.0,0.0,1.0,1.0)
        color_ramp.elements[1].color = (0.0,1.0,0.0,1.0)
        
        bpy.ops.object.custom_color_ramp_white_color_sum_button('INVOKE_DEFAULT')
        
        return {'FINISHED'}
    
class CustomColorRampPreset04Button(bpy.types.Operator):
    bl_idname = "object.custom_color_ramp_preset04"
    bl_label = "Cyan Red"
    bl_description=""
    
    def execute(self, context):

        # reset color ramp
        main_material = get_main_material()
        color_ramp = main_material.node_tree.nodes["Custom Chromatic Aberration Color Ramp"].color_ramp
        reset_color_ramp(color_ramp)
        
        color_ramp.elements[0].color = (0.0,1.0,1.0,1.0)
        color_ramp.elements[1].color = (1.0,0.0,0.0,1.0)
        
        bpy.ops.object.custom_color_ramp_white_color_sum_button('INVOKE_DEFAULT')
        
        return {'FINISHED'}


class CustomColorRampWhiteColorSumButton(bpy.types.Operator):
    bl_idname = "object.custom_color_ramp_white_color_sum_button"
    bl_label = "White Color Sum"
    bl_description=""
    
    def execute(self, context):

        main_material = get_main_material()
        color_ramp = main_material.node_tree.nodes["Custom Chromatic Aberration Color Ramp"].color_ramp

        avg_colors = color_ramp_sample_avg( color_ramp )

        material = get_lens_camera_node()
        material.inputs["custom color ramp mult"].default_value[0] = 1.0 / avg_colors[0]
        material.inputs["custom color ramp mult"].default_value[1] = 1.0 / avg_colors[1]
        material.inputs["custom color ramp mult"].default_value[2] = 1.0 / avg_colors[2]
        
        return {'FINISHED'}
    
class CustomColorRampUnitIntensitySumButton(bpy.types.Operator):
    bl_idname = "object.custom_color_ramp_intensity_sum_button"
    bl_label = "Intensity Sum"
    bl_description=""
    
    def execute(self, context):

        main_material = get_main_material()
        color_ramp = main_material.node_tree.nodes["Custom Chromatic Aberration Color Ramp"].color_ramp

        avg_colors = color_ramp_sample_avg( color_ramp )

        intensity_sum = ( avg_colors[0] + avg_colors[1] + avg_colors[2] ) / 3.0
        
        material = get_lens_camera_node()
        material.inputs["custom color ramp mult"].default_value[0] = 1.0 / intensity_sum
        material.inputs["custom color ramp mult"].default_value[1] = 1.0 / intensity_sum
        material.inputs["custom color ramp mult"].default_value[2] = 1.0 / intensity_sum
        
        return {'FINISHED'}

class CustomColorRampResetButton(bpy.types.Operator):
    bl_idname = "object.custom_color_ramp_reset_button"
    bl_label = "Reset To Default"
    bl_description=""
    
    def execute(self, context):

        main_material = get_main_material()
        color_ramp = main_material.node_tree.nodes["Custom Chromatic Aberration Color Ramp"].color_ramp
        reset_color_ramp(color_ramp)
        
        material = get_lens_camera_node()
        material.inputs["custom color ramp mult"].default_value[0] = 1.0
        material.inputs["custom color ramp mult"].default_value[1] = 1.0
        material.inputs["custom color ramp mult"].default_value[2] = 1.0
        
        return {'FINISHED'}

class ResetLensPropertiesButton(bpy.types.Operator):
    bl_idname = "object.reset_lens_data_props_button"
    bl_label = ""
    bl_description="Reset Lens Data settings"
    
    #message: StringProperty(name="Message")
    #message: StringProperty(name="enter text", default="yolo")
    #message: Label(name="afsd")
    #bpy.props.StringProperty(name="Message")

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        
        layout.label(text="Are you sure? This will reset Lens Data parms to default.")
        #layout.label(text=current_lens)
    
    def execute(self, context):

        reset_lens_properties()
        
        return {'FINISHED'}



class ReRegisterEventHandlersButton(bpy.types.Operator):
    bl_idname = "object.re_register_event_handlers_button"
    bl_label = ""
    bl_description="Re installs the event handlers. Fixes issue with buttons not working"
    
    def execute(self, context):

        re_apply_event_handlers( True )
        
        return {'FINISHED'}


class OpenLensLinkButton(bpy.types.Operator):
    bl_idname = "object.open_lens_link_button"
    bl_label = "Web Link"
    bl_description="Opens a web link to the current Lens"
    
    #message: StringProperty(name="Message")
    #message: StringProperty(name="enter text", default="yolo")
    #message: Label(name="afsd")
    #bpy.props.StringProperty(name="Message")

    
    def invoke(self, context, event):

        web_link = get_link_parm()
        if web_link == "":
            
            wm = context.window_manager
            return wm.invoke_props_dialog(self)
        return self.execute(context)
    
    def draw(self, context):
        layout = self.layout
        
        layout.label(text="This lens has no Web Link.")
        #layout.label(text=current_lens)
        
    def execute(self, context):

        web_link = get_link_parm()
        if web_link != "":
            webbrowser.open( web_link )
        
        return {'FINISHED'}

def reset_color_ramp(color_ramp):
    
    # Ensure there are only two elements, one at position 0.0 and one at 1.0
    if len(color_ramp.elements) < 2:
        color_ramp.elements.new(1)
    else:
        while len(color_ramp.elements) > 2:
            color_ramp.elements.remove(color_ramp.elements[-1])  # Remove the last element

    # Reset the first element to be at position 0.0 with black color
    color_ramp.elements[0].position = 0.0
    color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)  # RGBA for black

    # Reset the second element to be at position 1.0 with white color
    color_ramp.elements[1].position = 1.0
    color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)  # RGBA for white
    
    color_ramp.color_mode = "RGB"
    color_ramp.interpolation = "LINEAR"

def reset_float_curve(float_curve):
    
    # Initialize the curve mapping to reset it
    #float_curve.initialize()
    #float_curve.update()
    
    for curve in float_curve.curves:
        # Remove all existing points
        while len(curve.points) > 2:
            curve.points.remove(curve.points[0])
    
        curve.points[0].location = (0.0, 0.0)
        curve.points[1].location = (1.0, 1.0)
    
    # Set the default clipping and black/white levels
    float_curve.black_level = (0.0, 0.0, 0.0)
    float_curve.white_level = (1.0, 1.0, 1.0)
    float_curve.clip_min_x = 0.0
    float_curve.clip_min_y = 0.0
    float_curve.clip_max_x = 1.0
    float_curve.clip_max_y = 1.0
    
    # update curve
    float_curve.update()


def resync_selected_lens(context):
    
    current_lens = get_current_lens()
    
    lenses = get_installed_lenses(None, context)
    for lens in lenses:
        if current_lens == lens[0]:
            context.scene.my_addon_props.lenses_enum = current_lens
    

class ResyncSelectedLensButton(bpy.types.Operator):
    bl_idname = "object.resync_selected_lens_button"
    bl_label = ""
    bl_description="Resync selected camera"
    
    def execute(self, context):

        resync_selected_lens(context)
        
        return {'FINISHED'}

class ResetCameraCTRLButton(bpy.types.Operator):
    bl_idname = "object.reset_camera_ctrl_button"
    bl_label = ""
    bl_description="Reset Camera settings"
    
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        
        layout.label(text="Are you sure? This will reset Camera parms to default.")
        #layout.label(text=current_lens)
    
    def execute(self, context):

        ignore = [  "viewport preview enable", "camera object scale",
                    "schematic*", "isolate lens", "cast*",
                    "focus*", "sensor pos", "rack focus", "astigmatizer",  "focus object",
                    "sensor mode", "focal length", "viewfinder scale",
                    "f stop",
                    "chromatic aberration"]

        reset_camera_properties(self, context, ignore)
        
        return {'FINISHED'}
    


class ResetAllCameraCTRLButton(bpy.types.Operator):
    bl_idname = "object.reset_all_camera_ctrl_button"
    bl_label = "reset camera CTRLs"
    bl_description="Reset All Camera Settings"
    
    def execute(self, context):

        ignore = []
        reset_camera_properties(self, context, ignore)
        
        return {'FINISHED'}
    

class AddAnamorphicButton(bpy.types.Operator):
    bl_idname = "object.add_anamorphic_button"
    bl_label = "add anamorphic adapter"
    bl_description="Adds a 2x Anamorphic Adapter to the lens"
    
    def execute(self, context):

        lens_node = get_lens_node()
        
        
        adapter_scale = 0.001
        adapter = [ [ "r", [ -151.881, 40.0, 40.0, 137.505, 100000.0, 101.25, 101.25, -137.505 ]],
                    [ "d", [ 4.8, 0.0, 13.0, 86.9, 4.4, 0.0, 11.2, 4.0 ]],
                    [ "dia", [ 68, 62, 62, 0.0, 69, 0.0, 69, 0.0 ]],
                    [ "t", [ 2,2,2,2 ]],
                    [ "ior", [ 1.6229, 1.6241, 1.6241, 1.6229 ]],
                    [ "V", [ 60.06, 36.11 , 36.11 , 60.06 ]] ]
        
        scale = lens_node.inputs[ "unit scale" ].default_value
        
        lens_node.inputs[ "rack focus idx" ].default_value = 2
        lens_node.inputs[ "aperture idx" ].default_value = lens_node.inputs[ "aperture idx" ].default_value + 4
        
        scale_mult = ( lens_node.inputs["dia1"].default_value * lens_node.inputs["unit scale"].default_value ) / (adapter[2][1][0] * adapter_scale)
        
        #scale_mult *= 1.25
        scale_mult *= context.scene.my_addon_props.anamorphoc_adapter_scale_mult
        #overwrite = False
        overwrite = False
        
        for data in adapter:
            
            name = data[0]
            values = data[1]
            
            x = 0
            
            if not overwrite:
                
                x = LensSim_MaxLenses*2
                
                while x != 0:
                    try:
                        lens_node.inputs[ name + str(x) ].default_value = lens_node.inputs[ name + str(x - len( values ) ) ].default_value
                    except:
                        pass

                    x -= 1
            
            x = 1
            for value in values:
                if name == "r" or name == "d" or name == "dia":
                    lens_node.inputs[ name + str(x) ].default_value = value * adapter_scale * (1.0/scale) * scale_mult
                else:
                    lens_node.inputs[ name + str(x) ].default_value = value
                x += 1
        
        build_lens_system()
        #bpy.ops.object.calculate_rack_focus_lut('INVOKE_DEFAULT')
        
        return {'FINISHED'}

class RemoveAnamorphicButton(bpy.types.Operator):
    bl_idname = "object.remove_anamorphic_button"
    bl_label = ""
    bl_description="Removes the adapter"
    
    def execute(self, context):

        lens_node = get_lens_node()
        
        
        adapter_exists = True
        if lens_node.inputs[ "t1" ].default_value != 2:
            adapter_exists = False
        if lens_node.inputs[ "t2" ].default_value != 2:
            adapter_exists = False
        if lens_node.inputs[ "t3" ].default_value != 2:
            adapter_exists = False
        if lens_node.inputs[ "t4" ].default_value != 2:
            adapter_exists = False
        if lens_node.inputs[ "t5" ].default_value != 0:
            adapter_exists = False
        if lens_node.inputs[ "rack focus idx" ].default_value == 0:
            adapter_exists = False
            
        if not adapter_exists:
            return {'FINISHED'}
        
        
        
        lens_node.inputs[ "rack focus idx" ].default_value = 0
        lens_node.inputs[ "aperture idx" ].default_value = lens_node.inputs[ "aperture idx" ].default_value - 4
        
        
        attributes = ["r", "d", "dia", "ior", "V", "t"]
        
        for attribute in attributes:
            name = attribute
            
            if name == "r" or name == "d" or name == "dia":
                
                x = 1
                while x != LensSim_MaxLenses*2:
                    try:
                        lens_node.inputs[ name + str(x) ].default_value = lens_node.inputs[ name + str( x + 8 ) ].default_value
                    except:
                        try:
                            lens_node.inputs[ name + str(x) ].default_value = 0.0
                        except:
                            pass
                    x += 1
            else:
                
                x = 1
                while x != LensSim_MaxLenses+1:
                    try:
                        lens_node.inputs[ name + str(x) ].default_value = lens_node.inputs[ name + str( x + 4 ) ].default_value
                    except:
                        try:
                            lens_node.inputs[ name + str(x) ].default_value = 0
                        except:
                            pass
                    x += 1
            

        
        build_lens_system()
        #bpy.ops.object.calculate_rack_focus_lut('INVOKE_DEFAULT')
        
        return {'FINISHED'}






def search_lenses_update(self, context, edit_text):

    context.scene.my_addon_props.search_lenses_enable = True

    lenses = get_installed_lenses(self, context)
    
    candidates = []
    for lens in lenses:
        candidates.append( lens[1] )
    #candidates = ["Apple", "Banana", "Cherry", "Date", "Elderberry", "Fig", "Grape"]
    
    # Filter the candidates based on the edit_text input
    filtered = [item for item in candidates if edit_text.lower() in item.lower()]
    
    # Optionally return additional info with each candidate
    return [(item, "A type of fruit") for item in filtered]

def search_lenses_apply(self, context):
    
    search_string = context.scene.my_addon_props.search_lenses
    
    if search_string != "":
    
        lenses = get_installed_lenses(self, context)
        
        chosen_lens = None
        
        for lens in lenses:
            if search_string == lens[1]:
                chosen_lens = lens[0]
        
        if chosen_lens != None:
            props = bpy.context.scene.my_addon_props
            props.lenses_enum = chosen_lens
            
        context.scene.my_addon_props.search_lenses = ""
    
    context.scene.my_addon_props.search_lenses_enable = False


def remove_focus_object():
    
    lens_material = get_main_material()

    # Access the driven property
    node = lens_material.node_tree.nodes["custom focus object"]

    # remove old driver
    for x in range(3):
        socket = node.inputs[x]
        driver = socket.driver_remove("default_value")
        
        socket.default_value = 0
        
    return

def focus_object_update(self, context):

    focus_object = context.scene.my_addon_props.focus_object

    lens_material = get_main_material()

    # Access the driven property
    node = lens_material.node_tree.nodes["custom focus object"]

    if focus_object == None:
        
        # remove old driver
        for x in range(3):
            socket = node.inputs[x]
            driver = socket.driver_remove("default_value")
            
            socket.default_value = 0
            
        return

    
    drivers = [ ["loc_x", "LOC_X", "WORLD_SPACE"],
                ["loc_y", "LOC_Y", "WORLD_SPACE"],
                ["loc_z", "LOC_Z", "WORLD_SPACE"] ]
    
    for x in range(3):
        
        socket = node.inputs[x]

        # Add a driver to the 'default_value' of the socket
        driver = socket.driver_add("default_value").driver

        # Clear existing variables if any
        #driver.variables.clear()

        # Iterate through all variables and remove them
        while driver.variables:
            driver.variables.remove(driver.variables[0])
        
        # Add a new variable to the driver
        var = driver.variables.new()
        var.name = drivers[x][0]
        var.type = 'TRANSFORMS'

        # Set up the target for the driver variable
        target = var.targets[0]
        target.id = focus_object
        target.transform_type = drivers[x][1]
        target.transform_space = drivers[x][2]

        # Set the driver expression to use the variable
        driver.expression = drivers[x][0]





def viewport_mode_button_update( self, context ):
    viewport_mode()



#
# define buttons
#

class MyAddonProperties(bpy.types.PropertyGroup):
    #geo_file_path: bpy.props.StringProperty(
    #    name="Geo File Path",
    #    description="Path to the .geo file",
    #    default="//blender_instance_points_v001.geo",
    #    subtype='FILE_PATH'
    #)
    
    pin_camera: bpy.props.BoolProperty(
        name="Pin Camera",
        description="",
        default=False
    )

    favorite: bpy.props.BoolProperty(
        name="",
        description="Mark lens as favorite",
        update=favorite_set,
        default=False
    )
    
    help_disable_lens: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_camera_scale: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_f_stop: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_schematic: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_focus_sample_h: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_image_scale_ref: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_sensor_best_fit_size: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_limit_last_lens_diameter: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_sensor_focus_pos: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_visualize_ray_hit: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_ray_spread: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_ray_edge_angle: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_guide_spread: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_guide_coverage: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_guide_coverage_values: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_unit_scale: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_aperture: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_rack_focus_index: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_surfaces: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_chromatic_aberration: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_rack_focus_LUT: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_build_lens_graph: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_lens_mesh_distance: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_clipping: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_monitor_mode: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_compensate_exposure: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_ray_guiding: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_bloom: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_glare: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_tilt: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_offset: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    
    help_lens_scale: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_global_scale: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_squeeze_factor: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_bokeh_aspect: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_bokeh_aspect_wierd: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_bokeh_swirliness: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_bokeh_swirliness_min_max: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_dof_factor: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_focal_length_add: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_aperture_image: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_lens_dirt_image: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_lens_dirt_image_gamma: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_lens_dirt_image_new: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_custom_ramp: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_custom_ramp_color_correction: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_custom_ramp_wavelength_diffraction_spread: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_diopter: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    help_diopter_distance: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_internal_rotation: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_lens_dirt_mesh_distance: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    help_lens_dirt_mesh_scale: bpy.props.BoolProperty(
        name="Help",
        description="",
        default=False
    )
    
    sensor_mode_items = [
                #("0","Maximized Coverage",""),
                ("0","Best Fit",""),
                ("1","Focal Length",""),
                ("2","Sensor Width","")
                ]
                
    description  = "Sets the camera sensor size.\n\n"
    description += "Best Fit: Sensor will fill the largest usable image area with an aspect ratio of 1.777\n"
    description += "Focal Length: Will replicate blenders focal length\n"
    description += "Sensor Width: Set cusom sensor size\n"
    description += "\nNote; Best Fit is a general solution and is not suited for wide format aspect ratios. For anamorphic "
    description += "lenses I recommend setting the sensor width manually.\n"
    description += "\nCurrent mode"
    
    sensor_mode0: bpy.props.EnumProperty(
        items = sensor_mode_items,
        name="sensor",
        description=description,
        default="0",
        update=update_sensor_mode
    )
    sensor_mode1: bpy.props.EnumProperty(
        items = sensor_mode_items,
        name="sensor",
        description=description,
        default="1",
        update=update_sensor_mode
    )
    sensor_mode2: bpy.props.EnumProperty(
        items = sensor_mode_items,
        name="sensor",
        description=description,
        default="2",
        update=update_sensor_mode
    )


    focusing_screen0: bpy.props.BoolProperty(
        name="",
        description="Enable focusing screen",
        default=False,
        update=focusing_screen_update
    )
    focusing_screen1: bpy.props.BoolProperty(
        name="",
        description="Enable focusing screen",
        default=True,
        update=focusing_screen_update
    )




    name         = "Rotates the lens by 90 degrees."
    description  = "Usefull when shooting in a portrait orientation to avoid rotating the camera"
    
    internal_rotation0: bpy.props.BoolProperty(
        name=name,
        description=description,
        default=0,
        update=internal_rotation_update
    )
    internal_rotation1: bpy.props.BoolProperty(
        name=name,
        description=description,
        default=1,
        update=internal_rotation_update
    )
    
    
    
    description  = "Modes for focusing.\n\n"
    description += "Focus Empty: Use a focus empty for focusing\n"
    description += "Focus Object: Focus on the origin point of an object\n"
    description += "Distance: Set focus distance\n"
    description += "Manual: Move sensor manually\n\n"
    description += "Note; All focus distances are callibrated in the center of the image. Due to the nature of the lenses the focus "
    description += "might be off when trying to focus off center.\n"
    description += "\nCurrent mode"
    
    focus_mode_items = [
                ("0","Focus Empty",""),
                ("-1","Focus Object",""),
                ("1","Distance",""),
                ("2","Manual","")
                ]
                
    focus_mode_description  = "Modes for focusing."
    
    
    focus_mode00: bpy.props.EnumProperty(
        items = focus_mode_items,
        name="focus mode",
        description=description,
        default="-1",
        update=use_focus_object_update
    )
    focus_mode0: bpy.props.EnumProperty(
        items = focus_mode_items,
        name="focus mode",
        description=description,
        default="0",
        update=use_focus_object_update
    )
    focus_mode1: bpy.props.EnumProperty(
        items = focus_mode_items,
        name="focus mode",
        description=description,
        default="1",
        update=use_focus_object_update
    )
    focus_mode2: bpy.props.EnumProperty(
        items = focus_mode_items,
        name="focus mode",
        description=description,
        default="2",
        update=use_focus_object_update
    )
    
    focus_object: bpy.props.PointerProperty(
        name="Select Object",
        type=bpy.types.Object,
        description="Pick an object from the scene",
        update=focus_object_update
    )
    

    focus_empty_attach_help = "Unparent Focus Empty from the camera"

    focus_empty_attach0: bpy.props.BoolProperty(
        name="",
        description=focus_empty_attach_help,
        default=False,
        update=focus_empty_attach_update
    )
    focus_empty_attach1: bpy.props.BoolProperty(
        name="",
        description=focus_empty_attach_help,
        default=True,
        update=focus_empty_attach_update
    )

    anamorphoc_adapter_scale_mult: bpy.props.FloatProperty(
        name="",
        description="Scale of the adapter relative to the last lens element.",
        default=1.5
    )
    
    '''
    chromatic_aberration_type2: bpy.props.EnumProperty(
        items = chromatic_aberration_type_items,
        name="type",
        description="",
        default="2",
        update=chromatic_aberration_type_update
    )
    chromatic_aberration_type3: bpy.props.EnumProperty(
        items = chromatic_aberration_type_items,
        name="type",
        description="",
        default="3",
        update=chromatic_aberration_type_update
    )
    chromatic_aberration_type4: bpy.props.EnumProperty(
        items = chromatic_aberration_type_items,
        name="type",
        description="",
        default="4",
        update=chromatic_aberration_type_update
    )
    chromatic_aberration_type5: bpy.props.EnumProperty(
        items = chromatic_aberration_type_items,
        name="type",
        description="",
        default="5",
        update=chromatic_aberration_type_update
    )
    '''

    description  = 'Adds color correction to the image. \n\n'
    description += 'White Color Sum: Sum of the RGB pixels will be {1.0,1.0,1.0}. Will compensate for brightness loss and color tint. \n'
    description += 'Intensity Sum: Sum of the (R+G+B)/3.0 will be 1.0. Will only compensate for brightness loss. \n'
    description += "\nCurrent mode"

    bokeh_image_mode_items = [
                ("0","No Color Correction",""),
                ("1","White Color Sum",""),
                ("2","Intensity Sum","")
                ]

    bokeh_image_mode0: bpy.props.EnumProperty(
        items = bokeh_image_mode_items,
        name="type",
        description=description,
        default="0",
        update=bokeh_image_mode_update
    )
    bokeh_image_mode1: bpy.props.EnumProperty(
        items = bokeh_image_mode_items,
        name="type",
        description=description,
        default="1",
        update=bokeh_image_mode_update
    )
    bokeh_image_mode2: bpy.props.EnumProperty(
        items = bokeh_image_mode_items,
        name="type",
        description=description,
        default="2",
        update=bokeh_image_mode_update
    )


    lens_dirt_image_mode_items = [
                ("0","No Color Correction",""),
                ("1","White Color Sum",""),
                ("2","Intensity Sum","")
                ]

    lens_dirt_image_mode0: bpy.props.EnumProperty(
        items = lens_dirt_image_mode_items,
        name="type",
        description=description,
        default="0",
        update=lens_dirt_image_mode_update
    )
    lens_dirt_image_mode1: bpy.props.EnumProperty(
        items = lens_dirt_image_mode_items,
        name="type",
        description=description,
        default="1",
        update=lens_dirt_image_mode_update
    )
    lens_dirt_image_mode2: bpy.props.EnumProperty(
        items = lens_dirt_image_mode_items,
        name="type",
        description=description,
        default="2",
        update=lens_dirt_image_mode_update
    )



    # Define the string property
    new_lens_name: bpy.props.StringProperty(
        name="Name",
        description="Enter a custom name",
        default="MyNewLens",
        maxlen=1024,
    )
    
    # Define the string property
    lens_link: bpy.props.StringProperty(
        name="",
        description="Web Link to the lens",
        default="",
        maxlen=1024,
        update=on_link_parm_change
    )
    
    #custom_word = context.scene.my_addon_props.new_lens_name
    
    description  = 'Select lens. \n\n'
    description += 'Note; Keep in mind that some lenses might be built for a certain camera and sensor size, so even tho the '
    description += 'circle of illumination is quite large on a lens it might not be designed to have a large sensor. '
    description += 'Hence why the focal length is not a 1:1 ratio to how wide the field of view is.'
    description += '\n'
    description += 'Lenses with lower f-stops will in general have more depth of field.'
    description += '\n'
    description += '\nCurrent lens'
    
    lenses_enum: bpy.props.EnumProperty(
        name="Lenses",
        description=description,
        #description="Current lens",
        #items=[["asdf","asdf",""],["asdf","asdf",""]]
        #searchable=True,  # Bool Property to determine if list is searchable
        #search_options= {'SORT'},
        items=get_installed_lenses,
        update=on_lens_enum_change  # Call this function when the enum changes
    )
    #lens = context.scene.my_addon_props.lenses_enum
    
    search_lenses: bpy.props.StringProperty(
        name="Search lens.",
        search=search_lenses_update,
        update=search_lenses_apply
    )
    
    search_lenses_enable: bpy.props.BoolProperty(
        name="Quit searching.",
        default=False
    )
    
    disable_all: bpy.props.BoolProperty(
        name="Apply on all lenses",
        default=True,
        update=viewport_mode_button_update
    )
    
    description  = 'Force enable lenses when rendering with F12. \n \n'
    description += 'NB! Does not work when rendering from command line'
    
    force_lens_render: bpy.props.BoolProperty(
        name="",
        description=description,
        default=False,
        update=viewport_mode_button_update
    )
    
    force_lens_dof_render: bpy.props.BoolProperty(
        name="",
        description='Disables depth of field when lenses is disabled',
        default=True,
        update=viewport_mode_button_update
    )
    
    '''
    bokeh_enum: bpy.props.EnumProperty(
        name="Bokeh Shape",
        description="Default Bokeh Image",
        #items=[["asdf","asdf",""],["asdf","asdf",""]]
        items=update_bokeh_enum,
        update=on_bokeh_enum_change  # Call this function when the enum changes
    )
    '''
    #lens = context.scene.my_addon_props.lenses_enum
    









def CalcRayHitPosition( context, lens_data, reference_distance, ray_axis ):
    
    scene = context.scene
    #lens_props = scene.lens_data_props
    
    #lens_data = get_lens_data()
    lens_node = get_lens_node()

    unit_scale = lens_node.inputs[ "unit scale" ].default_value

    dia1 = lens_node.inputs[ "dia1" ].default_value
    focus_sample_h = lens_node.inputs[ "focus sample h" ].default_value

    ray_h = ( unit_scale * dia1 * 0.5 ) / focus_sample_h
    lens_length = lens_data[1]

    ray_lens_p = vec3(-lens_length,ray_h,0.0)
    
    ray_p = vec3(-reference_distance,0.0,0.0)
    ray_n = ray_lens_p - ray_p
    ray_n = vec3_normalize( ray_n )
    ray_p = ray_lens_p - ray_n
    
    plane_normal = vec3(0.0,1.0,0.0)
    plane_point = vec3(0.0,0.0,0.0)
    
    if ray_axis == 1:
        ray_n = vec3( ray_n[0],0.0,ray_n[1] )
        ray_p = vec3( ray_p[0],0.0,ray_p[1] )
        plane_normal = vec3(0.0,0.0,1.0)
    
    rays = []
    trace_backwards = False
    isolate_lens = 0

    ray_p, ray_n, rays = lens_trace( ray_p, ray_n, trace_backwards, lens_data, isolate_lens )
    ray_p = rayPlaneIntersect( ray_p, ray_n, plane_normal, plane_point)

    return ray_p[0]

def CalcOptimalRackFocusDist( context, lens_data_original, distance ):

    maxit = 500
    inc = 0.005
    error_threshold = 0.0000001
    
    rack_focus = 0.0
    result0 = 0.0
    result1 = 0.0
    dir = True
    
    for i in range(0,maxit,1):

        lens_data = lens_data_copy( lens_data_original )

        lens_data = lens_data_override_rack_focus( lens_data, rack_focus )

        result0 = CalcRayHitPosition( context, lens_data, distance, 0 )
        result1 = CalcRayHitPosition( context, lens_data, distance, 1 )
        
        if result0 > result1:
            if dir:
                inc *= 0.5
            dir = False
            rack_focus -= inc
        else:
            if not dir:
                inc *= 0.5
            dir = True
            rack_focus += inc
        
        #print(abs(result0-result1))
        
        if abs(result0-result1) < error_threshold:
            return rack_focus
        
    return rack_focus

class CalculateRackFocusLUT(bpy.types.Operator):
    bl_idname = "object.calculate_rack_focus_lut"
    bl_label = "caculate focus lut"
    
    def execute(self, context):

        scene = context.scene
        #lens_props = scene.lens_data_props

        lens_data = get_lens_data(False)
        lens_node = get_lens_node()

        for x in range(1,LensSim_RackFocusLUTSize+1):
            
            distance = lens_node.inputs[ "rack focus m lut"+str(x) ].default_value
            
            # reset to default
            if distance < 0.001:
                default_value = bpy.data.node_groups["LensSim_LensData"].interface.items_tree["rack focus m lut"+str(x)].default_value
                lens_node.inputs[ "rack focus m lut"+str(x) ].default_value = default_value
                distance = default_value
            
            rack_focus = CalcOptimalRackFocusDist( context, lens_data, distance )
            rack_focus *= 1000.0
        
            # set parms
            parm = "rack focus p lut"+str(x)
            lens_node.inputs[ parm ].default_value = rack_focus
            
            #lens_node.inputs[ parm ].default_value = rack_focus
            #setattr(lens_props, parm.replace(" ", "_"), rack_focus )
        
        #node = get_lens_camera_node()
        #bpy.data.materials["LensSimMaterial"].node_tree.nodes["LensSim"].inputs[13].default_value = rack_focus
        
        return {'FINISHED'}


#bpy.data.node_groups["LensData"].interface.items_tree[393].default_value

#bpy.data.node_groups["LensData"].interface.items_tree[293].default_value
#bpy.data.node_groups["LensData"].interface.items_tree[293].min_value
#interface.items_tree[293].max_value
#bpy.data.materials["LensSimMaterial"].node_tree.nodes["Lens"].inputs[30].default_value
#bpy.data.node_groups["LensData"].interface.items_tree[471].default_value
#bpy.data.node_groups["LensData"].interface.items_tree[471].min_value
#bpy.data.node_groups["LensData"].interface.items_tree[196].default_value



class SensorBestFitSizeAdd(bpy.types.Operator):
    bl_idname = "object.sensor_best_fit_size_add"
    bl_label = ""
    bl_description="Add a small increment"
    
    def execute(self, context):

        lens_node = get_lens_node()
        lens_node.inputs[ "default sensor size" ].default_value += 0.0002

        return {'FINISHED'}
    
class SensorBestFitSizeSubtract(bpy.types.Operator):
    bl_idname = "object.sensor_best_fit_size_subtract"
    bl_label = ""
    bl_description="Subtract a small increment"
    
    def execute(self, context):

        lens_node = get_lens_node()
        lens_node.inputs[ "default sensor size" ].default_value -= 0.0002

        return {'FINISHED'}
   
   
    
class BuildLensButton(bpy.types.Operator):
    bl_idname = "object.build_lens_button"
    bl_label = "Build Lens Graph"
    bl_description="when adding, removing or changing lens elements, its nessesary to rebuild the lens node graph"
    
    def execute(self, context):

        build_lens_system()

        return {'FINISHED'}

# ??? outdated?
class ReRegisterButton(bpy.types.Operator):
    bl_idname = "object.re_register_button"
    bl_label = ""
    bl_description="Re-registers event handlers, should fix issues with buttons not working"
    
    def execute(self, context):

        #unregister()
        #register()
        register_event_handlers()

        return {'FINISHED'}
    
    
def save_lens(lens_name, lens_path):
    
    #lenses_path = get_lenses_path()
    lens_node = get_lens_node()

    #lens_name = context.scene.my_addon_props.lenses_enum
    #lens_path = lenses_path + "\\" + lens_name

    #save_lens(lens_name, lens_path)
    
    
    lens_node = get_lens_node()
    lens_node_grp = bpy.data.node_groups["LensSim_LensData"]

    rack_focus_idx = False
    if lens_node.inputs["rack focus idx"].default_value > 0:
        rack_focus_idx = True

    file_content = []

    # get lens link
    link = get_link_parm()
    if link != "":
        file_content.append( "link = " + link )

    # get bokeh image
    image = bpy.context.scene.my_thumbnails
    if lens_node.inputs["aperture use image"].default_value == 1:
        file_content.append( "bokeh image = " + image )

    for parm in lens_node_grp.interface.items_tree:
        
        try:
            type = parm.in_out
            if type == "INPUT":
                default = parm.default_value
                
                # skip linked values
                if lens_node.inputs[ parm.name ].is_linked:
                    continue

                # skip rack focus if not enabled
                rack_focus_parm = parm.name.startswith( "rack focus" )
                if not rack_focus_idx and rack_focus_parm:
                    continue
                    
                value = lens_node.inputs[ parm.name ].default_value
                
                # skip none zero values
                if value == 0.0 or value == 0:
                    continue
                
                # round float values
                if isinstance(value, float):
                    value = round_float( value )
                
                file_content.append( parm.name + " = " + str(value) )
                
        except:
            continue
    
    
    #write file
    file = open(lens_path, 'w')
    
    for line in file_content:
        file.write( line + "\n" )
    file.close()
    
    
    '''
    lens_node = get_lens_node()
    
    rack_focus_idx = False
    if lens_node.inputs["rack focus idx"].default_value > 0:
        rack_focus_idx = True
    
    
    
    #write file
    file = open(lens_path, 'w')
    for parm in LensSim_LensParms:
        

        default_value = bpy.data.node_groups["LensData"].interface.items_tree["rack focus m lut"+str(x)].default_value
        
        val = lens_node.inputs[ parm ].default_value
        
        #val = round_float( lens_node.inputs.get( parm ).default_value )

        writeparm = False

        # dont write if rack focus is off, else write all rack focus parms
        if rack_focus_idx:
            if parm.startswith( "rack focus" ):
                writeparm = True
            else:
                if val != 0 and val != 0.0:
                    writeparm = True
        else:
            if not parm.startswith( "rack focus" ):
                if val != 0 and val != 0.0:
                    writeparm = True

        if writeparm:
            file.write( parm + " = " + str(val) + "\n" )
    file.close()
    '''    
    
    
class ExportLens(bpy.types.Operator):
    bl_idname = "object.export_lens"
    bl_label = "Save New"
    
    def execute(self, context):

        lenses_path = get_lenses_path()
        lens_node = get_lens_node()

        lens_name = context.scene.my_addon_props.new_lens_name
        new_lens_path = os.path.join(lenses_path, lens_name + ".txt")

        save_lens(lens_name, new_lens_path)

        return {'FINISHED'}

class SaveCurrentLens(bpy.types.Operator):
    bl_idname = "object.save_current_lens"
    bl_label = "Override Current"
    
    def invoke(self, context, event):

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        
        main_material = LensSim_LensMaterial
        current_lens = get_current_lens()
        
        layout.label(text="Are you sure? This will override:")
        layout.label(text=current_lens)
            
    def execute(self, context):

        lenses_path = get_lenses_path()
        lens_node = get_lens_node()

        lens_name = context.scene.my_addon_props.lenses_enum
        lens_path = os.path.join(lenses_path, lens_name)

        save_lens(lens_name, lens_path)

        return {'FINISHED'}


def lerp(a, b, t):
    return (1 - t) * a + t * b

def fit(value, oldmin, oldmax, newmin, newmax):
    # Linear interpolation formula to remap the value
    return newmin + ((value - oldmin) * (newmax - newmin) / (oldmax - oldmin))

def efit(value, oldmin, oldmax, newmin, newmax):
    # Normalize the input value to the 0-1 range
    t = (value - oldmin) / (oldmax - oldmin)
    
    # Remap to the new range
    result = newmin + t * (newmax - newmin)
    
    return result


def calculate_image_scale_ref( reference_distance, focal_length_add ):

    lens_data = get_lens_data(False)

    lens_length = lens_data[1]

    ray_p = vec3(1.0,0.002,0.0)
    ray_n = vec3(-1.0,0.0,0.0)
    
    rays = []
    trace_backwards = True
    isolate_lens = 0
    ray_p, ray_n, rays = lens_trace( ray_p, ray_n, trace_backwards, lens_data, isolate_lens )
    
    if focal_length_add != 0.0:
        
        focal_length_add = (focal_length_add * -0.01) + 1.0
        

        
        plane_normal = vec3(-1.0,0.0,0.0)
        plane_point = vec3(-lens_length,0.0,0.0)
        ray_p = rayPlaneIntersect( ray_p, ray_n, plane_normal, plane_point)
        ray_p[1] = ray_p[1] * focal_length_add
        ray_p[2] = ray_p[2] * focal_length_add
        
        ray_n[1] = ray_n[1] * focal_length_add
        ray_n[2] = ray_n[2] * focal_length_add
        
        ray_n = vec3_normalize(ray_n)
        
    
    plane_normal = vec3(-1.0,0.0,0.0)
    plane_point = vec3(-reference_distance,0.0,0.0)        
    ray_p = rayPlaneIntersect( ray_p, ray_n, plane_normal, plane_point)


    '''
    rays[ len(rays)-1 ] = ray_p
    ray_list = [rays]
    draw_baseray = False
    apply_rays(self, context, ray_list, draw_baseray)
    '''

    
    
    focal_length_ref = abs(ray_p[1])

    #focal_length_ref = focal_length_ref * efit( reference_distance, 3.0, 10.0, 1.0, 0.005 )

    return focal_length_ref


class CalcImageScaleRefButton(bpy.types.Operator):
    bl_idname = "object.calc_image_scale_ref"
    bl_label = "calc image scale ref"
    
    def execute(self, context):

        reference_distance = 3.0
        
        focal_length_ref = calculate_image_scale_ref( reference_distance, 0.0 )
        
        material = get_lens_node()
        material.inputs["image scale ref"].default_value = focal_length_ref
        
        #AutoApplyLensData(self, context)

        return {'FINISHED'}
    
class CalcFocusPosButton(bpy.types.Operator):
    bl_idname = "object.calc_focus_pos"
    bl_label = "calc focus pos"
    
    def execute(self, context):

        scene = context.scene
        #lens_props = scene.lens_data_props

        material = get_lens_node()

        #reference_distance = 3.0
        
        lens_data = get_lens_data(False)

        calculations = [[material.inputs[ "f s pos start m" ].default_value,   "f s pos start"],
                        [material.inputs[ "f s pos end m" ].default_value, "f s pos end"],
                        [material.inputs[ "squeeze factor d min" ].default_value, "squeeze factor d min sensor pos"],
                        [material.inputs[ "squeeze factor d max" ].default_value, "squeeze factor d max sensor pos"]]

        
        unit_scale = material.inputs["unit scale"].default_value
        dia1 = material.inputs["dia1"].default_value
        focus_sample_h = material.inputs["focus sample h"].default_value
        
        ray_h = ( unit_scale * dia1 * 0.5 ) / focus_sample_h
        lens_length = lens_data[1]


        for calc in calculations:

            if calc[0] == 0:
                continue

            ray_lens_p = vec3(-lens_length,ray_h,0.0)

            ray_p = vec3(-calc[0],0.0,0.0)
            
            ray_n = ray_lens_p - ray_p
            
            ray_n = vec3_normalize( ray_n )
            
            ray_p = ray_lens_p - ray_n
            
            rays = []
            trace_backwards = False
            isolate_lens = 0
            ray_p, ray_n, rays = lens_trace( ray_p, ray_n, trace_backwards, lens_data, isolate_lens )
            
            
            plane_normal = vec3(0.0,1.0,0.0)
            plane_point = vec3(0.0,0.0,0.0)        
            ray_p = rayPlaneIntersect( ray_p, ray_n, plane_normal, plane_point)


            focus_point = ray_p[0]
            
            property_name = calc[1]

            material.inputs[ property_name ].default_value = focus_point * 1000.0
            
        
        #AutoApplyLensData(self, context)
        

        return {'FINISHED'}
    
def get_custom_dof_object():
    
    material = get_main_material()
    node = material.node_tree.nodes["custom focus object"]
    socket = node.inputs[0]
    
    # Check if the socket's default_value has a driver
    # NodeSocketFloat typically has a 'default_value' if it's a value input
    if not socket.is_linked:
        try:
            fcurve = material.node_tree.animation_data.drivers.find(f'nodes["{node.name}"].inputs[{node.inputs.find(socket.name)}].default_value')
            if fcurve:
                #print("Driver found!")
                # Access driver properties
                driver = fcurve.driver
                #print("Driver type:", driver.type)
                #print("Driver expression:", driver.expression)
                # Access driver variables
                for var in driver.variables:
                    #print("Driver variable name:", var.name)
                    #print("Driver variable type:", var.type)
                    
                    target = var.targets[0]
                    #dof_object = target.id
                    return target.id
            else:
                #print("No driver found on this socket.")
                pass
        except AttributeError:
            #print("This socket does not support drivers.")
            pass
               
    return None
    
def get_dof_empty_object():
    
    material = get_main_material()
    node = material.node_tree.nodes["DOF world pos"]
    socket = node.inputs[0]
    
    # Check if the socket's default_value has a driver
    # NodeSocketFloat typically has a 'default_value' if it's a value input
    if not socket.is_linked:
        try:
            fcurve = material.node_tree.animation_data.drivers.find(f'nodes["{node.name}"].inputs[{node.inputs.find(socket.name)}].default_value')
            if fcurve:
                #print("Driver found!")
                # Access driver properties
                driver = fcurve.driver
                #print("Driver type:", driver.type)
                #print("Driver expression:", driver.expression)
                # Access driver variables
                for var in driver.variables:
                    #print("Driver variable name:", var.name)
                    #print("Driver variable type:", var.type)
                    
                    target = var.targets[0]
                    #dof_object = target.id
                    return target.id
            else:
                #print("No driver found on this socket.")
                pass
        except AttributeError:
            #print("This socket does not support drivers.")
            pass
               
    return None
    
def get_dof_object():
    
    if get_lens_camera_node().inputs["focus mode"].default_value == -1:
        return get_custom_dof_object()
    else:
        return get_dof_empty_object()



class SelectCameraFocusEmptyButton(bpy.types.Operator):
    bl_idname = "object.select_camera_focus_object_button"
    bl_label = ""
    bl_description = "Select Camera Focus Empty"
    #bl_icon = "FILE_FOLDER" #does not work...

    def execute(self, context):

        dof_object = get_dof_object()
        
        # select object
        if dof_object != None:
            for ob in bpy.context.selected_objects:
                ob.select_set(False)
            dof_object.select_set(True)
        
        return {'FINISHED'}


def get_focus_distance( from_blender_camera ):
    
    lens_node = get_lens_camera_node()
    
    focus_mode = lens_node.inputs["focus mode"].default_value
    
    focus_distance = 3.0
    
    if focus_mode == 1:
        
        focus_distance = lens_node.inputs["focus dist"].default_value
    
    # note we ignore manual sensor mode
    else:
    
        focus_object_attach = lens_node.inputs["focus object attached"].default_value
        dof_object = get_dof_object()
        
        world_position = dof_object.matrix_world.translation
        inv_matrix = LensSim_Camera.matrix_world.inverted()
        local_position = inv_matrix @ world_position
        
        #dof_object.parent = LensSim_DofEmptyParent
        
        focus_distance = -local_position[2]

    
    # add gap between lens mesh and camera
    if from_blender_camera:
        focus_distance = focus_distance - LensSim_LensMesh.location[2]
        
    return focus_distance


def focus_object_attach():
    
    main_material = get_main_material()
    material = LensSim_LensMaterial
    lens_node = get_lens_camera_node()
    
    focus_object_attach = lens_node.inputs["focus object attached"].default_value
    dof_object = get_dof_object()
    
    
    
    if dof_object == None or LensSim_DofEmptyParent == None:
        return
    
    if focus_object_attach:

        world_position = dof_object.matrix_world.translation
        inv_matrix = LensSim_Camera.matrix_world.inverted()
        local_position = inv_matrix @ world_position
        
        dof_object.parent = LensSim_DofEmptyParent
        
        dof_object.location[0] = 0.0
        dof_object.location[1] = 0.0
        dof_object.location[2] = get_focus_distance( True )

        dof_object.lock_rotation[0] = True
        dof_object.lock_rotation[1] = True
        dof_object.lock_rotation[2] = True
        dof_object.lock_location[0] = True
        dof_object.lock_location[1] = True
        dof_object.lock_scale[2] = True
        
        dof_object.scale[0] = 0.4
        dof_object.scale[1] = 0.4
        dof_object.scale[2] = 0.0

    else:
        
        world_position = dof_object.matrix_world.translation
        
        dof_object.parent = None
        
        dof_object.location[0] = world_position[0]
        dof_object.location[1] = world_position[1]
        dof_object.location[2] = world_position[2]

        dof_object.lock_rotation[0] = False
        dof_object.lock_rotation[1] = False
        dof_object.lock_rotation[2] = False
        dof_object.lock_location[0] = False
        dof_object.lock_location[1] = False
        dof_object.lock_scale[0] = False
        dof_object.lock_scale[1] = False
        dof_object.lock_scale[2] = False
        
        dof_object.scale[0] = 0.4
        dof_object.scale[1] = 0.4
        dof_object.scale[2] = 0.4

    
    '''
    LensSim_DofEmptyParent

    empty0_obj.parent = plane_obj
    empty1_obj.parent = empty0_obj

    empty1_obj.scale[0] = 0.4
    empty1_obj.scale[1] = 0.4
    empty1_obj.scale[2] = 0.0
            
    empty1_obj.lock_rotation[0] = True
    empty1_obj.lock_rotation[1] = True
    empty1_obj.lock_rotation[2] = True
    empty1_obj.lock_location[0] = True
    empty1_obj.lock_location[1] = True
    empty1_obj.lock_scale[2] = True
    '''
    
class OpenLensPath(bpy.types.Operator):
    bl_idname = "object.open_lens_path"
    bl_label = "Open Lens Folder"
    #bl_icon = "FILE_FOLDER" #does not work...

    def execute(self, context):

        open_file(  get_lenses_path() )
        
        return {'FINISHED'}

def remove_limit_scale_constraint(cam_obj):
    for constraint in cam_obj.constraints:
        if constraint.name == 'LensSimLimitScale':
            cam_obj.constraints.remove(constraint)

def add_limit_scale_constraint(cam_obj):
    
    get_constraint = None
    for constraint in cam_obj.constraints:
        if constraint.name == 'LensSimLimitScale':
            get_constraint = constraint
    
    constraint = get_constraint
    if constraint == None:
        # Add a 'Limit Scale' constraint to the camera object
        constraint = cam_obj.constraints.new(type='LIMIT_SCALE')

    # Set constraint values
    constraint.use_min_x = True
    constraint.use_min_y = True
    constraint.use_min_z = True
    constraint.use_max_x = True
    constraint.use_max_y = True
    constraint.use_max_z = True
    constraint.min_x = 1.0
    constraint.min_y = 1.0
    constraint.min_z = 1.0
    constraint.max_x = 1.0
    constraint.max_y = 1.0
    constraint.max_z = 1.0
    constraint.use_transform_limit = True
    constraint.owner_space = 'WORLD'
    constraint.name = 'LensSimLimitScale'

'''
# ??? CANT MAKE THE VIEWER NODE WORK
def geometry_node_hide_lens_mesh( object ):
    
    # Define the geometry node name and scale factor
    geo_node_name = "LensSim_HideLensMesh"
    geo_node_name = "yolo"
    scale_factor = (2.0, 2.0, 2.0)

    # Get the selected object
    #obj = bpy.context.active_object

    # Check if the object is a mesh
    if object and object.type == 'MESH':

        
        if object:

            # if nodetree exists
            node_tree = bpy.data.node_groups.get( geo_node_name )

            if node_tree:
                
                # Create a new Geometry Nodes modifier for the selected object
                modifier = object.modifiers.new(name=geo_node_name, type='NODES')
                modifier.node_group = node_tree
            
            # create new geometry node
            else:        
                
                return 
            
                
            
            
                object.select_set(True)
                bpy.ops.node.new_geometry_nodes_modifier()
                
                object.modifiers[0].name = geo_node_name
                
                node_tree = object.modifiers[0].node_group
                
                #node_tree.name = geo_node_name
                
                #node_tree = bpy.data.node_groups.new("yolo3", 'GeometryNodeTree')
                
                # Create a new node for input geometry
                #input_node = node_tree.nodes.new(type='NodeGroupInput')
                #input_node.location = (-300, 0)  # Position the input node

                # Create a new node for transforming (scaling)
                transform_node = node_tree.nodes.new(type='GeometryNodeTransform')
                transform_node.location = (0, 0)  # Position the transform node

                # Create a new node for output geometry
                #output_node = node_tree.nodes.new(type='NodeGroupOutput')
                #output_node.location = (300, 0)  # Position the output node

                #output_node.inputs.new('NodeSocketGeometry', "Geometry")
                
                # create viewer node
                viewer_node = node_tree.nodes.new(type="GeometryNodeViewer")
                viewer_node.location = (300, -200)  # Position the transform node
                viewer_node.data_type = "INT"
                #viewer_node.activate_viewer()


                # Clear all selections
                #for node in node_tree.nodes:
                #    node.select = False
                #viewer_node.select = True
                #node_tree.nodes.active = viewer_node
                #bpy.ops.node.activate_viewer()
                
                input_node = node_tree.nodes["Group Input"]
                output_node = node_tree.nodes["Group Output"]
                
                # Set the scaling factors
                # Note: The scaling values are set in the 'Translation' input (X, Y, Z)
                transform_node.inputs['Translation'].default_value = (0.0, 0.0, 0.0)  # No translation
                transform_node.inputs['Scale'].default_value = (2.0, 2.0, 2.0)  # Scale by 2.0 in all directions

                # Link the nodes
                links = node_tree.links
                links.new(input_node.outputs[0], transform_node.inputs['Geometry'])
                #links.new(transform_node.outputs['Geometry'], output_node.inputs[0])
                links.new(transform_node.outputs['Geometry'], viewer_node.inputs[0])
                

'''

def create_camera( self, context, camera ):
    
    disable_cameras = get_viewport_mode()
    
    convert_camera = False
    if camera != None:
        convert_camera = True
    
    layout = self.layout
    props = context.scene.my_addon_props
    
    scn = bpy.context.scene
    
    bpy.ops.object.select_all(action='DESELECT')
    
    clip_start = 0.0
    
    collection = None
    if convert_camera == False:
        # create new collection
        collection = bpy.data.collections.new("LensSimCamera")
        scn.collection.children.link(collection)
        
        collection.name = "LensSim_Camera"
    
        # create the first camera
        camera = bpy.data.cameras.new("Camera")
    
    # Get the 3D cursor's location
    cursor_location = bpy.context.scene.cursor.location

    # create the first camera object
    cam_obj = None
    cam_obj_focus_object = None
    cam_obj_focus_dist = 0.0
    cam_obj_fstop = 1.0
    
    if convert_camera == False:
        cam_obj = bpy.data.objects.new("Camera", camera)
        #cam_obj.name = "LensSimCamera"
        #scn.collection.objects.link(cam_obj)
        cam_obj.name = LensSim_CameraName
    
    else:
        cam_obj = bpy.data.objects[ camera.name ]
        
        clip_start = cam_obj.data.clip_start

        if clip_start < 0.11:
            clip_start = 0.0
        
        if cam_obj.data.dof.use_dof:
            cam_obj_focus_object = cam_obj.data.dof.focus_object
            cam_obj_focus_dist = cam_obj.data.dof.focus_distance
            cam_obj_fstop = cam_obj.data.dof.aperture_fstop
    
    # edit camera parameters
    if convert_camera == False:
        cam_obj.location = cursor_location
        cam_obj.rotation_euler = (math.radians(90), 0, 0.0)
    
    cam_obj.lock_scale[0] = True
    cam_obj.lock_scale[1] = True
    cam_obj.lock_scale[2] = True
    
    # set camera parameters
    camera_data = cam_obj.data
    
    camera_data.dof.focus_object = None
    
    camera_data.ortho_scale = 1.0
    camera_data.clip_start = 0.001
    camera_data.type = "ORTHO"

    camera_data.sensor_fit = "AUTO"
    camera_data.sensor_width = 36.0
    
    camera_data.dof.use_dof = True
    camera_data.dof.focus_distance = 0.01
    
    camera_data.shift_x = 0.0
    camera_data.shift_y = 0.0
    
    camera_data.dof.aperture_fstop = 100.0
    camera_data.dof.aperture_blades = 0
    camera_data.dof.aperture_rotation = 0.0
    camera_data.dof.aperture_ratio = 1.0

    #add_limit_scale_constraint(cam_obj)

    if convert_camera == False:
        collection.objects.link(cam_obj) # add camera to collection
    
    bpy.ops.mesh.primitive_plane_add(
        size=1.005,
        calc_uvs=True,
        enter_editmode=False,
        align='WORLD',
        location=(0,0,-0.01),
        rotation=(0, 0, 0),
        scale=(0, 0, 0)
    )
    
    # Get the plane object
    plane = bpy.context.view_layer.objects.active
    plane_obj = bpy.context.selected_objects[0]

    #collection.objects.link(cam_obj)
    if convert_camera == False:
        collection.objects.link(plane_obj) # add plane to collection


    #geometry_node_hide_lens_mesh(plane_obj)




    # set viewport visibility
    plane_object_data = bpy.data.objects[plane_obj.name]
    plane_object_data.display_type = "BOUNDS"
    plane_object_data.display_bounds_type = "CYLINDER"
    plane_object_data.display.show_shadows = False
    plane_object_data.visible_diffuse = False
    plane_object_data.visible_glossy = False
    plane_object_data.visible_transmission = False
    plane_object_data.visible_volume_scatter = False
    plane_object_data.visible_shadow = False

    #add_limit_scale_constraint(plane_obj)

    # set camera focus distance
    #camera_data.dof.focus_object = plane_obj


    empty0 = bpy.ops.object.empty_add(
        location=(0,0,0.0),
        rotation=(math.radians(180), 0, 0)
    )
    empty0_obj = bpy.context.selected_objects[0]
    
    add_limit_scale_constraint(empty0_obj)
    
    if convert_camera == False:
        collection.objects.link(empty0_obj) # add plane to collection
    
    for x in [0,1,2]:
        empty0_obj.lock_rotation[x] = True
        empty0_obj.lock_location[x] = True
        empty0_obj.lock_scale[x] = True
    
    
    empty1 = bpy.ops.object.empty_add(
        location=(0,0,3.0)
        #scale=(0.4, 0.4, 0)
    )
    empty1_obj = bpy.context.selected_objects[0]
    
    if convert_camera == False:
        collection.objects.link(empty1_obj) # add to collection
    
    empty1_obj.scale[0] = 0.4
    empty1_obj.scale[1] = 0.4
    empty1_obj.scale[2] = 0.0
    
    empty1_obj.lock_rotation[0] = True
    empty1_obj.lock_rotation[1] = True
    empty1_obj.lock_rotation[2] = True
    empty1_obj.lock_location[0] = True
    empty1_obj.lock_location[1] = True
    empty1_obj.lock_scale[2] = True
    

    #empty1_obj.empty_display_type = "SPHERE"
    
    # set parent
    plane_obj.parent = cam_obj
    empty0_obj.parent = plane_obj
    empty1_obj.parent = empty0_obj

    empty0_obj.empty_display_size = 0.0


    
    
    # remove unwanted collections from objects
    if convert_camera == False:
        objects = [ cam_obj, plane_obj, empty0_obj, empty1_obj ]
        for obj in objects:
            for col in obj.users_collection:
                if col != collection:
                    
                    col.objects.unlink( obj )
    
    # put objects in the existing camera collection
    else:
        objects = [ plane_obj, empty0_obj, empty1_obj ]

        # add collections that is part of the camera collection
        for object in objects:
            for cam_col in cam_obj.users_collection:
                add_collection = False
                for col in object.users_collection:
                    if col != cam_col:
                        add_collection = True
                if add_collection:
                    cam_col.objects.link( object )
        
        # remove collections that is not part of the camera collection
        for object in objects:
            
            for col in object.users_collection:
                remove_collection = True
                for cam_col in cam_obj.users_collection:
                    if col == cam_col:
                        remove_collection = False
                if remove_collection:
                    
                    # quick fix for error when col does not has object in it...
                    if col in object.users_collection:
                        col.objects.unlink( object )
                    
            '''
            for col in object.users_collection:
                remove_collection = True
                for cam_col in cam_obj.users_collection:
                    if col == cam_col:
                        remove_collection = False
                if remove_collection:
                    col.objects.unlink( object )
            '''
    
    # find material
    get_lens_material = None
    
    # it doesent take that long to create a new camera, just import a new one pga version controll etc
    for material in bpy.data.materials:
        if material.name.startswith( LensSim_LensMaterialName ):
            get_lens_material = material
    
    '''
    # get the new material
    for material in bpy.data.materials:
        if material.name.startswith( LensSim_LensMaterialName ):
            try:
                check_for_new_feature = material.node_tree.nodes["LensSim"].inputs["lens internal rotation"].default_value
                if material.node_tree.nodes["Version"].label == LensSim_Version:
                    lens_material = material
                    break
            except:
                continue
    '''
    
    lens_material = None
    
    # if material found, make a copy
    if get_lens_material != None:
        lens_material = get_lens_material.copy()
    
    # import from blend file
    else:
        
        ## FIX
        script_folder_path = get_script_folder_path()
        ## FIX
        blend_file_path = os.path.join( script_folder_path, os.path.join( LensSim_CameraFolder, LensSim_CameraFile ) )
        
        # Append the collection
        
        material_name = LensSim_LensMaterialName
        
        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
            if material_name in data_from.materials:
                data_to.materials = [material_name]

        # get the new material
        for material in bpy.data.materials:
            if material.name.startswith( LensSim_LensMaterialName ):
                lens_material = material
                break
            
                #try:
                #    check_for_new_feature = material.node_tree.nodes["LensSim"].inputs["lens internal rotation"].default_value
                #    if material.node_tree.nodes["Version"].label == LensSim_Version:
                #        lens_material = material
                #        break
                #except:
                #    continue
        
        
        #if material_name in bpy.data.materials:
            #lens_material = bpy.data.materials[material_name]
    
    
    # importing material will also add the blend scene, delete this scene
    scene_name = "LensSimAddonScene"
    # Check if the scene exists
    if scene_name in bpy.data.scenes:

        scene_to_delete = bpy.data.scenes[scene_name]

        # Ensure that the scene you want to delete is not the active one
        if bpy.context.scene != scene_to_delete:
            # Switch to another scene before deleting
            
            #bpy.context.window.scene = bpy.data.scenes[0] if len(bpy.data.scenes) > 1 else None
        
            # Remove the scene
            bpy.data.scenes.remove(scene_to_delete)
    
    
    
    # assign material
    if lens_material != None:
        plane_obj.data.materials.append( lens_material )
    
    # rename objects
    empty0_obj.name = "Rot_Fix"
    empty1_obj.name = LensSim_DofEmptyName
    plane_obj.name = "Lens"
    
    #if convert_camera == False:
        #collection.name = "LensSimCollection"
        
        #if lens_material != None:
            #cam_obj.name = "LensSim Camera"
    
    # disable selection etc
    plane_obj.hide_select = True
    
    empty0_obj.hide_select = True
    empty0_obj.hide_viewport = True
    empty0_obj.hide_render = True
    
    #
    # add DOF driver
    #
    
    # Access the driven property
    node = lens_material.node_tree.nodes["DOF world pos"]
    
    drivers = [ ["loc_x", "LOC_X", "WORLD_SPACE"],
                ["loc_y", "LOC_Y", "WORLD_SPACE"],
                ["loc_z", "LOC_Z", "WORLD_SPACE"] ]
      
    for x in range(3):
        
        socket = node.inputs[x]

        # Add a driver to the 'default_value' of the socket
        driver = socket.driver_add("default_value").driver

        # Clear existing variables if any
        #driver.variables.clear()

        # Iterate through all variables and remove them
        while driver.variables:
            driver.variables.remove(driver.variables[0])
        
        
        # Add a new variable to the driver
        var = driver.variables.new()
        var.name = drivers[x][0]
        var.type = 'TRANSFORMS'

        # Set up the target for the driver variable
        target = var.targets[0]
        target.id = empty1_obj
        target.transform_type = drivers[x][1]
        target.transform_space = drivers[x][2]

        # Set the driver expression to use the variable
        driver.expression = drivers[x][0]
    
    
    #
    # select camera update global parameters
    #
    
    # select camera
    empty0_obj.select_set(False)
    empty1_obj.select_set(False)
    plane_obj.select_set(False)
    cam_obj.select_set(True)

    
    # update active camera
    #global LensSim_CameraExists
    #global LensSim_Camera
    #global LensSim_LensMaterial
    
    #LensSim_CameraExists = True
    #LensSim_Camera = cam_obj
    #LensSim_LensMaterial = lens_material
    
    # makee new camera the current one
    is_LensSimCamera(cam_obj)
    
    # set ui to default
    ignore = []
    reset_camera_properties(self, context, ignore)
    
    # load default lens
    props.lenses_enum = LensSim_DefaultCamera
    on_lens_enum_change(self, context)
    
    
    
    #
    # restore old camera parameters
    #
    

    # fix dof parent issue
    main_material = get_main_material()
    main_material_tree = main_material.node_tree
    
    # turn it off on
    main_material_tree.nodes["LensSim"].inputs["focus object attached"].default_value = 0
    focus_empty_attach_update(self, context)
    focus_object_attach()
    main_material_tree.nodes["LensSim"].inputs["focus object attached"].default_value = 1
    focus_empty_attach_update(self, context)
    focus_object_attach()

    # reset distance
    dof_object = get_dof_empty_object()
    dof_object.location[2] = 3.0

    # fix lens mesh distance
    update_lens_mesh_distance()

    update_camera_scale()
    build_lens_mesh()
    
    # set clip start
    if clip_start > 0.1:
        lens_material.node_tree.nodes["LensSim"].inputs["clip start"].default_value = clip_start

    # set dof
    if cam_obj_focus_object != None:
        
        lens_material.node_tree.nodes["LensSim"].inputs["focus mode"].default_value = -1
        context.scene.my_addon_props.focus_object = cam_obj_focus_object
        focus_empty_visibility("-1") # hide dof empty
        
    elif cam_obj_focus_dist != 0.0:
        empty1_obj.location[2] = cam_obj_focus_dist

    if cam_obj_fstop > 1.0:
        lens_material.node_tree.nodes["LensSim"].inputs["f stop"].default_value = cam_obj_fstop

    # restore viewport mode
    if disable_cameras != None:
        lens_material.node_tree.nodes["LensSim"].inputs["viewport preview enable"].default_value = disable_cameras
        viewport_mode()

class ConvertCameraButton(bpy.types.Operator):
    bl_idname = "object.convert_camera_button"
    bl_label = "Convert to Lens Sim Camera"
    bl_description = "Convert selected camera to a Lens Sim camera.\nClip Start(if not set to default) and focus distance/object will be inherited when converted"
    
    def execute(self, context):
        
        camera = None
        
        selected_objects = bpy.context.selected_objects
        for obj in selected_objects:
            if obj.type == 'CAMERA':
                if not is_LensSimCamera(obj):
                    camera = obj
            break
        
        if camera != None:
            create_camera( self, context, camera )
        
        return {'FINISHED'}

class CreateCameraButton(bpy.types.Operator):
    bl_idname = "object.create_camera_button"
    bl_label = "Create Lens Sim Camera"
    bl_description = "Create a new Lens Sim camera"
    
    def execute(self, context):
        
        camera = None
        create_camera( self, context, camera )
        
        return {'FINISHED'}
        



         

class ImportLens(bpy.types.Operator):
    bl_idname = "object.import_lens"
    bl_label = "Import Lens"
        
    def execute(self, context):

        lenses_path = get_lenses_path()
        lens_node = get_lens_node()
        lensCTRL = get_lens_camera_node()
        
        selected_lens = context.scene.my_addon_props.lenses_enum
        
        main_material = get_main_material()

        
        old_f_number = lens_node.inputs["f number"].default_value


        # get lens parameters from file
        file_LensSim_LensParms = []

        for file in os.listdir(lenses_path):
            if file.endswith(".txt"):
                # Prints only text file present in My Folder
                
                if file == selected_lens:
                    
                    lens_file = open( os.path.join( lenses_path, file), 'r')
                    Lines = lens_file.readlines()
                    
                    for line in Lines:
                        
                        #print( line )
                        
                        content = line.split(" = ")            
                
                        if len(content) == 2:
                        
                            if content[0].endswith(" "):
                                content[0] = content[0][:-1]
                            
                            if content[1].endswith(" "):
                                content[1] = content[1][:-1]
                            if content[1].endswith("\n"):
                                content[1] = content[1][:-1]
                                
                            if content[1].startswith(" "):
                                content[1] = content[1][1:]
                            
                            if content[0] != "" and content[1] != "":
                                file_LensSim_LensParms.append( content )
        
        
        if len( file_LensSim_LensParms ) > 20:

            reset_lens_properties()

            #set parameters from file
            for content in file_LensSim_LensParms:
                
                parm = content[0]
                value = content[1]
                
                if content[0] == "link":
                    set_link_parm( content[1] )
                    continue
                if content[0] == "bokeh image":
                    bpy.context.scene.my_thumbnails = content[1]
                    continue
                
                node_parameter = lens_node.inputs.get( parm )
                
                if node_parameter == None:
                    print( "Could not find: " + parm )
                else:
                    type = lens_node.inputs.get( parm ).type
                    
                    #if not type == None:
                    if type == "INT":
                        lens_node.inputs.get( parm ).default_value = int( value )
                    if type == "VALUE":
                        lens_node.inputs.get( parm ).default_value = float( value )
                    if type == "BOOLEAN":
                        if value == "True":
                            lens_node.inputs.get( parm ).default_value = 1
                        else:
                            lens_node.inputs.get( parm ).default_value = 0
                        #lens_node.inputs.get( parm ).default_value = float( value )
            

            
            # Update UI
            '''
            auto_set_lens_parms_enabled = context.scene.lens_data_props.auto_set_lens_parms
            if auto_set_lens_parms_enabled:
                context.scene.lens_data_props.auto_set_lens_parms = False  
            mode = 0
            update_lens_property(self, context, mode)
            if auto_set_lens_parms_enabled:
                context.scene.lens_data_props.auto_set_lens_parms = True
            '''
            # build lens nodes
            build_lens_system()
            
            # update material lens name
            set_current_lens( selected_lens )

        # DELETEME ???
        sync_ui_parameters()

        build_lens_mesh()
        
        viewport_mode()

        # set f stop
        if lensCTRL.inputs["f stop"].default_value == old_f_number:
            lensCTRL.inputs["f stop"].default_value = lens_node.inputs["f number"].default_value
        lensCTRL.inputs["f stop"].default_value = max( lensCTRL.inputs["f stop"].default_value, lens_node.inputs["f number"].default_value )


        return {'FINISHED'}
        
        
        
        
        
        
        
        





def wrap_text(text, width):
    '''
    lines = []
    while len(text) > width:
        # Find the last space within the width limit
        wrap_pos = text.rfind(' ', 0, width)
        if wrap_pos == -1:
            wrap_pos = width
        lines.append(text[:wrap_pos])
        text = text[wrap_pos:].strip()
    lines.append(text)
    '''
    lines = []
    line = ""
    words = 0
    text_split = text.split(" ")
    for word in text_split:
        
        if word == "-n":
            lines.append(line)
            line = ""
            words = 0
            continue
        
        words += len(word)
        if words > width:
            lines.append(line)
            line = ""
            words = len(word)
        line = line + " " + word
    if len(line )> 0:
        lines.append(line)
    return lines

def draw_text_box(layout, long_text, icons ):
    # Wrap the text at 50 characters width
    
    region = bpy.context.region
    region_width = region.width  # Get the width of the region
    region_width = int( (region_width * .15) - 15 )
    wrapped_lines = wrap_text(long_text, region_width)
    box = layout.box()
    box.scale_y = 0.5
    for line in wrapped_lines:
        box.label(text=line)

    if icons != None:
        for content in icons:
            box.label(icon=content[0],text=content[1] )






class LensDataMainPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_LensDataMainPanel" # sub panel id
    bl_label = "Lens Data"
    #bl_parent_id = "VIEW3D_PT_LensSim_MainPanel" # parent of
    bl_parent_id = "VIEW3D_PT_LensSim_AdvancedSettingsPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}


    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True
    
    
    def draw_header_preset(self, context):
        layout = self.layout
        props = context.scene.my_addon_props
        
        #layout.operator("object.reset_camera_ctrl_button", text="", icon="TRASH")
        layout.operator("object.reset_lens_data_props_button", text="", icon="TRASH")
      
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        #lens_props = scene.LensDataProperties

        #layout.operator("object.reset_lens_data_props_button", text="Reset Data", icon="TRASH")

class SaveLensPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_SaveLensPanel" # sub panel id
    bl_label = "Save Lens"
    bl_parent_id = "VIEW3D_PT_LensSim_LensDataMainPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True
    
    def draw(self, context):
        
        layout = self.layout
        props = context.scene.my_addon_props
        
        layout.prop(props, "new_lens_name")
        layout.operator("object.open_lens_path", icon="FILE_FOLDER")
        split = layout.split()
        split.operator("object.save_current_lens", text="Override Current", icon="FILE_TICK")
        split.operator("object.export_lens", icon="FILE_TICK")



class LensDataCommonPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_LensDataCommonPanel" # sub panel id
    bl_label = "Common"
    bl_parent_id = "VIEW3D_PT_LensSim_LensDataMainPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True

    def draw(self, context):
        
        layout = self.layout
        scene = context.scene
        props = context.scene.my_addon_props
        
        material = get_lens_node()
        
        #layout.prop(props, "lens_link" )
 
        #test.tooltip = "This is the size of the default sensor."
        #layout.prop(material.inputs["default camera dof ref"], "default_value", text="default camera dof ref")
        #bpy.data.materials["LensSimMaterial"].node_tree.nodes["Lens"].inputs[32].default_value        
    
        
        layout.prop(material.inputs["f number"], "default_value", text="F Number")
        
        layout.separator()
        
        split = layout.split(factor=0.6)
        split.prop(material.inputs["focus sample h"], "default_value", text="Focus Sample")
        row = split.row(align=True)
        row.prop(material.inputs["focus sample d min"], "default_value", text="From (Optional)")
        row.prop(props, "help_focus_sample_h", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        split = layout.split(factor=0.6)
        split.prop(material.inputs["focus sample h to max"], "default_value", text="Focus Sample To (Optional)")
        row = split.row(align=True)
        row.prop(material.inputs["focus sample d max"], "default_value", text="To (Optional)")
        row.prop(props, "help_focus_sample_h", icon="BLANK1", emboss=True, icon_only=True )
        #expand=False,  emboss=True,
        if context.scene.my_addon_props.help_focus_sample_h:
            text  = 'Used to calculate the focus point, adjust until subject is focused at the corresponding focus distance. '
            text += 'Sometimes the Focus Sample point is not optimal at all distances, for this you can lerp between two Focus Sample points, '
            text += 'set a From and To distance to lerp between the two Focus Sample values.'
            draw_text_box(layout, text, None )
        layout.separator()
        
        
        #layout.prop(material.inputs["squeeze factor"], "default_value", text="Squeeze Factor")   
        
        

        layout.prop(material.inputs["squeeze factor"], "default_value", text="Squeeze Factor")
        split01 = layout.split(factor=0.5)
        split01.prop(material.inputs["squeeze factor d min sensor pos"], "default_value", text="From Sensor Pos (Optional)")
        split02 = split01.split(factor=0.59)
        split02.prop(material.inputs["squeeze factor d min"], "default_value", text="")
        split02.operator("object.calc_focus_pos", text="Calculate" )
        
        layout.prop(material.inputs["squeeze factor to max"], "default_value", text="Squeeze Factor To (Optional)")
        split01 = layout.split(factor=0.5)
        split01.prop(material.inputs["squeeze factor d max sensor pos"], "default_value", text="To Sensor Pos (Optional)")
        split02 = split01.split(factor=0.59)
        split02.prop(material.inputs["squeeze factor d max"], "default_value", text="")
        split02.operator("object.calc_focus_pos", text="Calculate" )

        
        layout.separator()
        
        
        
        
        
        
        #layout.prop(material.inputs["chromatic aberration type"], "default_value", text="Chromatic Aberration Type")   
        layout.prop(material.inputs["chromatic aberration"], "default_value", text="Chromatic Aberration Multiplier") 
        
        layout.separator()
        
        split = layout.split(factor=LensSim_CalcButtonFactor)
        #split.prop(lens_props, f"image_scale_ref" )
        split.prop(material.inputs["image scale ref"], "default_value", text="Image Scale Ref")
        
        row = split.row(align=True)
        image_scale_ref = material.inputs["image scale ref"].default_value
        if image_scale_ref == 0.0:
            row.alert = True
        row.operator("object.calc_image_scale_ref", text="Calculate" )
        row.prop(props, "help_image_scale_ref", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        #expand=False,  emboss=True,
        if context.scene.my_addon_props.help_image_scale_ref:
            text  = 'A reference value for the lens image scale, used to calculate sensor Focal Length and the Disable Lens mode.'
            draw_text_box(layout, text, None )
        #layout.separator()
        
        
        
        row = layout.row(align=True)
        row.prop(material.inputs["default sensor size"], "default_value", text="Sensor Best Fit Size")
        
        row.operator("object.sensor_best_fit_size_subtract", icon="REMOVE" )
        row.operator("object.sensor_best_fit_size_add", icon="ADD")
        
        row.prop(props, "help_sensor_best_fit_size", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        #expand=False,  emboss=True,
        if context.scene.my_addon_props.help_sensor_best_fit_size:
            text  = 'Largest usable sensor scale with at a aspect ratio of 1.777, f-stop at 50.0 and focus distance at 500m.'
            draw_text_box(layout, text, None )
        
        #layout.prop(material.inputs["focusing screen scale"], "default_value", text="Focusing Screen Scale")

        #layout.prop(material.inputs["schematic size"], "default_value", text="schematic size")
        
        layout.separator()
        
        layout.prop(material.inputs["limit min focus dist"], "default_value", text="Clamp Min Focus Dist")
        layout.prop(material.inputs["limit max focus dist"], "default_value", text="Clamp Max Focus Dist")

        row = layout.row(align=True)
        row.prop(material.inputs["limit last lens diameter"], "default_value", text="Clamp Last Lens Diameter")
        row.prop(props, "help_limit_last_lens_diameter", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        #expand=False,  emboss=True,
        if context.scene.my_addon_props.help_limit_last_lens_diameter:
            text  = 'Clamps the last lens diameter when rendering, this will not affect lens schematics.'
            draw_text_box(layout, text, None )

        layout.separator()
        
        layout.prop(props, "lens_link", text= "Web Link" )


class LensDataRayGuidingPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_LensDataRayGuidingPanel" # sub panel id
    bl_label = "Ray Guiding"
    bl_parent_id = "VIEW3D_PT_LensSim_LensDataMainPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True
    
    '''
    def draw_header_preset(self, context):
        
        layout = self.layout
        props = context.scene.my_addon_props
        material = get_lens_node()
    
        if material.inputs["f s pos start"].default_value == 0.0 or material.inputs["f s pos end"].default_value == 0.0:
            #split = layout.split( factor=LensSim_CalcButtonFactor )
            layout.label(text="NB! Sensor Focus Pos not calculated!")
            #split.operator("object.calc_focus_pos", text="Calculate" )
    '''
    
    def draw(self, context):
        
        layout = self.layout
        scene = context.scene
        props = context.scene.my_addon_props
        
        lens_ctrl = get_lens_camera_node()
        if lens_ctrl == None:
            return
        
        material = get_lens_node()

        
        #layout.prop(lens_props, f"exposure" )
        #layout.prop(lens_props, f"exposure_max_f" )
        #layout.prop(lens_props, f"min_ray_guide_factor" )

        start_m = str( round_float( material.inputs["f s pos start m"].default_value ) ) + "m"
        end_m = str( round_float( material.inputs["f s pos end m"].default_value ) ) + "m"

        sensor_calibrated = True
        if material.inputs["f s pos start"].default_value == 0.0 or material.inputs["f s pos end"].default_value == 0.0:
            sensor_calibrated = False
            
        box = layout
        split01 = box.split(factor=0.55)
        split01.prop(material.inputs["f s pos start"], "default_value", text="Sensor Pos Near")
        split01.prop(material.inputs["f s pos start m"], "default_value", text="")
        split02 = split01.split()
        if not sensor_calibrated:
            split02.alert = True
        row = split02.row(align=True)
        row.operator("object.calc_focus_pos", text="Calculate" )
        row.prop(props, "help_sensor_focus_pos", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        split01 = box.split(factor=0.55)
        split01.prop(material.inputs["f s pos end"], "default_value", text="Sensor Pos Far")
        split01.prop(material.inputs["f s pos end m"], "default_value", text="")
        split02 = split01.split()
        if not sensor_calibrated:
            split02.alert = True
        row = split02.row(align=True)
        row.operator("object.calc_focus_pos", text="Calculate" )
        row.prop(props, "help_sensor_focus_pos", icon="BLANK1", emboss=True, icon_only=True )
        
        layout.separator()

        if context.scene.my_addon_props.help_sensor_focus_pos:
            text  = 'The Ray Guiding system is using two focus points as reference distances, Near and Far. The Far Pos should be at near infinity (usually 500.0m), the Near Pos should '
            text += 'be at a close distance within the lens working range (usually 1.0 m or closer). -n -n Note; -n -If the Near Pos is too close or too far it could alter the '
            text += 'quiality of the ray guiding. For example; trying to set the Near Pos on a 1000mm lens to 0.1m is not going to work, a tele lens is not suppose to work that '
            text += 'close. You might have to experiment with different distances for the optimal distance. -n -n '
            text += '-When adjusting parameters below, set the focus distance to the Near value and callibrate all parameters for that distance. Then do the same with the Far '
            text += 'distance, and if necessary the < Near distance. -n -n '
            text += '-Its important to check the whole Focus and and F-Stop range to verify the calibration. If calibrated correctly the results should be stable within the '
            text += 'working range of the lens. '
            draw_text_box(layout, text, None )

        #layout.enabled = sensor_calibrated

        #if material.inputs["f s pos start"].default_value == 0.0 or material.inputs["f s pos end"].default_value == 0.0:

            #split = layout.split( factor=LensSim_CalcButtonFactor )
            #split.label(text="NB! Sensor Focus Pos not calculated!")
            #split.operator("object.calc_focus_pos", text="Calculate" )
            #layout.label(text="NB! Calculate Focus Pos before continuing.")
            #layout.separator()
            
        #layout.prop(material.inputs["exposure"], "default_value", text="exposure")
        #layout.prop(material.inputs["exposure max f"], "default_value", text="exposure max f")
        row = layout.row(align=True)
        row.prop(lens_ctrl.inputs["visualize ray hit"], "default_value", text="Visualize Ray Hit", toggle=True )
        icon_id = "COLORSET_13_VEC"
        if lens_ctrl.inputs["visualize ray hit color"].default_value == True:
            icon_id = "COLORSET_01_VEC"
        row.prop(lens_ctrl.inputs["visualize ray hit color"], "default_value", text="", toggle=True, icon=icon_id, emboss=True )
        row.prop(props, "help_visualize_ray_hit", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_visualize_ray_hit:
            text  = 'Shows an exaggerated view whether or not rays gets occluded by the lens. '
            text += 'Calibrated with the AgX View Transform. -n '
            text += 'Red = occluded, Black = not occluded -n '
            draw_text_box(layout, text, [["COLORSET_13_VEC", "Disable color exaggeration"]] )

        #layout.prop(material.inputs["ray spread"], "default_value", text="Ray Spread")
        #layout.prop(material.inputs["ray spread 500m"], "default_value", text="Ray Spread 500m (Optional)")
        #layout.label(text="F-Stop 1.0, focus dist " + start_m + ":")
        split = layout.row()
        split.prop(material.inputs["ray spread"], "default_value", text="Ray Spread " + start_m)
        split.prop(material.inputs["ray spread 500m"], "default_value", text= end_m + " (Optional)")
        row = split.row(align=True)
        row.prop(material.inputs["ray spread < 1m"], "default_value", text="< " + start_m + " (Optional)")
        row.prop(props, "help_ray_spread", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_ray_spread:
            text  = 'Narrows the rays. Adjust untill rays in the center of the image is not occluded, the center of the image '
            text += 'should not be darkened. This would result in a natural vignetting towards the edges of the image. -n -n Note; Only the center point should not be occluded, setting the value too low will result '
            text += 'in stopping down the lens. F-Stop should be set to 1.0 while adjusting this value.'
            draw_text_box(layout, text, None )


        #layout.prop(material.inputs["ray edge angle"], "default_value", text="Ray Edge Angle")
        #layout.prop(material.inputs["ray edge angle 500m"], "default_value", text="Ray Edge Angle 500m (optional)")  
        split = layout.row()
        split.prop(material.inputs["ray edge angle"], "default_value", text="Ray Edge Angle " + start_m)
        split.prop(material.inputs["ray edge angle 500m"], "default_value", text= end_m + " (Optional)")
        row = split.row(align=True)
        row.prop(material.inputs["ray edge angle < 1m"], "default_value", text="< " + start_m + " (Optional)")
        row.prop(props, "help_ray_edge_angle", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_ray_edge_angle:
            text  = 'Angles rays towoards the side of the lens, counteracts the Ray Spread value. Adjust until the whole image is '
            text += 'covered. -n -n Note; Setting this value too low or too high could alter the bokeh shape, pay atention so that the bokeh shape is at '
            text += 'its optimal shape. F-Stop should be set to 1.0 while adjusting this value.'
            draw_text_box(layout, text, None )


        layout.separator()
        #layout.label(text="F-Stop 50.0, focus dist " + start_m + ":")
        #(data, property, text, text_ctxt, translate, icon, placeholder, expand, slider, toggle, icon_only, event, full_event, emboss, index, icon_value, invert_checkbox)
        split = layout.row()
        split.prop(material.inputs["ray guiding spread"], "default_value", text="Guide Spread " + start_m)
        split.prop(material.inputs["ray guiding focus shift 500m"], "default_value", text=end_m)
        row = split.row(align=True)
        row.prop(material.inputs["ray guiding focus shift < 1m"], "default_value", text="< " + start_m + " (Optional)")
        row.prop(props, "help_guide_spread", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

        if context.scene.my_addon_props.help_guide_spread:
            text  = 'Guides the rays towards the aperture opening. -n '
            text += 'Set the F-stop to 50.0, adjust this value until the edges of the image is at its clearest (not occluded), a donut shape will most likely emerge, '
            text += 'the donut shape is addressed in the next step.'
            draw_text_box(layout, text, None )
        

        row = layout.row(align=True)
        row.prop(material.inputs["ray guiding guide coverage"], "default_value", text="Guide Ramp Coverage " + start_m)
        row.prop(props, "help_guide_coverage", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

        if context.scene.my_addon_props.help_guide_coverage:
            text  = 'Sets the area where we can fine tune rays to be guided towards the aperture opening. -n '
            text += 'Set the F-stop to 50.0, Adjust until the blak area reaches the edge of the image where the edge is the clearest (not occluded), this will '
            text += 'result in a nearly black image apart from the edges.'
            draw_text_box(layout, text, None )
        
        split = layout.split()
        split.prop(material.inputs["ray guiding guide rampv5"], "default_value", text="")
        split.prop(material.inputs["ray guiding guide rampv4"], "default_value", text="")
        split.prop(material.inputs["ray guiding guide rampv3"], "default_value", text="")
        split.prop(material.inputs["ray guiding guide rampv2"], "default_value", text="")
        #split.prop(material.inputs["ray guiding guide rampv1"], "default_value", text="")
        row = split.row(align=True)
        row.prop(material.inputs["ray guiding guide rampv1"], "default_value", text="")
        row.prop(props, "help_guide_coverage_values", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_guide_coverage_values:
            text  = 'Angles rays towoards the aperture opening within the Guide Ramp Coverage. -n '
            text += 'Set the F-stop to 50.0, adjust each value to minimize the ray occlusion (usually a value between 8.0-15.0). -n -n '
            text += 'Note; This is not a perfect system, rays might still be occluded after setting the optimal values, sometimes '
            text += 'just minimizing the occlusion is the best thing you can do. '
            draw_text_box(layout, text, None )
        
        #layout.prop(material.inputs["ray guiding spread"], "default_value", text="Spread")


        

        '''
        layout.separator()
        
        #custom_word = context.scene.my_addon_props.new_lens_name
        
        
        #layout.prop(material.inputs["ray spread"], "default_value", text="Ray Spread")
        #layout.prop(material.inputs["ray edge angle"], "default_value", text="Ray Edge Angle")   
        
        row = layout.row(align=True)
        row.prop(material.inputs["ray spread"], "default_value", text="Ray Spread")
        row.prop(lens_props, "help_ray_spread", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_ray_spread:
            text  = 'Controls the incoming light cone. Adjust this value until the '
            text += 'center of the image no longer gets darkened. Setting this value too low will result in '
            text += 'a loss of incoming light data. Setting it too high will result in a darkened image with many '
            text += 'rays hitting the lens body.'
            draw_text_box(layout, text)
        
        row = layout.row(align=True)
        row.prop(material.inputs["ray edge angle"], "default_value", text="Ray Edge Angle")
        row.prop(lens_props, "help_ray_edge_angle", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

        if context.scene.my_addon_props.help_ray_edge_angle:
            text  = 'Shifts the incoming light cone angle of the outer rays. This will counteract issues with "Ray Spread" '
            text += 'and allow more light to hit the edges of the image. Adjust until the image no longer gets '
            text += 'brightened. Also, check the bokeh size; adjust this value until the bokeh is at its fullest at the '
            text += 'edges of the image.'
            draw_text_box(layout, text)

        layout.separator()

        #layout.label(text="Adjust Ray Guiding:")
        #layout.prop(material.inputs["min ray guide factor"], "default_value", text="Min Ray Guide Factor")
        row = layout.row(align=True)
        row.prop(material.inputs["f p f4 1m"], "default_value", text="f4 1m")
        row.prop(lens_props, "help_ray_guiding", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        row = layout.row(align=True)
        row.prop(material.inputs["f p f32 1m"], "default_value", text="f32 1m")
        row.prop(lens_props, "help_ray_guiding", icon="BLANK1", emboss=True, icon_only=True )
        row = layout.row(align=True)
        row.prop(material.inputs["f p shift 500m"], "default_value", text="f32 500m")
        row.prop(lens_props, "help_ray_guiding", icon="BLANK1", emboss=True, icon_only=True )
        
        if context.scene.my_addon_props.help_ray_guiding:
            text  = 'Steers the rays towards the aperture opening. -n -n OBS! Make sure you calculate the Sensor Focus Pos under before starting. '
            text += '-n -n Start with "f32 1m": Set the camera\'s F-Stop to 32 and the focus distance '
            text += 'to 1m. Adjust this value until you find the sweet spot where the edge of the image is the sharpest and the '
            text += 'overall image has consistent brightness. -n -n Do the same with "f4 1m" (F-Stop 4), make sure that this value is not higher '
            text += 'than the "f32 1m" value, that can result in issues. -n -n For "f32 500m", set the F-Stop to 32 and the focus distance to 500m, then make the same adjustments. '
            text += ' -n -n You might need to go back and forth between these parameters until you can adjust the aperture and focus distance freely '
            text += 'without seeing any issues. '
            draw_text_box(layout, text)
        '''



class LensSurfacesPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_LensSurfacesPanel" # sub panel id
    bl_label = "Surfaces"
    bl_parent_id = "VIEW3D_PT_LensSim_LensDataMainPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.my_addon_props
        
        material = get_lens_node()
        
        #box = layout.box()
        
        #layout.prop(lens_props, f"unit_scale" )
        
        #layout.operator("object.build_lens_button", icon="MOD_BUILD")
        
        row = layout.row(align=True)
        row.operator("object.build_lens_button", icon="MOD_BUILD")
        row.prop(props, "help_build_lens_graph", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        #expand=False,  emboss=True,
        
        if context.scene.my_addon_props.help_build_lens_graph:
            text  = 'When adding a lens element or changing the index of the aperture/rack focus we need to rebuild the material node graph.'
            draw_text_box(layout, text, None )

        layout.separator()
        
        row = layout.row(align=True)
        row.prop(material.inputs["unit scale"], "default_value", text="Unit Scale")
        row.prop(props, "help_unit_scale", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        #expand=False,  emboss=True,
            
        if context.scene.my_addon_props.help_unit_scale:
            text  = 'All metric values will be multiplied with this value.'
            draw_text_box(layout, text, None )
                
        layout.separator()
        
        #row = layout.row()
        #row.prop(lens_props, f"aperture_idx" )
        #row.prop(lens_props, f"aperture_r", text="r" )
        #row.prop(lens_props, f"aperture_d", text="d" )
        
        #layout.prop(lens_props, f"rack_focus_idx" )
        
        row = layout.row()
        row.prop(material.inputs["aperture idx"], "default_value", text="Aperture Idx")
        row.prop(material.inputs["aperture r"], "default_value", text="r")
        row2 = row.row(align=True)
        row2.prop(material.inputs["aperture d"], "default_value", text="d")
        row2.prop(props, "help_aperture", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        #expand=False,  emboss=True,
            
        if context.scene.my_addon_props.help_aperture:
            text  = 'Aperture Idx; The aperture is positioned afther this lens number. When 0, aperture is disabled. -n '
            text += 'Radius(r) is the opening radius when F-Stop is set to the lens F Number. -n Distance(d) is the '
            text += 'distance from the lens.'
            draw_text_box(layout, text, None )
        
        row = layout.row(align=True)
        row.prop(material.inputs["rack focus idx"], "default_value", text="Rack Focus Idx")
        row.prop(props, "help_rack_focus_index", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        #expand=False,  emboss=True,
            
        if context.scene.my_addon_props.help_rack_focus_index:
            text  = 'Index of the lens being shifted when racking the focus, used for anamorphic lenses. '
            draw_text_box(layout, text, None )
        
        
        layout.separator()
        split = layout.split(factor=0.65)
        row = split.row(align=True)
        row.operator("object.add_anamorphic_button", text="Add 2x Anamorphic Adapter", icon="ADD")
        row.operator("object.remove_anamorphic_button", text="", icon="TRASH")
        split.prop(props, "anamorphoc_adapter_scale_mult", text="Scale" )

        
        layout.separator()
        
        #               name            label
        attributes = [  ["r",           "r"],
                        ["d",           "d"],
                        ["dia",       "dia"],
                        ["t",           "type"],
                        ["ior",         "ior"],
                        ["V",           "V"]     ]
        
        attributes.insert(0,["",""])
        
        
        if context.scene.my_addon_props.help_surfaces:
            row = layout.row(align=True)
            
            #if context.scene.my_addon_props.help_surfaces:
            text  = 'r:        Radius -n '
            text += 'd:       Distance -n '
            text += 'dia:    Diameter -n '
            text += 'type:  0=Spherical, 1=Cylindrixal x-axis, 2=Cylindrixal y-axis -n '
            text += 'ior:     Index Of Refraction -n '
            text += 'V:       Abbe Number '
            text += ' -n -n '
            text += 'We describe each lens surface from the outer lens to the inner lens. '
            text += 'Each lens surface is described with two radiuses, two distances and two diameter values. The first distance value describes the '
            text += 'thickness of the lens, the second distance describes the distance to the next lens. '
            text += 'If two lenses is fused together in a lens group the distance between the lenses is set to 0.0. '
            text += 'The diameter describes the height cutoff of the lens surfaces. '
            
            draw_text_box(row, text, None )
            
            row.prop(props, "help_surfaces", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
        
        
        row = layout.row()
        cols = [row.column() for i in range(len(attributes))]
        
        
        if not context.scene.my_addon_props.help_surfaces:
            
            for i in range(len(attributes)):
                r = cols[i].row()
                
                if i != len(attributes)-1:
                    r.alignment = 'CENTER'
                    r.label(text=attributes[i][1])
                else:
                    row01 = r.row()
                    row01.alignment = 'CENTER'
                    row01.label(text="")

                    row02 = r.row()
                    row02.alignment = 'CENTER'
                    row02.label(text=attributes[i][1])
                    
                    row03 = r.row()
                    row03.alignment = 'RIGHT'
                    row03.prop(props, "help_surfaces", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )

        else:
            
            for i in range(len(attributes)):
                r = cols[i].row()
                r.alignment = 'CENTER'
                r.label(text=attributes[i][1])
                    
        
        cols[0].alignment = 'RIGHT'

        for i in range(1, LensSim_MaxLenses*2 + 1):
            
            cols[0].label(text=str(i))
            cols[0].alignment = 'RIGHT'
            
            #cols[1].prop(lens_props, f'{attributes[1][0]}{i}',text="" )
            #cols[2].prop(lens_props, f'{attributes[2][0]}{i}',text="" )
            #cols[3].prop(lens_props, f'{attributes[3][0]}{i}',text="" )
            
            cols[1].prop(material.inputs[f'{attributes[1][0]}{i}'], "default_value",text="" )
            cols[2].prop(material.inputs[f'{attributes[2][0]}{i}'], "default_value",text="" )
            cols[3].prop(material.inputs[f'{attributes[3][0]}{i}'], "default_value",text="" )

            if i < LensSim_MaxLenses+1:
                #cols[4].prop(lens_props, f'{attributes[4][0]}{i}',text="" )
                #cols[5].prop(lens_props, f'{attributes[5][0]}{i}',text="" )
                #cols[6].prop(lens_props, f'{attributes[6][0]}{i}',text="" )
                cols[4].prop(material.inputs[f'{attributes[4][0]}{i}'], "default_value",text="" )
                cols[5].prop(material.inputs[f'{attributes[5][0]}{i}'], "default_value",text="" )
                cols[6].prop(material.inputs[f'{attributes[6][0]}{i}'], "default_value",text="" )
        
        

class ApertureShapePanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_ApertureShapePanel" # sub panel id
    bl_label = "Aperture Shape"
    bl_parent_id = "VIEW3D_PT_LensSim_LensDataMainPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        #lens_props = scene.lens_data_props
        
        material = get_lens_node()
        main_material = get_main_material()
                
        #layout.separator()
        #layout.prop(material.inputs["aperture ray guiding"], "default_value", text="Ray Guiding")
        
        #layout.prop(props, "bokeh_enum")
        
        #row = layout.box()
        
        aperture_enable = material.inputs[f'aperture idx'].default_value
        
        aperture_enable_image = material.inputs[f'aperture use image'].default_value
        
        if aperture_enable > 0:
        
            layout.prop(material.inputs[f'aperture use image'], "default_value", text="Use Image", toggle=True, icon="IMAGE_DATA" )
            #row.scale_y = 0.4
        
            if aperture_enable_image:
                row = layout.split()
                #row.prop(material.inputs[f'aperture use image'], "default_value", text="" )
                row.template_icon_view(context.scene, "my_thumbnails", show_labels=True, scale=4.0)
                
                #layout.prop(material.inputs[f'aperture use image'], "default_value", text="Use Image", toggle=True )

                # color space
                #image_texture = main_material.node_tree.nodes["BokehImage"].image
                #layout.prop(image_texture.colorspace_settings, "name", text="Color Space" )
                
                #bpy.data.images["shape.001.png"].colorspace_settings.name
                #row.scale_y = 1.0
                layout.prop(material.inputs[f'aperture rotation'], "default_value", text="Rotation" )
                
                #(data, property, text, text_ctxt, translate, icon, placeholder, expand, slider, toggle, icon_only, event, full_event, emboss, index, icon_value, invert_checkbox)
                
                # Just a way to access which one is selected
                #row = layout.row()
                #row.label(text="You selected: " + bpy.context.scene.my_thumbnails)
            
        else:
            
            layout.label(text="Aperture not enabled, check Aperture Idx")

class RackFocusLUTPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_LensSim_RackFocusLUTPanel" # sub panel id
    bl_label = "Rack Focus LUT"
    bl_parent_id = "VIEW3D_PT_LensSim_LensDataMainPanel" # parent of
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lens Sim"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not LensSim_CameraExists:
            return False
        #return context.scene.my_addon_props.show_advanced_options
        return True
    

    def draw(self, context):
        #layout = self.layout
        scene = context.scene
        #lens_props = scene.lens_data_props
        
        
        
        #box = layout.box()
        
        #layout.prop(lens_props, f"unit_scale" )
        
        #layout.separator()
        
        layout = self.layout
        props = context.scene.my_addon_props
        
        material = get_lens_node()
        
        
        
        if material.inputs[f'rack focus idx'].default_value == 0:
            layout.label(text="Rack focus not enabled, check Rack Focus Idx")
        else:

            #layout.prop(material.inputs["aperture ray guiding"], "default_value", text="ray guiding")
            
            #layout.operator("object.build_lens_button")
            #layout.operator("object.calculate_rack_focus_lut", text="Calculate")
            
            row = layout.row(align=True)
            row.operator("object.calculate_rack_focus_lut", text="     Calculate")
            row.prop(props, "help_rack_focus_LUT", icon=LensSim_QuestionIcon, emboss=True, icon_only=True )
            #expand=False,  emboss=True,
                
            if context.scene.my_addon_props.help_rack_focus_LUT:
                text  = 'The Rack Focus shift is calibrated to the corresponding focus distance, the distances will be interpolated linearly. -n -n '
                text += 'Note; Make sure the Focus Sample (Common panel) is correctly adjusted to all distances in the lenses working range before calculating. '
                #text += 'distance from the lens.'
                draw_text_box(layout, text, None )
            
            

            for i in range(1, LensSim_RackFocusLUTSize + 1):
                
                split = layout.split(factor=0.3)
                #row.prop(lens_props, f'rack_focus_m_lut{i}')
                #row.prop(lens_props, f'rack_focus_p_lut{i}')
                split.prop(material.inputs[f'rack focus m lut{i}'], "default_value", text="" )
                split.prop(material.inputs[f'rack focus p lut{i}'], "default_value", text="Rack Focus" )
                
                
                #cols[1].prop(lens_props, f'{attributes[1][0]}{i}',text="" )
                #cols[2].prop(lens_props, f'{attributes[2][0]}{i}',text="" )
                #cols[3].prop(lens_props, f'{attributes[3][0]}{i}',text="" )


    
    
def lookup_table(table, x):
    """
    Linearly interpolates between values in a lookup table.
    """
    
    
    
    # Sort the lookup table by keys (x-values)
    table = sorted(table, key=lambda pair: pair[0])
    #print(table)
    # Handle edge cases: if x is out of bounds of the table
    if x <= table[0][0]:
        return table[0][1]
    elif x >= table[-1][0]:
        return table[-1][1]

    # Find two table points (x1, y1) and (x2, y2) such that x1 <= x <= x2
    for i in range(len(table) - 1):
        x1, y1 = table[i]
        x2, y2 = table[i + 1]
        
        if x1 <= x <= x2:
            # Linear interpolation formula: y = y1 + (x - x1) * (y2 - y1) / (x2 - x1)
            return y1 + (x - x1) * (y2 - y1) / (x2 - x1)
   
def update_lens_mesh_distance():
    
    lensCTR = get_lens_camera_node()
    
    lens_mesh_distance = lensCTR.inputs["lens mesh distance"].default_value
    
    LensSim_Camera.data.dof.focus_distance = lensCTR.inputs["lens mesh distance"].default_value
    
    table = [(0.01, 100), (0.015, 65), (0.02, 50), (0.03, 30), (0.04, 25), (0.05, 20), (0.06, 16), (0.07, 14), (0.08, 12.3), (0.09, 11), (0.1, 10)]
    
    LensSim_Camera.data.dof.aperture_fstop = lookup_table(table, lens_mesh_distance)
    
    LensSim_LensMesh.location[2] = -lens_mesh_distance
   
def update_camera_scale():
    
    camera = LensSim_Camera
    if not camera:
        return
    
    lens_object = None
    
    # Check each child object of the camera
    for child in camera.children:
        # Check if the child is a mesh object
        if child.type == 'MESH':
            for mat in child.data.materials:
                if mat.name.startswith( LensSim_LensMaterialName ):
                    lens_object = child
    if not lens_object:
        return
    
    
    # Access the mesh data (vertices) directly in object mode
    mesh = lens_object.data

    lensCTR = get_lens_camera_node()
    scale = lensCTR.inputs["camera object scale"].default_value


    ray_portal_plane_scale_x = lensCTR.inputs["ray portal plane scale x"].default_value
    ray_portal_plane_scale_y = lensCTR.inputs["ray portal plane scale y"].default_value

    lens_object.scale[0] = ray_portal_plane_scale_x
    lens_object.scale[1] = ray_portal_plane_scale_y

    oversize = 0.005

    sx = (( scale * 0.5 ) * ( 1.0 / ray_portal_plane_scale_x ))
    sy = (( scale * 0.5 ) * ( 1.0 / ray_portal_plane_scale_y ))

    sx += oversize * sx
    sy += oversize * sy

    positions = [   [ sx, sy,0.0],
                    [ sx,-sy,0.0],
                    [-sx, sy,0.0],
                    [-sx,-sy,0.0]   ]

    # Access and modify the vertex positions
    i = 0
    for vert in mesh.vertices:

        vert.co.x = positions[i][0]
        vert.co.y = positions[i][1]
        vert.co.z = positions[i][2]
            
        #print(f"Original Position: {vert.co}")
        #vert.co.x += 1.0  # Example: Move vertices by +1 unit on X-axis
        #vert.co.y += 1.0  # Example: Move vertices by +1 unit on Y-axis
        #vert.co.z += 1.0  # Example: Move vertices by +1 unit on Z-axis

        i += 1

    # Update the object to reflect the changes
    lens_object.data.update()

   

def apply_viewport_mode():

    if LensSim_Camera != None:
    
        material = get_lens_camera_node()
        lens_node = get_lens_node()
        main_material = get_main_material()
        
        lensCTR = get_lens_camera_node()
        viewport_preview_enable = lensCTR.inputs["viewport preview enable"].default_value
        lensCTR.inputs["viewport preview enable state"].default_value = viewport_preview_enable
        
        camera_data = LensSim_Camera.data
        
        if viewport_preview_enable:
            
            remove_limit_scale_constraint(LensSim_Camera)
            
            camera_data.type = "PERSP"
            
            image_scale_ref01 = calculate_image_scale_ref( 3.0, 0.0 )
            focal_length_add = lensCTR.inputs["change focal length"].default_value
            image_scale_ref02 = calculate_image_scale_ref( get_focus_distance( False ), focal_length_add )
            ref_ratio = get_focus_distance( True ) / 3.0
            focus_dist_ratio = (image_scale_ref01 * ref_ratio) / image_scale_ref02
            
            #focal_length_add = material.inputs["change focal length"].default_value * .72
            
            # focal width
            if material.inputs["sensor mode"].default_value == 1:
                
                camera_data.lens = material.inputs["focal length"].default_value

            # best fit or sensor with
            else:
                
                image_scale_ref = lens_node.inputs["image scale ref"].default_value
                sensor_size = material.inputs["viewfinder scale"].default_value

                if material.inputs["sensor mode"].default_value == 0:
                    sensor_size = lens_node.inputs["default sensor size"].default_value
                
                camera_data.lens = ( ( 1.0/sensor_size ) * ( 1.0/image_scale_ref * 0.2169 ) ) #0.208 ? 0.217
            
            camera_data.lens = camera_data.lens * focus_dist_ratio
            #camera_data.lens = camera_data.lens + focal_length_add
            
            focus_mode = material.inputs["focus mode"].default_value
            
            if focus_mode < 1:
                camera_data.dof.focus_object = get_dof_object()
            
            if focus_mode == 2:
                camera_data.dof.focus_object = None
                camera_data.dof.use_dof = False
                
            if focus_mode == 1:
                camera_data.dof.focus_object = None
                dof_object = get_dof_object()
                
                if dof_object == None or LensSim_DofEmptyParent == None:
                    return

                focus_dist = get_focus_distance( True )
                    
                camera_data.dof.use_dof = True
                camera_data.dof.focus_distance = focus_dist
                camera_data.dof.aperture_fstop = 1.0
            
            aperture_ratio = 1.0 / lensCTR.inputs["anamorph emulator squeeze factor"].default_value
            aperture_ratio *= 1.0 + (lensCTR.inputs["anamorph emulator bokeh aspect ratio"].default_value * 2.0)
            camera_data.dof.aperture_ratio = aperture_ratio
            
            fstop_0_1 = (1.0 / lensCTR.inputs["f stop"].default_value) * lens_node.inputs["f number"].default_value
            #fstop_0_1 = 
            fstop = max( lensCTR.inputs["f stop"].default_value, lens_node.inputs["f number"].default_value )
            

            
            if bpy.context.scene.my_addon_props.force_lens_dof_render:
                camera_data.dof.use_dof = True
            else:
                camera_data.dof.use_dof = False
                
            camera_data.dof.aperture_fstop = fstop
            #print( fstop_0_1 )
            
                    
            #LensSim_LensMesh.hide_select = True
            LensSim_LensMesh.hide_viewport = True
            LensSim_LensMesh.hide_render = True
            
            # set clip start
            camera_data.clip_start = lensCTR.inputs["clip start"].default_value
            
            if camera_data.clip_start < 0.01:
                camera_data.clip_start = 0.01
            
            lens_dirt_surface = get_lens_dirt_surface()
            if lens_dirt_surface != None:
                lens_dirt_surface.hide_viewport = True
            
            lens_visualize_mesh = get_lens_visualize_mesh()
            if lens_visualize_mesh != None:
                lens_visualize_mesh.hide_viewport = True
            
        else:
            
            
            add_limit_scale_constraint(LensSim_Camera)
            
            LensSim_LensMesh.hide_viewport = False
            LensSim_LensMesh.hide_render = False
            
            camera_data.dof.focus_object = None
            camera_data.dof.use_dof = True
            camera_data.type = "ORTHO"
            #camera_data.dof.focus_distance = 0.01
            camera_data.dof.focus_object = None
            camera_data.dof.aperture_fstop = 100.0
            camera_data.dof.aperture_ratio = 1.0
            camera_data.dof.aperture_blades = 0
            camera_data.clip_start = 0.001

            update_lens_mesh_distance()

            #camera_data.dof.focus_object = plane_obj
            
            lens_dirt_surface = get_lens_dirt_surface()
            if lens_dirt_surface != None:
                lens_dirt_surface.hide_viewport = False
                
            lens_visualize_mesh = get_lens_visualize_mesh()
            if lens_visualize_mesh != None:
                lens_visualize_mesh.hide_viewport = False

def get_viewport_mode():
    
    current_camera = LensSim_Camera

    if not is_LensSimCamera( current_camera ):
        return None
    
    viewport_preview_state = get_lens_camera_node().inputs["viewport preview enable"].default_value
    
    result = False
    
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA':
            if is_LensSimCamera( obj ):
                
                result = get_lens_camera_node().inputs["viewport preview enable"].default_value
                break
   
    # restore camera
    is_LensSimCamera( current_camera )

    return result

def set_viewport_mode( mode ):

    current_camera = LensSim_Camera

    # Iterate through all scenes
    for scene in bpy.data.scenes:
        # Iterate through all objects in the scene
        for obj in scene.objects:
            # Check if the object is a camera
            if obj.type == 'CAMERA':
                if is_LensSimCamera( obj ):

                    get_lens_camera_node().inputs["viewport preview enable"].default_value = mode
                    apply_viewport_mode()
    
    # restore camera
    is_LensSimCamera( current_camera )

def viewport_mode():

    disable_all = bpy.context.scene.my_addon_props.disable_all
    
    if disable_all:
        
        current_camera = LensSim_Camera
        viewport_preview_state = get_lens_camera_node().inputs["viewport preview enable"].default_value
        
        # Iterate through all scenes
        for scene in bpy.data.scenes:
            # Iterate through all objects in the scene
            for obj in scene.objects:
                if obj.type == 'CAMERA':
                    if is_LensSimCamera( obj ):

                        get_lens_camera_node().inputs["viewport preview enable"].default_value = viewport_preview_state
                        apply_viewport_mode()
                    
        # restore camera
        is_LensSimCamera( current_camera )

    else:
        apply_viewport_mode()

def sync_material_parms():

    lensCTR = get_lens_camera_node()
    lens_data = get_lens_node()

    if lensCTR == None:
        return

    material = LensSim_LensMaterial

    schematic = lensCTR.inputs["schematic enable"].default_value
    schematic_old = lensCTR.inputs["schematic enable state"].default_value
    
    if schematic_old != schematic:
        lensCTR.inputs["schematic enable state"].default_value = schematic
        build_lens_system()

    ray_enable = lensCTR.inputs["cast rays"].default_value
    ray_enable_old = lensCTR.inputs["cast rays state"].default_value
    
    if ray_enable_old != ray_enable:
        lensCTR.inputs["cast rays state"].default_value = ray_enable
        update_lens_rays()
        
    if schematic and ray_enable:
        update_lens_rays()
        
        
        
    viewport_preview_enable = lensCTR.inputs["viewport preview enable"].default_value
    viewport_preview_enable_old = lensCTR.inputs["viewport preview enable state"].default_value
    
    if viewport_preview_enable_old != viewport_preview_enable:

        lensCTR.inputs["viewport preview enable state"].default_value = viewport_preview_enable
        
        viewport_mode()
        
        #if viewport_preview_enable:
            #viewport_mode()
    
    focus_object_attached = lensCTR.inputs["focus object attached"].default_value
    focus_object_attached_old = lensCTR.inputs["focus object attached state"].default_value
    
    if focus_object_attached_old != focus_object_attached:
        lensCTR.inputs["focus object attached state"].default_value = focus_object_attached
        focus_object_attach()
    
    
    #LensSim_Camera
    
    ray_portal_plane_scale_y_is_x = lensCTR.inputs["ray portal plane scale y is x"].default_value
    ray_portal_plane_scale_y_is_x_state = lensCTR.inputs["ray portal plane scale y is x state"].default_value
    
    if ray_portal_plane_scale_y_is_x != ray_portal_plane_scale_y_is_x_state:
        lensCTR.inputs["ray portal plane scale y is x state"].default_value = ray_portal_plane_scale_y_is_x
        lensCTR.inputs["ray portal plane scale y"].default_value = lensCTR.inputs["ray portal plane scale x"].default_value
    
    camera_object_scale = lensCTR.inputs["camera object scale"].default_value
    camera_object_scale_old = lensCTR.inputs["camera object scale state"].default_value
    
    camera_object_scale_even = lensCTR.inputs["camera object scale even"].default_value
    camera_object_scale_even_old = lensCTR.inputs["camera object scale even state"].default_value
    
    ray_portal_plane_scale_x = lensCTR.inputs["ray portal plane scale x"].default_value
    ray_portal_plane_scale_y = lensCTR.inputs["ray portal plane scale y"].default_value
    ray_portal_plane_scale_x_old = lensCTR.inputs["ray portal plane scale x state"].default_value
    ray_portal_plane_scale_y_old = lensCTR.inputs["ray portal plane scale y state"].default_value
    
    if camera_object_scale_old != camera_object_scale or camera_object_scale_even_old != camera_object_scale_even or ray_portal_plane_scale_x != ray_portal_plane_scale_x_old or ray_portal_plane_scale_y != ray_portal_plane_scale_y_old:
        lensCTR.inputs["camera object scale state"].default_value = camera_object_scale
        lensCTR.inputs["camera object scale even state"].default_value = camera_object_scale_even

        lensCTR.inputs["ray portal plane scale x state"].default_value = ray_portal_plane_scale_x
        lensCTR.inputs["ray portal plane scale y state"].default_value = ray_portal_plane_scale_y

        if ray_portal_plane_scale_y_is_x:
            if ray_portal_plane_scale_x != ray_portal_plane_scale_x_old:
                lensCTR.inputs["ray portal plane scale y"].default_value = lensCTR.inputs["ray portal plane scale x"].default_value
            if ray_portal_plane_scale_y != ray_portal_plane_scale_y_old:
                lensCTR.inputs["ray portal plane scale x"].default_value = lensCTR.inputs["ray portal plane scale y"].default_value
                
        camera_data = LensSim_Camera.data
        
        if camera_object_scale_even == True:
            camera_data.display_size = camera_object_scale
        else:
            camera_data.display_size = 1.0

        update_camera_scale()

        camera_data.ortho_scale = camera_object_scale
    
    build_lens_mesh_state = lensCTR.inputs["lens geo enable"].default_value
    build_lens_mesh_state_old = lensCTR.inputs["lens geo enable state"].default_value
    
    global_scale = lensCTR.inputs["global scale"].default_value
    global_scale_old = lensCTR.inputs["global scale state"].default_value
    
    if build_lens_mesh_state_old != build_lens_mesh_state or global_scale != global_scale_old:
        lensCTR.inputs["lens geo enable state"].default_value = build_lens_mesh_state
        lensCTR.inputs["global scale state"].default_value = global_scale
        
        build_lens_mesh()
        lens_dirt_surface_update()
    
    
    
    
    
    lens_dirt_object = lensCTR.inputs["lens dirt object enable"].default_value
    lens_dirt_object_state = lensCTR.inputs["lens dirt object enable state"].default_value
    
    if lens_dirt_object != lens_dirt_object_state:
        
        lensCTR.inputs["lens dirt object enable state"].default_value = lens_dirt_object
    
        lens_dirt_surface_update()
    
    

    attribs = ["lens dirt object distance", "lens dirt object scale"]
    
    for attrib in attribs:
        val = lensCTR.inputs[attrib].default_value
        val_old = lensCTR.inputs[attrib+" state"].default_value
    
        if val != val_old:
            lensCTR.inputs[attrib+" state"].default_value = val
            lens_dirt_surface_update()
    
    
    lens_mesh_distance = lensCTR.inputs["lens mesh distance"].default_value
    lens_mesh_distance_old = lensCTR.inputs["lens mesh distance state"].default_value
    
    if lens_mesh_distance_old != lens_mesh_distance:
        
        if lens_mesh_distance < 0.01:
            lens_mesh_distance = 0.01
            lensCTR.inputs["lens mesh distance"].default_value = lens_mesh_distance
        
        lensCTR.inputs["lens mesh distance state"].default_value = lens_mesh_distance
        update_lens_mesh_distance()


    
    fstop = lensCTR.inputs["f stop"].default_value
    fstop_old = lensCTR.inputs["f stop state"].default_value
    
    if fstop_old != fstop:

        # clamp f stop
        if lens_data.inputs["f number"].default_value > fstop:
            lensCTR.inputs["f stop"].default_value = lens_data.inputs["f number"].default_value

        lensCTR.inputs["f stop state"].default_value = lensCTR.inputs["f stop"].default_value
    
    
    array = [[ "BokehTextureCustom", "BokehImageCustomName", "aperture custom image white color sum", "aperture custom image intensity sum", "aperture custom image gamma", "aperture custom image gamma state" ],
             [ "LensDirtImage", "LensDirtImageName", "lens dirt image white color sum", "lens dirt image intensity sum", "lens dirt image gamma", "lens dirt image gamma state" ]]
    
    for strings in array:
        #print( strings )
    
        BokehImageCustom = None
        try:
            BokehImageCustom = LensSim_LensMaterial.node_tree.nodes[ strings[0] ].image.name
        except:
            BokehImageCustom = None
        
        if BokehImageCustom != None:
            
            BokehImageCustomState = LensSim_LensMaterial.node_tree.nodes[ strings[1] ].label
            
            gamma = lensCTR.inputs[ strings[4] ].default_value
            gamma_old = lensCTR.inputs[ strings[5] ].default_value
            
            # if image has changed
            if BokehImageCustom != BokehImageCustomState or gamma != gamma_old:
                # update node label
                LensSim_LensMaterial.node_tree.nodes[ strings[1] ].label = BokehImageCustom
                
                # get image
                image_name = LensSim_LensMaterial.node_tree.nodes[ strings[0] ].image.name
                if image_name in bpy.data.images:
                    
                    image = bpy.data.images[ image_name ]
                    
                    # calculate white color sum etc
                    material = get_lens_camera_node()

                    lensCTR.inputs[ strings[5] ].default_value = gamma
                    
                    white_color_sum( image, material.inputs[ strings[2] ], gamma )
                    unit_intensity_sum( image, material.inputs[ strings[3] ], gamma )

                    # set color space
                    colorspace = "Non-Color"
                    if image.colorspace_settings.name != colorspace:
                        image.colorspace_settings.name = colorspace



    # disable lens update
    states = [  "sensor mode",
                "focal length",
                "viewfinder scale",
                "change focal length",
                "f stop" ]
                
    for prop in states:
        val0 = lensCTR.inputs[prop].default_value
        val1 = lensCTR.inputs[prop + " state"].default_value
        if val0 != val1:
            lensCTR.inputs[prop + " state"].default_value = val0
        
            if lensCTR.inputs["viewport preview enable"].default_value:
                viewport_mode()

def LensSim_check_material_changes(scene, depsgraph):


    props = bpy.context.scene.my_addon_props
    pinned = getattr(props, "pin_camera" )
    
    #WIP find a better way to do this, sometimes the event handler get triggered but there is no update.
    if len( depsgraph.updates ) == 0:
        sync_material_parms()
    
    for update in depsgraph.updates:

        # update camera if not pinned
        if not pinned:
            # update lenses_enum when selecting a new lens
            selected_objects = bpy.context.selected_objects

            for obj in selected_objects:

                if obj.type == 'CAMERA':
                    #if obj != LensSim_Camera:
                    if is_LensSimCamera(obj):

                        main_material = LensSim_LensMaterial
                        current_lens = get_current_lens()
                        
                        props = scene.my_addon_props
                        if props.lenses_enum != current_lens:
                            props.lenses_enum = current_lens
                            
                            sync_lens_parm()
                        
                        sync_bokeh_ui()
                        
        if isinstance(update.id, bpy.types.Material):

            # if changes to lens material
            if update.id.name.startswith( LensSim_LensMaterialName ):

                sync_material_parms()


preview_collections = {}

def generate_previews():
    # We are accessing all of the information that we generated in the register function below
    pcoll = preview_collections["thumbnail_previews"]
    #image_location = pcoll.images_location
    
    image_location = get_bokeh_path()
    
    VALID_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.exr', '.tiff')
    
    enum_items = []

    # Generate the thumbnails
    for i, image in enumerate(os.listdir(image_location)):
        if image.endswith(VALID_EXTENSIONS):
            filepath = os.path.join(image_location, image)
            thumb = pcoll.load(filepath, filepath, 'IMAGE')
            image_view_name = image[ : -(len( image.split(".")[ len(image.split("."))-1]) +1 ) ]
            enum_items.append((image, image_view_name, "", thumb.icon_id, i))
            

    return enum_items

'''  
preview_lens_collections = {}

def generate_lens_previews():
    # We are accessing all of the information that we generated in the register function below
    pcoll = preview_collections["lens_thumbnail_previews"]
    #image_location = pcoll.images_location
    
    image_location = get_lenses_path()
    
    VALID_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.exr', '.tiff')
    
    enum_items = []
    
    # Generate the thumbnails
    for i, image in enumerate(os.listdir(image_location)):
        if image.endswith(VALID_EXTENSIONS):
            filepath = os.path.join(image_location, image)
            thumb = pcoll.load(filepath, filepath, 'IMAGE')
            image_view_name = image[ : -(len( image.split(".")[ len(image.split("."))-1]) +1 ) ]
            enum_items.append((image, image_view_name, "", thumb.icon_id, i))
            
    return enum_items
'''
        
        
        

        
# Function to run when rendering starts
def LensSim_on_render_start(scene):
    global LensSim_ViewportModeLock
    global LensSim_IsRendering
    
    LensSim_IsRendering = True
    
    if bpy.context.scene.my_addon_props.force_lens_render and get_viewport_mode():
    
        LensSim_ViewportModeLock = True
        set_viewport_mode( False )
    
    #print("Render started")
    # Add any logic you want to execute here

# Function to run when rendering ends
def LensSim_on_render_end(scene):
    
    global LensSim_IsRendering
    global LensSim_ViewportModeLock
    
    if LensSim_ViewportModeLock:
    
        #LensSim_ViewportModeLock = True
        set_viewport_mode( True )
    
    LensSim_IsRendering = False
    LensSim_ViewportModeLock = False
    
    #print("Render ended")
    # Add any logic you want to execute here

        
        
        
        
        
        
# Register classes
classes = [


    MyPanel,
    ImportLens,

    AdvancedSettingsPanel,
    AdvancedSettingsCameraPanel,
    
    CameraObjectPanel,
    #SearchLensesButton,
    SensorPanel,
    OpenLensLinkButton,
    BuildLensButton,
    ReRegisterButton,
    AperturePanel,
    ReRegisterEventHandlersButton,
    #FocusPanel,
    OpenLensPath,
    
#FULL_VERSION_START
    LensDirtPanel,
    SplitDiopterPanel,
    TiltShiftPanel,
#FULL_VERSION_END
    EmulationPanel,
    ChromaticAberrationPanel,
    BloomGlarePanel,
#FULL_VERSION_START
    DistortionPanel,
#FULL_VERSION_END
    BlurEmulatorPanel,
    AnamorphEmulatorPanel,
#FULL_VERSION_START
    ExperimentalPanel,
#FULL_VERSION_END
    
    #ExportLensPanel,
    ResyncSelectedLensButton,
    ResetCameraCTRLButton,
    ResetAllCameraCTRLButton,
    
    AddAnamorphicButton,
    RemoveAnamorphicButton,
    
    SensorBestFitSizeAdd,
    SensorBestFitSizeSubtract,
    
    #ImportCamera,
    CreateCameraButton,
    ConvertCameraButton,
    SelectCameraFocusEmptyButton,
    #GetLensPropertiesButton,
    ResetLensPropertiesButton,
    #SetLensParmsButton,
    CalcImageScaleRefButton,
    CalcFocusPosButton,
    #SetLensPropertyOperator,
    #LensDataPanel,
    CustomColorRampWhiteColorSumButton,
    CustomColorRampUnitIntensitySumButton,
    CustomColorRampResetButton,
    
    CustomColorRampPreset01Button,
    CustomColorRampPreset02Button,
    CustomColorRampPreset03Button,
    CustomColorRampPreset04Button,
    
    MyAddonProperties,
    
    #LensDataProperties,
    
#FULL_VERSION_START
    LensDataMainPanel,
    LensDataCommonPanel,
    LensDataRayGuidingPanel,
    LensSurfacesPanel,
    ApertureShapePanel,
    RackFocusLUTPanel,
    SaveLensPanel,
#FULL_VERSION_END
    
    CalculateRackFocusLUT,
    
    SaveCurrentLens,
    ExportLens
    
    
]


# ??? should we have a global state to check this only once?
def re_apply_event_handlers( force_append ):
    
    handlers = bpy.app.handlers.depsgraph_update_post
    handler_exists = False
    for handler in handlers[:]:
        if handler.__name__ == "LensSim_check_material_changes":
            if force_append:
                handlers.remove(handler)
                handler_exists = False
            else:
                handler_exists = True
            break
    if not handler_exists:
        bpy.app.handlers.depsgraph_update_post.append(LensSim_check_material_changes)
        if force_append:
            print("installed LensSim_check_material_changes")

    # Add the functions to the handlers
    handlers = bpy.app.handlers.render_init
    handler_exists = False
    for handler in handlers[:]:  # Create a copy of the list to avoid modifying it while iterating
        if handler.__name__ == "LensSim_on_render_start":
            if force_append:
                handlers.remove(handler)
                handler_exists = False
            else:
                handler_exists = True
            break
    if not handler_exists:
        bpy.app.handlers.render_init.append(LensSim_on_render_start)
        if force_append:
            print("installed LensSim_on_render_start")
        
    handlers = bpy.app.handlers.render_complete
    handler_exists = False
    for handler in handlers[:]:  # Create a copy of the list to avoid modifying it while iterating
        if handler.__name__ == "LensSim_on_render_end":
            if force_append:
                handlers.remove(handler)
                handler_exists = False
            else:
                handler_exists = True
            break
    if not handler_exists:
        bpy.app.handlers.render_complete.append(LensSim_on_render_end)
        if force_append:
            print("installed LensSim_on_render_end")
        
    handlers = bpy.app.handlers.render_cancel
    handler_exists = False
    for handler in handlers[:]:  # Create a copy of the list to avoid modifying it while iterating
        if handler.__name__ == "LensSim_on_render_end":
            if force_append:
                handlers.remove(handler)
                handler_exists = False
            else:
                handler_exists = True
            break
    if not handler_exists:
        bpy.app.handlers.render_cancel.append(LensSim_on_render_end)
        if force_append:
            print("installed LensSim_on_render_end")
    

'''
# ??? outdated?
def register_event_handlers():
    
    #bpy.app.handlers.depsgraph_update_post.clear()
    handlers = bpy.app.handlers.depsgraph_update_post
    for handler in handlers[:]:  # Create a copy of the list to avoid modifying it while iterating
        if handler.__name__ == "LensSim_check_material_changes":
            handlers.remove(handler)
            #print("Handler unregistered:", handler)

    bpy.app.handlers.depsgraph_update_post.append(LensSim_check_material_changes)
'''

'''
def ensure_directories():
    script_path = get_script_folder_path()
    directories = [
        os.path.join(script_path, LensSim_DataFolder),
        os.path.join(script_path, LensSim_LensesFolder),
        os.path.join(script_path, LensSim_CameraFolder),
        os.path.join(script_path, LensSim_TextureFolder),
        os.path.join(script_path, LensSim_BokehFolder)
        
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
'''




def register():
    
    
    # Ensure directories exist
    #ensure_directories()
    
    
    # Check if the class is already registered
    for cls in classes:
        # Try to unregister the class; if it's not registered, catch the exception
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass  # The class was not registered, so there's nothing to do
    
    for cls in classes:
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.my_addon_props = bpy.props.PointerProperty(type=MyAddonProperties)
    #bpy.types.Scene.lens_data_props = bpy.props.PointerProperty(type=LensDataProperties)
    
    #register_event_handlers()
    
    handlers = bpy.app.handlers.depsgraph_update_post
    for handler in handlers[:]:
        if handler.__name__ == "LensSim_check_material_changes":
            handlers.remove(handler)

    # Add the functions to the handlers
    handlers = bpy.app.handlers.render_init
    for handler in handlers[:]:  # Create a copy of the list to avoid modifying it while iterating
        if handler.__name__ == "LensSim_on_render_start":
            handlers.remove(handler)
            #print("Handler unregistered:", handler)
    handlers = bpy.app.handlers.render_complete
    for handler in handlers[:]:  # Create a copy of the list to avoid modifying it while iterating
        if handler.__name__ == "LensSim_on_render_end":
            handlers.remove(handler)
            #print("Handler unregistered:", handler)
    handlers = bpy.app.handlers.render_cancel
    for handler in handlers[:]:  # Create a copy of the list to avoid modifying it while iterating
        if handler.__name__ == "LensSim_on_render_end":
            handlers.remove(handler)
            #print("Handler unregistered:", handler)
    
    bpy.app.handlers.depsgraph_update_post.append(LensSim_check_material_changes)
    bpy.app.handlers.render_init.append(LensSim_on_render_start)
    bpy.app.handlers.render_complete.append(LensSim_on_render_end)
    bpy.app.handlers.render_cancel.append(LensSim_on_render_end)

    #
    # bokeh thumbnails
    #
    
    from bpy.types import Scene
    from bpy.props import StringProperty, EnumProperty
    
    # Create a new preview collection (only upon register)
    pcoll = bpy.utils.previews.new()
    pcoll2 = bpy.utils.previews.new()
    
    # This line needs to be uncommented if you install as an addon
    #pcoll.images_location = os.path.join(os.path.dirname(__file__), "images")
    
    # This line is for running as a script. Make sure images are in a folder called images in the same
    # location as the Blender file. Comment out if you install as an addon
    #pcoll.images_location = bpy.path.abspath('//images')
    
    # Enable access to our preview collection outside of this function
    preview_collections["thumbnail_previews"] = pcoll
    preview_collections["lens_thumbnail_previews"] = pcoll2
    
    # This is an EnumProperty to hold all of the images
    # You really can save it anywhere in bpy.types.*  Just make sure the location makes sense
    bpy.types.Scene.my_thumbnails = EnumProperty(
        items=generate_previews(),update=on_bokeh_enum_change
        )
    
    #bpy.types.Scene.my_lens_thumbnails = EnumProperty(
    #    items=generate_lens_previews()
    #    #update=on_bokeh_enum_change
    #    )

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    #del bpy.types.Scene.lens_data_props
    del bpy.types.Scene.my_addon_props
    
    
    handlers = bpy.app.handlers.depsgraph_update_post
    for handler in handlers[:]:  # Create a copy of the list to avoid modifying it while iterating
        if handler.__name__ == "LensSim_check_material_changes":
            handlers.remove(handler)
            #print("Handler unregistered:", handler)
    #bpy.app.handlers.depsgraph_update_post.remove(LensSim_check_material_changes)


    #bpy.utils.unregister_class(LensDataMainPanel)
    #bpy.utils.unregister_class(LensDataPanel)
    #bpy.utils.unregister_class(LensDataRayGuidingPanel)
    #bpy.utils.unregister_class(LensDataCommonPanel)
    
    #del bpy.types.Scene.lens_data_props
    
    #bpy.utils.unregister_class(LensProperties)

    
    
    #
    # bokeh thumbnails
    #
    
    from bpy.types import WindowManager
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()
    
    del bpy.types.Scene.my_thumbnails
    
    bpy.app.handlers.render_init.remove(LensSim_on_render_start)
    bpy.app.handlers.render_complete.remove(LensSim_on_render_end)
    bpy.app.handlers.render_cancel.remove(LensSim_on_render_end)

if __name__ == "__main__":
    register()
    #registerLensProperties()
