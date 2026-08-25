"""Application service importing reviewed no-CAD scenes into formal projects."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from .no_cad_scheme import EquipmentScene, MODULE_BY_TYPE, NoCadSchemeService
from .project import AssetRecord, DeviceModule, FlowNode, PptProject
from .scheme_service import (
    SchemeError,
    SchemeMaterializationResult,
    materialize_equipment_scheme,
)
from .template_renderer import TemplateManifest


CATEGORY_TO_DEVICE_TYPE = {
    "feed": "上料",
    "convey": "搬运",
    "position": "定位",
    "inspect": "视觉检测",
    "reject": "分拣",
    "unload": "下料",
}

CATEGORY_TO_FLOW_TYPE = {
    "feed": "上料",
    "convey": "搬运",
    "position": "定位",
    "inspect": "检测",
    "reject": "分拣",
    "unload": "下料",
}


@dataclass(frozen=True)
class NoCadImportResult:
    flow_nodes: int
    equipment_modules: int
    image_targets: int
    pending_images: int


@dataclass(frozen=True)
class NoCadPptSyncResult:
    imported: NoCadImportResult
    materialization: SchemeMaterializationResult | None
    pending_image_names: tuple[str, ...]

    @property
    def ppt_updated(self) -> bool:
        return self.materialization is not None


def _remember_asset(
    project: PptProject,
    path: str,
    *,
    target_id: str,
    target_kind: str,
    provenance: dict,
) -> None:
    if not path:
        return
    resolved = str(Path(path).expanduser().resolve())
    metadata = {
        "source": str(provenance.get("source") or "no-cad-ai"),
        "targetId": target_id,
        "targetKind": target_kind,
        "provenance": deepcopy(provenance),
    }
    existing = next(
        (item for item in project.assets if Path(item.path) == Path(resolved)),
        None,
    )
    if existing is None:
        project.assets.append(
            AssetRecord(
                path=resolved,
                category="设备图",
                metadata=metadata,
            )
        )
    else:
        existing.category = "设备图"
        existing.metadata.update(metadata)


def import_no_cad_scene(
    project: PptProject,
    scene: EquipmentScene,
) -> NoCadImportResult:
    """Upsert one reviewed Scene without touching manually-created project modules."""
    service = NoCadSchemeService()
    result = service.evaluate(scene)
    if not result.can_generate_ai:
        raise SchemeError("无CAD设备方案未通过逻辑门禁，不能同步到正式项目")
    stale_targets = service.stale_image_target_ids(scene, result)
    if stale_targets:
        raise SchemeError(
            "以下采用图已因模块结构或顺序变化失效，请重新生成："
            + "、".join(stale_targets)
        )

    scheme = project.equipment_scheme
    overview = result.visual_target("overview")
    scheme.initialized = True
    scheme.overview_structure = deepcopy(dict(overview.structure))
    scheme.overview_prompt = overview.prompt
    scheme.overview_image = scene.overview_image
    scheme.overview_image_provenance = deepcopy(
        scene.overview_image_provenance
    )
    if not scheme.overview_description.strip():
        names = "、".join(node.name for node in scene.nodes)
        scheme.overview_description = (
            f"本设备按照从左到右的产品主线布置，由{names}组成。"
        )

    existing_modules = {
        value.source_scene_node_id: value
        for value in scheme.equipment_modules
        if value.source_scene_node_id
    }
    manual_modules = [
        value for value in scheme.equipment_modules if not value.source_scene_node_id
    ]
    imported_modules: list[DeviceModule] = []
    modules_by_node_id: dict[str, DeviceModule] = {}
    for node in scene.nodes:
        definition = MODULE_BY_TYPE.get(node.module_type)
        category = definition.category if definition else ""
        module = existing_modules.get(node.node_id)
        if module is None:
            module = DeviceModule(
                name=node.name,
                source_scene_node_id=node.node_id,
            )
        target = result.visual_target(node.node_id)
        module.name = node.name
        module.module_type = CATEGORY_TO_DEVICE_TYPE.get(category, "其他")
        module.function = node.description
        module.action = str(target.structure.get("productPath") or "")
        module.station = node.station_id
        module.image_path = node.image_path
        module.structure_definition = deepcopy(dict(target.structure))
        module.image_prompt = target.prompt
        module.image_provenance = deepcopy(node.image_provenance)
        module.source_scene_node_id = node.node_id
        imported_modules.append(module)
        modules_by_node_id[node.node_id] = module

    existing_flows = {
        value.source_scene_node_id: value
        for value in scheme.flow_nodes
        if value.source_scene_node_id
    }
    manual_flows = [value for value in scheme.flow_nodes if not value.source_scene_node_id]
    imported_flows: list[FlowNode] = []
    for node in scene.nodes:
        definition = MODULE_BY_TYPE.get(node.module_type)
        category = definition.category if definition else ""
        flow = existing_flows.get(node.node_id)
        if flow is None:
            flow = FlowNode(
                name=node.name,
                source_scene_node_id=node.node_id,
            )
        flow.name = node.name
        flow.node_type = CATEGORY_TO_FLOW_TYPE.get(category, "其他")
        flow.station = node.station_id
        flow.action = node.description
        flow.output = "下一步"
        flow.equipment_module_id = modules_by_node_id[node.node_id].id
        flow.source_scene_node_id = node.node_id
        imported_flows.append(flow)

    scheme.equipment_modules = imported_modules + manual_modules
    scheme.flow_nodes = imported_flows + manual_flows

    _remember_asset(
        project,
        scene.overview_image,
        target_id="overview",
        target_kind="overview",
        provenance=scene.overview_image_provenance,
    )
    for node in scene.nodes:
        _remember_asset(
            project,
            node.image_path,
            target_id=node.node_id,
            target_kind="module",
            provenance=node.image_provenance,
        )

    targets = result.visual_targets
    accepted = sum(bool(value.image_path) for value in targets)
    return NoCadImportResult(
        flow_nodes=len(imported_flows),
        equipment_modules=len(imported_modules),
        image_targets=len(targets),
        pending_images=len(targets) - accepted,
    )


def sync_no_cad_scene_to_ppt(
    project: PptProject,
    scene: EquipmentScene,
    manifest: TemplateManifest,
) -> NoCadPptSyncResult:
    """Import a project-owned Scene and materialize PPT modules only when complete."""
    project_name = project.project_name.strip()
    scene_name = scene.project_name.strip()
    if not project_name or scene_name != project_name:
        raise SchemeError(
            f"无CAD方案项目名称“{scene_name or '未填写'}”与当前项目名称“{project_name or '未填写'}”不一致"
        )

    imported = import_no_cad_scene(project, scene)
    project.no_cad_scene = scene.to_dict()
    result = NoCadSchemeService().evaluate(scene)
    pending: list[str] = []
    for target in result.visual_targets:
        path = Path(target.image_path).expanduser() if target.image_path else None
        if path is None or not path.is_file():
            pending.append("整机方案" if target.target_id == "overview" else target.title)

    scene_module_ids = {node.node_id for node in scene.nodes}
    for module in project.equipment_scheme.equipment_modules:
        if (
            module.enabled
            and module.source_scene_node_id not in scene_module_ids
            and (
                not module.image_path
                or not Path(module.image_path).expanduser().is_file()
            )
        ):
            pending.append(module.name.strip() or "未命名手工模块")

    pending_names = tuple(dict.fromkeys(pending))
    if pending_names:
        return NoCadPptSyncResult(
            imported=imported,
            materialization=None,
            pending_image_names=pending_names,
        )
    return NoCadPptSyncResult(
        imported=imported,
        materialization=materialize_equipment_scheme(project, manifest),
        pending_image_names=(),
    )


__all__ = [
    "NoCadImportResult",
    "NoCadPptSyncResult",
    "import_no_cad_scene",
    "sync_no_cad_scene_to_ppt",
]
