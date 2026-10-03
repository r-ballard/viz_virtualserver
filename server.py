"""Compatibility import for viz_virtualserver.server."""

import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("viz_virtualserver.server")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("viz_virtualserver.server:app", host="127.0.0.1", port=5699)
