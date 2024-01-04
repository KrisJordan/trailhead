"""Entrypoint of the Trailhead server."""


def main() -> int:
    """Run the Trailhead server."""
    import argparse
    import uvicorn
    from .app import app

    parser = argparse.ArgumentParser(description="Trailhead Server")

    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    try:
        if args.reload:
            uvicorn.run(
                "trailhead.app:app",
                host="0.0.0.0",
                port=1109,
                reload=True,
                reload_includes=["/workspace/server/src/trailhead"],
                reload_excludes=["/workspace/demo"],
            )
        else:
            print("Starting Trailhead server at http://localhost:1110")
            print("Press Ctrl+C to Stop the Trailhead Server")
            uvicorn.run(app, host="0.0.0.0", port=1110, log_level="error")
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
