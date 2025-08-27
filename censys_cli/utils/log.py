"""
Structured logging utilities for the Censys CLI.
Outputs JSON logs to file and human-readable logs to stderr.
"""
import json
import logging
import sys

class JsonFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""
    def format(self, record):
        data = {
            "level": record.levelname.lower(),
            "msg": record.getMessage(),
        }
        if hasattr(record, "asctime"):
            data["time"] = record.asctime
        for k, v in getattr(record, "__dict__", {}).items():
            if k in ("msg", "args", "name", "levelname", "levelno", "pathname",
                     "filename", "module", "exc_info", "exc_text", "stack_info",
                     "lineno", "funcName", "created", "msecs", "relativeCreated",
                     "thread", "threadName", "processName", "process"):
                continue
            if k not in data and not k.startswith("_"):
                data[k] = v
        return json.dumps(data, ensure_ascii=False)

def get_logger(name: str, logfile: str, verbose: bool = False):
    """Configure a logger with file and stderr handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers = []

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.DEBUG if verbose else logging.INFO)
    sh.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(sh)

    fh = logging.FileHandler(logfile, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(JsonFormatter())
    logger.addHandler(fh)

    return logger