"""Structured equipment-scheme operations independent from PySide6."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from .module_service import ensure_project_modules, page_template_by_key
from .project import (
    DeviceModule,
    FlowNode,
    PptProject,
    ProjectModule,
    ProjectSlide,
)

if TYPE_CHECKING:
    from .template_renderer import TemplateManifest


FLOW_SLOT_KEYS = tuple(f"flow_step_{index:02d}" for index in range(1, 9))
DEFAULT_FLOW_CAPACITY = len(FLOW_SLOT_KEYS)
FLOW_AUX_VALUES = {
    "flow_aux_vision": "视觉检测",
    "flow_aux_station": "检测工位",
    "flow_aux_reject": "剔料口",
    "flow_aux_container": "周转箱",
    "flow_result_minor_ng": "待复检",
    "flow_result_severe_ng": "NG下料",
}

DEVICE_SLOT_KEYS: dict[int, dict[str, str]] = {
    6: {
        "title": "equipment_module_title_s6",
        "description": "equipment_module_description_s6",
        "image": "equipment_module_image_s6",
        "caption": "equipment_module_caption_s6",
        "note": "equipment_module_note_s6",
    },
    7: {
        "title": "equipment_module_title_s7",
        "description": "equipment_module_description_s7",
        "image": "equipment_module_image_s7",
        "caption": "equipment_module_caption_s7",
    },
    8: {
        "title": "equipment_module_title_s8",
        "description": "equipment_module_description_s8",
        "image": "equipment_module_image_s8",
        "caption": "equipment_module_caption_s8",
    },
    9: {
        "title": "equipment_module_title_s9",
        "description": "equipment_module_description_s9",
        "image": "equipment_module_image_s9",
        "caption": "equipment_module_caption_s9",
        "note": "equipment_module_note_s9",
    },
}


class SchemeError(ValueError):
    """Raised when structured scheme data cannot be materialized safely."""


@dataclass(frozen=True)
class SchemeMaterializationResult:
    flow_pages: int
    equipment_pages: int
    overview_updated: bool


def initialize_equipment_scheme(project: PptProject) -> None:
    """Migrate legacy flow Slot values once without recreating deleted nodes."""
    scheme = project.equipment_scheme
    if scheme.initialized:
        return
    for index, key in enumerate(FLOW_SLOT_KEYS, start=1):
        name = str(project.values.get(key) or "").strip()
        if name:
            scheme.flow_nodes.append(
                FlowNode(name=name, node_type="检测" if "检测" in name else "其他")
            )
    scheme.initialized = True


def flow_node_by_id(project: PptProject, node_id: str) -> FlowNode:
    for node in project.equipment_scheme.flow_nodes:
        if node.id == node_id:
            return node
    raise SchemeError(f"设备流程中不存在节点：{node_id}")


def device_module_by_id(project: PptProject, module_id: str) -> DeviceModule:
    for module in project.equipment_scheme.equipment_modules:
        if module.id == module_id:
            return module
    raise SchemeError(f"设备方案中不存在功能模块：{module_id}")


def add_flow_node(project: PptProject, name: str = "新流程节点") -> FlowNode:
    initialize_equipment_scheme(project)
    node = FlowNode(name=name)
    project.equipment_scheme.flow_nodes.append(node)
    return node


def remove_flow_node(project: PptProject, node_id: str) -> FlowNode:
    node = flow_node_by_id(project, node_id)
    project.equipment_scheme.flow_nodes.remove(node)
    return node


def move_flow_node(project: PptProject, node_id: str, offset: int) -> bool:
    nodes = project.equipment_scheme.flow_nodes
    node = flow_node_by_id(project, node_id)
    current = nodes.index(node)
    target = current + offset
    if target < 0 or target >= len(nodes):
        return False
    nodes.pop(current)
    nodes.insert(target, node)
    return True


def add_device_module(project: PptProject, name: str = "新设备模块") -> DeviceModule:
    initialize_equipment_scheme(project)
    module = DeviceModule(name=name)
    project.equipment_scheme.equipment_modules.append(module)
    return module


def referenced_flow_nodes(project: PptProject, module_id: str) -> list[FlowNode]:
    return [
        node
        for node in project.equipment_scheme.flow_nodes
        if node.equipment_module_id == module_id
    ]


def remove_device_module(
    project: PptProject,
    module_id: str,
    *,
    clear_links: bool = False,
) -> DeviceModule:
    module = device_module_by_id(project, module_id)
    references = referenced_flow_nodes(project, module_id)
    if references and not clear_links:
        names = "、".join(node.name for node in references)
        raise SchemeError(f"设备模块“{module.name}”仍被流程节点引用：{names}")
    for node in references:
        node.equipment_module_id = ""
    project.equipment_scheme.equipment_modules.remove(module)
    return module


def move_device_module(project: PptProject, module_id: str, offset: int) -> bool:
    modules = project.equipment_scheme.equipment_modules
    module = device_module_by_id(project, module_id)
    current = modules.index(module)
    target = current + offset
    if target < 0 or target >= len(modules):
        return False
    modules.pop(current)
    modules.insert(target, module)
    return True


def _project_module(project: PptProject, key: str) -> ProjectModule:
    module = next(
        (
            item
            for item in project.modules
            if item.template_module_key == key and not item.generated_by_binding_id
        ),
        None,
    )
    if module is None:
        raise SchemeError(f"当前模板项目缺少“{key}”PPT模块")
    return module


def _manifest_module(manifest: "TemplateManifest", key: str) -> dict:
    module = next((item for item in manifest.modules if item["key"] == key), None)
    if module is None:
        raise SchemeError(f"模板配置缺少“{key}”模块")
    return module


def _chunks(items: list[FlowNode], size: int) -> Iterable[list[FlowNode]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _flow_capacity(manifest: "TemplateManifest") -> int:
    configured = int(
        _manifest_module(manifest, "inspection_flow").get(
            "flow_capacity", DEFAULT_FLOW_CAPACITY
        )
    )
    if not 1 <= configured <= len(FLOW_SLOT_KEYS):
        raise SchemeError(
            f"检测流程页面容量必须在 1～{len(FLOW_SLOT_KEYS)} 之间"
        )
    return configured


def _sync_scheme_page_template_metadata(
    project: PptProject,
    manifest: "TemplateManifest",
) -> None:
    """Apply new cleanup metadata when an older schema-v2 project is opened."""
    raw_module = _manifest_module(manifest, "equipment_module")
    raw_templates = raw_module.get("page_templates") or []
    removals_by_source = {
        int(item["source_slide"]): [
            int(shape_id) for shape_id in item.get("remove_shape_ids", [])
        ]
        for item in raw_templates
        if isinstance(item, dict) and item.get("source_slide")
    }
    module = _project_module(project, "equipment_module")
    for template in module.page_templates:
        if template.source_slide in removals_by_source:
            template.remove_shape_ids = list(
                removals_by_source[template.source_slide]
            )


def _flow_page_template(module: ProjectModule):
    template = next(
        (item for item in module.page_templates if item.source_slide == 4),
        None,
    )
    if template is None:
        raise SchemeError("检测流程模块没有绑定模板第4页")
    return template


def _device_page_template(module: ProjectModule, requested_key: str):
    if requested_key:
        try:
            requested = page_template_by_key(module, requested_key)
            if requested.source_slide in DEVICE_SLOT_KEYS:
                return requested
        except ValueError:
            pass
    preferred = next(
        (item for item in module.page_templates if item.source_slide == 7),
        None,
    )
    if preferred:
        return preferred
    fallback = next(
        (item for item in module.page_templates if item.source_slide in DEVICE_SLOT_KEYS),
        None,
    )
    if fallback is None:
        raise SchemeError("设备模块没有绑定模板第6～9页中的可用页面")
    return fallback


def _validate_scheme(project: PptProject, *, require_module_images: bool) -> None:
    scheme = project.equipment_scheme
    empty_nodes = [index for index, node in enumerate(scheme.flow_nodes, start=1) if not node.name.strip()]
    if empty_nodes:
        raise SchemeError(f"流程第 {empty_nodes[0]} 步没有填写节点名称")
    long_nodes = [node.name for node in scheme.flow_nodes if len(node.name) > 16]
    if long_nodes:
        raise SchemeError(f"流程节点名称超过16字：{long_nodes[0]}")

    enabled = [item for item in scheme.equipment_modules if item.enabled]
    empty_modules = [item for item in enabled if not item.name.strip()]
    if empty_modules:
        raise SchemeError("启用的设备功能模块必须填写名称")
    names = [item.name.strip() for item in enabled]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise SchemeError(f"设备功能模块名称重复：{duplicates[0]}")
    valid_ids = {item.id for item in scheme.equipment_modules}
    invalid_link = next(
        (
            node
            for node in scheme.flow_nodes
            if node.equipment_module_id
            and node.equipment_module_id not in valid_ids
        ),
        None,
    )
    if invalid_link:
        raise SchemeError(f"流程节点“{invalid_link.name}”关联了不存在的设备模块")
    if require_module_images:
        missing = [
            item.name
            for item in enabled
            if not item.image_path or not Path(item.image_path).expanduser().is_file()
        ]
        if missing:
            raise SchemeError(
                f"设备模块“{missing[0]}”还没有有效方案图，不能同步到正式PPT"
            )
    overview_image = scheme.overview_image.strip()
    if overview_image and not Path(overview_image).expanduser().is_file():
        raise SchemeError(f"整机方案图不存在：{overview_image}")


def _materialize_flow(project: PptProject, manifest: "TemplateManifest") -> int:
    nodes = project.equipment_scheme.flow_nodes
    if not nodes:
        return 0
    module = _project_module(project, "inspection_flow")
    template = _flow_page_template(module)
    capacity = _flow_capacity(manifest)
    pages = list(_chunks(nodes, capacity))
    result: list[ProjectSlide] = []
    for page_index, page_nodes in enumerate(pages, start=1):
        overrides = {key: "" for key in FLOW_SLOT_KEYS}
        for node_index, node in enumerate(page_nodes, start=1):
            overrides[FLOW_SLOT_KEYS[node_index - 1]] = node.name.strip()
        overrides.update(
            {
                "flow_title": (
                    "2.2  检测流程"
                    if len(pages) == 1
                    else f"2.2  检测流程（{page_index}/{len(pages)}）"
                ),
                "flow_result_ok": str(project.values.get("flow_result_ok") or "OK"),
                "flow_result_ng": str(project.values.get("flow_result_ng") or "NG"),
                "flow_caption": (
                    "图 2.2 设备功能流程图"
                    if len(pages) == 1
                    else f"图 2.2-{page_index} 设备功能流程图"
                ),
            }
        )
        overrides.update(
            {
                key: str(project.values.get(key, default) or "")
                for key, default in FLOW_AUX_VALUES.items()
            }
        )
        start = (page_index - 1) * capacity + 1
        end = start + len(page_nodes) - 1
        result.append(
            ProjectSlide(
                page_template_key=template.key,
                title=(
                    "检测流程"
                    if len(pages) == 1
                    else f"检测流程 {page_index}/{len(pages)}"
                ),
                subtitle=f"步骤 {start}～{end}",
                overrides=overrides,
            )
        )
    module.module_type = "dataDriven"
    module.enabled = True
    module.slides = result
    return len(result)


def _linked_node_names(project: PptProject, module_id: str) -> list[str]:
    return [
        node.name.strip()
        for node in project.equipment_scheme.flow_nodes
        if node.equipment_module_id == module_id
    ]


def _device_description(
    module: DeviceModule,
    linked_nodes: list[str],
) -> str:
    lines: list[str] = []
    if module.station.strip():
        lines.append(f"对应工位：{module.station.strip()}")
    if module.function.strip():
        lines.append(f"模块功能：{module.function.strip()}")
    if module.action.strip():
        lines.append(f"动作过程：{module.action.strip()}")
    if linked_nodes:
        lines.append(f"关联流程：{'、'.join(linked_nodes)}")
    return "\n".join(lines) or "设备模块说明待工程师确认。"


def _materialize_overview(project: PptProject) -> bool:
    scheme = project.equipment_scheme
    enabled = [item for item in scheme.equipment_modules if item.enabled]
    if not enabled and not scheme.overview_description.strip() and not scheme.overview_image.strip():
        return False
    module = _project_module(project, "equipment_overview")
    if not module.slides:
        if not module.default_sequence:
            raise SchemeError("设备总览模块没有默认页面")
        module.slides = [ProjectSlide(page_template_key=module.default_sequence[0])]
    description = scheme.overview_description.strip()
    if not description and enabled:
        names = "、".join(item.name.strip() for item in enabled[:12])
        suffix = "等" if len(enabled) > 12 else ""
        description = f"本设备由{names}{suffix}组成，各模块按照检测流程协同运行。"
    overrides = {
        "equipment_title": "3.1  设备示意图",
        "equipment_description": description,
        "equipment_caption": "图 3.1 设备示意图",
    }
    if scheme.overview_image.strip():
        overrides["equipment_image"] = scheme.overview_image.strip()
    module.slides[0].title = "设备总览"
    module.slides[0].overrides.update(overrides)
    module.enabled = True
    return True


def _materialize_device_modules(project: PptProject) -> int:
    scheme = project.equipment_scheme
    if not scheme.equipment_modules:
        return 0
    ppt_module = _project_module(project, "equipment_module")
    slides: list[ProjectSlide] = []
    enabled_modules = [item for item in scheme.equipment_modules if item.enabled]
    for index, module in enumerate(enabled_modules, start=1):
        template = _device_page_template(ppt_module, module.page_template_key)
        module.page_template_key = template.key
        keys = DEVICE_SLOT_KEYS[template.source_slide]
        linked_nodes = _linked_node_names(project, module.id)
        title = f"3.1.{index}  {module.name.strip()}"
        caption = f"图 3.{index + 1} {module.name.strip()}"
        overrides = {
            keys["title"]: title,
            keys["description"]: _device_description(module, linked_nodes),
            keys["image"]: str(Path(module.image_path).expanduser().resolve()),
            keys["caption"]: caption,
        }
        note_key = keys.get("note")
        if note_key:
            overrides[note_key] = (
                module.note.strip()
                or "特别说明：机械方案图以工程师最终确认版本为准。"
            )
        slides.append(
            ProjectSlide(
                page_template_key=template.key,
                title=module.name.strip(),
                subtitle="、".join(linked_nodes),
                overrides=overrides,
            )
        )
    ppt_module.module_type = "dataDriven"
    ppt_module.slides = slides
    ppt_module.enabled = bool(slides)
    return len(slides)


def materialize_equipment_scheme(
    project: PptProject,
    manifest: "TemplateManifest",
    *,
    require_module_images: bool = True,
) -> SchemeMaterializationResult:
    """Write the confirmed scheme into existing PPT module/page instances."""
    ensure_project_modules(project, manifest)
    initialize_equipment_scheme(project)
    _sync_scheme_page_template_metadata(project, manifest)
    _validate_scheme(project, require_module_images=require_module_images)
    flow_pages = _materialize_flow(project, manifest)
    overview_updated = _materialize_overview(project)
    equipment_pages = _materialize_device_modules(project)
    return SchemeMaterializationResult(
        flow_pages=flow_pages,
        equipment_pages=equipment_pages,
        overview_updated=overview_updated,
    )
