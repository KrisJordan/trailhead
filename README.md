# Trailhead

Trailhead is a browser-based environment for exploring and running introductory
Python projects. It runs directly on macOS, Windows, and Linux; Docker, a
devcontainer, Caddy, and Honcho are optional and are not part of the native setup.

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 22.12 or newer with npm (Node.js 24 LTS is recommended)

uv installs the pinned Python 3.14 development runtime and manages the project
environment from `server/uv.lock`. Node.js is needed to build or live-reload the
browser client. Once the client has been built into the Python package, a normal
Trailhead run only needs Python 3.11 or newer.

## Native quick start

The bootstrap script uses uv to synchronize `server/.venv`, installs Trailhead in
editable mode, installs the client with `npm ci`, and builds the browser assets.
It works on all three host platforms.

macOS or Linux:

```sh
uv run python scripts/bootstrap.py
uv run --project server python scripts/dev.py
```

Windows PowerShell or Command Prompt:

```powershell
uv run python scripts\bootstrap.py
uv run --project server python scripts\dev.py
```

Open <http://127.0.0.1:1110>. The development runner starts the Python backend on
port 1109 and Vite on port 1110, routes HTTP and WebSocket requests through Vite,
and stops both process trees when you press Ctrl+C. Caddy is not involved.

Add `--student` to the bootstrap command to install the optional notebook,
plotting, data-science, and image packages used by the wider COMP110 environment.
They are kept out of the core server so a native Trailhead install does not depend
on large or system-sensitive scientific/graphics stacks.

By default Trailhead opens the repository's `demo` project. Pass another project
directory, including a path containing spaces, as the first argument:

```sh
uv run --project server python scripts/dev.py /path/to/python-project
```

```powershell
uv run --project server python scripts\dev.py "C:\Users\Student\My Project"
```

Run `scripts/dev.py --help` for host, backend port, frontend port, browser-open,
and reload options.

The local `demo/compstagram.py` module uses an optional template server on port
2100 and Pillow from the student dependencies. Install those dependencies, then
build and launch it with the managed development processes:

```sh
uv run python scripts/bootstrap.py --student
npm ci --prefix compstagram
npm run build --prefix compstagram
uv run --project server python scripts/dev.py --compstagram
```

On Windows, use backslashes in the script paths if desired. Ctrl+C stops the
backend, Vite, and the template server together.

## Run the built application

The bootstrap step also creates a production client build. Run the installed
server directly when live frontend reloading is not needed:

macOS or Linux:

```sh
uv run --project server trailhead --root demo
```

Windows:

```powershell
uv run --project server trailhead --root demo
```

This serves both the API and built client at <http://127.0.0.1:1110>. The command
accepts `--root`, `--host`, `--port`, and `--reload`; see `trailhead --help` for
the complete interface. The relative examples assume the repository root. From
another directory, activate the environment or use the absolute `trailhead`
executable and pass an absolute project path to `--root`. Use `--host 0.0.0.0`
only when Trailhead intentionally needs to be reachable from other machines.

## Run pytest modules in the browser

Trailhead recognizes standard pytest module names (`test_*.py` and
`*_test.py`) as well as modules with top-level `test_*` functions or `Test*`
classes. Opening one selects a **Tests** tab that collects the module's tests
and provides controls to run one test, run the full module, or cancel an active
run. Parametrized cases retain their exact pytest node IDs.

Failures distinguish collection, fixture setup, test call, and fixture teardown
errors. Assertion details and captured standard output, standard error, and logs
are available directly in each test result.

The **Autorun on changes** toggle is off by default and is saved in the browser.
When enabled, changes to any Python file in the project schedule a debounced
rerun of the open test module. Changes detected during an active run are
coalesced into one follow-up run, and repeated rapid reruns automatically pause
autorun to prevent loops from tests that write Python source files.

## Network access and browser origins

Trailhead runs arbitrary Python from the selected project and does not provide
user authentication. Keep it on loopback unless every machine that can reach it
is trusted. Browser WebSocket requests use exact-origin checks: non-browser
clients may omit `Origin`, but wildcards are never accepted.

The development runner automatically allows the frontend URL for a concrete
`--host`. When binding all interfaces, explicitly list each browser-visible LAN
origin (and ensure the host firewall is configured appropriately):

```sh
uv run --project server python scripts/dev.py --host 0.0.0.0 \
  --allow-origin http://192.168.1.50:1110
```

The installed server accepts the same repeatable option. Reverse proxies and
HTTPS deployments must allow their exact public origin, for example
`--allow-origin https://trailhead.example.edu`. Exact origins can instead be
supplied as a comma-separated `TRAILHEAD_ALLOWED_ORIGINS` environment variable.
Loopback same-origin access and the standard local Vite proxy work without extra
configuration.

## Manual setup

If a scripted bootstrap is undesirable, the equivalent commands on all platforms
are:

```sh
uv sync --project server --locked
npm ci --prefix client
npm run build --prefix client
```

Add `--extra student` to `uv sync` for the optional teaching and data-science
packages. uv installs the project as editable by default; environment activation
is unnecessary when commands are run through `uv run --project server`.

## Development and verification

```sh
# Python tests, linting, formatting, and type checking
uv run --project server --locked python -m pytest server/tests
uv run --project server --locked ruff check --config server/pyproject.toml \
  server/src server/tests scripts bin/build-trailhead
uv run --project server --locked ruff format --check \
  --config server/pyproject.toml \
  server/src server/tests scripts bin/build-trailhead
uv run --project server --locked pyright --project pyrightconfig.json

# Browser client checks
npm run typecheck --prefix client
npm test --prefix client
npm run build --prefix client

# Optional GUI template builds
npm ci --prefix compstagram
npm run build --prefix compstagram
npm ci --prefix turtle
npm run build --prefix turtle
```

The legacy unpacked distribution used by `Dockerfile.students` can be produced
portably with:

```sh
uv run --project server python bin/build-trailhead
```

or on Windows:

```powershell
uv run --project server python bin\build-trailhead
```

The build script uses Python filesystem APIs rather than Unix commands, fails on
the first unsuccessful build step, and writes `dist/trailhead`.

## Ports and architecture

| Mode | Browser URL | Backend | Routing |
| --- | --- | --- | --- |
| Native development | `127.0.0.1:1110` | `127.0.0.1:1109` | Vite proxy |
| Built application | `127.0.0.1:1110` | same process | FastAPI static files |

The backend starts student modules with the same Python interpreter that launched
Trailhead. Paths, child-process pipes, file watching, and shutdown are handled by
Python APIs that work across macOS, Windows, and Linux.

## Troubleshooting

- `Node.js and npm were not found`: install Node.js 22.12+ (or Node.js 24 LTS), open a
  new terminal so `PATH` is refreshed, then rerun the bootstrap script.
- `Address already in use`: stop the process using port 1110 or pass alternate
  ports to `scripts/dev.py`. For the built server, pass `--port`.
- A page reports that browser assets are missing: run `npm ci --prefix client`
  followed by `npm run build --prefix client`.
- uv cannot find a compatible Python: run `uv python install 3.14`, then rerun
  the bootstrap script.
- To reset only the local Python environment, remove `server/.venv` and run
  `uv sync --project server --locked`. Client dependencies can be recreated at
  any time with `npm ci`.

## Optional Docker workflow

The existing Dockerfiles and `.devcontainer` remain available for teams that want
them, but native development is the primary workflow. To create the student image,
first build the unpacked distribution as shown above and then run the existing
multi-architecture image command:

```sh
export TAG=0.2.0
docker buildx build \
  --push \
  --platform linux/arm64,linux/amd64 \
  --tag krisjordan/trailhead:$TAG \
  --file Dockerfile.students \
  .
```
