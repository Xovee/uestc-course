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
- For issue or PR based ingestion, read the issue/PR body and comments before
  finalizing placement. Explicit guidance there, such as course, category,
  author, teacher, and incompleteness notes, is high-priority metadata.
- For `历年试题` / `历年真题`, do not add ZIP files unless the archive only wraps
  image screenshots. Extract exam archives and place the resulting files or
  folders according to the course's existing convention; list the final
  resources in README, not the archive.

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
- Prefer filenames that start with the course name, matching the examples in
  `课程目录/0-模板`, unless the target course already uses a different local
  convention for that category.
- When actively reorganizing a course/category, update older resources in that
  same target category to the current naming and README conventions too. Do not
  leave mixed old/new styles in one README just because some entries predate the
  current ingestion task.
- For exam materials, inspect the file content whenever possible before
  finalizing filename and README metadata. Derive year/semester, exam type,
  exam form, and answer status from the paper itself; use the original filename
  only as fallback evidence when content cannot be read.
- Convert academic terms from content when clear, for example `2007-2008学年第一学期`
  means `2007年秋`, and `2007-2008学年第二学期` means `2008年春`.
- If an exam answer or annotated paper is not clearly official, mark that in
  both filename and README. Use statuses like `仅非官方答案` or `含非官方答案`,
  and add a short README `备注` such as `非官方整理` or `参考答案非官方`.
- For exam files, prefer the existing pattern
  `年份学期-考试类型-答案状态-补充信息.ext`, for example
  `2026年春-期末考试-无答案-计院-回忆版.pdf`. Put teachers,
  incompleteness, and author notes in README `备注` when possible.
- If course matching is ambiguous, leave the item for human review.
- SQL machine-test practice materials are usually review/practice resources,
  not `历年试题`, unless the user explicitly says otherwise.

## Commit and Push Policy

- After organizing materials, decide whether the result is low-risk enough to
  finish end-to-end or should wait for human review.
- If the placement is clear, the content screening is low-risk, metadata can be
  verified from file content or issue/PR guidance, README format matches the
  template, and verification passes, commit and push directly to GitHub.
- If there is meaningful uncertainty, stop before `git add`, `git commit`, and
  `git push`; summarize the concern and wait for the user to review and approve.
- Human review is required for unclear course ownership, privacy or copyright
  concerns, sensitive/prohibited content, conflicting metadata, unreadable
  archives or binary resources, new-course structure uncertainty, or exam
  metadata that cannot be reliably inferred.
- Never open a PR unless the user explicitly asks. The normal maintainer flow is
  direct push to `origin/main` after a low-risk local verification pass.

## README Updates

- `课程目录/0-模板` is authoritative for README structure. Use the matching
  template's columns when creating or repairing course/category README files;
  do not add new columns such as `科目`, `考试形式`, or `答案` unless that target
  README already uses them.
- Match the template's header and separator text exactly, including spacing such
  as `文件名|来源 | 文件类型|文件大小|备注` for `历年试题`.
- Category templates contain example rows. Use their title/header/separator as
  the schema, but do not copy example rows into real course directories.
- Use existing source vocabulary where possible, for example `GitHub Issue`,
  `PR`, `河畔`, or `Local`; do not invent source labels such as `Issue #153`.
- Read the target README's actual table header and fill columns dynamically.
- Do not reformat, reorder, or clean up existing historical tables.
- If a README has multiple `文件名` tables, do not auto-insert; ask the user.
- If the user names an author but the target README has no `作者` column, record
  it in `备注`; if there is no `备注` column, add one conservatively.
- If exam metadata such as `闭卷`, `A卷`, `回忆版`, or `非官方答案` has no matching
  template column, encode the essential answer status in the filename and put
  the rest in `备注`.
- Do not auto-write `教材` entries unless a separate schema is designed.

## Verification

Run these after changing the automation code or tests:

```powershell
python -m unittest tests.test_ingest_resources
python -m py_compile tools\ingest_resources.py tests\test_ingest_resources.py
python tools\ingest_resources.py audit
git diff --check
```
