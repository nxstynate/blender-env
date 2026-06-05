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

from abc import ABC, abstractmethod
from enum import Flag, StrEnum, auto
from typing import Optional

import bpy


class MenuCategory(StrEnum):
    EMITTER = "Emitter"
    OBJECTS = "Objects"
    SIMULATION = "Simulation"
    GENERATORS = "Generators"
    LOGIC = "Logic"
    PARTICLE = "Particle"
    FORCE = "Force"
    UTILITY = "Utility"


class UIFlags(Flag):
    NONE = 0
    RESET_BUTTON = auto()
    VISIBLE_IN_EDITOR = auto()
    HELP_BUTTON = auto()


class NexusObject(ABC):
    object_type: str = "NX_BASE"
    object_name: str = "NeXus Object"  # Internal name (e.g., "nxGravity")
    object_label: str = "Object"  # Display label (e.g., "Gravity Modifier")
    object_description: str = "Base NeXus object"
    icon_name: str = ""
    ui_flags: UIFlags = UIFlags.NONE
    category: str = "General"
    menu_category: MenuCategory = MenuCategory.FORCE
    gizmo_config: dict = None
    default_location: tuple[float, float, float] = (0.0, 0.0, 0.0)
    cache_specs: tuple = ()
    handles_own_sync: bool = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if getattr(cls, "cache_specs", ()):
            from ..libs.cache_spec import install_cache_hooks

            install_cache_hooks(cls)

    @classmethod
    def get_icon_id(cls) -> int:
        from ..icons import get_icon

        if cls.icon_name:
            return get_icon(cls.icon_name)
        return 0

    @classmethod
    def get_instance_icon_id(cls, obj: "bpy.types.Object") -> int:
        return cls.get_icon_id()

    @classmethod
    def get_theron_type(cls, obj: bpy.types.Object) -> Optional[str]:
        """Return the theron type string for this object.

        Default derives from object_type: NX_GRAVITY -> TR_MODIFIER_TYPE_GRAVITY.
        Override in subclasses that need dynamic type resolution (e.g. fluids).
        """
        suffix = cls.object_type.removeprefix("NX_")
        return f"TR_MODIFIER_TYPE_{suffix}"

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return []

    @classmethod
    def draw_ui(cls, layout, data) -> None:
        pass

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        pass

    @classmethod
    def get_tabs(cls, props) -> list[tuple[str, str]]:
        """Return extra tabs to draw in the UI as (section_id, label) pairs."""
        return []

    @classmethod
    def draw_tab(cls, section_id: str, layout, props) -> None:
        pass

    @classmethod
    def should_show_display_section(cls, props) -> bool:
        return True

    @classmethod
    def get_gradient_specs(cls):
        return []

    @classmethod
    def get_curve_specs(cls):
        return []

    @classmethod
    def on_create(cls, obj: bpy.types.Object) -> None:
        pass

    @classmethod
    def post_sync(
        cls,
        obj: bpy.types.Object,
        container: int,
        handle: int,
        props,
        scene: bpy.types.Scene,
        depsgraph: bpy.types.Depsgraph | None = None,
        original_props=None,
    ) -> None:
        pass

    @classmethod
    def post_execute_pipeline(
        cls,
        obj: bpy.types.Object,
        pipeline_handle: int,
        props,
        scene: bpy.types.Scene,
        *,
        depsgraph: bpy.types.Depsgraph | None = None,
    ) -> None:
        """Override on modifiers with ``handles_own_sync=True`` that need a post-frame hook.

        ``pipeline_handle`` is the Theron modifier pipeline."""
        pass

    @classmethod
    def post_execute_object(
        cls,
        obj: bpy.types.Object,
        handle: int,
        props,
        scene: bpy.types.Scene,
        *,
        depsgraph: bpy.types.Depsgraph | None = None,
    ) -> None:
        """Override on standard per-object modifiers that need a post-frame hook.

        ``handle`` is the per-object Theron handle."""
        pass

    @classmethod
    def on_reset(cls, obj: bpy.types.Object, props) -> None:
        pass

    @classmethod
    def sync_to_pipeline(
        cls,
        obj: bpy.types.Object,
        scene: bpy.types.Scene,
        *,
        pipeline_handle: int,
        disabled: bool,
        depsgraph: bpy.types.Depsgraph | None = None,
    ) -> None:
        """Override when handles_own_sync=True."""
        pass

    @classmethod
    def on_disable(cls, obj: bpy.types.Object, props) -> None:
        """Called when a modifier's ``enabled`` flag transitions True->False.

        Cascade-disabled descendants also fire this. Override to hide or clear
        owned overlays/child objects that would otherwise survive because
        post-execute hooks skip disabled modifiers."""
        pass

    @classmethod
    def on_destroy(cls, mod_uid: str) -> None:
        """Called when a modifier object is deleted. Receives the deleted
        object's persistent ``_nexus_object_uid``. Override for per-object
        cache cleanup keyed by UID."""
        pass

    @classmethod
    def on_state_clear(cls, *, free_resources: bool = True) -> None:
        """Called during state clear. free_resources=True when C library is loaded (free handles).
        free_resources=False on file load (handles are dangling, just clear Python state)."""
        pass

    @classmethod
    def on_pipeline_destroy(cls, pipeline_handle: int, *, free_resources: bool = True) -> None:
        pass

    @classmethod
    def create_object(cls, context, name: Optional[str] = None) -> bpy.types.Object:
        obj_name = name or cls.object_name

        bpy.ops.object.empty_add(type="PLAIN_AXES", location=cls.default_location)
        obj = context.active_object
        obj.name = obj_name

        obj.empty_display_size = 0
        obj["nexus_modifier_type"] = cls.object_type

        from ..pipeline_manager.identity import ensure_object_uid

        ensure_object_uid(obj)

        cls._apply_preview_icon(obj)
        cls.on_create(obj)

        from ..libs.modifier_spec import get_modifier_spec

        spec = get_modifier_spec(cls.object_type)
        if spec and spec.enum_defaults:
            props = obj.nexus_modifier
            for prop_name, value in spec.enum_defaults.items():
                try:
                    setattr(props, prop_name, value)
                except Exception:
                    pass

        from ..libs.nexus_rate import convert_object_rate_defaults
        from ..libs.nexus_time import convert_object_time_defaults

        fps = context.scene.render.fps / max(context.scene.render.fps_base, 1e-6)
        convert_object_time_defaults(obj, fps)
        convert_object_rate_defaults(obj)

        gradient_specs = cls.get_gradient_specs()
        if gradient_specs:
            from ..utils.gradient import create_gradient_nodes

            create_gradient_nodes(obj, gradient_specs)

        curve_specs = cls.get_curve_specs()
        if curve_specs:
            from ..utils.curve import create_curve_nodes

            create_curve_nodes(obj, curve_specs)

        return obj

    @classmethod
    def is_modifier_object(cls, obj: bpy.types.Object) -> bool:
        return obj.get("nexus_modifier_type") == cls.object_type

    @classmethod
    def draw_property(cls, layout, data, prop_name: str, ui_config: dict = None):
        config = (ui_config or {}).get(prop_name, {})

        if config.get("type") == "nodetree":
            from ..ui import draw_nodetree

            draw_nodetree(
                layout,
                data,
                prop_name,
                config["index_prop"],
                label=config.get("label", "Objects"),
                draw_item_settings=config.get("draw_item_settings"),
                menu_id=config.get("menu_id"),
                show_quick_add=config.get("show_quick_add"),
                allowed_types=config.get("allowed_types"),
                allow_duplicates=config.get("allow_duplicates", False),
                per_item_toggles=config.get("per_item_toggles"),
            )
        else:
            use_split = config.get("use_property_split", True)
            col = layout.column()
            col.use_property_split = use_split
            col.prop(data, prop_name)

    @classmethod
    def _apply_preview_icon(cls, obj: bpy.types.Object) -> bool:
        if not cls.icon_name:
            return False

        from ..icons import get_icon_path

        icon_path = get_icon_path(cls.icon_name)

        if not icon_path:
            return False

        try:
            obj.preview_ensure()
            img = bpy.data.images.load(icon_path, check_existing=True)

            if img and obj.preview:
                obj.preview.image_size = (32, 32)
                img.scale(32, 32)

                if len(img.pixels) >= 32 * 32 * 4:
                    obj.preview.image_pixels_float = img.pixels[:]

                if img.users == 0:
                    bpy.data.images.remove(img)

                return True
        except Exception:
            pass

        return False


class NexusModifier(NexusObject):
    # If true, execute is called on any param change, not just frame advance
    always_execute: bool = False

    @classmethod
    @abstractmethod
    def get_modifier_properties(cls) -> list[str]:
        pass

    @classmethod
    @abstractmethod
    def draw_ui(cls, layout, data):
        pass

    @classmethod
    @abstractmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        pass
