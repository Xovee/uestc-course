#!/usr/bin/env python
"""Ingest local course resources into the UESTC Course repository.

The CLI intentionally has two phases:

1. scan: inspect an incoming directory and emit a JSON plan.
2. apply: apply a human-reviewed JSON plan to the repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree


COURSE_ROOT_NAME = "课程目录"
DEFAULT_INCOMING = "_incoming"

CATEGORY_REVIEW = "复习资料"
CATEGORY_EXAMS = "历年试题"
CATEGORY_ASSIGNMENTS = "作业"

EXAM_KEYWORDS = ("考试", "试题", "真题", "期中", "期末", "考题", "试卷", "A卷", "B卷")
ASSIGNMENT_KEYWORDS = ("作业", "实验", "报告", "随堂测试", "课堂测试", "练习")
REVIEW_HINT_KEYWORDS = ("复习", "总结", "知识汇总", "练手")
STRONG_EXAM_EVIDENCE_KEYWORDS = ("试题", "真题", "试卷", "A卷", "B卷", "回忆版")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
WORD_EXTENSIONS = {".doc", ".docx"}
PPT_EXTENSIONS = {".ppt", ".pptx"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".tsv"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
TEXT_SCAN_EXTENSIONS = {".txt", ".md", ".csv", ".tsv"}
DOCX_EXTENSION = ".docx"

PRIVACY_PATTERNS = {
    "phone_number": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "id_card_number": re.compile(
        r"(?<!\d)[1-9]\d{5}(?:18|19|20)\d{2}"
        r"(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"
    ),
    "email_address": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}
PRIVACY_KEYWORDS = (
    "姓名",
    "学号",
    "身份证",
    "手机号",
    "电话号码",
    "联系电话",
    "家庭住址",
    "住址",
    "宿舍",
    "银行卡",
    "微信号",
    "微信",
    "QQ号",
)
PROHIBITED_KEYWORDS = (
    "涉密",
    "机密",
    "绝密",
    "不得外传",
    "内部资料",
    "色情",
    "赌博",
    "毒品",
    "枪支",
    "邪教",
    "恐怖",
    "凶杀",
    "反动",
    "诈骗",
    "代考",
    "买答案",
    "作弊",
    "论文代写",
)
SUBJECTIVE_KEYWORDS = ("老师很", "老师太", "给分", "挂科率", "水课", "避雷", "垃圾课", "坑人", "好过", "差评", "老师人品")
COPYRIGHT_KEYWORDS = ("教材扫描版", "电子书完整版", "影印版", "盗版", "课件全集", "教师课件")
MAX_TEXT_CHARS_PER_FILE = 200_000
MAX_FOLDER_SCREEN_FILES = 30


@dataclass(frozen=True)
class CourseMatch:
    course: str | None
    candidates: list[str]
    warnings: list[str]


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize_for_match(value: str) -> str:
    return re.sub(r"[\s_\-—–·,，.。()（）\[\]【】]+", "", value.casefold())


def list_courses(repo_root: Path) -> list[str]:
    course_root = repo_root / COURSE_ROOT_NAME
    if not course_root.exists():
        return []
    return sorted(
        path.name
        for path in course_root.iterdir()
        if path.is_dir() and not path.name.startswith("0-")
    )


def infer_course(entry_name: str, courses: list[str]) -> CourseMatch:
    normalized_name = normalize_for_match(Path(entry_name).stem)
    candidates = [
        course
        for course in courses
        if normalize_for_match(course) and normalize_for_match(course) in normalized_name
    ]
    candidates.sort(key=lambda value: (-len(normalize_for_match(value)), value))
    if len(candidates) == 1:
        return CourseMatch(candidates[0], candidates, [])
    if not candidates:
        return CourseMatch(None, [], ["course_not_matched"])
    return CourseMatch(None, candidates, ["multiple_course_matches"])


def infer_category(entry_name: str) -> str:
    stem = Path(entry_name).stem
    if "机考题" in stem and not any(keyword in stem for keyword in STRONG_EXAM_EVIDENCE_KEYWORDS):
        return CATEGORY_REVIEW
    if any(keyword in stem for keyword in REVIEW_HINT_KEYWORDS) and not any(
        keyword in stem for keyword in STRONG_EXAM_EVIDENCE_KEYWORDS
    ):
        return CATEGORY_REVIEW
    if any(keyword in stem for keyword in EXAM_KEYWORDS):
        return CATEGORY_EXAMS
    if any(keyword in stem for keyword in ASSIGNMENT_KEYWORDS):
        return CATEGORY_ASSIGNMENTS
    return CATEGORY_REVIEW


def infer_new_course_name(entry_name: str) -> str | None:
    stem = clean_name_part(Path(entry_name).stem)
    if not stem:
        return None
    for separator in ("-", "—", "–", "_", " "):
        if separator in stem:
            candidate = stem.split(separator, 1)[0].strip()
            return candidate or None
    return stem


def clean_name_part(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[\\/<>:\"|?*]+", "-", value)
    value = re.sub(r"[\s_]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-. ")


def normalize_resource_filename(source: Path, course: str | None) -> str:
    if source.is_dir():
        suffix = ""
        stem = source.name
    else:
        suffix = source.suffix
        stem = source.stem
    clean_stem = clean_name_part(stem)
    if course:
        clean_course = clean_name_part(course)
        normalized_stem = normalize_for_match(clean_stem)
        normalized_course = normalize_for_match(clean_course)
        if normalized_course and not normalized_stem.startswith(normalized_course):
            clean_stem = f"{clean_course}-{clean_stem}"
    return f"{clean_stem}{suffix}"


def classify_file_type(path: Path) -> str:
    if path.is_dir():
        return "Folder"
    ext = path.suffix.casefold()
    if ext == ".pdf":
        return "PDF"
    if ext in WORD_EXTENSIONS:
        return "Word"
    if ext in PPT_EXTENSIONS:
        return "PPT"
    if ext in IMAGE_EXTENSIONS:
        return "图片"
    if ext in ARCHIVE_EXTENSIONS:
        return "ZIP"
    if ext in TEXT_EXTENSIONS:
        return "Text"
    if ext in AUDIO_EXTENSIONS:
        return "Audio"
    if ext in VIDEO_EXTENSIONS:
        return "Video"
    return ext[1:].upper() if ext else "Unknown"


def resource_size_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def resource_mtime(path: Path) -> float:
    if path.is_file():
        return path.stat().st_mtime
    mtimes = [path.stat().st_mtime]
    for child in path.rglob("*"):
        try:
            mtimes.append(child.stat().st_mtime)
        except OSError:
            continue
    return max(mtimes)


def format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    kb = num_bytes / 1024
    if kb < 1024:
        return f"{format_decimal(kb, 1)} KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{format_decimal(mb, 2)} MB"
    gb = mb / 1024
    return f"{format_decimal(gb, 2)} GB"


def format_decimal(value: float, places: int) -> str:
    text = f"{value:.{places}f}"
    return text.rstrip("0").rstrip(".")


def format_chinese_date(timestamp: float) -> str:
    dt = datetime.fromtimestamp(timestamp)
    return f"{dt.year}年{dt.month}月{dt.day}日"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def screen_resource(path: Path) -> dict[str, Any]:
    scanned_files = []
    warnings = []
    findings: list[dict[str, Any]] = []
    text_items = extract_resource_text(path)

    findings.extend(scan_text_for_risks(path.name, "filename"))
    for item in text_items:
        if item.get("warning"):
            warnings.append(item["warning"])
            continue
        rel_path = item["path"]
        text = str(item.get("text", ""))[:MAX_TEXT_CHARS_PER_FILE]
        scanned_files.append(rel_path)
        findings.extend(scan_text_for_risks(text, rel_path))

    unique_warnings = sorted(set(warnings))
    return {
        "scanned": bool(scanned_files),
        "scanned_files": scanned_files,
        "warnings": unique_warnings,
        "findings": findings,
        "risk_level": content_risk_level(findings, unique_warnings),
    }


def extract_resource_text(path: Path) -> list[dict[str, Any]]:
    if path.is_dir():
        results = []
        files = [child for child in sorted(path.rglob("*")) if child.is_file()]
        for child in files[:MAX_FOLDER_SCREEN_FILES]:
            for item in extract_file_text(child):
                item["path"] = str(child.relative_to(path))
                results.append(item)
        if len(files) > MAX_FOLDER_SCREEN_FILES:
            results.append({"path": str(path), "warning": "folder_screen_file_limit_reached"})
        return results
    return extract_file_text(path)


def extract_file_text(path: Path) -> list[dict[str, Any]]:
    ext = path.suffix.casefold()
    if ext in TEXT_SCAN_EXTENSIONS:
        return [{"path": path.name, "text": read_text_best_effort(path)}]
    if ext == ".pdf":
        return extract_pdf_text(path)
    if ext == DOCX_EXTENSION:
        text = extract_docx_text(path)
        if not text.strip():
            return [{"path": path.name, "warning": "content_not_scanned_docx_extract_empty"}]
        return [{"path": path.name, "text": text}]
    if ext in IMAGE_EXTENSIONS:
        return [{"path": path.name, "warning": "content_not_scanned_image"}]
    if ext in {".doc", ".ppt"}:
        return [{"path": path.name, "warning": "content_not_scanned_legacy_office"}]
    if ext in PPT_EXTENSIONS or ext in ARCHIVE_EXTENSIONS or ext in AUDIO_EXTENSIONS or ext in VIDEO_EXTENSIONS:
        return [{"path": path.name, "warning": f"content_not_scanned_{ext[1:] or 'unknown'}"}]
    return [{"path": path.name, "warning": "content_not_scanned_unknown_type"}]


def read_text_best_effort(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding, errors="strict")
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_pdf_text(path: Path) -> list[dict[str, Any]]:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return [{"path": path.name, "warning": "content_not_scanned_pdf_no_pdftotext"}]
    result = subprocess.run(
        [pdftotext, "-enc", "UTF-8", str(path), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    if result.returncode != 0:
        return [{"path": path.name, "warning": "content_not_scanned_pdf_extract_failed"}]
    return [{"path": path.name, "text": result.stdout}]


def extract_docx_text(path: Path) -> str:
    text_parts: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = [
                name
                for name in archive.namelist()
                if name.startswith("word/")
                and name.endswith(".xml")
                and any(part in name for part in ("document", "header", "footer", "footnotes", "endnotes"))
            ]
            for name in names:
                root = ElementTree.fromstring(archive.read(name))
                for element in root.iter():
                    if element.tag.endswith("}t") and element.text:
                        text_parts.append(element.text)
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError):
        return ""
    return "\n".join(text_parts)


def scan_text_for_risks(text: str, source: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name, pattern in PRIVACY_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            findings.append(
                {
                    "source": source,
                    "type": "privacy_pattern",
                    "name": name,
                    "count": len(matches),
                }
            )
    findings.extend(keyword_findings(text, source, "privacy_keyword", PRIVACY_KEYWORDS))
    findings.extend(keyword_findings(text, source, "prohibited_keyword", PROHIBITED_KEYWORDS))
    findings.extend(keyword_findings(text, source, "subjective_keyword", SUBJECTIVE_KEYWORDS))
    findings.extend(keyword_findings(text, source, "copyright_keyword", COPYRIGHT_KEYWORDS))
    return findings


def keyword_findings(text: str, source: str, finding_type: str, keywords: tuple[str, ...]) -> list[dict[str, Any]]:
    findings = []
    for keyword in keywords:
        count = text.count(keyword)
        if count:
            findings.append(
                {
                    "source": source,
                    "type": finding_type,
                    "name": keyword,
                    "count": count,
                }
            )
    return findings


def content_risk_level(findings: list[dict[str, Any]], warnings: list[str]) -> str:
    if any(finding["type"] in {"privacy_pattern", "privacy_keyword", "prohibited_keyword"} for finding in findings):
        return "high"
    if any(finding["type"] in {"subjective_keyword", "copyright_keyword"} for finding in findings):
        return "medium"
    if warnings:
        return "unknown"
    return "low"


def existing_resource_names(category_dir: Path) -> set[str]:
    if not category_dir.exists():
        return set()
    names = set()
    for child in category_dir.iterdir():
        if child.name == "README.md":
            continue
        names.add(child.name.casefold())
        names.add(child.stem.casefold())
    return names


def readme_resource_names(readme_path: Path) -> set[str]:
    if not readme_path.exists():
        return set()
    try:
        lines = read_text(readme_path).splitlines()
    except UnicodeDecodeError:
        return set()
    table = find_file_table(lines)
    if table is None:
        return set()
    header_index, _, headers = table
    try:
        name_index = normalized_headers(headers).index("文件名")
    except ValueError:
        return set()
    names = set()
    for line in lines[header_index + 2 :]:
        if "|" not in line or not line.strip():
            break
        cells = split_table_row(line)
        if len(cells) > name_index and cells[name_index]:
            names.add(cells[name_index].casefold())
    return names


def build_entry(source: Path, incoming: Path, repo_root: Path, courses: list[str], *, prepare: bool = False) -> dict[str, Any]:
    relative_source = source.relative_to(incoming).as_posix()
    course_match = infer_course(source.name, courses)
    proposed_new_course = None
    new_course = False
    if course_match.course is None and not course_match.candidates:
        proposed_new_course = infer_new_course_name(source.name)
        if prepare and proposed_new_course:
            new_course = True
    category = infer_category(source.name)
    if course_match.course is not None:
        category = resolve_category_alias(repo_root, course_match.course, category)
    warnings = list(course_match.warnings)

    course_for_filename = course_match.course or (proposed_new_course if prepare else None)
    destination_filename = normalize_resource_filename(source, course_for_filename) if prepare else source.name
    display_name = destination_filename if source.is_dir() else Path(destination_filename).stem
    destination_path = None
    status = "ready"
    should_apply = True
    destination_course = course_match.course or (proposed_new_course if prepare else None)
    if destination_course:
        destination_path = (
            repo_root / COURSE_ROOT_NAME / destination_course / category / destination_filename
        ).as_posix()

    if course_match.course is None:
        status = "needs_review"
        should_apply = False
        if new_course:
            warnings.append("new_course_candidate")
    else:
        category_dir = repo_root / COURSE_ROOT_NAME / course_match.course / category
        destination_path = (category_dir / destination_filename).as_posix()
        existing_names = existing_resource_names(category_dir)
        readme_names = readme_resource_names(category_dir / "README.md")
        if count_file_tables(category_dir / "README.md") > 1:
            warnings.append("multiple_readme_file_tables")
        if destination_filename.casefold() in existing_names or display_name.casefold() in existing_names:
            warnings.append("destination_file_exists")
        if display_name.casefold() in readme_names:
            warnings.append("readme_name_exists")
        if "multiple_readme_file_tables" in warnings:
            status = "needs_review"
            should_apply = False
        elif any(warning.endswith("_exists") for warning in warnings):
            status = "conflict"
            should_apply = False

    content_screening = None
    if prepare:
        content_screening = screen_resource(source)
        if category in {CATEGORY_EXAMS, "历年真题"}:
            warnings.append("exam_metadata_requires_content_review")
            status = "needs_review"
            should_apply = False
            if source.suffix.casefold() in ARCHIVE_EXTENSIONS:
                warnings.append("exam_archive_should_be_extracted")
        if content_screening["risk_level"] in {"high", "medium", "unknown"}:
            if content_screening["findings"]:
                warnings.append("content_risk_found")
            if content_screening["warnings"]:
                warnings.append("content_needs_manual_review")
            status = "needs_review"
            should_apply = False

    return {
        "source": relative_source,
        "apply": should_apply,
        "status": status,
        "warnings": warnings,
        "new_course": new_course,
        "proposed_new_course": proposed_new_course,
        "course_candidates": course_match.candidates,
        "destination": {
            "course": destination_course,
            "category": category,
            "filename": destination_filename,
            "path": destination_path,
        },
        "metadata": {
            "display_name": display_name,
            "author": "Unknown",
            "source": "Local",
            "file_type": classify_file_type(source),
            "file_size": format_size(resource_size_bytes(source)),
            "updated_at": format_chinese_date(resource_mtime(source)),
            "remark": "",
        },
        "content_screening": content_screening,
    }


def scan_resources(incoming: Path, repo_root: Path) -> dict[str, Any]:
    incoming = incoming.resolve()
    repo_root = repo_root.resolve()
    if not incoming.exists():
        raise FileNotFoundError(f"Incoming directory does not exist: {incoming}")
    if not incoming.is_dir():
        raise NotADirectoryError(f"Incoming path is not a directory: {incoming}")

    courses = list_courses(repo_root)
    entries = []
    for source in sorted(incoming.iterdir(), key=lambda path: path.name.casefold()):
        if source.name.startswith("."):
            continue
        entries.append(build_entry(source, incoming, repo_root, courses))

    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "repo_root": str(repo_root),
        "incoming": str(incoming),
        "entries": entries,
        "audit": audit_repository(repo_root),
    }


def prepare_resources(incoming: Path, repo_root: Path) -> dict[str, Any]:
    incoming = incoming.resolve()
    repo_root = repo_root.resolve()
    if not incoming.exists():
        raise FileNotFoundError(f"Incoming directory does not exist: {incoming}")
    if not incoming.is_dir():
        raise NotADirectoryError(f"Incoming path is not a directory: {incoming}")

    courses = list_courses(repo_root)
    entries = []
    for source in sorted(incoming.iterdir(), key=lambda path: path.name.casefold()):
        if source.name.startswith("."):
            continue
        entries.append(build_entry(source, incoming, repo_root, courses, prepare=True))

    return {
        "schema_version": 2,
        "mode": "prepare",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "repo_root": str(repo_root),
        "incoming": str(incoming),
        "entries": entries,
        "review_summary": summarize_review(entries),
        "audit": audit_repository(repo_root),
    }


def summarize_review(entries: list[dict[str, Any]]) -> dict[str, Any]:
    needs_review = [entry["source"] for entry in entries if entry.get("status") == "needs_review"]
    conflicts = [entry["source"] for entry in entries if entry.get("status") == "conflict"]
    ready = [entry["source"] for entry in entries if entry.get("apply")]
    return {
        "ready_count": len(ready),
        "needs_review_count": len(needs_review),
        "conflict_count": len(conflicts),
        "ready": ready,
        "needs_review": needs_review,
        "conflicts": conflicts,
    }


def resolve_category_alias(repo_root: Path, course: str, category: str) -> str:
    if category != CATEGORY_EXAMS:
        return category
    course_dir = repo_root / COURSE_ROOT_NAME / course
    canonical = course_dir / CATEGORY_EXAMS
    legacy = course_dir / "历年真题"
    if not canonical.exists() and legacy.exists():
        return legacy.name
    return category


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


def normalized_headers(headers: list[str]) -> list[str]:
    return [re.sub(r"\s+", "", header) for header in headers]


def find_file_table(lines: list[str]) -> tuple[int, int, list[str]] | None:
    for index in range(len(lines) - 1):
        if "|" not in lines[index] or not is_separator_row(lines[index + 1]):
            continue
        headers = split_table_row(lines[index])
        if "文件名" in normalized_headers(headers):
            return index, index + 1, headers
    return None


def count_file_tables(readme_path: Path) -> int:
    if not readme_path.exists():
        return 0
    try:
        lines = read_text(readme_path).splitlines()
    except UnicodeDecodeError:
        return 0
    count = 0
    for index in range(len(lines) - 1):
        if "|" not in lines[index] or not is_separator_row(lines[index + 1]):
            continue
        headers = split_table_row(lines[index])
        if "文件名" in normalized_headers(headers):
            count += 1
    return count


def read_template(repo_root: Path, *relative_parts: str) -> str | None:
    template = repo_root / COURSE_ROOT_NAME / "0-模板"
    for part in relative_parts:
        template = template / part
    if not template.exists():
        return None
    return read_text(template)


def fallback_readme_content(category: str) -> str:
    if category in {CATEGORY_EXAMS, "历年真题"}:
        header = "文件名|来源|文件类型|文件大小|备注"
        separator = "---|---|---|---|---"
    elif category == CATEGORY_ASSIGNMENTS:
        header = "文件名|文件类型|文件大小|备注"
        separator = "---|---|---|---"
    else:
        header = "文件名|作者|来源|文件类型|文件大小|最近更新时间|备注"
        separator = "---|---|---|---|---|---|---"
    return f"# {category}\n\n{header}\n{separator}\n"


def default_readme_content(category: str, repo_root: Path) -> str:
    template_category = CATEGORY_EXAMS if category == "历年真题" else category
    template = read_template(repo_root, template_category, "README.md")
    if template is None:
        return fallback_readme_content(category)
    if category != template_category:
        template = re.sub(r"^# .+$", f"# {category}", template, count=1, flags=re.MULTILINE)
    lines = template.splitlines()
    table = find_file_table(lines)
    if table is not None:
        _, separator_index, _ = table
        template = "\n".join(lines[: separator_index + 1]) + "\n"
    return template if template.endswith("\n") else template + "\n"


def fallback_course_readme_content(course: str) -> str:
    return (
        f"# {course}\n\n"
        "课程介绍。\n\n"
        "## 下载\n\n"
        "[点击链接，下载文件夹内所有内容]"
        f"(https://xovee.github.io/gitzip/?https://github.com/Xovee/uestc-course/tree/main/课程目录/{course})\n"
        "<br><h1>资源贡献</h1><br>"
        "希望大家能多多贡献资源，促进仓库良性发展，帮助更多的同学考个好成绩！"
        "仓库地址：[https://github.com/Xovee/uestc-course](https://github.com/Xovee/uestc-course)"
        "<br><br>国内访问GitHub不太稳定，有时候需要特殊手段。"
        "有问题可以邮件联系我：`xovee at uestc.edu.cn` \n"
    )


def default_course_readme_content(course: str, repo_root: Path) -> str:
    template = read_template(repo_root, "README.md")
    if template is None:
        return fallback_course_readme_content(course)
    template = re.sub(r"^# .+$", f"# {course}", template, count=1, flags=re.MULTILINE)
    template = template.replace("【替换为文件夹名】", course)
    return template if template.endswith("\n") else template + "\n"


def ensure_course_readme(course_dir: Path, course: str, repo_root: Path) -> None:
    readme = course_dir / "README.md"
    if not readme.exists():
        write_text(readme, default_course_readme_content(course, repo_root))


def row_for_headers(headers: list[str], metadata: dict[str, Any]) -> str:
    values = []
    normalized = normalized_headers(headers)
    row_metadata = metadata_with_author_note(normalized, metadata)
    for header in normalized:
        values.append(value_for_header(header, row_metadata))
    return "|".join(values)


def metadata_with_author_note(headers: list[str], metadata: dict[str, Any]) -> dict[str, Any]:
    author = str(metadata.get("author") or "")
    if not author or author == "Unknown" or "作者" in headers or "备注" not in headers:
        return metadata
    row_metadata = dict(metadata)
    remark = str(row_metadata.get("remark") or "")
    author_note = f"作者：{author}"
    if author_note not in remark:
        row_metadata["remark"] = f"{remark}；{author_note}" if remark else author_note
    return row_metadata


def value_for_header(header: str, metadata: dict[str, Any]) -> str:
    if header == "文件名":
        return str(metadata.get("display_name", ""))
    if header == "作者":
        return str(metadata.get("author") or "Unknown")
    if header == "来源":
        return str(metadata.get("source") or "Local")
    if header == "科目":
        return str(metadata.get("subject", ""))
    if header == "考试形式":
        return str(metadata.get("exam_form", ""))
    if header == "答案":
        return str(metadata.get("answer", ""))
    if header == "文件类型":
        return str(metadata.get("file_type", ""))
    if header == "文件大小":
        return str(metadata.get("file_size", ""))
    if header in {"最近更新时间", "最后更新时间", "最后更新", "更新时间", "时间"}:
        return str(metadata.get("updated_at", ""))
    if header == "备注":
        return str(metadata.get("remark", ""))
    return ""


def update_category_readme(readme_path: Path, category: str, metadata: dict[str, Any], repo_root: Path) -> None:
    if not readme_path.exists():
        write_text(readme_path, default_readme_content(category, repo_root))

    content = read_text(readme_path)
    lines = content.splitlines()
    if count_file_tables(readme_path) > 1:
        raise ValueError(f"Multiple README file tables need manual handling: {readme_path}")
    table = find_file_table(lines)
    if table is None:
        if content and not content.endswith("\n"):
            content += "\n"
        content += "\n" + default_readme_content(category, repo_root)
        lines = content.splitlines()
        table = find_file_table(lines)
        if table is None:
            raise ValueError(f"Could not create README table in {readme_path}")

    _, separator_index, headers = table
    lines, separator_index, headers = ensure_remark_column_for_author(lines, separator_index, headers, metadata)
    row = row_for_headers(headers, metadata)
    lines.insert(separator_index + 1, row)
    write_text(readme_path, "\n".join(lines) + "\n")


def ensure_remark_column_for_author(
    lines: list[str],
    separator_index: int,
    headers: list[str],
    metadata: dict[str, Any],
) -> tuple[list[str], int, list[str]]:
    normalized = normalized_headers(headers)
    author = str(metadata.get("author") or "")
    if not author or author == "Unknown" or "作者" in normalized or "备注" in normalized:
        return lines, separator_index, headers

    header_index = separator_index - 1
    lines[header_index] = lines[header_index].rstrip("|") + "|备注"
    lines[separator_index] = lines[separator_index].rstrip("|") + "|---"
    index = separator_index + 1
    while index < len(lines) and "|" in lines[index] and lines[index].strip():
        lines[index] = lines[index].rstrip("|") + "|"
        index += 1
    return lines, separator_index, headers + ["备注"]


def validate_plan_entry(entry: dict[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
    destination = entry.get("destination") or {}
    metadata = entry.get("metadata") or {}
    course = destination.get("course")
    category = destination.get("category")
    filename = destination.get("filename")
    if not course or not category or not filename:
        raise ValueError(f"Entry is missing destination fields: {entry.get('source')}")
    if Path(str(filename)).name != filename:
        raise ValueError(f"Destination filename must not contain path separators: {filename}")
    return str(course), str(category), str(filename), metadata


def apply_plan(incoming: Path, repo_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    incoming = incoming.resolve()
    repo_root = repo_root.resolve()
    applied = []
    skipped = []

    for entry in plan.get("entries", []):
        if not entry.get("apply", False):
            skipped.append({"source": entry.get("source"), "reason": "apply_false"})
            continue

        course, category, filename, metadata = validate_plan_entry(entry)
        if (
            category in {CATEGORY_EXAMS, "历年真题"}
            and Path(filename).suffix.casefold() in ARCHIVE_EXTENSIONS
            and not entry.get("allow_exam_archive", False)
        ):
            raise ValueError(
                "Exam archives must be extracted before applying, unless allow_exam_archive is true: "
                f"{entry.get('source')}"
            )
        source = (incoming / str(entry.get("source", ""))).resolve()
        if not is_relative_to(source, incoming):
            raise ValueError(f"Source escapes incoming directory: {entry.get('source')}")
        if not source.exists():
            raise FileNotFoundError(f"Source does not exist: {source}")

        course_dir = repo_root / COURSE_ROOT_NAME / course
        target_dir = course_dir / category
        target_dir.mkdir(parents=True, exist_ok=True)
        ensure_course_readme(course_dir, course, repo_root)
        target = target_dir / filename
        if target.exists():
            raise FileExistsError(f"Destination already exists: {target}")

        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)

        update_category_readme(target_dir / "README.md", category, metadata, repo_root)
        applied.append(
            {
                "source": str(source),
                "destination": str(target),
                "readme": str(target_dir / "README.md"),
            }
        )

    return {"applied": applied, "skipped": skipped}


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def audit_repository(repo_root: Path) -> dict[str, Any]:
    course_root = repo_root / COURSE_ROOT_NAME
    return {
        "missing_category_readmes": missing_category_readmes(course_root),
        "category_readme_template_mismatches": category_readme_template_mismatches(repo_root),
        "top_level_readme_issues": top_level_readme_issues(repo_root),
        "template_missing_targets": template_missing_targets(repo_root),
        "missing_relative_markdown_links": missing_relative_markdown_links(repo_root),
        "old_master_links": old_master_links(repo_root),
        "placeholder_download_links": placeholder_download_links(course_root),
        "download_link_mismatches": download_link_mismatches(course_root),
    }


def missing_category_readmes(course_root: Path) -> list[str]:
    if not course_root.exists():
        return []
    missing = []
    for course in course_root.iterdir():
        if not course.is_dir() or course.name.startswith("0-"):
            continue
        for category_dir in course.iterdir():
            if category_dir.is_dir() and not (category_dir / "README.md").exists():
                missing.append(str(category_dir))
    return sorted(missing)


def template_table_schema(repo_root: Path, category: str) -> tuple[str, str] | None:
    template_category = CATEGORY_EXAMS if category == "历年真题" else category
    template = read_template(repo_root, template_category, "README.md")
    if template is None:
        return None
    lines = template.splitlines()
    table = find_file_table(lines)
    if table is None:
        return None
    header_index, separator_index, _ = table
    return lines[header_index], lines[separator_index]


def category_readme_template_mismatches(repo_root: Path) -> list[dict[str, Any]]:
    course_root = repo_root / COURSE_ROOT_NAME
    if not course_root.exists():
        return []
    mismatches = []
    for course in course_root.iterdir():
        if not course.is_dir() or course.name.startswith("0-"):
            continue
        for category_dir in course.iterdir():
            readme = category_dir / "README.md"
            if not category_dir.is_dir() or not readme.exists():
                continue
            expected = template_table_schema(repo_root, category_dir.name)
            if expected is None:
                continue
            try:
                lines = read_text(readme).splitlines()
            except UnicodeDecodeError:
                continue
            table = find_file_table(lines)
            if table is None:
                mismatches.append({"path": str(readme), "issue": "missing_file_table"})
                continue
            header_index, separator_index, _ = table
            actual = (lines[header_index], lines[separator_index])
            if actual != expected:
                mismatches.append(
                    {
                        "path": str(readme),
                        "expected_header": expected[0],
                        "actual_header": actual[0],
                        "expected_separator": expected[1],
                        "actual_separator": actual[1],
                    }
                )
    return sorted(mismatches, key=lambda item: item["path"])


def template_missing_targets(repo_root: Path) -> list[str]:
    template_readme = repo_root / "assets" / "模板" / "README.md"
    if not template_readme.exists():
        return []
    content = read_text(template_readme)
    missing = []
    for match in re.finditer(r"\]\((\./[^)]+\.md)\)", content):
        target = (template_readme.parent / match.group(1)).resolve()
        if not target.exists():
            missing.append(str(target))
    return sorted(set(missing))


def top_level_readme_issues(repo_root: Path) -> list[dict[str, Any]]:
    checks = [
        (repo_root / COURSE_ROOT_NAME / "README.md", "empty_or_missing"),
        (repo_root / "考研目录" / "README.md", "missing"),
    ]
    issues = []
    for path, issue in checks:
        if not path.exists():
            issues.append({"path": str(path), "issue": "missing"})
        elif issue == "empty_or_missing" and path.stat().st_size == 0:
            issues.append({"path": str(path), "issue": "empty"})
    return issues


def missing_relative_markdown_links(repo_root: Path) -> list[dict[str, Any]]:
    pattern = re.compile(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+\.md)(?:#[^)]+)?\)")
    results = []
    for path in iter_markdown_files(repo_root):
        try:
            lines = read_text(path).splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for match in pattern.finditer(line):
                target_text = match.group(1).strip()
                target = (path.parent / unquote(target_text)).resolve()
                if not target.exists():
                    results.append(
                        {
                            "path": str(path),
                            "line": line_number,
                            "target": str(target),
                        }
                    )
    return results


def iter_markdown_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.md") if ".git" not in path.parts]


def old_master_links(repo_root: Path) -> list[dict[str, Any]]:
    results = []
    for path in iter_markdown_files(repo_root):
        try:
            lines = read_text(path).splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if "tree/master" in line or "raw/master" in line:
                results.append({"path": str(path), "line": line_number})
    return results


def placeholder_download_links(course_root: Path) -> list[dict[str, Any]]:
    if not course_root.exists():
        return []
    results = []
    for readme in course_root.glob("*/README.md"):
        try:
            content = read_text(readme)
        except UnicodeDecodeError:
            continue
        if "【替换为文件夹名】" in content or "/[" in content:
            results.append({"path": str(readme)})
    return results


def download_link_mismatches(course_root: Path) -> list[dict[str, Any]]:
    if not course_root.exists():
        return []
    pattern = re.compile(r"github\.com/Xovee/uestc-course/tree/(?:main|master)/课程目录/([^\s)]+)")
    results = []
    for course in course_root.iterdir():
        readme = course / "README.md"
        if not course.is_dir() or course.name.startswith("0-") or not readme.exists():
            continue
        try:
            content = read_text(readme)
        except UnicodeDecodeError:
            continue
        for match in pattern.finditer(content):
            linked_course = unquote(match.group(1)).rstrip("/")
            if "【" in linked_course or "[" in linked_course:
                continue
            if linked_course != course.name:
                results.append(
                    {
                        "path": str(readme),
                        "course": course.name,
                        "linked_course": linked_course,
                    }
                )
    return results


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def dump_json(data: dict[str, Any], path: Path | None = None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if path is not None:
        path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=repo_root_from_script(),
        help="Repository root. Defaults to the parent of this script directory.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan incoming resources and emit a JSON plan.")
    scan_parser.add_argument("--incoming", type=Path, default=Path(DEFAULT_INCOMING))
    scan_parser.add_argument("--output", type=Path, help="Optional file to also write the JSON plan.")

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Prepare a richer, human-reviewable ingestion plan with naming and content screening.",
    )
    prepare_parser.add_argument("--incoming", type=Path, default=Path(DEFAULT_INCOMING))
    prepare_parser.add_argument("--output", type=Path, help="Optional file to also write the JSON plan.")

    apply_parser = subparsers.add_parser("apply", help="Apply a human-reviewed JSON plan.")
    apply_parser.add_argument("--incoming", type=Path, default=Path(DEFAULT_INCOMING))
    apply_parser.add_argument("--plan", type=Path, required=True)

    subparsers.add_parser("audit", help="Audit repository consistency without modifying files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "scan":
            plan = scan_resources(args.incoming, args.repo_root)
            dump_json(plan, args.output)
        elif args.command == "prepare":
            plan = prepare_resources(args.incoming, args.repo_root)
            dump_json(plan, args.output)
        elif args.command == "apply":
            plan = load_json(args.plan)
            report = apply_plan(args.incoming, args.repo_root, plan)
            dump_json(report)
        elif args.command == "audit":
            report = audit_repository(args.repo_root)
            dump_json(report)
        else:
            parser.error(f"Unknown command: {args.command}")
    except Exception as exc:  # noqa: BLE001 - CLI should surface concise failures.
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
