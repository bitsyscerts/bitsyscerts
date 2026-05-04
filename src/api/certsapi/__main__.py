"""CLI entrypoint for the BitsyCerts read-only REST API."""

from __future__ import annotations

import argparse

import uvicorn


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="certsapi",
        description="BitsyCerts read-only REST API",
    )
    parser.set_defaults(func=lambda _: parser.print_help())

    sub = parser.add_subparsers(metavar="<command>")

    serve = sub.add_parser("serve", help="Start the HTTP server")
    serve.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind host (default: 0.0.0.0)",  # noqa: S104
    )
    serve.add_argument(
        "--port", type=int, default=8000, help="Bind port (default: 8000)"
    )
    serve.add_argument(
        "--reload", action="store_true", help="Enable auto-reload (development only)"
    )
    serve.add_argument(
        "--workers", type=int, default=1, help="Number of worker processes (default: 1)"
    )
    serve.set_defaults(func=_serve)

    return parser


def _serve(args: argparse.Namespace) -> None:
    print(f"Starting certsapi on http://{args.host}:{args.port} — press Ctrl+C to stop")
    try:
        uvicorn.run(
            "certsapi.app:create_app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers,
            factory=True,
        )
    except KeyboardInterrupt:
        print("\nStopping certsapi...")


def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate command."""
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
