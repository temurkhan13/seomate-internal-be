"""SEOMATE read-only API.

Run with ``python -m seomate_api`` so uvicorn picks up our custom
SelectorEventLoop factory (see ``seomate_api/loop.py`` and ``__main__.py``)
instead of the default ProactorEventLoop on Windows, which psycopg's
async mode does not support.
"""

__version__ = "0.1.0"
