"""Application service coordinating auto-solution v2 bounded modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import getpass
import os
from pathlib import Path
from typing import Callable, Sequence
from uuid import uuid4

from .auto_solution_repository import JsonAutoSolutionRepository
from .requirement_management import (
    RequirementRecord,
    RequirementSuggestion,
    RequirementSuggestionProvider,
    RequirementVersionSnapshot,
    RuleBasedRequirementParser,
    apply_requirement_suggestions,
)
from .solution_generation import (
    CandidateSolution,
    CandidateSolutionGenerator,
    CandidateStation,
    DrawingPromptBuilder,
    DrawingSpecification,
    DrawingSpecificationBuilder,
    HistoricalMatch,
    HistoricalSolutionRetriever,
)


def current_time_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def default_auto_solution_store_path() -> Path:
    configured = os.environ.get("KY_PPT_AUTO_SOLUTION_STORE", "").strip()
    if configured:
        return Path(configured)
    project_root = Path(__file__).resolve().parents[1]
    return project_root / "output" / "auto_solution_v2_store.json"


@dataclass(frozen=True)
class RequirementSummary:
    id: str
    requirement_no: str
    customer_name: str
    project_name: str
    product_name: str
    target_cycle: str
    created_by: str
    updated_time: str
    status: str
    solution_count: int
    version: int


class AutoSolutionApplication:
    """Stable use-case boundary; UI passes IDs rather than peer widget objects."""

    def __init__(
        self,
        repository: JsonAutoSolutionRepository | None = None,
        suggestion_provider: RequirementSuggestionProvider | None = None,
        retriever: HistoricalSolutionRetriever | None = None,
        generator: CandidateSolutionGenerator | None = None,
        clock: Callable[[], str] = current_time_iso,
        actor: str | None = None,
    ) -> None:
        self.repository = repository or JsonAutoSolutionRepository(
            default_auto_solution_store_path()
        )
        self.suggestion_provider = suggestion_provider or RuleBasedRequirementParser()
        self.retriever = retriever or HistoricalSolutionRetriever()
        self.generator = generator or CandidateSolutionGenerator()
        self.clock = clock
        self.actor = actor or getpass.getuser() or "当前用户"

    @property
    def parser_name(self) -> str:
        return self.suggestion_provider.name

    @property
    def storage_path(self) -> Path:
        return self.repository.path

    def new_requirement(self) -> RequirementRecord:
        now = self.clock()
        return RequirementRecord(
            id=str(uuid4()),
            requirement_no=self._next_requirement_no(now),
            created_by=self.actor,
            created_time=now,
            updated_time=now,
        )

    def _next_requirement_no(self, now: str) -> str:
        digits = reformat_date(now)
        prefix = f"REQ-{digits}-"
        numbers = []
        for record in self.repository.list_requirements(include_archived=True):
            if record.requirement_no.startswith(prefix):
                suffix = record.requirement_no[len(prefix) :]
                if suffix.isdigit():
                    numbers.append(int(suffix))
        return f"{prefix}{max(numbers, default=0) + 1:03d}"

    def list_requirement_summaries(
        self,
        include_archived: bool = False,
    ) -> list[RequirementSummary]:
        records = self.repository.list_requirements(include_archived=include_archived)
        candidate_counts: dict[str, int] = {}
        for candidate in self.repository.list_candidates():
            candidate_counts[candidate.requirement_id] = (
                candidate_counts.get(candidate.requirement_id, 0) + 1
            )
        return [
            RequirementSummary(
                id=record.id,
                requirement_no=record.requirement_no,
                customer_name=record.customer_name,
                project_name=record.project_name,
                product_name=record.product_name,
                target_cycle=record.structured_requirement.capacity_and_cycle.target_cycle,
                created_by=record.created_by,
                updated_time=record.updated_time,
                status=record.status,
                solution_count=candidate_counts.get(record.id, 0),
                version=record.version,
            )
            for record in records
        ]

    def get_requirement(self, requirement_id: str) -> RequirementRecord:
        record = self.repository.get_requirement(requirement_id)
        if record is None:
            raise KeyError(f"找不到需求记录：{requirement_id}")
        return record

    def requirement_exists(self, requirement_id: str) -> bool:
        return self.repository.get_requirement(requirement_id) is not None

    def save_requirement(
        self,
        record: RequirementRecord,
        action: str = "update",
    ) -> RequirementRecord:
        return self.repository.save_requirement(
            record,
            changed_by=self.actor,
            changed_time=self.clock(),
            action=action,
        )

    def copy_requirement(self, requirement_id: str) -> RequirementRecord:
        source = self.get_requirement(requirement_id)
        copy = source.clone()
        now = self.clock()
        copy.id = str(uuid4())
        copy.requirement_no = self._next_requirement_no(now)
        copy.project_name = f"{source.project_name}（复制）" if source.project_name else "复制需求"
        copy.status = "draft"
        copy.created_by = self.actor
        copy.created_time = now
        copy.updated_time = now
        copy.version = 1
        return self.save_requirement(copy, action="copy")

    def archive_requirement(self, requirement_id: str) -> RequirementRecord:
        record = self.get_requirement(requirement_id)
        record.status = "archived"
        return self.save_requirement(record, action="archive")

    def delete_requirement(self, requirement_id: str) -> bool:
        record = self.get_requirement(requirement_id)
        if record.status != "draft":
            raise ValueError("仅草稿需求允许删除；其它状态请归档")
        if self.repository.list_candidates(requirement_id):
            raise ValueError("已有候选方案的需求不能删除，请改为归档")
        return self.repository.delete_requirement(requirement_id)

    def requirement_history(
        self,
        requirement_id: str,
    ) -> list[RequirementVersionSnapshot]:
        return self.repository.requirement_history(requirement_id)

    def parse_requirement(
        self,
        requirement: RequirementRecord,
    ) -> list[RequirementSuggestion]:
        return self.suggestion_provider.suggest(requirement.clone())

    def apply_suggestions(
        self,
        requirement: RequirementRecord,
        suggestions: Sequence[RequirementSuggestion],
    ) -> list[str]:
        return apply_requirement_suggestions(requirement, suggestions)

    def retrieve_history(self, requirement_id: str) -> list[HistoricalMatch]:
        requirement = self.get_requirement(requirement_id)
        return self.retriever.retrieve(
            requirement,
            self.repository.list_historical_solutions(),
        )

    def generate_candidate(self, requirement_id: str) -> CandidateSolution:
        requirement = self.get_requirement(requirement_id)
        if requirement.status == "archived":
            raise ValueError("归档需求不能生成候选方案")
        existing = self.repository.list_candidates(requirement_id)
        matches = self.retrieve_history(requirement_id)
        candidate = self.generator.generate(
            requirement=requirement,
            matches=matches,
            version=max((value.version for value in existing), default=0) + 1,
            created_time=self.clock(),
            created_by=self.actor,
        )
        return self.repository.save_candidate(candidate)

    def list_candidates(self, requirement_id: str) -> list[CandidateSolution]:
        return self.repository.list_candidates(requirement_id)

    def get_candidate(self, candidate_id: str) -> CandidateSolution:
        candidate = self.repository.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError(f"找不到候选方案：{candidate_id}")
        return candidate

    def save_candidate_edits(
        self,
        candidate_id: str,
        process_flow: Sequence[str],
        stations: Sequence[CandidateStation],
        drawing_specification: DrawingSpecification,
    ) -> CandidateSolution:
        candidate = self.get_candidate(candidate_id)
        clean_process = [value.strip() for value in process_flow if value.strip()]
        candidate.process_flow = clean_process
        candidate.stations = list(stations)
        requirement = self.get_requirement(candidate.requirement_id)
        candidate.drawing_specification = DrawingSpecificationBuilder().synchronize(
            drawing_specification,
            requirement,
            clean_process,
            candidate.stations,
        )
        candidate.drawing_prompt = DrawingPromptBuilder().build(
            candidate.drawing_specification
        )
        return self.repository.save_candidate(candidate)

    def confirm_candidate(self, candidate_id: str) -> CandidateSolution:
        candidate = self.get_candidate(candidate_id)
        candidate.status = "confirmed"
        return self.repository.save_candidate(candidate)


def reformat_date(iso_time: str) -> str:
    try:
        return datetime.fromisoformat(iso_time).strftime("%Y%m%d")
    except ValueError:
        return datetime.now().strftime("%Y%m%d")


__all__ = [
    "AutoSolutionApplication",
    "RequirementSummary",
    "current_time_iso",
    "default_auto_solution_store_path",
]
