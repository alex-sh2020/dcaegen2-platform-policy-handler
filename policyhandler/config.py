# ================================================================================
# Copyright (c) 2017-2018 AT&T Intellectual Property. All rights reserved.
# ================================================================================
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============LICENSE_END=========================================================
#
# ECOMP is a trademark and service mark of AT&T Intellectual Property.

"""read and use the config"""

import copy
import json
import logging
import logging.config
import os

from .discovery import DiscoveryClient
from .onap.audit import Audit
from .policy_utils import Utils

LOGS_DIR = 'logs'

try:
    os.makedirs(LOGS_DIR, mode=0o770, exist_ok=True)
except Exception:
    pass

logging.basicConfig(
    filename=os.path.join(LOGS_DIR, 'policy_handler.log'),
    format=('%(asctime)s.%(msecs)03d %(levelname)+8s ' +
            '%(threadName)s %(name)s.%(funcName)s: %(message)s'),
    datefmt='%Y%m%d_%H%M%S', level=logging.DEBUG)

class Settings(object):
    """settings of module or an application
    that is the config filtered by the collection of config-keys.

    keeps track of changes versus the previous set_config unless committed
    """
    def __init__(self, *config_keys):
        """provide the collection of top level keys in config to limit the config"""
        self._config_keys = config_keys
        self._changed = False
        self._config = None
        self._prev_config = None

    def __str__(self):
        """get str of the config"""
        return Audit.json_dumps({
            "config_keys": self._config_keys,
            "changed": self._changed,
            "config": self._config,
            "prev_config": self._prev_config
        })

    def is_loaded(self):
        """whether loaded already"""
        return bool(self._config)

    def commit_change(self):
        """set the prev config to the latest config"""
        self._prev_config = copy.deepcopy(self._config)
        self._changed = False

    def _set_changed(self):
        """determine whether the config changed"""
        self._changed = not (self._prev_config
                             and Utils.are_the_same(self._prev_config, self._config,
                                                    Audit.json_dumps))

    def set_config(self, config, auto_commit=False):
        """update the config"""
        self.commit_change()

        if isinstance(config, Settings):
            config = config._config

        if not isinstance(config, dict):
            config = {}

        self._config = copy.deepcopy(dict((k, v) for (k, v) in config.items()
                                          if not self._config_keys or k in self._config_keys))

        if auto_commit:
            self.commit_change()
        else:
            self._set_changed()

    def is_changed(self):
        """whether the config has changed"""
        return self._changed

    def get_by_key(self, config_key, default=None):
        """get the latest sub config by config_key and whether it has changed"""
        if not config_key or not isinstance(config_key, str):
            return False, default

        value = copy.deepcopy(self._config.get(config_key, default))
        if not self._prev_config:
            return True, value
        prev_value = self._prev_config.get(config_key, default)
        return self._changed and not Utils.are_the_same(prev_value, value, Audit.json_dumps), value

    def update(self, config_key, value=None):
        """set the latest sub config by config_key and determine whether the config has changed"""
        if not config_key:
            return

        self._config[config_key] = copy.deepcopy(value)
        self._set_changed()


class Config(object):
    """main config of the application"""
    _logger = logging.getLogger("policy_handler.config")
    CONFIG_FILE_PATH = "etc/config.json"
    LOGGER_CONFIG_FILE_PATH = "etc/common_logger.config"
    SERVICE_NAME_POLICY_HANDLER = "policy_handler"

    FIELD_SYSTEM = "system"
    FIELD_WSERVICE_PORT = "wservice_port"
    FIELD_POLICY_ENGINE = "policy_engine"
    POOL_CONNECTIONS = "pool_connections"
    DEPLOY_HANDLER = "deploy_handler"
    THREAD_POOL_SIZE = "thread_pool_size"
    POLICY_RETRY_COUNT = "policy_retry_count"
    POLICY_RETRY_SLEEP = "policy_retry_sleep"
    RECONFIGURE = "reconfigure"
    TIMER_INTERVAL = "interval"

    system_name = SERVICE_NAME_POLICY_HANDLER
    wservice_port = 25577
    _local_config = Settings()
    discovered_config = Settings()

    @staticmethod
    def init_config(file_path=None):
        """read and store the config from config file"""
        if Config._local_config.is_loaded():
            Config._logger.info("config already inited: %s", Config._local_config)
            return

        if not file_path:
            file_path = Config.CONFIG_FILE_PATH

        loaded_config = None
        if os.access(file_path, os.R_OK):
            with open(file_path, 'r') as config_json:
                loaded_config = json.load(config_json)

        if not loaded_config:
            Config._logger.warning("config not loaded from file: %s", file_path)
            return

        Config._logger.info("config loaded from file: %s", file_path)
        logging_config = loaded_config.get("logging")
        if logging_config:
            logging.config.dictConfig(logging_config)

        Config.wservice_port = loaded_config.get(Config.FIELD_WSERVICE_PORT, Config.wservice_port)

        local_config = loaded_config.get(Config.SERVICE_NAME_POLICY_HANDLER)
        Config.system_name = local_config.get(Config.FIELD_SYSTEM, Config.system_name)

        Config._local_config.set_config(local_config, auto_commit=True)
        Config._logger.info("config loaded from file(%s): %s", file_path, Config._local_config)

    @staticmethod
    def discover(audit):
        """bring and merge the config settings from the discovery service"""
        discovery_key = Config.system_name
        new_config = DiscoveryClient.get_value(audit, discovery_key)

        if not new_config or not isinstance(new_config, dict):
            Config._logger.warning("unexpected config from discovery: %s", new_config)
            return

        Config._logger.debug("loaded config from discovery(%s): %s",
                             discovery_key, Audit.json_dumps(new_config))

        Config.discovered_config.set_config(new_config.get(Config.SERVICE_NAME_POLICY_HANDLER))
        Config._logger.info("config from discovery: %s", Config.discovered_config)
