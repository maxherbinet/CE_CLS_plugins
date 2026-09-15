"""Palo Alto Cortex XDR Plugin Constants."""

PLATFORM_NAME = "Palo Alto Cortex XDR"
MODULE_NAME = "CLS"
PLUGIN_VERSION = "1.0.0"

MAX_RETRY_COUNT = 4
DEFAULT_WAIT_TIME = 60
MAX_RETRY_AFTER_IN_MIN = 5
MAX_WAIT_TIME = 300

# Cortex XDR HTTP Log Collector limits (per Palo Alto documentation):
# total request body up to 10 MiB (1 MiB recommended), each record <= 5 MB.
TARGET_CHUNK_SIZE_BYTES = 1_000_000  # ~1 MiB, PAN's recommended request size
MAX_REQUEST_SIZE_BYTES = 10 * 1024 * 1024  # 10 MiB hard limit
MAX_RECORD_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB per-record hard limit

COMPRESSION_GZIP = "gzip"
COMPRESSION_UNCOMPRESSED = "uncompressed"

CE_LOG_SOURCE_IDENTIFIER = "Netskope Cloud Exchange"
