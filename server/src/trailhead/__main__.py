import argparse
import uvicorn
from .app import app


def main() -> None:
    """Run the Trailhead server."""
    parser = argparse.ArgumentParser(description="Trailhead Server")

    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

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
        uvicorn.run(app, host="0.0.0.0", port=1110, log_level="error")
