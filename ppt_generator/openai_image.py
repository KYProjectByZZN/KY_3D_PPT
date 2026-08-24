"""OpenAI image-provider boundary for reviewed no-CAD equipment scenes."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from .no_cad_scheme import EquipmentScene, NoCadSchemeResult, NoCadSchemeService


DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-2-2026-04-21"
DEFAULT_OPENAI_IMAGE_SIZE = "1536x1024"
DEFAULT_OPENAI_IMAGE_QUALITY = "medium"
OPENAI_IMAGE_QUALITIES = ("low", "medium", "high")
OPENAI_IMAGE_SIZES = ("1536x1024", "2048x1152")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class OpenAIImageError(RuntimeError):
    """Raised when configuration, handoff, or provider output is invalid."""


class ImageProvider(Protocol):
    """Provider port used by the UI worker and focused tests."""

    def test_connection(self, api_key: str) -> str:
        """Validate credentials and return the resolved model id."""

    def generate(
        self,
        request: "OpenAIImageRequest",
        api_key: str,
    ) -> "OpenAIImageBatch":
        """Generate one traceable candidate batch."""


@dataclass(frozen=True)
class OpenAIImageRequest:
    scene_hash: str
    scene_snapshot: Mapping[str, Any]
    prompt: str
    control_image_path: Path
    output_root: Path
    model: str = DEFAULT_OPENAI_IMAGE_MODEL
    size: str = DEFAULT_OPENAI_IMAGE_SIZE
    quality: str = DEFAULT_OPENAI_IMAGE_QUALITY
    candidate_count: int = 1

    def __post_init__(self) -> None:
        if len(self.scene_hash) != 64:
            raise ValueError("scene_hash must be a 64-character SHA-256 value")
        if not self.prompt.strip():
            raise ValueError("prompt cannot be empty")
        if self.size not in OPENAI_IMAGE_SIZES:
            raise ValueError(f"unsupported image size: {self.size}")
        if self.quality not in OPENAI_IMAGE_QUALITIES:
            raise ValueError(f"unsupported image quality: {self.quality}")
        if not 1 <= self.candidate_count <= 4:
            raise ValueError("candidate_count must be between 1 and 4")

    def to_manifest_dict(self) -> dict[str, Any]:
        return {
            "sceneHash": self.scene_hash,
            "sceneSnapshot": dict(self.scene_snapshot),
            "prompt": self.prompt,
            "controlImage": str(self.control_image_path),
            "model": self.model,
            "size": self.size,
            "quality": self.quality,
            "candidateCount": self.candidate_count,
        }


@dataclass(frozen=True)
class OpenAIImageCandidate:
    candidate_id: str
    image_path: Path
    sha256: str
    revised_prompt: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "candidateId": self.candidate_id,
            "imagePath": str(self.image_path),
            "sha256": self.sha256,
            "revisedPrompt": self.revised_prompt,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OpenAIImageCandidate":
        return cls(
            candidate_id=str(raw.get("candidateId") or ""),
            image_path=Path(str(raw.get("imagePath") or "")),
            sha256=str(raw.get("sha256") or ""),
            revised_prompt=str(raw.get("revisedPrompt") or ""),
        )


@dataclass(frozen=True)
class OpenAIImageBatch:
    batch_id: str
    scene_hash: str
    provider: str
    model: str
    request_id: str
    created_at: str
    output_dir: Path
    manifest_path: Path
    candidates: tuple[OpenAIImageCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "batchId": self.batch_id,
            "sceneHash": self.scene_hash,
            "provider": self.provider,
            "model": self.model,
            "requestId": self.request_id,
            "createdAt": self.created_at,
            "outputDir": str(self.output_dir),
            "manifestPath": str(self.manifest_path),
            "candidates": [value.to_dict() for value in self.candidates],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OpenAIImageBatch":
        candidates = raw.get("candidates") or []
        if not isinstance(candidates, list):
            raise ValueError("候选批次 candidates 必须是数组")
        return cls(
            batch_id=str(raw.get("batchId") or ""),
            scene_hash=str(raw.get("sceneHash") or ""),
            provider=str(raw.get("provider") or ""),
            model=str(raw.get("model") or ""),
            request_id=str(raw.get("requestId") or ""),
            created_at=str(raw.get("createdAt") or ""),
            output_dir=Path(str(raw.get("outputDir") or "")),
            manifest_path=Path(str(raw.get("manifestPath") or "")),
            candidates=tuple(
                OpenAIImageCandidate.from_dict(value)
                for value in candidates
                if isinstance(value, Mapping)
            ),
        )


def build_openai_equipment_prompt(result: NoCadSchemeResult) -> str:
    """Build a conservative prompt around the deterministic scene brief."""

    return (
        "Create one industrial automation equipment concept rendering for a technical proposal.\n"
        "The attached image is an immutable engineering logic reference, not a style reference.\n"
        "Hard constraints:\n"
        "1. Preserve exactly the module count, left-to-right order, product-flow direction, and inspection/reject sequence shown in the reference.\n"
        "2. Do not add, remove, merge, duplicate, reverse, or exchange any station or functional module.\n"
        "3. Show one coherent machine on a clean light-gray studio background, with a practical steel frame, guarding, conveyor or feeder connections, cameras, lighting, reject mechanism, and collection area only where specified.\n"
        "4. Use a restrained industrial visual language: white and dark-gray enclosure panels, steel/aluminum structure, small red accents, realistic but concept-level detail.\n"
        "5. Use an elevated three-quarter engineering presentation view. Keep the full machine visible with generous margins.\n"
        "6. Do not render labels, captions, logos, dimensions, people, forklifts, workshop clutter, extra conveyors, or decorative machinery. The software will add authoritative labels later.\n"
        "7. This is a sales concept image, not a CAD drawing and not a manufacturing drawing.\n\n"
        "Authoritative scene constraints:\n"
        + result.generation_brief.strip()
    )


def prepare_openai_image_request(
    scene: EquipmentScene,
    result: NoCadSchemeResult,
    *,
    control_image_path: str | Path,
    output_root: str | Path,
    model: str = DEFAULT_OPENAI_IMAGE_MODEL,
    size: str = DEFAULT_OPENAI_IMAGE_SIZE,
    quality: str = DEFAULT_OPENAI_IMAGE_QUALITY,
    candidate_count: int = 1,
    target_id: str = "",
) -> OpenAIImageRequest:
    """Freeze a validated scene handoff without granting provider write access."""

    snapshot = EquipmentScene.from_dict(scene.to_dict())
    current = NoCadSchemeService().evaluate(snapshot)
    if not current.can_generate_ai:
        raise OpenAIImageError("当前设备方案未通过逻辑门禁，禁止提交 OpenAI。")
    if current.scene_hash != result.scene_hash:
        raise OpenAIImageError("设备方案已发生变化，请刷新检查结果后再生成。")
    control_path = Path(control_image_path)
    if not control_path.is_file():
        raise OpenAIImageError(f"结构控制图不存在：{control_path}")
    if target_id:
        try:
            target = current.visual_target(target_id)
        except ValueError as exc:
            raise OpenAIImageError(str(exc)) from exc
        request_hash = target.target_hash
        request_snapshot: Mapping[str, Any] = {
            "equipmentScene": snapshot.to_dict(),
            "generationTarget": target.to_dict(),
        }
        prompt = target.prompt
    else:
        request_hash = current.scene_hash
        request_snapshot = snapshot.to_dict()
        prompt = build_openai_equipment_prompt(current)
    return OpenAIImageRequest(
        scene_hash=request_hash,
        scene_snapshot=request_snapshot,
        prompt=prompt,
        control_image_path=control_path,
        output_root=Path(output_root),
        model=model,
        size=size,
        quality=quality,
        candidate_count=candidate_count,
    )


class OpenAIImageProvider:
    """Official OpenAI Python SDK adapter for Image Edit."""

    provider_name = "openai"
    display_name = "OpenAI API（单独计费）"
    requires_api_key = True
    supports_login = False

    def __init__(
        self,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._client_factory = client_factory

    def _client(self, api_key: str) -> Any:
        key = api_key.strip()
        if not key:
            raise OpenAIImageError(
                "未配置 OpenAI API Key。请粘贴密钥或设置 OPENAI_API_KEY。"
            )
        if self._client_factory is not None:
            return self._client_factory(api_key=key)
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise OpenAIImageError(
                "尚未安装官方 openai SDK，请先按 requirements.txt 安装依赖。"
            ) from exc
        return OpenAI(api_key=key)

    def test_connection(self, api_key: str) -> str:
        try:
            model = self._client(api_key).models.retrieve(DEFAULT_OPENAI_IMAGE_MODEL)
        except OpenAIImageError:
            raise
        except Exception as exc:
            raise OpenAIImageError(self._safe_provider_error(exc, api_key)) from exc
        return str(_field(model, "id") or DEFAULT_OPENAI_IMAGE_MODEL)

    def generate(
        self,
        request: OpenAIImageRequest,
        api_key: str,
    ) -> OpenAIImageBatch:
        if not request.control_image_path.is_file():
            raise OpenAIImageError(
                f"结构控制图不存在：{request.control_image_path}"
            )
        client = self._client(api_key)
        try:
            with request.control_image_path.open("rb") as control_image:
                response = client.images.edit(
                    model=request.model,
                    image=control_image,
                    prompt=request.prompt,
                    size=request.size,
                    quality=request.quality,
                    n=request.candidate_count,
                )
        except Exception as exc:
            raise OpenAIImageError(self._safe_provider_error(exc, api_key)) from exc

        response_data = list(_field(response, "data") or [])
        if len(response_data) != request.candidate_count:
            raise OpenAIImageError(
                "OpenAI 返回的候选图数量与请求不一致，结果未保存。"
            )

        created_at = datetime.now(timezone.utc).isoformat()
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output_dir = request.output_root / request.scene_hash / batch_id
        output_dir.mkdir(parents=True, exist_ok=False)
        candidates: list[OpenAIImageCandidate] = []
        try:
            for index, item in enumerate(response_data, start=1):
                encoded = str(_field(item, "b64_json") or "")
                if not encoded:
                    raise OpenAIImageError("OpenAI 未返回可保存的图片数据。")
                try:
                    image_bytes = base64.b64decode(encoded, validate=True)
                except ValueError as exc:
                    raise OpenAIImageError("OpenAI 返回的图片编码无效。") from exc
                if not image_bytes.startswith(PNG_SIGNATURE):
                    raise OpenAIImageError("OpenAI 返回的候选图不是有效 PNG。")
                image_path = output_dir / f"candidate_{index:02d}.png"
                _atomic_write_bytes(image_path, image_bytes)
                candidates.append(
                    OpenAIImageCandidate(
                        candidate_id=f"candidate-{index:02d}",
                        image_path=image_path,
                        sha256=hashlib.sha256(image_bytes).hexdigest(),
                        revised_prompt=str(_field(item, "revised_prompt") or ""),
                    )
                )

            manifest_path = output_dir / "generation.json"
            batch = OpenAIImageBatch(
                batch_id=batch_id,
                scene_hash=request.scene_hash,
                provider=self.provider_name,
                model=request.model,
                request_id=str(getattr(response, "_request_id", "") or ""),
                created_at=created_at,
                output_dir=output_dir,
                manifest_path=manifest_path,
                candidates=tuple(candidates),
            )
            manifest = {
                "schemaVersion": "openai-image-batch/v1",
                "request": request.to_manifest_dict(),
                "controlImageSha256": _sha256_file(request.control_image_path),
                "result": batch.to_dict(),
            }
            _atomic_write_text(
                manifest_path,
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
            return batch
        except Exception:
            # Keep any returned image files for diagnosis, but never write a success manifest.
            raise

    @staticmethod
    def _safe_provider_error(exc: Exception, api_key: str) -> str:
        message = str(exc).strip() or exc.__class__.__name__
        if api_key:
            message = message.replace(api_key, "***")
        lowered = message.lower()
        if "insufficient_quota" in lowered or "credit balance exhausted" in lowered:
            return (
                "OpenAI API 余额不足。ChatGPT/Codex 会员与 API 单独计费；"
                "如不希望充值，请切换到“Codex Pro（ChatGPT 登录）”。"
            )
        return "OpenAI 请求失败：" + message


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _atomic_write_text(path: Path, payload: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


__all__ = [
    "DEFAULT_OPENAI_IMAGE_MODEL",
    "DEFAULT_OPENAI_IMAGE_QUALITY",
    "DEFAULT_OPENAI_IMAGE_SIZE",
    "ImageProvider",
    "OPENAI_IMAGE_QUALITIES",
    "OPENAI_IMAGE_SIZES",
    "OpenAIImageBatch",
    "OpenAIImageCandidate",
    "OpenAIImageError",
    "OpenAIImageProvider",
    "OpenAIImageRequest",
    "build_openai_equipment_prompt",
    "prepare_openai_image_request",
]
