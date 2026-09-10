#!/usr/bin/env python3
"""Executable entry point for bs-sql-organize."""

import sys
from pathlib import Path

# Ensure package directory is on sys.path when executed directly
package_root = Path(__file__).resolve().parents[1]
if str(package_root) not in sys.path:
    sys.path.insert(0, str(package_root))

from bs_database_script_organizer.cli import main
from bs_database_script_organizer.organizer import OrganizeError

if __name__ == "__main__":
    try:
        sys.exit(main())
    except OrganizeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
