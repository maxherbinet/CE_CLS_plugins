"""Minimal stand-in for netskope.common.utils (NOT the real SDK).

Only the subset of CommonPluginBase behavior needed to instantiate and
exercise netskope.integrations.cls.plugin_base.PluginBase subclasses
offline. self.notifier and self.proxy are not constructor parameters
on the real CLS PluginBase.__init__ (confirmed by reading its source
on a live Cloud Exchange 6.1.0 instance), so they default here and are
expected to be set post-construction by test fixtures, mirroring how
Cloud Exchange's core likely injects them after instantiation.
"""


class PluginBase:
    """Stand-in for netskope.common.utils.PluginBase."""

    metadata = {}

    def __init__(
        self,
        name,
        configuration,
        storage,
        last_run_at,
        logger,
        use_proxy=True,
        ssl_validation=True,
    ):
        """Initialize."""
        self.name = name
        self._configuration = configuration
        self.storage = storage
        self.last_run_at = last_run_at
        self.logger = logger
        self.use_proxy = use_proxy
        self.ssl_validation = ssl_validation
        self.proxy = {}
        self.notifier = None

    @property
    def configuration(self):
        """Get configuration."""
        return self._configuration

    @configuration.setter
    def configuration(self, value):
        self._configuration = value
