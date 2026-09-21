"""Keep Chinese command-line messages readable on Windows and redirected logs."""
import sys


def configure_console():
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
