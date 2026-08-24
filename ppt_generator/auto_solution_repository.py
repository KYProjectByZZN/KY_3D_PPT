"""JSON persistence for auto-solution v2 aggregates."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from .requirement_management import RequirementRecord, RequirementVersionSnapshot
from .solution_generation import (
    CandidateSolution,
    HistoricalSolutionRecord,
    demo_historical_solutions,
)


STORE_SCHEMA_VERSION = 1


class JsonAutoSolutionRepository:
    """Single-file repository with atomic replacement and no business inference."""

    def __init__(self, path: str | Path, include_demo_history: bool = True) -> None:
        self.path = Path(path)
        self.include_demo_history = include_demo_history

    def _empty_data(self) -> dict[str, Any]:
        return {
            "schemaVersion": STORE_SCHEMA_VERSION,
            "requirements": [],
            "requirementVersions": [],
            "historicalSolutions": [],
            "candidateSolutions": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_data()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"无法读取自动方案数据文件：{self.path}") from exc
        if not isinstance(raw, Mapping):
            raise ValueError("自动方案数据文件根节点必须是 JSON 对象")
        version = int(raw.get("schemaVersion") or 0)
        if version != STORE_SCHEMA_VERSION:
            raise ValueError(f"不支持的自动方案数据版本：{version}")
        data = self._empty_data()
        for key in (
            "requirements",
            "requirementVersions",
            "historicalSolutions",
            "candidateSolutions",
        ):
            value = raw.get(key, [])
            if not isinstance(value, list):
                raise ValueError(f"自动方案数据字段 {key} 必须是数组")
            data[key] = value
        return data

    def _save(self, data: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.stem}-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_path = handle.name
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path and Path(temporary_path).exists():
                Path(temporary_path).unlink()

    def list_requirements(self, include_archived: bool = False) -> list[RequirementRecord]:
        records = [
            RequirementRecord.from_dict(value)
            for value in self._load()["requirements"]
            if isinstance(value, Mapping)
        ]
        if not include_archived:
            records = [value for value in records if value.status != "archived"]
        records.sort(key=lambda value: (value.updated_time, value.requirement_no), reverse=True)
        return records

    def get_requirement(self, requirement_id: str) -> RequirementRecord | None:
        for record in self.list_requirements(include_archived=True):
            if record.id == requirement_id:
                return record
        return None

    def save_requirement(
        self,
        record: RequirementRecord,
        changed_by: str,
        changed_time: str,
        action: str = "update",
    ) -> RequirementRecord:
        record.validate()
        data = self._load()
        raw_records = data["requirements"]
        existing_index = next(
            (
                index
                for index, value in enumerate(raw_records)
                if isinstance(value, Mapping) and str(value.get("id") or "") == record.id
            ),
            -1,
        )
        working = record.clone()
        if existing_index < 0:
            working.version = 1
            working.created_by = working.created_by or changed_by
            working.created_time = working.created_time or changed_time
            working.updated_time = changed_time
            after_dict = working.to_dict()
            raw_records.append(after_dict)
            data["requirementVersions"].append(
                RequirementVersionSnapshot(
                    requirement_id=working.id,
                    version=1,
                    before={},
                    after=after_dict,
                    changed_time=changed_time,
                    changed_by=changed_by,
                    action="create" if action == "update" else action,
                ).to_dict()
            )
            self._save(data)
            return working

        before = RequirementRecord.from_dict(raw_records[existing_index])
        working.requirement_no = before.requirement_no
        working.created_by = before.created_by
        working.created_time = before.created_time
        working.updated_time = before.updated_time
        working.version = before.version
        if self._record_payload(before) == self._record_payload(working):
            return before

        working.version = before.version + 1
        working.updated_time = changed_time
        after_dict = working.to_dict()
        raw_records[existing_index] = after_dict
        data["requirementVersions"].append(
            RequirementVersionSnapshot(
                requirement_id=working.id,
                version=working.version,
                before=before.to_dict(),
                after=after_dict,
                changed_time=changed_time,
                changed_by=changed_by,
                action=action,
            ).to_dict()
        )
        self._save(data)
        return working

    @staticmethod
    def _record_payload(record: RequirementRecord) -> dict[str, Any]:
        value = record.to_dict()
        for key in ("version", "createdTime", "updatedTime", "createdBy", "requirementNo"):
            value.pop(key, None)
        return value

    def delete_requirement(self, requirement_id: str) -> bool:
        data = self._load()
        before_count = len(data["requirements"])
        data["requirements"] = [
            value
            for value in data["requirements"]
            if not isinstance(value, Mapping) or str(value.get("id") or "") != requirement_id
        ]
        if len(data["requirements"]) == before_count:
            return False
        data["requirementVersions"] = [
            value
            for value in data["requirementVersions"]
            if not isinstance(value, Mapping)
            or str(value.get("requirementId") or "") != requirement_id
        ]
        self._save(data)
        return True

    def requirement_history(self, requirement_id: str) -> list[RequirementVersionSnapshot]:
        snapshots = [
            RequirementVersionSnapshot.from_dict(value)
            for value in self._load()["requirementVersions"]
            if isinstance(value, Mapping)
            and str(value.get("requirementId") or "") == requirement_id
        ]
        snapshots.sort(key=lambda value: value.version)
        return snapshots

    def list_historical_solutions(self) -> list[HistoricalSolutionRecord]:
        stored = [
            HistoricalSolutionRecord.from_dict(value)
            for value in self._load()["historicalSolutions"]
            if isinstance(value, Mapping)
        ]
        if not self.include_demo_history:
            return stored
        stored_ids = {value.id for value in stored}
        return stored + [
            value for value in demo_historical_solutions() if value.id not in stored_ids
        ]

    def save_historical_solution(
        self,
        record: HistoricalSolutionRecord,
    ) -> HistoricalSolutionRecord:
        record.validate()
        data = self._load()
        raw_records = data["historicalSolutions"]
        index = next(
            (
                index
                for index, value in enumerate(raw_records)
                if isinstance(value, Mapping) and str(value.get("id") or "") == record.id
            ),
            -1,
        )
        if index < 0:
            raw_records.append(record.to_dict())
        else:
            raw_records[index] = record.to_dict()
        self._save(data)
        return HistoricalSolutionRecord.from_dict(record.to_dict())

    def list_candidates(self, requirement_id: str | None = None) -> list[CandidateSolution]:
        candidates = [
            CandidateSolution.from_dict(value)
            for value in self._load()["candidateSolutions"]
            if isinstance(value, Mapping)
        ]
        if requirement_id:
            candidates = [value for value in candidates if value.requirement_id == requirement_id]
        candidates.sort(key=lambda value: (value.requirement_id, value.version))
        return candidates

    def get_candidate(self, candidate_id: str) -> CandidateSolution | None:
        return next(
            (value for value in self.list_candidates() if value.id == candidate_id),
            None,
        )

    def save_candidate(self, candidate: CandidateSolution) -> CandidateSolution:
        candidate.validate()
        data = self._load()
        raw_candidates = data["candidateSolutions"]
        index = next(
            (
                index
                for index, value in enumerate(raw_candidates)
                if isinstance(value, Mapping) and str(value.get("id") or "") == candidate.id
            ),
            -1,
        )
        if index < 0:
            raw_candidates.append(candidate.to_dict())
        else:
            raw_candidates[index] = candidate.to_dict()
        self._save(data)
        return CandidateSolution.from_dict(candidate.to_dict())


__all__ = ["JsonAutoSolutionRepository", "STORE_SCHEMA_VERSION"]
