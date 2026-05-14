from .service_locator import ServiceLocator

class BaseHandler:
    """
    Base class for all command handlers.
    Provides centralized access to core managers via ServiceLocator.
    """
    def __init__(self, **kwargs):
        self._managers = kwargs

    @property
    def server_manager(self):
        return self._managers.get("server_manager") or ServiceLocator.get("ServerManager")

    @property
    def rcon_manager(self):
        return self._managers.get("rcon_manager") or ServiceLocator.get("RCONManager")

    @property
    def discord_manager(self):
        return self._managers.get("discord_manager") or ServiceLocator.get("DiscordManager")

    @property
    def version_manager(self):
        return self._managers.get("version_manager") or ServiceLocator.get("VersionManager")

    @property
    def config_manager(self):
        return self._managers.get("config_manager") or ServiceLocator.get("ConfigManager")

    @property
    def backup_manager(self):
        return self._managers.get("backup_manager") or ServiceLocator.get("BackupManager")

    @property
    def player_manager(self):
        return self._managers.get("player_manager") or ServiceLocator.get("PlayerManager")

    @property
    def schedule_manager(self):
        return self._managers.get("schedule_manager") or ServiceLocator.get("ScheduleManager")

    @property
    def raptorchat_manager(self):
        return self._managers.get("raptorchat_manager") or ServiceLocator.get("RaptorChatManager")

    @property
    def telemetry_manager(self):
        return self._managers.get("telemetry_manager") or ServiceLocator.get("TelemetryManager")
