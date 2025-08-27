"""
Utilities for file I/O operations.
Ensures parent directories exist for output files.
"""
import pathlib

def ensure_parent(path: pathlib.Path):
    """Create parent directories for the given path if they do not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)