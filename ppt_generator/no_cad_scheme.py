"""No-CAD equipment logic scheme domain and deterministic renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from html import escape
import json
from typing import Any, Mapping, Sequence


SCENE_SCHEMA_VERSION = "no-cad-equipment-scene-v2"
CANVAS_WIDTH = 1600
CANVAS_HEIGHT = 900
MIN_MODULES = 2
MAX_MODULES = 12
ISSUE_LEVELS = {"blocking", "warning", "info"}

CATEGORY_NAMES = {
    "feed": "上料",
    "convey": "输送",
    "position": "定位",
    "inspect": "检测",
    "reject": "分选",
    "unload": "下料",
}

CATEGORY_COLORS = {
    "feed": "#59636D",
    "convey": "#486879",
    "position": "#6E6250",
    "inspect": "#A92328",
    "reject": "#8B562A",
    "unload": "#4E6C57",
}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


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
class ModuleDefinition:
    module_type: str
    name: str
    category: str
    description: str
    integrated_components: tuple[str, ...]
    color: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "moduleType": self.module_type,
            "name": self.name,
            "category": self.category,
            "categoryName": CATEGORY_NAMES[self.category],
            "description": self.description,
            "integratedComponents": list(self.integrated_components),
            "color": self.color,
        }


def _definition(
    module_type: str,
    name: str,
    category: str,
    description: str,
    *components: str,
) -> ModuleDefinition:
    return ModuleDefinition(
        module_type=module_type,
        name=name,
        category=category,
        description=description,
        integrated_components=tuple(components),
        color=CATEGORY_COLORS[category],
    )


MODULE_CATALOG: tuple[ModuleDefinition, ...] = (
    _definition("manual_feed", "人工上料", "feed", "人工把产品放入设备入口", "上料台", "安全入口"),
    _definition("vibratory_bowl_feed", "振动盘上料", "feed", "散料定向并连续输出", "振动盘", "直振接口"),
    _definition("tray_feed", "料盘上料", "feed", "托盘或吸塑盘供料", "料盘定位", "取料区"),
    _definition("belt_feed", "皮带线上料", "feed", "与客户前段皮带线对接", "入口皮带", "导向"),
    _definition("belt_transfer", "皮带输送", "convey", "沿水平主线连续输送", "输送带", "导向机构"),
    _definition("linear_feeder", "直线送料", "convey", "承接振动盘并稳定送料", "直振", "缓存通道"),
    _definition("stop_position", "阻挡定位", "position", "产品停止并建立检测基准", "阻挡气缸", "定位治具"),
    _definition("rotary_position", "旋转定位", "position", "产品定位后按要求旋转", "旋转治具", "定位传感器"),
    _definition("top_vision", "顶部视觉检测", "inspect", "从上方检测产品表面", "顶部相机", "镜头", "检测光源", "遮光结构"),
    _definition("side_vision", "侧面视觉检测", "inspect", "从侧面检测产品特征", "侧面相机", "镜头", "侧向光源", "安装支架"),
    _definition("bottom_vision", "底部视觉检测", "inspect", "通过透明承载或间隙检测底面", "底部相机", "镜头", "背光/底部光源"),
    _definition("multi_view_vision", "多视角检测", "inspect", "同一工位组合多个观察方向", "多相机组", "组合光源", "遮光防护"),
    _definition("air_reject", "气吹分选", "reject", "对轻小产品进行快速气吹剔除", "气嘴", "电磁阀", "NG通道"),
    _definition("pusher_reject", "气缸推料分选", "reject", "将NG产品推入独立通道", "推料气缸", "分流挡板", "NG通道"),
    _definition("ok_ng_bins", "OK/NG收料", "unload", "分别收集合格品和不合格品", "OK料盒", "NG料盒", "出料导向"),
    _definition("belt_unload", "皮带线下料", "unload", "与客户后段皮带线对接", "出口皮带", "出料传感器"),
)

MODULE_BY_TYPE = {value.module_type: value for value in MODULE_CATALOG}

STRUCTURE_LIST_FIELDS = (
    "components",
    "mechanismRelations",
    "motionRelations",
    "visualComponents",
    "safetyConstraints",
    "prohibitedElements",
)


def default_module_structure(module_type: str) -> dict[str, Any]:
    """Return the editable structured baseline for one standard module."""
    definition = MODULE_BY_TYPE.get(module_type)
    components = list(definition.integrated_components) if definition else []
    visual_components = [
        value
        for value in components
        if any(token in value for token in ("相机", "镜头", "光源", "背光"))
    ]
    return {
        "components": components,
        "productPath": "产品沿设备主线从左向右通过本模块",
        "mechanismRelations": [],
        "motionRelations": [],
        "visualComponents": visual_components,
        "safetyConstraints": [],
        "prohibitedElements": [],
        "customNotes": "",
    }


def normalize_module_structure(
    raw: Mapping[str, Any] | None,
    module_type: str,
) -> dict[str, Any]:
    """Validate a user-editable structure object and fill stable fields."""
    if raw is None:
        return default_module_structure(module_type)
    if not isinstance(raw, Mapping):
        raise ValueError("模块自定义结构必须是 JSON 对象")
    baseline = default_module_structure(module_type)
    result: dict[str, Any] = {}
    for key in STRUCTURE_LIST_FIELDS:
        value = raw.get(key, baseline[key])
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise ValueError(f"模块结构 {key} 必须是字符串数组")
        result[key] = [_text(item) for item in value if _text(item)]
    for key in ("productPath", "customNotes"):
        value = raw.get(key, baseline[key])
        if value is not None and not isinstance(value, str):
            raise ValueError(f"模块结构 {key} 必须是文字")
        result[key] = _text(value)
    return result


@dataclass
class SceneNode:
    node_id: str
    module_type: str
    name: str
    station_id: str
    description: str
    x: int = 0
    y: int = 330
    width: int = 160
    height: int = 270
    locked: bool = False
    reference_image: str = ""
    structure: dict[str, Any] = field(default_factory=dict)
    prompt_requirements: str = ""
    image_path: str = ""
    image_provenance: dict[str, Any] = field(default_factory=dict)

    def to_generation_dict(self) -> dict[str, Any]:
        """Return only data that authoritatively controls image generation."""
        return {
            "nodeId": self.node_id,
            "moduleType": self.module_type,
            "name": self.name,
            "stationId": self.station_id,
            "description": self.description,
            "bounds": {
                "x": self.x,
                "y": self.y,
                "width": self.width,
                "height": self.height,
            },
            "locked": self.locked,
            "referenceImage": self.reference_image,
            "structure": normalize_module_structure(
                self.structure or None,
                self.module_type,
            ),
            "promptRequirements": self.prompt_requirements,
        }

    def to_dict(self) -> dict[str, Any]:
        result = self.to_generation_dict()
        result["imagePath"] = self.image_path
        result["imageProvenance"] = dict(self.image_provenance)
        return result

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SceneNode":
        bounds = raw.get("bounds") or {}
        provenance = raw.get("imageProvenance") or {}
        if not isinstance(bounds, Mapping):
            raise ValueError("模块 bounds 必须是对象")
        if not isinstance(provenance, Mapping):
            raise ValueError("模块 imageProvenance 必须是对象")
        module_type = _text(raw.get("moduleType"))
        return cls(
            node_id=_text(raw.get("nodeId")),
            module_type=module_type,
            name=_text(raw.get("name")),
            station_id=_text(raw.get("stationId")),
            description=_text(raw.get("description")),
            x=int(bounds.get("x") or 0),
            y=int(bounds.get("y") or 330),
            width=int(bounds.get("width") or 160),
            height=int(bounds.get("height") or 270),
            locked=bool(raw.get("locked", False)),
            reference_image=_text(raw.get("referenceImage")),
            structure=normalize_module_structure(
                raw.get("structure"),
                module_type,
            ),
            prompt_requirements=_text(raw.get("promptRequirements")),
            image_path=_text(raw.get("imagePath")),
            image_provenance=dict(provenance),
        )


@dataclass(frozen=True)
class FlowLink:
    source_id: str
    target_id: str
    relation: str = "product_flow"

    def to_dict(self) -> dict[str, str]:
        return {
            "sourceId": self.source_id,
            "targetId": self.target_id,
            "relation": self.relation,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "FlowLink":
        return cls(
            source_id=_text(raw.get("sourceId")),
            target_id=_text(raw.get("targetId")),
            relation=_text(raw.get("relation")) or "product_flow",
        )


@dataclass
class EquipmentScene:
    project_name: str
    product_name: str
    nodes: list[SceneNode] = field(default_factory=list)
    connections: list[FlowLink] = field(default_factory=list)
    overview_structure: dict[str, Any] = field(default_factory=dict)
    overview_prompt_requirements: str = ""
    overview_image: str = ""
    overview_image_provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCENE_SCHEMA_VERSION

    def to_generation_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "projectName": self.project_name,
            "productName": self.product_name,
            "flowDirection": "left_to_right",
            "overviewStructure": dict(self.overview_structure),
            "overviewPromptRequirements": self.overview_prompt_requirements,
            "nodes": [value.to_generation_dict() for value in self.nodes],
            "connections": [value.to_dict() for value in self.connections],
        }

    def to_dict(self) -> dict[str, Any]:
        result = self.to_generation_dict()
        result["nodes"] = [value.to_dict() for value in self.nodes]
        result["overviewImage"] = self.overview_image
        result["overviewImageProvenance"] = dict(
            self.overview_image_provenance
        )
        return result

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "EquipmentScene":
        overview_structure = raw.get("overviewStructure") or {}
        overview_provenance = raw.get("overviewImageProvenance") or {}
        if not isinstance(overview_structure, Mapping):
            raise ValueError("整机 overviewStructure 必须是对象")
        if not isinstance(overview_provenance, Mapping):
            raise ValueError("整机 overviewImageProvenance 必须是对象")
        return cls(
            schema_version=SCENE_SCHEMA_VERSION,
            project_name=_text(raw.get("projectName")),
            product_name=_text(raw.get("productName")),
            nodes=[
                SceneNode.from_dict(value)
                for value in raw.get("nodes", [])
                if isinstance(value, Mapping)
            ],
            connections=[
                FlowLink.from_dict(value)
                for value in raw.get("connections", [])
                if isinstance(value, Mapping)
            ],
            overview_structure=dict(overview_structure),
            overview_prompt_requirements=_text(
                raw.get("overviewPromptRequirements")
            ),
            overview_image=_text(raw.get("overviewImage")),
            overview_image_provenance=dict(overview_provenance),
        )


@dataclass(frozen=True)
class LogicIssue:
    level: str
    code: str
    message: str
    node_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.level not in ISSUE_LEVELS:
            raise ValueError(f"未知问题级别：{self.level}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "nodeIds": list(self.node_ids),
        }


@dataclass(frozen=True)
class VisualGenerationTarget:
    target_id: str
    target_kind: str
    title: str
    target_hash: str
    structure: Mapping[str, Any]
    prompt: str
    control_svg: str
    image_path: str = ""
    image_provenance: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_control_svg: bool = False) -> dict[str, Any]:
        result = {
            "targetId": self.target_id,
            "targetKind": self.target_kind,
            "title": self.title,
            "targetHash": self.target_hash,
            "structure": dict(self.structure),
            "prompt": self.prompt,
            "imagePath": self.image_path,
            "imageProvenance": dict(self.image_provenance),
        }
        if include_control_svg:
            result["controlSvg"] = self.control_svg
        return result


@dataclass(frozen=True)
class NoCadSchemeResult:
    scene_hash: str
    issues: tuple[LogicIssue, ...]
    can_generate_ai: bool
    svg: str
    generation_brief: str
    visual_targets: tuple[VisualGenerationTarget, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "sceneHash": self.scene_hash,
            "canGenerateAi": self.can_generate_ai,
            "issues": [value.to_dict() for value in self.issues],
            "generationBrief": self.generation_brief,
            "visualTargets": [value.to_dict() for value in self.visual_targets],
        }

    def visual_target(self, target_id: str) -> VisualGenerationTarget:
        for target in self.visual_targets:
            if target.target_id == target_id:
                return target
        raise ValueError(f"当前方案不存在视觉生成目标：{target_id}")


class NoCadSchemeService:
    """Own no-CAD scene operations and conservative single-line checks."""

    @property
    def module_catalog(self) -> tuple[ModuleDefinition, ...]:
        return MODULE_CATALOG

    def create_demo_scene(self) -> EquipmentScene:
        scene = EquipmentScene(
            project_name="筒形壳体无CAD检测方案",
            product_name="筒形壳体",
        )
        for module_type in (
            "vibratory_bowl_feed",
            "linear_feeder",
            "stop_position",
            "top_vision",
            "side_vision",
            "pusher_reject",
            "ok_ng_bins",
        ):
            self.add_module(scene, module_type)
        self.auto_layout(scene)
        return scene

    def create_minimum_scene(self) -> EquipmentScene:
        scene = EquipmentScene(
            project_name="未命名无CAD设备方案",
            product_name="待确认产品",
        )
        for module_type in ("manual_feed", "top_vision", "ok_ng_bins"):
            self.add_module(scene, module_type)
        self.auto_layout(scene)
        return scene

    def add_module(
        self,
        scene: EquipmentScene,
        module_type: str,
        index: int | None = None,
    ) -> SceneNode:
        definition = self._get_definition(module_type)
        node_number = self._next_node_number(scene)
        station_number = 1 + sum(
            1
            for node in scene.nodes
            if MODULE_BY_TYPE.get(node.module_type, definition).category
            not in {"feed", "unload"}
        )
        station_id = {
            "feed": "IN",
            "unload": "OUT",
        }.get(definition.category, f"ST{station_number:02d}")
        node = SceneNode(
            node_id=f"M{node_number:02d}",
            module_type=definition.module_type,
            name=definition.name,
            station_id=station_id,
            description=definition.description,
            structure=default_module_structure(definition.module_type),
        )
        if index is None:
            scene.nodes.append(node)
        else:
            scene.nodes.insert(max(0, min(index, len(scene.nodes))), node)
        self.rebuild_connections(scene)
        return node

    def replace_module(
        self,
        scene: EquipmentScene,
        node_id: str,
        module_type: str,
    ) -> SceneNode:
        definition = self._get_definition(module_type)
        node = self._get_node(scene, node_id)
        self._ensure_unlocked(node, "替换")
        node.module_type = definition.module_type
        node.name = definition.name
        node.description = definition.description
        node.structure = default_module_structure(definition.module_type)
        node.prompt_requirements = ""
        node.image_path = ""
        node.image_provenance = {}
        if definition.category == "feed":
            node.station_id = "IN"
        elif definition.category == "unload":
            node.station_id = "OUT"
        elif node.station_id in {"IN", "OUT", ""}:
            node.station_id = self._next_station_id(scene, exclude=node.node_id)
        self.rebuild_connections(scene)
        return node

    def remove_module(self, scene: EquipmentScene, node_id: str) -> None:
        node = self._get_node(scene, node_id)
        self._ensure_unlocked(node, "删除")
        before = len(scene.nodes)
        scene.nodes[:] = [value for value in scene.nodes if value.node_id != node_id]
        if len(scene.nodes) == before:
            raise ValueError(f"未找到模块节点：{node_id}")
        self.rebuild_connections(scene)

    def move_module(self, scene: EquipmentScene, node_id: str, offset: int) -> int:
        if not offset:
            return next(index for index, value in enumerate(scene.nodes) if value.node_id == node_id)
        current = next(
            (index for index, value in enumerate(scene.nodes) if value.node_id == node_id),
            None,
        )
        if current is None:
            raise ValueError(f"未找到模块节点：{node_id}")
        self._ensure_unlocked(scene.nodes[current], "移动")
        target = max(0, min(len(scene.nodes) - 1, current + offset))
        node = scene.nodes.pop(current)
        scene.nodes.insert(target, node)
        self.rebuild_connections(scene)
        return target

    def reorder_modules(self, scene: EquipmentScene, node_ids: Sequence[str]) -> None:
        if len(node_ids) != len(scene.nodes) or set(node_ids) != {
            value.node_id for value in scene.nodes
        }:
            raise ValueError("拖动排序必须包含当前全部模块且不得重复")
        old_positions = {value.node_id: index for index, value in enumerate(scene.nodes)}
        new_positions = {value: index for index, value in enumerate(node_ids)}
        moved_locked = [
            value.node_id
            for value in scene.nodes
            if value.locked and old_positions[value.node_id] != new_positions[value.node_id]
        ]
        if moved_locked:
            raise ValueError("已锁定模块不能调整顺序：" + "、".join(moved_locked))
        by_id = {value.node_id: value for value in scene.nodes}
        scene.nodes[:] = [by_id[value] for value in node_ids]
        self.rebuild_connections(scene)

    @staticmethod
    def rebuild_connections(scene: EquipmentScene) -> None:
        scene.connections[:] = [
            FlowLink(scene.nodes[index].node_id, scene.nodes[index + 1].node_id)
            for index in range(max(0, len(scene.nodes) - 1))
        ]

    def auto_layout(self, scene: EquipmentScene) -> None:
        count = len(scene.nodes)
        if not count:
            return
        start_x = 140
        available_width = 1320
        gap = 32 if count <= 8 else 22
        width = min(176, max(82, (available_width - gap * (count - 1)) // count))
        occupied = width * count + gap * (count - 1)
        start_x = (CANVAS_WIDTH - occupied) // 2
        for index, node in enumerate(scene.nodes):
            if node.locked:
                continue
            node.x = start_x + index * (width + gap)
            node.y = 330
            node.width = width
            node.height = 270
        self.rebuild_connections(scene)

    def evaluate(self, scene: EquipmentScene) -> NoCadSchemeResult:
        issues = tuple(self.validate(scene))
        scene_hash = _stable_hash(scene.to_generation_dict())
        can_generate_ai = not any(value.level == "blocking" for value in issues)
        brief = self.build_generation_brief(scene, scene_hash, can_generate_ai)
        svg = self.render_svg(scene, issues, scene_hash)
        visual_targets = self.build_visual_targets(
            scene,
            scene_hash,
            brief,
            svg,
        )
        return NoCadSchemeResult(
            scene_hash=scene_hash,
            issues=issues,
            can_generate_ai=can_generate_ai,
            svg=svg,
            generation_brief=brief,
            visual_targets=visual_targets,
        )

    def build_visual_targets(
        self,
        scene: EquipmentScene,
        scene_hash: str,
        generation_brief: str,
        overview_svg: str,
    ) -> tuple[VisualGenerationTarget, ...]:
        """Build one overview target plus one independently hashed target per node."""
        overview_structure = {
            "flowDirection": "left_to_right",
            "moduleOrder": [value.node_id for value in scene.nodes],
            "moduleStructures": {
                value.node_id: normalize_module_structure(
                    value.structure or None,
                    value.module_type,
                )
                for value in scene.nodes
            },
            "custom": dict(scene.overview_structure),
        }
        targets: list[VisualGenerationTarget] = [
            VisualGenerationTarget(
                target_id="overview",
                target_kind="overview",
                title="整机设备总览",
                target_hash=scene_hash,
                structure=overview_structure,
                prompt=self._build_overview_prompt(scene, generation_brief),
                control_svg=overview_svg,
                image_path=scene.overview_image,
                image_provenance=scene.overview_image_provenance,
            )
        ]
        for index, node in enumerate(scene.nodes):
            previous_node = scene.nodes[index - 1] if index else None
            next_node = scene.nodes[index + 1] if index + 1 < len(scene.nodes) else None
            structure = normalize_module_structure(
                node.structure or None,
                node.module_type,
            )
            target_payload = {
                "targetKind": "module",
                "projectName": scene.project_name,
                "productName": scene.product_name,
                "node": node.to_generation_dict(),
                "upstreamNodeId": previous_node.node_id if previous_node else "",
                "downstreamNodeId": next_node.node_id if next_node else "",
            }
            target_hash = _stable_hash(target_payload)
            targets.append(
                VisualGenerationTarget(
                    target_id=node.node_id,
                    target_kind="module",
                    title=f"{node.station_id or node.node_id} · {node.name}",
                    target_hash=target_hash,
                    structure=structure,
                    prompt=self._build_module_prompt(
                        scene,
                        node,
                        previous_node,
                        next_node,
                        structure,
                    ),
                    control_svg=self.render_module_svg(
                        scene,
                        node,
                        previous_node,
                        next_node,
                        structure,
                        target_hash,
                    ),
                    image_path=node.image_path,
                    image_provenance=node.image_provenance,
                )
            )
        return tuple(targets)

    @staticmethod
    def _build_overview_prompt(
        scene: EquipmentScene,
        generation_brief: str,
    ) -> str:
        extra = scene.overview_prompt_requirements.strip()
        return (
            "Create one industrial automation equipment concept rendering for a technical proposal.\n"
            "Use the attached structure control image as an immutable engineering logic reference.\n"
            "Preserve exactly the module count, left-to-right order, product flow, inspection sequence and reject sequence.\n"
            "Show one coherent practical machine with a steel/aluminum frame, appropriate guarding and only the registered mechanisms.\n"
            "Use a restrained white and dark-gray industrial design with small red accents on a clean light-gray background.\n"
            "Use an elevated three-quarter view, keep the complete machine visible, and leave generous margins.\n"
            "Do not add labels, logos, dimensions, people, workshop clutter or unregistered equipment.\n"
            "This is a concept image for human engineering review, not CAD or a manufacturing drawing.\n\n"
            "Authoritative scene constraints:\n"
            + generation_brief.strip()
            + ("\n\nUser-confirmed additional requirements:\n" + extra if extra else "")
        )

    @staticmethod
    def _build_module_prompt(
        scene: EquipmentScene,
        node: SceneNode,
        previous_node: SceneNode | None,
        next_node: SceneNode | None,
        structure: Mapping[str, Any],
    ) -> str:
        upstream = previous_node.name if previous_node else "设备入口"
        downstream = next_node.name if next_node else "设备出口"
        structure_json = _canonical_json(structure)
        extra = node.prompt_requirements.strip()
        return (
            "Create one isolated industrial automation functional-module concept rendering for a technical proposal.\n"
            f"Module identity: {node.node_id}/{node.station_id or 'unassigned'} {node.name}.\n"
            f"Product: {scene.product_name or 'to be confirmed'}. Function: {node.description or 'to be confirmed'}.\n"
            f"Interface context: upstream is {upstream}; downstream is {downstream}; product travels left to right.\n"
            "Show only this functional module and the short mechanical interfaces required to explain its connection.\n"
            "Preserve every registered component and relation; do not invent extra cameras, lights, robots, turntables, branches or conveyors.\n"
            "Use a practical steel/aluminum industrial construction, clean light-gray background, elevated three-quarter engineering view and generous margins.\n"
            "No text, labels, logos, dimensions, people or workshop clutter. This is a concept image, not CAD or a manufacturing drawing.\n"
            f"Authoritative module structure JSON: {structure_json}"
            + ("\nUser-confirmed additional requirements: " + extra if extra else "")
        )

    @staticmethod
    def bind_accepted_image(
        scene: EquipmentScene,
        target_id: str,
        image_path: str,
        provenance: Mapping[str, Any],
    ) -> None:
        """Bind a human-accepted image to exactly one Scene-owned target."""
        path = _text(image_path)
        if not path:
            raise ValueError("采用图片路径不能为空")
        target = NoCadSchemeService().evaluate(scene).visual_target(target_id)
        if _text(provenance.get("targetHash")) != target.target_hash:
            raise ValueError("采用图片的目标哈希与当前结构不一致")
        if target_id == "overview":
            scene.overview_image = path
            scene.overview_image_provenance = dict(provenance)
            return
        node = NoCadSchemeService._get_node(scene, target_id)
        node.image_path = path
        node.image_provenance = dict(provenance)

    @staticmethod
    def stale_image_target_ids(
        scene: EquipmentScene,
        result: NoCadSchemeResult,
    ) -> tuple[str, ...]:
        """Return accepted-image targets whose recorded hash is no longer current."""
        current_hashes = {
            target.target_id: target.target_hash
            for target in result.visual_targets
        }
        stale: list[str] = []
        if scene.overview_image and _text(
            scene.overview_image_provenance.get("targetHash")
        ) != current_hashes.get("overview"):
            stale.append("overview")
        for node in scene.nodes:
            if node.image_path and _text(
                node.image_provenance.get("targetHash")
            ) != current_hashes.get(node.node_id):
                stale.append(node.node_id)
        return tuple(stale)

    @staticmethod
    def invalidate_stale_images(
        scene: EquipmentScene,
        result: NoCadSchemeResult,
    ) -> tuple[str, ...]:
        """Clear only image bindings invalidated by the current target hashes."""
        stale = NoCadSchemeService.stale_image_target_ids(scene, result)
        for target_id in stale:
            if target_id == "overview":
                scene.overview_image = ""
                scene.overview_image_provenance = {}
                continue
            node = NoCadSchemeService._get_node(scene, target_id)
            node.image_path = ""
            node.image_provenance = {}
        return stale

    def validate(self, scene: EquipmentScene) -> list[LogicIssue]:
        issues: list[LogicIssue] = []
        count = len(scene.nodes)
        if count < MIN_MODULES or count > MAX_MODULES:
            issues.append(
                LogicIssue(
                    "blocking",
                    "MODULE_COUNT",
                    f"单主线必须包含 {MIN_MODULES}～{MAX_MODULES} 个模块，当前为 {count} 个",
                )
            )
        if not scene.product_name:
            issues.append(LogicIssue("warning", "PRODUCT_EMPTY", "产品名称尚未填写"))
        node_ids = [value.node_id for value in scene.nodes]
        duplicates = sorted({value for value in node_ids if node_ids.count(value) > 1})
        if duplicates:
            issues.append(
                LogicIssue(
                    "blocking",
                    "DUPLICATE_NODE_ID",
                    "模块节点ID重复：" + "、".join(duplicates),
                    tuple(duplicates),
                )
            )
        unknown = [value.node_id for value in scene.nodes if value.module_type not in MODULE_BY_TYPE]
        if unknown:
            issues.append(
                LogicIssue(
                    "blocking",
                    "UNKNOWN_MODULE_TYPE",
                    "存在未登记的模块类型",
                    tuple(unknown),
                )
            )
        invalid_size = [
            value.node_id
            for value in scene.nodes
            if value.width <= 0 or value.height <= 0
        ]
        if invalid_size:
            issues.append(
                LogicIssue(
                    "blocking",
                    "INVALID_SIZE",
                    "模块宽度和高度必须大于0",
                    tuple(invalid_size),
                )
            )

        known_nodes = [value for value in scene.nodes if value.module_type in MODULE_BY_TYPE]
        categories = [MODULE_BY_TYPE[value.module_type].category for value in known_nodes]
        if known_nodes:
            if categories[0] != "feed":
                issues.append(
                    LogicIssue(
                        "blocking",
                        "ENTRY_NOT_FEED",
                        "第一模块必须是上料模块",
                        (known_nodes[0].node_id,),
                    )
                )
            if categories[-1] != "unload":
                issues.append(
                    LogicIssue(
                        "blocking",
                        "EXIT_NOT_UNLOAD",
                        "最后模块必须是下料模块",
                        (known_nodes[-1].node_id,),
                    )
                )
            feed_nodes = [node.node_id for node, category in zip(known_nodes, categories) if category == "feed"]
            if len(feed_nodes) != 1 or categories[0] != "feed":
                issues.append(
                    LogicIssue(
                        "blocking",
                        "FEED_POSITION",
                        "单主线只能有一个上料模块，且必须位于第一位",
                        tuple(feed_nodes),
                    )
                )
            unload_nodes = [node.node_id for node, category in zip(known_nodes, categories) if category == "unload"]
            if len(unload_nodes) != 1 or categories[-1] != "unload":
                issues.append(
                    LogicIssue(
                        "blocking",
                        "UNLOAD_POSITION",
                        "单主线只能有一个下料模块，且必须位于最后一位",
                        tuple(unload_nodes),
                    )
                )
            inspect_indices = [index for index, category in enumerate(categories) if category == "inspect"]
            reject_indices = [index for index, category in enumerate(categories) if category == "reject"]
            if not inspect_indices:
                issues.append(LogicIssue("blocking", "NO_INSPECTION", "设备方案至少需要一个检测模块"))
            else:
                first_inspect = inspect_indices[0]
                last_inspect = inspect_indices[-1]
                before = categories[:first_inspect]
                if "position" not in before:
                    issues.append(
                        LogicIssue(
                            "warning",
                            "NO_POSITION_BEFORE_INSPECTION",
                            "检测前没有明确定位模块；连续输送检测可人工确认后保留",
                            (known_nodes[first_inspect].node_id,),
                        )
                    )
                if not reject_indices:
                    issues.append(
                        LogicIssue(
                            "warning",
                            "NO_REJECT_AFTER_INSPECTION",
                            "检测后没有明确分选模块；如由后段设备处理可人工确认",
                        )
                    )
                elif min(reject_indices) < first_inspect:
                    issues.append(
                        LogicIssue(
                            "blocking",
                            "REJECT_BEFORE_INSPECTION",
                            "分选模块不能位于全部检测之前",
                            (known_nodes[min(reject_indices)].node_id,),
                        )
                    )
                if any(index > min(reject_indices) for index in inspect_indices) if reject_indices else False:
                    offending = tuple(
                        known_nodes[index].node_id
                        for index in inspect_indices
                        if index > min(reject_indices)
                    )
                    issues.append(
                        LogicIssue(
                            "blocking",
                            "INSPECTION_AFTER_REJECT",
                            "分选后不能再次进入检测模块",
                            offending,
                        )
                    )
                if known_nodes[0].module_type == "vibratory_bowl_feed" and first_inspect == 1:
                    issues.append(
                        LogicIssue(
                            "warning",
                            "BOWL_DIRECT_TO_INSPECTION",
                            "振动盘后直接检测，建议增加直线送料或定位模块",
                            (known_nodes[0].node_id, known_nodes[first_inspect].node_id),
                        )
                    )

        expected_links = [
            (scene.nodes[index].node_id, scene.nodes[index + 1].node_id, "product_flow")
            for index in range(max(0, count - 1))
        ]
        actual_links = [
            (value.source_id, value.target_id, value.relation)
            for value in scene.connections
        ]
        if actual_links != expected_links:
            issues.append(
                LogicIssue(
                    "blocking",
                    "FLOW_BROKEN",
                    "产品主线连接必须严格连接相邻模块，当前连接已断裂或顺序不一致",
                )
            )

        direction_nodes: list[str] = []
        overlaps: list[str] = []
        for previous, current in zip(scene.nodes, scene.nodes[1:]):
            if current.x <= previous.x:
                direction_nodes.extend((previous.node_id, current.node_id))
            elif current.x < previous.x + previous.width:
                overlaps.extend((previous.node_id, current.node_id))
        if direction_nodes:
            issues.append(
                LogicIssue(
                    "blocking",
                    "FLOW_DIRECTION",
                    "产品主线坐标必须从左到右递增；请自动排布或解除冲突锁定",
                    tuple(dict.fromkeys(direction_nodes)),
                )
            )
        if overlaps:
            issues.append(
                LogicIssue(
                    "warning",
                    "MODULE_OVERLAP",
                    "相邻模块在结构图上发生重叠",
                    tuple(dict.fromkeys(overlaps)),
                )
            )

        station_ids = [value.station_id for value in scene.nodes if value.station_id]
        empty_station = [value.node_id for value in scene.nodes if not value.station_id]
        duplicate_station = sorted(
            {value for value in station_ids if station_ids.count(value) > 1}
        )
        if empty_station:
            issues.append(
                LogicIssue(
                    "warning",
                    "EMPTY_STATION_ID",
                    "存在未填写工位编号的模块",
                    tuple(empty_station),
                )
            )
        if duplicate_station:
            affected = tuple(
                value.node_id for value in scene.nodes if value.station_id in duplicate_station
            )
            issues.append(
                LogicIssue(
                    "warning",
                    "DUPLICATE_STATION_ID",
                    "工位编号重复；同一工位的多模块可人工确认后保留",
                    affected,
                )
            )
        if not any(value.reference_image for value in scene.nodes):
            issues.append(
                LogicIssue(
                    "info",
                    "NO_REFERENCE_IMAGES",
                    "当前未配置模块参考图；后续AI效果只受逻辑结构控制",
                )
            )
        locked = tuple(value.node_id for value in scene.nodes if value.locked)
        if locked:
            issues.append(
                LogicIssue(
                    "info",
                    "LOCKED_NODES",
                    "自动排布会保留已锁定模块的位置",
                    locked,
                )
            )
        issues.append(
            LogicIssue(
                "info",
                "CONCEPT_ONLY",
                "当前结果是无CAD售前逻辑方案，仍需工程师确认后才能对外使用",
            )
        )
        return issues

    def build_generation_brief(
        self,
        scene: EquipmentScene,
        scene_hash: str,
        can_generate_ai: bool,
    ) -> str:
        lines = [
            "无CAD设备效果图生成约束",
            f"方案：{scene.project_name or '未命名方案'}",
            f"产品：{scene.product_name or '待确认产品'}",
            f"场景哈希：{scene_hash}",
            f"逻辑门禁：{'通过' if can_generate_ai else '未通过，禁止提交图片Provider'}",
            f"严格保留 {len(scene.nodes)} 个流程模块，入口在左、出口在右。",
            "模块顺序不得增加、删除、合并或交换：",
        ]
        for index, node in enumerate(scene.nodes, 1):
            definition = MODULE_BY_TYPE.get(node.module_type)
            structure = normalize_module_structure(
                node.structure or None,
                node.module_type,
            )
            components = "、".join(structure["components"]) or (
                "、".join(definition.integrated_components) if definition else "未知"
            )
            locked = "；结构已锁定" if node.locked else ""
            reference = f"；参考图={node.reference_image}" if node.reference_image else ""
            lines.append(
                f"{index}. {node.node_id}/{node.station_id} {node.name}｜内部部件：{components}{locked}{reference}"
            )
        lines.extend(
            [
                "只生成工业设备售前概念效果，不标注为CAD、施工图或最终机械设计。",
                "所有文字、工位编号、产品流向和参数由PPT软件后期叠加，不在图片中生成。",
                "不得出现Scene中未登记的机械臂、转盘、相机、光源、输送分支或悬浮机构。",
            ]
        )
        return "\n".join(lines)

    def render_module_svg(
        self,
        scene: EquipmentScene,
        node: SceneNode,
        previous_node: SceneNode | None,
        next_node: SceneNode | None,
        structure: Mapping[str, Any],
        target_hash: str,
    ) -> str:
        """Render a deterministic control board for one module target."""
        xml = lambda value: escape(_text(value), quote=True)
        definition = MODULE_BY_TYPE.get(node.module_type)
        color = definition.color if definition else "#A92328"
        components = list(structure.get("components") or [])
        relations = list(structure.get("mechanismRelations") or [])
        motions = list(structure.get("motionRelations") or [])
        upstream = previous_node.name if previous_node else "设备入口"
        downstream = next_node.name if next_node else "设备出口"
        component_text = "、".join(components) or "待人工定义"
        relation_text = "；".join(relations) or "待人工定义"
        motion_text = "；".join(motions) or "待人工定义"
        return "\n".join(
            [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">',
                '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#C62026"/></marker><filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="7" flood-color="#111827" flood-opacity="0.14"/></filter><style>text{font-family:\'Microsoft YaHei\',\'Noto Sans CJK SC\',sans-serif;fill:#20242A}.muted{fill:#6B747D}.white{fill:#FFFFFF}</style></defs>',
                '<rect width="1600" height="900" fill="#F3F5F6"/>',
                '<rect width="1600" height="96" fill="#20252B"/>',
                f'<text x="64" y="58" font-size="30" font-weight="700" class="white">{xml(node.station_id or node.node_id)} · {xml(node.name)}</text>',
                '<text x="1536" y="56" text-anchor="end" font-size="18" class="white">MODULE STRUCTURE CONTROL</text>',
                '<text x="800" y="180" text-anchor="middle" font-size="22" class="muted">产品主线：左进右出</text>',
                '<line x1="150" y1="430" x2="1450" y2="430" stroke="#C62026" stroke-width="6" marker-end="url(#arrow)"/>',
                f'<rect x="505" y="250" width="590" height="360" rx="4" fill="#FFFFFF" stroke="{color}" stroke-width="4" filter="url(#shadow)"/>',
                f'<rect x="505" y="250" width="590" height="78" fill="{color}"/>',
                f'<text x="800" y="300" text-anchor="middle" font-size="28" font-weight="700" class="white">{xml(node.name)}</text>',
                f'<text x="535" y="370" font-size="19" font-weight="700" fill="{color}">内部部件</text>',
                f'<text x="535" y="405" font-size="18">{xml(_short(component_text, 52))}</text>',
                '<text x="535" y="458" font-size="19" font-weight="700" fill="#4B5964">机构关系</text>',
                f'<text x="535" y="493" font-size="18">{xml(_short(relation_text, 52))}</text>',
                '<text x="535" y="546" font-size="19" font-weight="700" fill="#4B5964">运动关系</text>',
                f'<text x="535" y="581" font-size="18">{xml(_short(motion_text, 52))}</text>',
                f'<text x="150" y="396" font-size="19" class="muted">上游：{xml(upstream)}</text>',
                f'<text x="1450" y="396" text-anchor="end" font-size="19" class="muted">下游：{xml(downstream)}</text>',
                f'<text x="800" y="680" text-anchor="middle" font-size="20">{xml(structure.get("productPath") or "产品路径待确认")}</text>',
                f'<text x="64" y="838" font-size="16" class="muted">Target Hash：{xml(target_hash[:32])}…</text>',
                '<text x="1536" y="838" text-anchor="end" font-size="16" class="muted">模块结构控制图 · 非 CAD · 不代表制造尺寸</text>',
                '</svg>',
            ]
        )

    def render_svg(
        self,
        scene: EquipmentScene,
        issues: Sequence[LogicIssue],
        scene_hash: str,
    ) -> str:
        def xml(value: Any) -> str:
            return escape(_text(value), quote=True)

        blocking_nodes = {
            node_id
            for issue in issues
            if issue.level == "blocking"
            for node_id in issue.node_ids
        }
        blocking_count = sum(value.level == "blocking" for value in issues)
        warning_count = sum(value.level == "warning" for value in issues)
        status_color = "#A92328" if blocking_count else "#2F7346"
        status_text = (
            f"逻辑未通过 · {blocking_count}项阻断"
            if blocking_count
            else f"逻辑通过 · {warning_count}项待确认"
        )
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}">',
            "<defs>",
            '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#C62026"/></marker>',
            '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="6" flood-color="#111827" flood-opacity="0.13"/></filter>',
            "<style>",
            "text{font-family:'Microsoft YaHei','Noto Sans CJK SC',sans-serif;fill:#20242A}",
            ".white{fill:#FFFFFF}.muted{fill:#6B747D}.small{font-size:16px}.body{font-size:18px}.title{font-size:30px;font-weight:700}.module-name{font-size:21px;font-weight:700;fill:#FFFFFF}",
            "</style>",
            "</defs>",
            '<rect width="1600" height="900" fill="#F3F5F6"/>',
            '<rect width="1600" height="96" fill="#20252B"/>',
            f'<text x="64" y="58" class="white title">{xml(scene.project_name or "未命名无CAD设备方案")}</text>',
            '<text x="1536" y="55" text-anchor="end" class="white body">NO-CAD LOGIC SCHEME</text>',
            '<rect x="64" y="126" width="8" height="62" fill="#C62026"/>',
            f'<text x="92" y="153" font-size="23" font-weight="700">产品：{xml(scene.product_name or "待确认")}</text>',
            '<text x="92" y="184" class="muted small">单条产品主线 · 逻辑优先 · 外观仅作概念表达</text>',
            f'<rect x="1250" y="126" width="286" height="58" fill="{status_color}"/>',
            f'<text x="1393" y="162" text-anchor="middle" class="white body" font-weight="700">{xml(status_text)}</text>',
            '<line x1="64" y1="224" x2="1536" y2="224" stroke="#D1D7DC" stroke-width="2"/>',
            '<rect x="65" y="454" width="1470" height="72" fill="#DDE2E5" stroke="#A8B0B7" stroke-width="2"/>',
            '<line x1="86" y1="490" x2="1514" y2="490" stroke="#C62026" stroke-width="5" marker-end="url(#arrow)"/>',
            '<text x="86" y="443" class="muted small">设备入口 / 产品输入</text>',
            '<text x="1514" y="443" text-anchor="end" class="muted small">设备出口 / 产品输出</text>',
        ]
        for index, node in enumerate(scene.nodes, 1):
            definition = MODULE_BY_TYPE.get(node.module_type)
            category = definition.category if definition else "inspect"
            category_name = CATEGORY_NAMES.get(category, "未知")
            color = definition.color if definition else "#A92328"
            border = "#D10000" if node.node_id in blocking_nodes else "#87919A"
            border_width = 5 if node.node_id in blocking_nodes else 2
            structure = normalize_module_structure(
                node.structure or None,
                node.module_type,
            )
            component_text = "、".join(structure["components"]) or (
                "、".join(definition.integrated_components)
                if definition
                else "模块类型未登记"
            )
            title_limit = max(5, node.width // 19)
            body_limit = max(7, node.width // 16)
            lines.extend(
                [
                    f'<g data-node-id="{xml(node.node_id)}" data-module-type="{xml(node.module_type)}">',
                    f'<rect x="{node.x}" y="{node.y}" width="{node.width}" height="{node.height}" fill="#FFFFFF" stroke="{border}" stroke-width="{border_width}" filter="url(#shadow)"/>',
                    f'<rect x="{node.x}" y="{node.y}" width="{node.width}" height="70" fill="{color}"/>',
                    f'<text x="{node.x + 14}" y="{node.y + 26}" class="white small" font-weight="700">{index:02d} · {xml(node.station_id or "未编号")}</text>',
                    f'<text x="{node.x + 14}" y="{node.y + 55}" class="module-name">{xml(_short(node.name, title_limit))}</text>',
                    f'<text x="{node.x + 14}" y="{node.y + 103}" class="small" font-weight="700" fill="{color}">{xml(category_name)}模块</text>',
                    f'<text x="{node.x + 14}" y="{node.y + 137}" class="small">{xml(_short(node.description, body_limit))}</text>',
                    f'<line x1="{node.x + 14}" y1="{node.y + 157}" x2="{node.x + node.width - 14}" y2="{node.y + 157}" stroke="#D9DEE2"/>',
                    f'<text x="{node.x + 14}" y="{node.y + 185}" class="muted small">内部结构</text>',
                    f'<text x="{node.x + 14}" y="{node.y + 214}" class="small">{xml(_short(component_text, body_limit))}</text>',
                    f'<text x="{node.x + 14}" y="{node.y + node.height - 18}" class="small" fill="{color}">{"已锁定" if node.locked else "可调整"}{" · 有参考图" if node.reference_image else ""}</text>',
                    "</g>",
                ]
            )
        lines.extend(
            [
                '<rect x="64" y="656" width="1472" height="148" fill="#FFFFFF" stroke="#D2D8DD" stroke-width="2"/>',
                '<text x="88" y="696" font-size="20" font-weight="700" fill="#A92328">逻辑审核基线</text>',
                f'<text x="88" y="734" class="body">主线：{xml(" → ".join(node.name for node in scene.nodes) or "尚未配置")}</text>',
                f'<text x="88" y="770" class="muted small">Scene Hash：{xml(scene_hash[:28])}…</text>',
                '<text x="1512" y="770" text-anchor="end" class="muted small">无CAD售前逻辑方案 · 非制造图 · 工程师确认后使用</text>',
                '<text x="64" y="858" class="muted small">KY Project · modules and product flow are authoritative; visual appearance is illustrative</text>',
                "</svg>",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _get_definition(module_type: str) -> ModuleDefinition:
        try:
            return MODULE_BY_TYPE[module_type]
        except KeyError as exc:
            raise ValueError(f"未知标准模块类型：{module_type}") from exc

    @staticmethod
    def _get_node(scene: EquipmentScene, node_id: str) -> SceneNode:
        for node in scene.nodes:
            if node.node_id == node_id:
                return node
        raise ValueError(f"未找到模块节点：{node_id}")

    @staticmethod
    def _next_node_number(scene: EquipmentScene) -> int:
        used = {
            int(value.node_id[1:])
            for value in scene.nodes
            if value.node_id.startswith("M") and value.node_id[1:].isdigit()
        }
        candidate = 1
        while candidate in used:
            candidate += 1
        return candidate

    @staticmethod
    def _next_station_id(scene: EquipmentScene, exclude: str = "") -> str:
        used = {value.station_id for value in scene.nodes if value.node_id != exclude}
        candidate = 1
        while f"ST{candidate:02d}" in used:
            candidate += 1
        return f"ST{candidate:02d}"

    @staticmethod
    def _ensure_unlocked(node: SceneNode, action: str) -> None:
        if node.locked:
            raise ValueError(f"模块 {node.node_id} 已锁定，解除锁定后才能{action}")


def demo_equipment_scene() -> EquipmentScene:
    return NoCadSchemeService().create_demo_scene()


__all__ = [
    "CANVAS_HEIGHT",
    "CANVAS_WIDTH",
    "CATEGORY_NAMES",
    "EquipmentScene",
    "FlowLink",
    "LogicIssue",
    "MAX_MODULES",
    "MIN_MODULES",
    "MODULE_BY_TYPE",
    "MODULE_CATALOG",
    "ModuleDefinition",
    "NoCadSchemeResult",
    "NoCadSchemeService",
    "SCENE_SCHEMA_VERSION",
    "SceneNode",
    "VisualGenerationTarget",
    "default_module_structure",
    "demo_equipment_scene",
    "normalize_module_structure",
]
