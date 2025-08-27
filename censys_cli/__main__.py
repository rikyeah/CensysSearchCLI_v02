"""Entry point for the censys_cli package when executed as a module.

This allows the command ``python -m censys_cli`` to run the CLI directly.
"""
from .main import main

if __name__ == "__main__":
    main()