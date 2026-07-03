---
name: extracting-pdf-text-multimodal
description: 当需要在不使用 OCR 的情况下从 PDF 文件中提取文本或结构化内容，或者传统 PDF 解析库无法正确捕获布局、结构或内容时使用。
---

# 通过多模态提取 PDF 文本

## 概览
当传统的 PDF 文本提取（例如 `PyPDF2`）失败，或者明确禁止使用 OCR 时，可利用多模态能力：首先使用 PyMuPDF (`fitz`) 将 PDF 页面转换为图像，然后使用 `view_file` 查看这些图像以读取和转录内容。当用户要求使用模型来提取文字时，也这样做，无论 OCR 效果如何或者用户是否提及 OCR。

## 何时使用
- 明确要求**不要**使用 OCR 从 PDF 提取文本。
- `PyPDF2` 或类似工具返回乱码、丢失结构信息或完全无法提取文本。
- PDF 包含复杂的布局、图表或图像，准确提取需要视觉上下文的支持。
- 当用户要求使用模型来提取文字时，也这样做，无论 OCR 效果如何或者用户是否提及 OCR。

## 核心模式

1. **编写提取脚本：** 编写一个 Python 脚本，使用 `PyMuPDF` (`fitz`) 将目标 PDF 页面转换为图像。
2. **执行脚本：** 使用 `uv run --with PyMuPDF python3 <script_name>.py <pdf_path> <output_dir>` 运行该脚本。
3. **查看图像：** 使用 `view_file` 工具可视化检查每个生成的图像。
4. **转录：** 根据看到的视觉信息转录或处理文本。

## 快速参考
| 步骤 | 操作 | 工具 / 命令 |
|---|---|---|
| 1. 编写脚本 | 编写 PyMuPDF 转换脚本 | `write_to_file` |
| 2. 执行 | 使用 `uv run` 运行脚本 | `run_command` 和 `uv run --with PyMuPDF python3 ...` |
| 3. 查看 | 检查生成的图像 | `view_file` |
| 4. 提取 | 从图像中处理文本 | 模型的视觉多模态能力 |

## 实现方式

编写如下所示的脚本将 PDF 转换为图像：

```python
import fitz
import sys
import os

pdf_path = sys.argv[1]
output_dir = sys.argv[2]

try:
    doc = fitz.open(pdf_path)
    # 定义要提取的页面 (例如, 前 10 页)
    num_pages = min(10, len(doc))
    for i in range(num_pages):
        page = doc.load_page(i)
        pix = page.get_pixmap()
        output_path = os.path.join(output_dir, f"page_{i+1:02d}.png")
        pix.save(output_path)
    print(f"Successfully extracted {num_pages} pages to {output_dir}")
except Exception as e:
    print(f"Error: {e}")
```

然后运行它：
```bash
uv run --with PyMuPDF python3 extract_script.py "/path/to/input.pdf" "/path/to/output_dir"
```

接着使用 `view_file` 查看 `/path/to/output_dir/page_01.png` 等文件以读取内容。

## 常见错误
- **忘记使用 `uv run`：** 如果未全局安装 `PyMuPDF`，标准的 `python3` 将会失败。始终使用 `uv run --with PyMuPDF python3` 以确保依赖可用。
- **一次提取过多页面：** 如果只需要几页，请避免一次性提取数百页，因为查看每张图像非常耗时且占用大量上下文。请指定所需的确切范围。
- **对图像使用通用文本工具：** 不要对生成的 PNG 文件使用 `cat` 或 `grep`。请使用 `view_file`，以便多模态视觉能力能够处理图像。
