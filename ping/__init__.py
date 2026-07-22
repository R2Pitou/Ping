"""Ping respectful web spider."""

from importlib.metadata import version as installed_version
from pathlib import Path
import tomllib

from .dok import Dok
from .hasher import Tra
from .ping import Ping
from .rok import Rok
from .sanya import Sanya
from .yok import Yok

__all__ = ["Dok", "Ping", "Rok", "Sanya", "Tra", "Yok", "__version__"]


def _version() -> str:
    """Read the source project's version, or installed distribution metadata."""
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if pyproject.is_file():
        with pyproject.open("rb") as file:
            return tomllib.load(file)["project"]["version"]
    return installed_version("ping-spider")


__version__ = _version()
