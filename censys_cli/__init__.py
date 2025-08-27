"""
Package initializer for the `censys_cli` package.

This module exposes the primary classes and functions for ease of access:

* ``CensysClient`` – API client for Censys Search v2.
* ``Analytics`` – Collects and summarises CAPTCHA bypass metrics.
* ``MLPredictor`` – Machine‑learning predictor for choosing the best CAPTCHA bypass method.
* ``FlattenHelper`` – Utility for flattening nested JSON structures.
* ``main``, ``parse_args``, ``run_browser_fallback`` – Entry points for the command‑line interface.
"""

from .client import CensysClient
from .analytics import Analytics
from .ml_predictor import MLPredictor
from .utils.flatten import FlattenHelper
from . import main  # import the CLI module
from .main import parse_args, run_browser_fallback  # import functions for convenience

# Expose a canonical name for the CLI main function
cli_main = main.main

__all__ = [
    "CensysClient",
    "Analytics",
    "MLPredictor",
    "FlattenHelper",
    "main",
    "cli_main",
    "parse_args",
    "run_browser_fallback",
]