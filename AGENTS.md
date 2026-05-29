# Codex Automation Notes

This repository contains UESTC course resources. When the user asks Codex to
organize newly provided materials, follow this durable workflow.

## Local Resource Ingestion

- The user places new materials in `_incoming/`.
- Start with:

```powershell
python tools\ingest_resources.py prepare --incoming _incoming --output _incoming\plan.json
```

- Review `_incoming/plan.json` before applying anything.
- Do not commit, push, or open a PR unless the user explicitly asks.
- Do not delete files from `_incoming/`; the ingestion flow preserves source
  files by default.

## Review Rules

- Treat privacy, prohibited content, copyright risk, and subjective course or
  teacher evaluations as human-review gates.
- If `content_screening.risk_level` is `high`, `medium`, or `unknown`, explain
  the finding and ask for confirmation before setting `apply` to `true`.
- Images, old `.doc` / `.ppt`, archives, audio, and video may not be fully
  text-scannable; keep them in manual review unless the user confirms.
- Use file modification time (`mtime`) for README update dates, not today's date.
- README `文件名` cells should normally omit file extensions; actual files keep
  their extensions.

## Placement and Naming

- Existing courses go under `课程目录/<课程名>/<分类>/`.
- Categories are usually `复习资料`, `历年试题`, and `作业`.
- If a course already uses `历年真题`, use that instead of creating `历年试题`.
- For new courses, create:
  - `课程目录/<课程名>/README.md`
  - the needed category directory
  - the needed category `README.md`
- Use conservative filename normalization: clean spaces, illegal characters, and
  repeated separators; preserve original meaning. Do not invent year, semester,
  answer status, teacher, author, or source.
- If course matching is ambiguous, leave the item for human review.

## README Updates

- Read the target README's actual table header and fill columns dynamically.
- Do not reformat, reorder, or clean up existing historical tables.
- If a README has multiple `文件名` tables, do not auto-insert; ask the user.
- Do not auto-write `教材` entries unless a separate schema is designed.

## Verification

Run these after changing the automation code or tests:

```powershell
python -m unittest tests.test_ingest_resources
python -m py_compile tools\ingest_resources.py tests\test_ingest_resources.py
git diff --check
```
