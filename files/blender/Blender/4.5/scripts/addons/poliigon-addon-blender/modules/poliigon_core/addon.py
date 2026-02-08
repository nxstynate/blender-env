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

from concurrent.futures import Future
from datetime import datetime
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple
from errno import EACCES, ENOSPC
import functools
import os
import json
import webbrowser

from .assets import (AssetType,
                     AssetData,
                     ModelType,
                     SIZES)
from .user import (PoliigonUser,
                   PoliigonSubscription,
                   SubscriptionState)
from . import api
from . import asset_index
from . import env
from .logger import (DEBUG,  # noqa F401, allowing downstream const usage
                     ERROR,
                     INFO,
                     get_addon_logger,
                     NOT_SET,
                     WARNING)
from .notifications import NotificationSystem
from . import settings
from . import updater
from .multilingual import Multilingual
from . import thread_manager as tm


DIR_PATH = os.path.dirname(os.path.abspath(__file__))
RESOURCES_PATH = os.path.join(DIR_PATH, "resources")


class PoliigonAddon():
    """Poliigon addon used for creating base singleton in DCC applications."""

    addon_name: str  # e.g. poliigon-addon-blender
    addon_version: tuple  # Current addon version
    software_source: str  # e.g. blender
    software_version: tuple  # DCC software version, e.g. (3, 0)
    addon_convention: int  # Maximum convention supported by DCC implementation

    library_paths: List = []

    def __init__(self,
                 addon_name: str,
                 addon_version: tuple,
                 software_source: str,
                 software_version: tuple,
                 addon_env: env.PoliigonEnvironment,
                 addon_settings: settings.PoliigonSettings,
                 addon_convention: int,
                 addon_supported_model: List[ModelType] = [ModelType.FBX],
                 language: str = "en-US",
                 # See ThreadManager.__init__ for signature below,
                 #   e.g. print_exc(fut: Future, key_pool: PoolKeys)
                 callback_print_exc: Optional[Callable] = None):
        self.log_manager = get_addon_logger(env=addon_env)

        if addon_env.env_name == "prod":
            have_filehandler = False
        else:
            have_filehandler = True
        self.logger = self.log_manager.initialize_logger(
            have_filehandler=have_filehandler)
        self.logger_api = self.log_manager.initialize_logger(
            "API", have_filehandler=have_filehandler)
        self.logger_dl = self.log_manager.initialize_logger(
            "DL", have_filehandler=have_filehandler)

        self.language = language

        self.multilingual = Multilingual()
        self.multilingual.install_domain(language=self.language,
                                         dir_lang=os.path.join(RESOURCES_PATH, "lang"),
                                         domain="addon-core")

        self.addon_name = addon_name
        self.addon_version = addon_version
        self.software_source = software_source
        self.software_version = software_version
        self.addon_convention = addon_convention

        self.user = None
        self.login_error = None
        self.api_rc = None  # To be set on the DCC side

        self._env = addon_env

        self.set_logger_verbose(verbose=False)

        self._settings = addon_settings
        self._api = api.PoliigonConnector(
            env=self._env,
            software=software_source,
            logger=self.logger_api
        )
        self.logger.debug(f"API URL V1: {self._api.api_url}")
        self.logger.debug(f"API URL V2: {self._api.api_url_v2}")
        if "v1" in self._api.api_url and "apiv1" not in self._api.api_url:
            self.logger.warning("Likely you are running with an outdated API V1 URL")
        self._api.register_update(
            ".".join([str(x) for x in addon_version]),
            ".".join([str(x) for x in software_version])
        )
        self._tm = tm.ThreadManager(callback_print_exc=callback_print_exc)
        self.notify = NotificationSystem(self)
        self._api.notification_system = self.notify
        self._updater = updater.SoftwareUpdater(
            addon_name=addon_name,
            addon_version=addon_version,
            software_version=software_version,
            notification_system=self.notify,
            local_json=self._env.local_updater_json
        )

        self.settings_config = self._settings.config

        self.user_addon_dir = os.path.join(
            os.path.expanduser("~"),
            "Poliigon"
        )

        self.setup_libraries()
        self.categories_path = os.path.join(self.user_addon_dir, "categories.json")

        default_asset_index_path = os.path.join(
            self.user_addon_dir,
            "AssetIndex",
            "asset_index.json",
        )
        self._asset_index = asset_index.AssetIndex(
            addon=self,
            addon_convention=addon_convention,
            path_cache=default_asset_index_path,
            addon_supported_model=addon_supported_model,
            log=None
        )
        self.online_previews_path = self.setup_temp_previews_folder()

    # TODO(Andreas): Could well be done in constructor itself.
    #                Yet, it would break DCC implementations, atm.
    def init_addon_parameters(
        self,
        *,
        get_optin: Callable,
        callback_on_invalidated_token: Callable,
        report_message: Callable,
        report_thread: Callable,
        status_listener: Callable,
        urls_dcc: Dict[str, str],
        notify_icon_info: Any,
        notify_icon_no_connection: Any,
        notify_icon_survey: Any,
        notify_icon_warn: Any,
        notify_update_body: str
        # TODO(Andreas): Once API RC gets instanced here, add:
        # page_size_online_assets: int,
        # page_size_my_assets: int,
        # callback_get_categories_done: Callable,
        # callback_get_asset_done: Callable,
        # callback_get_user_data_done: Callable,
        # callback_get_download_prefs_done: Callable
    ) -> None:
        """Initializes all parameters of PoliigonAddon."""

        self._api.get_optin = get_optin
        self._api.set_on_invalidated(callback_on_invalidated_token)
        self._api._status_listener = status_listener
        self._api.add_poliigon_urls(urls_dcc)
        self._api._report_message = report_message

        self._tm.reporting_callable = report_thread

        self.notify.init_icons(
            icon_info=notify_icon_info,
            icon_no_connection=notify_icon_no_connection,
            icon_survey=notify_icon_survey,
            icon_warn=notify_icon_warn)
        self.notify.addon_params.update_body = notify_update_body

        # TODO(Andreas): Once API RC gets instanced in constructor,
        #                add the following here:
        # params = self.api_rc._addon_params
        # params.online_assets_chunk_size = page_size_online_assets
        # params.my_assets_chunk_size = page_size_my_assets
        # params.callback_get_categories_done = callback_get_categories_done
        # params.callback_get_asset_done = callback_get_asset_done
        # params.callback_get_user_data_done = callback_get_user_data_done
        # params.callback_get_download_prefs_done = callback_get_download_prefs_done

    # Decorator copied from comment in thread_manager.py
    def run_threaded(key_pool: tm.PoolKeys,
                     max_threads: Optional[int] = None,
                     foreground: bool = False) -> Callable:
        """Schedule a function to run in a thread of a chosen pool"""
        def wrapped_func(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapped_func_call(self, *args, **kwargs):
                args = (self, ) + args
                return self._tm.queue_thread(func, key_pool,
                                             max_threads, foreground,
                                             *args, **kwargs)
            return wrapped_func_call
        return wrapped_func

    def setup_libraries(self):
        default_lib_path = os.path.join(self.user_addon_dir, "Library")
        multi_dir = self.settings_config["directories"]

        primary_lib_path = self.settings_config.get(
            "library", "primary", fallback=None)

        # If primary lib is not found in settings, set the default path as
        # primary, the DCC side should handle the value missing in settings
        # (e.g. choose main lib screen)
        if primary_lib_path not in [None, ""]:
            self.library_paths.append(primary_lib_path)
        else:
            self.library_paths.append(default_lib_path)

        for dir_idx in multi_dir.keys():
            path = self.settings_config.get("directories", str(dir_idx))
            self.library_paths.append(path)

    # TODO(Andreas): why is it called temp?
    def setup_temp_previews_folder(self) -> str:
        previews_dir = os.path.join(self.user_addon_dir, "OnlinePreviews")
        try:
            os.makedirs(previews_dir, exist_ok=True)
        except Exception:
            self.logger.exception(
                f"Failed to create directory: {previews_dir}")

        # Removing lock temp files for thumbs
        for _file in os.listdir(previews_dir):
            file_path = os.path.join(previews_dir, _file)
            if os.path.isfile(file_path) and _file.endswith("_temp"):
                os.remove(file_path)
        return previews_dir

    def load_categories_from_disk(self) -> Optional[Dict]:
        """Loads categories from disk."""

        if not os.path.exists(self.categories_path):
            return None

        try:
            with open(self.categories_path, "r") as file_categories:
                category_json = json.load(file_categories)
                if not isinstance(category_json, List):
                    return None

        # TODO(Andreas): error handling
        #                Whatever error we encounter, worst outcome is no cached categories
        except OSError as e:
            if e.errno == EACCES:
                return None
            else:
                return None
        except Exception:
            return None

        return category_json

    def save_categories_to_disk(self, category_json: List) -> None:
        """Stores categories (as received from API) to disk."""

        try:
            with open(self.categories_path, "w") as file_categories:
                json.dump(category_json, file_categories, indent=4)
        # TODO(Andreas): error handling
        #                Whatever error we encounter, worst outcome is no cached categories
        except OSError as e:
            if e.errno == ENOSPC:
                return
            elif e.errno == EACCES:
                return
            else:
                return
        except Exception:
            return

    def set_logger_verbose(self, verbose: bool) -> None:
        """To be used by DCC side to set main logger verbosity."""

        log_lvl_from_env = NOT_SET
        if self._env.config is not None:
            log_lvl_from_env = self._env.config.getint(
                "DEFAULT", "log_lvl", fallback=NOT_SET)
        if log_lvl_from_env != NOT_SET:
            self.logger.info(f"Log level forced by env: {log_lvl_from_env}")
            return
        log_lvl = INFO if verbose else ERROR
        self.logger.setLevel(log_lvl)

    def is_logged_in(self) -> bool:
        """Returns whether or not the user is currently logged in."""
        return self._api.token is not None and not self._api.invalidated

    def is_user_invalidated(self) -> bool:
        """Returns whether or not the user token was invalidated."""
        return self._api.invalidated

    def clear_user_invalidated(self):
        """Clears any invalidation flag for a user."""
        self._api.invalidated = False

    @run_threaded(tm.PoolKeys.INTERACTIVE)
    def log_in_with_credentials(self,
                                email: str,
                                password: str,
                                *,
                                wait_for_user: bool = False) -> Future:
        self.clear_user_invalidated()

        req = self._api.log_in(
            email,
            password
        )

        if req.ok:
            user_data = req.body.get("user", {})

            fut = self.create_user(user_data.get("name"), user_data.get("id"))
            if wait_for_user:
                fut.result(timeout=api.TIMEOUT)

            self.login_error = None
        else:
            self.login_error = req.error

        return req

    def log_in_with_website(self):
        pass

    def check_for_survey_notice(
            self,
            free_user_url: str,
            plan_user_url: str,
            interval: int,
            label: str,
            tooltip: str = "",
            auto_enqueue: bool = True) -> None:

        already_shown = self.settings_config.get(
            "user", "survey_notice_shown", fallback=None)

        if already_shown not in [None, ""]:
            # Never notify again if already did once
            return

        first_local_asset = self.settings_config.get(
            "user", "first_local_asset", fallback=None)

        if first_local_asset in ["", None]:
            return

        def set_user_survey_flag() -> None:
            self.settings_config.set(
                "user", "survey_notice_shown", str(datetime.now()))
            self._settings.save_settings()

        first_asset_dl = datetime.strptime(first_local_asset, "%Y-%m-%d %H:%M:%S.%f")
        difference = datetime.now() - first_asset_dl
        if difference.days >= interval:
            self.notify.create_survey(
                is_free_user=self.is_free_user(),
                tooltip=tooltip,
                free_survey_url=free_user_url,
                active_survey_url=plan_user_url,
                label=label,
                auto_enqueue=auto_enqueue,
                on_dismiss_callable=set_user_survey_flag
            )

    @run_threaded(tm.PoolKeys.INTERACTIVE)
    def log_out(self):
        req = self._api.log_out()
        if req.ok:
            print("Logout success")
        else:
            print(req.error)

        self._api.token = None

        # Clear out user on logout.
        self.user = None

    def add_library_path(self,
                         path: str,
                         primary: bool = True,
                         update_local_assets: bool = True
                         ) -> None:
        if not os.path.isdir(path):
            self.logger.info(f"Library Path to be added is not a directory: {path}")
            return
        elif path in self.library_paths:
            if primary:
                self.remove_library_path(path)
            else:
                self.logger.info(f"Library Path to be added is already in the list: {path}")
                return

        if primary:
            if len(self.library_paths) == 0:
                self.library_paths = [path]
            else:
                self.library_paths[0] = path
            self.settings_config.set("library", "primary", path)
        else:
            self.library_paths.append(path)
            idx = 0
            list_directory_idxs = list(self.settings_config["directories"].keys())
            if len(list_directory_idxs) > 0:
                idx = int(list_directory_idxs[-1]) + 1
            self.settings_config.set("directories", str(idx), path)

        self._settings.save_settings()

        if update_local_assets:
            self._asset_index.update_all_local_assets(self.library_paths)

    def remove_library_path(self,
                            path: str,
                            update_local_assets: bool = True
                            ) -> None:
        if path not in self.library_paths:
            self.logger.info(f"Library Path to be removed is not in the list: {path}")
            return

        self.library_paths.remove(path)

        for dir_idx in self.settings_config["directories"].keys():
            dir_path = self.settings_config.get("directories", dir_idx)
            if dir_path == path:
                self.settings_config.remove_option("directories", dir_idx)
        self._settings.save_settings()

        if update_local_assets:
            self._asset_index.flush_is_local()
            self._asset_index.update_all_local_assets(self.library_paths)

    def replace_library_path(self,
                             path_old: str,
                             path_new: str,
                             primary: bool = True,
                             update_local_assets: bool = True
                             ) -> None:
        self.remove_library_path(path_old, update_local_assets=False)
        self._asset_index.flush_is_local()
        self.add_library_path(path_new,
                              primary=primary,
                              update_local_assets=update_local_assets)

    def get_library_paths(self):
        return self.library_paths

    def get_library_path(self, primary: bool = True):
        if self.library_paths and primary:
            return self.library_paths[0]
        elif len(self.library_paths) > 1:
            # TODO(Mitchell): Return the most relevant lib path based on some input (?)
            return None
        else:
            return None

    def _get_user_info(self) -> Tuple:
        req = self._api.get_user_info()
        user_name = None
        user_id = None

        if req.ok:
            data = req.body
            user_name = data["user"]["name"]
            user_id = data["user"]["id"]
            self.login_error = None
        else:
            # TODO(SOFT-1029): Create an error log for fail in get user info
            self.login_error = req.error

        return user_name, user_id

    def _get_credits(self):
        if self.user is None:
            msg = "_get_credits() called without user."
            self._api.report_message(
                "addon_get_credits", msg, "error")
            return

        req = self._api.get_user_balance()
        if req.ok:
            data = req.body
            self.user.credits = data.get("subscription_balance")
            self.user.credits_od = data.get("ondemand_balance")
        else:
            self.user.credits = None
            self.user.credits_od = None
            msg = f"ERROR: {req.error}"
            self._api.report_message(
                "addon_get_credits", msg, "error")

    def _get_subscription_details(self):
        """Fetches the current user's subscription status."""
        req = self._api.get_subscription_details()

        if req.ok:
            plan = req.body
            self.user.plan.update_from_dict(plan)

    @run_threaded(tm.PoolKeys.INTERACTIVE)
    def update_plan_data(self, done_callback: Optional[Callable] = None) -> None:
        # TODO(Joao): sub thread the two private functions
        self._get_credits()
        self._get_subscription_details()
        if done_callback is not None:
            done_callback()

    def create_user(
            self,
            user_name: Optional[str] = None,
            user_id: Optional[int] = None,
            done_callback: Optional[Callable] = None) -> Optional[Future]:

        if user_name is None or user_id is None:
            user_name, user_id = self._get_user_info()

        if user_name is None or user_id is None:
            return None

        self.user = PoliigonUser(
            user_name=user_name,
            user_id=user_id,
            plan=PoliigonSubscription(
                subscription_state=SubscriptionState.NOT_POPULATED)
        )

        future = self.update_plan_data(done_callback)
        return future

    def is_free_user(self) -> bool:
        """Identifies a free user which neither
        has a plan nor on demand credits."""

        sub_state = self.user.plan.subscription_state
        free_plan = sub_state == SubscriptionState.FREE
        no_credits = self.user.credits in [0, None]
        no_od_credits = self.user.credits_od in [0, None]

        return free_plan and no_credits and no_od_credits

    def is_unlimited_user(self) -> bool:
        if self.user is None:
            return False
        elif self.user.plan in [None, SubscriptionState.NOT_POPULATED]:
            return False
        elif self.user.plan.is_unlimited is None:
            return False
        return self.user.plan.is_unlimited

    def is_paused_subscription(self) -> Optional[bool]:
        """Return True, if the Subscription is in paused state.

        Return value may be None, if there is no plan.
        """

        if self.user is None or self.user.plan is None:
            return None
        return self.user.plan.subscription_state == SubscriptionState.PAUSED

    def get_user_credits(self, incl_od: bool = True) -> int:
        """Returns the number of _spendable_ credits."""

        subscr_paused = self.is_paused_subscription()

        credits = self.user.credits
        credits_od = self.user.credits_od

        if not incl_od and credits_od is not None:
            credits_od = 0

        if credits is None and credits_od is None:
            return 0
        elif credits_od is None:
            return credits if not subscr_paused else 0
        elif credits is None:
            return credits_od
        else:
            if subscr_paused:
                return credits_od
            else:
                return credits + credits_od

    def get_thumbnail_path(self, asset_name, index):
        """Return the best fitting thumbnail preview for an asset.

        The primary grid UI preview will be named asset_preview1.png,
        all others will be named such as asset_preview1_1K.png
        """
        if index == 0:
            # 0 is the small grid preview version of _preview1.

            # Fallback to legacy option of .jpg files if .png not found.
            thumb = os.path.join(
                self.online_previews_path,
                asset_name + "_preview1.png"
            )
            if not os.path.exists(thumb):
                thumb = os.path.join(
                    self.online_previews_path,
                    asset_name + "_preview1.jpg"
                )
        else:
            thumb = os.path.join(
                self.online_previews_path,
                asset_name + f"_preview{index}_1K.png")
        return thumb

    def get_type_default_size(self, asset_data: AssetData) -> Optional[str]:
        """Returns a list of sizes valid for download."""

        type_data = asset_data.get_type_data()
        sizes_data = type_data.get_size_list()

        size = None
        if asset_data.asset_type == AssetType.TEXTURE:
            size = self.settings_config.get("download", "tex_res")
        elif asset_data.asset_type == AssetType.MODEL:
            settings_size = self.settings_config.get(
                "download", "model_res")
            size_default = asset_data.model.size_default
            has_default = size_default is not None
            if settings_size in ["", "NONE", None] and has_default:
                size = size_default
            else:
                size = settings_size
        elif asset_data.asset_type == AssetType.HDRI:
            size = self.settings_config.get("download", "hdri_light")
            # TODO(Andreas): what about bg size?
        elif asset_data.asset_type == AssetType.BRUSH:
            size = self.settings_config.get("download", "brush")

        valid_size = size in sizes_data

        # If no valid size found, try to find at least one matching asset's
        # available size data
        if not valid_size:
            for _size in reversed(SIZES):
                if _size in sizes_data:
                    size = _size
                    break

        return size

    def set_first_local_asset(self, force_update: bool = False) -> None:
        """Conditionally assigns the current date to the settings file.

        Meant to be used in conjunction with surveying, this should be called
        either on first download or first import, if the value hasn't already
        been set or if force_update is true."""

        first_asset_timestamp = self.settings_config.get(
            "user", "first_local_asset", fallback="")
        if first_asset_timestamp == "" or force_update:
            time_stamp = datetime.now()
            self.settings_config.set(
                "user", "first_local_asset", str(time_stamp))
            self._settings.save_settings()

    def set_first_preview_import(self, force_update: bool = False) -> None:
        first_wm_timestamp = self.settings_config.get(
            "user", "first_preview_import", fallback="")
        if first_wm_timestamp == "" or force_update:
            time_stamp = datetime.now()
            self.settings_config.set(
                "user", "first_preview_import", str(time_stamp))
            self._settings.save_settings()

    def set_first_purchase(self, force_update: bool = False) -> None:
        first_purchase_timestamp = self.settings_config.get(
            "user", "first_purchase", fallback="")
        if first_purchase_timestamp == "" or force_update:
            time_stamp = datetime.now()
            self.settings_config.set(
                "user", "first_purchase", str(time_stamp))
            self._settings.save_settings()

    def print_debug(self, *args, dbg=False, bg=True):
        """Print out a debug statement with no separator line.

        Cache based on args up to a limit, to avoid excessive repeat prints.
        All args must be flat values, such as already casted to strings, else
        an error will be thrown.
        """
        if dbg:
            # Ensure all inputs are hashable, otherwise lru_cache fails.
            stringified = [str(arg) for arg in args]
            self._cached_print(*stringified, bg=bg)

    @lru_cache(maxsize=32)
    def _cached_print(self, *args, bg: bool):
        """A safe-to-cache function for printing."""
        print(*args)

    def open_asset_url(self, asset_id: int) -> None:
        asset_data = self._asset_index.get_asset(asset_id)
        url = self._api.add_utm_suffix(asset_data.url)
        webbrowser.open(url)

    def open_poliigon_link(self,
                           link_type: str,
                           add_utm_suffix: bool = True
                           ) -> None:
        """Opens a Poliigon URL"""

        # TODO(Andreas): As soon as P4B uses PoliigonAddon move code from
        #                api.open_poliigon_link here and remove function in api
        self._api.open_poliigon_link(
            link_type, add_utm_suffix, env_name=self._env.env_name)

    def get_wm_download_path(self, asset_name: str) -> str:
        """Returns an asset name path inside the OnlinePreviews folder"""

        path_poliigon = os.path.dirname(self._settings.base)
        path_thumbs = os.path.join(path_poliigon, "OnlinePreviews")
        path_wm_previews = os.path.join(path_thumbs, asset_name)
        return path_wm_previews

    def download_material_wm(
            self, files_to_download: List[Tuple[str, str]]) -> None:
        """Synchronous function to download material preview."""

        urls = []
        files_dl = []
        for _url_wm, _filename_wm_dl in files_to_download:
            urls.append(_url_wm)
            files_dl.append(_filename_wm_dl)

        resp = self._api.pooled_preview_download(urls, files_dl)
        if not resp.ok:
            msg = f"Failed to download WM preview\n{resp}"
            self._api.report_message(
                "download_mat_preview_dl_failed", msg, "error")
            # Continue, as some may have worked.

        for _filename_wm_dl in files_dl:
            filename_wm = _filename_wm_dl[:-3]  # cut of _dl

            try:
                file_exists = os.path.exists(filename_wm)
                dl_exists = os.path.exists(_filename_wm_dl)
                if file_exists and dl_exists:
                    os.remove(filename_wm)
                elif not file_exists and not dl_exists:
                    raise FileNotFoundError
                if dl_exists:
                    os.rename(_filename_wm_dl, filename_wm)
            except FileNotFoundError:
                msg = f"Neither {filename_wm}, nor {_filename_wm_dl} exist"
                self._api.report_message(
                    "download_mat_existing_file", msg, "error")
            except FileExistsError:
                msg = f"File {filename_wm} already exists, failed to rename"
                self._api.report_message(
                    "download_mat_rename", msg, "error")
            except Exception as e:
                self.logger.exception("Unexpected exception while renaming WM preview")
                msg = f"Unexpected exception while renaming {_filename_wm_dl}\n{e}"
                self._api.report_message(
                    "download_wm_exception", msg, "error")
        return resp

    def get_config_param(self,
                         name_param: str,
                         name_group: str = "DEFAULT",
                         fallback: Optional[Any] = None
                         ) -> Any:
        """Safely read a value from config (regardless of setup env or not)."""

        if self._env.config is None:
            return fallback
        return self._env.config.get(name_group, name_param, fallback=fallback)
