"""Shared pytest fixtures for the Palo Alto Cortex XDR plugin tests.

Inserts the local SDK stub onto sys.path before the plugin module is
imported, since the real netskope.integrations.cls.plugin_base is only
available inside a live Cloud Exchange instance.
"""
import json
import os
import sys

import pytest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_DIR = os.path.dirname(_TESTS_DIR)
_REPO_ROOT = os.path.dirname(_PLUGIN_DIR)

sys.path.insert(0, os.path.join(_TESTS_DIR, "sdk_stub"))
sys.path.insert(0, _REPO_ROOT)


class StubLogger:
    """Matches Netskope's logger interface: message positional-or-
    keyword, optional details= kwarg."""

    def _log(self, level, message, details=None):
        print(f"[{level}] {message}")
        if details:
            print(f"  details: {details}")

    def debug(self, message, details=None):
        self._log("DEBUG", message, details)

    def info(self, message, details=None):
        self._log("INFO", message, details)

    def warn(self, message, details=None):
        self._log("WARN", message, details)

    def error(self, message, details=None):
        self._log("ERROR", message, details)


@pytest.fixture
def manifest():
    with open(os.path.join(_PLUGIN_DIR, "manifest.json")) as f:
        return json.load(f)


@pytest.fixture
def mappings():
    with open(os.path.join(_PLUGIN_DIR, "mappings.json")) as f:
        return json.load(f)


@pytest.fixture
def common_config():
    return {
        "transformData": False,
        "api_url": (
            "https://api-fake-tenant.xdr.paloaltonetworks.com"
            "/logs/v1/event"
        ),
        "api_key": "fake-token-123",
        "compression": "uncompressed",
        "log_source_identifier": "Netskope Cloud Exchange",
    }


@pytest.fixture
def make_plugin(manifest, mappings, common_config, mocker):
    """Factory fixture: build a CortexXDRPlugin instance with the
    given configuration overrides applied on top of common_config."""
    from palo_alto_cortex_xdr.main import CortexXDRPlugin

    CortexXDRPlugin.metadata = manifest

    def _make(config_overrides=None):
        configuration = dict(common_config)
        configuration.update(config_overrides or {})
        return CortexXDRPlugin(
            "test-config",
            configuration=configuration,
            logger=StubLogger(),
            source="test-source",
            mappings=mappings,
            notifier=mocker.MagicMock(),
            proxy={},
            ssl_validation=True,
        )

    return _make


@pytest.fixture
def fake_response():
    def _make(mocker, status_code=200, body=None):
        resp = mocker.MagicMock()
        resp.status_code = status_code
        resp.text = json.dumps(body or {"error": "false"})
        resp.json.return_value = body or {"error": "false"}
        resp.headers = {}
        return resp

    return _make
