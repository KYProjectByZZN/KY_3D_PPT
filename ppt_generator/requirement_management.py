"""Requirement domain for the auto-solution v2 workflow.

The original customer text and the structured configuration deliberately live in
the same aggregate.  Parsers only return proposals; applying a proposal is a
separate, explicit operation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping, Protocol, Sequence


TRI_STATE_VALUES = {"yes", "no", "unknown"}
REQUIREMENT_STATUSES = {"draft", "confirmed", "archived"}
PRODUCT_STATE_FIELDS: tuple[tuple[str, str], ...] = (
    ("oil", "有油"),
    ("water", "有水"),
    ("dust", "有粉尘"),
    ("reflective", "反光"),
    ("transparent", "透明"),
    ("easyScratch", "易划伤"),
    ("deformable", "易变形"),
    ("burr", "有毛刺"),
    ("sharpEdge", "尖锐边缘"),
)
LOADING_MODES = (
    "未知",
    "人工上料",
    "振动盘上料",
    "皮带线上料",
    "料盘上料",
    "机械手上料",
    "机器人上料",
    "连续带材上料",
    "其他",
)
UNLOADING_MODES = (
    "未知",
    "人工下料",
    "皮带线下料",
    "料盘收料",
    "机械手下料",
    "机器人下料",
    "OK/NG分选",
    "多级分选",
    "其他",
)


def _as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


@dataclass
class BasicInformation:
    product_type: str = ""
    model: str = ""
    size: str = ""
    material: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "productType": self.product_type,
            "model": self.model,
            "size": self.size,
            "material": self.material,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "BasicInformation":
        return cls(
            product_type=_as_text(raw.get("productType")),
            model=_as_text(raw.get("model")),
            size=_as_text(raw.get("size")),
            material=_as_text(raw.get("material")),
        )


@dataclass
class CapacityAndCycle:
    target_cycle: str = ""
    batch_quantity: str = ""
    daily_capacity: str = ""
    continuous_production: str = "unknown"

    def validate(self) -> None:
        if self.continuous_production not in TRI_STATE_VALUES:
            raise ValueError("连续生产状态必须是 yes、no 或 unknown")

    def to_dict(self) -> dict[str, str]:
        self.validate()
        return {
            "targetCycle": self.target_cycle,
            "batchQuantity": self.batch_quantity,
            "dailyCapacity": self.daily_capacity,
            "continuousProduction": self.continuous_production,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "CapacityAndCycle":
        item = cls(
            target_cycle=_as_text(raw.get("targetCycle")),
            batch_quantity=_as_text(raw.get("batchQuantity")),
            daily_capacity=_as_text(raw.get("dailyCapacity")),
            continuous_production=_as_text(
                raw.get("continuousProduction") or "unknown"
            ),
        )
        item.validate()
        return item


@dataclass
class TransferRequirement:
    mode: str = "未知"
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"mode": self.mode, "note": self.note}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TransferRequirement":
        return cls(
            mode=_as_text(raw.get("mode")) or "未知",
            note=_as_text(raw.get("note")),
        )


@dataclass
class InspectionRequirement:
    name: str
    accuracy: str = ""
    range: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "accuracy": self.accuracy,
            "range": self.range,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "InspectionRequirement":
        return cls(
            name=_as_text(raw.get("name")),
            accuracy=_as_text(raw.get("accuracy")),
            range=_as_text(raw.get("range")),
            note=_as_text(raw.get("note")),
        )


def _default_product_states() -> dict[str, str]:
    return {key: "unknown" for key, _label in PRODUCT_STATE_FIELDS}


@dataclass
class StructuredRequirement:
    basic_info: BasicInformation = field(default_factory=BasicInformation)
    capacity_and_cycle: CapacityAndCycle = field(default_factory=CapacityAndCycle)
    loading: TransferRequirement = field(default_factory=TransferRequirement)
    unloading: TransferRequirement = field(default_factory=TransferRequirement)
    inspection_items: list[InspectionRequirement] = field(default_factory=list)
    product_states: dict[str, str] = field(default_factory=_default_product_states)
    special_requirements: str = ""

    def validate(self) -> None:
        self.capacity_and_cycle.validate()
        for key, _label in PRODUCT_STATE_FIELDS:
            value = self.product_states.get(key, "unknown")
            if value not in TRI_STATE_VALUES:
                raise ValueError(f"产品状态 {key} 必须是 yes、no 或 unknown")
        if any(not item.name.strip() for item in self.inspection_items):
            raise ValueError("检测项名称不能为空")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        states = _default_product_states()
        states.update(self.product_states)
        return {
            "basicInfo": self.basic_info.to_dict(),
            "capacityAndCycle": self.capacity_and_cycle.to_dict(),
            "loading": self.loading.to_dict(),
            "unloading": self.unloading.to_dict(),
            "inspectionItems": [item.to_dict() for item in self.inspection_items],
            "productStates": states,
            "specialRequirements": self.special_requirements,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "StructuredRequirement":
        raw_states = raw.get("productStates") or {}
        states = _default_product_states()
        if isinstance(raw_states, Mapping):
            states.update({str(key): _as_text(value) for key, value in raw_states.items()})
        item = cls(
            basic_info=BasicInformation.from_dict(raw.get("basicInfo") or {}),
            capacity_and_cycle=CapacityAndCycle.from_dict(
                raw.get("capacityAndCycle") or {}
            ),
            loading=TransferRequirement.from_dict(raw.get("loading") or {}),
            unloading=TransferRequirement.from_dict(raw.get("unloading") or {}),
            inspection_items=[
                InspectionRequirement.from_dict(value)
                for value in raw.get("inspectionItems", [])
                if isinstance(value, Mapping)
            ],
            product_states=states,
            special_requirements=_as_text(raw.get("specialRequirements")),
        )
        item.validate()
        return item


@dataclass
class RequirementRecord:
    id: str
    requirement_no: str
    customer_name: str = ""
    project_name: str = ""
    product_name: str = ""
    original_requirement: str = ""
    structured_requirement: StructuredRequirement = field(
        default_factory=StructuredRequirement
    )
    status: str = "draft"
    created_by: str = ""
    created_time: str = ""
    updated_time: str = ""
    version: int = 1

    def validate(self) -> None:
        if not self.id:
            raise ValueError("需求记录缺少 id")
        if not self.requirement_no:
            raise ValueError("需求记录缺少 requirementNo")
        if self.status not in REQUIREMENT_STATUSES:
            raise ValueError(f"未知需求状态：{self.status}")
        if self.version < 1:
            raise ValueError("需求版本必须从 V1 开始")
        self.structured_requirement.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "id": self.id,
            "requirementNo": self.requirement_no,
            "customerName": self.customer_name,
            "projectName": self.project_name,
            "productName": self.product_name,
            "originalRequirement": self.original_requirement,
            "structuredRequirement": self.structured_requirement.to_dict(),
            "status": self.status,
            "createdBy": self.created_by,
            "createdTime": self.created_time,
            "updatedTime": self.updated_time,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RequirementRecord":
        item = cls(
            id=_as_text(raw.get("id")),
            requirement_no=_as_text(raw.get("requirementNo")),
            customer_name=_as_text(raw.get("customerName")),
            project_name=_as_text(raw.get("projectName")),
            product_name=_as_text(raw.get("productName")),
            original_requirement=str(raw.get("originalRequirement") or ""),
            structured_requirement=StructuredRequirement.from_dict(
                raw.get("structuredRequirement") or {}
            ),
            status=_as_text(raw.get("status") or "draft"),
            created_by=_as_text(raw.get("createdBy")),
            created_time=_as_text(raw.get("createdTime")),
            updated_time=_as_text(raw.get("updatedTime")),
            version=int(raw.get("version") or 1),
        )
        item.validate()
        return item

    def clone(self) -> "RequirementRecord":
        return RequirementRecord.from_dict(self.to_dict())


@dataclass
class RequirementVersionSnapshot:
    requirement_id: str
    version: int
    before: dict[str, Any]
    after: dict[str, Any]
    changed_time: str
    changed_by: str
    action: str = "update"

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirementId": self.requirement_id,
            "version": self.version,
            "before": self.before,
            "after": self.after,
            "changedTime": self.changed_time,
            "changedBy": self.changed_by,
            "action": self.action,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RequirementVersionSnapshot":
        return cls(
            requirement_id=_as_text(raw.get("requirementId")),
            version=int(raw.get("version") or 1),
            before=dict(raw.get("before") or {}),
            after=dict(raw.get("after") or {}),
            changed_time=_as_text(raw.get("changedTime")),
            changed_by=_as_text(raw.get("changedBy")),
            action=_as_text(raw.get("action") or "update"),
        )


@dataclass
class RequirementSuggestion:
    field_path: str
    proposed_value: Any
    current_value: Any = ""
    evidence: str = ""
    confidence: int = 0
    provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "fieldPath": self.field_path,
            "currentValue": self.current_value,
            "proposedValue": self.proposed_value,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "provider": self.provider,
        }


class RequirementSuggestionProvider(Protocol):
    """Port for a local parser or a future online AI adapter."""

    name: str

    def suggest(self, requirement: RequirementRecord) -> list[RequirementSuggestion]:
        ...


def requirement_field_value(requirement: RequirementRecord, path: str) -> Any:
    structured = requirement.structured_requirement
    getters: dict[str, Any] = {
        "customerName": requirement.customer_name,
        "projectName": requirement.project_name,
        "productName": requirement.product_name,
        "basicInfo.productType": structured.basic_info.product_type,
        "basicInfo.model": structured.basic_info.model,
        "basicInfo.size": structured.basic_info.size,
        "basicInfo.material": structured.basic_info.material,
        "capacityAndCycle.targetCycle": structured.capacity_and_cycle.target_cycle,
        "capacityAndCycle.batchQuantity": structured.capacity_and_cycle.batch_quantity,
        "capacityAndCycle.dailyCapacity": structured.capacity_and_cycle.daily_capacity,
        "capacityAndCycle.continuousProduction": structured.capacity_and_cycle.continuous_production,
        "loading.mode": structured.loading.mode,
        "loading.note": structured.loading.note,
        "unloading.mode": structured.unloading.mode,
        "unloading.note": structured.unloading.note,
        "inspectionItems": [item.to_dict() for item in structured.inspection_items],
        "specialRequirements": structured.special_requirements,
    }
    if path.startswith("productStates."):
        return structured.product_states.get(path.split(".", 1)[1], "unknown")
    if path not in getters:
        raise KeyError(f"未知需求字段路径：{path}")
    return getters[path]


def _is_empty_requirement_value(path: str, value: Any) -> bool:
    if path in {"loading.mode", "unloading.mode"}:
        return not value or value == "未知"
    if path.startswith("productStates.") or path.endswith("continuousProduction"):
        return not value or value == "unknown"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return len(value) == 0
    return not _as_text(value)


def apply_requirement_suggestions(
    requirement: RequirementRecord,
    suggestions: Sequence[RequirementSuggestion],
) -> list[str]:
    """Apply proposals only to empty/unknown fields and return applied paths."""

    applied: list[str] = []
    structured = requirement.structured_requirement
    scalar_setters = {
        "customerName": lambda value: setattr(requirement, "customer_name", _as_text(value)),
        "projectName": lambda value: setattr(requirement, "project_name", _as_text(value)),
        "productName": lambda value: setattr(requirement, "product_name", _as_text(value)),
        "basicInfo.productType": lambda value: setattr(structured.basic_info, "product_type", _as_text(value)),
        "basicInfo.model": lambda value: setattr(structured.basic_info, "model", _as_text(value)),
        "basicInfo.size": lambda value: setattr(structured.basic_info, "size", _as_text(value)),
        "basicInfo.material": lambda value: setattr(structured.basic_info, "material", _as_text(value)),
        "capacityAndCycle.targetCycle": lambda value: setattr(structured.capacity_and_cycle, "target_cycle", _as_text(value)),
        "capacityAndCycle.batchQuantity": lambda value: setattr(structured.capacity_and_cycle, "batch_quantity", _as_text(value)),
        "capacityAndCycle.dailyCapacity": lambda value: setattr(structured.capacity_and_cycle, "daily_capacity", _as_text(value)),
        "capacityAndCycle.continuousProduction": lambda value: setattr(structured.capacity_and_cycle, "continuous_production", _as_text(value)),
        "loading.mode": lambda value: setattr(structured.loading, "mode", _as_text(value)),
        "loading.note": lambda value: setattr(structured.loading, "note", _as_text(value)),
        "unloading.mode": lambda value: setattr(structured.unloading, "mode", _as_text(value)),
        "unloading.note": lambda value: setattr(structured.unloading, "note", _as_text(value)),
        "specialRequirements": lambda value: setattr(structured, "special_requirements", _as_text(value)),
    }
    for suggestion in suggestions:
        path = suggestion.field_path
        current = requirement_field_value(requirement, path)
        if not _is_empty_requirement_value(path, current):
            continue
        if path == "inspectionItems":
            raw_items = suggestion.proposed_value
            if isinstance(raw_items, Sequence) and not isinstance(raw_items, (str, bytes)):
                structured.inspection_items = [
                    InspectionRequirement.from_dict(value)
                    for value in raw_items
                    if isinstance(value, Mapping) and _as_text(value.get("name"))
                ]
        elif path.startswith("productStates."):
            key = path.split(".", 1)[1]
            proposed = _as_text(suggestion.proposed_value)
            if proposed not in TRI_STATE_VALUES:
                continue
            structured.product_states[key] = proposed
        elif path in scalar_setters:
            scalar_setters[path](suggestion.proposed_value)
        else:
            continue
        applied.append(path)
    structured.validate()
    return applied


class RuleBasedRequirementParser:
    """Conservative offline parser used until an online AI provider is configured."""

    name = "local_rule_parser_v1"

    _MATERIALS = (
        "不锈钢",
        "铝合金",
        "铝",
        "铜",
        "塑料",
        "玻璃",
        "陶瓷",
        "橡胶",
        "钢",
    )
    _INSPECTION_TERMS = (
        "划伤",
        "压伤",
        "缺口",
        "毛刺",
        "裂纹",
        "脏污",
        "异物",
        "尺寸",
        "高度",
        "直径",
        "同心度",
        "圆度",
        "字符",
        "二维码",
        "装配",
        "有无",
        "颜色",
    )
    _STATE_TERMS: dict[str, tuple[str, ...]] = {
        "oil": ("有油", "油污", "带油"),
        "water": ("有水", "水渍", "带水"),
        "dust": ("粉尘", "粉末"),
        "reflective": ("反光", "高反"),
        "transparent": ("透明",),
        "easyScratch": ("易划伤", "怕划伤"),
        "deformable": ("易变形", "柔性"),
        "burr": ("有毛刺",),
        "sharpEdge": ("尖锐边缘", "锐边"),
    }

    def suggest(self, requirement: RequirementRecord) -> list[RequirementSuggestion]:
        text = requirement.original_requirement.strip()
        if not text:
            return []
        suggestions: list[RequirementSuggestion] = []

        def add(path: str, value: Any, evidence: str, confidence: int) -> None:
            current = requirement_field_value(requirement, path)
            if value in (None, "", [], {}):
                return
            suggestions.append(
                RequirementSuggestion(
                    field_path=path,
                    current_value=current,
                    proposed_value=value,
                    evidence=evidence,
                    confidence=confidence,
                    provider=self.name,
                )
            )

        size_match = re.search(
            r"(?<!\d)(\d+(?:\.\d+)?)\s*[×xX*]\s*(\d+(?:\.\d+)?)(?:\s*[×xX*]\s*(\d+(?:\.\d+)?))?\s*(mm|毫米|cm|厘米)?",
            text,
            re.IGNORECASE,
        )
        if size_match:
            unit = size_match.group(4) or "mm"
            dimensions = "×".join(value for value in size_match.groups()[:3] if value)
            add("basicInfo.size", f"{dimensions} {unit}", size_match.group(0), 92)

        for material in self._MATERIALS:
            if material in text:
                add("basicInfo.material", material, material, 90)
                break

        cycle_match = re.search(
            r"(?:节拍|检测速度|速度)[^\d]{0,8}(\d+(?:\.\d+)?)\s*(秒|s|S)(?:\s*/\s*(?:件|个|pcs?))?",
            text,
        )
        if cycle_match:
            add(
                "capacityAndCycle.targetCycle",
                f"{cycle_match.group(1)} s/件",
                cycle_match.group(0),
                94,
            )

        batch_match = re.search(r"(?:每批|单批|一批)[^\d]{0,6}(\d+)\s*(?:件|个|pcs?)", text, re.IGNORECASE)
        if batch_match:
            add("capacityAndCycle.batchQuantity", f"{batch_match.group(1)} 件", batch_match.group(0), 92)

        daily_match = re.search(r"(?:日产能|每天|日需求)[^\d]{0,8}(\d+(?:\.\d+)?)\s*(万)?\s*(?:件|个|pcs?)", text, re.IGNORECASE)
        if daily_match:
            number = daily_match.group(1) + (" 万" if daily_match.group(2) else "")
            add("capacityAndCycle.dailyCapacity", f"{number} 件/天", daily_match.group(0), 91)

        if "连续生产" in text or "连续运行" in text or "24小时" in text:
            add("capacityAndCycle.continuousProduction", "yes", "连续生产关键词", 88)

        loading_map = (
            ("振动盘", "振动盘上料"),
            ("料盘上料", "料盘上料"),
            ("托盘上料", "料盘上料"),
            ("皮带线上料", "皮带线上料"),
            ("机械手上料", "机械手上料"),
            ("机器人上料", "机器人上料"),
            ("人工上料", "人工上料"),
        )
        for keyword, mode in loading_map:
            if keyword in text:
                add("loading.mode", mode, keyword, 95)
                break

        unloading_map = (
            ("多级分选", "多级分选"),
            ("OK/NG", "OK/NG分选"),
            ("良品不良品", "OK/NG分选"),
            ("料盘收料", "料盘收料"),
            ("皮带线下料", "皮带线下料"),
            ("机械手下料", "机械手下料"),
            ("机器人下料", "机器人下料"),
            ("人工下料", "人工下料"),
        )
        for keyword, mode in unloading_map:
            if keyword.lower() in text.lower():
                add("unloading.mode", mode, keyword, 95)
                break

        inspection_scopes = re.findall(
            r"(?:检测|检查|检验)(?:项目|项|内容|要求)?[：:，,\s]*([^。；;\n]{1,120})",
            text,
        )
        inspection_text = " ".join(inspection_scopes)
        inspection_items = []
        for term in self._INSPECTION_TERMS:
            if term in inspection_text and term not in {item["name"] for item in inspection_items}:
                inspection_items.append(
                    {"name": term, "accuracy": "", "range": "", "note": "来自原始需求关键词"}
                )
        if inspection_items:
            add("inspectionItems", inspection_items, "、".join(item["name"] for item in inspection_items), 80)

        for state_key, keywords in self._STATE_TERMS.items():
            for keyword in keywords:
                if keyword in text:
                    add(f"productStates.{state_key}", "yes", keyword, 82)
                    break
        return suggestions


__all__ = [
    "BasicInformation",
    "CapacityAndCycle",
    "InspectionRequirement",
    "LOADING_MODES",
    "PRODUCT_STATE_FIELDS",
    "REQUIREMENT_STATUSES",
    "RequirementRecord",
    "RequirementSuggestion",
    "RequirementSuggestionProvider",
    "RequirementVersionSnapshot",
    "RuleBasedRequirementParser",
    "StructuredRequirement",
    "TRI_STATE_VALUES",
    "TransferRequirement",
    "UNLOADING_MODES",
    "apply_requirement_suggestions",
    "requirement_field_value",
]
