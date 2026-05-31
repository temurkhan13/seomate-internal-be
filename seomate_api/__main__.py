"""Launch SEOMATE API as ``python -m seomate_api``.

Forces uvicorn to use ``SelectorEventLoop`` via a custom loop-factory
import string. Setting an asyncio event-loop *policy* before uvicorn
starts is not enough: as of uvicorn 0.46, the default loop factory
hard-codes ``asyncio.ProactorEventLoop`` on Windows regardless of any
policy. Passing our own factory is the supported override.

CLI flags forwarded via env vars:

    UVICORN_HOST       (default 127.0.0.1)
    UVICORN_PORT       (default 8000)
    UVICORN_RELOAD     ("1" enables --reload)
    UVICORN_LOG_LEVEL  (default info)
"""
from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "seomate_api.main:app",
        host=os.environ.get("UVICORN_HOST", "127.0.0.1"),
        port=int(os.environ.get("UVICORN_PORT", "8000")),
        reload=os.environ.get("UVICORN_RELOAD", "0") == "1",
        log_level=os.environ.get("UVICORN_LOG_LEVEL", "info"),
        loop="seomate_api.loop:selector_loop_factory",
    )


if __name__ == "__main__":
    main()
