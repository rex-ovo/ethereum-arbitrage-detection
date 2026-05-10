from pathlib import Path

import build_final_thesis_docx as base


ROOT = Path(r"E:\goldphish\goldphish-main\goldphish-main")

base.SOURCE_DOCX = ROOT / "output" / "毕业设计_论文完善版_2026-04-29.docx"
base.DEST_DOCX = ROOT / "output" / "毕业设计_论文完善版_2026-05-05.docx"
base.MD_PATH = ROOT / "output" / "thesis_partial_draft_2026-05-05.md"


if __name__ == "__main__":
    base.main()
