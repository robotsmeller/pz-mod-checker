"""Allow running as `python -m src`."""

import sys

from .cli import main

sys.exit(main())
