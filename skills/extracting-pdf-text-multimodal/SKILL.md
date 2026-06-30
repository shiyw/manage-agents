---
name: extracting-pdf-text-multimodal
description: Use when you need to extract text or structured content from a PDF file without using OCR, or when traditional PDF parsing libraries fail to capture the layout, structure, or content correctly.
---

# Extracting PDF Text via Multimodal

## Overview
When traditional PDF text extraction (like `PyPDF2`) fails or OCR is explicitly forbidden, you can leverage your multimodal capabilities by first converting PDF pages to images using PyMuPDF (`fitz`), and then viewing those images with `view_file` to read and transcribe the content.

## When to Use
- You are explicitly asked NOT to use OCR to extract text from a PDF.
- `PyPDF2` or similar tools return garbled text, lose structural information, or fail to extract text entirely.
- The PDF contains complex layouts, charts, or images where visual context is necessary for accurate extraction.

## Core Pattern

1. **Write an extraction script:** Write a Python script to convert the target PDF pages into images using `PyMuPDF` (`fitz`).
2. **Execute the script:** Run the script using `uv run --with PyMuPDF python3 <script_name>.py <pdf_path> <output_dir>`.
3. **View the images:** Use the `view_file` tool to visually inspect each generated image.
4. **Transcribe:** Transcribe or process the text based on the visual information you see.

## Quick Reference
| Step | Action | Tool / Command |
|---|---|---|
| 1. Scripting | Write PyMuPDF conversion script | `write_to_file` |
| 2. Execution | Run the script with `uv run` | `run_command` with `uv run --with PyMuPDF python3 ...` |
| 3. Viewing | Inspect generated images | `view_file` |
| 4. Extraction | Process text from images | Model's multimodal capability |

## Implementation

Write a script like the following to convert PDF to images:

```python
import fitz
import sys
import os

pdf_path = sys.argv[1]
output_dir = sys.argv[2]

try:
    doc = fitz.open(pdf_path)
    # Define pages to extract (e.g., first 10 pages)
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

Then run it:
```bash
uv run --with PyMuPDF python3 extract_script.py "/path/to/input.pdf" "/path/to/output_dir"
```

Then use `view_file` on `/path/to/output_dir/page_01.png`, etc., to read the content.

## Common Mistakes
- **Forgetting to use `uv run`:** If `PyMuPDF` is not installed globally, standard `python3` will fail. Always use `uv run --with PyMuPDF python3` to ensure the dependency is available.
- **Extracting too many pages at once:** Avoid extracting hundreds of pages at once if you only need a few, as viewing each image is time-consuming and context-heavy. Specify the exact range needed.
- **Using general text tools on the images:** Don't use `cat` or `grep` on the generated PNG files. Use `view_file` so your multimodal vision can process the image.
