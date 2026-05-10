from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


ROOT = Path(r"E:\goldphish\goldphish-main\goldphish-main")
FIG_DIR = ROOT / "output" / "thesis_figures_2026_05_07"
FIG_DIR.mkdir(parents=True, exist_ok=True)


plt.rcParams["font.sans-serif"] = [
    "SimHei",
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "Arial Unicode MS",
]
plt.rcParams["axes.unicode_minus"] = False


def draw_box_flow(filename: Path):
    fig, ax = plt.subplots(figsize=(14, 4.5))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 30)
    ax.axis("off")

    boxes = [
        (3, 10, 16, 10, "链上原始数据\n区块/交易/回执/日志"),
        (23, 10, 16, 10, "事件标准化\nTransfer / Swap / Token映射"),
        (43, 10, 16, 10, "交易图建模\nToken节点 + 资产流边"),
        (63, 10, 16, 10, "baseline识别\n闭环检测 + 利润判断"),
        (83, 10, 14, 10, "结果清洗与分析\n语义过滤 / 误报统计"),
    ]
    colors = ["#dbeafe", "#e0f2fe", "#ecfccb", "#fef3c7", "#fee2e2"]

    for idx, (x, y, w, h, text) in enumerate(boxes):
        patch = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.4,rounding_size=1.8",
            linewidth=1.5,
            edgecolor="#444444",
            facecolor=colors[idx],
        )
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=12)
        if idx < len(boxes) - 1:
            ax.annotate(
                "",
                xy=(boxes[idx + 1][0] - 1, y + h / 2),
                xytext=(x + w + 1, y + h / 2),
                arrowprops=dict(arrowstyle="->", lw=1.8, color="#333333"),
            )

    ax.text(
        50,
        26,
        "图3-1 以太坊原子套利识别的数据处理与分析流程",
        ha="center",
        va="center",
        fontsize=13,
        fontweight="bold",
    )
    plt.tight_layout()
    fig.savefig(filename, dpi=220, bbox_inches="tight")
    plt.close(fig)


def draw_semantic_filter_flow(filename: Path):
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    steps = [
        (35, 84, 30, 10, "候选交易与回执解析"),
        (35, 66, 30, 10, "Transfer主识别\n候选exchange提取"),
        (10, 46, 32, 12, "交易级协议过滤\nCoW / Tokenlon / Dexible"),
        (58, 46, 32, 12, "地址级角色过滤\nrouter / relayer / wrapper"),
        (35, 25, 30, 12, "误报标注与样本清洗\nodd token / false positive"),
        (35, 6, 30, 10, "保留高可信样本\nsample_arbitrages_no_fp"),
    ]
    colors = ["#e0f2fe", "#dbeafe", "#fef3c7", "#fef3c7", "#fee2e2", "#dcfce7"]

    for idx, (x, y, w, h, text) in enumerate(steps):
        patch = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.5,rounding_size=2.0",
            linewidth=1.5,
            edgecolor="#444444",
            facecolor=colors[idx],
        )
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=11)

    def arrow(x1, y1, x2, y2):
        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops=dict(arrowstyle="->", lw=1.8, color="#333333"),
        )

    arrow(50, 84, 50, 76)
    arrow(50, 66, 26, 58)
    arrow(50, 66, 74, 58)
    arrow(26, 46, 50, 37)
    arrow(74, 46, 50, 37)
    arrow(50, 25, 50, 16)

    ax.text(
        50,
        97,
        "图4-1 协议语义过滤优化方法的处理流程",
        ha="center",
        va="center",
        fontsize=13,
        fontweight="bold",
    )
    plt.tight_layout()
    fig.savefig(filename, dpi=220, bbox_inches="tight")
    plt.close(fig)


def draw_experiment_charts(filename: Path):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4))

    methods = ["Baseline", "Ours"]
    total = [2460, 2202]
    fp = [382, 125]
    no_fp = [2078, 2077]

    x = range(len(methods))
    width = 0.23
    axes[0].bar([i - width for i in x], total, width=width, label="候选样本数", color="#93c5fd")
    axes[0].bar(x, fp, width=width, label="误报样本数", color="#fca5a5")
    axes[0].bar([i + width for i in x], no_fp, width=width, label="过滤后样本数", color="#86efac")
    axes[0].set_xticks(list(x))
    axes[0].set_xticklabels(methods)
    axes[0].set_ylabel("样本数量")
    axes[0].set_title("局部验证区间样本对比")
    axes[0].legend(fontsize=9)

    methods2 = ["Swap-only", "Hybrid(v2)", "Hybrid(v2+v3)"]
    samples2 = [0, 3, 8]
    colors = ["#cbd5e1", "#fde68a", "#a7f3d0"]
    axes[1].bar(methods2, samples2, color=colors)
    axes[1].set_ylabel("识别样本数")
    axes[1].set_title("融合识别实验结果")
    for i, v in enumerate(samples2):
        axes[1].text(i, v + 0.2, str(v), ha="center", va="bottom", fontsize=10)

    fig.suptitle("图5-1 局部实验区间的识别结果与优化效果对比", fontsize=13, fontweight="bold")
    plt.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(filename, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    draw_box_flow(FIG_DIR / "figure_3_1_workflow.png")
    draw_semantic_filter_flow(FIG_DIR / "figure_4_1_semantic_filter.png")
    draw_experiment_charts(FIG_DIR / "figure_5_1_experiments.png")
    for p in FIG_DIR.glob("*.png"):
        print(p)


if __name__ == "__main__":
    main()
