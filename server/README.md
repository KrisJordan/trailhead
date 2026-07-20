# Trailhead server

Trailhead is a local FastAPI server for exploring and running Python modules in
a browser. It supports Python 3.11 or newer on macOS, Windows, and Linux.

From the repository root, install it in a virtual environment with:

```console
python -m pip install -e "server[dev,student]"
```

The `student` extra supplies the optional data-science and teaching libraries;
the base install contains only Trailhead's server runtime. Run a project with:

```console
trailhead --root demo
```

Use `trailhead --help` for host, port, reload, and log-level options. The web
client must be built before creating a release wheel so that `static/index.html`
and `static/assets/` are included as package data.
