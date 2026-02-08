import bpy
from .lib import *
def create_nodetree_from_serialized(tree, ser_nodes,loc):
    t_nodes = tree.nodes
    t_links = tree.links
    first_node_loc_delta = None
    new_nodes = {}
    delta = 20
    for node in ser_nodes:
        n, l, t, inputs, outputs, props = ser_nodes[node].values()
        new_node = t_nodes.new(type=t)
        new_node.location = [math.floor((l[0])/delta)*delta,math.floor((l[1])/delta)*delta]
        new_node.name = n
        new_node.select = False
        if not first_node_loc_delta and loc:
            loc = Vector(loc)
            first_node_loc_delta = loc - new_node.location
        if loc:
            new_node.location += first_node_loc_delta
        new_node.select = bool(loc)
        for prop in props:
            for k, v in prop.items():
                if k == 'object':
                    if v in bpy.data.objects:
                        new_node.object = bpy.data.objects[v]
                elif k == 'image':
                    if v in bpy.data.images:
                        new_node.image = bpy.data.images[v]
                elif GV.after4 and k == 'width_hidden':
                    pass
                else: setattr(new_node, k, v)
        if inputs:
            for socket in inputs:
                try:
                    if socket[1]: new_node.inputs[socket[0]].default_value = socket[1]
                except Exception as e:
                    pass
        if outputs:
            for socket in outputs:
                try:
                    if socket[1]: new_node.outputs[socket[0]].default_value = socket[1]
                except Exception as e:
                    pass
        new_nodes[node] = new_node
    for node in ser_nodes:
        n, l, t, inputs, outputs, props = ser_nodes[node].values()
        if inputs:
            for socket in inputs:
                if len(socket) == 3:
                    for input_node in socket[2]:
                        if input_node[1] in new_nodes:
                            try:
                                t_links.new(new_nodes[input_node[1]].outputs[input_node[0]], new_nodes[node].inputs[socket[0]])
                            except Exception as e:
                                pass
class CBL_OT_DeserializeNode(bpy.types.Operator):
    """"""
    bl_idname = "cbl.deserialize_node"
    bl_label = "Cablerator: Deserialize Nodes"
    bl_options = {"INTERNAL"}
    def execute(self, context):
        loc = None
        if hasattr(bpy, 'temp_string_serializer'):
            loc, tree, string = bpy.temp_string_serializer
            del bpy.temp_string_serializer
        else:
            string = context.window_manager.clipboard
        serialized_nodes = json.loads(string)
        create_nodetree_from_serialized(tree, serialized_nodes, loc)
        return {'FINISHED'}
def register():
    bpy.utils.register_class(CBL_OT_DeserializeNode)
def unregister():
    bpy.utils.unregister_class(CBL_OT_DeserializeNode)