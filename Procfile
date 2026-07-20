# Optional process-manager entrypoint. The recommended cross-platform command is
# `python scripts/dev.py`, which also manages child-process shutdown on Windows.
# If Honcho is already installed, `honcho start` runs the same two core services.

server: trailhead --reload --root demo --host 127.0.0.1 --port 1109
client: npm run dev --prefix client
