# NOTE: This is a verbatim copy of the real
# netskope/integrations/cls/plugin_base.py, pulled directly from a live
# Cloud Exchange 6.1.0 instance (cloudexchange_core_1 container,
# /opt/netskope/integrations/cls/plugin_base.py) for local test
# fidelity. It is NOT maintained by this project - if CE is upgraded,
# re-pull this file to keep the stub accurate.
"""Provides plugin implementation related classes."""

from typing import List, Optional
from pydantic import BaseModel

from netskope.common.utils import PluginBase as CommonPluginBase


class ValidationResult(BaseModel):
    """Validation result model (returned by Plugin.validate method)."""

    message: str
    success: bool = False


class PushResult(BaseModel):
    """Push result model (returned by Plugin.push method)."""

    message: str
    success: bool = False
    failed_data: Optional[List] = []


class PluginBase(CommonPluginBase):
    """CLS plugin base class."""

    integration = "cls"

    def __init__(
        self,
        name,
        configuration,
        storage,
        last_run_at,
        logger,
        use_proxy=True,
        ssl_validation=True,
        source=None,
        mappings=None,
    ):
        """Initialize."""
        super().__init__(
            name,
            configuration,
            storage,
            last_run_at,
            logger,
            use_proxy=use_proxy,
            ssl_validation=ssl_validation,
        )
        if self.configuration:
            transform_data = self._configuration.get("transformData")
            if (
                isinstance(transform_data, str)
                and self.metadata
                and not self.metadata.get("format_options", None)
            ):
                self._configuration["transformData"] = (
                    transform_data == "cef"
                )

        self._source = source
        self._mappings = mappings

    def pull(self, cursor=None, start_time=None, end_time=None) -> List:
        """Pull indicators from Netskope."""
        pass

    def push(self, transformed_data, data_type, subtype) -> PushResult:
        """Push the transformed_data to the 3rd party platform."""
        raise NotImplementedError()

    def transform(self, raw_data, data_type, subtype) -> List:
        """Transform the raw netskope JSON data into target platform
        supported data formats."""
        raise NotImplementedError()

    def validate(self, configuration: dict, value: None) -> ValidationResult:
        """Validate the configuration parameters dict and mapping
        file."""
        raise NotImplementedError()

    def extract_and_store_fields(
        self, data: list, data_type: str, subtype: str
    ) -> None:
        """Extract and store fields from data."""
        raise NotImplementedError()

    @staticmethod
    def chunk_size() -> int:
        """Define the chunk size of data to be pushed in one go."""
        return 10000

    def get_subtypes(self, data_type):
        """Extract the data types from plugin specific mapping file."""
        pass

    @property
    def mappings(self) -> dict:
        """Get the mapping for CLS."""
        return self._mappings

    @property
    def source(self) -> str:
        """Get source for the current configuration."""
        return self._source

    def validate_mappings(self) -> ValidationResult:
        """Validate the configured mappings."""
        pass
