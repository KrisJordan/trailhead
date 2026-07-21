# Trailhead server

Trailhead is a local FastAPI server for exploring and running Python modules in
a browser. It supports Python 3.11 or newer on macOS, Windows, and Linux. The
PyPI distribution is named `trailhead-edu`; the import package and command remain
`trailhead`.

Install the command from PyPI in an isolated tool environment with:

```console
uv tool install trailhead-edu
```

For repository development, synchronize the locked environment from the
repository root:

```console
uv sync --project server --locked --extra student
```

The `student` extra supplies the optional data-science and teaching libraries;
the base installation contains only Trailhead's server runtime. Run a project
with:

```console
trailhead --root demo
```

Use `trailhead --help` for host, port, reload, and log-level options. The web
client must be built before creating a release wheel so that `static/index.html`
and `static/assets/` are included as package data.
