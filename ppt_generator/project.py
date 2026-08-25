"""UI-independent project state for the desktop PPT workflow."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .excel_mapper import ExcelMappingRule


PROJECT_SCHEMA_VERSION = 5
SUPPORTED_PROJECT_SCHEMA_VERSIONS = {1, 2, 3, 4, PROJECT_SCHEMA_VERSION}


@dataclass
class NavigationItem:
    """One project-level navigation section and its template modules."""

    name: str
    module_keys: list[str] = field(default_factory=list)

    def validate(self) -> None:
        name = self.name.strip()
        if not name:
            raise ValueError("导航栏目名称不能为空")
        if len(name) > 10:
            raise ValueError("导航栏目名称不能超过 10 个字符")
        if len(set(self.module_keys)) != len(self.module_keys):
            raise ValueError(f"导航栏目“{name}”包含重复模块")
        if any(not str(key).strip() for key in self.module_keys):
            raise ValueError(f"导航栏目“{name}”包含空模块 key")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "name": self.name.strip(),
            "module_keys": [str(key).strip() for key in self.module_keys],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "NavigationItem":
        if not isinstance(raw, Mapping):
            raise ValueError("导航栏目必须是对象")
        module_keys = raw.get("module_keys", [])
        if not isinstance(module_keys, list):
            raise ValueError("导航栏目 module_keys 必须是数组")
        item = cls(
            name=str(raw.get("name") or "").strip(),
            module_keys=[str(key).strip() for key in module_keys],
        )
        item.validate()
        return item


def default_navigation_items() -> list[NavigationItem]:
    """Return the approved technical-proposal navigation structure."""
    return [
        NavigationItem(
            "公司简介",
            [
                "cover",
                "company_intro",
                "company_qualification",
                "revision_record",
                "ending",
            ],
        ),
        NavigationItem(
            "工艺分析",
            ["customer_requirement", "inspection_flow"],
        ),
        NavigationItem(
            "设备设计",
            ["equipment_overview", "equipment_module", "equipment_parameters"],
        ),
        NavigationItem(
            "检测效果",
            ["inspection_result", "inspection_items"],
        ),
        NavigationItem(
            "系统介绍",
            ["vision_system", "control_system", "ai_algorithm", "core_components"],
        ),
    ]


@dataclass
class PresentationStyle:
    """Project-level visual settings shared by preview and final rendering."""

    navigation_height: float = 0.52
    navigation_background: str = "#FFFFFF"
    navigation_font_size: float | None = None
    navigation_items: list[NavigationItem] = field(
        default_factory=default_navigation_items
    )

    def validate(self) -> None:
        if not 0.42 <= self.navigation_height <= 0.72:
            raise ValueError("导航栏高度必须在 0.42～0.72 英寸之间")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", self.navigation_background):
            raise ValueError("导航栏背景色必须使用 #RRGGBB 格式")
        if self.navigation_font_size is not None and not (
            9.0 <= float(self.navigation_font_size) <= 16.0
        ):
            raise ValueError("导航栏手动字号必须在 9～16 pt 之间")
        if not 1 <= len(self.navigation_items) <= 7:
            raise ValueError("导航栏目数量必须在 1～7 个之间")
        names: set[str] = set()
        assigned_modules: set[str] = set()
        for item in self.navigation_items:
            if not isinstance(item, NavigationItem):
                raise ValueError("导航栏目必须是 NavigationItem")
            item.validate()
            normalized_name = item.name.strip()
            if normalized_name in names:
                raise ValueError(f"导航栏目名称不能重复：{normalized_name}")
            names.add(normalized_name)
            overlap = assigned_modules.intersection(item.module_keys)
            if overlap:
                raise ValueError(f"同一模块不能归属多个导航栏目：{sorted(overlap)[0]}")
            assigned_modules.update(item.module_keys)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "navigation_height": round(float(self.navigation_height), 2),
            "navigation_background": self.navigation_background.upper(),
            "navigation_font_size": (
                None
                if self.navigation_font_size is None
                else round(float(self.navigation_font_size), 1)
            ),
            "navigation_items": [item.to_dict() for item in self.navigation_items],
        }

    def resolved_navigation_font_size(self) -> float:
        """Return the manual size or the height-derived automatic size."""
        if self.navigation_font_size is not None:
            return round(float(self.navigation_font_size), 1)
        automatic = 10.0 * float(self.navigation_height) / 0.52
        return min(14.0, max(9.0, round(automatic * 2) / 2))

    def navigation_index_for(self, template_module_key: str) -> int | None:
        for index, item in enumerate(self.navigation_items):
            if template_module_key in item.module_keys:
                return index
        return None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "PresentationStyle":
        if not isinstance(raw, Mapping):
            raise ValueError("项目样式 presentation_style 必须是对象")
        raw_items = raw.get("navigation_items")
        if raw_items is None:
            navigation_items = default_navigation_items()
        elif not isinstance(raw_items, list):
            raise ValueError("项目样式 navigation_items 必须是数组")
        else:
            navigation_items = [NavigationItem.from_dict(item) for item in raw_items]
        style = cls(
            navigation_height=float(raw.get("navigation_height", 0.52)),
            navigation_background=str(
                raw.get("navigation_background") or "#FFFFFF"
            ).upper(),
            navigation_font_size=(
                None
                if raw.get("navigation_font_size") in (None, "")
                else float(raw["navigation_font_size"])
            ),
            navigation_items=navigation_items,
        )
        style.validate()
        return style


def new_project_id() -> str:
    """Return a compact stable identifier for project-owned objects."""
    return uuid4().hex


def normalize_project_id(value: Any = "") -> str:
    """Return a safe stable project identifier for project-owned directories."""
    project_id = str(value or new_project_id()).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32}", project_id):
        raise ValueError("项目 project_id 必须是32位十六进制标识")
    return project_id


def normalize_ai_image_batches(
    batches: Any,
    project_id: str,
) -> list[dict[str, Any]]:
    if not isinstance(batches, list):
        raise ValueError("项目文件 ai_image_batches 必须是数组")
    normalized: list[dict[str, Any]] = []
    for batch in batches:
        if not isinstance(batch, Mapping):
            raise ValueError("项目候选批次记录必须是对象")
        record = deepcopy(dict(batch))
        owner = str(record.get("projectId") or "")
        if owner and owner != project_id:
            raise ValueError("项目候选批次 projectId 与当前项目不一致")
        record["projectId"] = project_id
        normalized.append(record)
    return normalized


@dataclass
class SourceRecord:
    path: str
    kind: str = ""
    content: str = ""


@dataclass
class AssetRecord:
    path: str
    category: str = "未分类"
    slot_key: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PageTemplateRef:
    key: str
    name: str
    source_slide: int
    role: str = "content"
    default_title: str = ""
    default_subtitle: str = ""
    system_slots: dict[str, int] = field(default_factory=dict)
    remove_shape_ids: list[int] = field(default_factory=list)
    number_format: str = "{page_number} / {total_pages}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "PageTemplateRef":
        return cls(
            key=str(raw.get("key") or ""),
            name=str(raw.get("name") or raw.get("key") or "未命名页面模板"),
            source_slide=int(raw.get("source_slide") or 0),
            role=str(raw.get("role") or "content"),
            default_title=str(raw.get("default_title") or ""),
            default_subtitle=str(raw.get("default_subtitle") or ""),
            system_slots={
                str(key): int(value)
                for key, value in dict(raw.get("system_slots") or {}).items()
            },
            remove_shape_ids=[
                int(value) for value in raw.get("remove_shape_ids", [])
            ],
            number_format=str(
                raw.get("number_format") or "{page_number} / {total_pages}"
            ),
        )


@dataclass
class ProjectSlide:
    page_template_key: str
    title: str = ""
    subtitle: str = ""
    overrides: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=new_project_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "page_template_key": self.page_template_key,
            "title": self.title,
            "subtitle": self.subtitle,
            "overrides": deepcopy(self.overrides),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ProjectSlide":
        overrides = raw.get("overrides", {})
        if not isinstance(overrides, dict):
            raise ValueError("项目页面 overrides 必须是对象")
        return cls(
            id=str(raw.get("id") or new_project_id()),
            page_template_key=str(raw.get("page_template_key") or ""),
            title=str(raw.get("title") or ""),
            subtitle=str(raw.get("subtitle") or ""),
            overrides=deepcopy(overrides),
        )


@dataclass
class ProjectModule:
    template_module_key: str
    name: str
    module_type: str = "fixed"
    enabled: bool = True
    module_values: dict[str, Any] = field(default_factory=dict)
    page_templates: list[PageTemplateRef] = field(default_factory=list)
    default_sequence: list[str] = field(default_factory=list)
    default_add_template: str = ""
    generated_by_binding_id: str = ""
    generated_row_index: int | None = None
    slides: list[ProjectSlide] = field(default_factory=list)
    id: str = field(default_factory=new_project_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "template_module_key": self.template_module_key,
            "name": self.name,
            "module_type": self.module_type,
            "enabled": self.enabled,
            "module_values": deepcopy(self.module_values),
            "page_templates": [item.to_dict() for item in self.page_templates],
            "default_sequence": list(self.default_sequence),
            "default_add_template": self.default_add_template,
            "generated_by_binding_id": self.generated_by_binding_id,
            "generated_row_index": self.generated_row_index,
            "slides": [item.to_dict() for item in self.slides],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ProjectModule":
        module_values = raw.get("module_values", {})
        if not isinstance(module_values, dict):
            raise ValueError("项目模块 module_values 必须是对象")
        return cls(
            id=str(raw.get("id") or new_project_id()),
            template_module_key=str(raw.get("template_module_key") or ""),
            name=str(raw.get("name") or "未命名模块"),
            module_type=str(raw.get("module_type") or "fixed"),
            enabled=bool(raw.get("enabled", True)),
            module_values=deepcopy(module_values),
            page_templates=[
                PageTemplateRef.from_dict(item)
                for item in raw.get("page_templates", [])
            ],
            default_sequence=[str(item) for item in raw.get("default_sequence", [])],
            default_add_template=str(raw.get("default_add_template") or ""),
            generated_by_binding_id=str(raw.get("generated_by_binding_id") or ""),
            generated_row_index=(
                int(raw["generated_row_index"])
                if raw.get("generated_row_index") is not None
                else None
            ),
            slides=[ProjectSlide.from_dict(item) for item in raw.get("slides", [])],
        )


@dataclass
class ExcelModuleBinding:
    source_module_id: str
    source_path: str
    sheet: str
    header_row: int = 1
    data_range: str = ""
    field_map: dict[str, str] = field(default_factory=dict)
    module_name_field: str = ""
    id: str = field(default_factory=new_project_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ExcelModuleBinding":
        field_map = raw.get("field_map", {})
        if not isinstance(field_map, dict):
            raise ValueError("模块 Excel 绑定 field_map 必须是对象")
        return cls(
            id=str(raw.get("id") or new_project_id()),
            source_module_id=str(raw.get("source_module_id") or ""),
            source_path=str(raw.get("source_path") or ""),
            sheet=str(raw.get("sheet") or ""),
            header_row=int(raw.get("header_row") or 1),
            data_range=str(raw.get("data_range") or "").upper(),
            field_map={str(key): str(value) for key, value in field_map.items()},
            module_name_field=str(raw.get("module_name_field") or ""),
        )


@dataclass
class FlowNode:
    name: str
    node_type: str = "其他"
    station: str = ""
    action: str = ""
    equipment_module_id: str = ""
    cycle_time: str = ""
    output: str = "下一步"
    source_scene_node_id: str = ""
    id: str = field(default_factory=new_project_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "FlowNode":
        return cls(
            id=str(raw.get("id") or new_project_id()),
            name=str(raw.get("name") or ""),
            node_type=str(raw.get("node_type") or "其他"),
            station=str(raw.get("station") or ""),
            action=str(raw.get("action") or ""),
            equipment_module_id=str(raw.get("equipment_module_id") or ""),
            cycle_time=str(raw.get("cycle_time") or ""),
            output=str(raw.get("output") or "下一步"),
            source_scene_node_id=str(raw.get("source_scene_node_id") or ""),
        )


@dataclass
class DeviceModule:
    name: str
    module_type: str = "其他"
    function: str = ""
    action: str = ""
    station: str = ""
    image_path: str = ""
    note: str = ""
    page_template_key: str = ""
    enabled: bool = True
    source_scene_node_id: str = ""
    structure_definition: dict[str, Any] = field(default_factory=dict)
    image_prompt: str = ""
    image_provenance: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=new_project_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "DeviceModule":
        structure = raw.get("structure_definition") or {}
        provenance = raw.get("image_provenance") or {}
        if not isinstance(structure, Mapping):
            raise ValueError("设备模块 structure_definition 必须是对象")
        if not isinstance(provenance, Mapping):
            raise ValueError("设备模块 image_provenance 必须是对象")
        return cls(
            id=str(raw.get("id") or new_project_id()),
            name=str(raw.get("name") or ""),
            module_type=str(raw.get("module_type") or "其他"),
            function=str(raw.get("function") or ""),
            action=str(raw.get("action") or ""),
            station=str(raw.get("station") or ""),
            image_path=str(raw.get("image_path") or ""),
            note=str(raw.get("note") or ""),
            page_template_key=str(raw.get("page_template_key") or ""),
            enabled=bool(raw.get("enabled", True)),
            source_scene_node_id=str(raw.get("source_scene_node_id") or ""),
            structure_definition=deepcopy(dict(structure)),
            image_prompt=str(raw.get("image_prompt") or ""),
            image_provenance=deepcopy(dict(provenance)),
        )


@dataclass
class EquipmentScheme:
    initialized: bool = False
    overview_image: str = ""
    overview_description: str = ""
    overview_structure: dict[str, Any] = field(default_factory=dict)
    overview_prompt: str = ""
    overview_image_provenance: dict[str, Any] = field(default_factory=dict)
    flow_nodes: list[FlowNode] = field(default_factory=list)
    equipment_modules: list[DeviceModule] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "initialized": self.initialized,
            "overview_image": self.overview_image,
            "overview_description": self.overview_description,
            "overview_structure": deepcopy(self.overview_structure),
            "overview_prompt": self.overview_prompt,
            "overview_image_provenance": deepcopy(
                self.overview_image_provenance
            ),
            "flow_nodes": [item.to_dict() for item in self.flow_nodes],
            "equipment_modules": [
                item.to_dict() for item in self.equipment_modules
            ],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "EquipmentScheme":
        flow_nodes = raw.get("flow_nodes", [])
        equipment_modules = raw.get("equipment_modules", [])
        overview_structure = raw.get("overview_structure") or {}
        overview_provenance = raw.get("overview_image_provenance") or {}
        if not isinstance(flow_nodes, list):
            raise ValueError("设备方案 flow_nodes 必须是数组")
        if not isinstance(equipment_modules, list):
            raise ValueError("设备方案 equipment_modules 必须是数组")
        if not isinstance(overview_structure, Mapping):
            raise ValueError("设备方案 overview_structure 必须是对象")
        if not isinstance(overview_provenance, Mapping):
            raise ValueError("设备方案 overview_image_provenance 必须是对象")
        return cls(
            initialized=bool(raw.get("initialized", False)),
            overview_image=str(raw.get("overview_image") or ""),
            overview_description=str(raw.get("overview_description") or ""),
            overview_structure=deepcopy(dict(overview_structure)),
            overview_prompt=str(raw.get("overview_prompt") or ""),
            overview_image_provenance=deepcopy(dict(overview_provenance)),
            flow_nodes=[FlowNode.from_dict(item) for item in flow_nodes],
            equipment_modules=[
                DeviceModule.from_dict(item) for item in equipment_modules
            ],
        )


@dataclass
class PptProject:
    project_id: str = field(default_factory=new_project_id)
    project_name: str = "未命名技术方案"
    template_path: str = ""
    manifest_path: str = ""
    output_path: str = ""
    presentation_style: PresentationStyle = field(default_factory=PresentationStyle)
    excel_path: str = ""
    values: dict[str, Any] = field(default_factory=dict)
    enabled_modules: list[str] = field(default_factory=list)
    module_order: list[str] = field(default_factory=list)
    modules: list[ProjectModule] = field(default_factory=list)
    module_bindings: list[ExcelModuleBinding] = field(default_factory=list)
    equipment_scheme: EquipmentScheme = field(default_factory=EquipmentScheme)
    no_cad_scene: dict[str, Any] = field(default_factory=dict)
    ai_image_batches: list[dict[str, Any]] = field(default_factory=list)
    sources: list[SourceRecord] = field(default_factory=list)
    assets: list[AssetRecord] = field(default_factory=list)
    excel_mappings: list[ExcelMappingRule] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        project_id = normalize_project_id(self.project_id)
        return {
            "schema_version": PROJECT_SCHEMA_VERSION,
            "project_id": project_id,
            "project_name": self.project_name,
            "template_path": self.template_path,
            "manifest_path": self.manifest_path,
            "output_path": self.output_path,
            "presentation_style": self.presentation_style.to_dict(),
            "excel_path": self.excel_path,
            "values": deepcopy(self.values),
            # Retained for schema-v1 tools. The schema-v2 UI uses ``modules``.
            "enabled_modules": list(self.enabled_modules),
            "module_order": list(self.module_order),
            "modules": [item.to_dict() for item in self.modules],
            "module_bindings": [item.to_dict() for item in self.module_bindings],
            "equipment_scheme": self.equipment_scheme.to_dict(),
            "no_cad_scene": deepcopy(self.no_cad_scene),
            "ai_image_batches": normalize_ai_image_batches(
                self.ai_image_batches,
                project_id,
            ),
            "sources": [asdict(item) for item in self.sources],
            "assets": [asdict(item) for item in self.assets],
            "excel_mappings": [item.to_dict() for item in self.excel_mappings],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PptProject":
        schema_version = raw.get("schema_version")
        if schema_version not in SUPPORTED_PROJECT_SCHEMA_VERSIONS:
            raise ValueError("项目文件 schema_version 必须为 1、2、3、4 或 5")
        values = raw.get("values", {})
        if not isinstance(values, dict):
            raise ValueError("项目文件 values 必须是对象")
        project_id = normalize_project_id(raw.get("project_id"))
        no_cad_scene = raw.get("no_cad_scene") or {}
        if not isinstance(no_cad_scene, Mapping):
            raise ValueError("项目文件 no_cad_scene 必须是对象")
        normalized_batches = normalize_ai_image_batches(
            raw.get("ai_image_batches") or [],
            project_id,
        )
        return cls(
            project_id=project_id,
            project_name=str(raw.get("project_name") or "未命名技术方案"),
            template_path=str(raw.get("template_path") or ""),
            manifest_path=str(raw.get("manifest_path") or ""),
            output_path=str(raw.get("output_path") or ""),
            presentation_style=PresentationStyle.from_dict(
                raw.get("presentation_style") or {}
            ),
            excel_path=str(raw.get("excel_path") or ""),
            values=deepcopy(values),
            enabled_modules=[str(item) for item in raw.get("enabled_modules", [])],
            module_order=[str(item) for item in raw.get("module_order", [])],
            modules=[ProjectModule.from_dict(item) for item in raw.get("modules", [])],
            module_bindings=[
                ExcelModuleBinding.from_dict(item)
                for item in raw.get("module_bindings", [])
            ],
            equipment_scheme=EquipmentScheme.from_dict(
                raw.get("equipment_scheme") or {}
            ),
            no_cad_scene=deepcopy(dict(no_cad_scene)),
            ai_image_batches=normalized_batches,
            sources=[SourceRecord(**item) for item in raw.get("sources", [])],
            assets=[AssetRecord(**item) for item in raw.get("assets", [])],
            excel_mappings=[
                ExcelMappingRule.from_dict(item) for item in raw.get("excel_mappings", [])
            ],
        )


def save_project(project: PptProject, path: str | Path) -> Path:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(project.to_dict(), ensure_ascii=False, indent=2).encode("utf-8")
    if destination.is_file() and destination.read_bytes() == content:
        return destination

    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if destination.is_file():
            oldest = destination.with_suffix(destination.suffix + ".bak3")
            oldest.unlink(missing_ok=True)
            for number in range(2, 0, -1):
                source = destination.with_suffix(destination.suffix + f".bak{number}")
                target = destination.with_suffix(destination.suffix + f".bak{number + 1}")
                if source.is_file():
                    os.replace(source, target)
            shutil.copy2(
                destination,
                destination.with_suffix(destination.suffix + ".bak1"),
            )
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def load_project(path: str | Path) -> PptProject:
    source = Path(path).expanduser().resolve()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"项目文件不是有效 JSON：{exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("项目文件顶层必须是对象")
    return PptProject.from_dict(raw)
