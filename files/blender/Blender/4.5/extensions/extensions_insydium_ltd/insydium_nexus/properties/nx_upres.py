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
from bpy.props import (
    BoolProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
)

from ..libs.modifier_spec import (
    ENABLED_DESCRIPTOR,
    ModifierPropertySpec,
    PropertyDescriptor,
)
from ..libs.nodetree_sync import NodeTreeSyncSpec
from ..libs.theron_sync import Transform
from ..ui import NodeTreeDef, make_allowed_types_poll


class NexusUpresEmitterItem(bpy.types.PropertyGroup):
    obj: PointerProperty(
        name="Object", type=bpy.types.Object, poll=make_allowed_types_poll(["NX_EMITTER"])
    )
    enabled: BoolProperty(name="Enabled", default=True)

    def get_list_icon(self):
        if self.obj and self.obj.preview:
            return self.obj.preview.icon_id
        return 0


_UPRES_SOURCE = NodeTreeDef(
    "Source", item_type=NexusUpresEmitterItem, allowed_types=["NX_EMITTER"]
)
_UPRES_DEST = NodeTreeDef(
    "Destination", item_type=NexusUpresEmitterItem, allowed_types=["NX_EMITTER"]
)


NX_UPRES_UI_CONFIG = {
    **_UPRES_SOURCE.ui_config("upres_source"),
    **_UPRES_DEST.ui_config("upres_dest"),
}


def get_upres_ui_config():
    return NX_UPRES_UI_CONFIG


def _resolve_emitter_link(theron, item, _obj, scene, _depsgraph):
    from ..handlers.pipeline import get_nexus_obj_handle

    if item.obj is None:
        return None
    return get_nexus_obj_handle(scene, item.obj)


_UPRES_SOURCE_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_UPRES_SOURCE_EMITTER",
    collection_attr="upres_source",
    sequential_node_id=True,
    node_link_resolver=_resolve_emitter_link,
    skip_if_no_link=True,
)

_UPRES_DEST_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_UPRES_DEST_EMITTER",
    collection_attr="upres_dest",
    sequential_node_id=True,
    node_link_resolver=_resolve_emitter_link,
    skip_if_no_link=True,
)


SPEC = ModifierPropertySpec(
    modifier_type="NX_UPRES",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_UPRES_STRENGTH",
            prop=FloatProperty(
                name="Strength",
                description="Overall upres strength",
                default=100.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_UPRES_POSITION",
            prop=FloatProperty(
                name="Position",
                description="Position variation for upres particles",
                default=0.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_UPRES_VELOCITY",
            prop=FloatProperty(
                name="Velocity",
                description="Velocity variation for upres particles",
                default=100.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_UPRES_RADIUS",
            prop=FloatProperty(
                name="Radius",
                description="Radius variation for upres particles",
                default=0.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_UPRES_MASS",
            prop=FloatProperty(
                name="Mass",
                description="Mass variation for upres particles",
                default=0.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_UPRES_COLOR",
            prop=FloatProperty(
                name="Color",
                description="Color variation for upres particles",
                default=0.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_UPRES_GROUP",
            prop=BoolProperty(
                name="Group",
                description="Group upres particles",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_UPRES_MAX_NB",
            prop=IntProperty(
                name="Max Count",
                description="Maximum number of upres particles per source particle",
                default=3,
                min=1,
                max=64,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_UPRES_LIMIT_DIST",
            prop=BoolProperty(
                name="Limit Distance",
                description="Limit the distance of upres particles from source",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_UPRES_MAX_DIST",
            prop=FloatProperty(
                name="Max Distance",
                description="Maximum distance from source particle",
                default=2.0,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_UPRES_PUSH",
            prop=BoolProperty(
                name="Push",
                description="Push upres particles apart",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_UPRES_PUSH_DISTANCE",
            prop=FloatProperty(
                name="Push Distance",
                description="Distance to push upres particles apart",
                default=200.0,
                min=0.0,
                soft_max=400.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        *(
            PropertyDescriptor(name=n, prop=p, preset=False, reset=True, snapshot=True)
            for n, p in _UPRES_SOURCE.properties("upres_source").items()
        ),
        *(
            PropertyDescriptor(name=n, prop=p, preset=False, reset=True, snapshot=True)
            for n, p in _UPRES_DEST.properties("upres_dest").items()
        ),
    ),
    item_classes=(NexusUpresEmitterItem,),
    nodetree_sync=(_UPRES_SOURCE_TREE_SPEC, _UPRES_DEST_TREE_SPEC),
)


# `upres_source` / `upres_dest`: pure scene-link lists; not portable preset data.
