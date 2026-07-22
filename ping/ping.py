"""Ping traversal facade.

``Spider`` remains the descriptive implementation name; ``Ping`` is the
project's concise public component name.
"""

from .spider import Spider

Ping = Spider

__all__ = ["Ping"]
