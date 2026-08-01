"""Domain contracts, split by domain but exported from one namespace.

External code keeps importing the unified surface:

    from jobfindsme.contracts import JobSummary, SearchPlan

Each module below owns one domain:

    base.py      — StrictModel, Workspace
    source.py    — platforms, provenance, subscriptions, run stats
    job.py       — postings, salary, summaries, match evidence
    search.py    — plans, constraints, run diagnostics
    tracking.py  — job state and incremental changes
    profile.py   — suggested plans and presentation facts
    mcp.py       — adapter-facing wire outputs
"""

from __future__ import annotations

from jobfindsme.contracts.base import StrictModel, Workspace
from jobfindsme.contracts.job import (
    EmploymentType,
    EvidencePair,
    JobDetails,
    JobMatchSummary,
    JobPosting,
    JobSummary,
    MatchEvidence,
    RecruitmentTrack,
    SalaryDetails,
    SalaryPeriod,
)
from jobfindsme.contracts.mcp import (
    ExportReceipt,
    SearchConfiguration,
    SearchDiagnosticSummary,
    SearchIntegrity,
)
from jobfindsme.contracts.profile import (
    SearchPresentationContext,
    SuggestedPlan,
)
from jobfindsme.contracts.search import (
    SalaryPolicy,
    SearchChanges,
    SearchPlan,
    SearchRefreshMode,
    SearchRunDiagnostics,
    SearchRunResult,
)
from jobfindsme.contracts.source import (
    DiscoverySource,
    DiscoverySourceKind,
    JobDetailLevel,
    JobLiveness,
    JobSourceRecord,
    SourceEvidence,
    SourceHealth,
    SourceKind,
    SourceLink,
    SourceRunStats,
    SourceRunStatus,
    SourceSubscription,
)
from jobfindsme.contracts.tracking import (
    JobChangeType,
    JobMatch,
    JobState,
    JobStateKind,
)

__all__ = [
    "DiscoverySource",
    "DiscoverySourceKind",
    "EmploymentType",
    "EvidencePair",
    "ExportReceipt",
    "JobChangeType",
    "JobDetailLevel",
    "JobDetails",
    "JobLiveness",
    "JobMatch",
    "JobMatchSummary",
    "JobPosting",
    "JobSourceRecord",
    "JobState",
    "JobStateKind",
    "JobSummary",
    "MatchEvidence",
    "RecruitmentTrack",
    "SalaryDetails",
    "SalaryPeriod",
    "SalaryPolicy",
    "SearchChanges",
    "SearchConfiguration",
    "SearchDiagnosticSummary",
    "SearchIntegrity",
    "SearchPlan",
    "SearchPresentationContext",
    "SearchRefreshMode",
    "SearchRunDiagnostics",
    "SearchRunResult",
    "SourceEvidence",
    "SourceHealth",
    "SourceKind",
    "SourceLink",
    "SourceRunStats",
    "SourceRunStatus",
    "SourceSubscription",
    "StrictModel",
    "SuggestedPlan",
    "Workspace",
]
