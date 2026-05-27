"""Safety audit for marketplace output artifacts."""

from __future__ import annotations

from pathlib import Path

from pulse50.engine.risk import BANNED_OUTPUT_TERMS


SCAN_PATHS = ("README.md", "examples")


def audit() -> list[str]:
    violations = []
    for root in SCAN_PATHS:
        path = Path(root)
        files = [path] if path.is_file() else list(path.rglob("*"))
        for file_path in files:
            if not file_path.is_file() or file_path.suffix.lower() in {".pyc", ".docx"}:
                continue
            text = file_path.read_text(encoding="utf-8", errors="ignore").lower()
            for term in BANNED_OUTPUT_TERMS:
                if term in text:
                    violations.append(f"{file_path}: banned term '{term}'")
    return violations


if __name__ == "__main__":
    findings = audit()
    if findings:
        raise SystemExit("\n".join(findings))
    print("Safety audit passed")
