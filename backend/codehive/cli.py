"""Codehive CLI with subcommands."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-platform autonomous coding agent with sub-agent orchestration",
    )
    subparsers = parser.add_subparsers(dest="command")

    # serve subcommand
    serve_parser = subparsers.add_parser("serve", help="Start the codehive API server")
    serve_parser.add_argument("--host", type=str, default=None, help="Bind host")
    serve_parser.add_argument("--port", type=int, default=None, help="Bind port")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    if args.command == "serve":
        _serve(args)
    else:
        parser.print_help()


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    from codehive.config import Settings

    settings = Settings()
    host = args.host or settings.host
    port = args.port or settings.port
    reload = args.reload or settings.debug

    uvicorn.run(
        "codehive.api.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


if __name__ == "__main__":
    main()
