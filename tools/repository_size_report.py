#!/usr/bin/env python
"""Report tracked repository size and large resource candidates."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Callable


ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}
DEFAULT_LIMIT = 20
DEFAULT_THRESHOLD_MB = 50.0


@dataclass(frozen=True)
class FileRecord:
    path: str
    size_bytes: int


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def collect_tracked_files(root: Path) -> list[FileRecord]:
    root = root.resolve()
    from_git = collect_tracked_files_from_git(root)
    if from_git is not None:
        return from_git
    return collect_files_from_filesystem(root)


def collect_tracked_files_from_git(root: Path) -> list[FileRecord] | None:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return None
    records: list[FileRecord] = []
    for raw_path in result.stdout.decode("utf-8", errors="surrogateescape").split("\0"):
        if not raw_path:
            continue
        path = root / raw_path
        if path.is_file():
            records.append(FileRecord(normalize_relative_path(Path(raw_path)), path.stat().st_size))
    return records


def collect_files_from_filesystem(root: Path) -> list[FileRecord]:
    records: list[FileRecord] = []
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.relative_to(root).parts:
            continue
        relative = path.relative_to(root)
        records.append(FileRecord(normalize_relative_path(relative), path.stat().st_size))
    return records


def normalize_relative_path(path: Path) -> str:
    return path.as_posix()


def build_report(records: list[FileRecord], *, limit: int, threshold_bytes: int) -> dict[str, object]:
    sorted_records = sorted(records, key=lambda record: (-record.size_bytes, record.path))
    return {
        "total_files": len(records),
        "total_size_bytes": sum(record.size_bytes for record in records),
        "largest_files": records_to_dicts(sorted_records[:limit]),
        "large_files": records_to_dicts(
            [record for record in sorted_records if record.size_bytes >= threshold_bytes]
        ),
        "exam_archives": records_to_dicts(find_exam_archives(sorted_records)),
        "by_extension": aggregate(records, extension_key),
        "by_top_level": aggregate(records, top_level_key),
    }


def records_to_dicts(records: list[FileRecord]) -> list[dict[str, object]]:
    return [record_with_human_size(record) for record in records]


def record_with_human_size(record: FileRecord) -> dict[str, object]:
    data = asdict(record)
    data["size"] = human_size(record.size_bytes)
    return data


def find_exam_archives(records: list[FileRecord]) -> list[FileRecord]:
    archives: list[FileRecord] = []
    for record in records:
        path = PurePosixPath(record.path)
        if path.suffix.casefold() not in ARCHIVE_EXTENSIONS:
            continue
        parts = path.parts
        if len(parts) >= 4 and parts[0] == "课程目录" and "历年试题" in parts:
            archives.append(record)
    return archives


def aggregate(records: list[FileRecord], key_func: Callable[[FileRecord], str]) -> list[dict[str, object]]:
    buckets: dict[str, dict[str, object]] = {}
    for record in records:
        key = key_func(record)
        bucket = buckets.setdefault(key, {"name": key, "files": 0, "size_bytes": 0})
        bucket["files"] = int(bucket["files"]) + 1
        bucket["size_bytes"] = int(bucket["size_bytes"]) + record.size_bytes
    rows = sorted(buckets.values(), key=lambda row: (-int(row["size_bytes"]), str(row["name"])))
    for row in rows:
        row["size"] = human_size(int(row["size_bytes"]))
    return rows


def extension_key(record: FileRecord) -> str:
    suffix = PurePosixPath(record.path).suffix.casefold()
    return suffix or "[no extension]"


def top_level_key(record: FileRecord) -> str:
    parts = PurePosixPath(record.path).parts
    return parts[0] if parts else "."


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def format_report(report: dict[str, object], *, limit: int, threshold_mb: float) -> str:
    lines = [
        "# Repository Size Report",
        "",
        f"Tracked files: {report['total_files']}",
        f"Tracked size: {human_size(int(report['total_size_bytes']))}",
        "",
    ]
    add_file_section(lines, f"Largest files (top {limit})", report["largest_files"])
    add_file_section(lines, f"Files at least {threshold_mb:g} MB", report["large_files"])
    add_file_section(lines, "Exam archives", report["exam_archives"])
    add_aggregate_section(lines, "By extension", report["by_extension"])
    add_aggregate_section(lines, "By top-level directory", report["by_top_level"])
    return "\n".join(lines).rstrip() + "\n"


def add_file_section(lines: list[str], title: str, rows: object) -> None:
    lines.append(f"## {title}")
    rows = list(rows) if isinstance(rows, list) else []
    if not rows:
        lines.append("(none)")
        lines.append("")
        return
    for index, row in enumerate(rows, start=1):
        lines.append(f"{index}. {row['size']}  {row['path']}")
    lines.append("")


def add_aggregate_section(lines: list[str], title: str, rows: object) -> None:
    lines.append(f"## {title}")
    rows = list(rows) if isinstance(rows, list) else []
    if not rows:
        lines.append("(none)")
        lines.append("")
        return
    for row in rows:
        lines.append(f"- {row['name']}: {row['files']} files, {row['size']}")
    lines.append("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repo_root_from_script())
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--threshold-mb", type=float, default=DEFAULT_THRESHOLD_MB)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    threshold_bytes = int(args.threshold_mb * 1024 * 1024)
    records = collect_tracked_files(args.root)
    report = build_report(records, limit=max(args.limit, 0), threshold_bytes=threshold_bytes)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_report(report, limit=max(args.limit, 0), threshold_mb=args.threshold_mb), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
