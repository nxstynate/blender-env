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

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import html

from .api import STR_NO_PLAN
from .assets import (MapType)

from .logger import (DEBUG,  # noqa F401, allowing downstream const usage
                     ERROR,
                     INFO,
                     get_addon_logger,
                     NOT_SET,
                     WARNING)


class SubscriptionState(Enum):
    """Values for allowed user subscription states."""
    NOT_POPULATED = 0
    FREE = 1,
    ACTIVE = 2,
    PAUSED = 3,
    CANCELLED = 4


@dataclass
class MapFormats:
    map_type: MapType
    default: str
    required: bool
    extensions: Dict[str, bool]
    enabled: bool
    selected: Optional[str] = None


class UserDownloadPreferences:
    resolution_options: List[str]
    default_resolution: str
    selected_resolution: Optional[str] = None

    texture_maps: List[MapFormats]

    software_selected: Optional[str] = None
    render_engine_selected: Optional[str] = None

    lod_options: List[str]
    lod_selected: Optional[str] = None

    def __init__(self, res: Dict):
        self.res = res

        self.set_resolution()
        self.set_lods()
        self.set_software()
        self.set_texture_maps()

    def set_resolution(self) -> None:
        resolution_info = self.res.get("default_resolution", {})
        self.resolution_options = resolution_info.get("resolution_options")
        self.default_resolution = resolution_info.get("default")
        self.selected_resolution = resolution_info.get("selected")

    def set_lods(self) -> None:
        lods_info = self.res.get("lods", {})
        self.lod_options = lods_info.get("lod_options")
        self.lod_selected = lods_info.get("selected")

    def set_software(self) -> None:
        software_info = self.res.get("softwares", {})
        for _soft, soft_inf in software_info.items():
            soft_selected = soft_inf.get("selected", None)
            renderer_selected = soft_inf.get("selected_render_engine", None)
            if soft_selected is not None and renderer_selected is not None:
                self.software_selected = soft_selected
                self.render_engine_selected = renderer_selected
                break

    def set_texture_maps(self) -> None:
        self.texture_maps = []
        texture_maps_info = self.res.get("texture_maps", {})
        for _map, map_info in texture_maps_info.items():
            map_type = MapType.from_type_code(_map)
            enabled = map_info.get("selected") is not None
            map_format = MapFormats(map_type=map_type,
                                    default=map_info.get("default"),
                                    enabled=enabled,
                                    selected=map_info.get("selected"),
                                    required=map_info.get("required"),
                                    extensions=map_info.get("formats"))

            self.texture_maps.append(map_format)

    def string_stamp(self) -> str:
        string_stamp = ""
        for _map in self.texture_maps:
            string_stamp += f"{_map.map_type.name}:{str(_map.selected)};"
        return string_stamp

    def get_map_preferences(self, map_type: MapType) -> Optional[MapFormats]:
        for _map in self.texture_maps:
            if _map.map_type.get_effective() == map_type.get_effective():
                return _map
        return None

    def get_all_maps_enabled(self):
        return [_map for _map in self.texture_maps if _map.enabled]


@dataclass
class PoliigonSubscription:
    """Container object for a subscription."""

    plan_name: Optional[str] = None
    plan_credit: Optional[int] = None
    next_credit_renewal_date: Optional[datetime] = None
    current_term_end: Optional[datetime] = None
    next_subscription_renewal_date: Optional[datetime] = None
    plan_paused_at: Optional[datetime] = None
    plan_paused_until: Optional[datetime] = None
    subscription_state: Optional[SubscriptionState] = SubscriptionState.NOT_POPULATED
    period_unit: Optional[str] = None  # e.g. per "month" or "year" for renewing
    plan_price_id: Optional[str] = None
    plan_price: Optional[int] = None
    currency_code: Optional[str] = None  # e.g. "USD"
    base_price: Optional[int] = None
    currency_symbol: Optional[str] = None  # e.g. "$" (special character)
    is_unlimited: Optional[bool] = None

    def update_from_dict(self, plan_dictionary: Dict):
        if plan_dictionary.get("plan_name") and plan_dictionary["plan_name"] != STR_NO_PLAN:
            # TODO(SOFT-1030): Create User thread lock
            self.plan_name = plan_dictionary["plan_name"]
            self.plan_credit = plan_dictionary.get("plan_credit", None)

            # Extract "2022-08-19" from "2022-08-19 23:58:37"
            renew = plan_dictionary.get("next_subscription_renewal_date", None)
            try:
                renew = datetime.strptime(renew, "%Y-%m-%d %H:%M:%S")
                self.next_subscription_renewal_date = renew
            except (ValueError, TypeError):
                self.next_subscription_renewal_date = None

            end_plan = plan_dictionary.get("current_term_end", None)
            try:
                end_plan = datetime.strptime(end_plan, "%Y-%m-%d %H:%M:%S")
                self.current_term_end = end_plan
            except (ValueError, TypeError):
                self.current_term_end = None

            next_credits = plan_dictionary.get("next_credit_renewal_date", None)
            try:
                next_credits = datetime.strptime(
                    next_credits, "%Y-%m-%d %H:%M:%S")
                self.next_credit_renewal_date = next_credits
            except (ValueError, TypeError):
                self.next_credit_renewal_date = None

            paused_plan_info = plan_dictionary.get("paused_info", None)
            if paused_plan_info is not None:
                self.subscription_state = SubscriptionState.PAUSED
                paused_date = paused_plan_info.get("pause_date", None)
                resume_date = paused_plan_info.get("resume_date", None)

                try:
                    self.plan_paused_at = datetime.strptime(
                        paused_date, "%Y-%m-%d %H:%M:%S")
                    self.plan_paused_until = datetime.strptime(
                        resume_date, "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    self.plan_paused_until = None
                    self.plan_paused_at = None
            else:
                self.subscription_state = SubscriptionState.ACTIVE

            self.period_unit = plan_dictionary.get("period_unit", None)
            self.plan_price_id = plan_dictionary.get("plan_price_id", None)
            plan_price = plan_dictionary.get("plan_price", None)
            try:
                plan_price = int(plan_price)
            except ValueError:
                plan_price = None
            self.plan_price = plan_price
            self.currency_code = plan_dictionary.get("currency_code", None)
            try:
                base_price = plan_dictionary.get("base_price", None)
            except ValueError:
                base_price = None
            self.base_price = base_price
            self.currency_symbol = self._decode_currency_symbol(
                plan_dictionary.get("currency_symbol", ""))

            unlimited = plan_dictionary.get("unlimited", None)
            if unlimited is not None:
                self.is_unlimited = bool(unlimited)
        else:
            self.plan_name = None
            self.plan_credit = None
            self.next_subscription_renewal_date = None
            self.next_credit_renewal_date = None
            self.subscription_state = SubscriptionState.FREE
            self.period_unit = None
            self.plan_price_id = None
            self.plan_price = None
            self.currency_code = None
            self.base_price = None
            self.currency_symbol = None

    @staticmethod
    def _decode_currency_symbol(currency_str: str) -> str:
        decoded_str = ""
        chars = currency_str.split(";")
        for _char in chars:
            # Processing chrs in html format (e.g "82;&#36" => R$)
            try:
                int_char = int(_char)
                _char = chr(int_char)
            except ValueError:
                _char = html.unescape(_char)
            if len(_char) != 1:
                _char = ""
            decoded_str += _char
        return decoded_str


@dataclass
class PoliigonUser:
    """Container object for a user."""

    user_name: str
    user_id: int
    credits: Optional[int] = None
    credits_od: Optional[int] = None
    plan: Optional[PoliigonSubscription] = None
    map_preferences: Optional[UserDownloadPreferences] = None
    # Todo(Joao): remove this flag when all addons are using map prefs
    use_preferences_on_download: bool = False
