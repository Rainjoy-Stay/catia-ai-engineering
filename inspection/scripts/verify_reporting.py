"""Verify bundled JSON-to-DOCX and image annotation dependencies offline."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation" / "reporting-self-check"
OUT.mkdir(parents=True, exist_ok=True)
sample = OUT / "sample.json"
image = OUT / "sample.jpg"
annotated = OUT / "sample_marked.jpg"
Image.new("RGB", (640, 360), "white").save(image)
payload = {
    "schema_version": "1.1.0", "run_id": "SELF-CHECK", "document": "SELF-CHECK.CATProduct",
    "counts": {"PASS": 0, "WARN": 1, "FAIL": 0, "NOT_EVALUATED": 0, "EXEMPTED": 0, "ERROR": 0},
    "source": {"cleanup_verified": True, "truncated": False, "source_saved_by_tool": False},
    "confidence_budget": {"checked": ["报告依赖"], "not_checked": [], "assumptions": [], "degraded": []},
    "findings": [{"issue_id": "SELF-CHECK-01", "status": "WARN", "severity": "S1",
                  "rule_id": "SELF", "title": "报告依赖自检", "message": "仅用于离线渲染验证",
                  "object_a": "A", "object_b": "B", "measured_value": None, "unit": None,
                  "recommendation": "无", "evidence": [{"kind": "SCREENSHOT", "path": str(annotated), "description": "红框自检"}]}],
    "audit": {"geometry_authority": "SELF-CHECK", "source_model_modified": False},
}
sample.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
commands = [
    [sys.executable, str(ROOT / "scripts" / "annotate_evidence.py"), str(image), "--output", str(annotated), "--box", "180,90,460,270", "--label", "SELF-CHECK-01"],
    [sys.executable, str(ROOT / "project" / "tools" / "generate_check_report.py"), str(sample), "--docx", str(OUT / "sample.docx")],
]
for command in commands:
    subprocess.run(command, cwd=ROOT, check=True)
for path in (annotated, OUT / "sample.docx"):
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"reporting self-check did not create {path}")
print(json.dumps({"status": "PASS", "docx": str(OUT / "sample.docx"), "annotated": str(annotated)}, ensure_ascii=False))
