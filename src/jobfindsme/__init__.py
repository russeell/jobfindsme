"""Agent Job Search local product core.

The import namespace remains ``jobfindsme`` for compatibility.
"""

from importlib.metadata import version as _version

from jobfindsme.contracts import SearchPlan, Workspace

__all__ = ["SearchPlan", "Workspace"]
try:
    __version__ = _version("agent-job-search")
except Exception:
    __version__ = _version("jobfindsme")
