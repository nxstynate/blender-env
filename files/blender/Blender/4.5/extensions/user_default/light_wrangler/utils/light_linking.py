import bpy
from mathutils import Vector
from bpy_extras import view3d_utils
from .blender_compat import supports_light_linking


def is_blender_version_compatible():
    """Check if current Blender version supports light linking features."""
    return bpy.app.version >= (4, 0, 0)


def save_linking_state(light):
    """Save the current light linking state for potential reversion."""
    if not supports_light_linking(bpy.context.scene.render.engine):
        return None

    state = {
        'blocker_collection': light.light_linking.blocker_collection,
        'receiver_collection': light.light_linking.receiver_collection,
        'objects': {}
    }
    for collection_type in ('blocker_collection', 'receiver_collection'):
        collection = getattr(light.light_linking, collection_type)
        if collection:
            state[collection_type + '_name'] = collection.name
            for linked_obj in collection.objects:
                state['objects'][linked_obj.name] = {
                    'light_linking_state': linked_obj.get('light_linking_state', None),
                    'collection_type': collection_type
                }
    return state

def revert_linking_state(context, light, original_state):
    """Revert light linking to a previously saved state."""
    if not supports_light_linking(bpy.context.scene.render.engine) or not original_state:
        return

    if not light or light.type != 'LIGHT':
        return

    # Clear current collections
    for collection_type in ('blocker_collection', 'receiver_collection'):
        current_collection = getattr(light.light_linking, collection_type)
        if current_collection:
            for obj in list(current_collection.objects):
                current_collection.objects.unlink(obj)
                if 'light_linking_state' in obj:
                    del obj['light_linking_state']

            # Check if the collection was created during this operation
            if collection_type + '_name' not in original_state:
                # Check if the collection is used by any other lights
                is_unused = True
                for obj in bpy.data.objects:
                    if obj.type == 'LIGHT' and obj != light:
                        if (collection_type == 'blocker_collection' and obj.light_linking.blocker_collection == current_collection) or \
                        (collection_type == 'receiver_collection' and obj.light_linking.receiver_collection == current_collection):
                            is_unused = False
                            break

                if is_unused:
                    cleanup_unused_collection(context, current_collection)
                    if collection_type == 'blocker_collection':
                        light.light_linking.blocker_collection = None
                    else:
                        light.light_linking.receiver_collection = None

            setattr(light.light_linking, collection_type, None)

    # Restore original state
    restore_collections_and_objects(context, light, original_state)

def ensure_light_linking_collection(context, light, is_blocker):
    """Ensure the appropriate light linking collection exists."""
    if not supports_light_linking(bpy.context.scene.render.engine):
        return

    if is_blocker:
        if not light.light_linking.blocker_collection:
            bpy.ops.object.light_linking_blocker_collection_new()
    else:
        if not light.light_linking.receiver_collection:
            bpy.ops.object.light_linking_receiver_collection_new()

def cleanup_unused_collection(context, collection):
    """Remove an unused collection from all scenes and viewlayers."""
    for scene in bpy.data.scenes:
        if collection.name in scene.collection.children:
            scene.collection.children.unlink(collection)
        for layer in scene.view_layers:
            if collection.name in layer.layer_collection.children:
                layer.layer_collection.children.unlink(collection)
    
    bpy.data.collections.remove(collection, do_unlink=True)
    bpy.data.orphans_purge(do_recursive=True)

def restore_collections_and_objects(context, light, original_state):
    """Restore collections and object states from saved state."""
    for collection_type in ('blocker_collection', 'receiver_collection'):
        collection_name = original_state.get(collection_type + '_name')
        if collection_name:
            collection = bpy.data.collections.get(collection_name)
            if not collection:
                collection = bpy.data.collections.new(collection_name)
                context.scene.collection.children.link(collection)
            setattr(light.light_linking, collection_type, collection)

    for obj_name, obj_data in original_state['objects'].items():
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            continue
        if obj_data['light_linking_state']:
            obj['light_linking_state'] = obj_data['light_linking_state']
        elif 'light_linking_state' in obj:
            del obj['light_linking_state']

        collection = getattr(light.light_linking, obj_data['collection_type'])
        if collection and obj.name not in collection.objects:
            collection.objects.link(obj)

def get_object_under_cursor(context, event):
    """Perform ray-casting to find object under cursor."""
    region = context.region
    rv3d = context.region_data
    coord = event.mouse_region_x, event.mouse_region_y

    is_ortho_camera = (rv3d.view_perspective == 'CAMERA' and
                    context.scene.camera.data.type == 'ORTHO')

    # Determine clipping settings
    if rv3d.view_perspective == 'CAMERA':
        near_clip = context.scene.camera.data.clip_start
    else:
        space = context.space_data
        near_clip = space.clip_start if space.type == 'VIEW_3D' else 0.1

    # Get ray origin and direction
    if is_ortho_camera:
        camera_matrix = context.scene.camera.matrix_world
        camera_direction = camera_matrix.to_3x3() @ Vector((0, 0, -1))
        mouse_pos_3d = view3d_utils.region_2d_to_location_3d(region, rv3d, coord, camera_matrix.translation)
        ray_origin = mouse_pos_3d + camera_direction * near_clip
        ray_direction = camera_direction
    else:
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        ray_direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin += ray_direction * near_clip

    return context.scene.ray_cast(
        context.view_layer.depsgraph,
        ray_origin,
        ray_direction
    )

def handle_light_linking(context, event, light, is_blocker):
    """Handle light linking operations for an object under cursor."""
    if not supports_light_linking(context.scene.render.engine):
        return "Light linking is only available in Cycles or EEVEE render engines", 'WARNING'

    result, location, normal, index, object, matrix = get_object_under_cursor(context, event)

    if not (result and object and light):
        return "No object under mouse or no active light", 'WARNING'

    # Ensure the appropriate collection exists
    ensure_light_linking_collection(context, light, is_blocker)
    
    # Get the appropriate collection
    collection = light.light_linking.blocker_collection if is_blocker else light.light_linking.receiver_collection
    
    if not collection:
        return "Failed to create or get light linking collection", 'ERROR'

    # Process the light linking
    return process_light_linking(context, light, object, collection, is_blocker)

def process_light_linking(context, light, object, collection, is_blocker):
    """Process light linking state changes for an object."""
    if not collection:
        return "No valid collection for light linking", 'ERROR'
        
    if object.name not in collection.objects:
        return handle_new_link(context, light, object, collection, is_blocker)
    else:
        return handle_existing_link(context, light, object, collection, is_blocker)

def handle_new_link(context, light, object, collection, is_blocker):
    """Handle linking a new object to the collection."""
    is_first_object = len(collection.objects) == 0
    
    if is_blocker:
        bpy.ops.object.light_linking_blockers_link(link_state='INCLUDE')
        if is_first_object:
            status_message = f"{object.name} is now the only object that casts shadow from {light.name}"
        else:
            status_message = f"{object.name} now casts shadow from {light.name}"
    else:
        bpy.ops.object.light_linking_receivers_link(link_state='INCLUDE')
        if is_first_object:
            status_message = f"{object.name} is now the only object that receives light from {light.name}"
        else:
            status_message = f"{object.name} now receives light from {light.name}"
    
    object['light_linking_state'] = 'INCLUDE'
    return status_message, 'INFO'

def handle_existing_link(context, light, object, collection, is_blocker):
    """Handle changing or removing an existing link."""
    link_state = object.get('light_linking_state', 'INCLUDE')
    
    if link_state == 'INCLUDE':
        return toggle_include_to_exclude(context, light, object, collection, is_blocker)
    else:
        return remove_from_collection(context, light, object, collection, is_blocker)

def toggle_include_to_exclude(context, light, object, collection, is_blocker):
    """Toggle an object's state from included to excluded."""
    is_only_object = len(collection.objects) == 1
    
    if is_blocker:
        bpy.ops.object.light_linking_blockers_link(link_state='EXCLUDE')
        if is_only_object:
            status_message = f"{object.name}, the only blocker, no longer casts shadow from {light.name}"
        else:
            status_message = f"{object.name} no longer casts shadow from {light.name}"
    else:
        bpy.ops.object.light_linking_receivers_link(link_state='EXCLUDE')
        if is_only_object:
            status_message = f"{object.name}, the only receiver, now ignores light from {light.name}"
        else:
            status_message = f"{object.name} now ignores light from {light.name}"
    
    object['light_linking_state'] = 'EXCLUDE'
    return status_message, 'INFO'

def remove_from_collection(context, light, object, collection, is_blocker):
    """Remove an object from the light linking collection."""
    collection.objects.unlink(object)
    if is_blocker:
        status_message = f"{object.name} removed from shadow linking collection for {light.name}"
    else:
        status_message = f"{object.name} removed from light linking collection for {light.name}"

    if 'light_linking_state' in object:
        del object['light_linking_state']

    # Handle empty collection cleanup
    if len(collection.objects) == 0:
        handle_empty_collection(context, light, collection, is_blocker)

    return status_message, 'INFO'

def handle_empty_collection(context, light, collection, is_blocker):
    """Handle cleanup of empty collections."""
    is_unused = True
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT' and obj != light:
            if (is_blocker and obj.light_linking.blocker_collection == collection) or \
               (not is_blocker and obj.light_linking.receiver_collection == collection):
                is_unused = False
                break

    if is_unused:
        cleanup_unused_collection(context, collection)
        if is_blocker:
            light.light_linking.blocker_collection = None
        else:
            light.light_linking.receiver_collection = None

