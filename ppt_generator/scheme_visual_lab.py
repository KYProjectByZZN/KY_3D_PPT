"""Deterministic scheme-visual laboratory core.

The laboratory intentionally stops before image generation.  It converts an
approved drawing specification into traceable, provider-neutral intermediate
artifacts that engineers can inspect first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from html import escape
import json
from typing import Any, Mapping, Sequence

from .solution_generation import DrawingSpecification


LAB_SCHEMA_VERSION = "scheme-visual-lab-v1"
LAYOUT_VERSION = "industrial-single-line-v1"
PROMPT_TEMPLATE_VERSION = "equipment-structure-v1"
CANVAS_WIDTH = 1600
CANVAS_HEIGHT = 900
MIN_STATIONS = 1
MAX_STATIONS = 8


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _text_list(raw: Any) -> list[str]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [_text(value) for value in raw if _text(value)]


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _stable_hash(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _short(value: str, limit: int) -> str:
    value = _text(value)
    if len(value) <= limit:
        return value
    return value[: max(1, limit - 1)] + "…"


@dataclass(frozen=True)
class LayoutStation:
    station_id: str
    name: str
    description: str
    position: str
    x: int
    y: int
    width: int
    height: int
    fixed_parts: tuple[str, ...] = ()
    moving_parts: tuple[str, ...] = ()
    vision_parts: tuple[str, ...] = ()
    fixture: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "stationId": self.station_id,
            "name": self.name,
            "description": self.description,
            "position": self.position,
            "bounds": {
                "x": self.x,
                "y": self.y,
                "width": self.width,
                "height": self.height,
            },
            "fixedParts": list(self.fixed_parts),
            "movingParts": list(self.moving_parts),
            "visionParts": list(self.vision_parts),
            "fixture": self.fixture,
        }


@dataclass(frozen=True)
class FlowConnection:
    connection_id: str
    source: str
    target: str
    start_x: int
    end_x: int
    y: int
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "connectionId": self.connection_id,
            "source": self.source,
            "target": self.target,
            "start": {"x": self.start_x, "y": self.y},
            "end": {"x": self.end_x, "y": self.y},
            "label": self.label,
        }


@dataclass(frozen=True)
class LayoutPlan:
    schema_version: str
    layout_version: str
    canvas_width: int
    canvas_height: int
    drawing_type: str
    product_name: str
    overall_layout: str
    stations: tuple[LayoutStation, ...]
    connections: tuple[FlowConnection, ...]
    annotations: tuple[str, ...]
    prohibited_elements: tuple[str, ...]
    source_spec_hash: str
    layout_hash: str

    def _payload(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "layoutVersion": self.layout_version,
            "canvas": {
                "width": self.canvas_width,
                "height": self.canvas_height,
            },
            "drawingType": self.drawing_type,
            "productName": self.product_name,
            "overallLayout": self.overall_layout,
            "stations": [station.to_dict() for station in self.stations],
            "connections": [connection.to_dict() for connection in self.connections],
            "annotations": list(self.annotations),
            "prohibitedElements": list(self.prohibited_elements),
            "sourceSpecHash": self.source_spec_hash,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload()
        payload["layoutHash"] = self.layout_hash
        return payload


@dataclass(frozen=True)
class PromptRecipe:
    recipe_version: str
    provider: str
    model: str
    workflow_version: str
    prompt_template_version: str
    positive_prompt: str
    negative_prompt: str
    seed_pool: tuple[int, ...]
    width: int
    height: int
    steps: int
    guidance: float
    control_mode: str
    control_strength: float
    evaluation_checklist: tuple[str, ...]
    source_spec_hash: str
    layout_hash: str
    recipe_hash: str

    def _payload(self) -> dict[str, Any]:
        return {
            "recipeVersion": self.recipe_version,
            "provider": self.provider,
            "model": self.model,
            "workflowVersion": self.workflow_version,
            "promptTemplateVersion": self.prompt_template_version,
            "positivePrompt": self.positive_prompt,
            "negativePrompt": self.negative_prompt,
            "seedPool": list(self.seed_pool),
            "image": {"width": self.width, "height": self.height},
            "generation": {
                "steps": self.steps,
                "guidance": self.guidance,
            },
            "structureControl": {
                "mode": self.control_mode,
                "strength": self.control_strength,
                "input": "本次生成的 SVG 结构示意图",
            },
            "evaluationChecklist": list(self.evaluation_checklist),
            "sourceSpecHash": self.source_spec_hash,
            "layoutHash": self.layout_hash,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload()
        payload["recipeHash"] = self.recipe_hash
        return payload


@dataclass(frozen=True)
class SchemeVisualLabResult:
    layout_plan: LayoutPlan
    svg: str
    prompt_recipe: PromptRecipe


class SchemeVisualLabService:
    """Create deterministic structural artifacts from one drawing spec."""

    def run(self, specification: DrawingSpecification) -> SchemeVisualLabResult:
        plan = self.build_layout_plan(specification)
        svg = self.render_layout_svg(plan)
        recipe = self.build_prompt_recipe(specification, plan)
        return SchemeVisualLabResult(
            layout_plan=plan,
            svg=svg,
            prompt_recipe=recipe,
        )

    def build_layout_plan(self, specification: DrawingSpecification) -> LayoutPlan:
        specification.validate()
        self._validate_specification(specification)
        source_spec_hash = _stable_hash(specification.to_dict())
        station_count = len(specification.stations)
        gap = 56 if station_count <= 5 else 34
        available_width = 1120
        station_width = min(
            300,
            (available_width - gap * (station_count - 1)) // station_count,
        )
        station_height = 300
        occupied_width = station_width * station_count + gap * (station_count - 1)
        start_x = (CANVAS_WIDTH - occupied_width) // 2
        station_y = 310

        stations: list[LayoutStation] = []
        for index, raw in enumerate(specification.stations, 1):
            stations.append(
                LayoutStation(
                    station_id=_text(raw.get("stationId")),
                    name=_text(raw.get("name")),
                    description=_text(raw.get("description")),
                    position=_text(raw.get("position")) or f"从左到右第 {index} 个工位",
                    x=start_x + (index - 1) * (station_width + gap),
                    y=station_y,
                    width=station_width,
                    height=station_height,
                    fixed_parts=tuple(_text_list(raw.get("fixedParts", []))),
                    moving_parts=tuple(_text_list(raw.get("movingParts", []))),
                    vision_parts=tuple(_text_list(raw.get("visionParts", []))),
                    fixture=_text(raw.get("fixture")),
                )
            )

        flow_y = station_y + 194
        connections = [
            FlowConnection(
                connection_id="flow-input",
                source="INPUT",
                target=stations[0].station_id,
                start_x=80,
                end_x=stations[0].x,
                y=flow_y,
                label="输入",
            )
        ]
        for index in range(station_count - 1):
            current = stations[index]
            following = stations[index + 1]
            connections.append(
                FlowConnection(
                    connection_id=f"flow-{current.station_id}-{following.station_id}",
                    source=current.station_id,
                    target=following.station_id,
                    start_x=current.x + current.width,
                    end_x=following.x,
                    y=flow_y,
                    label="流转",
                )
            )
        connections.append(
            FlowConnection(
                connection_id="flow-output",
                source=stations[-1].station_id,
                target="OUTPUT",
                start_x=stations[-1].x + stations[-1].width,
                end_x=1520,
                y=flow_y,
                label="输出",
            )
        )

        temporary = LayoutPlan(
            schema_version=LAB_SCHEMA_VERSION,
            layout_version=LAYOUT_VERSION,
            canvas_width=CANVAS_WIDTH,
            canvas_height=CANVAS_HEIGHT,
            drawing_type=specification.drawing_type,
            product_name=_text(specification.product.get("name")) or "未命名产品",
            overall_layout=specification.overall_layout,
            stations=tuple(stations),
            connections=tuple(connections),
            annotations=tuple(specification.annotations),
            prohibited_elements=tuple(specification.prohibited_elements),
            source_spec_hash=source_spec_hash,
            layout_hash="",
        )
        return LayoutPlan(
            **{
                **temporary.__dict__,
                "layout_hash": _stable_hash(temporary._payload()),
            }
        )

    def build_prompt_recipe(
        self,
        specification: DrawingSpecification,
        plan: LayoutPlan,
    ) -> PromptRecipe:
        station_lines: list[str] = []
        confirmed_visuals: list[str] = []
        for index, station in enumerate(plan.stations, 1):
            details: list[str] = []
            if station.fixed_parts:
                details.append("固定部件：" + "、".join(station.fixed_parts))
            if station.moving_parts:
                details.append("运动部件：" + "、".join(station.moving_parts))
            if station.vision_parts:
                value = "、".join(station.vision_parts)
                details.append("视觉部件：" + value)
                confirmed_visuals.append(f"{station.station_id}={value}")
            if station.fixture:
                details.append("治具：" + station.fixture)
            suffix = "；" + "；".join(details) if details else ""
            station_lines.append(
                f"{index}. {station.station_id}「{station.name}」{suffix}"
            )

        annotations = "；".join(specification.annotations) or "无额外标注"
        structures = "；".join(specification.key_structures) or "仅按结构控制图表达"
        positive_prompt = "\n".join(
            [
                "生成工业自动化设备技术方案结构效果图。",
                f"产品：{plan.product_name}。画面为 16:9，严格保留 {len(plan.stations)} 个工位。",
                "设备入口在左、出口在右，产品沿一条水平主线从左向右流动。",
                "工位顺序和名称必须逐项一致，不合并、不拆分、不调换：",
                *station_lines,
                f"总体布局：{specification.overall_layout}",
                f"关键结构：{structures}",
                f"工程标注：{annotations}",
                "使用本次 SVG 结构示意图作为线稿/边缘结构控制输入，保持外轮廓、工位位置和流向。",
                "视觉风格：真实可制造的工业钣金与铝型材设备，正交或轻微俯视，白灰背景，深灰结构，少量工业红强调，光照均匀，无科幻光效。",
                "这是结构效果图，不是 CAD 施工图；文字标签仅作为核验辅助。",
            ]
        )
        user_prohibitions = "；".join(specification.prohibited_elements)
        negative_parts = [
            "禁止改变工位数量、编号、顺序和主输送方向",
            "禁止增加任何未在结构化规格中确认的视觉部件、执行机构或悬浮结构",
            "禁止卡通、科幻、霓虹、发光描边、圆润玩具感、不可制造结构",
            "禁止把概念效果图标注为 CAD 图、施工图或最终工程结构",
            "禁止重复工位、遮挡流向箭头、裁切设备入口或出口",
        ]
        if user_prohibitions:
            negative_parts.append("用户禁止项：" + user_prohibitions)
        negative_prompt = "；".join(negative_parts)
        checklist = self._evaluation_checklist(plan, confirmed_visuals)

        temporary = PromptRecipe(
            recipe_version=LAB_SCHEMA_VERSION,
            provider="unconfigured",
            model="",
            workflow_version=LAYOUT_VERSION,
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            seed_pool=(101, 202, 303, 404),
            width=1536,
            height=864,
            steps=30,
            guidance=6.5,
            control_mode="lineart",
            control_strength=0.85,
            evaluation_checklist=tuple(checklist),
            source_spec_hash=plan.source_spec_hash,
            layout_hash=plan.layout_hash,
            recipe_hash="",
        )
        return PromptRecipe(
            **{
                **temporary.__dict__,
                "recipe_hash": _stable_hash(temporary._payload()),
            }
        )

    def render_layout_svg(self, plan: LayoutPlan) -> str:
        def x(value: Any) -> str:
            return escape(_text(value), quote=True)

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{plan.canvas_width}" '
                f'height="{plan.canvas_height}" viewBox="0 0 {plan.canvas_width} {plan.canvas_height}">'
            ),
            "<defs>",
            '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#C62026"/></marker>',
            '<filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#111827" flood-opacity="0.14"/></filter>',
            "<style>",
            "text{font-family:'Microsoft YaHei','Noto Sans CJK SC',sans-serif;fill:#20242A}",
            ".small{font-size:17px;fill:#5F6872}.body{font-size:18px}.label{font-size:16px;fill:#66707A}",
            ".station-title{font-size:24px;font-weight:700;fill:#FFFFFF}.station-id{font-size:17px;font-weight:700;fill:#C62026}",
            ".header-title{fill:#FFFFFF}.header-subtitle{fill:#D9DDE1}.accent{fill:#C62026}",
            "</style>",
            "</defs>",
            '<rect x="0" y="0" width="1600" height="900" fill="#F4F5F6"/>',
            '<rect x="0" y="0" width="1600" height="96" fill="#20242A"/>',
            f'<text x="70" y="58" font-size="32" font-weight="700" class="header-title">{x(plan.product_name)} · 设备结构方案</text>',
            '<text x="1530" y="56" font-size="18" text-anchor="end" class="header-subtitle">方案图实验室</text>',
            '<rect x="70" y="126" width="8" height="64" fill="#C62026"/>',
            f'<text x="98" y="153" font-size="23" font-weight="700">{x(_short(plan.drawing_type, 48))}</text>',
            f'<text x="98" y="184" class="small">{x(_short(plan.overall_layout, 82))}</text>',
            '<text x="1530" y="150" text-anchor="end" font-size="20" font-weight="700" class="accent">结构示意图</text>',
            '<text x="1530" y="180" text-anchor="end" class="small">非 CAD 施工图 · 部件以确认输入为准</text>',
            '<line x1="70" y1="226" x2="1530" y2="226" stroke="#D8DCE0" stroke-width="2"/>',
            '<rect x="70" y="474" width="1460" height="60" fill="#DDE1E4" stroke="#AEB5BC" stroke-width="2"/>',
            '<line x1="90" y1="504" x2="1510" y2="504" stroke="#7B858F" stroke-width="4" stroke-dasharray="16 12"/>',
        ]

        for connection in plan.connections:
            lines.extend(
                [
                    (
                        f'<line id="{x(connection.connection_id)}" x1="{connection.start_x}" '
                        f'y1="{connection.y}" x2="{connection.end_x}" y2="{connection.y}" '
                        'stroke="#C62026" stroke-width="5" marker-end="url(#arrow)"/>'
                    ),
                    (
                        f'<text x="{(connection.start_x + connection.end_x) // 2}" '
                        f'y="{connection.y - 18}" text-anchor="middle" class="label">{x(connection.label)}</text>'
                    ),
                ]
            )

        for index, station in enumerate(plan.stations, 1):
            header_height = 64
            body_top = station.y + header_height
            lines.extend(
                [
                    f'<g data-station-id="{x(station.station_id)}">',
                    (
                        f'<rect x="{station.x}" y="{station.y}" width="{station.width}" '
                        f'height="{station.height}" fill="#FFFFFF" stroke="#8C959E" '
                        'stroke-width="2" filter="url(#softShadow)"/>'
                    ),
                    (
                        f'<rect x="{station.x}" y="{station.y}" width="{station.width}" '
                        f'height="{header_height}" fill="#343A40"/>'
                    ),
                    (
                        f'<rect x="{station.x}" y="{station.y}" width="8" '
                        f'height="{header_height}" fill="#C62026"/>'
                    ),
                    (
                        f'<text x="{station.x + 20}" y="{station.y + 27}" '
                        f'class="station-id">{x(station.station_id)}</text>'
                    ),
                    (
                        f'<text x="{station.x + 20}" y="{station.y + 52}" '
                        f'class="station-title">{x(_short(station.name, max(8, station.width // 22)))}</text>'
                    ),
                    (
                        f'<text x="{station.x + 18}" y="{body_top + 32}" '
                        f'class="small">第 {index}/{len(plan.stations)} 工位</text>'
                    ),
                ]
            )
            cursor_y = body_top + 68
            if station.description:
                lines.append(
                    f'<text x="{station.x + 18}" y="{cursor_y}" class="body">{x(_short(station.description, max(10, station.width // 18)))}</text>'
                )
                cursor_y += 36
            if station.vision_parts:
                lines.extend(
                    [
                        (
                            f'<rect x="{station.x + 16}" y="{cursor_y - 23}" '
                            f'width="{station.width - 32}" height="42" fill="#FFF3F3" '
                            'stroke="#D95055" stroke-width="1"/>'
                        ),
                        (
                            f'<text x="{station.x + 27}" y="{cursor_y + 5}" '
                            f'font-size="16" font-weight="700" fill="#A7191E">视觉｜{x(_short("、".join(station.vision_parts), max(8, station.width // 18)))}</text>'
                        ),
                    ]
                )
                cursor_y += 53
            if station.fixture:
                lines.extend(
                    [
                        (
                            f'<rect x="{station.x + 16}" y="{cursor_y - 23}" '
                            f'width="{station.width - 32}" height="42" fill="#EDF2F5" '
                            'stroke="#87939E" stroke-width="1"/>'
                        ),
                        (
                            f'<text x="{station.x + 27}" y="{cursor_y + 5}" '
                            f'font-size="16" font-weight="700">治具｜{x(_short(station.fixture, max(8, station.width // 18)))}</text>'
                        ),
                    ]
                )
            lines.extend(
                [
                    (
                        f'<line x1="{station.x + 18}" y1="{station.y + station.height - 42}" '
                        f'x2="{station.x + station.width - 18}" y2="{station.y + station.height - 42}" '
                        'stroke="#D7DBDF" stroke-width="2"/>'
                    ),
                    (
                        f'<text x="{station.x + station.width // 2}" y="{station.y + station.height - 15}" '
                        f'text-anchor="middle" class="label">{x(_short(station.position, max(10, station.width // 17)))}</text>'
                    ),
                    "</g>",
                ]
            )

        station_sequence = " → ".join(station.station_id for station in plan.stations)
        lines.extend(
            [
                '<rect x="70" y="674" width="1460" height="132" fill="#FFFFFF" stroke="#D4D9DE" stroke-width="2"/>',
                '<text x="94" y="713" font-size="19" font-weight="700" class="accent">核验基线</text>',
                f'<text x="94" y="749" class="body">工位顺序：{x(station_sequence)}</text>',
                f'<text x="94" y="782" class="small">布局哈希：{x(plan.layout_hash[:24])}…</text>',
                '<text x="1505" y="782" text-anchor="end" class="small">相同规格产生相同布局 · 人工确认后方可进入正式方案</text>',
                '<text x="70" y="858" class="small">KY Project · Scheme Visual Lab · deterministic structure preview</text>',
                "</svg>",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _validate_specification(specification: DrawingSpecification) -> None:
        station_count = len(specification.stations)
        if station_count < MIN_STATIONS or station_count > MAX_STATIONS:
            raise ValueError(
                f"方案图实验室仅支持 {MIN_STATIONS}～{MAX_STATIONS} 个工位，当前为 {station_count} 个"
            )
        station_ids = [_text(value.get("stationId")) for value in specification.stations]
        if len(set(station_ids)) != len(station_ids):
            raise ValueError("工位 stationId 不得重复")
        for raw in specification.stations:
            for key in ("fixedParts", "movingParts", "visionParts"):
                value = raw.get(key, [])
                if value is not None and (
                    not isinstance(value, Sequence) or isinstance(value, (str, bytes))
                ):
                    raise ValueError(f"工位 {raw.get('stationId')} 的 {key} 必须是数组")

    @staticmethod
    def _evaluation_checklist(
        plan: LayoutPlan,
        confirmed_visuals: Sequence[str],
    ) -> list[str]:
        sequence = " → ".join(station.station_id for station in plan.stations)
        checklist = [
            f"工位总数必须为 {len(plan.stations)} 个",
            f"从左到右顺序必须为 {sequence}",
            "必须显示左侧输入、右侧输出和连续的水平产品流向",
            "工位编号和名称必须与 DrawingSpecification 完全一致",
            "不得新增 DrawingSpecification 未确认的设备部件",
            "不得把结构效果图表述为 CAD 施工图或最终工程结构",
        ]
        if confirmed_visuals:
            checklist.append("已确认视觉部件位置必须保持：" + "；".join(confirmed_visuals))
        else:
            checklist.append("当前未确认视觉部件，图中不得自行补充")
        checklist.extend(
            f"不得出现用户禁止项：{value}" for value in plan.prohibited_elements
        )
        return checklist


def demo_drawing_specification() -> DrawingSpecification:
    """Return a reviewable three-station demo with explicit component scope."""

    return DrawingSpecification.from_dict(
        {
            "drawingType": "工业自动化视觉检测设备二维俯视布局示意图",
            "product": {
                "name": "筒形壳体",
                "type": "冲压件",
                "model": "演示样件",
                "size": "待确认",
                "material": "金属",
            },
            "overallLayout": "单条水平主线，三个工位从左到右排列，入口在左、出口在右",
            "processFlow": ["人工上料", "定位", "外观检测", "分选下料"],
            "stations": [
                {
                    "stationId": "ST01",
                    "name": "上料定位",
                    "position": "设备左侧入口",
                    "description": "样件进入并完成基准定位",
                    "fixedParts": ["机架", "导向机构"],
                    "movingParts": ["输送带"],
                    "visionParts": [],
                    "fixture": "产品定位治具",
                },
                {
                    "stationId": "ST02",
                    "name": "俯视检测",
                    "position": "设备中部",
                    "description": "检测上表面外观缺陷",
                    "fixedParts": ["遮光罩", "安装底板"],
                    "movingParts": ["输送带"],
                    "visionParts": ["工业相机", "镜头", "环形光源"],
                    "fixture": "检测定位治具",
                },
                {
                    "stationId": "ST03",
                    "name": "分选下料",
                    "position": "设备右侧出口",
                    "description": "按检测结果完成 OK/NG 分流",
                    "fixedParts": ["机架", "收料区"],
                    "movingParts": ["分选气缸"],
                    "visionParts": [],
                    "fixture": "",
                },
            ],
            "motionRelations": [
                "产品从设备左侧进入",
                "产品沿主输送线依次通过 ST01、ST02、ST03",
                "产品从设备右侧分选输出",
            ],
            "keyStructures": [
                "一体式工业机架",
                "连续水平输送通道",
                "检测工位独立遮光防护",
            ],
            "annotations": ["设备外观为结构示意", "所有尺寸与部件品牌待工程确认"],
            "prohibitedElements": [
                "未确认的机械臂与旋转机构",
                "科幻光效与悬浮结构",
            ],
            "referenceImages": [],
        }
    )


__all__ = [
    "CANVAS_HEIGHT",
    "CANVAS_WIDTH",
    "LAB_SCHEMA_VERSION",
    "FlowConnection",
    "LayoutPlan",
    "LayoutStation",
    "PromptRecipe",
    "SchemeVisualLabResult",
    "SchemeVisualLabService",
    "demo_drawing_specification",
]
