"""Keep the interactive initialization console open for installed users."""
from .windows_exporter import main


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            input("\nPress Enter to close this initialization window...")
        except EOFError:
            pass
