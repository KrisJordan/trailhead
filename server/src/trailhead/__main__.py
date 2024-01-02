import uvicorn
from .app import app


def main() -> int:
    return uvicorn.run(app, host="0.0.0.0", port=1100)


if __name__ == "__main__":
    main()
