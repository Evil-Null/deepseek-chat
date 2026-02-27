import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="dschat",
        description="DS Chat — Professional DeepSeek AI Terminal Client",
    )
    parser.add_argument(
        "-v", "--version", action="store_true", help="Show version and exit"
    )
    parser.add_argument(
        "-q", "--question", type=str, help="Ask a question and exit (inline mode)"
    )
    parser.add_argument(
        "-m", "--model", type=str, help="Model to use (deepseek-chat, deepseek-reasoner)"
    )

    args = parser.parse_args()

    if args.version:
        from . import __version__
        print(f"DS Chat v{__version__}")
        return

    try:
        from .app import ChatApp

        app = ChatApp()

        # Override model if specified
        if args.model:
            from .config import MODELS
            if args.model in MODELS:
                app.current_model = args.model
            else:
                valid = ", ".join(MODELS.keys())
                print(f"  Unknown model: {args.model}. Valid: {valid}", file=sys.stderr)
                sys.exit(1)

        if args.question:
            app.run_inline(args.question)
        else:
            app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        _handle_fatal_error(e)
        sys.exit(1)


def _handle_fatal_error(error: Exception):
    """Show user-friendly error messages for common startup failures."""
    from pydantic import ValidationError

    if isinstance(error, ValidationError):
        print("\n  Configuration error:", file=sys.stderr)
        for err in error.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            msg = err["msg"]
            if "DEEPSEEK_API_KEY" in field or "api_key" in field:
                print(
                    "  - Missing API key. Set DEEPSEEK_API_KEY in .env or environment.",
                    file=sys.stderr,
                )
            else:
                print(f"  - {field}: {msg}", file=sys.stderr)
        print(file=sys.stderr)
    else:
        print(f"\n  Fatal error: {error}\n", file=sys.stderr)


if __name__ == "__main__":
    main()
