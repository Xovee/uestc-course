# Codex Automation Notes

This repository contains UESTC course resources. When the user asks Codex to
organize newly provided materials, follow this durable workflow.

## Local Resource Ingestion

- The user places new materials in `_incoming/`.
- Explicitly read text files, README files, generated plans, issue/PR exports,
  and metadata as UTF-8 whenever the tool supports an encoding option. Set the
  console/output encoding to UTF-8 before inspecting Chinese content.
- Start with:

```powershell
python tools\ingest_resources.py prepare --incoming _incoming --output _incoming\plan.json
```

- Review `_incoming/plan.json` before applying anything.
- The prepare/scan flow ignores generated `_incoming/plan.json` files; do not
  treat them as resources to ingest.
- Do not delete files from `_incoming/`; the ingestion flow preserves source
  files by default.
- Keep only active, not-yet-reviewed batches in `_incoming/`. After a batch is
  organized and either committed or explicitly approved for cleanup, delete its
  original source files from `_incoming/` instead of archiving them. If
  `_incoming/` contains old batches, run the prepare command against the current
  batch subfolder to avoid mixing unrelated resources into one plan.

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
- For `历年试题`, do not add ZIP files unless the archive only wraps
  image screenshots. Extract exam archives and place the resulting files or
  folders according to the course's existing convention; list the final
  resources in README, not the archive.

## Placement and Naming

- Existing courses go under `课程目录/<课程名>/<分类>/`.
- Categories are usually `复习资料`, `历年试题`, and `作业`.
- Use `历年试题` as the canonical exam category. If an old course still has
  `历年真题`, migrate it to `历年试题` instead of continuing the old name.
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
- For ordinary resource ingestion, stop after organizing resources and running
  verification, then ask the user to inspect the final changes before `git add`,
  `git commit`, or `git push`. Only commit and push after the user explicitly
  approves that batch.
- If the placement is clear, the content screening is low-risk, metadata can be
  verified from file content or issue/PR guidance, README format matches the
  template, and verification passes, present the verified diff summary to the
  user for review instead of committing directly.
- After successfully adding and pushing resources from a GitHub issue, reply to
  the issue with a short thank-you such as `感谢贡献，资源已添加到仓库！`, then
  close the issue when GitHub write access is available.
- If there is meaningful uncertainty, stop before `git add`, `git commit`, and
  `git push`; summarize the concern and wait for the user to review and approve.
- Human review is required for unclear course ownership, privacy or copyright
  concerns, sensitive/prohibited content, conflicting metadata, unreadable
  archives or binary resources, new-course structure uncertainty, or exam
  metadata that cannot be reliably inferred.
- Never open a PR unless the user explicitly asks. The normal maintainer flow is
  direct push to `origin/main` only after the user has inspected and approved
  the final local changes for that batch.

## README Updates

- `课程目录/0-模板` is authoritative for README structure. Use the matching
  template's columns when creating or repairing course/category README files;
  do not add new columns such as `科目`, `考试形式`, or `答案` unless that target
  README already uses them.
- Do not update the root `README.md` course/resource count after ordinary
  resource additions. Only update that project-level statistic when the user
  explicitly asks, and prefer approximate phrasing such as `150余门课程，1800多个资源`
  / `150+ courses with 1800+ materials` instead of exact numbers.
- Match the template's header and separator text exactly, including spacing such
  as `文件名|来源 | 文件类型|文件大小|备注` for `历年试题`.
- Category templates contain example rows. Use their title/header/separator as
  the schema, but do not copy example rows into real course directories.
- Use existing source vocabulary where possible, for example `GitHub Issue`,
  `PR`, `河畔`, or `Local`; do not invent source labels such as `Issue #153`.
- Read the target README's actual table header and fill columns dynamically.
- Sort README resource rows in reverse chronological order when the filename or
  verified metadata contains a year/term/date. Keep undated rows after dated
  rows unless the target README already has a stronger local convention.
- Do not reformat, reorder, or clean up existing historical tables.
- If a README has multiple `文件名` tables, do not auto-insert; ask the user.
- If the user names an author but the target README has no `作者` column, record
  it in `备注`; if there is no `备注` column, add one conservatively.
- If exam metadata such as `闭卷`, `A卷`, `回忆版`, or `非官方答案` has no matching
  template column, encode the essential answer status in the filename and put
  the rest in `备注`.
- When a source URL is recorded in `备注`, prefer concise Markdown links with
  the source name, for example `来自[河畔](https://...)`, instead of bare URLs.
- README table cell values should be single-line Markdown-table-safe text.
  Replace embedded newlines with spaces and avoid raw `|` characters inside
  cells.
- Do not auto-write `教材` entries unless a separate schema is designed.

## Apply Safety

- Before applying a reviewed plan, the tool should preflight all `apply: true`
  entries before copying files or editing README files.
- Reject plans that would write outside `课程目录`, reuse one destination path
  for multiple entries, use path separators in course/category/filename fields,
  use an empty or root `_incoming` source, or target the legacy `历年真题`
  category instead of canonical `历年试题`.
- Keep the apply step all-or-nothing for validation errors: if one active entry
  is invalid, no earlier active entry should have been copied first.

## Audit Coverage

`python tools\ingest_resources.py audit` should report repository consistency
issues without modifying files. Keep coverage for README/template mismatches,
legacy `历年真题` category directories, empty resource directories in standard
resource categories, suspicious duplicate file extensions such as `.pdf.pdf`,
duplicate README `文件名` rows, README row chronological ordering, README rows
without local files, and local files or folders missing README rows. Do not
treat `教材` directories as ordinary local-file resource directories unless a
separate textbook schema is designed.

## Verification

Run these after changing the automation code or tests:

```powershell
python -m unittest discover -s tests
python -m py_compile tools\ingest_resources.py tools\repository_size_report.py tests\test_ingest_resources.py tests\test_repository_size_report.py
python tools\ingest_resources.py audit
git diff --check
```
