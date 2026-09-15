"""Netskope Cloud Exchange - Cloud Log Shipper (CLS) Plugin.

Palo Alto Cortex XDR Plugin for Netskope.
"""

import json
import time
import traceback
import uuid
from typing import List

from netskope.integrations.cls.plugin_base import (
    PluginBase,
    PushResult,
    ValidationResult,
)

from .utils.constant import (
    CE_LOG_SOURCE_IDENTIFIER,
    COMPRESSION_GZIP,
    COMPRESSION_UNCOMPRESSED,
    MODULE_NAME,
    PLATFORM_NAME,
    PLUGIN_VERSION,
)
from .utils.exception import CortexXDRException, MappingValidationError
from .utils.helper import CortexXDRPluginHelper
from .utils.utilities import (
    filter_events,
    get_cortex_xdr_mappings,
    gzip_compress,
    split_into_size,
)
from .utils.validator import CortexXDRValidator


class CortexXDRPlugin(PluginBase):
    """The Palo Alto Cortex XDR plugin implementation class."""

    def __init__(self, name, *args, **kwargs):
        """Initialize Palo Alto Cortex XDR plugin class."""
        super().__init__(name, *args, **kwargs)
        self.plugin_name, self.plugin_version = self._get_plugin_info()
        self.log_prefix = f"{MODULE_NAME} {self.plugin_name}"
        self.config_name = name
        if name:
            self.log_prefix = f"{self.log_prefix} [{name}]"
        self.cortex_xdr_helper = CortexXDRPluginHelper(
            logger=self.logger,
            log_prefix=self.log_prefix,
            plugin_name=self.plugin_name,
            plugin_version=self.plugin_version,
        )

    def _get_plugin_info(self) -> tuple:
        """Get plugin name and version from manifest.

        Returns:
            tuple: Tuple of plugin's name and version fetched from
            manifest.
        """
        try:
            manifest_json = CortexXDRPlugin.metadata
            plugin_name = manifest_json.get("name", PLATFORM_NAME)
            plugin_version = manifest_json.get("version", PLUGIN_VERSION)
            return plugin_name, plugin_version
        except Exception as exp:
            self.logger.error(
                message=(
                    f"{MODULE_NAME} {PLATFORM_NAME}: Error occurred while "
                    f"getting plugin details. Error: {exp}"
                ),
                details=str(traceback.format_exc()),
            )
        return PLATFORM_NAME, PLUGIN_VERSION

    @staticmethod
    def get_subtype_mapping(mappings: dict, subtype: str):
        """Retrieve subtype mapping (mapping for a subtype of alert/event).

        Args:
            mappings (dict): Mapping dict from which the subtype mapping
            is to be retrieved.
            subtype (str): Subtype (e.g. DLP for alerts) for which the
            mapping is to be fetched.

        Returns:
            The mapping value for the given subtype (an empty list means
            "pass all fields through" for this raw-JSON plugin).
        """
        mappings = {k.lower(): v for k, v in mappings.items()}
        if subtype.lower() in mappings:
            return mappings[subtype.lower()]
        return mappings.get(subtype.upper(), [])

    def transform(self, raw_data: List, data_type: str, subtype: str) -> List:
        """Transform Netskope data (alerts and events) for Cortex XDR.

        This plugin only supports sharing raw JSON logs (the
        'Transform the raw logs' toggle must be disabled), so this
        method only filters out empty records - it does not remap
        fields.

        Args:
            raw_data (List): Raw data list pulled from the tenant.
            data_type (str): Data type.
            subtype (str): Subtype.

        Returns:
            List: List of records to push.
        """
        if self.configuration.get("transformData", True):
            err_msg = (
                "The plugin only supports sharing raw JSON logs. Please "
                "disable the 'Transform the raw logs' toggle in the "
                "Basic plugin configuration."
            )
            self.logger.error(f"{self.log_prefix}: {err_msg}")
            raise CortexXDRException(err_msg)

        try:
            _, _, taxonomy = get_cortex_xdr_mappings(self.mappings, "json")
            subtype_mapping = self.get_subtype_mapping(
                taxonomy.get(data_type, {}), subtype
            )
        except (KeyError, MappingValidationError) as err:
            err_msg = f"Error in {PLATFORM_NAME} mapping file."
            self.logger.error(
                message=f"{self.log_prefix}: {err_msg} Error: {err}",
                details=traceback.format_exc(),
            )
            raise CortexXDRException(err_msg)

        skipped_empty, data = filter_events(raw_data)

        # An empty subtype mapping list means "pass all fields through"
        # for this raw-JSON plugin - no field-level remapping.
        if not subtype_mapping:
            if skipped_empty > 0:
                self.logger.info(
                    f"{self.log_prefix}: [{data_type}] [{subtype}] - "
                    f"Plugin couldn't process {skipped_empty} record(s) "
                    "because they had no data. These record(s) will be "
                    "skipped."
                )
            return data

        return data

    def push(self, transformed_data: List, data_type: str, subtype: str):
        """Push the transformed data to Palo Alto Cortex XDR.

        Args:
            transformed_data (List): Transformed data.
            data_type (str): Data type.
            subtype (str): Subtype.

        Returns:
            PushResult: Result of the push operation.
        """
        uid = uuid.uuid1()
        log_msg = f"{self.log_prefix}: [{data_type}] [{subtype}] -"

        self.logger.debug(
            f"{log_msg} Received {len(transformed_data)} record(s) to "
            f"push to {self.plugin_name}. UUID: {uid}"
        )

        if not transformed_data:
            msg = (
                f"Received empty transformed data hence the record(s) "
                f"were skipped. UUID: {uid}."
            )
            self.logger.info(f"{log_msg} {msg}")
            return PushResult(success=True, message=msg)

        url = self.configuration.get("api_url", "").strip("/").strip()
        api_key = self.configuration.get("api_key")
        compression = self.configuration.get(
            "compression", COMPRESSION_UNCOMPRESSED
        )
        log_source_identifier = self.configuration.get(
            "log_source_identifier", CE_LOG_SOURCE_IDENTIFIER
        ).strip()

        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        if compression == COMPRESSION_GZIP:
            headers["Content-Encoding"] = "gzip"

        chunks, skipped_oversized = split_into_size(
            transformed_data, log_source_identifier
        )
        if skipped_oversized:
            msg = (
                f"{skipped_oversized} record(s) exceeded Cortex XDR's "
                "5 MB per-record limit and were skipped."
            )
            self.logger.error(f"{log_msg} {msg}")
            self.notifier.error(f"{self.plugin_name}: {msg}")

        try:
            count = 0
            start = time.time()
            for batch, chunk in enumerate(chunks, start=1):
                payload_str = "\n".join(chunk)
                data = (
                    gzip_compress(payload_str)
                    if compression == COMPRESSION_GZIP
                    else payload_str
                )
                batch_start = time.time()
                self.cortex_xdr_helper.api_helper(
                    url=url,
                    method="POST",
                    headers=headers,
                    data=data,
                    proxies=self.proxy,
                    verify=self.ssl_validation,
                    logger_msg=(
                        f"ingesting {len(chunk)} record(s) of datatype "
                        f'"{data_type}" and subtype "{subtype}" in batch '
                        f'{batch} into {PLATFORM_NAME} having UUID "{uid}"'
                    ),
                )
                time_taken = round(time.time() - batch_start, 2)
                count += len(chunk)
                self.logger.info(
                    f"{log_msg} Successfully ingested {len(chunk)} "
                    f"record(s) in batch {batch}. Total record(s) "
                    f"pushed: {count}. Time taken: {time_taken}s. "
                    f"UUID: {uid}"
                )

            total_time = round(time.time() - start, 2)
            msg = (
                f"Successfully ingested {count} record(s) to "
                f"{PLATFORM_NAME} in {total_time}s. UUID: {uid}."
            )
            self.logger.info(f"{log_msg} {msg}")
            return PushResult(success=True, message=msg)
        except CortexXDRException as err:
            err_msg = f"Could not ingest data into {self.plugin_name}."
            self.logger.error(
                message=f"{log_msg} {err_msg} UUID: {uid}. Error: {err}",
                details=traceback.format_exc(),
            )
            return PushResult(success=False, message=f"{err_msg} {err}")
        except Exception as err:
            err_msg = f"Unexpected error while ingesting data. UUID: {uid}."
            self.logger.error(
                message=f"{log_msg} {err_msg} Error: {err}",
                details=traceback.format_exc(),
            )
            return PushResult(success=False, message=err_msg)

    def validate_auth(
        self, url: str, api_key: str, compression: str
    ) -> ValidationResult:
        """Validate credentials by sending a small test record.

        Args:
            url (str): HTTP Log Collector URL.
            api_key (str): API Key.
            compression (str): Compression mode.

        Returns:
            ValidationResult: Result with success flag and message.
        """
        payload_str = json.dumps(
            {
                "message": (
                    "Validation call from Netskope Cloud Exchange "
                    f"{PLATFORM_NAME} plugin."
                ),
                "timestamp": int(time.time() * 1000),
            }
        )
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        data = payload_str
        if compression == COMPRESSION_GZIP:
            headers["Content-Encoding"] = "gzip"
            data = gzip_compress(payload_str)

        try:
            self.cortex_xdr_helper.api_helper(
                url=url,
                method="POST",
                headers=headers,
                data=data,
                proxies=self.proxy,
                verify=self.ssl_validation,
                logger_msg="validating authentication parameters",
                is_validation=True,
            )
            msg = (
                f"Validation successful for {MODULE_NAME} "
                f"{PLATFORM_NAME} plugin."
            )
            self.logger.debug(f"{self.log_prefix}: {msg}")
            return ValidationResult(success=True, message=msg)
        except CortexXDRException as exp:
            return ValidationResult(success=False, message=str(exp))
        except Exception as exp:
            err_msg = "Unexpected validation error occurred."
            self.logger.error(
                message=f"{self.log_prefix}: {err_msg} Error: {exp}",
                details=traceback.format_exc(),
            )
            return ValidationResult(
                success=False,
                message=f"{err_msg} Check logs for more details.",
            )

    def validate(self, configuration: dict, value=None) -> ValidationResult:
        """Validate the plugin configuration parameters.

        Args:
            configuration (dict): Configuration parameters dictionary.
            value: Unused by this plugin. Accepted for compatibility
            with the base class's validate(configuration, value)
            signature.

        Returns:
            ValidationResult: Result with success flag and message.
        """
        cortex_xdr_validator = CortexXDRValidator(
            self.logger, self.log_prefix
        )
        validation_err_msg = "Validation error occurred,"

        if configuration.get("transformData", True):
            msg = (
                "The plugin only supports sharing raw JSON logs. Please "
                "disable the 'Transform the raw logs' toggle to save the "
                "configuration."
            )
            self.logger.error(f"{self.log_prefix}: {msg}")
            return ValidationResult(success=False, message=msg)

        url = configuration.get("api_url", "").strip().rstrip("/")
        if not url:
            err_msg = "HTTP Log Collector URL is a required field."
            self.logger.error(
                f"{self.log_prefix}: {validation_err_msg} {err_msg}"
            )
            return ValidationResult(success=False, message=err_msg)
        elif not isinstance(
            url, str
        ) or not cortex_xdr_validator.validate_url(url):
            err_msg = "Invalid HTTP Log Collector URL provided."
            self.logger.error(
                f"{self.log_prefix}: {validation_err_msg} {err_msg}"
            )
            return ValidationResult(success=False, message=err_msg)

        api_key = configuration.get("api_key")
        if not api_key:
            err_msg = "API Key is a required field."
            self.logger.error(
                f"{self.log_prefix}: {validation_err_msg} {err_msg}"
            )
            return ValidationResult(success=False, message=err_msg)
        elif not isinstance(api_key, str):
            err_msg = "Invalid API Key provided."
            self.logger.error(
                f"{self.log_prefix}: {validation_err_msg} {err_msg}"
            )
            return ValidationResult(success=False, message=err_msg)

        compression = configuration.get("compression", "")
        if compression not in (COMPRESSION_GZIP, COMPRESSION_UNCOMPRESSED):
            err_msg = (
                "Compression must be either 'Uncompressed' or 'Gzip', "
                "and must match the setting configured on the Cortex "
                "XDR HTTP Log Collector."
            )
            self.logger.error(
                f"{self.log_prefix}: {validation_err_msg} {err_msg}"
            )
            return ValidationResult(success=False, message=err_msg)

        log_source_identifier = configuration.get(
            "log_source_identifier", ""
        ).strip()
        if not log_source_identifier:
            err_msg = "Log Source Identifier is a required field."
            self.logger.error(
                f"{self.log_prefix}: {validation_err_msg} {err_msg}"
            )
            return ValidationResult(success=False, message=err_msg)

        mappings = self.mappings.get("jsonData", None)
        try:
            mappings = json.loads(mappings)
        except (TypeError, json.JSONDecodeError) as err:
            err_msg = f"Invalid {PLATFORM_NAME} mapping file. Error: {err}"
            self.logger.error(
                f"{self.log_prefix}: {validation_err_msg} {err_msg}"
            )
            return ValidationResult(success=False, message=err_msg)

        if not isinstance(
            mappings, dict
        ) or not cortex_xdr_validator.validate_mappings(mappings):
            err_msg = (
                f"Invalid {PLATFORM_NAME} attribute mapping found in the "
                "configuration parameters."
            )
            self.logger.error(
                f"{self.log_prefix}: {validation_err_msg} {err_msg}"
            )
            return ValidationResult(success=False, message=err_msg)

        return self.validate_auth(
            url=url, api_key=api_key, compression=compression
        )
