"""Palo Alto Cortex XDR Plugin Utilities."""

import gzip
import json
import sys
from typing import List, Tuple

from .constant import MAX_RECORD_SIZE_BYTES, TARGET_CHUNK_SIZE_BYTES
from .exception import MappingValidationError


def get_cortex_xdr_mappings(mappings: dict, data_type: str) -> tuple:
    """Return the mapping tuple to be applied to raw data.

    self.mappings may be provided by the CE core either already merged
    with the parsed contents of its 'jsonData' field (so 'taxonomy' is
    directly accessible), or as the raw {"name", "jsonData", "isDefault"}
    record (as stored in mappings.json) requiring 'jsonData' to be
    parsed first. Both shapes are supported defensively here since the
    exact runtime shape is not independently verified.

    Args:
        mappings (dict): Mapping dict provided by the CE core.
        data_type (str): Data type (only "json" is supported by this
        plugin).

    Returns:
        tuple: (delimiter, cef_version, taxonomy dict)

    Raises:
        MappingValidationError: If the mapping dict is missing required
        keys for the given data_type.
    """
    resolved = mappings
    if "taxonomy" not in resolved and "jsonData" in resolved:
        try:
            resolved = json.loads(resolved["jsonData"])
        except (TypeError, json.JSONDecodeError) as err:
            raise MappingValidationError(
                f"Could not parse mapping file's jsonData. Error: {err}"
            )

    try:
        resolved["taxonomy"][data_type]
    except KeyError as err:
        raise MappingValidationError(
            f"Mapping file does not contain taxonomy for '{data_type}'. "
            f"Error: {err}"
        )
    return (
        resolved.get("delimiter"),
        resolved.get("cef_version"),
        resolved["taxonomy"],
    )


def filter_events(events: List) -> Tuple[int, List]:
    """Filter out empty records from the raw event list.

    Args:
        events (List): List of raw event/alert dicts.

    Returns:
        Tuple[int, List]: Count of skipped (empty) records, and the
        filtered list of records.
    """
    skipped_empty = 0
    data = []
    for event in events:
        if event:
            data.append(event)
        else:
            skipped_empty += 1
    return skipped_empty, data


def split_into_size(
    transformed_data: List[dict], log_source_identifier: str
) -> Tuple[List[List[str]], int]:
    """Split transformed events into chunks sized for Cortex XDR.

    Cortex XDR's HTTP Log Collector accepts a request body of
    newline-delimited raw JSON objects (no envelope), up to 10 MiB per
    request (1 MiB recommended), with each individual record capped at
    5 MB.

    Args:
        transformed_data (List[dict]): List of mapped event/alert dicts.
        log_source_identifier (str): Value to tag each record with.

    Returns:
        Tuple[List[List[str]], int]: List of chunks (each a list of
        JSON-encoded record strings), and the count of records skipped
        for exceeding the per-record size limit.
    """
    result = []
    current_part = []
    current_size_bytes = 0
    skipped_oversized = 0

    for record in transformed_data:
        if isinstance(record, dict):
            record.setdefault(
                "log_source_identifier", log_source_identifier
            )
        record_str = json.dumps(record)
        record_size_bytes = sys.getsizeof(record_str)

        if record_size_bytes > MAX_RECORD_SIZE_BYTES:
            skipped_oversized += 1
            continue

        if (
            current_size_bytes + record_size_bytes
            >= TARGET_CHUNK_SIZE_BYTES
            and current_part
        ):
            result.append(current_part)
            current_part = []
            current_size_bytes = 0

        current_part.append(record_str)
        current_size_bytes += record_size_bytes

    if current_part:
        result.append(current_part)

    return result, skipped_oversized


def gzip_compress(payload_str: str) -> bytes:
    """Gzip-compress a payload string.

    Args:
        payload_str (str): The newline-delimited JSON payload.

    Returns:
        bytes: Gzip-compressed payload.
    """
    return gzip.compress(payload_str.encode("utf-8"))
