"""Palo Alto Cortex XDR Plugin Validator."""

import traceback
from urllib.parse import urlparse

from jsonschema import validate
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError


class CortexXDRValidator(object):
    """Palo Alto Cortex XDR plugin validator class."""

    def __init__(self, logger, log_prefix):
        """Initialize the validator.

        Args:
            logger (Logger): Logger object.
            log_prefix (str): Log prefix.
        """
        super().__init__()
        self.logger = logger
        self.log_prefix = log_prefix

    def validate_url(self, url: str) -> bool:
        """Validate the URL using parsing.

        Args:
            url (str): Given URL.

        Returns:
            bool: True if valid, False otherwise.
        """
        parsed = urlparse(url)
        return parsed.scheme.strip() != "" and parsed.netloc.strip() != ""

    def validate_mappings(self, mappings: dict) -> bool:
        """Validate the given mapping dict against the expected schema.

        Args:
            mappings (dict): Mapping dict (parsed from mappings.json's
            jsonData field).

        Returns:
            bool: True if valid, False otherwise.
        """
        schema = {
            "type": "object",
            "properties": {
                "taxonomy": {
                    "type": "object",
                    "properties": {"json": {"type": "object"}},
                    "anyOf": [{"required": ["json"]}],
                }
            },
            "required": ["taxonomy"],
        }

        try:
            validate(instance=mappings, schema=schema)
            return True
        except JsonSchemaValidationError as err:
            self.logger.error(
                message=(
                    f"{self.log_prefix}: Error occurred while validating "
                    f"Mapping String. Error: {err}"
                ),
                details=traceback.format_exc(),
            )
        return False
