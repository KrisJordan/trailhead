import argparse
import uvicorn
from .app import app


def main() -> int:
    parser = argparse.ArgumentParser(description="Trailhead Server")

    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    if args.reload:
        print("Running uvicorn with autoreload")
        return uvicorn.run(
            "trailhead.app:app",
            host="0.0.0.0",
            port=1109,
            reload=True,
            reload_includes=["/workspace/server/src/trailhead"],
            reload_excludes=["/workspace/demo"],
        )
    else:
        return uvicorn.run(app, host="0.0.0.0", port=1110)


if __name__ == "__main__":
    main()
