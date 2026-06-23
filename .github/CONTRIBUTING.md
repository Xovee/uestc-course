# 贡献指南

感谢你愿意帮助完善 `uestc-course`。如果你只是想上传资源，最简单的方式是提交
“资源贡献” Issue，把文件拖拽到输入框即可。

详细说明请参考仓库内的 [贡献指南](../assets/贡献指南.md)。

## 资源贡献

提交资源时，如果你知道下面的信息，可以顺手写上；不知道可以留空，维护者会协助整理。

- 课程名称
- 资源类型：复习资料、历年试题、作业、教材或其他
- 资源说明：例如复习提纲、期末试题、实验报告模板等
- 年份、学期、考试类型、是否含答案
- 来源、作者或原始链接
- 需要特别说明的版权、隐私或转载限制

请尽量避免上传包含个人隐私、主观课程/教师评价、明显版权风险或不适合公开传播的内容。

## Pull Request

如果你通过 Pull Request 贡献资源，请尽量保持现有目录结构和 README 表格风格。
维护脚本会检查资源目录、README 表格和下载链接的一致性。

维护者在合并前通常会运行：

```powershell
python -m unittest tests.test_ingest_resources
python -m py_compile tools\ingest_resources.py tests\test_ingest_resources.py
python tools\ingest_resources.py audit
git diff --check
```
