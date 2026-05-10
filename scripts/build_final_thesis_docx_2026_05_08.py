from pathlib import Path

import build_final_thesis_docx as base


ROOT = Path(r"E:\goldphish\goldphish-main\goldphish-main")

base.SOURCE_DOCX = ROOT / "output" / "\u6bd5\u4e1a\u8bbe\u8ba1_\u8bba\u6587\u5b8c\u5584\u7248_2026-05-05.docx"
base.DEST_DOCX = ROOT / "output" / "\u6bd5\u4e1a\u8bbe\u8ba1_\u8bba\u6587\u5b8c\u5584\u7248_2026-05-08_\u4fee\u8ba2\u7248.docx"
base.MD_PATH = ROOT / "output" / "thesis_partial_draft_2026-05-08.md"


if __name__ == "__main__":
    base.main()
