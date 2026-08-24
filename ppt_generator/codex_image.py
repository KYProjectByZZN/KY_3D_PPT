"""Codex ChatGPT-subscription adapter for no-CAD equipment images."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from .openai_image import (
    PNG_SIGNATURE,
    OpenAIImageBatch,
    OpenAIImageCandidate,
    OpenAIImageError,
    OpenAIImageRequest,
)


DEFAULT_CODEX_AGENT_MODEL = "gpt-5.6-sol"
CODEX_PROVIDER_NAME = "codex-pro"


class CodexImageError(OpenAIImageError):
    """Raised when Codex login, execution, or image output is invalid."""


@dataclass(frozen=True)
class CodexAccountStatus:
    signed_in: bool
    auth_mode: str
    summary: str
    raw_output: str = ""


@dataclass(frozen=True)
class CodexCommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


CodexCommandRunner = Callable[
    [Sequence[str], Path | None, str, int], CodexCommandResult
]


class CodexImageProvider:
    """Run an isolated local Codex image task with ChatGPT authentication."""

    provider_name = CODEX_PROVIDER_NAME
    display_name = "Codex Pro（ChatGPT 登录）"
    requires_api_key = False
    supports_login = True

    def __init__(
        self,
        *,
        codex_bin: str | Path | None = None,
        command_runner: CodexCommandRunner | None = None,
        agent_model: str = DEFAULT_CODEX_AGENT_MODEL,
        execution_timeout_seconds: int = 900,
    ) -> None:
        self._configured_codex_bin = str(codex_bin or "").strip()
        self._command_runner = command_runner or self._run_subprocess
        self.agent_model = agent_model.strip() or DEFAULT_CODEX_AGENT_MODEL
        self.execution_timeout_seconds = execution_timeout_seconds

    def account_status(self) -> CodexAccountStatus:
        result = self._run(("login", "status"), timeout_seconds=30)
        raw = "\n".join(
            value.strip() for value in (result.stdout, result.stderr) if value.strip()
        )
        lowered = raw.lower()
        if result.returncode == 0 and "chatgpt" in lowered and "logged in" in lowered:
            return CodexAccountStatus(
                signed_in=True,
                auth_mode="chatgpt",
                summary="Codex 已通过 ChatGPT 登录，可使用会员套餐额度。",
                raw_output=raw,
            )
        if result.returncode == 0 and "api" in lowered and "logged in" in lowered:
            return CodexAccountStatus(
                signed_in=True,
                auth_mode="api-key",
                summary=(
                    "Codex 当前使用 API Key 登录。请重新使用 ChatGPT 登录，"
                    "才能走会员套餐额度。"
                ),
                raw_output=raw,
            )
        return CodexAccountStatus(
            signed_in=False,
            auth_mode="none",
            summary="Codex 尚未登录。请点击“登录 Codex”并在浏览器完成 ChatGPT 登录。",
            raw_output=raw,
        )

    def login(self) -> str:
        status = self.account_status()
        if status.signed_in and status.auth_mode == "chatgpt":
            return status.summary
        result = self._run(("login",), timeout_seconds=600)
        if result.returncode != 0:
            raise CodexImageError(self._command_error(result, action="登录 Codex"))
        status = self.account_status()
        if not status.signed_in or status.auth_mode != "chatgpt":
            raise CodexImageError(status.summary)
        return status.summary

    def test_connection(self, api_key: str = "") -> str:
        del api_key
        status = self.account_status()
        if not status.signed_in or status.auth_mode != "chatgpt":
            raise CodexImageError(status.summary)
        return f"{status.summary} 代理模型：{self.agent_model}"

    def generate(
        self,
        request: OpenAIImageRequest,
        api_key: str = "",
    ) -> OpenAIImageBatch:
        del api_key
        self.test_connection()
        if not request.control_image_path.is_file():
            raise CodexImageError(f"结构控制图不存在：{request.control_image_path}")

        created_at = datetime.now(timezone.utc).isoformat()
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output_dir = request.output_root / request.scene_hash / batch_id
        output_dir.mkdir(parents=True, exist_ok=False)
        control_path = output_dir / "structure_control.png"
        _atomic_write_bytes(control_path, request.control_image_path.read_bytes())

        expected_paths = tuple(
            output_dir / f"candidate_{index:02d}.png"
            for index in range(1, request.candidate_count + 1)
        )
        prompt = self._build_codex_prompt(request, expected_paths)
        result = self._run(
            (
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                "workspace-write",
                "--model",
                self.agent_model,
                "-c",
                'forced_login_method="chatgpt"',
                "--color",
                "never",
                "--json",
                "--image",
                str(control_path),
                "-",
            ),
            cwd=output_dir,
            stdin_text=prompt,
            timeout_seconds=self.execution_timeout_seconds,
        )
        if result.returncode != 0:
            raise CodexImageError(self._command_error(result, action="Codex 生成图片"))

        payloads = _extract_png_payloads(result.stdout)
        candidate_paths = self._collect_candidate_files(
            output_dir,
            control_path,
            expected_paths,
            payloads,
        )
        if len(candidate_paths) != request.candidate_count:
            details = _last_nonempty_text(result.stdout, result.stderr)
            suffix = f"\nCodex 返回：{details}" if details else ""
            raise CodexImageError(
                "Codex 已完成任务，但没有返回要求数量的 PNG 候选图。"
                "请确认当前账号可使用 ImageGen 后重试。" + suffix
            )

        candidates = tuple(
            OpenAIImageCandidate(
                candidate_id=f"candidate-{index:02d}",
                image_path=path,
                sha256=_sha256_file(path),
            )
            for index, path in enumerate(candidate_paths, start=1)
        )
        manifest_path = output_dir / "generation.json"
        batch = OpenAIImageBatch(
            batch_id=batch_id,
            scene_hash=request.scene_hash,
            provider=self.provider_name,
            model=f"{self.agent_model}+imagegen",
            request_id=_extract_execution_id(result.stdout),
            created_at=created_at,
            output_dir=output_dir,
            manifest_path=manifest_path,
            candidates=candidates,
        )
        manifest = {
            "schemaVersion": "codex-image-batch/v1",
            "request": request.to_manifest_dict(),
            "controlImageSha256": _sha256_file(control_path),
            "codex": {
                "authMode": "chatgpt",
                "agentModel": self.agent_model,
                "sandbox": "workspace-write",
                "ephemeral": True,
            },
            "result": batch.to_dict(),
        }
        _atomic_write_text(
            manifest_path,
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
        return batch

    def _collect_candidate_files(
        self,
        output_dir: Path,
        control_path: Path,
        expected_paths: Sequence[Path],
        payloads: Sequence[bytes],
    ) -> tuple[Path, ...]:
        file_payloads: list[bytes] = []
        seen_payload_hashes: set[str] = set()

        def read_png(path: Path) -> bytes:
            payload = path.read_bytes()
            if not payload.startswith(PNG_SIGNATURE):
                raise CodexImageError(f"Codex 返回的候选图不是有效 PNG：{path.name}")
            return payload

        for path in expected_paths:
            if path.is_file():
                file_payloads.append(read_png(path))

        other_paths = sorted(
            path
            for path in output_dir.rglob("*.png")
            if path.resolve() != control_path.resolve()
            and path not in expected_paths
        )
        for path in other_paths:
            if len(file_payloads) >= len(expected_paths):
                break
            file_payloads.append(read_png(path))

        seen_payload_hashes.update(
            hashlib.sha256(payload).hexdigest() for payload in file_payloads
        )
        for payload in payloads:
            if len(file_payloads) >= len(expected_paths):
                break
            digest = hashlib.sha256(payload).hexdigest()
            if digest not in seen_payload_hashes:
                seen_payload_hashes.add(digest)
                file_payloads.append(payload)

        if len(file_payloads) < len(expected_paths):
            return ()
        for path, payload in zip(expected_paths, file_payloads, strict=True):
            _atomic_write_bytes(path, payload)
        return tuple(expected_paths)

    def _build_codex_prompt(
        self,
        request: OpenAIImageRequest,
        expected_paths: Sequence[Path],
    ) -> str:
        output_lines = "\n".join(
            f"- 候选 {index}: {path.name}"
            for index, path in enumerate(expected_paths, start=1)
        )
        return (
            "这是一个由本地桌面软件发起的受限图片生成任务。\n"
            "必须使用已安装的 imagegen 技能，并把附加的 structure_control.png "
            "作为不可变的工程逻辑参考图。\n"
            f"请生成恰好 {request.candidate_count} 张 PNG 候选图，目标尺寸 "
            f"{request.size}，质量 {request.quality}。\n"
            "只允许在当前工作目录中创建图片；不要修改、删除或读取其它目录中的文件。\n"
            "每张图必须保持相同模块数量、顺序、产品流向、检测和剔除关系。\n"
            "请把最终图片保存为以下文件名：\n"
            f"{output_lines}\n"
            "如果 imagegen 工具不能保存到指定名称，也必须在工具结果中返回完整 PNG。\n"
            "不要用程序绘制、占位图、SVG截图或复制控制图冒充生成结果。\n\n"
            "图片生成提示词：\n"
            f"{request.prompt.strip()}\n"
        )

    def _run(
        self,
        arguments: Sequence[str],
        *,
        cwd: Path | None = None,
        stdin_text: str = "",
        timeout_seconds: int,
    ) -> CodexCommandResult:
        executable = self._resolve_codex_bin()
        try:
            return self._command_runner(
                (executable, *arguments),
                cwd,
                stdin_text,
                timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise CodexImageError(
                "未检测到 Codex 本地运行时。请先安装或更新 ChatGPT/Codex。"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise CodexImageError(
                f"Codex 任务超过 {timeout_seconds} 秒仍未完成，请稍后重试。"
            ) from exc
        except OSError as exc:
            raise CodexImageError(f"无法启动 Codex 本地运行时：{exc}") from exc

    def _resolve_codex_bin(self) -> str:
        if self._configured_codex_bin:
            return self._configured_codex_bin
        candidates = ("codex.cmd", "codex.exe", "codex") if os.name == "nt" else ("codex",)
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        raise CodexImageError(
            "未检测到 Codex 本地运行时。请先安装或更新 ChatGPT/Codex。"
        )

    @staticmethod
    def _run_subprocess(
        command: Sequence[str],
        cwd: Path | None,
        stdin_text: str,
        timeout_seconds: int,
    ) -> CodexCommandResult:
        environment = os.environ.copy()
        environment.pop("OPENAI_API_KEY", None)
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(
            list(command),
            cwd=str(cwd) if cwd else None,
            input=stdin_text or None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=environment,
            creationflags=creation_flags,
            check=False,
        )
        return CodexCommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )

    @staticmethod
    def _command_error(result: CodexCommandResult, *, action: str) -> str:
        details = _last_nonempty_text(result.stdout, result.stderr)
        lowered = details.lower()
        if "not logged in" in lowered or "unauthorized" in lowered:
            return "Codex 尚未通过 ChatGPT 登录，请先点击“登录 Codex”。"
        if any(
            marker in lowered
            for marker in (
                "usage limit",
                "rate limit",
                "credit limit",
                "credits depleted",
                "reached your limit",
            )
        ):
            return "Codex 会员使用额度当前已达上限，请等待额度恢复后重试。"
        if "insufficient_quota" in lowered or "credit balance exhausted" in lowered:
            return (
                "Codex 当前仍在使用 API Key 计费路径。请重新用 ChatGPT 登录，"
                "不要在此模式下充值 API。"
            )
        suffix = f"：{details}" if details else "。"
        return f"{action}失败{suffix}"


def _extract_png_payloads(jsonl_text: str) -> tuple[bytes, ...]:
    payloads: list[bytes] = []
    seen: set[str] = set()

    def add_encoded(encoded: str) -> None:
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            return
        if not payload.startswith(PNG_SIGNATURE):
            return
        digest = hashlib.sha256(payload).hexdigest()
        if digest not in seen:
            seen.add(digest)
            payloads.append(payload)

    def walk(value: Any, key: str = "") -> None:
        if isinstance(value, Mapping):
            for child_key, child in value.items():
                walk(child, str(child_key))
            return
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            for child in value:
                walk(child, key)
            return
        if not isinstance(value, str):
            return
        if value.startswith("data:image/png;base64,"):
            add_encoded(value.split(",", 1)[1])
        elif key.lower() in {"b64_json", "base64", "image_base64"}:
            add_encoded(value)

    for line in jsonl_text.splitlines():
        try:
            walk(json.loads(line))
        except json.JSONDecodeError:
            continue
    return tuple(payloads)


def _extract_execution_id(jsonl_text: str) -> str:
    preferred_keys = {"thread_id", "threadid", "session_id", "sessionid", "conversation_id"}
    found = ""

    def walk(value: Any) -> None:
        nonlocal found
        if found:
            return
        if isinstance(value, Mapping):
            for key, child in value.items():
                if str(key).lower() in preferred_keys and isinstance(child, str):
                    found = child
                    return
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for line in jsonl_text.splitlines():
        try:
            walk(json.loads(line))
        except json.JSONDecodeError:
            continue
        if found:
            break
    return found


def _last_nonempty_text(*values: str, limit: int = 1200) -> str:
    lines: list[str] = []
    for value in values:
        for line in value.splitlines():
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
    if not lines:
        return ""
    text = lines[-1]
    try:
        parsed = json.loads(text)
        text = str(
            parsed.get("message")
            or parsed.get("error")
            or parsed.get("text")
            or text
        )
    except (json.JSONDecodeError, AttributeError):
        pass
    return text[-limit:]


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
    "CODEX_PROVIDER_NAME",
    "DEFAULT_CODEX_AGENT_MODEL",
    "CodexAccountStatus",
    "CodexCommandResult",
    "CodexImageError",
    "CodexImageProvider",
]
