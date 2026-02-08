bl_info = {
	"name" : "Procedural Chain",
	"author" : "Pedro Henrique",
	"version" : (4, 2, 0),
	"blender" : (4, 2, 3),
	"location" : "Node",
	"category" : "Node",
}

import bpy
import mathutils
import os

class Procedural_Chain(bpy.types.Operator):
	bl_idname = "node.procedural_chain"
	bl_label = "Procedural Chain"
	bl_options = {'REGISTER', 'UNDO'}
			
	def execute(self, context):
		#initialize chain node group
		def chain_node_group():
			chain = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Chain")

			chain.color_tag = 'NONE'
			chain.description = ""

			chain.is_modifier = True
			
			#chain interface
			#Socket Mesh
			mesh_socket = chain.interface.new_socket(name = "Mesh", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
			mesh_socket.attribute_domain = 'POINT'
			
			#Socket Scale
			scale_socket = chain.interface.new_socket(name = "Scale", in_out='INPUT', socket_type = 'NodeSocketFloat')
			scale_socket.default_value = 2.0
			scale_socket.min_value = 0.0
			scale_socket.max_value = 3.4028234663852886e+38
			scale_socket.subtype = 'DISTANCE'
			scale_socket.attribute_domain = 'POINT'
			
			#Socket Width
			width_socket = chain.interface.new_socket(name = "Width", in_out='INPUT', socket_type = 'NodeSocketFloat')
			width_socket.default_value = 0.5
			width_socket.min_value = -10000.0
			width_socket.max_value = 10000.0
			width_socket.subtype = 'NONE'
			width_socket.attribute_domain = 'POINT'
			
			#Socket Radius
			radius_socket = chain.interface.new_socket(name = "Radius", in_out='INPUT', socket_type = 'NodeSocketFloat')
			radius_socket.default_value = 0.10000002384185791
			radius_socket.min_value = -10000.0
			radius_socket.max_value = 10000.0
			radius_socket.subtype = 'NONE'
			radius_socket.attribute_domain = 'POINT'
			
			#Socket Material
			material_socket = chain.interface.new_socket(name = "Material", in_out='INPUT', socket_type = 'NodeSocketMaterial')
			material_socket.attribute_domain = 'POINT'
			
			#Socket ChainSides
			chainsides_socket = chain.interface.new_socket(name = "ChainSides", in_out='INPUT', socket_type = 'NodeSocketInt')
			chainsides_socket.default_value = 5
			chainsides_socket.min_value = 3
			chainsides_socket.max_value = 512
			chainsides_socket.subtype = 'NONE'
			chainsides_socket.attribute_domain = 'POINT'
			
			#Socket Roundness
			roundness_socket = chain.interface.new_socket(name = "Roundness", in_out='INPUT', socket_type = 'NodeSocketFloat')
			roundness_socket.default_value = 0.5
			roundness_socket.min_value = -10000.0
			roundness_socket.max_value = 10000.0
			roundness_socket.subtype = 'NONE'
			roundness_socket.attribute_domain = 'POINT'
			
			#Socket Bevel
			bevel_socket = chain.interface.new_socket(name = "Bevel", in_out='INPUT', socket_type = 'NodeSocketFloat')
			bevel_socket.default_value = 0.5
			bevel_socket.min_value = -10000.0
			bevel_socket.max_value = 10000.0
			bevel_socket.subtype = 'NONE'
			bevel_socket.attribute_domain = 'POINT'
			
			#Socket Twist
			twist_socket = chain.interface.new_socket(name = "Twist", in_out='INPUT', socket_type = 'NodeSocketFloat')
			twist_socket.default_value = 1.8325954675674438
			twist_socket.min_value = -3.4028234663852886e+38
			twist_socket.max_value = 3.4028234663852886e+38
			twist_socket.subtype = 'ANGLE'
			twist_socket.attribute_domain = 'POINT'
			
			#Socket Name
			name_socket = chain.interface.new_socket(name = "Name", in_out='INPUT', socket_type = 'NodeSocketString')
			name_socket.default_value = "ChainUV"
			name_socket.attribute_domain = 'POINT'
			
			#Socket Name
			name_socket_1 = chain.interface.new_socket(name = "Name", in_out='INPUT', socket_type = 'NodeSocketString')
			name_socket_1.default_value = "Edges"
			name_socket_1.attribute_domain = 'POINT'
			
			#Socket UV Scale
			uv_scale_socket = chain.interface.new_socket(name = "UV Scale", in_out='INPUT', socket_type = 'NodeSocketFloat')
			uv_scale_socket.default_value = 3.499999761581421
			uv_scale_socket.min_value = -10000.0
			uv_scale_socket.max_value = 10000.0
			uv_scale_socket.subtype = 'NONE'
			uv_scale_socket.attribute_domain = 'POINT'
			
			#Socket Rotate Profile
			rotate_profile_socket = chain.interface.new_socket(name = "Rotate Profile", in_out='INPUT', socket_type = 'NodeSocketFloat')
			rotate_profile_socket.default_value = 0.0
			rotate_profile_socket.min_value = -3.4028234663852886e+38
			rotate_profile_socket.max_value = 3.4028234663852886e+38
			rotate_profile_socket.subtype = 'ANGLE'
			rotate_profile_socket.attribute_domain = 'POINT'
			
			#Socket Resoulution
			resoulution_socket = chain.interface.new_socket(name = "Resoulution", in_out='INPUT', socket_type = 'NodeSocketInt')
			resoulution_socket.default_value = 23
			resoulution_socket.min_value = 1
			resoulution_socket.max_value = 1000
			resoulution_socket.subtype = 'NONE'
			resoulution_socket.attribute_domain = 'POINT'
			
			#Socket Base Resolution
			base_resolution_socket = chain.interface.new_socket(name = "Base Resolution", in_out='INPUT', socket_type = 'NodeSocketInt')
			base_resolution_socket.default_value = 8
			base_resolution_socket.min_value = 3
			base_resolution_socket.max_value = 1000
			base_resolution_socket.subtype = 'NONE'
			base_resolution_socket.attribute_domain = 'POINT'
			
			
			#initialize chain nodes
			#node Math.005
			math_005 = chain.nodes.new("ShaderNodeMath")
			math_005.name = "Math.005"
			math_005.operation = 'MULTIPLY'
			math_005.use_clamp = False
			#Value_001
			math_005.inputs[1].default_value = 0.5
			
			#node Math.006
			math_006 = chain.nodes.new("ShaderNodeMath")
			math_006.name = "Math.006"
			math_006.operation = 'MULTIPLY'
			math_006.use_clamp = False
			
			#node Curve Circle
			curve_circle = chain.nodes.new("GeometryNodeCurvePrimitiveCircle")
			curve_circle.name = "Curve Circle"
			curve_circle.mode = 'RADIUS'
			
			#node Curve Length
			curve_length = chain.nodes.new("GeometryNodeCurveLength")
			curve_length.name = "Curve Length"
			
			#node Math.007
			math_007 = chain.nodes.new("ShaderNodeMath")
			math_007.name = "Math.007"
			math_007.operation = 'DIVIDE'
			math_007.use_clamp = False
			
			#node Math.004
			math_004 = chain.nodes.new("ShaderNodeMath")
			math_004.name = "Math.004"
			math_004.operation = 'MULTIPLY'
			math_004.use_clamp = False
			#Value_001
			math_004.inputs[1].default_value = 0.4999999701976776
			
			#node Transform Geometry
			transform_geometry = chain.nodes.new("GeometryNodeTransform")
			transform_geometry.name = "Transform Geometry"
			transform_geometry.mode = 'COMPONENTS'
			#Translation
			transform_geometry.inputs[1].default_value = (0.0, 0.0, 0.0)
			#Scale
			transform_geometry.inputs[3].default_value = (1.0, 1.0, 1.0)
			
			#node Capture Attribute
			capture_attribute = chain.nodes.new("GeometryNodeCaptureAttribute")
			capture_attribute.name = "Capture Attribute"
			capture_attribute.active_index = 0
			capture_attribute.capture_items.clear()
			capture_attribute.capture_items.new('FLOAT', "Value")
			capture_attribute.capture_items["Value"].data_type = 'FLOAT_VECTOR'
			capture_attribute.domain = 'POINT'
			
			#node Mix
			mix = chain.nodes.new("ShaderNodeMix")
			mix.name = "Mix"
			mix.blend_type = 'MIX'
			mix.clamp_factor = True
			mix.clamp_result = False
			mix.data_type = 'VECTOR'
			mix.factor_mode = 'UNIFORM'
			
			#node Set Position
			set_position = chain.nodes.new("GeometryNodeSetPosition")
			set_position.name = "Set Position"
			#Selection
			set_position.inputs[1].default_value = True
			#Offset
			set_position.inputs[3].default_value = (0.0, 0.0, 0.0)
			
			#node Capture Attribute.001
			capture_attribute_001 = chain.nodes.new("GeometryNodeCaptureAttribute")
			capture_attribute_001.name = "Capture Attribute.001"
			capture_attribute_001.active_index = 0
			capture_attribute_001.capture_items.clear()
			capture_attribute_001.capture_items.new('FLOAT', "Value")
			capture_attribute_001.capture_items["Value"].data_type = 'FLOAT'
			capture_attribute_001.domain = 'POINT'
			
			#node Spline Parameter.001
			spline_parameter_001 = chain.nodes.new("GeometryNodeSplineParameter")
			spline_parameter_001.name = "Spline Parameter.001"
			
			#node Position
			position = chain.nodes.new("GeometryNodeInputPosition")
			position.name = "Position"
			
			#node Math.009
			math_009 = chain.nodes.new("ShaderNodeMath")
			math_009.name = "Math.009"
			math_009.operation = 'PINGPONG'
			math_009.use_clamp = False
			#Value_001
			math_009.inputs[1].default_value = 0.5
			
			#node Spline Parameter
			spline_parameter = chain.nodes.new("GeometryNodeSplineParameter")
			spline_parameter.name = "Spline Parameter"
			
			#node Capture Attribute.003
			capture_attribute_003 = chain.nodes.new("GeometryNodeCaptureAttribute")
			capture_attribute_003.name = "Capture Attribute.003"
			capture_attribute_003.active_index = 0
			capture_attribute_003.capture_items.clear()
			capture_attribute_003.capture_items.new('FLOAT', "Value")
			capture_attribute_003.capture_items["Value"].data_type = 'FLOAT'
			capture_attribute_003.domain = 'POINT'
			
			#node Math.011
			math_011 = chain.nodes.new("ShaderNodeMath")
			math_011.name = "Math.011"
			math_011.operation = 'MULTIPLY'
			math_011.use_clamp = False
			#Value_001
			math_011.inputs[1].default_value = 1.1999974250793457
			
			#node Math.012
			math_012 = chain.nodes.new("ShaderNodeMath")
			math_012.name = "Math.012"
			math_012.operation = 'DIVIDE'
			math_012.use_clamp = False
			
			#node Vector Math
			vector_math = chain.nodes.new("ShaderNodeVectorMath")
			vector_math.name = "Vector Math"
			vector_math.operation = 'DISTANCE'
			
			#node Set Material
			set_material = chain.nodes.new("GeometryNodeSetMaterial")
			set_material.name = "Set Material"
			#Selection
			set_material.inputs[1].default_value = True
			
			#node Group Output
			group_output = chain.nodes.new("NodeGroupOutput")
			group_output.name = "Group Output"
			group_output.is_active_output = True
			
			#node Set Shade Smooth
			set_shade_smooth = chain.nodes.new("GeometryNodeSetShadeSmooth")
			set_shade_smooth.name = "Set Shade Smooth"
			set_shade_smooth.domain = 'FACE'
			#Selection
			set_shade_smooth.inputs[1].default_value = True
			#Shade Smooth
			set_shade_smooth.inputs[2].default_value = True
			
			#node Math.003
			math_003 = chain.nodes.new("ShaderNodeMath")
			math_003.name = "Math.003"
			math_003.operation = 'ADD'
			math_003.use_clamp = False
			
			#node Capture Attribute.002
			capture_attribute_002 = chain.nodes.new("GeometryNodeCaptureAttribute")
			capture_attribute_002.name = "Capture Attribute.002"
			capture_attribute_002.active_index = 0
			capture_attribute_002.capture_items.clear()
			capture_attribute_002.capture_items.new('FLOAT', "Value")
			capture_attribute_002.capture_items["Value"].data_type = 'FLOAT'
			capture_attribute_002.domain = 'POINT'
			
			#node Quadrilateral.001
			quadrilateral_001 = chain.nodes.new("GeometryNodeCurvePrimitiveQuadrilateral")
			quadrilateral_001.name = "Quadrilateral.001"
			quadrilateral_001.mode = 'RECTANGLE'
			
			#node Math.002
			math_002 = chain.nodes.new("ShaderNodeMath")
			math_002.name = "Math.002"
			math_002.operation = 'MULTIPLY'
			math_002.use_clamp = False
			
			#node Math
			math = chain.nodes.new("ShaderNodeMath")
			math.name = "Math"
			math.operation = 'MULTIPLY'
			math.use_clamp = False
			
			#node Math.008
			math_008 = chain.nodes.new("ShaderNodeMath")
			math_008.name = "Math.008"
			math_008.operation = 'MULTIPLY'
			math_008.use_clamp = False
			
			#node Math.001
			math_001 = chain.nodes.new("ShaderNodeMath")
			math_001.name = "Math.001"
			math_001.operation = 'MULTIPLY'
			math_001.use_clamp = False
			#Value_001
			math_001.inputs[1].default_value = 0.5
			
			#node Math.010
			math_010 = chain.nodes.new("ShaderNodeMath")
			math_010.name = "Math.010"
			math_010.operation = 'MULTIPLY'
			math_010.use_clamp = False
			#Value_001
			math_010.inputs[1].default_value = 2.0
			
			#node Blur Attribute
			blur_attribute = chain.nodes.new("GeometryNodeBlurAttribute")
			blur_attribute.name = "Blur Attribute"
			blur_attribute.data_type = 'FLOAT_VECTOR'
			#Iterations
			blur_attribute.inputs[1].default_value = 125
			#Weight
			blur_attribute.inputs[2].default_value = 1.0
			
			#node Curve to Mesh
			curve_to_mesh = chain.nodes.new("GeometryNodeCurveToMesh")
			curve_to_mesh.name = "Curve to Mesh"
			#Fill Caps
			curve_to_mesh.inputs[2].default_value = False
			
			#node Combine XYZ
			combine_xyz = chain.nodes.new("ShaderNodeCombineXYZ")
			combine_xyz.name = "Combine XYZ"
			#Z
			combine_xyz.inputs[2].default_value = 0.0
			
			#node Vector Math.001
			vector_math_001 = chain.nodes.new("ShaderNodeVectorMath")
			vector_math_001.name = "Vector Math.001"
			vector_math_001.operation = 'SCALE'
			
			#node Store Named Attribute
			store_named_attribute = chain.nodes.new("GeometryNodeStoreNamedAttribute")
			store_named_attribute.name = "Store Named Attribute"
			store_named_attribute.data_type = 'FLOAT_VECTOR'
			store_named_attribute.domain = 'POINT'
			#Selection
			store_named_attribute.inputs[1].default_value = True
			
			#node Store Named Attribute.001
			store_named_attribute_001 = chain.nodes.new("GeometryNodeStoreNamedAttribute")
			store_named_attribute_001.name = "Store Named Attribute.001"
			store_named_attribute_001.data_type = 'FLOAT'
			store_named_attribute_001.domain = 'POINT'
			#Selection
			store_named_attribute_001.inputs[1].default_value = True
			
			#node Rotate Euler
			rotate_euler = chain.nodes.new("FunctionNodeRotateEuler")
			rotate_euler.name = "Rotate Euler"
			rotate_euler.rotation_type = 'AXIS_ANGLE'
			rotate_euler.space = 'OBJECT'
			#Rotation
			rotate_euler.inputs[0].default_value = (0.0, 0.0, 0.0)
			#Axis
			rotate_euler.inputs[2].default_value = (1.0, 0.0, 0.0)
			
			#node Transform Geometry.001
			transform_geometry_001 = chain.nodes.new("GeometryNodeTransform")
			transform_geometry_001.name = "Transform Geometry.001"
			transform_geometry_001.mode = 'COMPONENTS'
			#Translation
			transform_geometry_001.inputs[1].default_value = (0.0, 0.0, 0.0)
			#Scale
			transform_geometry_001.inputs[3].default_value = (1.0, 1.0, 1.0)
			
			#node Fillet Curve
			fillet_curve = chain.nodes.new("GeometryNodeFilletCurve")
			fillet_curve.name = "Fillet Curve"
			fillet_curve.mode = 'POLY'
			#Limit Radius
			fillet_curve.inputs[3].default_value = True
			
			#node Fillet Curve.001
			fillet_curve_001 = chain.nodes.new("GeometryNodeFilletCurve")
			fillet_curve_001.name = "Fillet Curve.001"
			fillet_curve_001.mode = 'POLY'
			#Limit Radius
			fillet_curve_001.inputs[3].default_value = True
			
			#node Group Input
			group_input = chain.nodes.new("NodeGroupInput")
			group_input.name = "Group Input"
			
			#node Math.013
			math_013 = chain.nodes.new("ShaderNodeMath")
			math_013.name = "Math.013"
			math_013.operation = 'MULTIPLY'
			math_013.use_clamp = False
			
			#node Axis Angle to Rotation
			axis_angle_to_rotation = chain.nodes.new("FunctionNodeAxisAngleToRotation")
			axis_angle_to_rotation.name = "Axis Angle to Rotation"
			#Axis
			axis_angle_to_rotation.inputs[0].default_value = (0.0, 0.0, 1.0)
			
			
			
			
			#Set locations
			math_005.location = (-200.17471313476562, 245.91812133789062)
			math_006.location = (19.999998092651367, 271.3543701171875)
			curve_circle.location = (-340.90008544921875, -330.1390686035156)
			curve_length.location = (-110.51155090332031, -387.43682861328125)
			math_007.location = (93.36013793945312, -289.66046142578125)
			math_004.location = (255.00799560546875, -163.02273559570312)
			transform_geometry.location = (1212.6217041015625, 297.29742431640625)
			capture_attribute.location = (924.4603271484375, 393.63397216796875)
			mix.location = (1276.6297607421875, 27.23674774169922)
			set_position.location = (1517.630126953125, 221.66046142578125)
			capture_attribute_001.location = (1738.0, 169.23812866210938)
			spline_parameter_001.location = (1480.82763671875, -30.712547302246094)
			position.location = (581.3546752929688, 312.67999267578125)
			math_009.location = (683.4566650390625, -365.9698791503906)
			spline_parameter.location = (410.04998779296875, -465.3617248535156)
			capture_attribute_003.location = (1983.25244140625, -182.983154296875)
			math_011.location = (1763.134765625, -321.77899169921875)
			math_012.location = (1502.8984375, -312.1466064453125)
			vector_math.location = (1279.38037109375, -185.0402374267578)
			set_material.location = (3728.87548828125, -69.55680084228516)
			group_output.location = (4169.4189453125, -54.373497009277344)
			set_shade_smooth.location = (3949.0, -45.077484130859375)
			math_003.location = (-168.8468475341797, 439.6830749511719)
			capture_attribute_002.location = (2242.808349609375, -38.693138122558594)
			quadrilateral_001.location = (235.79067993164062, 238.0586395263672)
			math_002.location = (-833.6751098632812, -20.966781616210938)
			math.location = (-525.0409545898438, 24.74319839477539)
			math_008.location = (491.0220031738281, -148.24575805664062)
			math_001.location = (-584.2724609375, -179.327880859375)
			math_010.location = (852.8032836914062, -165.39801025390625)
			blur_attribute.location = (1087.8583984375, -230.15219116210938)
			curve_to_mesh.location = (2730.28857421875, 109.52506256103516)
			combine_xyz.location = (2727.4228515625, -89.21951293945312)
			vector_math_001.location = (2974.012939453125, -106.4785385131836)
			store_named_attribute.location = (3160.88134765625, 99.0562973022461)
			store_named_attribute_001.location = (3375.220458984375, 20.27429962158203)
			rotate_euler.location = (936.2962646484375, 248.5963897705078)
			transform_geometry_001.location = (2492.7890625, 15.168170928955078)
			fillet_curve.location = (416.6661071777344, 162.53683471679688)
			fillet_curve_001.location = (742.64013671875, 2.55441951751709)
			group_input.location = (-1147.673095703125, 2.8397130966186523)
			math_013.location = (182.2842254638672, 21.6895751953125)
			axis_angle_to_rotation.location = (2238.213134765625, -187.05438232421875)
			
			#Set dimensions
			math_005.width, math_005.height = 140.0, 100.0
			math_006.width, math_006.height = 140.0, 100.0
			curve_circle.width, curve_circle.height = 140.0, 100.0
			curve_length.width, curve_length.height = 140.0, 100.0
			math_007.width, math_007.height = 140.0, 100.0
			math_004.width, math_004.height = 140.0, 100.0
			transform_geometry.width, transform_geometry.height = 140.0, 100.0
			capture_attribute.width, capture_attribute.height = 140.0, 100.0
			mix.width, mix.height = 140.0, 100.0
			set_position.width, set_position.height = 140.0, 100.0
			capture_attribute_001.width, capture_attribute_001.height = 140.0, 100.0
			spline_parameter_001.width, spline_parameter_001.height = 140.0, 100.0
			position.width, position.height = 140.0, 100.0
			math_009.width, math_009.height = 140.0, 100.0
			spline_parameter.width, spline_parameter.height = 140.0, 100.0
			capture_attribute_003.width, capture_attribute_003.height = 140.0, 100.0
			math_011.width, math_011.height = 140.0, 100.0
			math_012.width, math_012.height = 140.0, 100.0
			vector_math.width, vector_math.height = 140.0, 100.0
			set_material.width, set_material.height = 140.0, 100.0
			group_output.width, group_output.height = 140.0, 100.0
			set_shade_smooth.width, set_shade_smooth.height = 140.0, 100.0
			math_003.width, math_003.height = 140.0, 100.0
			capture_attribute_002.width, capture_attribute_002.height = 140.0, 100.0
			quadrilateral_001.width, quadrilateral_001.height = 140.0, 100.0
			math_002.width, math_002.height = 140.0, 100.0
			math.width, math.height = 140.0, 100.0
			math_008.width, math_008.height = 140.0, 100.0
			math_001.width, math_001.height = 140.0, 100.0
			math_010.width, math_010.height = 140.0, 100.0
			blur_attribute.width, blur_attribute.height = 140.0, 100.0
			curve_to_mesh.width, curve_to_mesh.height = 140.0, 100.0
			combine_xyz.width, combine_xyz.height = 140.0, 100.0
			vector_math_001.width, vector_math_001.height = 140.0, 100.0
			store_named_attribute.width, store_named_attribute.height = 140.0, 100.0
			store_named_attribute_001.width, store_named_attribute_001.height = 140.0, 100.0
			rotate_euler.width, rotate_euler.height = 140.0, 100.0
			transform_geometry_001.width, transform_geometry_001.height = 140.0, 100.0
			fillet_curve.width, fillet_curve.height = 140.0, 100.0
			fillet_curve_001.width, fillet_curve_001.height = 140.0, 100.0
			group_input.width, group_input.height = 140.0, 100.0
			math_013.width, math_013.height = 140.0, 100.0
			axis_angle_to_rotation.width, axis_angle_to_rotation.height = 140.0, 100.0
			
			#initialize chain links
			#math_001.Value -> curve_circle.Radius
			chain.links.new(math_001.outputs[0], curve_circle.inputs[4])
			#transform_geometry_001.Geometry -> curve_to_mesh.Profile Curve
			chain.links.new(transform_geometry_001.outputs[0], curve_to_mesh.inputs[1])
			#math_002.Value -> math_001.Value
			chain.links.new(math_002.outputs[0], math_001.inputs[0])
			#quadrilateral_001.Curve -> fillet_curve.Curve
			chain.links.new(quadrilateral_001.outputs[0], fillet_curve.inputs[0])
			#group_input.Scale -> math.Value
			chain.links.new(group_input.outputs[0], math.inputs[0])
			#group_input.Scale -> math_002.Value
			chain.links.new(group_input.outputs[0], math_002.inputs[0])
			#group_input.Radius -> math_002.Value
			chain.links.new(group_input.outputs[2], math_002.inputs[1])
			#group_input.Width -> math.Value
			chain.links.new(group_input.outputs[1], math.inputs[1])
			#group_input.Scale -> math_003.Value
			chain.links.new(group_input.outputs[0], math_003.inputs[0])
			#math_003.Value -> quadrilateral_001.Width
			chain.links.new(math_003.outputs[0], quadrilateral_001.inputs[0])
			#math_002.Value -> math_003.Value
			chain.links.new(math_002.outputs[0], math_003.inputs[1])
			#group_input.Material -> set_material.Material
			chain.links.new(group_input.outputs[3], set_material.inputs[2])
			#curve_circle.Curve -> fillet_curve_001.Curve
			chain.links.new(curve_circle.outputs[0], fillet_curve_001.inputs[0])
			#math_008.Value -> fillet_curve_001.Radius
			chain.links.new(math_008.outputs[0], fillet_curve_001.inputs[2])
			#group_input.ChainSides -> curve_circle.Resolution
			chain.links.new(group_input.outputs[4], curve_circle.inputs[0])
			#math_006.Value -> fillet_curve.Radius
			chain.links.new(math_006.outputs[0], fillet_curve.inputs[2])
			#math.Value -> math_005.Value
			chain.links.new(math.outputs[0], math_005.inputs[0])
			#math_005.Value -> math_006.Value
			chain.links.new(math_005.outputs[0], math_006.inputs[0])
			#group_input.Roundness -> math_006.Value
			chain.links.new(group_input.outputs[5], math_006.inputs[1])
			#curve_length.Length -> math_007.Value
			chain.links.new(curve_length.outputs[0], math_007.inputs[0])
			#group_input.ChainSides -> math_007.Value
			chain.links.new(group_input.outputs[4], math_007.inputs[1])
			#math_007.Value -> math_004.Value
			chain.links.new(math_007.outputs[0], math_004.inputs[0])
			#curve_circle.Curve -> curve_length.Curve
			chain.links.new(curve_circle.outputs[0], curve_length.inputs[0])
			#math_004.Value -> math_008.Value
			chain.links.new(math_004.outputs[0], math_008.inputs[0])
			#group_input.Bevel -> math_008.Value
			chain.links.new(group_input.outputs[6], math_008.inputs[1])
			#capture_attribute.Geometry -> transform_geometry.Geometry
			chain.links.new(capture_attribute.outputs[0], transform_geometry.inputs[0])
			#rotate_euler.Rotation -> transform_geometry.Rotation
			chain.links.new(rotate_euler.outputs[0], transform_geometry.inputs[2])
			#transform_geometry.Geometry -> set_position.Geometry
			chain.links.new(transform_geometry.outputs[0], set_position.inputs[0])
			#mix.Result -> set_position.Position
			chain.links.new(mix.outputs[1], set_position.inputs[2])
			#fillet_curve.Curve -> capture_attribute.Geometry
			chain.links.new(fillet_curve.outputs[0], capture_attribute.inputs[0])
			#position.Position -> capture_attribute.Value
			chain.links.new(position.outputs[0], capture_attribute.inputs[1])
			#capture_attribute.Value -> mix.A
			chain.links.new(capture_attribute.outputs[1], mix.inputs[4])
			#position.Position -> mix.B
			chain.links.new(position.outputs[0], mix.inputs[5])
			#spline_parameter.Factor -> math_009.Value
			chain.links.new(spline_parameter.outputs[0], math_009.inputs[0])
			#math_010.Value -> mix.Factor
			chain.links.new(math_010.outputs[0], mix.inputs[0])
			#set_shade_smooth.Geometry -> group_output.Mesh
			chain.links.new(set_shade_smooth.outputs[0], group_output.inputs[0])
			#capture_attribute_001.Geometry -> curve_to_mesh.Curve
			chain.links.new(capture_attribute_001.outputs[0], curve_to_mesh.inputs[0])
			#math_009.Value -> math_010.Value
			chain.links.new(math_009.outputs[0], math_010.inputs[0])
			#group_input.Twist -> rotate_euler.Angle
			chain.links.new(group_input.outputs[7], rotate_euler.inputs[3])
			#set_position.Geometry -> capture_attribute_001.Geometry
			chain.links.new(set_position.outputs[0], capture_attribute_001.inputs[0])
			#spline_parameter_001.Length -> capture_attribute_001.Value
			chain.links.new(spline_parameter_001.outputs[1], capture_attribute_001.inputs[1])
			#spline_parameter_001.Length -> capture_attribute_002.Value
			chain.links.new(spline_parameter_001.outputs[1], capture_attribute_002.inputs[1])
			#curve_to_mesh.Mesh -> store_named_attribute.Geometry
			chain.links.new(curve_to_mesh.outputs[0], store_named_attribute.inputs[0])
			#vector_math_001.Vector -> store_named_attribute.Value
			chain.links.new(vector_math_001.outputs[0], store_named_attribute.inputs[3])
			#capture_attribute_001.Value -> combine_xyz.X
			chain.links.new(capture_attribute_001.outputs[1], combine_xyz.inputs[0])
			#capture_attribute_002.Value -> combine_xyz.Y
			chain.links.new(capture_attribute_002.outputs[1], combine_xyz.inputs[1])
			#group_input.Name -> store_named_attribute.Name
			chain.links.new(group_input.outputs[8], store_named_attribute.inputs[2])
			#position.Position -> blur_attribute.Value
			chain.links.new(position.outputs[0], blur_attribute.inputs[0])
			#blur_attribute.Value -> vector_math.Vector
			chain.links.new(blur_attribute.outputs[0], vector_math.inputs[0])
			#position.Position -> vector_math.Vector
			chain.links.new(position.outputs[0], vector_math.inputs[1])
			#math_011.Value -> capture_attribute_003.Value
			chain.links.new(math_011.outputs[0], capture_attribute_003.inputs[1])
			#fillet_curve_001.Curve -> capture_attribute_003.Geometry
			chain.links.new(fillet_curve_001.outputs[0], capture_attribute_003.inputs[0])
			#capture_attribute_003.Geometry -> capture_attribute_002.Geometry
			chain.links.new(capture_attribute_003.outputs[0], capture_attribute_002.inputs[0])
			#capture_attribute_003.Value -> store_named_attribute_001.Value
			chain.links.new(capture_attribute_003.outputs[1], store_named_attribute_001.inputs[3])
			#store_named_attribute.Geometry -> store_named_attribute_001.Geometry
			chain.links.new(store_named_attribute.outputs[0], store_named_attribute_001.inputs[0])
			#group_input.Name -> store_named_attribute_001.Name
			chain.links.new(group_input.outputs[9], store_named_attribute_001.inputs[2])
			#math_012.Value -> math_011.Value
			chain.links.new(math_012.outputs[0], math_011.inputs[0])
			#vector_math.Value -> math_012.Value
			chain.links.new(vector_math.outputs[1], math_012.inputs[0])
			#set_material.Geometry -> set_shade_smooth.Geometry
			chain.links.new(set_material.outputs[0], set_shade_smooth.inputs[0])
			#math.Value -> quadrilateral_001.Height
			chain.links.new(math.outputs[0], quadrilateral_001.inputs[1])
			#math_008.Value -> math_012.Value
			chain.links.new(math_008.outputs[0], math_012.inputs[1])
			#combine_xyz.Vector -> vector_math_001.Vector
			chain.links.new(combine_xyz.outputs[0], vector_math_001.inputs[0])
			#group_input.UV Scale -> vector_math_001.Scale
			chain.links.new(group_input.outputs[10], vector_math_001.inputs[3])
			#store_named_attribute_001.Geometry -> set_material.Geometry
			chain.links.new(store_named_attribute_001.outputs[0], set_material.inputs[0])
			#capture_attribute_002.Geometry -> transform_geometry_001.Geometry
			chain.links.new(capture_attribute_002.outputs[0], transform_geometry_001.inputs[0])
			#group_input.Resoulution -> math_013.Value
			chain.links.new(group_input.outputs[12], math_013.inputs[0])
			#group_input.Resoulution -> fillet_curve_001.Count
			chain.links.new(group_input.outputs[12], fillet_curve_001.inputs[1])
			#math_013.Value -> fillet_curve.Count
			chain.links.new(math_013.outputs[0], fillet_curve.inputs[1])
			#group_input.Base Resolution -> math_013.Value
			chain.links.new(group_input.outputs[13], math_013.inputs[1])
			#group_input.Rotate Profile -> axis_angle_to_rotation.Angle
			chain.links.new(group_input.outputs[11], axis_angle_to_rotation.inputs[1])
			#axis_angle_to_rotation.Rotation -> transform_geometry_001.Rotation
			chain.links.new(axis_angle_to_rotation.outputs[0], transform_geometry_001.inputs[2])
			return chain

		chain = chain_node_group()

		#initialize curve_on_surface node group
		def curve_on_surface_node_group():
			curve_on_surface = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Curve on Surface")

			curve_on_surface.color_tag = 'NONE'
			curve_on_surface.description = ""

			curve_on_surface.is_modifier = True
			
			#curve_on_surface interface
			#Socket Geometry
			geometry_socket = curve_on_surface.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
			geometry_socket.attribute_domain = 'POINT'
			
			#Socket Geometry
			geometry_socket_1 = curve_on_surface.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
			geometry_socket_1.attribute_domain = 'POINT'
			
			#Socket Target
			target_socket = curve_on_surface.interface.new_socket(name = "Target", in_out='INPUT', socket_type = 'NodeSocketGeometry')
			target_socket.attribute_domain = 'POINT'
			
			#Socket Scale
			scale_socket_1 = curve_on_surface.interface.new_socket(name = "Scale", in_out='INPUT', socket_type = 'NodeSocketFloat')
			scale_socket_1.default_value = 0.699999988079071
			scale_socket_1.min_value = -10000.0
			scale_socket_1.max_value = 10000.0
			scale_socket_1.subtype = 'NONE'
			scale_socket_1.attribute_domain = 'POINT'
			
			#Socket Project
			project_socket = curve_on_surface.interface.new_socket(name = "Project", in_out='INPUT', socket_type = 'NodeSocketFloat')
			project_socket.default_value = 7.299999237060547
			project_socket.min_value = -10000.0
			project_socket.max_value = 10000.0
			project_socket.subtype = 'NONE'
			project_socket.attribute_domain = 'POINT'
			
			
			#initialize curve_on_surface nodes
			#node Position
			position_1 = curve_on_surface.nodes.new("GeometryNodeInputPosition")
			position_1.name = "Position"
			
			#node Sample Nearest Surface
			sample_nearest_surface = curve_on_surface.nodes.new("GeometryNodeSampleNearestSurface")
			sample_nearest_surface.name = "Sample Nearest Surface"
			sample_nearest_surface.data_type = 'FLOAT_VECTOR'
			#Group ID
			sample_nearest_surface.inputs[2].default_value = 0
			#Sample Position
			sample_nearest_surface.inputs[3].default_value = (0.0, 0.0, 0.0)
			#Sample Group ID
			sample_nearest_surface.inputs[4].default_value = 0
			
			#node Sample Nearest Surface.001
			sample_nearest_surface_001 = curve_on_surface.nodes.new("GeometryNodeSampleNearestSurface")
			sample_nearest_surface_001.name = "Sample Nearest Surface.001"
			sample_nearest_surface_001.data_type = 'FLOAT_VECTOR'
			#Group ID
			sample_nearest_surface_001.inputs[2].default_value = 0
			#Sample Position
			sample_nearest_surface_001.inputs[3].default_value = (0.0, 0.0, 0.0)
			#Sample Group ID
			sample_nearest_surface_001.inputs[4].default_value = 0
			
			#node Normal
			normal = curve_on_surface.nodes.new("GeometryNodeInputNormal")
			normal.name = "Normal"
			
			#node Group Input
			group_input_1 = curve_on_surface.nodes.new("NodeGroupInput")
			group_input_1.name = "Group Input"
			
			#node Group Output
			group_output_1 = curve_on_surface.nodes.new("NodeGroupOutput")
			group_output_1.name = "Group Output"
			group_output_1.is_active_output = True
			
			#node Set Position.001
			set_position_001 = curve_on_surface.nodes.new("GeometryNodeSetPosition")
			set_position_001.name = "Set Position.001"
			
			#node Vector Math
			vector_math_1 = curve_on_surface.nodes.new("ShaderNodeVectorMath")
			vector_math_1.name = "Vector Math"
			vector_math_1.operation = 'SCALE'
			
			#node Math
			math_1 = curve_on_surface.nodes.new("ShaderNodeMath")
			math_1.name = "Math"
			math_1.operation = 'MULTIPLY'
			math_1.use_clamp = False
			#Value_001
			math_1.inputs[1].default_value = 0.5
			
			#node Geometry Proximity
			geometry_proximity = curve_on_surface.nodes.new("GeometryNodeProximity")
			geometry_proximity.name = "Geometry Proximity"
			geometry_proximity.target_element = 'FACES'
			#Group ID
			geometry_proximity.inputs[1].default_value = 0
			#Source Position
			geometry_proximity.inputs[2].default_value = (0.0, 0.0, 0.0)
			#Sample Group ID
			geometry_proximity.inputs[3].default_value = 0
			
			#node Compare
			compare = curve_on_surface.nodes.new("FunctionNodeCompare")
			compare.name = "Compare"
			compare.data_type = 'FLOAT'
			compare.mode = 'ELEMENT'
			compare.operation = 'LESS_THAN'
			
			#node Math.001
			math_001_1 = curve_on_surface.nodes.new("ShaderNodeMath")
			math_001_1.name = "Math.001"
			math_001_1.operation = 'MULTIPLY'
			math_001_1.use_clamp = False
			
			
			
			
			#Set locations
			position_1.location = (-308.31939697265625, 179.57078552246094)
			sample_nearest_surface.location = (-37.640594482421875, 117.58584594726562)
			sample_nearest_surface_001.location = (-23.808753967285156, -46.01835632324219)
			normal.location = (-232.78741455078125, -150.93023681640625)
			group_input_1.location = (-315.99578857421875, -2.793203115463257)
			group_output_1.location = (1068.41650390625, 97.46424102783203)
			set_position_001.location = (798.343017578125, 132.67001342773438)
			vector_math_1.location = (463.86810302734375, -6.58807373046875)
			math_1.location = (175.3985595703125, -100.43643951416016)
			geometry_proximity.location = (182.46656799316406, -274.2442932128906)
			compare.location = (474.2286682128906, -322.7191162109375)
			math_001_1.location = (254.0, -414.003173828125)
			
			#Set dimensions
			position_1.width, position_1.height = 140.0, 100.0
			sample_nearest_surface.width, sample_nearest_surface.height = 150.0, 100.0
			sample_nearest_surface_001.width, sample_nearest_surface_001.height = 150.0, 100.0
			normal.width, normal.height = 140.0, 100.0
			group_input_1.width, group_input_1.height = 140.0, 100.0
			group_output_1.width, group_output_1.height = 140.0, 100.0
			set_position_001.width, set_position_001.height = 140.0, 100.0
			vector_math_1.width, vector_math_1.height = 140.0, 100.0
			math_1.width, math_1.height = 140.0, 100.0
			geometry_proximity.width, geometry_proximity.height = 140.0, 100.0
			compare.width, compare.height = 140.0, 100.0
			math_001_1.width, math_001_1.height = 140.0, 100.0
			
			#initialize curve_on_surface links
			#set_position_001.Geometry -> group_output_1.Geometry
			curve_on_surface.links.new(set_position_001.outputs[0], group_output_1.inputs[0])
			#group_input_1.Target -> sample_nearest_surface.Mesh
			curve_on_surface.links.new(group_input_1.outputs[1], sample_nearest_surface.inputs[0])
			#position_1.Position -> sample_nearest_surface.Value
			curve_on_surface.links.new(position_1.outputs[0], sample_nearest_surface.inputs[1])
			#group_input_1.Geometry -> set_position_001.Geometry
			curve_on_surface.links.new(group_input_1.outputs[0], set_position_001.inputs[0])
			#sample_nearest_surface.Value -> set_position_001.Position
			curve_on_surface.links.new(sample_nearest_surface.outputs[0], set_position_001.inputs[2])
			#group_input_1.Target -> sample_nearest_surface_001.Mesh
			curve_on_surface.links.new(group_input_1.outputs[1], sample_nearest_surface_001.inputs[0])
			#normal.Normal -> sample_nearest_surface_001.Value
			curve_on_surface.links.new(normal.outputs[0], sample_nearest_surface_001.inputs[1])
			#vector_math_1.Vector -> set_position_001.Offset
			curve_on_surface.links.new(vector_math_1.outputs[0], set_position_001.inputs[3])
			#sample_nearest_surface_001.Value -> vector_math_1.Vector
			curve_on_surface.links.new(sample_nearest_surface_001.outputs[0], vector_math_1.inputs[0])
			#math_1.Value -> vector_math_1.Scale
			curve_on_surface.links.new(math_1.outputs[0], vector_math_1.inputs[3])
			#group_input_1.Scale -> math_1.Value
			curve_on_surface.links.new(group_input_1.outputs[2], math_1.inputs[0])
			#group_input_1.Target -> geometry_proximity.Geometry
			curve_on_surface.links.new(group_input_1.outputs[1], geometry_proximity.inputs[0])
			#geometry_proximity.Distance -> compare.A
			curve_on_surface.links.new(geometry_proximity.outputs[1], compare.inputs[0])
			#compare.Result -> set_position_001.Selection
			curve_on_surface.links.new(compare.outputs[0], set_position_001.inputs[1])
			#math_001_1.Value -> compare.B
			curve_on_surface.links.new(math_001_1.outputs[0], compare.inputs[1])
			#group_input_1.Scale -> math_001_1.Value
			curve_on_surface.links.new(group_input_1.outputs[2], math_001_1.inputs[0])
			#group_input_1.Project -> math_001_1.Value
			curve_on_surface.links.new(group_input_1.outputs[3], math_001_1.inputs[1])
			return curve_on_surface

		curve_on_surface = curve_on_surface_node_group()

		#initialize connect_curves node group
		def connect_curves_node_group():
			connect_curves = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Connect Curves")

			connect_curves.color_tag = 'NONE'
			connect_curves.description = ""

			connect_curves.is_modifier = True
			
			#connect_curves interface
			#Socket Geometry
			geometry_socket_2 = connect_curves.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
			geometry_socket_2.attribute_domain = 'POINT'
			
			#Socket Geometry
			geometry_socket_3 = connect_curves.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
			geometry_socket_3.attribute_domain = 'POINT'
			
			#Socket Geometry
			geometry_socket_4 = connect_curves.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
			geometry_socket_4.attribute_domain = 'POINT'
			
			#Socket Scale
			scale_socket_2 = connect_curves.interface.new_socket(name = "Scale", in_out='INPUT', socket_type = 'NodeSocketFloat')
			scale_socket_2.default_value = 0.0010000000474974513
			scale_socket_2.min_value = 0.0
			scale_socket_2.max_value = 3.4028234663852886e+38
			scale_socket_2.subtype = 'DISTANCE'
			scale_socket_2.attribute_domain = 'POINT'
			
			#Socket Connect Distance
			connect_distance_socket = connect_curves.interface.new_socket(name = "Connect Distance", in_out='INPUT', socket_type = 'NodeSocketFloat')
			connect_distance_socket.default_value = 2.5
			connect_distance_socket.min_value = -10000.0
			connect_distance_socket.max_value = 10000.0
			connect_distance_socket.subtype = 'NONE'
			connect_distance_socket.attribute_domain = 'POINT'
			
			#Socket Target
			target_socket_1 = connect_curves.interface.new_socket(name = "Target", in_out='INPUT', socket_type = 'NodeSocketGeometry')
			target_socket_1.attribute_domain = 'POINT'
			
			#Socket Project
			project_socket_1 = connect_curves.interface.new_socket(name = "Project", in_out='INPUT', socket_type = 'NodeSocketFloat')
			project_socket_1.default_value = 7.299999237060547
			project_socket_1.min_value = -10000.0
			project_socket_1.max_value = 10000.0
			project_socket_1.subtype = 'NONE'
			project_socket_1.attribute_domain = 'POINT'
			
			#Socket Attach to Surface
			attach_to_surface_socket = connect_curves.interface.new_socket(name = "Attach to Surface", in_out='INPUT', socket_type = 'NodeSocketBool')
			attach_to_surface_socket.default_value = True
			attach_to_surface_socket.attribute_domain = 'POINT'
			
			
			#initialize connect_curves nodes
			#node Endpoint Selection
			endpoint_selection = connect_curves.nodes.new("GeometryNodeCurveEndpointSelection")
			endpoint_selection.name = "Endpoint Selection"
			#Start Size
			endpoint_selection.inputs[0].default_value = 1
			#End Size
			endpoint_selection.inputs[1].default_value = 2
			
			#node Capture Attribute
			capture_attribute_1 = connect_curves.nodes.new("GeometryNodeCaptureAttribute")
			capture_attribute_1.name = "Capture Attribute"
			capture_attribute_1.active_index = 0
			capture_attribute_1.capture_items.clear()
			capture_attribute_1.capture_items.new('FLOAT', "Value")
			capture_attribute_1.capture_items["Value"].data_type = 'BOOLEAN'
			capture_attribute_1.domain = 'POINT'
			
			#node Reverse Curve
			reverse_curve = connect_curves.nodes.new("GeometryNodeReverseCurve")
			reverse_curve.name = "Reverse Curve"
			#Selection
			reverse_curve.inputs[1].default_value = True
			
			#node Capture Attribute.001
			capture_attribute_001_1 = connect_curves.nodes.new("GeometryNodeCaptureAttribute")
			capture_attribute_001_1.name = "Capture Attribute.001"
			capture_attribute_001_1.active_index = 0
			capture_attribute_001_1.capture_items.clear()
			capture_attribute_001_1.capture_items.new('FLOAT', "Value")
			capture_attribute_001_1.capture_items["Value"].data_type = 'BOOLEAN'
			capture_attribute_001_1.domain = 'POINT'
			
			#node Boolean Math
			boolean_math = connect_curves.nodes.new("FunctionNodeBooleanMath")
			boolean_math.name = "Boolean Math"
			boolean_math.operation = 'OR'
			
			#node Merge by Distance
			merge_by_distance = connect_curves.nodes.new("GeometryNodeMergeByDistance")
			merge_by_distance.name = "Merge by Distance"
			merge_by_distance.mode = 'ALL'
			
			#node Curve to Mesh
			curve_to_mesh_1 = connect_curves.nodes.new("GeometryNodeCurveToMesh")
			curve_to_mesh_1.name = "Curve to Mesh"
			#Fill Caps
			curve_to_mesh_1.inputs[2].default_value = False
			
			#node Math
			math_2 = connect_curves.nodes.new("ShaderNodeMath")
			math_2.name = "Math"
			math_2.operation = 'MULTIPLY'
			math_2.use_clamp = False
			
			#node Mesh to Curve
			mesh_to_curve = connect_curves.nodes.new("GeometryNodeMeshToCurve")
			mesh_to_curve.name = "Mesh to Curve"
			#Selection
			mesh_to_curve.inputs[1].default_value = True
			
			#node Group Output
			group_output_2 = connect_curves.nodes.new("NodeGroupOutput")
			group_output_2.name = "Group Output"
			group_output_2.is_active_output = True
			
			#node Resample Curve
			resample_curve = connect_curves.nodes.new("GeometryNodeResampleCurve")
			resample_curve.name = "Resample Curve"
			resample_curve.mode = 'LENGTH'
			#Selection
			resample_curve.inputs[1].default_value = True
			
			#node Group
			group = connect_curves.nodes.new("GeometryNodeGroup")
			group.name = "Group"
			group.node_tree = curve_on_surface
			
			#node Switch
			switch = connect_curves.nodes.new("GeometryNodeSwitch")
			switch.name = "Switch"
			switch.input_type = 'GEOMETRY'
			
			#node Group Input
			group_input_2 = connect_curves.nodes.new("NodeGroupInput")
			group_input_2.name = "Group Input"
			
			
			
			
			#Set locations
			endpoint_selection.location = (-270.7879638671875, 140.82760620117188)
			capture_attribute_1.location = (-37.532508850097656, -42.661705017089844)
			reverse_curve.location = (187.42642211914062, -148.3493194580078)
			capture_attribute_001_1.location = (573.5389404296875, 116.80841827392578)
			boolean_math.location = (191.3841552734375, -12.739456176757812)
			merge_by_distance.location = (1013.7264404296875, 170.47183227539062)
			curve_to_mesh_1.location = (794.0, 140.22784423828125)
			math_2.location = (383.65869140625, 102.09771728515625)
			mesh_to_curve.location = (1201.508544921875, 138.7646484375)
			group_output_2.location = (2139.1552734375, 2.8592796325683594)
			resample_curve.location = (1887.4505615234375, 67.95384216308594)
			group.location = (1446.5819091796875, 146.9390106201172)
			switch.location = (1678.074462890625, 182.8203125)
			group_input_2.location = (-320.2218322753906, 3.8755199909210205)
			
			#Set dimensions
			endpoint_selection.width, endpoint_selection.height = 140.0, 100.0
			capture_attribute_1.width, capture_attribute_1.height = 140.0, 100.0
			reverse_curve.width, reverse_curve.height = 140.0, 100.0
			capture_attribute_001_1.width, capture_attribute_001_1.height = 140.0, 100.0
			boolean_math.width, boolean_math.height = 140.0, 100.0
			merge_by_distance.width, merge_by_distance.height = 140.0, 100.0
			curve_to_mesh_1.width, curve_to_mesh_1.height = 140.0, 100.0
			math_2.width, math_2.height = 140.0, 100.0
			mesh_to_curve.width, mesh_to_curve.height = 140.0, 100.0
			group_output_2.width, group_output_2.height = 140.0, 100.0
			resample_curve.width, resample_curve.height = 140.0, 100.0
			group.width, group.height = 140.0, 100.0
			switch.width, switch.height = 140.0, 100.0
			group_input_2.width, group_input_2.height = 140.0, 100.0
			
			#initialize connect_curves links
			#math_2.Value -> merge_by_distance.Distance
			connect_curves.links.new(math_2.outputs[0], merge_by_distance.inputs[2])
			#capture_attribute_1.Geometry -> reverse_curve.Curve
			connect_curves.links.new(capture_attribute_1.outputs[0], reverse_curve.inputs[0])
			#group_input_2.Geometry -> capture_attribute_1.Geometry
			connect_curves.links.new(group_input_2.outputs[0], capture_attribute_1.inputs[0])
			#endpoint_selection.Selection -> capture_attribute_1.Value
			connect_curves.links.new(endpoint_selection.outputs[0], capture_attribute_1.inputs[1])
			#endpoint_selection.Selection -> boolean_math.Boolean
			connect_curves.links.new(endpoint_selection.outputs[0], boolean_math.inputs[0])
			#capture_attribute_1.Value -> boolean_math.Boolean
			connect_curves.links.new(capture_attribute_1.outputs[1], boolean_math.inputs[1])
			#resample_curve.Curve -> group_output_2.Geometry
			connect_curves.links.new(resample_curve.outputs[0], group_output_2.inputs[0])
			#curve_to_mesh_1.Mesh -> merge_by_distance.Geometry
			connect_curves.links.new(curve_to_mesh_1.outputs[0], merge_by_distance.inputs[0])
			#reverse_curve.Curve -> capture_attribute_001_1.Geometry
			connect_curves.links.new(reverse_curve.outputs[0], capture_attribute_001_1.inputs[0])
			#boolean_math.Boolean -> capture_attribute_001_1.Value
			connect_curves.links.new(boolean_math.outputs[0], capture_attribute_001_1.inputs[1])
			#capture_attribute_001_1.Value -> merge_by_distance.Selection
			connect_curves.links.new(capture_attribute_001_1.outputs[1], merge_by_distance.inputs[1])
			#capture_attribute_001_1.Geometry -> curve_to_mesh_1.Curve
			connect_curves.links.new(capture_attribute_001_1.outputs[0], curve_to_mesh_1.inputs[0])
			#group_input_2.Scale -> math_2.Value
			connect_curves.links.new(group_input_2.outputs[1], math_2.inputs[0])
			#group_input_2.Connect Distance -> math_2.Value
			connect_curves.links.new(group_input_2.outputs[2], math_2.inputs[1])
			#merge_by_distance.Geometry -> mesh_to_curve.Mesh
			connect_curves.links.new(merge_by_distance.outputs[0], mesh_to_curve.inputs[0])
			#switch.Output -> resample_curve.Curve
			connect_curves.links.new(switch.outputs[0], resample_curve.inputs[0])
			#group_input_2.Scale -> resample_curve.Length
			connect_curves.links.new(group_input_2.outputs[1], resample_curve.inputs[3])
			#mesh_to_curve.Curve -> group.Geometry
			connect_curves.links.new(mesh_to_curve.outputs[0], group.inputs[0])
			#group_input_2.Target -> group.Target
			connect_curves.links.new(group_input_2.outputs[3], group.inputs[1])
			#group_input_2.Scale -> group.Scale
			connect_curves.links.new(group_input_2.outputs[1], group.inputs[2])
			#group_input_2.Project -> group.Project
			connect_curves.links.new(group_input_2.outputs[4], group.inputs[3])
			#group.Geometry -> switch.True
			connect_curves.links.new(group.outputs[0], switch.inputs[2])
			#mesh_to_curve.Curve -> switch.False
			connect_curves.links.new(mesh_to_curve.outputs[0], switch.inputs[1])
			#group_input_2.Attach to Surface -> switch.Switch
			connect_curves.links.new(group_input_2.outputs[5], switch.inputs[0])
			return connect_curves

		connect_curves = connect_curves_node_group()

		#initialize curveinstancer node group
		def curveinstancer_node_group():
			curveinstancer = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "CurveInstancer")

			curveinstancer.color_tag = 'NONE'
			curveinstancer.description = ""

			curveinstancer.is_modifier = True
			
			#curveinstancer interface
			#Socket Instances
			instances_socket = curveinstancer.interface.new_socket(name = "Instances", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
			instances_socket.attribute_domain = 'POINT'
			
			#Socket Curve
			curve_socket = curveinstancer.interface.new_socket(name = "Curve", in_out='INPUT', socket_type = 'NodeSocketGeometry')
			curve_socket.attribute_domain = 'POINT'
			
			#Socket Length
			length_socket = curveinstancer.interface.new_socket(name = "Length", in_out='INPUT', socket_type = 'NodeSocketFloat')
			length_socket.default_value = 0.10000000149011612
			length_socket.min_value = 0.009999999776482582
			length_socket.max_value = 3.4028234663852886e+38
			length_socket.subtype = 'DISTANCE'
			length_socket.attribute_domain = 'POINT'
			
			#Socket Instance
			instance_socket = curveinstancer.interface.new_socket(name = "Instance", in_out='INPUT', socket_type = 'NodeSocketGeometry')
			instance_socket.attribute_domain = 'POINT'
			
			#Socket Value
			value_socket = curveinstancer.interface.new_socket(name = "Value", in_out='INPUT', socket_type = 'NodeSocketFloat')
			value_socket.default_value = 24.0
			value_socket.min_value = -10000.0
			value_socket.max_value = 10000.0
			value_socket.subtype = 'NONE'
			value_socket.attribute_domain = 'POINT'
			
			#Socket Surface
			surface_socket = curveinstancer.interface.new_socket(name = "Surface", in_out='INPUT', socket_type = 'NodeSocketObject')
			surface_socket.attribute_domain = 'POINT'
			
			#Socket Connect Distance
			connect_distance_socket_1 = curveinstancer.interface.new_socket(name = "Connect Distance", in_out='INPUT', socket_type = 'NodeSocketFloat')
			connect_distance_socket_1.default_value = 9.899999618530273
			connect_distance_socket_1.min_value = -10000.0
			connect_distance_socket_1.max_value = 10000.0
			connect_distance_socket_1.subtype = 'NONE'
			connect_distance_socket_1.attribute_domain = 'POINT'
			
			#Socket Angle
			angle_socket = curveinstancer.interface.new_socket(name = "Angle", in_out='INPUT', socket_type = 'NodeSocketFloat')
			angle_socket.default_value = 0.0
			angle_socket.min_value = -3.4028234663852886e+38
			angle_socket.max_value = 3.4028234663852886e+38
			angle_socket.subtype = 'ANGLE'
			angle_socket.attribute_domain = 'POINT'
			
			#Socket Rotate
			rotate_socket = curveinstancer.interface.new_socket(name = "Rotate", in_out='INPUT', socket_type = 'NodeSocketFloat')
			rotate_socket.default_value = 0.0
			rotate_socket.min_value = -3.4028234663852886e+38
			rotate_socket.max_value = 3.4028234663852886e+38
			rotate_socket.subtype = 'ANGLE'
			rotate_socket.attribute_domain = 'POINT'
			
			#Socket Project
			project_socket_2 = curveinstancer.interface.new_socket(name = "Project", in_out='INPUT', socket_type = 'NodeSocketFloat')
			project_socket_2.default_value = 7.299999237060547
			project_socket_2.min_value = -10000.0
			project_socket_2.max_value = 10000.0
			project_socket_2.subtype = 'NONE'
			project_socket_2.attribute_domain = 'POINT'
			
			#Socket Attach to Surface
			attach_to_surface_socket_1 = curveinstancer.interface.new_socket(name = "Attach to Surface", in_out='INPUT', socket_type = 'NodeSocketBool')
			attach_to_surface_socket_1.default_value = True
			attach_to_surface_socket_1.attribute_domain = 'POINT'
			
			#Socket Pick Instance
			pick_instance_socket = curveinstancer.interface.new_socket(name = "Pick Instance", in_out='INPUT', socket_type = 'NodeSocketBool')
			pick_instance_socket.default_value = False
			pick_instance_socket.attribute_domain = 'POINT'
			
			
			#initialize curveinstancer nodes
			#node Curve Tangent
			curve_tangent = curveinstancer.nodes.new("GeometryNodeInputTangent")
			curve_tangent.name = "Curve Tangent"
			
			#node Math
			math_3 = curveinstancer.nodes.new("ShaderNodeMath")
			math_3.name = "Math"
			math_3.operation = 'MULTIPLY'
			math_3.use_clamp = False
			
			#node Spline Parameter
			spline_parameter_1 = curveinstancer.nodes.new("GeometryNodeSplineParameter")
			spline_parameter_1.name = "Spline Parameter"
			
			#node Math.001
			math_001_2 = curveinstancer.nodes.new("ShaderNodeMath")
			math_001_2.name = "Math.001"
			math_001_2.operation = 'MULTIPLY'
			math_001_2.use_clamp = False
			
			#node Math.003
			math_003_1 = curveinstancer.nodes.new("ShaderNodeMath")
			math_003_1.name = "Math.003"
			math_003_1.operation = 'MULTIPLY'
			math_003_1.use_clamp = False
			
			#node Curve Length
			curve_length_1 = curveinstancer.nodes.new("GeometryNodeCurveLength")
			curve_length_1.name = "Curve Length"
			
			#node Resample Curve
			resample_curve_1 = curveinstancer.nodes.new("GeometryNodeResampleCurve")
			resample_curve_1.name = "Resample Curve"
			resample_curve_1.mode = 'LENGTH'
			#Selection
			resample_curve_1.inputs[1].default_value = True
			
			#node Set Curve Normal
			set_curve_normal = curveinstancer.nodes.new("GeometryNodeSetCurveNormal")
			set_curve_normal.name = "Set Curve Normal"
			set_curve_normal.mode = 'Z_UP'
			#Selection
			set_curve_normal.inputs[1].default_value = True
			
			#node Capture Attribute.001
			capture_attribute_001_2 = curveinstancer.nodes.new("GeometryNodeCaptureAttribute")
			capture_attribute_001_2.name = "Capture Attribute.001"
			capture_attribute_001_2.active_index = 0
			capture_attribute_001_2.capture_items.clear()
			capture_attribute_001_2.capture_items.new('FLOAT', "Value")
			capture_attribute_001_2.capture_items["Value"].data_type = 'FLOAT'
			capture_attribute_001_2.domain = 'POINT'
			
			#node Object Info
			object_info = curveinstancer.nodes.new("GeometryNodeObjectInfo")
			object_info.name = "Object Info"
			object_info.transform_space = 'RELATIVE'
			#As Instance
			object_info.inputs[1].default_value = False
			
			#node Combine XYZ
			combine_xyz_1 = curveinstancer.nodes.new("ShaderNodeCombineXYZ")
			combine_xyz_1.name = "Combine XYZ"
			#Y
			combine_xyz_1.inputs[1].default_value = 0.0
			#Z
			combine_xyz_1.inputs[2].default_value = 0.0
			
			#node Capture Attribute
			capture_attribute_2 = curveinstancer.nodes.new("GeometryNodeCaptureAttribute")
			capture_attribute_2.name = "Capture Attribute"
			capture_attribute_2.active_index = 0
			capture_attribute_2.capture_items.clear()
			capture_attribute_2.capture_items.new('FLOAT', "Value")
			capture_attribute_2.capture_items["Value"].data_type = 'FLOAT_VECTOR'
			capture_attribute_2.domain = 'POINT'
			
			#node Group Output
			group_output_3 = curveinstancer.nodes.new("NodeGroupOutput")
			group_output_3.name = "Group Output"
			group_output_3.is_active_output = True
			
			#node Math.002
			math_002_1 = curveinstancer.nodes.new("ShaderNodeMath")
			math_002_1.name = "Math.002"
			math_002_1.operation = 'MODULO'
			math_002_1.use_clamp = False
			#Value_001
			math_002_1.inputs[1].default_value = 2.0
			
			#node Float to Integer
			float_to_integer = curveinstancer.nodes.new("FunctionNodeFloatToInt")
			float_to_integer.name = "Float to Integer"
			float_to_integer.rounding_mode = 'ROUND'
			
			#node Index
			index = curveinstancer.nodes.new("GeometryNodeInputIndex")
			index.name = "Index"
			
			#node Compare
			compare_1 = curveinstancer.nodes.new("FunctionNodeCompare")
			compare_1.name = "Compare"
			compare_1.data_type = 'INT'
			compare_1.mode = 'ELEMENT'
			compare_1.operation = 'GREATER_THAN'
			#B_INT
			compare_1.inputs[3].default_value = 0
			
			#node Curve to Mesh
			curve_to_mesh_2 = curveinstancer.nodes.new("GeometryNodeCurveToMesh")
			curve_to_mesh_2.name = "Curve to Mesh"
			#Fill Caps
			curve_to_mesh_2.inputs[2].default_value = False
			
			#node Mesh to Points
			mesh_to_points = curveinstancer.nodes.new("GeometryNodeMeshToPoints")
			mesh_to_points.name = "Mesh to Points"
			mesh_to_points.mode = 'EDGES'
			#Selection
			mesh_to_points.inputs[1].default_value = True
			#Position
			mesh_to_points.inputs[2].default_value = (0.0, 0.0, 0.0)
			#Radius
			mesh_to_points.inputs[3].default_value = 0.05000000074505806
			
			#node Capture Attribute.002
			capture_attribute_002_1 = curveinstancer.nodes.new("GeometryNodeCaptureAttribute")
			capture_attribute_002_1.name = "Capture Attribute.002"
			capture_attribute_002_1.active_index = 0
			capture_attribute_002_1.capture_items.clear()
			capture_attribute_002_1.capture_items.new('FLOAT', "Value")
			capture_attribute_002_1.capture_items["Value"].data_type = 'BOOLEAN'
			capture_attribute_002_1.domain = 'POINT'
			
			#node Math.004
			math_004_1 = curveinstancer.nodes.new("ShaderNodeMath")
			math_004_1.name = "Math.004"
			math_004_1.operation = 'ADD'
			math_004_1.use_clamp = False
			#Value_001
			math_004_1.inputs[1].default_value = 1.0
			
			#node Rotate Instances
			rotate_instances = curveinstancer.nodes.new("GeometryNodeRotateInstances")
			rotate_instances.name = "Rotate Instances"
			#Selection
			rotate_instances.inputs[1].default_value = True
			#Pivot Point
			rotate_instances.inputs[3].default_value = (0.0, 0.0, 0.0)
			#Local Space
			rotate_instances.inputs[4].default_value = True
			
			#node Rotate Instances.001
			rotate_instances_001 = curveinstancer.nodes.new("GeometryNodeRotateInstances")
			rotate_instances_001.name = "Rotate Instances.001"
			#Pivot Point
			rotate_instances_001.inputs[3].default_value = (0.0, 0.0, 0.0)
			#Local Space
			rotate_instances_001.inputs[4].default_value = True
			
			#node Rotate Instances.002
			rotate_instances_002 = curveinstancer.nodes.new("GeometryNodeRotateInstances")
			rotate_instances_002.name = "Rotate Instances.002"
			#Selection
			rotate_instances_002.inputs[1].default_value = True
			#Pivot Point
			rotate_instances_002.inputs[3].default_value = (0.0, 0.0, 0.0)
			#Local Space
			rotate_instances_002.inputs[4].default_value = True
			
			#node Store Named Attribute.002
			store_named_attribute_002 = curveinstancer.nodes.new("GeometryNodeStoreNamedAttribute")
			store_named_attribute_002.name = "Store Named Attribute.002"
			store_named_attribute_002.data_type = 'FLOAT'
			store_named_attribute_002.domain = 'INSTANCE'
			#Selection
			store_named_attribute_002.inputs[1].default_value = True
			#Name
			store_named_attribute_002.inputs[2].default_value = "IIndex"
			
			#node Index.001
			index_001 = curveinstancer.nodes.new("GeometryNodeInputIndex")
			index_001.name = "Index.001"
			
			#node Group Input
			group_input_3 = curveinstancer.nodes.new("NodeGroupInput")
			group_input_3.name = "Group Input"
			
			#node Group
			group_1 = curveinstancer.nodes.new("GeometryNodeGroup")
			group_1.name = "Group"
			group_1.node_tree = connect_curves
			
			#node Instance on Points
			instance_on_points = curveinstancer.nodes.new("GeometryNodeInstanceOnPoints")
			instance_on_points.name = "Instance on Points"
			#Selection
			instance_on_points.inputs[1].default_value = True
			#Scale
			instance_on_points.inputs[6].default_value = (1.0, 1.0, 1.0)
			
			#node Random Value
			random_value = curveinstancer.nodes.new("FunctionNodeRandomValue")
			random_value.name = "Random Value"
			random_value.data_type = 'INT'
			#Min_002
			random_value.inputs[4].default_value = 0
			#Max_002
			random_value.inputs[5].default_value = 100
			#ID
			random_value.inputs[7].default_value = 0
			#Seed
			random_value.inputs[8].default_value = 0
			
			#node Align Rotation to Vector
			align_rotation_to_vector = curveinstancer.nodes.new("FunctionNodeAlignRotationToVector")
			align_rotation_to_vector.name = "Align Rotation to Vector"
			align_rotation_to_vector.axis = 'X'
			align_rotation_to_vector.pivot_axis = 'AUTO'
			#Rotation
			align_rotation_to_vector.inputs[0].default_value = (0.0, 0.0, 0.0)
			#Factor
			align_rotation_to_vector.inputs[1].default_value = 1.0
			
			#node Axis Angle to Rotation
			axis_angle_to_rotation_1 = curveinstancer.nodes.new("FunctionNodeAxisAngleToRotation")
			axis_angle_to_rotation_1.name = "Axis Angle to Rotation"
			#Axis
			axis_angle_to_rotation_1.inputs[0].default_value = (1.0, 0.0, 0.0)
			
			#node Axis Angle to Rotation.001
			axis_angle_to_rotation_001 = curveinstancer.nodes.new("FunctionNodeAxisAngleToRotation")
			axis_angle_to_rotation_001.name = "Axis Angle to Rotation.001"
			#Axis
			axis_angle_to_rotation_001.inputs[0].default_value = (1.0, 0.0, 0.0)
			
			
			
			
			#Set locations
			curve_tangent.location = (-156.37527465820312, -152.6856689453125)
			math_3.location = (-1205.638671875, -123.10977172851562)
			spline_parameter_1.location = (-1425.1300048828125, -287.51019287109375)
			math_001_2.location = (-934.5739135742188, -120.57117462158203)
			math_003_1.location = (-609.15087890625, -150.73297119140625)
			curve_length_1.location = (-953.1588134765625, -311.0531005859375)
			resample_curve_1.location = (-1133.0330810546875, 31.918617248535156)
			set_curve_normal.location = (-840.411865234375, 49.094749450683594)
			capture_attribute_001_2.location = (476.1127014160156, 43.1953125)
			object_info.location = (-1135.225341796875, 236.4207000732422)
			combine_xyz_1.location = (1110.0272216796875, -232.64625549316406)
			capture_attribute_2.location = (206.75314331054688, 53.427581787109375)
			group_output_3.location = (2826.534423828125, 44.230690002441406)
			math_002_1.location = (209.90762329101562, 388.6302490234375)
			float_to_integer.location = (430.0, 371.4397888183594)
			index.location = (-230.05230712890625, 403.1832275390625)
			compare_1.location = (649.9144897460938, 370.66162109375)
			curve_to_mesh_2.location = (805.4127197265625, 51.52560043334961)
			mesh_to_points.location = (1058.988525390625, 23.242015838623047)
			capture_attribute_002_1.location = (1343.9979248046875, 204.8698272705078)
			math_004_1.location = (-10.0, 387.7796630859375)
			rotate_instances.location = (2402.364990234375, 61.96180725097656)
			rotate_instances_001.location = (2041.6231689453125, 82.51504516601562)
			rotate_instances_002.location = (2222.0, 69.18842315673828)
			store_named_attribute_002.location = (2588.81103515625, 74.30148315429688)
			index_001.location = (2400.794677734375, -172.40065002441406)
			group_input_3.location = (-1446.135498046875, 35.92435073852539)
			group_1.location = (-166.5796356201172, 112.15518188476562)
			instance_on_points.location = (1601.0899658203125, 31.73095703125)
			random_value.location = (1384.6461181640625, -96.54732513427734)
			align_rotation_to_vector.location = (756.5602416992188, -198.64688110351562)
			axis_angle_to_rotation_1.location = (1816.6827392578125, -152.29257202148438)
			axis_angle_to_rotation_001.location = (2002.5390625, -261.7918701171875)
			
			#Set dimensions
			curve_tangent.width, curve_tangent.height = 140.0, 100.0
			math_3.width, math_3.height = 140.0, 100.0
			spline_parameter_1.width, spline_parameter_1.height = 140.0, 100.0
			math_001_2.width, math_001_2.height = 140.0, 100.0
			math_003_1.width, math_003_1.height = 140.0, 100.0
			curve_length_1.width, curve_length_1.height = 140.0, 100.0
			resample_curve_1.width, resample_curve_1.height = 140.0, 100.0
			set_curve_normal.width, set_curve_normal.height = 140.0, 100.0
			capture_attribute_001_2.width, capture_attribute_001_2.height = 140.0, 100.0
			object_info.width, object_info.height = 140.0, 100.0
			combine_xyz_1.width, combine_xyz_1.height = 140.0, 100.0
			capture_attribute_2.width, capture_attribute_2.height = 140.0, 100.0
			group_output_3.width, group_output_3.height = 140.0, 100.0
			math_002_1.width, math_002_1.height = 140.0, 100.0
			float_to_integer.width, float_to_integer.height = 140.0, 100.0
			index.width, index.height = 140.0, 100.0
			compare_1.width, compare_1.height = 140.0, 100.0
			curve_to_mesh_2.width, curve_to_mesh_2.height = 140.0, 100.0
			mesh_to_points.width, mesh_to_points.height = 140.0, 100.0
			capture_attribute_002_1.width, capture_attribute_002_1.height = 140.0, 100.0
			math_004_1.width, math_004_1.height = 140.0, 100.0
			rotate_instances.width, rotate_instances.height = 100.0, 100.0
			rotate_instances_001.width, rotate_instances_001.height = 100.0, 100.0
			rotate_instances_002.width, rotate_instances_002.height = 100.0, 100.0
			store_named_attribute_002.width, store_named_attribute_002.height = 140.0, 100.0
			index_001.width, index_001.height = 140.0, 100.0
			group_input_3.width, group_input_3.height = 140.0, 100.0
			group_1.width, group_1.height = 146.04335021972656, 100.0
			instance_on_points.width, instance_on_points.height = 140.0, 100.0
			random_value.width, random_value.height = 140.0, 100.0
			align_rotation_to_vector.width, align_rotation_to_vector.height = 140.0, 100.0
			axis_angle_to_rotation_1.width, axis_angle_to_rotation_1.height = 140.0, 100.0
			axis_angle_to_rotation_001.width, axis_angle_to_rotation_001.height = 140.0, 100.0
			
			#initialize curveinstancer links
			#resample_curve_1.Curve -> set_curve_normal.Curve
			curveinstancer.links.new(resample_curve_1.outputs[0], set_curve_normal.inputs[0])
			#curve_tangent.Tangent -> capture_attribute_2.Value
			curveinstancer.links.new(curve_tangent.outputs[0], capture_attribute_2.inputs[1])
			#group_input_3.Length -> resample_curve_1.Length
			curveinstancer.links.new(group_input_3.outputs[1], resample_curve_1.inputs[3])
			#group_input_3.Instance -> instance_on_points.Instance
			curveinstancer.links.new(group_input_3.outputs[2], instance_on_points.inputs[2])
			#spline_parameter_1.Factor -> math_3.Value
			curveinstancer.links.new(spline_parameter_1.outputs[0], math_3.inputs[0])
			#spline_parameter_1.Length -> math_3.Value
			curveinstancer.links.new(spline_parameter_1.outputs[1], math_3.inputs[1])
			#math_3.Value -> math_001_2.Value
			curveinstancer.links.new(math_3.outputs[0], math_001_2.inputs[0])
			#rotate_instances_002.Instances -> rotate_instances.Instances
			curveinstancer.links.new(rotate_instances_002.outputs[0], rotate_instances.inputs[0])
			#combine_xyz_1.Vector -> rotate_instances.Rotation
			curveinstancer.links.new(combine_xyz_1.outputs[0], rotate_instances.inputs[2])
			#capture_attribute_2.Geometry -> capture_attribute_001_2.Geometry
			curveinstancer.links.new(capture_attribute_2.outputs[0], capture_attribute_001_2.inputs[0])
			#math_003_1.Value -> capture_attribute_001_2.Value
			curveinstancer.links.new(math_003_1.outputs[0], capture_attribute_001_2.inputs[1])
			#capture_attribute_001_2.Value -> combine_xyz_1.X
			curveinstancer.links.new(capture_attribute_001_2.outputs[1], combine_xyz_1.inputs[0])
			#group_input_3.Curve -> resample_curve_1.Curve
			curveinstancer.links.new(group_input_3.outputs[0], resample_curve_1.inputs[0])
			#group_input_3.Value -> math_001_2.Value
			curveinstancer.links.new(group_input_3.outputs[3], math_001_2.inputs[1])
			#math_001_2.Value -> math_003_1.Value
			curveinstancer.links.new(math_001_2.outputs[0], math_003_1.inputs[0])
			#curve_length_1.Length -> math_003_1.Value
			curveinstancer.links.new(curve_length_1.outputs[0], math_003_1.inputs[1])
			#group_input_3.Curve -> curve_length_1.Curve
			curveinstancer.links.new(group_input_3.outputs[0], curve_length_1.inputs[0])
			#group_input_3.Length -> group_1.Scale
			curveinstancer.links.new(group_input_3.outputs[1], group_1.inputs[1])
			#curve_to_mesh_2.Mesh -> mesh_to_points.Mesh
			curveinstancer.links.new(curve_to_mesh_2.outputs[0], mesh_to_points.inputs[0])
			#group_input_3.Surface -> object_info.Object
			curveinstancer.links.new(group_input_3.outputs[4], object_info.inputs[0])
			#object_info.Geometry -> group_1.Target
			curveinstancer.links.new(object_info.outputs[4], group_1.inputs[3])
			#align_rotation_to_vector.Rotation -> instance_on_points.Rotation
			curveinstancer.links.new(align_rotation_to_vector.outputs[0], instance_on_points.inputs[5])
			#group_input_3.Connect Distance -> group_1.Connect Distance
			curveinstancer.links.new(group_input_3.outputs[5], group_1.inputs[2])
			#instance_on_points.Instances -> rotate_instances_001.Instances
			curveinstancer.links.new(instance_on_points.outputs[0], rotate_instances_001.inputs[0])
			#capture_attribute_002_1.Value -> rotate_instances_001.Selection
			curveinstancer.links.new(capture_attribute_002_1.outputs[1], rotate_instances_001.inputs[1])
			#compare_1.Result -> capture_attribute_002_1.Value
			curveinstancer.links.new(compare_1.outputs[0], capture_attribute_002_1.inputs[1])
			#float_to_integer.Integer -> compare_1.A
			curveinstancer.links.new(float_to_integer.outputs[0], compare_1.inputs[2])
			#math_002_1.Value -> float_to_integer.Float
			curveinstancer.links.new(math_002_1.outputs[0], float_to_integer.inputs[0])
			#index.Index -> math_004_1.Value
			curveinstancer.links.new(index.outputs[0], math_004_1.inputs[0])
			#mesh_to_points.Points -> capture_attribute_002_1.Geometry
			curveinstancer.links.new(mesh_to_points.outputs[0], capture_attribute_002_1.inputs[0])
			#capture_attribute_002_1.Geometry -> instance_on_points.Points
			curveinstancer.links.new(capture_attribute_002_1.outputs[0], instance_on_points.inputs[0])
			#math_004_1.Value -> math_002_1.Value
			curveinstancer.links.new(math_004_1.outputs[0], math_002_1.inputs[0])
			#axis_angle_to_rotation_1.Rotation -> rotate_instances_001.Rotation
			curveinstancer.links.new(axis_angle_to_rotation_1.outputs[0], rotate_instances_001.inputs[2])
			#rotate_instances_001.Instances -> rotate_instances_002.Instances
			curveinstancer.links.new(rotate_instances_001.outputs[0], rotate_instances_002.inputs[0])
			#axis_angle_to_rotation_001.Rotation -> rotate_instances_002.Rotation
			curveinstancer.links.new(axis_angle_to_rotation_001.outputs[0], rotate_instances_002.inputs[2])
			#group_input_3.Project -> group_1.Project
			curveinstancer.links.new(group_input_3.outputs[8], group_1.inputs[4])
			#index_001.Index -> store_named_attribute_002.Value
			curveinstancer.links.new(index_001.outputs[0], store_named_attribute_002.inputs[3])
			#rotate_instances.Instances -> store_named_attribute_002.Geometry
			curveinstancer.links.new(rotate_instances.outputs[0], store_named_attribute_002.inputs[0])
			#store_named_attribute_002.Geometry -> group_output_3.Instances
			curveinstancer.links.new(store_named_attribute_002.outputs[0], group_output_3.inputs[0])
			#group_input_3.Attach to Surface -> group_1.Attach to Surface
			curveinstancer.links.new(group_input_3.outputs[9], group_1.inputs[5])
			#group_input_3.Pick Instance -> instance_on_points.Pick Instance
			curveinstancer.links.new(group_input_3.outputs[10], instance_on_points.inputs[3])
			#random_value.Value -> instance_on_points.Instance Index
			curveinstancer.links.new(random_value.outputs[2], instance_on_points.inputs[4])
			#set_curve_normal.Curve -> group_1.Geometry
			curveinstancer.links.new(set_curve_normal.outputs[0], group_1.inputs[0])
			#group_1.Geometry -> capture_attribute_2.Geometry
			curveinstancer.links.new(group_1.outputs[0], capture_attribute_2.inputs[0])
			#capture_attribute_001_2.Geometry -> curve_to_mesh_2.Curve
			curveinstancer.links.new(capture_attribute_001_2.outputs[0], curve_to_mesh_2.inputs[0])
			#capture_attribute_2.Value -> align_rotation_to_vector.Vector
			curveinstancer.links.new(capture_attribute_2.outputs[1], align_rotation_to_vector.inputs[2])
			#group_input_3.Angle -> axis_angle_to_rotation_1.Angle
			curveinstancer.links.new(group_input_3.outputs[6], axis_angle_to_rotation_1.inputs[1])
			#group_input_3.Rotate -> axis_angle_to_rotation_001.Angle
			curveinstancer.links.new(group_input_3.outputs[7], axis_angle_to_rotation_001.inputs[1])
			return curveinstancer

		curveinstancer = curveinstancer_node_group()

		#initialize procedural_chain node group
		def procedural_chain_node_group():
			procedural_chain = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Procedural Chain")

			procedural_chain.color_tag = 'NONE'
			procedural_chain.description = ""

			procedural_chain.is_modifier = True
			
			#procedural_chain interface
			#Socket Geometry
			geometry_socket_5 = procedural_chain.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
			geometry_socket_5.attribute_domain = 'POINT'
			
			#Socket Geometry
			geometry_socket_6 = procedural_chain.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
			geometry_socket_6.attribute_domain = 'POINT'
			
			#Socket Scale
			scale_socket_3 = procedural_chain.interface.new_socket(name = "Scale", in_out='INPUT', socket_type = 'NodeSocketFloat')
			scale_socket_3.default_value = 0.10000000149011612
			scale_socket_3.min_value = 0.009999999776482582
			scale_socket_3.max_value = 3.4028234663852886e+38
			scale_socket_3.subtype = 'DISTANCE'
			scale_socket_3.attribute_domain = 'POINT'
			
			#Socket Width
			width_socket_1 = procedural_chain.interface.new_socket(name = "Width", in_out='INPUT', socket_type = 'NodeSocketFloat')
			width_socket_1.default_value = 0.5
			width_socket_1.min_value = 0.0
			width_socket_1.max_value = 1.0
			width_socket_1.subtype = 'FACTOR'
			width_socket_1.attribute_domain = 'POINT'
			
			#Socket Radius
			radius_socket_1 = procedural_chain.interface.new_socket(name = "Radius", in_out='INPUT', socket_type = 'NodeSocketFloat')
			radius_socket_1.default_value = 0.24173200130462646
			radius_socket_1.min_value = 0.0
			radius_socket_1.max_value = 1.0
			radius_socket_1.subtype = 'FACTOR'
			radius_socket_1.attribute_domain = 'POINT'
			
			#Socket Twist
			twist_socket_1 = procedural_chain.interface.new_socket(name = "Twist", in_out='INPUT', socket_type = 'NodeSocketFloat')
			twist_socket_1.default_value = 0.0
			twist_socket_1.min_value = -3.4028234663852886e+38
			twist_socket_1.max_value = 3.4028234663852886e+38
			twist_socket_1.subtype = 'ANGLE'
			twist_socket_1.attribute_domain = 'POINT'
			
			#Socket Rotate Profile
			rotate_profile_socket_1 = procedural_chain.interface.new_socket(name = "Rotate Profile", in_out='INPUT', socket_type = 'NodeSocketFloat')
			rotate_profile_socket_1.default_value = 0.0
			rotate_profile_socket_1.min_value = -3.4028234663852886e+38
			rotate_profile_socket_1.max_value = 3.4028234663852886e+38
			rotate_profile_socket_1.subtype = 'ANGLE'
			rotate_profile_socket_1.attribute_domain = 'POINT'
			
			#Socket ChainSides
			chainsides_socket_1 = procedural_chain.interface.new_socket(name = "ChainSides", in_out='INPUT', socket_type = 'NodeSocketInt')
			chainsides_socket_1.default_value = 6
			chainsides_socket_1.min_value = 3
			chainsides_socket_1.max_value = 512
			chainsides_socket_1.subtype = 'NONE'
			chainsides_socket_1.attribute_domain = 'POINT'
			
			#Socket Roundness
			roundness_socket_1 = procedural_chain.interface.new_socket(name = "Roundness", in_out='INPUT', socket_type = 'NodeSocketFloat')
			roundness_socket_1.default_value = 0.5
			roundness_socket_1.min_value = 0.0
			roundness_socket_1.max_value = 1.0
			roundness_socket_1.subtype = 'FACTOR'
			roundness_socket_1.attribute_domain = 'POINT'
			
			#Socket Bevel
			bevel_socket_1 = procedural_chain.interface.new_socket(name = "Bevel", in_out='INPUT', socket_type = 'NodeSocketFloat')
			bevel_socket_1.default_value = 0.5
			bevel_socket_1.min_value = 0.0
			bevel_socket_1.max_value = 1.0
			bevel_socket_1.subtype = 'FACTOR'
			bevel_socket_1.attribute_domain = 'POINT'
			
			#Socket Connect Distance
			connect_distance_socket_2 = procedural_chain.interface.new_socket(name = "Connect Distance", in_out='INPUT', socket_type = 'NodeSocketFloat')
			connect_distance_socket_2.default_value = 2.4000000953674316
			connect_distance_socket_2.min_value = 0.0
			connect_distance_socket_2.max_value = 10000.0
			connect_distance_socket_2.subtype = 'NONE'
			connect_distance_socket_2.attribute_domain = 'POINT'
			
			#Socket Tilt
			tilt_socket = procedural_chain.interface.new_socket(name = "Tilt", in_out='INPUT', socket_type = 'NodeSocketFloat')
			tilt_socket.default_value = 0.0
			tilt_socket.min_value = -10000.0
			tilt_socket.max_value = 10000.0
			tilt_socket.subtype = 'NONE'
			tilt_socket.attribute_domain = 'POINT'
			
			#Socket Rotate
			rotate_socket_1 = procedural_chain.interface.new_socket(name = "Rotate", in_out='INPUT', socket_type = 'NodeSocketFloat')
			rotate_socket_1.default_value = 0.0
			rotate_socket_1.min_value = -3.4028234663852886e+38
			rotate_socket_1.max_value = 3.4028234663852886e+38
			rotate_socket_1.subtype = 'ANGLE'
			rotate_socket_1.attribute_domain = 'POINT'
			
			#Socket Jump Rotation
			jump_rotation_socket = procedural_chain.interface.new_socket(name = "Jump Rotation", in_out='INPUT', socket_type = 'NodeSocketFloat')
			jump_rotation_socket.default_value = 1.5707963705062866
			jump_rotation_socket.min_value = -3.4028234663852886e+38
			jump_rotation_socket.max_value = 3.4028234663852886e+38
			jump_rotation_socket.subtype = 'ANGLE'
			jump_rotation_socket.attribute_domain = 'POINT'
			
			#Socket UV Scale
			uv_scale_socket_1 = procedural_chain.interface.new_socket(name = "UV Scale", in_out='INPUT', socket_type = 'NodeSocketFloat')
			uv_scale_socket_1.default_value = 3.499999761581421
			uv_scale_socket_1.min_value = -10000.0
			uv_scale_socket_1.max_value = 10000.0
			uv_scale_socket_1.subtype = 'NONE'
			uv_scale_socket_1.attribute_domain = 'POINT'
			
			#Socket Material
			material_socket_1 = procedural_chain.interface.new_socket(name = "Material", in_out='INPUT', socket_type = 'NodeSocketMaterial')
			material_socket_1.attribute_domain = 'POINT'
			
			#Socket Surface
			surface_socket_1 = procedural_chain.interface.new_socket(name = "Surface", in_out='INPUT', socket_type = 'NodeSocketObject')
			surface_socket_1.attribute_domain = 'POINT'
			
			#Socket Attach to Surface
			attach_to_surface_socket_2 = procedural_chain.interface.new_socket(name = "Attach to Surface", in_out='INPUT', socket_type = 'NodeSocketBool')
			attach_to_surface_socket_2.default_value = False
			attach_to_surface_socket_2.attribute_domain = 'POINT'
			
			#Socket Project on Surface
			project_on_surface_socket = procedural_chain.interface.new_socket(name = "Project on Surface", in_out='INPUT', socket_type = 'NodeSocketFloat')
			project_on_surface_socket.default_value = 2.0
			project_on_surface_socket.min_value = 0.0
			project_on_surface_socket.max_value = 10000.0
			project_on_surface_socket.subtype = 'NONE'
			project_on_surface_socket.attribute_domain = 'POINT'
			
			#Socket Resolution
			resolution_socket = procedural_chain.interface.new_socket(name = "Resolution", in_out='INPUT', socket_type = 'NodeSocketInt')
			resolution_socket.default_value = 8
			resolution_socket.min_value = 0
			resolution_socket.max_value = 1000
			resolution_socket.subtype = 'NONE'
			resolution_socket.attribute_domain = 'POINT'
			
			#Socket Subdivision
			subdivision_socket = procedural_chain.interface.new_socket(name = "Subdivision", in_out='INPUT', socket_type = 'NodeSocketInt')
			subdivision_socket.default_value = 16
			subdivision_socket.min_value = 1
			subdivision_socket.max_value = 1000
			subdivision_socket.subtype = 'NONE'
			subdivision_socket.attribute_domain = 'POINT'
			
			#Socket Convert Instances
			convert_instances_socket = procedural_chain.interface.new_socket(name = "Convert Instances", in_out='INPUT', socket_type = 'NodeSocketBool')
			convert_instances_socket.default_value = False
			convert_instances_socket.attribute_domain = 'POINT'
			
			#Socket Chain Collection
			chain_collection_socket = procedural_chain.interface.new_socket(name = "Chain Collection", in_out='INPUT', socket_type = 'NodeSocketCollection')
			chain_collection_socket.attribute_domain = 'POINT'
			
			#Socket Use Custom Chain Collection
			use_custom_chain_collection_socket = procedural_chain.interface.new_socket(name = "Use Custom Chain Collection", in_out='INPUT', socket_type = 'NodeSocketBool')
			use_custom_chain_collection_socket.default_value = False
			use_custom_chain_collection_socket.attribute_domain = 'POINT'
			
			#Socket Custom Chain Scale
			custom_chain_scale_socket = procedural_chain.interface.new_socket(name = "Custom Chain Scale", in_out='INPUT', socket_type = 'NodeSocketFloat')
			custom_chain_scale_socket.default_value = 0.10000002384185791
			custom_chain_scale_socket.min_value = -10000.0
			custom_chain_scale_socket.max_value = 10000.0
			custom_chain_scale_socket.subtype = 'NONE'
			custom_chain_scale_socket.attribute_domain = 'POINT'
			
			#Socket Output Chain Instance
			output_chain_instance_socket = procedural_chain.interface.new_socket(name = "Output Chain Instance", in_out='INPUT', socket_type = 'NodeSocketBool')
			output_chain_instance_socket.default_value = False
			output_chain_instance_socket.attribute_domain = 'POINT'
			
			
			#initialize procedural_chain nodes
			#node Group.001
			group_001 = procedural_chain.nodes.new("GeometryNodeGroup")
			group_001.name = "Group.001"
			group_001.node_tree = chain
			#Input_9
			group_001.inputs[8].default_value = "ChainUV"
			#Input_10
			group_001.inputs[9].default_value = "Edges"
			
			#node Realize Instances
			realize_instances = procedural_chain.nodes.new("GeometryNodeRealizeInstances")
			realize_instances.name = "Realize Instances"
			#Selection
			realize_instances.inputs[1].default_value = True
			#Realize All
			realize_instances.inputs[2].default_value = True
			#Depth
			realize_instances.inputs[3].default_value = 0
			
			#node Switch.001
			switch_001 = procedural_chain.nodes.new("GeometryNodeSwitch")
			switch_001.name = "Switch.001"
			switch_001.input_type = 'GEOMETRY'
			
			#node Collection Info
			collection_info = procedural_chain.nodes.new("GeometryNodeCollectionInfo")
			collection_info.name = "Collection Info"
			collection_info.transform_space = 'RELATIVE'
			#Separate Children
			collection_info.inputs[1].default_value = True
			#Reset Children
			collection_info.inputs[2].default_value = False
			
			#node Switch.002
			switch_002 = procedural_chain.nodes.new("GeometryNodeSwitch")
			switch_002.name = "Switch.002"
			switch_002.input_type = 'GEOMETRY'
			
			#node Transform Geometry
			transform_geometry_1 = procedural_chain.nodes.new("GeometryNodeTransform")
			transform_geometry_1.name = "Transform Geometry"
			transform_geometry_1.mode = 'COMPONENTS'
			#Translation
			transform_geometry_1.inputs[1].default_value = (0.0, 0.0, 0.0)
			#Rotation
			transform_geometry_1.inputs[2].default_value = (0.0, 0.0, 0.0)
			
			#node Vector Math
			vector_math_2 = procedural_chain.nodes.new("ShaderNodeVectorMath")
			vector_math_2.name = "Vector Math"
			vector_math_2.operation = 'SCALE'
			#Vector
			vector_math_2.inputs[0].default_value = (1.0, 1.0, 1.0)
			
			#node Math
			math_4 = procedural_chain.nodes.new("ShaderNodeMath")
			math_4.name = "Math"
			math_4.operation = 'MULTIPLY'
			math_4.use_clamp = False
			
			#node Group Input
			group_input_4 = procedural_chain.nodes.new("NodeGroupInput")
			group_input_4.name = "Group Input"
			
			#node Group Output
			group_output_4 = procedural_chain.nodes.new("NodeGroupOutput")
			group_output_4.name = "Group Output"
			group_output_4.is_active_output = True
			
			#node Switch.003
			switch_003 = procedural_chain.nodes.new("GeometryNodeSwitch")
			switch_003.name = "Switch.003"
			switch_003.input_type = 'GEOMETRY'
			
			#node Switch
			switch_1 = procedural_chain.nodes.new("GeometryNodeSwitch")
			switch_1.name = "Switch"
			switch_1.input_type = 'GEOMETRY'
			
			#node Group
			group_2 = procedural_chain.nodes.new("GeometryNodeGroup")
			group_2.name = "Group"
			group_2.node_tree = curveinstancer
			
			
			
			
			#Set locations
			group_001.location = (78.72453308105469, 23.800968170166016)
			realize_instances.location = (1222.0294189453125, -78.9502944946289)
			switch_001.location = (1053.0616455078125, -169.97579956054688)
			collection_info.location = (83.73515319824219, 179.4037322998047)
			switch_002.location = (546.5451049804688, 56.159637451171875)
			transform_geometry_1.location = (299.746337890625, 182.1358642578125)
			vector_math_2.location = (77.32620239257812, 374.1398620605469)
			math_4.location = (-204.0821533203125, -64.09663391113281)
			group_input_4.location = (-545.9957885742188, -6.038071155548096)
			group_output_4.location = (1875.150634765625, 47.69766616821289)
			switch_003.location = (1693.4686279296875, -13.338691711425781)
			switch_1.location = (1465.905029296875, 113.3572769165039)
			group_2.location = (806.3787841796875, -27.913101196289062)
			
			#Set dimensions
			group_001.width, group_001.height = 140.0, 100.0
			realize_instances.width, realize_instances.height = 140.0, 100.0
			switch_001.width, switch_001.height = 140.0, 100.0
			collection_info.width, collection_info.height = 135.53060913085938, 100.0
			switch_002.width, switch_002.height = 140.0, 100.0
			transform_geometry_1.width, transform_geometry_1.height = 140.0, 100.0
			vector_math_2.width, vector_math_2.height = 140.0, 100.0
			math_4.width, math_4.height = 140.0, 100.0
			group_input_4.width, group_input_4.height = 140.0, 100.0
			group_output_4.width, group_output_4.height = 140.0, 100.0
			switch_003.width, switch_003.height = 140.0, 100.0
			switch_1.width, switch_1.height = 140.0, 100.0
			group_2.width, group_2.height = 140.0, 100.0
			
			#initialize procedural_chain links
			#group_input_4.Scale -> group_2.Length
			procedural_chain.links.new(group_input_4.outputs[1], group_2.inputs[1])
			#group_input_4.Scale -> group_001.Scale
			procedural_chain.links.new(group_input_4.outputs[1], group_001.inputs[0])
			#group_input_4.Radius -> group_001.Radius
			procedural_chain.links.new(group_input_4.outputs[3], group_001.inputs[2])
			#group_input_4.Width -> group_001.Width
			procedural_chain.links.new(group_input_4.outputs[2], group_001.inputs[1])
			#group_input_4.Material -> group_001.Material
			procedural_chain.links.new(group_input_4.outputs[14], group_001.inputs[3])
			#group_input_4.ChainSides -> group_001.ChainSides
			procedural_chain.links.new(group_input_4.outputs[6], group_001.inputs[4])
			#group_input_4.Roundness -> group_001.Roundness
			procedural_chain.links.new(group_input_4.outputs[7], group_001.inputs[5])
			#group_input_4.Bevel -> group_001.Bevel
			procedural_chain.links.new(group_input_4.outputs[8], group_001.inputs[6])
			#group_input_4.Tilt -> group_2.Value
			procedural_chain.links.new(group_input_4.outputs[10], group_2.inputs[3])
			#group_input_4.Twist -> group_001.Twist
			procedural_chain.links.new(group_input_4.outputs[4], group_001.inputs[7])
			#group_input_4.Geometry -> group_2.Curve
			procedural_chain.links.new(group_input_4.outputs[0], group_2.inputs[0])
			#group_input_4.Surface -> group_2.Surface
			procedural_chain.links.new(group_input_4.outputs[15], group_2.inputs[4])
			#group_input_4.Connect Distance -> group_2.Connect Distance
			procedural_chain.links.new(group_input_4.outputs[9], group_2.inputs[5])
			#group_input_4.Jump Rotation -> group_2.Angle
			procedural_chain.links.new(group_input_4.outputs[12], group_2.inputs[6])
			#group_input_4.Rotate -> group_2.Rotate
			procedural_chain.links.new(group_input_4.outputs[11], group_2.inputs[7])
			#group_input_4.Project on Surface -> group_2.Project
			procedural_chain.links.new(group_input_4.outputs[17], group_2.inputs[8])
			#group_input_4.UV Scale -> group_001.UV Scale
			procedural_chain.links.new(group_input_4.outputs[13], group_001.inputs[10])
			#group_input_4.Rotate Profile -> group_001.Rotate Profile
			procedural_chain.links.new(group_input_4.outputs[5], group_001.inputs[11])
			#group_input_4.Attach to Surface -> group_2.Attach to Surface
			procedural_chain.links.new(group_input_4.outputs[16], group_2.inputs[9])
			#group_input_4.Subdivision -> group_001.Resoulution
			procedural_chain.links.new(group_input_4.outputs[19], group_001.inputs[12])
			#realize_instances.Geometry -> switch_1.True
			procedural_chain.links.new(realize_instances.outputs[0], switch_1.inputs[2])
			#group_2.Instances -> switch_1.False
			procedural_chain.links.new(group_2.outputs[0], switch_1.inputs[1])
			#switch_001.Output -> realize_instances.Geometry
			procedural_chain.links.new(switch_001.outputs[0], realize_instances.inputs[0])
			#group_2.Instances -> switch_001.True
			procedural_chain.links.new(group_2.outputs[0], switch_001.inputs[2])
			#group_input_4.Convert Instances -> switch_001.Switch
			procedural_chain.links.new(group_input_4.outputs[20], switch_001.inputs[0])
			#group_input_4.Resolution -> group_001.Base Resolution
			procedural_chain.links.new(group_input_4.outputs[18], group_001.inputs[13])
			#group_001.Mesh -> switch_002.False
			procedural_chain.links.new(group_001.outputs[0], switch_002.inputs[1])
			#transform_geometry_1.Geometry -> switch_002.True
			procedural_chain.links.new(transform_geometry_1.outputs[0], switch_002.inputs[2])
			#group_input_4.Chain Collection -> collection_info.Collection
			procedural_chain.links.new(group_input_4.outputs[21], collection_info.inputs[0])
			#switch_002.Output -> group_2.Instance
			procedural_chain.links.new(switch_002.outputs[0], group_2.inputs[2])
			#group_input_4.Use Custom Chain Collection -> switch_002.Switch
			procedural_chain.links.new(group_input_4.outputs[22], switch_002.inputs[0])
			#collection_info.Instances -> transform_geometry_1.Geometry
			procedural_chain.links.new(collection_info.outputs[0], transform_geometry_1.inputs[0])
			#vector_math_2.Vector -> transform_geometry_1.Scale
			procedural_chain.links.new(vector_math_2.outputs[0], transform_geometry_1.inputs[3])
			#math_4.Value -> vector_math_2.Scale
			procedural_chain.links.new(math_4.outputs[0], vector_math_2.inputs[3])
			#group_input_4.Custom Chain Scale -> math_4.Value
			procedural_chain.links.new(group_input_4.outputs[23], math_4.inputs[0])
			#group_input_4.Scale -> math_4.Value
			procedural_chain.links.new(group_input_4.outputs[1], math_4.inputs[1])
			#group_input_4.Use Custom Chain Collection -> group_2.Pick Instance
			procedural_chain.links.new(group_input_4.outputs[22], group_2.inputs[10])
			#group_input_4.Convert Instances -> switch_1.Switch
			procedural_chain.links.new(group_input_4.outputs[20], switch_1.inputs[0])
			#group_001.Mesh -> switch_003.True
			procedural_chain.links.new(group_001.outputs[0], switch_003.inputs[2])
			#switch_1.Output -> switch_003.False
			procedural_chain.links.new(switch_1.outputs[0], switch_003.inputs[1])
			#switch_003.Output -> group_output_4.Geometry
			procedural_chain.links.new(switch_003.outputs[0], group_output_4.inputs[0])
			#group_input_4.Output Chain Instance -> switch_003.Switch
			procedural_chain.links.new(group_input_4.outputs[24], switch_003.inputs[0])
			return procedural_chain

		procedural_chain = procedural_chain_node_group()

		name = bpy.context.object.name
		obj = bpy.data.objects[name]
		mod = obj.modifiers.new(name = "Procedural Chain", type = 'NODES')
		mod.node_group = procedural_chain
		return {'FINISHED'}

def menu_func(self, context):
	self.layout.operator(Procedural_Chain.bl_idname)
			
def register():
	bpy.utils.register_class(Procedural_Chain)
	bpy.types.VIEW3D_MT_object.append(menu_func)
			
def unregister():
	bpy.utils.unregister_class(Procedural_Chain)
	bpy.types.VIEW3D_MT_object.remove(menu_func)
			
if __name__ == "__main__":
	register()
