"""jobfindsme local product core."""

from importlib.metadata import version as _version

from jobfindsme.contracts import SearchPlan, Workspace

__all__ = ["SearchPlan", "Workspace"]
__version__ = _version("jobfindsme")
