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
- 准备、审查和应用计划期间保留 `_incoming/` 原始文件。某批次整理完成，
  且其资源及 README 已提交，或用户明确批准清理该批次后，清理该批次
  已处理的原始来源文件，不另行归档。清理前核对文件清单及目标路径；
  保留待审、未处理和其他批次文件。
- 存在多个批次时，仅对当前批次子目录运行 prepare，避免混入旧批次。

## Review Rules

- Treat privacy, prohibited content, copyright risk, and subjective course or
  teacher evaluations as human-review gates.
- 对可能违反仓库政策的资源、`content_screening.risk_level` 为 `high`、
  `medium` 或 `unknown` 的资源，以及尚未充分检查的图片、旧版 `.doc` /
  `.ppt`、压缩包、音视频，保持 `apply: false`。先完成允许的只读检查，
  列出具体风险、候选归属和需要用户决定的事项；用户确认前不收录这些资源。
  经 Xovee Xu 确认后，可以不收录相关资源。
- 待审项不阻止其他独立且已授权资源的整理与验证。计划应用仍须对全部
  `apply: true` 条目先统一预检，验证失败时不得部分写入。最终摘要分别
  列出已整理项和待审项。
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
- 非试题资源默认以课程名开头，目标分类已有明确命名惯例时沿用。试题
  优先采用下文的 `年份学期-考试类型-答案状态-补充信息.ext` 规则；目标
  试题分类已有一致的课程名前缀时可保留。模板示例用于说明格式，不覆盖
  本节的试题专用规则。
- 普通新增资源只修改新增文件、对应 README 条目及必要链接，不自动统一
  旧资源命名或重排历史条目。已有表格按倒序排列时，将新增条目插入相应
  位置；否则保留旧条目的相对顺序。
- 用户明确要求整理某课程或分类时，在该范围内统一新旧资源的命名、README
  格式和日期顺序，并修复受影响链接；保留原有事实信息，不扩展到其他分类
  或独立历史表格。有可核实日期的条目倒序排列，未注明日期的条目置后，
  除非目标表格已有更明确的局部约定。
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

- 普通资源入库在首次请求审核前，应完成本批次已授权的整理、README 更新、
  适用验证，以及本次改动引入问题的修复，形成可直接检查的最终差异。
- 无论风险是否较低，均须在 `git add`、`git commit`、`git push` 前展示
  差异摘要，并等待用户检查、明确批准该批次。用户批准后，继续完成批准
  范围内的提交和推送，不重复索要同一授权；若最终差异或风险发生实质变化，
  说明变化并重新确认受影响部分。
- After successfully adding and pushing resources from a GitHub issue, reply to
  the issue with a short thank-you such as `感谢贡献，资源已添加到仓库！`, then
  close the issue when GitHub write access is available.
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
- README 条目排序和历史内容整理范围遵循上文 Placement and Naming 的规定。
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

仅新增或整理资源时，核对本批次计划、目标文件或目录、README 条目、命名、
元数据和受影响链接，并运行 `git diff --check`；使用只读 audit 检查一致性，
区分本次引入的问题与既有问题，不自动修复范围外历史问题。

修改自动化代码或测试时，运行下列四项检查。修复本次改动引入的失败后，
重跑受影响检查；通过后没有新改动或新证据，不重复运行。无法完成的检查
应明确报告，不将未验证结果称为通过。

```powershell
python -m unittest discover -s tests
python -m py_compile tools\build_static_site.py tools\ingest_resources.py tools\repository_size_report.py tests\test_build_static_site.py tests\test_ingest_resources.py tests\test_repository_size_report.py
python tools\ingest_resources.py audit
git diff --check
```
