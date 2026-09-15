"""Local stand-in for the real Netskope CE SDK's plugin_base module.

NOT the real Netskope SDK. It exists only so this plugin's unit tests
can import and instantiate the Plugin class offline. Attribute and
method signatures mirror what is documented in the official CLS
Plugin Developer Guide and observed in the crowdstrike_ngsiem_cls
reference plugin. If the real plugin_base.py ever becomes available
(e.g. pulled from a CE sandbox instance), diff it against this file
to catch any wrong assumptions.
"""


class ValidationResult:
    def __init__(self, success, message):
        self.success = success
        self.message = message

    def __repr__(self):
        return (
            f"ValidationResult(success={self.success}, "
            f"message={self.message!r})"
        )


class PushResult:
    def __init__(self, success, message):
        self.success = success
        self.message = message

    def __repr__(self):
        return (
            f"PushResult(success={self.success}, "
            f"message={self.message!r})"
        )


class PluginBase:
    metadata = {}

    def __init__(
        self,
        name,
        configuration=None,
        storage=None,
        last_run_at=None,
        logger=None,
        use_proxy=False,
        ssl_validation=True,
        source=None,
        mappings=None,
        notifier=None,
        proxy=None,
        **kwargs,
    ):
        self.name = name
        self.configuration = configuration or {}
        self.storage = storage if storage is not None else {}
        self.last_run_at = last_run_at
        self.logger = logger
        self.use_proxy = use_proxy
        self.ssl_validation = ssl_validation
        self.source = source
        self.mappings = mappings or {}
        self.notifier = notifier
        self.proxy = proxy or {}
