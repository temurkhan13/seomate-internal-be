"""Custom uvicorn loop factory.

uvicorn 0.46+'s default ``asyncio_loop_factory`` hard-codes
``asyncio.ProactorEventLoop`` on Windows, which is incompatible with
psycopg's async mode. We override by passing
``loop="seomate_api.loop:selector_loop_factory"`` to uvicorn so it
instantiates ``SelectorEventLoop`` instead.

When the loop is given via a custom import string, uvicorn returns the
function as-is and ``asyncio.Runner`` calls ``loop_factory()`` to get a
loop instance — so this function must produce an instance per call,
not return a loop class.
"""
from __future__ import annotations

import asyncio


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    """Return a fresh SelectorEventLoop instance."""
    return asyncio.SelectorEventLoop()
