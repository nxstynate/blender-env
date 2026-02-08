import bpy
from .blender_compat import world_has_nodes

def find_hdri_domes_and_mapping_nodes():
    mapping_nodes = []
    dome_objects = []
    
    active_world = bpy.context.scene.world
    if not active_world or not world_has_nodes(active_world):
        return mapping_nodes, dome_objects
    
    def is_node_connected_to_output(node, output_node, checked_nodes=None):
        if checked_nodes is None:
            checked_nodes = set()
        if node in checked_nodes:
            return False
        checked_nodes.add(node)
        
        for output in node.outputs:
            for link in output.links:
                if link.to_node == output_node:
                    return True
                if is_node_connected_to_output(link.to_node, output_node, checked_nodes):
                    return True
        return False

    def process_node_tree(node_tree):
        if not node_tree:
            return
            
        nodes = node_tree.nodes
        links = node_tree.links
        output_node = next((n for n in nodes if n.type == 'OUTPUT_WORLD'), None)
        if not output_node:
            return

        env_nodes = [n for n in nodes if n.type == 'TEX_ENVIRONMENT' 
                     and is_node_connected_to_output(n, output_node)]
        
        for env_node in env_nodes:
            vector_input = env_node.inputs['Vector']
            mapping_node = None
            
            if vector_input.is_linked:
                prev_node = vector_input.links[0].from_node
                if prev_node.type == 'MAPPING':
                    mapping_node = prev_node
                else:
                    mapping_node = nodes.new(type='ShaderNodeMapping')
                    mapping_node.name = f'Mapping_{env_node.name}'
                    mapping_node.location = (
                        (prev_node.location.x + env_node.location.x) / 2,
                        (prev_node.location.y + env_node.location.y) / 2
                    )
                    
                    existing_link = vector_input.links[0]
                    links.new(existing_link.from_socket, mapping_node.inputs['Vector'])
                    links.new(mapping_node.outputs['Vector'], vector_input)
            else:
                mapping_node = nodes.new(type='ShaderNodeMapping')
                mapping_node.name = f'Mapping_{env_node.name}'
                mapping_node.location = (env_node.location.x - 200, env_node.location.y)
                
                tex_coord_node = nodes.new(type='ShaderNodeTexCoord')
                tex_coord_node.name = f'TexCoord_{env_node.name}'
                tex_coord_node.location = (mapping_node.location.x - 200, mapping_node.location.y)
                
                links.new(tex_coord_node.outputs['Generated'], mapping_node.inputs['Vector'])
                links.new(mapping_node.outputs['Vector'], vector_input)
            
            if mapping_node and mapping_node not in mapping_nodes:
                mapping_nodes.append(mapping_node)

    process_node_tree(active_world.node_tree)

    for obj in bpy.context.scene.objects:
        if obj.hide_viewport or not obj.visible_get():
            continue
        for mat_slot in obj.material_slots:
            if mat_slot.material and mat_slot.material.use_nodes:
                mat_nodes = mat_slot.material.node_tree.nodes
                output_node = next((n for n in mat_nodes if n.type == 'OUTPUT_MATERIAL'), None)
                if output_node:
                    env_nodes = [n for n in mat_nodes if n.type == 'TEX_ENVIRONMENT' 
                                 and is_node_connected_to_output(n, output_node)]
                    if env_nodes:
                        dome_objects.append(obj)
                        break
    return mapping_nodes, dome_objects