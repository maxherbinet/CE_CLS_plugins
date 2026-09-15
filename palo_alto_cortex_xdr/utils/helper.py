"""Palo Alto Cortex XDR Plugin Helper."""

import time
import traceback
from typing import Dict, Union

import requests

from .constant import (
    DEFAULT_WAIT_TIME,
    MAX_RETRY_AFTER_IN_MIN,
    MAX_RETRY_COUNT,
    MAX_WAIT_TIME,
    MODULE_NAME,
    PLATFORM_NAME,
)
from .exception import CortexXDRException


class CortexXDRPluginHelper:
    """Helper class for Palo Alto Cortex XDR plugin HTTP operations."""

    def __init__(
        self,
        logger,
        log_prefix: str,
        plugin_name: str,
        plugin_version: str,
    ):
        """Initialize the helper.

        Args:
            logger (Logger): Logger object.
            log_prefix (str): Log prefix.
            plugin_name (str): Plugin name.
            plugin_version (str): Plugin version.
        """
        self.logger = logger
        self.log_prefix = log_prefix
        self.plugin_name = plugin_name
        self.plugin_version = plugin_version

    def _add_user_agent(self, headers: Union[Dict, None] = None) -> Dict:
        """Add User-Agent header.

        Format: netskope-ce-<module>-<plugin_name>-<version>

        Args:
            headers (Dict, optional): Existing headers dict.

        Returns:
            Dict: Headers dict with User-Agent added.
        """
        headers = headers or {}
        module_slug = MODULE_NAME.lower()
        plugin_slug = self.plugin_name.lower().replace(" ", "-")
        headers["User-Agent"] = (
            f"netskope-ce-{module_slug}-{plugin_slug}-{self.plugin_version}"
        )
        return headers

    def handle_error(self, response, logger_msg: str, is_validation: bool):
        """Interpret Cortex XDR HTTP Log Collector response codes.

        Cortex XDR documents the following codes for the HTTP Log
        Collector endpoint: 200 (success), 401 (unauthorized/collector
        disabled), 404 (wrong URL), 413 (payload too large, >10 MB),
        429 (rate limit, >400 req/sec/customer/endpoint), 500
        (log format/compression mismatch between request and the
        collector's configuration).

        Args:
            response: The requests Response object.
            logger_msg (str): Description of the operation for logging.
            is_validation (bool): Whether this call is a validation check.

        Returns:
            dict: Parsed JSON response body, if any.
        """
        status_code = response.status_code

        if status_code == 200:
            try:
                return response.json()
            except ValueError:
                return {}

        err_map = {
            401: (
                "Unauthorized. Verify the API Key, and confirm the "
                "HTTP Log Collector is not deleted or disabled in "
                "Cortex XDR."
            ),
            404: (
                "Not Found. Verify the HTTP Log Collector URL is "
                "correct."
            ),
            413: (
                "Payload Too Large. The request exceeded Cortex XDR's "
                "10 MB request size limit."
            ),
            500: (
                "Cortex XDR failed to process the request. This "
                "usually means the 'Compression' configuration "
                "parameter (gzip/uncompressed) does not match the "
                "Compression setting on the Cortex XDR HTTP Log "
                "Collector, or the Log Format configured on the "
                "collector is not JSON."
            ),
        }

        base_msg = err_map.get(
            status_code,
            f"Received unexpected HTTP status code {status_code}.",
        )
        err_msg = f"Error occurred while {logger_msg}. {base_msg}"
        self.logger.error(
            message=f"{self.log_prefix}: {err_msg}",
            details=f"API response: {response.text}",
        )
        if is_validation:
            raise CortexXDRException(base_msg)
        raise CortexXDRException(err_msg)

    def api_helper(
        self,
        logger_msg: str,
        url: str,
        method: str,
        data=None,
        headers=None,
        verify: bool = True,
        proxies=None,
        is_validation: bool = False,
    ):
        """Make an HTTP request to Cortex XDR with retry handling.

        Args:
            logger_msg (str): Description of the operation for logging.
            url (str): API endpoint.
            method (str): HTTP method.
            data (Any, optional): Request body.
            headers (Dict, optional): Request headers.
            verify (bool, optional): Verify SSL. Defaults to True.
            proxies (Dict, optional): Proxies. Defaults to None.
            is_validation (bool, optional): Whether this is a validation
            call. Defaults to False.

        Returns:
            dict: Parsed JSON response body, if any.
        """
        headers = self._add_user_agent(headers)
        try:
            for retry_counter in range(MAX_RETRY_COUNT):
                response = requests.request(
                    url=url,
                    method=method,
                    data=data,
                    headers=headers,
                    verify=verify,
                    proxies=proxies,
                    timeout=30,
                )
                status_code = response.status_code
                self.logger.debug(
                    f"{self.log_prefix}: Received API response for "
                    f"{logger_msg}. Status Code={status_code}."
                )

                if status_code == 429 or 500 <= status_code < 600:
                    if status_code == 500:
                        # 500 from Cortex XDR means a format/compression
                        # mismatch, not a transient server error -
                        # retrying will not help.
                        return self.handle_error(
                            response, logger_msg, is_validation
                        )
                    if retry_counter == MAX_RETRY_COUNT - 1:
                        err_msg = (
                            f"Received exit code {status_code} while "
                            f"{logger_msg}. Max retries exceeded."
                        )
                        self.logger.error(
                            message=f"{self.log_prefix}: {err_msg}",
                            details=str(response.text),
                        )
                        raise CortexXDRException(err_msg)

                    retry_after = response.headers.get("Retry-After")
                    if retry_after is None:
                        wait_time = DEFAULT_WAIT_TIME
                    else:
                        wait_time = int(retry_after)
                        if wait_time > MAX_WAIT_TIME:
                            err_msg = (
                                "'Retry-After' value received from "
                                f"response headers while {logger_msg} "
                                f"is greater than {MAX_RETRY_AFTER_IN_MIN}"
                                " minutes hence returning status code "
                                f"{status_code}."
                            )
                            self.logger.error(
                                message=f"{self.log_prefix}: {err_msg}"
                            )
                            raise CortexXDRException(err_msg)

                    self.logger.error(
                        message=(
                            f"{self.log_prefix}: Received response code "
                            f"{status_code} while {logger_msg}. Retrying "
                            f"after {wait_time} seconds. "
                            f"{MAX_RETRY_COUNT - 1 - retry_counter} "
                            "retries remaining."
                        ),
                        details=f"API response: {response.text}",
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    return self.handle_error(
                        response, logger_msg, is_validation
                    )
        except CortexXDRException:
            raise
        except requests.exceptions.ReadTimeout as error:
            err_msg = f"Read Timeout error occurred while {logger_msg}."
            self.logger.error(
                message=f"{self.log_prefix}: {err_msg} Error: {error}",
                details=traceback.format_exc(),
            )
            raise CortexXDRException(err_msg)
        except requests.exceptions.ProxyError as error:
            err_msg = (
                f"Proxy error occurred while {logger_msg}. Verify the "
                "proxy configuration provided."
            )
            self.logger.error(
                message=f"{self.log_prefix}: {err_msg} Error: {error}",
                details=traceback.format_exc(),
            )
            raise CortexXDRException(err_msg)
        except requests.exceptions.ConnectionError as error:
            err_msg = (
                f"Unable to establish connection with {PLATFORM_NAME} "
                f"while {logger_msg}. Verify the HTTP Log Collector URL "
                "and network/proxy configuration."
            )
            self.logger.error(
                message=f"{self.log_prefix}: {err_msg} Error: {error}",
                details=traceback.format_exc(),
            )
            raise CortexXDRException(err_msg)
        except Exception as exp:
            err_msg = f"Unexpected error occurred while {logger_msg}."
            self.logger.error(
                message=f"{self.log_prefix}: {err_msg} Error: {exp}",
                details=traceback.format_exc(),
            )
            raise CortexXDRException(err_msg)
