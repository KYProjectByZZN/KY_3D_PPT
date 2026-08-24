"""Historical retrieval and candidate generation for auto-solution v2."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping, Sequence
from uuid import uuid4

from .requirement_management import RequirementRecord


CANDIDATE_STATUSES = {"draft", "confirmed", "archived"}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _text_list(raw: Any) -> list[str]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [_text(value) for value in raw if _text(value)]


@dataclass
class HistoricalSolutionRecord:
    id: str
    project_name: str
    product_type: str = ""
    product_size: str = ""
    inspection_items: list[str] = field(default_factory=list)
    cycle_time: str = ""
    loading_mode: str = ""
    unloading_mode: str = ""
    process_flow: list[str] = field(default_factory=list)
    stations: list[dict[str, str]] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    layout_summary: str = ""
    reference_images: list[str] = field(default_factory=list)
    key_parameters: dict[str, str] = field(default_factory=dict)
    known_issues: list[str] = field(default_factory=list)
    special_requirements: str = ""
    source_kind: str = "user"
    verified: bool = False

    def validate(self) -> None:
        if not self.id or not self.project_name:
            raise ValueError("历史方案必须包含 id 和项目名称")
        if self.source_kind not in {"user", "demo"}:
            raise ValueError("历史方案来源必须是 user 或 demo")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "id": self.id,
            "projectName": self.project_name,
            "productType": self.product_type,
            "productSize": self.product_size,
            "inspectionItems": list(self.inspection_items),
            "cycleTime": self.cycle_time,
            "loadingMode": self.loading_mode,
            "unloadingMode": self.unloading_mode,
            "processFlow": list(self.process_flow),
            "stations": [dict(value) for value in self.stations],
            "modules": list(self.modules),
            "layoutSummary": self.layout_summary,
            "referenceImages": list(self.reference_images),
            "keyParameters": dict(self.key_parameters),
            "knownIssues": list(self.known_issues),
            "specialRequirements": self.special_requirements,
            "sourceKind": self.source_kind,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "HistoricalSolutionRecord":
        item = cls(
            id=_text(raw.get("id")),
            project_name=_text(raw.get("projectName")),
            product_type=_text(raw.get("productType")),
            product_size=_text(raw.get("productSize")),
            inspection_items=_text_list(raw.get("inspectionItems", [])),
            cycle_time=_text(raw.get("cycleTime")),
            loading_mode=_text(raw.get("loadingMode")),
            unloading_mode=_text(raw.get("unloadingMode")),
            process_flow=_text_list(raw.get("processFlow", [])),
            stations=[dict(value) for value in raw.get("stations", []) if isinstance(value, Mapping)],
            modules=_text_list(raw.get("modules", [])),
            layout_summary=_text(raw.get("layoutSummary")),
            reference_images=_text_list(raw.get("referenceImages", [])),
            key_parameters={str(key): _text(value) for key, value in (raw.get("keyParameters") or {}).items()},
            known_issues=_text_list(raw.get("knownIssues", [])),
            special_requirements=_text(raw.get("specialRequirements")),
            source_kind=_text(raw.get("sourceKind") or "user"),
            verified=bool(raw.get("verified", False)),
        )
        item.validate()
        return item


@dataclass
class HistoricalMatch:
    record: HistoricalSolutionRecord
    score: int
    reasons: list[str] = field(default_factory=list)

    def to_reference_dict(self) -> dict[str, Any]:
        return {
            "historyId": self.record.id,
            "projectName": self.record.project_name,
            "score": self.score,
            "reasons": list(self.reasons),
            "sourceKind": self.record.source_kind,
            "knownIssues": list(self.record.known_issues),
        }


@dataclass
class CandidateStation:
    station_id: str
    name: str
    description: str
    reference_module: str = ""
    reference_project: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "stationId": self.station_id,
            "name": self.name,
            "description": self.description,
            "referenceModule": self.reference_module,
            "referenceProject": self.reference_project,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "CandidateStation":
        return cls(
            station_id=_text(raw.get("stationId")),
            name=_text(raw.get("name")),
            description=_text(raw.get("description")),
            reference_module=_text(raw.get("referenceModule")),
            reference_project=_text(raw.get("referenceProject")),
        )


@dataclass
class DrawingSpecification:
    drawing_type: str
    product: dict[str, str]
    overall_layout: str
    process_flow: list[str]
    stations: list[dict[str, Any]]
    motion_relations: list[str]
    key_structures: list[str]
    annotations: list[str]
    prohibited_elements: list[str]
    reference_images: list[str]

    def validate(self) -> None:
        if not self.drawing_type or not self.overall_layout:
            raise ValueError("DrawingSpecification 缺少 drawingType 或 overallLayout")
        if not self.process_flow:
            raise ValueError("DrawingSpecification 必须包含 processFlow")
        if not self.stations:
            raise ValueError("DrawingSpecification 必须包含 stations")
        for station in self.stations:
            if not _text(station.get("stationId")) or not _text(station.get("name")):
                raise ValueError("DrawingSpecification 工位缺少 stationId 或 name")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "drawingType": self.drawing_type,
            "product": dict(self.product),
            "overallLayout": self.overall_layout,
            "processFlow": list(self.process_flow),
            "stations": [dict(value) for value in self.stations],
            "motionRelations": list(self.motion_relations),
            "keyStructures": list(self.key_structures),
            "annotations": list(self.annotations),
            "prohibitedElements": list(self.prohibited_elements),
            "referenceImages": list(self.reference_images),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "DrawingSpecification":
        item = cls(
            drawing_type=_text(raw.get("drawingType")),
            product={str(key): _text(value) for key, value in (raw.get("product") or {}).items()},
            overall_layout=_text(raw.get("overallLayout")),
            process_flow=_text_list(raw.get("processFlow", [])),
            stations=[dict(value) for value in raw.get("stations", []) if isinstance(value, Mapping)],
            motion_relations=_text_list(raw.get("motionRelations", [])),
            key_structures=_text_list(raw.get("keyStructures", [])),
            annotations=_text_list(raw.get("annotations", [])),
            prohibited_elements=_text_list(raw.get("prohibitedElements", [])),
            reference_images=_text_list(raw.get("referenceImages", [])),
        )
        item.validate()
        return item


@dataclass
class CandidateSolution:
    id: str
    requirement_id: str
    version: int
    historical_references: list[dict[str, Any]]
    process_flow: list[str]
    stations: list[CandidateStation]
    drawing_specification: DrawingSpecification
    drawing_prompt: str
    created_time: str
    created_by: str
    status: str = "draft"

    def validate(self) -> None:
        if not self.id or not self.requirement_id:
            raise ValueError("候选方案缺少 id 或 requirementId")
        if self.version < 1:
            raise ValueError("候选方案版本必须从 V1 开始")
        if self.status not in CANDIDATE_STATUSES:
            raise ValueError(f"未知候选方案状态：{self.status}")
        if not self.process_flow or not self.stations:
            raise ValueError("候选方案必须包含工艺流程和工位")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "id": self.id,
            "requirementId": self.requirement_id,
            "version": self.version,
            "historicalReferences": [dict(value) for value in self.historical_references],
            "processFlow": list(self.process_flow),
            "stations": [value.to_dict() for value in self.stations],
            "drawingSpecification": self.drawing_specification.to_dict(),
            "drawingPrompt": self.drawing_prompt,
            "createdTime": self.created_time,
            "createdBy": self.created_by,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "CandidateSolution":
        item = cls(
            id=_text(raw.get("id")),
            requirement_id=_text(raw.get("requirementId")),
            version=int(raw.get("version") or 1),
            historical_references=[dict(value) for value in raw.get("historicalReferences", []) if isinstance(value, Mapping)],
            process_flow=_text_list(raw.get("processFlow", [])),
            stations=[CandidateStation.from_dict(value) for value in raw.get("stations", []) if isinstance(value, Mapping)],
            drawing_specification=DrawingSpecification.from_dict(raw.get("drawingSpecification") or {}),
            drawing_prompt=str(raw.get("drawingPrompt") or ""),
            created_time=_text(raw.get("createdTime")),
            created_by=_text(raw.get("createdBy")),
            status=_text(raw.get("status") or "draft"),
        )
        item.validate()
        return item


def _number(value: str) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", value or "")
    return float(match.group(0)) if match else None


def _normalized_size(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\d+(?:\.\d+)?", value or ""))


def _keywords(value: str) -> set[str]:
    return {
        token.lower()
        for token in re.split(r"[\s,，、;；。/]+", value or "")
        if len(token.strip()) >= 2
    }


class HistoricalSolutionRetriever:
    """Small explainable matcher; it intentionally does not require a vector DB."""

    def retrieve(
        self,
        requirement: RequirementRecord,
        records: Sequence[HistoricalSolutionRecord],
        limit: int = 5,
    ) -> list[HistoricalMatch]:
        structured = requirement.structured_requirement
        target_type = structured.basic_info.product_type.lower()
        target_size = _normalized_size(structured.basic_info.size)
        target_inspections = {item.name.lower() for item in structured.inspection_items}
        target_cycle = _number(structured.capacity_and_cycle.target_cycle)
        target_special = _keywords(structured.special_requirements)
        matches: list[HistoricalMatch] = []
        for record in records:
            score = 0
            reasons: list[str] = []
            record_type = record.product_type.lower()
            if target_type and record_type:
                if target_type == record_type:
                    score += 25
                    reasons.append("产品类型相同 +25")
                elif target_type in record_type or record_type in target_type:
                    score += 15
                    reasons.append("产品类型近似 +15")
            record_size = _normalized_size(record.product_size)
            if target_size and record_size:
                if target_size == record_size:
                    score += 10
                    reasons.append("产品尺寸相同 +10")
                elif set(target_size) & set(record_size):
                    score += 5
                    reasons.append("产品尺寸部分相近 +5")
            history_inspections = {value.lower() for value in record.inspection_items}
            overlap = target_inspections & history_inspections
            if overlap:
                inspection_score = round(25 * len(overlap) / max(len(target_inspections), 1))
                score += inspection_score
                reasons.append(f"检测项命中 {len(overlap)} 项 +{inspection_score}")
            if structured.loading.mode != "未知" and structured.loading.mode == record.loading_mode:
                score += 10
                reasons.append("上料方式相同 +10")
            if structured.unloading.mode != "未知" and structured.unloading.mode == record.unloading_mode:
                score += 5
                reasons.append("下料方式相同 +5")
            record_cycle = _number(record.cycle_time)
            if target_cycle is not None and record_cycle is not None:
                delta = abs(target_cycle - record_cycle) / max(target_cycle, 0.001)
                if delta <= 0.1:
                    score += 15
                    reasons.append("节拍偏差不超过10% +15")
                elif delta <= 0.3:
                    score += 8
                    reasons.append("节拍偏差不超过30% +8")
            special_overlap = target_special & _keywords(record.special_requirements)
            if special_overlap:
                special_score = min(10, 3 * len(special_overlap))
                score += special_score
                reasons.append(f"特殊要求关键词命中 +{special_score}")
            if score > 0:
                matches.append(HistoricalMatch(record=record, score=min(score, 100), reasons=reasons))
        matches.sort(key=lambda value: (-value.score, value.record.project_name))
        return matches[:limit]


class DrawingSpecificationBuilder:
    def build(
        self,
        requirement: RequirementRecord,
        process_flow: Sequence[str],
        stations: Sequence[CandidateStation],
        matches: Sequence[HistoricalMatch],
    ) -> DrawingSpecification:
        structured = requirement.structured_requirement
        station_specs: list[dict[str, Any]] = []
        count = len(stations)
        for index, station in enumerate(stations, 1):
            station_specs.append(
                {
                    "stationId": station.station_id,
                    "name": station.name,
                    "position": f"从左到右第 {index}/{count} 个工位",
                    "description": station.description,
                    "fixedParts": ["机架", "安装底板", "安全防护"],
                    "movingParts": self._moving_parts(station.name),
                    "visionParts": self._vision_parts(station.name, structured.inspection_items),
                    "fixture": "产品定位治具" if "定位" in station.name or "检测" in station.name else "",
                    "referenceModule": station.reference_module,
                    "referenceProject": station.reference_project,
                }
            )
        motion_relations = [
            f"产品从设备左侧由{structured.loading.mode}进入 {stations[0].station_id}",
            *[
                f"产品沿主输送方向从 {stations[index].station_id} 移动到 {stations[index + 1].station_id}"
                for index in range(max(0, len(stations) - 1))
            ],
            f"产品从 {stations[-1].station_id} 向设备右侧通过{structured.unloading.mode}离开",
        ]
        conditions = [
            label
            for key, label in (
                ("oil", "带油"),
                ("water", "带水"),
                ("dust", "有粉尘"),
                ("reflective", "高反光"),
                ("transparent", "透明"),
                ("easyScratch", "易划伤"),
                ("deformable", "易变形"),
                ("burr", "有毛刺"),
                ("sharpEdge", "有尖锐边缘"),
            )
            if structured.product_states.get(key) == "yes"
        ]
        annotations = [
            f"产品：{requirement.product_name or '未命名产品'}",
            f"产品尺寸：{structured.basic_info.size or '待确认'}",
            f"目标节拍：{structured.capacity_and_cycle.target_cycle or '待确认'}",
            f"检测项：{'、'.join(item.name for item in structured.inspection_items) or '待确认'}",
        ]
        if conditions:
            annotations.append("产品状态：" + "、".join(conditions))
        reference_images = [
            image
            for match in matches[:3]
            for image in match.record.reference_images
        ]
        return DrawingSpecification(
            drawing_type="工业自动化设备二维俯视布局示意图",
            product={
                "name": requirement.product_name,
                "type": structured.basic_info.product_type,
                "model": structured.basic_info.model,
                "size": structured.basic_info.size,
                "material": structured.basic_info.material,
            },
            overall_layout=f"单条水平主线，{count} 个工位从左到右等距排列；设备入口在左，出口在右",
            process_flow=list(process_flow),
            stations=station_specs,
            motion_relations=motion_relations,
            key_structures=[
                "一体式工业铝型材或钣金机架",
                "连续主输送通道",
                "各工位独立安装底板与可维护空间",
                "检测工位采用遮光防护并预留相机、镜头和光源安装位",
            ],
            annotations=annotations,
            prohibited_elements=[
                "禁止添加需求和工位定义中未出现的机械臂或旋转机构",
                "禁止把概念示意图标注为施工图、CAD图或最终工程结构",
                "禁止省略产品运动方向箭头、工位编号和相对位置",
                "禁止使用圆角卡通风格、科幻光效或无法制造的悬浮部件",
            ],
            reference_images=reference_images,
        )

    def synchronize(
        self,
        specification: DrawingSpecification,
        requirement: RequirementRecord,
        process_flow: Sequence[str],
        stations: Sequence[CandidateStation],
    ) -> DrawingSpecification:
        """Keep duplicated drawing views one-way synchronized from the candidate."""

        existing = {
            str(value.get("stationId") or ""): dict(value)
            for value in specification.stations
        }
        count = len(stations)
        synchronized: list[dict[str, Any]] = []
        inspections = requirement.structured_requirement.inspection_items
        for index, station in enumerate(stations, 1):
            value = existing.get(station.station_id, {})
            value.update(
                {
                    "stationId": station.station_id,
                    "name": station.name,
                    "position": f"从左到右第 {index}/{count} 个工位",
                    "description": station.description,
                    "referenceModule": station.reference_module,
                    "referenceProject": station.reference_project,
                }
            )
            value.setdefault("fixedParts", ["机架", "安装底板", "安全防护"])
            value.setdefault("movingParts", self._moving_parts(station.name))
            value.setdefault("visionParts", self._vision_parts(station.name, inspections))
            value.setdefault(
                "fixture",
                "产品定位治具" if "定位" in station.name or "检测" in station.name else "",
            )
            synchronized.append(value)
        loading = requirement.structured_requirement.loading.mode
        unloading = requirement.structured_requirement.unloading.mode
        motions: list[str] = []
        if stations:
            motions = [
                f"产品从设备左侧由{loading}进入 {stations[0].station_id}",
                *[
                    f"产品沿主输送方向从 {stations[index].station_id} 移动到 {stations[index + 1].station_id}"
                    for index in range(len(stations) - 1)
                ],
                f"产品从 {stations[-1].station_id} 向设备右侧通过{unloading}离开",
            ]
        specification.process_flow = list(process_flow)
        specification.stations = synchronized
        specification.motion_relations = motions
        return specification

    @staticmethod
    def _moving_parts(station_name: str) -> list[str]:
        if "上料" in station_name:
            return ["上料机构", "进料方向箭头"]
        if "下料" in station_name or "分选" in station_name:
            return ["下料或分选机构", "出料方向箭头"]
        if "检测" in station_name:
            return ["产品输送或分度机构"]
        return ["产品输送机构"]

    @staticmethod
    def _vision_parts(station_name: str, inspection_items: Sequence[Any]) -> list[str]:
        if "检测" not in station_name:
            return []
        item_names = "、".join(item.name for item in inspection_items) or "待确认检测项"
        return [f"工业相机与镜头（面向{item_names}）", "与相机光轴匹配的工业光源"]


class DrawingPromptBuilder:
    def build(self, specification: DrawingSpecification) -> str:
        product = specification.product
        station_lines = []
        for station in specification.stations:
            station_lines.append(
                "- {stationId} {name}：{position}；{description}；固定部件={fixed}；"
                "移动部件={moving}；视觉部件={vision}；夹具={fixture}。".format(
                    stationId=station.get("stationId", ""),
                    name=station.get("name", ""),
                    position=station.get("position", ""),
                    description=station.get("description", ""),
                    fixed="、".join(station.get("fixedParts") or []) or "无",
                    moving="、".join(station.get("movingParts") or []) or "无",
                    vision="、".join(station.get("visionParts") or []) or "无",
                    fixture=station.get("fixture") or "无",
                )
            )
        return "\n".join(
            [
                f"生成一张{specification.drawing_type}。",
                "画面风格：白色或浅灰工程图背景，深灰设备主体，企业红作为少量方向和重点标识；正投影、清晰线稿、无透视夸张。",
                f"产品：{product.get('name') or '未命名产品'}；类型={product.get('type') or '待确认'}；型号={product.get('model') or '待确认'}；尺寸={product.get('size') or '待确认'}；材料={product.get('material') or '待确认'}。",
                f"总体空间关系：{specification.overall_layout}。",
                "工位数量和相对位置必须严格如下：",
                *station_lines,
                "产品与运动关系：",
                *[f"- {value}" for value in specification.motion_relations],
                "关键结构：" + "；".join(specification.key_structures) + "。",
                "必须标注：" + "；".join(specification.annotations) + "。",
                "禁止项：" + "；".join(specification.prohibited_elements) + "。",
                "输出要求：16:9 横向构图，所有工位完整可见，明确画出输入→输出主线、产品位置、运动箭头、相机/光源/夹具相对位置和工位编号；仅作为方案讨论用二维概念示意图。",
            ]
        )


class CandidateSolutionGenerator:
    def __init__(
        self,
        specification_builder: DrawingSpecificationBuilder | None = None,
        prompt_builder: DrawingPromptBuilder | None = None,
    ) -> None:
        self.specification_builder = specification_builder or DrawingSpecificationBuilder()
        self.prompt_builder = prompt_builder or DrawingPromptBuilder()

    def generate(
        self,
        requirement: RequirementRecord,
        matches: Sequence[HistoricalMatch],
        version: int,
        created_time: str,
        created_by: str,
    ) -> CandidateSolution:
        structured = requirement.structured_requirement
        inspection_names = [item.name for item in structured.inspection_items]
        inspection_text = "、".join(inspection_names) or "待确认检测项"
        process_flow = [
            structured.loading.mode if structured.loading.mode != "未知" else "上料方式待确认",
            "产品到位与精定位",
            f"视觉/测量检测（{inspection_text}）",
            "结果判定与数据记录",
            structured.unloading.mode if structured.unloading.mode != "未知" else "下料方式待确认",
        ]
        top = matches[0].record if matches else None
        reference_project = top.project_name if top else ""
        modules = list(top.modules) if top else []
        stations = [
            CandidateStation(
                station_id="S01",
                name="上料工位",
                description=f"采用{structured.loading.mode}，将产品送入主输送线；{structured.loading.note or '上料接口尺寸待工程确认'}。",
                reference_module=self._module_for(modules, "上料"),
                reference_project=reference_project,
            ),
            CandidateStation(
                station_id="S02",
                name="定位与检测工位",
                description=f"对产品精定位后完成{inspection_text}；精度、视野和相机数量以已确认需求为准。",
                reference_module=self._module_for(modules, "检测"),
                reference_project=reference_project,
            ),
            CandidateStation(
                station_id="S03",
                name="结果处理与下料工位",
                description=f"记录检测结果并采用{structured.unloading.mode}输出；{structured.unloading.note or '分选逻辑待工程确认'}。",
                reference_module=self._module_for(modules, "下料"),
                reference_project=reference_project,
            ),
        ]
        specification = self.specification_builder.build(
            requirement,
            process_flow,
            stations,
            matches,
        )
        candidate = CandidateSolution(
            id=str(uuid4()),
            requirement_id=requirement.id,
            version=version,
            historical_references=[match.to_reference_dict() for match in matches],
            process_flow=process_flow,
            stations=stations,
            drawing_specification=specification,
            drawing_prompt=self.prompt_builder.build(specification),
            created_time=created_time,
            created_by=created_by,
        )
        candidate.validate()
        return candidate

    @staticmethod
    def _module_for(modules: Sequence[str], keyword: str) -> str:
        return next((value for value in modules if keyword in value), modules[0] if modules else "")


def demo_historical_solutions() -> list[HistoricalSolutionRecord]:
    """Clearly labelled demo data used only to exercise the first usable chain."""

    return [
        HistoricalSolutionRecord(
            id="DEMO-HIS-001",
            project_name="演示案例A｜金属冲压件外观检测",
            product_type="金属冲压件",
            product_size="85×45×12 mm",
            inspection_items=["划伤", "压伤", "缺口", "尺寸"],
            cycle_time="1.5 s/件",
            loading_mode="振动盘上料",
            unloading_mode="OK/NG分选",
            process_flow=["振动盘上料", "精定位", "多视角检测", "OK/NG分选"],
            stations=[
                {"stationId": "S01", "name": "振动上料"},
                {"stationId": "S02", "name": "视觉检测"},
                {"stationId": "S03", "name": "分选"},
            ],
            modules=["振动盘上料模块", "多相机检测模块", "气吹分选模块"],
            layout_summary="左进右出直线式三工位",
            key_parameters={"cameraCount": "4", "cycleTime": "1.5 s/件"},
            known_issues=["高反光表面需要重新验证光源角度"],
            special_requirements="高反光表面",
            source_kind="demo",
            verified=True,
        ),
        HistoricalSolutionRecord(
            id="DEMO-HIS-002",
            project_name="演示案例B｜透明塑料件尺寸与缺陷检测",
            product_type="透明塑料件",
            product_size="120×60×20 mm",
            inspection_items=["尺寸", "缺口", "脏污", "有无"],
            cycle_time="2.0 s/件",
            loading_mode="皮带线上料",
            unloading_mode="皮带线下料",
            process_flow=["皮带线上料", "挡停定位", "背光检测", "皮带线下料"],
            modules=["皮带输送模块", "背光视觉检测模块", "挡停定位模块"],
            layout_summary="直线皮带输送，检测舱位于中部",
            known_issues=["透明件边缘算法对环境杂散光敏感"],
            special_requirements="透明 易划伤",
            source_kind="demo",
            verified=True,
        ),
        HistoricalSolutionRecord(
            id="DEMO-HIS-003",
            project_name="演示案例C｜托盘电子件字符检测",
            product_type="电子装配件",
            product_size="35×25×8 mm",
            inspection_items=["字符", "二维码", "装配", "有无"],
            cycle_time="3.0 s/盘",
            loading_mode="料盘上料",
            unloading_mode="料盘收料",
            process_flow=["料盘上料", "XY定位", "俯视检测", "料盘收料"],
            modules=["料盘升降模块", "XY平台检测模块", "料盘收料模块"],
            layout_summary="左右双料仓，中部XY检测平台",
            known_issues=["字符反光需要偏振方案复核"],
            special_requirements="防静电",
            source_kind="demo",
            verified=False,
        ),
    ]


__all__ = [
    "CandidateSolution",
    "CandidateSolutionGenerator",
    "CandidateStation",
    "DrawingPromptBuilder",
    "DrawingSpecification",
    "DrawingSpecificationBuilder",
    "HistoricalMatch",
    "HistoricalSolutionRecord",
    "HistoricalSolutionRetriever",
    "demo_historical_solutions",
]
