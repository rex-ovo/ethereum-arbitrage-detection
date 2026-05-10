import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(r"E:\goldphish\goldphish-main\goldphish-main")
DOCX_PATH = ROOT / "output" / "毕业设计_论文填充版.docx"
MD_PATH = ROOT / "output" / "thesis_partial_draft_2026-04-22.md"


def read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def split_front_matter(md: str):
    title = ""
    chinese_abstract = ""
    english_abstract = ""
    body = ""

    m = re.search(r"^#\s+(.+)$", md, re.M)
    if m:
        title = m.group(1).strip()

    m = re.search(r"##\s+摘要\s*\n+(.*?)\n+##\s+Abstract", md, re.S)
    if m:
        chinese_abstract = m.group(1).strip()

    m = re.search(r"##\s+Abstract\s*\n+(.*?)\n+#\s+1\s+绪论", md, re.S)
    if m:
        english_abstract = m.group(1).strip()

    m = re.search(r"\n(#\s+1\s+绪论.*)$", md, re.S)
    if m:
        body = m.group(1).strip()

    return title, chinese_abstract, english_abstract, body


def extract_original_parts(docx_path: Path):
    with zipfile.ZipFile(docx_path, "r") as zf:
        raw = zf.read("word/document.xml").decode("utf-8")

    prefix_match = re.search(r"^(<\?xml.*?<w:document\b.*?<w:body>)", raw, re.S)
    suffix_match = re.search(r"(</w:body></w:document>)\s*$", raw, re.S)
    sect_matches = re.findall(r"(<w:sectPr\b.*?</w:sectPr>)", raw, re.S)
    if not prefix_match or not suffix_match or not sect_matches:
        raise RuntimeError("Unable to parse template document.xml structure.")

    return prefix_match.group(1), sect_matches[-1], suffix_match.group(1)


def page_break_para() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def para(text: str, style: str = None, align: str = None, bold: bool = False, size: int = None) -> str:
    text = text.rstrip()
    if not text:
        return '<w:p/>'

    ppr = []
    if style:
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    ppr_xml = f"<w:pPr>{''.join(ppr)}</w:pPr>" if ppr else ""

    rpr = []
    if bold:
        rpr.append("<w:b/>")
        rpr.append("<w:bCs/>")
    if size:
        rpr.append(f"<w:sz w:val=\"{size}\"/>")
        rpr.append(f"<w:szCs w:val=\"{size}\"/>")
    rpr_xml = f"<w:rPr>{''.join(rpr)}</w:rPr>" if rpr else ""

    safe = escape(text)
    return f"<w:p>{ppr_xml}<w:r>{rpr_xml}<w:t xml:space=\"preserve\">{safe}</w:t></w:r></w:p>"


def field_toc() -> str:
    return (
        "<w:p><w:pPr><w:jc w:val=\"center\"/></w:pPr>"
        "<w:r><w:fldChar w:fldCharType=\"begin\"/></w:r>"
        "<w:r><w:instrText xml:space=\"preserve\"> TOC \\\\o \"1-3\" \\\\h \\\\z \\\\u </w:instrText></w:r>"
        "<w:r><w:fldChar w:fldCharType=\"separate\"/></w:r>"
        "<w:r><w:t>目录（请在 Word 中右键更新域）</w:t></w:r>"
        "<w:r><w:fldChar w:fldCharType=\"end\"/></w:r>"
        "</w:p>"
    )


def parse_body_blocks(body_md: str):
    lines = body_md.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue

        if line.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].rstrip())
                i += 1
            blocks.append(("table", table_lines))
            continue

        if re.match(r"^#{1,3}\s+", line):
            level = len(line) - len(line.lstrip("#"))
            text = re.sub(r"^#{1,3}\s+", "", line).strip()
            blocks.append(("heading", level, text))
            i += 1
            continue

        para_lines = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i].rstrip()
            if not nxt.strip():
                i += 1
                break
            if nxt.startswith("|") or re.match(r"^#{1,3}\s+", nxt):
                break
            para_lines.append(nxt)
            i += 1
        text = " ".join(x.strip() for x in para_lines)
        blocks.append(("para", text))
    return blocks


def make_table(table_lines):
    rows = []
    for idx, line in enumerate(table_lines):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if idx == 1 and all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue
        rows.append(cells)

    xml_rows = []
    for r_idx, row in enumerate(rows):
        tcs = []
        for cell in row:
            cell_text = escape(cell)
            if r_idx == 0:
                p = (
                    '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
                    '<w:r><w:rPr><w:b/><w:bCs/></w:rPr>'
                    f'<w:t xml:space="preserve">{cell_text}</w:t></w:r></w:p>'
                )
            else:
                p = f'<w:p><w:r><w:t xml:space="preserve">{cell_text}</w:t></w:r></w:p>'
            tcs.append(
                "<w:tc><w:tcPr><w:tcW w:w=\"1800\" w:type=\"dxa\"/></w:tcPr>"
                f"{p}</w:tc>"
            )
        xml_rows.append("<w:tr>" + "".join(tcs) + "</w:tr>")
    return (
        "<w:tbl>"
        "<w:tblPr><w:tblStyle w:val=\"aff4\"/>"
        "<w:tblW w:w=\"0\" w:type=\"auto\"/>"
        "<w:tblBorders>"
        "<w:top w:val=\"single\" w:sz=\"8\" w:space=\"0\" w:color=\"000000\"/>"
        "<w:left w:val=\"single\" w:sz=\"8\" w:space=\"0\" w:color=\"000000\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"8\" w:space=\"0\" w:color=\"000000\"/>"
        "<w:right w:val=\"single\" w:sz=\"8\" w:space=\"0\" w:color=\"000000\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"000000\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"000000\"/>"
        "</w:tblBorders></w:tblPr>"
        + "".join(xml_rows) +
        "</w:tbl>"
    )


def build_document_xml(prefix: str, sectpr: str, suffix: str, title: str, zh_abs: str, en_abs: str, body_md: str) -> str:
    parts = []

    parts.append(para("2026届本科生毕业论文（设计）", align="center", bold=True, size=32))
    parts.append(para("", align="center"))
    parts.append(para(title, align="center", bold=True, size=32))
    parts.append(para("", align="center"))
    parts.append(para("学生姓名：唐睿", align="center"))
    parts.append(para("学号：3220103690", align="center"))
    parts.append(para("学院：待按学校模板补充", align="center"))
    parts.append(para("行政班级：待按学校模板补充", align="center"))
    parts.append(para("指导教师：待按学校模板补充", align="center"))
    parts.append(para("完成时间：2026年", align="center"))

    parts.append(page_break_para())
    parts.append(para("摘  要", style="a0"))
    for p in [x.strip() for x in zh_abs.split("\n\n") if x.strip()]:
        if p.startswith("关键词："):
            parts.append(para(p, style="a7"))
        else:
            parts.append(para(p, style="a7"))

    parts.append(page_break_para())
    parts.append(para("Abstract", style="a0"))
    for p in [x.strip() for x in en_abs.split("\n\n") if x.strip()]:
        parts.append(para(p, style="a7"))

    parts.append(page_break_para())
    parts.append(para("目  录", style="a0"))
    parts.append(field_toc())

    current_level1_started = False
    for block in parse_body_blocks(body_md):
        kind = block[0]
        if kind == "heading":
            _, level, text = block
            if level == 1:
                if current_level1_started:
                    parts.append(page_break_para())
                current_level1_started = True
                parts.append(para(text, style="a0"))
            elif level == 2:
                parts.append(para(text, style="a8"))
            elif level == 3:
                parts.append(para(text, style="a9"))
        elif kind == "para":
            _, text = block
            parts.append(para(text, style="a7"))
        elif kind == "table":
            _, table_lines = block
            parts.append(make_table(table_lines))

    body_xml = "".join(parts) + sectpr
    return prefix + body_xml + suffix


def replace_document_xml(docx_path: Path, new_xml: str):
    tmp_path = docx_path.with_suffix(".tmp.docx")
    with zipfile.ZipFile(docx_path, "r") as zin, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = new_xml.encode("utf-8")
            zout.writestr(item, data)
    tmp_path.replace(docx_path)


def main():
    md = read_markdown(MD_PATH)
    title, zh_abs, en_abs, body = split_front_matter(md)
    prefix, sectpr, suffix = extract_original_parts(DOCX_PATH)
    new_xml = build_document_xml(prefix, sectpr, suffix, title, zh_abs, en_abs, body)
    replace_document_xml(DOCX_PATH, new_xml)
    print(DOCX_PATH)


if __name__ == "__main__":
    main()
