"""Allow running as `python -m pz_mod_checker`."""

import sys

from .cli import main

sys.exit(main())
