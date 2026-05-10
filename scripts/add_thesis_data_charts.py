from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
FIG_DIR = OUTPUT / "thesis_figures_2026_05_08"
SOURCE_DOCX = OUTPUT / "毕业设计_论文完善版_2026-05-08_修订版.docx"
DEST_DOCX = OUTPUT / "毕业设计_论文完善版_2026-05-08_图表增强版.docx"


def configure_matplotlib() -> None:
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 220


def insert_paragraph_after(paragraph, text: str = ""):
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = paragraph._parent.add_paragraph()
    new_para._p = new_p
    if text:
        new_para.add_run(text)
    return new_para


def format_caption(paragraph, text: str) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(text)
    run.bold = True
    run.font.name = "宋体"
    run._element.rPr.rFonts.set(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia",
        "宋体",
    )
    run.font.size = Pt(10.5)


def format_blank(paragraph) -> None:
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(12)
    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE


def add_figure_after(anchor, image_path: Path, caption: str, width: float = 5.8):
    image_para = insert_paragraph_after(anchor)
    image_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    image_para.paragraph_format.space_before = Pt(6)
    image_para.paragraph_format.space_after = Pt(0)
    run = image_para.add_run()
    run.add_picture(str(image_path), width=Inches(width))

    caption_para = insert_paragraph_after(image_para)
    format_caption(caption_para, caption)

    blank_para = insert_paragraph_after(caption_para)
    format_blank(blank_para)
    return blank_para


def find_paragraph(doc: Document, exact_text: str):
    for para in doc.paragraphs:
        if para.text.strip() == exact_text:
            return para
    raise ValueError(f"Paragraph not found: {exact_text}")


def make_chart_baseline_vs_ours(path: Path) -> None:
    methods = ["Baseline", "协议语义过滤"]
    totals = [2460, 2202]
    fps = [382, 125]

    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    x = range(len(methods))
    w = 0.32
    ax.bar([i - w / 2 for i in x], totals, width=w, label="候选样本数", color="#4C78A8")
    ax.bar([i + w / 2 for i in x], fps, width=w, label="误报样本数", color="#E45756")
    ax.set_xticks(list(x))
    ax.set_xticklabels(methods)
    ax.set_ylabel("样本数")
    ax.set_title("局部验证区间中 baseline 与协议语义过滤方法的样本对比")
    ax.legend(frameon=False)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    for i, v in enumerate(totals):
        ax.text(i - w / 2, v + 35, str(v), ha="center", va="bottom", fontsize=9)
    for i, v in enumerate(fps):
        ax.text(i + w / 2, v + 18, str(v), ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def make_chart_fp_reasons(path: Path) -> None:
    reasons = ["CoW Swap", "odd token", "relayer", "tokenlon"]
    baseline = [188, 143, 66, 3]
    ours = [0, 125, 0, 0]

    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    x = range(len(reasons))
    w = 0.32
    ax.bar([i - w / 2 for i in x], baseline, width=w, label="Baseline", color="#72B7B2")
    ax.bar([i + w / 2 for i in x], ours, width=w, label="协议语义过滤", color="#F58518")
    ax.set_xticks(list(x))
    ax.set_xticklabels(reasons, rotation=10)
    ax.set_ylabel("误报样本数")
    ax.set_title("局部验证区间中误报原因构成对比")
    ax.legend(frameon=False)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    for i, v in enumerate(baseline):
        ax.text(i - w / 2, v + 4, str(v), ha="center", va="bottom", fontsize=8.5)
    for i, v in enumerate(ours):
        ax.text(i + w / 2, v + 4, str(v), ha="center", va="bottom", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def make_chart_cycle_distribution(path: Path) -> None:
    cycles = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 21, 25, 29, 36]
    counts = [14297, 1328, 299, 116, 63, 23, 19, 7, 5, 6, 4, 3, 1, 2, 1, 1, 1, 1, 1]

    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.bar([str(c) for c in cycles], counts, color="#54A24B")
    ax.set_ylabel("样本数")
    ax.set_xlabel("环数")
    ax.set_title("大范围阶段性样本的环数分布")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.text(0, counts[0] + 240, str(counts[0]), ha="center", va="bottom", fontsize=8.5)
    ax.text(1, counts[1] + 70, str(counts[1]), ha="center", va="bottom", fontsize=8.5)
    ax.text(2, counts[2] + 25, str(counts[2]), ha="center", va="bottom", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def make_chart_profit_tokens(path: Path) -> None:
    tokens = ["WETH", "USDC", "USDT", "PAXG", "WBTC"]
    counts = [9386, 1302, 1232, 589, 301]

    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    bars = ax.bar(tokens, counts, color=["#4C78A8", "#72B7B2", "#F58518", "#E45756", "#54A24B"])
    ax.set_ylabel("样本数")
    ax.set_title("大范围阶段性样本的主要利润 token 分布（前五）")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    for bar, value in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 60, str(value), ha="center", va="bottom", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def make_chart_method_compare(path: Path) -> None:
    methods = ["Transfer-only", "Swap-only", "Hybrid(v2)", "Hybrid(v2+v3)"]
    counts = [2460, 0, 3, 8]

    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    bars = ax.bar(methods, counts, color=["#4C78A8", "#B279A2", "#F58518", "#54A24B"])
    ax.set_ylabel("识别样本数")
    ax.set_title("多事件融合实验的样本数量对比")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    for bar, value in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 35, str(value), ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def generate_figures() -> dict[str, Path]:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    configure_matplotlib()

    files = {
        "baseline_vs_ours": FIG_DIR / "figure_5_2_baseline_vs_ours.png",
        "fp_reasons": FIG_DIR / "figure_5_3_fp_reasons.png",
        "cycle_distribution": FIG_DIR / "figure_5_4_cycle_distribution.png",
        "profit_tokens": FIG_DIR / "figure_5_5_profit_tokens.png",
        "method_compare": FIG_DIR / "figure_5_6_method_compare.png",
    }
    make_chart_baseline_vs_ours(files["baseline_vs_ours"])
    make_chart_fp_reasons(files["fp_reasons"])
    make_chart_cycle_distribution(files["cycle_distribution"])
    make_chart_profit_tokens(files["profit_tokens"])
    make_chart_method_compare(files["method_compare"])
    return files


def patch_docx(figure_files: dict[str, Path]) -> None:
    doc = Document(str(SOURCE_DOCX))

    anchor = find_paragraph(doc, "5.2.3 样本结构与利润 token 分布")
    anchor = add_figure_after(anchor, figure_files["cycle_distribution"], "图5-2 大范围阶段性样本的环数分布")
    anchor = add_figure_after(anchor, figure_files["profit_tokens"], "图5-3 大范围阶段性样本的主要利润 token 分布（前五）")

    anchor = find_paragraph(doc, "5.3.1 样本规模与误报率变化")
    add_figure_after(anchor, figure_files["baseline_vs_ours"], "图5-4 局部验证区间中 baseline 与协议语义过滤方法的样本对比")

    anchor = find_paragraph(doc, "5.3.2 误报来源变化")
    add_figure_after(anchor, figure_files["fp_reasons"], "图5-5 局部验证区间中误报原因构成对比")

    anchor = find_paragraph(doc, "5.4.5 融合实验的总体结论")
    add_figure_after(anchor, figure_files["method_compare"], "图5-6 多事件融合实验的样本数量对比")

    doc.save(str(DEST_DOCX))


def main() -> None:
    if not SOURCE_DOCX.exists():
        raise FileNotFoundError(SOURCE_DOCX)
    figure_files = generate_figures()
    patch_docx(figure_files)
    print(DEST_DOCX)


if __name__ == "__main__":
    main()
