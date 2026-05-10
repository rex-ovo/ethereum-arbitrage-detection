import re
import shutil
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree


ROOT = Path(r"E:\goldphish\goldphish-main\goldphish-main")
SOURCE_DOCX = ROOT / "output" / "毕业设计_论文填充版.docx"
DEST_DOCX = ROOT / "output" / "毕业设计_论文完善版_2026-04-29.docx"
MD_PATH = ROOT / "output" / "thesis_partial_draft_2026-04-29.md"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def clean_inline(text: str) -> str:
    text = text.replace("`", "")
    text = text.replace("\u00a0", " ")
    return text.strip()


def split_front_matter(md: str):
    title = ""
    chinese_abstract = ""
    english_abstract = ""
    body = ""

    m = re.search(r"^#\s+(.+)$", md, re.M)
    if m:
        title = clean_inline(m.group(1))

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


def run_props(*, bold=False, size=None, ascii_font=None, east_font=None):
    props = []
    if bold:
        props.append("<w:b/>")
        props.append("<w:bCs/>")
    if ascii_font or east_font:
        attrs = []
        if ascii_font:
            attrs.append(f'w:ascii="{ascii_font}"')
            attrs.append(f'w:hAnsi="{ascii_font}"')
        if east_font:
            attrs.append(f'w:eastAsia="{east_font}"')
        props.append(f"<w:rFonts {' '.join(attrs)}/>")
    if size:
        props.append(f'<w:sz w:val="{size}"/>')
        props.append(f'<w:szCs w:val="{size}"/>')
    return "".join(props)


def para(
    text: str,
    *,
    style: str | None = None,
    align: str | None = None,
    bold: bool = False,
    size: int | None = None,
    ascii_font: str | None = None,
    east_font: str | None = None,
    first_line_chars: int | None = None,
    line: int | None = None,
    line_rule: str = "auto",
    before: int | None = None,
    after: int | None = None,
    hanging_chars: int | None = None,
) -> str:
    text = clean_inline(text)
    if not text:
        return "<w:p/>"

    ppr = []
    if style:
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    if any(v is not None for v in [before, after, line]):
        attrs = []
        if before is not None:
            attrs.append(f'w:before="{before}"')
        if after is not None:
            attrs.append(f'w:after="{after}"')
        if line is not None:
            attrs.append(f'w:line="{line}"')
            attrs.append(f'w:lineRule="{line_rule}"')
        ppr.append(f"<w:spacing {' '.join(attrs)}/>")
    if first_line_chars is not None:
        ppr.append(f'<w:ind w:firstLineChars="{first_line_chars}" w:firstLine="{first_line_chars}"/>')
    if hanging_chars is not None:
        ppr.append(f'<w:ind w:hangingChars="{hanging_chars}" w:hanging="{hanging_chars}"/>')
    ppr_xml = f"<w:pPr>{''.join(ppr)}</w:pPr>" if ppr else ""

    rpr_xml = run_props(
        bold=bold,
        size=size,
        ascii_font=ascii_font,
        east_font=east_font,
    )
    rpr_xml = f"<w:rPr>{rpr_xml}</w:rPr>" if rpr_xml else ""
    safe = escape(text)
    return f'<w:p>{ppr_xml}<w:r>{rpr_xml}<w:t xml:space="preserve">{safe}</w:t></w:r></w:p>'


def field_toc() -> str:
    return (
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:instrText xml:space="preserve"> TOC \\\\o "1-3" \\\\h \\\\z \\\\u </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        '<w:r><w:t>目录（请在 Word 中右键更新域）</w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
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
            text = clean_inline(re.sub(r"^#{1,3}\s+", "", line))
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
        text = clean_inline(" ".join(x.strip() for x in para_lines))
        blocks.append(("para", text))
    return blocks


def is_table_caption(text: str) -> bool:
    return bool(re.match(r"^表\s*\d", text)) or bool(re.match(r"^图\s*\d", text))


def is_reference_item(text: str) -> bool:
    return bool(re.match(r"^\[\d+\]", text))


def make_table(table_lines):
    rows = []
    for idx, line in enumerate(table_lines):
        cells = [clean_inline(c) for c in line.strip().strip("|").split("|")]
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
                    '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:line="240" w:lineRule="auto"/></w:pPr>'
                    '<w:r><w:rPr>'
                    + run_props(bold=True, size=21, ascii_font="Times New Roman", east_font="宋体")
                    + f'</w:rPr><w:t xml:space="preserve">{cell_text}</w:t></w:r></w:p>'
                )
            else:
                p = (
                    '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:line="240" w:lineRule="auto"/></w:pPr>'
                    '<w:r><w:rPr>'
                    + run_props(size=21, ascii_font="Times New Roman", east_font="宋体")
                    + f'</w:rPr><w:t xml:space="preserve">{cell_text}</w:t></w:r></w:p>'
                )
            tcs.append(
                "<w:tc>"
                "<w:tcPr>"
                '<w:tcW w:w="1800" w:type="dxa"/>'
                '<w:vAlign w:val="center"/>'
                "<w:tcMar>"
                '<w:top w:w="80" w:type="dxa"/>'
                '<w:left w:w="80" w:type="dxa"/>'
                '<w:bottom w:w="80" w:type="dxa"/>'
                '<w:right w:w="80" w:type="dxa"/>'
                "</w:tcMar>"
                "</w:tcPr>"
                f"{p}</w:tc>"
            )
        xml_rows.append("<w:tr>" + "".join(tcs) + "</w:tr>")
    return (
        "<w:tbl>"
        '<w:tblPr><w:tblStyle w:val="aff4"/>'
        '<w:tblW w:w="0" w:type="auto"/>'
        "<w:tblCellMar>"
        '<w:top w:w="80" w:type="dxa"/>'
        '<w:left w:w="80" w:type="dxa"/>'
        '<w:bottom w:w="80" w:type="dxa"/>'
        '<w:right w:w="80" w:type="dxa"/>'
        "</w:tblCellMar>"
        "<w:tblBorders>"
        '<w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:left w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:right w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:insideH w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
        '<w:insideV w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
        "</w:tblBorders></w:tblPr>"
        + "".join(xml_rows)
        + "</w:tbl>"
    )


def build_document_xml(prefix: str, sectpr: str, suffix: str, title: str, zh_abs: str, en_abs: str, body_md: str) -> str:
    parts = []

    parts.append(para("2026届本科生毕业论文（设计）", align="center", bold=True, size=32, ascii_font="Times New Roman", east_font="仿宋_GB2312"))
    parts.append(para("", align="center"))
    parts.append(para(title, align="center", bold=True, size=32, ascii_font="Times New Roman", east_font="仿宋_GB2312"))
    parts.append(para("", align="center"))
    parts.append(para("学生姓名：唐睿", align="center", size=30, ascii_font="Times New Roman", east_font="仿宋_GB2312"))
    parts.append(para("学号：3220103690", align="center", size=30, ascii_font="Times New Roman", east_font="仿宋_GB2312"))
    parts.append(para("学院：待按学校模板填写", align="center", size=30, ascii_font="Times New Roman", east_font="仿宋_GB2312"))
    parts.append(para("行政班级：待按学校模板填写", align="center", size=30, ascii_font="Times New Roman", east_font="仿宋_GB2312"))
    parts.append(para("指导教师：待按学校模板填写", align="center", size=30, ascii_font="Times New Roman", east_font="仿宋_GB2312"))
    parts.append(para("完成时间：2026年", align="center", size=30, ascii_font="Times New Roman", east_font="仿宋_GB2312"))

    parts.append(page_break_para())
    parts.append(para("摘要", style="a0"))
    for p in [x.strip() for x in zh_abs.split("\n\n") if x.strip()]:
        parts.append(para(p, style="a7"))

    parts.append(page_break_para())
    parts.append(para("Abstract", style="a0", ascii_font="Times New Roman", east_font="仿宋_GB2312"))
    for p in [x.strip() for x in en_abs.split("\n\n") if x.strip()]:
        parts.append(para(p, style="a7", ascii_font="Times New Roman", east_font="仿宋_GB2312"))

    parts.append(page_break_para())
    parts.append(para("目录", style="a0"))
    parts.append(field_toc())

    blocks = parse_body_blocks(body_md)
    current_level1_started = False
    for idx, block in enumerate(blocks):
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
            next_kind = blocks[idx + 1][0] if idx + 1 < len(blocks) else None
            if next_kind == "table" and is_table_caption(text):
                parts.append(
                    para(
                        text,
                        align="center",
                        bold=True,
                        size=21,
                        ascii_font="Times New Roman",
                        east_font="宋体",
                        line=240,
                        after=120,
                    )
                )
            elif is_reference_item(text):
                parts.append(
                    para(
                        text,
                        size=21,
                        ascii_font="Times New Roman",
                        east_font="宋体",
                        line=360,
                        hanging_chars=200,
                    )
                )
            else:
                parts.append(para(text, style="a7"))
        elif kind == "table":
            _, table_lines = block
            parts.append(make_table(table_lines))
            parts.append(para(""))

    body_xml = "".join(parts) + sectpr
    return prefix + body_xml + suffix


def set_font(rpr, east_font, ascii_font, size, bold=None):
    rfonts = rpr.find("w:rFonts", NS)
    if rfonts is None:
        rfonts = etree.SubElement(rpr, f"{{{W_NS}}}rFonts")
    rfonts.set(f"{{{W_NS}}}ascii", ascii_font)
    rfonts.set(f"{{{W_NS}}}hAnsi", ascii_font)
    rfonts.set(f"{{{W_NS}}}eastAsia", east_font)

    sz = rpr.find("w:sz", NS)
    if sz is None:
        sz = etree.SubElement(rpr, f"{{{W_NS}}}sz")
    sz.set(f"{{{W_NS}}}val", str(size))

    szcs = rpr.find("w:szCs", NS)
    if szcs is None:
        szcs = etree.SubElement(rpr, f"{{{W_NS}}}szCs")
    szcs.set(f"{{{W_NS}}}val", str(size))

    if bold is not None:
        if bold:
            if rpr.find("w:b", NS) is None:
                etree.SubElement(rpr, f"{{{W_NS}}}b")
            if rpr.find("w:bCs", NS) is None:
                etree.SubElement(rpr, f"{{{W_NS}}}bCs")
        else:
            for tag in ["b", "bCs"]:
                el = rpr.find(f"w:{tag}", NS)
                if el is not None:
                    rpr.remove(el)


def patch_style(root, sid, *, east_font, ascii_font, size, bold, jc=None, line=None, first_line=None, outline=None):
    style = root.xpath(f'//w:style[@w:styleId="{sid}"]', namespaces=NS)[0]
    ppr = style.find("w:pPr", NS)
    if ppr is None:
        ppr = etree.SubElement(style, f"{{{W_NS}}}pPr")
    rpr = style.find("w:rPr", NS)
    if rpr is None:
        rpr = etree.SubElement(style, f"{{{W_NS}}}rPr")
    set_font(rpr, east_font, ascii_font, size, bold)

    if jc:
        jc_el = ppr.find("w:jc", NS)
        if jc_el is None:
            jc_el = etree.SubElement(ppr, f"{{{W_NS}}}jc")
        jc_el.set(f"{{{W_NS}}}val", jc)

    if line is not None:
        spacing = ppr.find("w:spacing", NS)
        if spacing is None:
            spacing = etree.SubElement(ppr, f"{{{W_NS}}}spacing")
        spacing.set(f"{{{W_NS}}}line", str(line))
        spacing.set(f"{{{W_NS}}}lineRule", "auto")

    if first_line is not None:
        ind = ppr.find("w:ind", NS)
        if ind is None:
            ind = etree.SubElement(ppr, f"{{{W_NS}}}ind")
        ind.set(f"{{{W_NS}}}firstLineChars", str(first_line))
        ind.set(f"{{{W_NS}}}firstLine", str(first_line))

    if outline is not None:
        outline_el = ppr.find("w:outlineLvl", NS)
        if outline_el is None:
            outline_el = etree.SubElement(ppr, f"{{{W_NS}}}outlineLvl")
        outline_el.set(f"{{{W_NS}}}val", str(outline))


def patch_styles_xml(styles_xml: bytes) -> bytes:
    root = etree.fromstring(styles_xml)
    patch_style(root, "a0", east_font="仿宋_GB2312", ascii_font="Times New Roman", size=32, bold=True, jc="center", line=360, outline=0)
    patch_style(root, "a8", east_font="仿宋_GB2312", ascii_font="Times New Roman", size=30, bold=True, jc="both", line=360, outline=1)
    patch_style(root, "a9", east_font="仿宋_GB2312", ascii_font="Times New Roman", size=28, bold=True, jc="both", line=360, outline=2)
    patch_style(root, "aa", east_font="仿宋_GB2312", ascii_font="Times New Roman", size=24, bold=True, jc="both", line=360, outline=3)
    patch_style(root, "a7", east_font="仿宋_GB2312", ascii_font="Times New Roman", size=24, bold=False, jc="both", line=360, first_line=200)
    patch_style(root, "a2", east_font="仿宋_GB2312", ascii_font="Times New Roman", size=24, bold=False, jc="both", line=360, first_line=200)
    return etree.tostring(root, encoding="utf-8", xml_declaration=True, standalone="yes")


def replace_docx_parts(src: Path, dest: Path, new_document_xml: str):
    tmp_path = dest.with_suffix(".tmp.docx")
    with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = new_document_xml.encode("utf-8")
            elif item.filename == "word/styles.xml":
                data = patch_styles_xml(data)
            zout.writestr(item, data)
    tmp_path.replace(dest)


def main():
    if not SOURCE_DOCX.exists():
        raise FileNotFoundError(SOURCE_DOCX)
    md = read_markdown(MD_PATH)
    title, zh_abs, en_abs, body = split_front_matter(md)
    prefix, sectpr, suffix = extract_original_parts(SOURCE_DOCX)
    new_xml = build_document_xml(prefix, sectpr, suffix, title, zh_abs, en_abs, body)
    shutil.copyfile(SOURCE_DOCX, DEST_DOCX)
    replace_docx_parts(SOURCE_DOCX, DEST_DOCX, new_xml)
    print(DEST_DOCX)


if __name__ == "__main__":
    main()
