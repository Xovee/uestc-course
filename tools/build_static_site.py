#!/usr/bin/env python
"""Build a small static index for browsing course resources."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote


COURSE_ROOT_NAME = "课程目录"
SITE_DATA_DIR = Path("site") / "data"
STANDARD_CATEGORIES = ("复习资料", "历年试题", "作业", "教材")
REPOSITORY_BLOB_ROOT = "https://github.com/Xovee/uestc-course/blob/main"
GITZIP_ROOT = "https://xovee.github.io/gitzip/?https://github.com/Xovee/uestc-course/tree/main"


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def build_site_index(repo_root: Path) -> dict[str, Any]:
    course_root = repo_root / COURSE_ROOT_NAME
    courses = []
    resources = []
    for course_dir in course_dirs(course_root):
        course_resources = []
        category_counts = {category: 0 for category in STANDARD_CATEGORIES}
        for category in STANDARD_CATEGORIES:
            category_dir = course_dir / category
            readme = category_dir / "README.md"
            if not readme.exists():
                continue
            rows = readme_file_rows(readme)
            file_candidates = local_resource_candidates(category_dir)
            for row in rows:
                resource = resource_from_row(repo_root, course_dir.name, category, category_dir, row, file_candidates)
                resources.append(resource)
                course_resources.append(resource)
                category_counts[category] += 1
        courses.append(
            {
                "name": course_dir.name,
                "path": relative_posix(course_dir, repo_root),
                "resource_count": len(course_resources),
                "category_counts": category_counts,
                "github_url": github_url(relative_posix(course_dir, repo_root)),
                "download_url": gitzip_url(relative_posix(course_dir, repo_root)),
            }
        )
    return {
        "schema_version": 1,
        "course_count": len(courses),
        "resource_count": len(resources),
        "categories": list(STANDARD_CATEGORIES),
        "courses": sorted(courses, key=lambda course: course["name"]),
        "resources": sorted(resources, key=resource_sort_key),
    }


def course_dirs(course_root: Path) -> list[Path]:
    if not course_root.exists():
        return []
    return sorted(
        path
        for path in course_root.iterdir()
        if path.is_dir() and not path.name.startswith("0-")
    )


def readme_file_rows(readme_path: Path) -> list[dict[str, str]]:
    lines = readme_path.read_text(encoding="utf-8-sig").splitlines()
    table = find_file_table(lines)
    if table is None:
        return []
    header_index, separator_index, headers = table
    rows: list[dict[str, str]] = []
    for line in lines[separator_index + 1 :]:
        if not line.strip() or "|" not in line:
            break
        cells = split_table_row(line)
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))
        rows.append({header: cells[index].strip() for index, header in enumerate(headers)})
    return rows


def find_file_table(lines: list[str]) -> tuple[int, int, list[str]] | None:
    for index, line in enumerate(lines[:-1]):
        headers = split_table_row(line)
        if not headers or "文件名" not in [header.strip() for header in headers]:
            continue
        if is_separator_row(lines[index + 1]):
            return index, index + 1, [header.strip() for header in headers]
    return None


def split_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def is_separator_row(line: str) -> bool:
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", cell.strip()) for cell in cells)


def local_resource_candidates(category_dir: Path) -> dict[str, Path]:
    candidates: dict[str, Path] = {}
    if not category_dir.exists():
        return candidates
    for child in category_dir.iterdir():
        if child.name.casefold() == "readme.md":
            continue
        keys = {child.name, child.stem if child.is_file() else child.name}
        for key in keys:
            candidates.setdefault(normalized_resource_key(key), child)
    return candidates


def resource_from_row(
    repo_root: Path,
    course: str,
    category: str,
    category_dir: Path,
    row: dict[str, str],
    file_candidates: dict[str, Path],
) -> dict[str, Any]:
    raw_name = row.get("文件名", "").strip()
    display_name, markdown_url = extract_markdown_link(raw_name)
    display_name = display_name or raw_name
    candidate = file_candidates.get(normalized_resource_key(display_name))
    path = relative_posix(candidate, repo_root) if candidate else ""
    source_text, source_url = extract_markdown_link(row.get("来源", ""))
    remark_text, remark_url = extract_markdown_link(row.get("备注", ""))
    url = markdown_url or source_url or remark_url or (github_url(path) if path else github_url(relative_posix(category_dir, repo_root)))
    return {
        "course": course,
        "category": category,
        "name": markdown_plain_text(display_name),
        "path": path,
        "url": url,
        "is_local": bool(path),
        "source": markdown_plain_text(source_text or row.get("来源", "")),
        "author": markdown_plain_text(row.get("作者", "")),
        "file_type": markdown_plain_text(row.get("文件类型", "")),
        "file_size": markdown_plain_text(row.get("文件大小", "")),
        "updated_at": markdown_plain_text(row.get("最近更新时间", "")),
        "remark": markdown_plain_text(remark_text or row.get("备注", "")),
    }


def extract_markdown_link(value: str) -> tuple[str, str]:
    match = re.search(r"\[([^\]]+)\]\(([^)]+)\)", value)
    if not match:
        return value.strip(), ""
    return match.group(1).strip(), match.group(2).strip()


def markdown_plain_text(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", value)
    value = value.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    value = value.replace("|", "/")
    return " ".join(value.split())


def normalized_resource_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).casefold()


def resource_sort_key(resource: dict[str, Any]) -> tuple[str, int, str]:
    category_rank = {category: index for index, category in enumerate(STANDARD_CATEGORIES)}
    return (resource["course"], category_rank.get(resource["category"], 99), resource["name"])


def relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def github_url(path: str) -> str:
    return f"{REPOSITORY_BLOB_ROOT}/{quote(path, safe='/()[]-_.~')}"


def gitzip_url(path: str) -> str:
    return f"{GITZIP_ROOT}/{quote(path, safe='/()[]-_.~')}"


def write_site_index(repo_root: Path, output: Path) -> dict[str, Any]:
    index = build_site_index(repo_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repo_root_from_script())
    parser.add_argument("--output", type=Path, default=repo_root_from_script() / SITE_DATA_DIR / "resources.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    index = write_site_index(args.root.resolve(), args.output)
    print(f"Built {index['course_count']} courses and {index['resource_count']} resources at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
