from importlib.metadata import version, PackageNotFoundError

__all__ = []

try:
    __version__ = version("devtools-lark")
except PackageNotFoundError:
    # Package not installed (e.g. running from source without `pip install -e .`)
    __version__ = "0.0.0"