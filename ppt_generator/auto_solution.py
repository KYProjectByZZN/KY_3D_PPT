"""UI-independent draft models for the isolated auto-solution prototype."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


REQUIREMENT_FIELDS: tuple[tuple[str, str], ...] = (
    ("product", "产品信息"),
    ("dimensions", "产品尺寸"),
    ("material", "材料"),
    ("inspection_items", "检测项目"),
    ("accuracy", "精度要求"),
    ("cycle_time", "客户节拍"),
    ("capacity", "产能要求"),
    ("loading_method", "上下料方式"),
    ("process_requirements", "工艺要求"),
    ("special_requirements", "特殊要求"),
    ("constraints", "限制条件"),
)
REQUIREMENT_STATES = {"unknown", "need_confirm", "confirmed"}
SOURCE_TYPES = {
    "",
    "customer",
    "excel",
    "word",
    "pdf",
    "manual",
    "historical_project",
    "standard_module",
    "calculation",
    "ai_inference",
}
MODULE_STATUSES = {"draft", "unverified", "verified", "locked"}
ISSUE_SEVERITIES = {"info", "warning", "error", "blocking"}
ISSUE_STATUSES = {"open", "confirmed", "resolved", "waived"}


@dataclass
class RequirementValue:
    value: str = ""
    state: str = "unknown"
    source_type: str = ""
    source_ref: str = ""

    def validate(self) -> None:
        if self.state not in REQUIREMENT_STATES:
            raise ValueError(f"未知需求状态：{self.state}")
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"未知数据来源：{self.source_type}")
        if self.state == "confirmed" and not self.value.strip():
            raise ValueError("已确认的需求字段不能为空")
        if self.state == "confirmed" and self.source_type == "ai_inference":
            raise ValueError("AI推测不能直接标记为已确认")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RequirementValue":
        item = cls(
            value=str(raw.get("value") or ""),
            state=str(raw.get("state") or "unknown"),
            source_type=str(raw.get("source_type") or ""),
            source_ref=str(raw.get("source_ref") or ""),
        )
        item.validate()
        return item


def _default_requirement_fields() -> dict[str, RequirementValue]:
    return {key: RequirementValue() for key, _label in REQUIREMENT_FIELDS}


@dataclass
class RequirementModel:
    fields: dict[str, RequirementValue] = field(
        default_factory=_default_requirement_fields
    )
    source_files: list[str] = field(default_factory=list)

    def validate(self) -> None:
        for key, _label in REQUIREMENT_FIELDS:
            if key not in self.fields:
                raise ValueError(f"需求模型缺少字段：{key}")
        for item in self.fields.values():
            item.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "fields": {key: value.to_dict() for key, value in self.fields.items()},
            "source_files": list(self.source_files),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RequirementModel":
        raw_fields = raw.get("fields") or {}
        if not isinstance(raw_fields, Mapping):
            raise ValueError("Requirement fields 必须是对象")
        fields = _default_requirement_fields()
        for key, value in raw_fields.items():
            if not isinstance(value, Mapping):
                raise ValueError(f"需求字段 {key} 必须是对象")
            fields[str(key)] = RequirementValue.from_dict(value)
        model = cls(
            fields=fields,
            source_files=[str(item) for item in raw.get("source_files", [])],
        )
        model.validate()
        return model


@dataclass
class EvidenceRef:
    source_type: str
    reference: str = ""
    note: str = ""

    def validate(self) -> None:
        if self.source_type not in SOURCE_TYPES - {""}:
            raise ValueError(f"未知方案来源：{self.source_type}")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "EvidenceRef":
        item = cls(
            source_type=str(raw.get("source_type") or ""),
            reference=str(raw.get("reference") or ""),
            note=str(raw.get("note") or ""),
        )
        item.validate()
        return item


def confidence_grade(confidence: int) -> str:
    if not 0 <= confidence <= 100:
        raise ValueError("置信度必须在0～100之间")
    if confidence >= 90:
        return "A"
    if confidence >= 75:
        return "B"
    return "C"


@dataclass
class SolutionStation:
    station_id: str
    name: str = ""
    function: str = ""
    module_ids: list[str] = field(default_factory=list)
    principle: str = ""
    product_motion: str = ""
    actuator: str = ""
    positioning: str = ""
    inspection: str = ""
    expected_cycle_time: str = ""
    sources: list[EvidenceRef] = field(default_factory=list)
    confidence: int = 0
    locked: bool = False

    def validate(self) -> None:
        confidence_grade(self.confidence)
        for source in self.sources:
            source.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        data = asdict(self)
        data["sources"] = [item.to_dict() for item in self.sources]
        data["confidence_grade"] = confidence_grade(self.confidence)
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SolutionStation":
        item = cls(
            station_id=str(raw.get("station_id") or ""),
            name=str(raw.get("name") or ""),
            function=str(raw.get("function") or ""),
            module_ids=[str(value) for value in raw.get("module_ids", [])],
            principle=str(raw.get("principle") or ""),
            product_motion=str(raw.get("product_motion") or ""),
            actuator=str(raw.get("actuator") or ""),
            positioning=str(raw.get("positioning") or ""),
            inspection=str(raw.get("inspection") or ""),
            expected_cycle_time=str(raw.get("expected_cycle_time") or ""),
            sources=[EvidenceRef.from_dict(value) for value in raw.get("sources", [])],
            confidence=int(raw.get("confidence") or 0),
            locked=bool(raw.get("locked", False)),
        )
        item.validate()
        return item


@dataclass
class SolutionModel:
    version: int = 1
    process: list[str] = field(default_factory=list)
    stations: list[SolutionStation] = field(default_factory=list)
    module_ids: list[str] = field(default_factory=list)
    cycle_time: dict[str, Any] = field(default_factory=dict)
    inspection: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    references: list[EvidenceRef] = field(default_factory=list)

    def validate(self) -> None:
        if self.version < 1:
            raise ValueError("方案版本必须从1开始")
        for station in self.stations:
            station.validate()
        for reference in self.references:
            reference.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "version": self.version,
            "process": list(self.process),
            "stations": [item.to_dict() for item in self.stations],
            "module_ids": list(self.module_ids),
            "cycle_time": dict(self.cycle_time),
            "inspection": list(self.inspection),
            "risks": list(self.risks),
            "references": [item.to_dict() for item in self.references],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SolutionModel":
        model = cls(
            version=int(raw.get("version") or 1),
            process=[str(item) for item in raw.get("process", [])],
            stations=[SolutionStation.from_dict(item) for item in raw.get("stations", [])],
            module_ids=[str(item) for item in raw.get("module_ids", [])],
            cycle_time=dict(raw.get("cycle_time") or {}),
            inspection=[str(item) for item in raw.get("inspection", [])],
            risks=[str(item) for item in raw.get("risks", [])],
            references=[EvidenceRef.from_dict(item) for item in raw.get("references", [])],
        )
        model.validate()
        return model


@dataclass
class ModuleModel:
    module_id: str
    name: str = ""
    use_conditions: list[str] = field(default_factory=list)
    input_parameters: dict[str, Any] = field(default_factory=dict)
    output_parameters: dict[str, Any] = field(default_factory=dict)
    applicable_products: list[str] = field(default_factory=list)
    cycle_time_capability: str = ""
    size_range: str = ""
    load_range: str = ""
    accuracy_range: str = ""
    interfaces: list[str] = field(default_factory=list)
    engineering_assets: list[str] = field(default_factory=list)
    historical_projects: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    validation_status: str = "draft"

    def validate(self) -> None:
        if self.validation_status not in MODULE_STATUSES:
            raise ValueError(f"未知模块验证状态：{self.validation_status}")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ModuleModel":
        item = cls(
            module_id=str(raw.get("module_id") or ""),
            name=str(raw.get("name") or ""),
            use_conditions=[str(value) for value in raw.get("use_conditions", [])],
            input_parameters=dict(raw.get("input_parameters") or {}),
            output_parameters=dict(raw.get("output_parameters") or {}),
            applicable_products=[str(value) for value in raw.get("applicable_products", [])],
            cycle_time_capability=str(raw.get("cycle_time_capability") or ""),
            size_range=str(raw.get("size_range") or ""),
            load_range=str(raw.get("load_range") or ""),
            accuracy_range=str(raw.get("accuracy_range") or ""),
            interfaces=[str(value) for value in raw.get("interfaces", [])],
            engineering_assets=[str(value) for value in raw.get("engineering_assets", [])],
            historical_projects=[str(value) for value in raw.get("historical_projects", [])],
            risks=[str(value) for value in raw.get("risks", [])],
            validation_status=str(raw.get("validation_status") or "draft"),
        )
        item.validate()
        return item


@dataclass
class ValidationIssue:
    issue_id: str
    severity: str
    object_id: str
    rule: str
    message: str
    suggestion: str = ""
    status: str = "open"
    block_output: bool = False

    def validate(self) -> None:
        if self.severity not in ISSUE_SEVERITIES:
            raise ValueError(f"未知问题严重度：{self.severity}")
        if self.status not in ISSUE_STATUSES:
            raise ValueError(f"未知问题状态：{self.status}")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ValidationIssue":
        item = cls(
            issue_id=str(raw.get("issue_id") or ""),
            severity=str(raw.get("severity") or "warning"),
            object_id=str(raw.get("object_id") or ""),
            rule=str(raw.get("rule") or ""),
            message=str(raw.get("message") or ""),
            suggestion=str(raw.get("suggestion") or ""),
            status=str(raw.get("status") or "open"),
            block_output=bool(raw.get("block_output", False)),
        )
        item.validate()
        return item


@dataclass
class ValidationResult:
    passed: bool = False
    rule_version: str = ""
    issues: list[ValidationIssue] = field(default_factory=list)

    def validate(self) -> None:
        for issue in self.issues:
            issue.validate()
        if self.passed and any(
            issue.block_output and issue.status not in {"resolved", "waived"}
            for issue in self.issues
        ):
            raise ValueError("存在未解决的阻断问题时不能标记审核通过")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "passed": self.passed,
            "rule_version": self.rule_version,
            "issues": [item.to_dict() for item in self.issues],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ValidationResult":
        result = cls(
            passed=bool(raw.get("passed", False)),
            rule_version=str(raw.get("rule_version") or ""),
            issues=[ValidationIssue.from_dict(item) for item in raw.get("issues", [])],
        )
        result.validate()
        return result
