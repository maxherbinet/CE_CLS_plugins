"""Unit tests for the Palo Alto Cortex XDR CLS plugin.

Run with: PYTHONPATH=. pytest palo_alto_cortex_xdr/tests -v
"""
import gzip
import json

import pytest


RAW_ALERTS = [
    {
        "timestamp": 1700000000,
        "alert_name": "DLP violation",
        "user": "a@b.com",
    },
    {},  # empty record, must be filtered out
    {"timestamp": 1700000001, "alert_name": "Malware detected"},
]


def test_validate_success(make_plugin, fake_response, mocker):
    """Valid configuration + a 200 response should validate."""
    plugin = make_plugin()
    mock_req = mocker.patch(
        "requests.request", return_value=fake_response(mocker, 200)
    )
    result = plugin.validate(plugin.configuration)

    assert result.success is True
    headers = mock_req.call_args.kwargs["headers"]
    assert headers["Authorization"] == "fake-token-123"
    assert "Bearer" not in headers["Authorization"]
    assert "Content-Encoding" not in headers


def test_validate_rejects_transform_data_true(make_plugin):
    """The plugin only supports raw JSON; transformData=True must
    fail validation with a clear message."""
    plugin = make_plugin({"transformData": True})
    result = plugin.validate(plugin.configuration)

    assert result.success is False
    assert "raw JSON" in result.message


def test_validate_rejects_missing_url(make_plugin):
    plugin = make_plugin({"api_url": ""})
    result = plugin.validate(plugin.configuration)

    assert result.success is False
    assert "URL" in result.message


def test_validate_rejects_missing_api_key(make_plugin):
    plugin = make_plugin({"api_key": ""})
    result = plugin.validate(plugin.configuration)

    assert result.success is False
    assert "API Key" in result.message


def test_validate_accepts_base_class_signature(
    make_plugin, fake_response, mocker
):
    """Regression test: the real CLS PluginBase.validate() abstract
    method signature is validate(self, configuration, value) - two
    positional args. Calling with only one would raise TypeError if
    this plugin's override didn't also accept a second parameter."""
    plugin = make_plugin()
    mocker.patch("requests.request", return_value=fake_response(mocker, 200))
    result = plugin.validate(plugin.configuration, None)

    assert result.success is True


def test_validate_rejects_invalid_compression(make_plugin):
    plugin = make_plugin({"compression": "brotli"})
    result = plugin.validate(plugin.configuration)

    assert result.success is False
    assert "Compression" in result.message


def test_transform_filters_empty_records(make_plugin):
    plugin = make_plugin()
    transformed = plugin.transform(RAW_ALERTS, "alerts", "dlp")

    assert len(transformed) == 2
    assert all(record for record in transformed)


def test_transform_rejects_transform_data_true(make_plugin):
    plugin = make_plugin({"transformData": True})
    with pytest.raises(Exception, match="raw JSON"):
        plugin.transform(RAW_ALERTS, "alerts", "dlp")


def test_push_empty_data_is_a_noop_success(make_plugin, mocker):
    plugin = make_plugin()
    mock_req = mocker.patch("requests.request")
    result = plugin.push([], "alerts", "dlp")

    assert result.success is True
    mock_req.assert_not_called()


def test_push_uncompressed_sends_raw_ndjson(
    make_plugin, fake_response, mocker
):
    """Cortex XDR expects newline-delimited raw JSON with no envelope,
    Authorization with no 'Bearer' prefix, and no Content-Encoding
    header when uncompressed."""
    plugin = make_plugin()
    mock_req = mocker.patch(
        "requests.request", return_value=fake_response(mocker, 200)
    )
    transformed = plugin.transform(RAW_ALERTS, "alerts", "dlp")
    result = plugin.push(transformed, "alerts", "dlp")

    assert result.success is True
    headers = mock_req.call_args.kwargs["headers"]
    assert headers["Authorization"] == "fake-token-123"
    assert "Content-Encoding" not in headers

    sent_data = mock_req.call_args.kwargs["data"]
    lines = sent_data.split("\n")
    assert len(lines) == 2
    parsed = json.loads(lines[0])
    assert "event" not in parsed  # no Splunk-HEC-style envelope
    assert parsed["log_source_identifier"] == "Netskope Cloud Exchange"


def test_push_gzip_compresses_body_and_sets_header(
    make_plugin, fake_response, mocker
):
    plugin = make_plugin({"compression": "gzip"})
    mock_req = mocker.patch(
        "requests.request", return_value=fake_response(mocker, 200)
    )
    transformed = plugin.transform(RAW_ALERTS, "alerts", "dlp")
    result = plugin.push(transformed, "alerts", "dlp")

    assert result.success is True
    headers = mock_req.call_args.kwargs["headers"]
    assert headers["Content-Encoding"] == "gzip"

    sent_data = mock_req.call_args.kwargs["data"]
    decompressed = gzip.decompress(sent_data).decode("utf-8")
    assert len(decompressed.split("\n")) == 2


def test_push_500_is_surfaced_as_compression_mismatch(
    make_plugin, fake_response, mocker
):
    """Cortex XDR's 500 specifically means a format/compression
    mismatch between the request and the collector config - the
    error message should say so, not a generic failure."""
    plugin = make_plugin()
    mocker.patch(
        "requests.request",
        return_value=fake_response(
            mocker,
            500,
            {"error": "error processing request"},
        ),
    )
    transformed = plugin.transform(RAW_ALERTS, "alerts", "dlp")
    result = plugin.push(transformed, "alerts", "dlp")

    assert result.success is False
    assert "compression" in result.message.lower()


def test_push_retries_on_429_then_succeeds(
    make_plugin, fake_response, mocker
):
    plugin = make_plugin()
    mocker.patch("time.sleep")  # don't actually wait in tests
    responses = [
        fake_response(mocker, 429),
        fake_response(mocker, 200),
    ]
    mocker.patch("requests.request", side_effect=responses)
    transformed = plugin.transform(RAW_ALERTS, "alerts", "dlp")
    result = plugin.push(transformed, "alerts", "dlp")

    assert result.success is True


def test_push_skips_oversized_record_and_notifies(
    make_plugin, fake_response, mocker
):
    plugin = make_plugin()
    mocker.patch(
        "requests.request", return_value=fake_response(mocker, 200)
    )
    oversized_record = {"timestamp": 1, "blob": "x" * (6 * 1024 * 1024)}
    transformed = plugin.transform(
        [oversized_record, {"timestamp": 2, "ok": True}],
        "alerts",
        "dlp",
    )
    result = plugin.push(transformed, "alerts", "dlp")

    assert result.success is True
    plugin.notifier.error.assert_called_once()
