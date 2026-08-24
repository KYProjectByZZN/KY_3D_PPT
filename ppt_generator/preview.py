"""UI-independent current-page preview service."""

from __future__ import annotations

import json
import hashlib
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .module_service import rebuild_structure_context
from .project import PptProject
from .template_renderer import load_manifest, render_project_page


class PreviewError(RuntimeError):
    """Raised when a current-page preview cannot be produced."""


ProcessCallback = Callable[[subprocess.Popen[str] | None], None]
CancelCheck = Callable[[], bool]
OfficeExporter = Callable[[Path, int, Path], str]
ProjectRenderer = Callable[..., Path]


def _preview_context(
    project: PptProject,
    module_id: str,
    slide_id: str,
) -> Any:
    module = next((item for item in project.modules if item.id == module_id), None)
    if module is None:
        raise PreviewError("所选模块已不存在")
    if not any(item.id == slide_id for item in module.slides):
        raise PreviewError("所选页面已不存在")
    if not module.enabled:
        raise PreviewError("当前模块未启用，不属于最终 PPT；启用模块后可预览")
    manifest = load_manifest(project.manifest_path)
    context = next(
        (
            item
            for item in rebuild_structure_context(project, manifest)
            if item.module_id == module_id and item.slide_id == slide_id
        ),
        None,
    )
    if context is None:
        raise PreviewError("无法在最终 PPT 结构中定位当前页面")
    return context


def physical_slide_number(
    project: PptProject,
    module_id: str,
    slide_id: str,
) -> int:
    """Return the selected project's final, one-based physical page number."""
    return int(_preview_context(project, module_id, slide_id).physical_page_number)


def _value_file_stamps(value: Any) -> list[tuple[str, int, int]]:
    stamps: list[tuple[str, int, int]] = []
    if isinstance(value, dict):
        for item in value.values():
            stamps.extend(_value_file_stamps(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            stamps.extend(_value_file_stamps(item))
    elif isinstance(value, str):
        path = Path(value)
        try:
            if path.is_file():
                stat = path.stat()
                stamps.append((str(path.resolve()), stat.st_size, stat.st_mtime_ns))
        except OSError:
            pass
    return stamps


def preview_fingerprint(
    project: PptProject,
    module_id: str,
    slide_id: str,
) -> str:
    """Return a stable cache key for the selected page's resolved content."""
    context = _preview_context(project, module_id, slide_id)
    payload = {
        "template": str(Path(project.template_path).resolve()),
        "manifest": str(Path(project.manifest_path).resolve()),
        "module_id": module_id,
        "slide_id": slide_id,
        "source_slide": context.source_slide,
        "physical_page_number": context.physical_page_number,
        "physical_total_pages": context.physical_total_pages,
        "presentation_style": project.presentation_style.to_dict(),
        "values": context.values,
        "system_slots": context.system_slots,
        "file_stamps": _value_file_stamps(context.values),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def preview_source_slide(
    project: PptProject,
    module_id: str,
    slide_id: str,
) -> int:
    """Return the source template page for a selected project page."""
    return int(_preview_context(project, module_id, slide_id).source_slide)


def template_thumbnail_directory(
    project: PptProject,
    cache_root: str | Path,
) -> Path:
    manifest = load_manifest(project.manifest_path)
    return Path(cache_root).expanduser().resolve() / manifest.template_sha256.lower()


def template_thumbnail_path(
    project: PptProject,
    cache_root: str | Path,
    source_slide: int,
) -> Path:
    return template_thumbnail_directory(project, cache_root) / f"slide_{source_slide:04d}.png"


def _valid_png(path: Path) -> bool:
    try:
        return path.is_file() and path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    except OSError:
        return False


class OfficePreviewSession:
    """Client for one timeout-limited, reusable Office preview process."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 35.0,
        helper_path: str | Path | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.helper_path = (
            Path(helper_path).resolve()
            if helper_path
            else Path(__file__).with_name("office_preview_server.py")
        )
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[str | None] | None = None
        self.backend = ""

    @property
    def process_id(self) -> int | None:
        process = self._process
        return process.pid if process is not None and process.poll() is None else None

    def _read_responses(
        self,
        stream: Any,
        responses: queue.Queue[str | None],
    ) -> None:
        try:
            for line in stream:
                responses.put(line)
        finally:
            responses.put(None)

    def _wait_response_locked(
        self,
        deadline: float,
        cancelled: CancelCheck | None,
    ) -> dict[str, Any]:
        assert self._responses is not None
        while True:
            if cancelled and cancelled():
                self._terminate_locked()
                raise PreviewError("预览任务已取消")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._terminate_locked()
                raise PreviewError(
                    "Office 预览超时；请先手动启动 PowerPoint/WPS 完成首次设置后再刷新"
                )
            try:
                line = self._responses.get(timeout=min(0.1, remaining))
            except queue.Empty:
                continue
            if line is None:
                process = self._process
                message = "Office 预览进程意外结束"
                if process is not None and process.stderr is not None:
                    error = process.stderr.read().strip()
                    if error:
                        message += f"：{error}"
                self._terminate_locked()
                raise PreviewError(message)
            try:
                return json.loads(line)
            except json.JSONDecodeError as exc:
                self._terminate_locked()
                raise PreviewError("Office 预览后端返回了无效结果") from exc

    def _start_locked(
        self,
        deadline: float,
        cancelled: CancelCheck | None,
    ) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        responses: queue.Queue[str | None] = queue.Queue()
        process = subprocess.Popen(
            [sys.executable, str(self.helper_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._process = process
        self._responses = responses
        assert process.stdout is not None
        threading.Thread(
            target=self._read_responses,
            args=(process.stdout, responses),
            daemon=True,
        ).start()
        response = self._wait_response_locked(deadline, cancelled)
        if not response.get("ok"):
            message = str(response.get("error") or "Office 后端不可用")
            self._terminate_locked()
            raise PreviewError(f"当前页导出失败：{message}")
        self.backend = str(response.get("backend") or "Office")

    def export(
        self,
        pptx_path: Path,
        slide_number: int,
        output_path: Path,
        *,
        timeout_seconds: float | None = None,
        cancelled: CancelCheck | None = None,
    ) -> str:
        timeout = timeout_seconds or self.timeout_seconds
        deadline = time.monotonic() + timeout
        with self._lock:
            self._start_locked(deadline, cancelled)
            process = self._process
            if process is None or process.stdin is None:
                raise PreviewError("Office 预览进程未启动")
            request = {
                "command": "export",
                "input": str(pptx_path),
                "slide": slide_number,
                "output": str(output_path),
            }
            try:
                process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
                process.stdin.flush()
            except OSError as exc:
                self._terminate_locked()
                raise PreviewError("Office 预览进程通信失败") from exc
            response = self._wait_response_locked(deadline, cancelled)
            if not response.get("ok"):
                raise PreviewError(
                    "当前页导出失败："
                    + str(response.get("error") or "Office 后端不可用")
                )
            self.backend = str(response.get("backend") or self.backend or "Office")
            return self.backend

    def cancel_current(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    def _terminate_locked(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
        if process is not None:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
        self._process = None
        self._responses = None
        self.backend = ""

    def close(self) -> None:
        with self._lock:
            process = self._process
            if process is not None and process.poll() is None and process.stdin is not None:
                try:
                    process.stdin.write('{"command":"shutdown"}\n')
                    process.stdin.flush()
                    process.wait(timeout=3)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            self._terminate_locked()


def ensure_template_thumbnail(
    project: PptProject,
    cache_root: str | Path,
    source_slide: int,
    office_session: OfficePreviewSession,
    *,
    cancelled: CancelCheck | None = None,
) -> tuple[Path, str, bool]:
    """Return one persistent source-template thumbnail, creating it on demand."""
    manifest = load_manifest(project.manifest_path)
    if not 1 <= source_slide <= manifest.slide_count:
        raise PreviewError(
            f"模板页码超出范围：{source_slide}，模板共 {manifest.slide_count} 页"
        )
    destination = template_thumbnail_path(project, cache_root, source_slide)
    if _valid_png(destination):
        return destination, "持久缓存", True

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="kyppt_template_thumbnail_",
        dir=destination.parent,
    ) as temp_dir:
        temporary_directory = Path(temp_dir)
        temporary_template = temporary_directory / "template.pptx"
        temporary = temporary_directory / "slide.png"
        shutil.copy2(
            Path(project.template_path).expanduser().resolve(),
            temporary_template,
        )
        backend = office_session.export(
            temporary_template,
            source_slide,
            temporary,
            cancelled=cancelled,
        )
        if not _valid_png(temporary):
            raise PreviewError(f"模板第 {source_slide} 页缩略图无效")
        temporary.replace(destination)
    return destination, backend, False


def export_slide_with_office(
    pptx_path: Path,
    slide_number: int,
    output_path: Path,
    *,
    timeout_seconds: float = 35.0,
    process_callback: ProcessCallback | None = None,
    cancelled: CancelCheck | None = None,
) -> str:
    """Run the Office COM exporter in a limited child process."""
    helper = Path(__file__).with_name("office_preview.py")
    command = [
        sys.executable,
        str(helper),
        "--input",
        str(pptx_path),
        "--slide",
        str(slide_number),
        "--output",
        str(output_path),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if process_callback:
        process_callback(process)
    deadline = time.monotonic() + timeout_seconds
    try:
        while process.poll() is None:
            if cancelled and cancelled():
                process.terminate()
                raise PreviewError("预览任务已取消")
            if time.monotonic() >= deadline:
                process.terminate()
                raise PreviewError(
                    "Office 预览超时；请先手动启动 PowerPoint/WPS 完成首次设置后再刷新"
                )
            time.sleep(0.1)
        stdout, stderr = process.communicate()
    finally:
        if process_callback:
            process_callback(None)

    if process.returncode != 0:
        message = (stderr or stdout or "Office 后端不可用").strip()
        raise PreviewError(f"当前页导出失败：{message}")
    try:
        result = json.loads(stdout.strip().splitlines()[-1])
        return str(result["backend"])
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise PreviewError("Office 预览后端返回了无效结果") from exc


def render_page_preview(
    project: PptProject,
    module_id: str,
    slide_id: str,
    output_path: str | Path,
    *,
    exporter: OfficeExporter | None = None,
    renderer: ProjectRenderer | None = None,
    office_session: OfficePreviewSession | None = None,
    timeout_seconds: float = 35.0,
    process_callback: ProcessCallback | None = None,
    cancelled: CancelCheck | None = None,
) -> tuple[Path, str, int]:
    """Render the project and export its selected final slide to a PNG."""
    snapshot = PptProject.from_dict(project.to_dict())
    page_number = physical_slide_number(snapshot, module_id, slide_id)
    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.lower() != ".png":
        raise PreviewError("预览输出文件必须使用 .png 扩展名")
    destination.parent.mkdir(parents=True, exist_ok=True)
    render = renderer or render_project_page

    with tempfile.TemporaryDirectory(prefix="kyppt_preview_") as temp_dir:
        temp_pptx = Path(temp_dir) / "current_project.pptx"
        render(snapshot, module_id, slide_id, temp_pptx, overwrite=True)
        if cancelled and cancelled():
            raise PreviewError("预览任务已取消")
        if exporter:
            backend = exporter(temp_pptx, 1, destination)
        elif office_session:
            backend = office_session.export(
                temp_pptx,
                1,
                destination,
                timeout_seconds=timeout_seconds,
                cancelled=cancelled,
            )
        else:
            backend = export_slide_with_office(
                temp_pptx,
                1,
                destination,
                timeout_seconds=timeout_seconds,
                process_callback=process_callback,
                cancelled=cancelled,
            )

    if not destination.is_file() or not destination.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        raise PreviewError("预览后端没有生成有效的 PNG 图片")
    return destination, backend, page_number
