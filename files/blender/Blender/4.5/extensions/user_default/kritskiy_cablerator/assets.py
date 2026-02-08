from select import select
import bpy
import os
from .lib import *
from .ui import *
def run_cbl_ops(context, objs, optype):
    super_select(objs, context, deselect=False)
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if isinstance(space, bpy.types.SpaceView3D):
                    if GV.after4:
                        with context.temp_override(area=area, region=next(iter(region for region in area.regions if region.type == 'WINDOW'), None)):
                            if optype == 'geo':
                                bpy.ops.object.cablerator_geocable('INVOKE_DEFAULT')
                            elif optype == 'segment':
                                bpy.ops.object.cablerator_segment('INVOKE_DEFAULT')
                            elif optype == 'connector':
                                switch_mode('EDIT')
                                bpy.ops.object.cablerator_connector('INVOKE_DEFAULT')
                    else:
                        ctx = bpy.context.copy()
                        ctx['area'] = area
                        if optype == 'geo':
                            bpy.ops.object.cablerator_geocable(ctx, 'INVOKE_DEFAULT')
                        elif optype == 'segment':
                            bpy.ops.object.cablerator_segment(ctx, 'INVOKE_DEFAULT')
                        elif optype == 'connector':
                            switch_mode('EDIT')
                            bpy.ops.object.cablerator_connector(ctx, 'INVOKE_DEFAULT')
                    return
def asset_poll_condition(context):
    if not context.active_object: return False
    condition = bool(hasattr(context, 'active_file') and 'Object' in str(context.active_file.relative_path))
    return context.active_object.type == 'CURVE' and condition
def asset_import_to_scene(self, context):
    for ob in bpy.data.objects:
        ob.select_set(False)
    af = context.active_file
    print_attr(af)
    dir = context.space_data.params.directory.decode("utf-8")
    path = os.path.normpath(af.relative_path)
    path.split(os.sep)
    split_path = path.split(os.sep)
    file_name = split_path[0]
    path_to_ob = split_path[1:]
    if dir:
        path_to_blend = os.path.join(dir, file_name)
    else:
        wm = context.window_manager
        path_to_blend = wm.asset_path_dummy
    if len(path_to_blend.split(os.sep)) > 1:
        path = os.path.normpath(af.relative_path)
        path.split(os.sep)
        split_path = path.split(os.sep)
        file_name = split_path[0]
        path_to_ob = split_path[1:]
        with bpy.data.libraries.load(path_to_blend) as (data_from, data_to):
            data_to.objects = [name for name in data_from.objects if name == path_to_ob[-1]]
        context.scene.collection.objects.link(data_to.objects[0])
        data_to.objects[0].select_set(True)
    elif af.local_id:
        clone = duplicate_object(af.local_id, True)
        clone.select_set(True)
    else:
        print_attr(af)
        self.report({'ERROR'}, "Unknown condition met in the asset_import_to_scene, please check the system console")
        return {'CANCELLED'}
class CBL_OT_AddAssetGeo(bpy.types.Operator):
    bl_idname = "cbl.add_asset_geo"
    bl_label = "Cablerator: Add the asset as a Mesh Cable"
    @classmethod
    def poll(cls, context):
        return asset_poll_condition(context)
    def execute(self, context):
        self.objs = [ob for ob in context.selected_objects if ob.type == 'CURVE']
        if not self.objs:
            self.report(
                {'ERROR'},
                "No valid curve objects were found among the selected objects, Aborting",
            )
            return {'CANCELLED'}
        asset_import_to_scene(self, context)
        run_cbl_ops(context, self.objs, 'geo')
        return {'FINISHED'}
class CBL_OT_AddAssetSegment(bpy.types.Operator):
    bl_idname = "cbl.add_asset_segment"
    bl_label = "Cablerator: Add the asset as a Segment"
    @classmethod
    def poll(cls, context):
        return asset_poll_condition(context)
    def execute(self, context):
        self.objs = [ob for ob in context.selected_objects if ob.type == 'CURVE']
        if not self.objs:
            self.report(
                {'ERROR'},
                "No valid curve objects were found among the selected objects, Aborting",
            )
            return {'CANCELLED'}
        asset_import_to_scene(self, context)
        run_cbl_ops(context, self.objs, 'segment')
        return {'FINISHED'}
class CBL_OT_AddAssetConnector(bpy.types.Operator):
    bl_idname = "cbl.add_asset_connector"
    bl_label = "Cablerator: Add the asset as a Connector"
    @classmethod
    def poll(cls, context):
        return asset_poll_condition(context)
    def execute(self, context):
        self.objs = [ob for ob in context.selected_objects if ob.type == 'CURVE']
        if not self.objs:
            self.report(
                {'ERROR'},
                "No valid curve objects were found among the selected objects, Aborting",
            )
            return {'CANCELLED'}
        asset_import_to_scene(self, context)
        run_cbl_ops(context, self.objs, 'connector')
        return {'FINISHED'}
def cablerator_asset_menu(self, context):
    self.layout.separator()
    self.layout.operator(CBL_OT_AddAssetConnector.bl_idname, text=CBL_OT_AddAssetConnector.bl_label)
    self.layout.operator(CBL_OT_AddAssetSegment.bl_idname, text=CBL_OT_AddAssetSegment.bl_label)
    self.layout.operator(CBL_OT_AddAssetGeo.bl_idname, text=CBL_OT_AddAssetGeo.bl_label)
def register():
    if bpy.app.version >= (3, 0, 0):
        bpy.utils.register_class(CBL_OT_AddAssetGeo)
        bpy.utils.register_class(CBL_OT_AddAssetSegment)
        bpy.utils.register_class(CBL_OT_AddAssetConnector)
        bpy.types.ASSETBROWSER_MT_context_menu.append(cablerator_asset_menu)
def unregister():
    if bpy.app.version >= (3, 0, 0):
        bpy.utils.unregister_class(CBL_OT_AddAssetGeo)
        bpy.utils.unregister_class(CBL_OT_AddAssetSegment)
        bpy.utils.unregister_class(CBL_OT_AddAssetConnector)
        bpy.types.ASSETBROWSER_MT_context_menu.remove(cablerator_asset_menu)
