"""Domain contracts, exported from one unified namespace.

External code keeps importing the unified surface:

    from jobfindsme.contracts import JobSummary, SearchPlan

    models.py   — workspace, sources, jobs, salary, match evidence
    search.py   — plans, constraints, configuration, run diagnostics
    tracking.py — job state and incremental changes
"""

from __future__ import annotations

from jobfindsme.contracts.models import (
    DiscoverySource,
    DiscoverySourceKind,
    EmploymentType,
    EvidencePair,
    JobDetailLevel,
    JobDetails,
    JobLiveness,
    JobMatchSummary,
    JobPosting,
    JobSourceRecord,
    JobSummary,
    MatchEvidence,
    RecruitmentTrack,
    SalaryDetails,
    SalaryPeriod,
    SourceEvidence,
    SourceHealth,
    SourceKind,
    SourceLink,
    SourceRunStats,
    SourceRunStatus,
    SourceSubscription,
    StrictModel,
    Workspace,
)
from jobfindsme.contracts.search import (
    ExportReceipt,
    SalaryPolicy,
    SearchChanges,
    SearchConfiguration,
    SearchDiagnosticSummary,
    SearchIntegrity,
    SearchPlan,
    SearchPresentationContext,
    SearchRefreshMode,
    SearchRunDiagnostics,
    SearchRunResult,
    SuggestedPlan,
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
