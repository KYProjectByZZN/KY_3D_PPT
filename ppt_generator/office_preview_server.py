"""Persistent JSON-lines server for repeated PowerPoint/WPS preview exports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from office_preview import OfficeApplicationSession


def _respond(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def main() -> int:
    session = OfficeApplicationSession()
    try:
        try:
            backend = session.start()
        except Exception as exc:
            _respond({"event": "ready", "ok": False, "error": str(exc)})
            return 1
        _respond({"event": "ready", "ok": True, "backend": backend})

        for line in sys.stdin:
            try:
                request = json.loads(line)
                if request.get("command") == "shutdown":
                    _respond({"event": "shutdown", "ok": True})
                    return 0
                input_path = Path(str(request["input"])).resolve()
                output_path = Path(str(request["output"])).resolve()
                slide_number = int(request["slide"])
                backend = session.export(input_path, slide_number, output_path)
                _respond(
                    {
                        "event": "export",
                        "ok": True,
                        "backend": backend,
                    }
                )
            except Exception as exc:
                _respond({"event": "export", "ok": False, "error": str(exc)})
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
