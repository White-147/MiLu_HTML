# -*- coding: utf-8 -*-
"""Allow running milu via ``python -m milu``."""
from .cli.main import cli

if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
