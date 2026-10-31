"""JSON-lines logging, so LLM latency, retries, and session events are machine-readable."""
import json
import logging
import os
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # httpx logs every request URL at INFO; keep only our own summaries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # One line per processed frame: angles, visibility, phase observations, counter state
    if os.getenv("FRAME_TRACE") == "1":
        logging.getLogger("rehabflow.frames").setLevel(logging.DEBUG)
