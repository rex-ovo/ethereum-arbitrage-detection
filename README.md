# 基于交易图与协议语义过滤的以太坊原子套利识别方法研究

本仓库是本人本科毕业设计的代码仓库，研究主题为：

**基于交易图与协议语义过滤的以太坊原子套利识别方法研究**

项目以开源项目 **Goldphish** 为基础，围绕以太坊历史区块中的原子套利识别任务，完成了以下几类工作：

- 复现基于 `Transfer` 事件的原始候选套利识别流程。
- 补充链上历史数据抓取与样本落库的工程稳定性修补。
- 实现协议语义过滤优化，用于降低 CoW Swap、relayer、Tokenlon 等协议型误报。
- 设计并实现 `Swap-only` 与 `Hybrid` 两类多事件融合探索实验。
- 形成与毕业论文对应的局部对照实验与阶段性样本分析结果。

本 README 的目标不是完整介绍 Goldphish 的全部能力，而是帮助答辩老师、同学或复现实验的人快速理解：

- 仓库是做什么的
- 我在原项目上改了哪些部分
- 如何配置环境
- 如何运行与论文对应的关键实验

---

## 1. 仓库定位

该仓库主要用于**历史链上原子套利样本识别与分析**，并不面向实时交易执行。整体上可以分为两个方向：

1. **历史样本识别与后处理**
   - 目录：[`backtest/gather_samples`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples)
   - 用于从历史区块中识别候选套利样本、补充标签、分析误报来源。

2. **历史套利搜索与定价分析**
   - 目录：[`backtest/top_of_block`](E:/goldphish/goldphish-main/goldphish-main/backtest/top_of_block)
   - 属于原项目的另一部分，本毕设主要没有围绕这一部分展开实验。

因此，本毕业设计最核心的代码集中在：

- [`backtest/gather_samples/__main__.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/__main__.py)
- [`backtest/gather_samples/analyses.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/analyses.py)
- [`backtest/gather_samples/hybrid.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/hybrid.py)
- [`backtest/gather_samples/swap_only.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/swap_only.py)
- [`backtest/gather_samples/fill_false_positive/__main__.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/fill_false_positive/__main__.py)
- [`backtest/gather_samples/fill_odd_token_xfers/__main__.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/fill_odd_token_xfers/__main__.py)

---

## 2. 毕设工作概述

相较于原始 Goldphish，本仓库在毕业设计过程中主要完成了以下研究与实现工作。

### 2.1 `Transfer-only` baseline 复现

首先复现了原始基于 `Transfer` 事件的候选原子套利识别方法。该方法从交易回执中提取 ERC-20 `Transfer` 日志，构建 token 级别的局部交易图，并根据闭环结构与净收益判断候选套利样本。

对应代码主要位于：

- [`backtest/gather_samples/analyses.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/analyses.py)
- [`backtest/gather_samples/__main__.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/__main__.py)

### 2.2 工程稳定性修补

在真实历史区块抓取过程中，原脚本会受到 RPC 配额、WebSocket 断连和热点区间日志超限的影响。为此，本人补充了若干工程级稳定性改进，包括：

- `eth_getLogs` 超限后的自动拆分重试
- receipt 获取过程中的退避重试
- 局部实验区间的数据库重建与重复运行支持

这些修改保证了历史抓取实验可以持续推进，而不是在长时间运行中途直接中断。

### 2.3 协议语义过滤优化

在 baseline 运行完成后，通过误报分析发现，CoW Swap、relayer、Tokenlon 以及 odd token 行为是主要误差来源。基于此，本人实现了协议语义过滤优化，包括：

- 交易级协议过滤
- 地址级角色过滤
- 误报来源的结构化统计与对比

这部分是毕业设计的核心优化点。

### 2.4 多事件融合探索

为了评估 `Swap` 事件在原子套利识别中的作用，本人进一步实现了：

- `Swap-only`：仅依赖结构化 `Swap` 事件进行路径恢复
- `Hybrid`：以 `Transfer` 为主识别框架，利用 `Swap` 事件进行语义增强确认

实验结果表明：

- 纯 `Swap-only` 方法覆盖不足
- `Hybrid` 方法能提供少量高置信度样本
- 更合适的策略是：**Transfer 主框架 + 协议语义过滤 + Swap 语义增强**

---

## 3. 仓库结构说明

下面列出与本毕设最相关的目录：

```text
.
├─ abis/                         合约 ABI
├─ analysis_scripts/             一些分析辅助脚本
├─ backtest/
│  ├─ gather_samples/            毕设最核心的样本识别与分析代码
│  │  ├─ fill_known_exchanges/   已知 DEX / pool / swap 事件抓取
│  │  ├─ fill_false_positive/    误报标注
│  │  ├─ fill_odd_token_xfers/   odd token 标注
│  │  ├─ hybrid.py               Hybrid 融合实验
│  │  ├─ swap_only.py            Swap-only 实验
│  │  ├─ analyses.py             核心识别逻辑
│  │  └─ __main__.py             gather_samples 主入口
│  └─ top_of_block/              原项目的历史搜索部分
├─ contracts/                    Hardhat 合约
├─ output/                       论文草稿、图表、生成文档
├─ pricers/                      各类 DEX 定价模型
├─ scripts/                      论文文档生成、图表补充等脚本
├─ tests/                        回归测试与实验性测试
├─ Dockerfile                    Docker 构建文件
├─ requirements.txt              Python 依赖
└─ README.md                     当前说明文档
```

---

## 4. 环境要求

### 4.1 基本依赖

本项目主要依赖：

- Python 3
- PostgreSQL 14
- Docker
- 以太坊归档节点或等效 WebSocket RPC 服务

Python 依赖见：

- [`requirements.txt`](E:/goldphish/goldphish-main/goldphish-main/requirements.txt)

项目默认通过 Docker 运行，Docker 构建文件见：

- [`Dockerfile`](E:/goldphish/goldphish-main/goldphish-main/Dockerfile)

### 4.2 数据库要求

项目需要 PostgreSQL 数据库存储：

- 区块采样区间
- 已知交易所 / 池地址
- 候选套利样本
- 后处理标记结果

论文实验中使用的数据库容器名称为：

- `ethereum-measurement-pg`

数据库名通常为：

- `eth_measure_db`

---

## 5. 快速开始

下面的步骤适合复现实验链路。

### 5.1 构建镜像

```powershell
docker build -t goldphish .
```

### 5.2 创建 Docker 网络

```powershell
docker network create ethereum-measurement-net
```

### 5.3 启动 PostgreSQL

示例：

```powershell
docker run `
  -d `
  --name ethereum-measurement-pg `
  -e POSTGRES_PASSWORD=password `
  -e POSTGRES_USER=measure `
  -e POSTGRES_DB=eth_measure_db `
  -p 5410:5432 `
  -v E:\docker_data:/var/lib/postgresql/data `
  --network ethereum-measurement-net `
  postgres:14
```

### 5.4 初始化 `gather_samples` 相关表

```powershell
docker run --rm -t `
  --network ethereum-measurement-net `
  -v F:/STORAGE_DIR:/mnt/goldphish `
  -v E:\goldphish\goldphish-main\goldphish-main:/opt/goldphish `
  -w /opt/goldphish `
  goldphish python3 -m backtest.gather_samples --setup-db
```

### 5.5 初始化并抓取已知 exchange / swap 信息

```powershell
docker run --rm -t `
  --network ethereum-measurement-net `
  -v F:/STORAGE_DIR:/mnt/goldphish `
  -v E:\goldphish\goldphish-main\goldphish-main:/opt/goldphish `
  -w /opt/goldphish `
  goldphish python3 -m backtest.gather_samples.fill_known_exchanges --setup-db
```

```powershell
docker run --rm -t `
  --network ethereum-measurement-net `
  -v F:/STORAGE_DIR:/mnt/goldphish `
  -v E:\goldphish\goldphish-main\goldphish-main:/opt/goldphish `
  -w /opt/goldphish `
  -e WEB3_HOST=wss://YOUR_RPC_HOST `
  goldphish python3 -m backtest.gather_samples.fill_known_exchanges
```

### 5.6 运行 baseline 样本识别

```powershell
docker run --rm -t `
  --network ethereum-measurement-net `
  -v F:/STORAGE_DIR:/mnt/goldphish `
  -v E:\goldphish\goldphish-main\goldphish-main:/opt/goldphish `
  -w /opt/goldphish `
  -e WEB3_HOST=wss://YOUR_RPC_HOST `
  goldphish python3 -m backtest.gather_samples
```

### 5.7 运行后处理

#### odd token 标注

```powershell
docker run --rm -t `
  --network ethereum-measurement-net `
  -v F:/STORAGE_DIR:/mnt/goldphish `
  -v E:\goldphish\goldphish-main\goldphish-main:/opt/goldphish `
  -w /opt/goldphish `
  -e WEB3_HOST=wss://YOUR_RPC_HOST `
  goldphish python3 -m backtest.gather_samples.fill_odd_token_xfers --n-workers 1 --id 0
```

#### false positive 标注

```powershell
"yes" | docker run --rm -i `
  --network ethereum-measurement-net `
  -v F:/STORAGE_DIR:/mnt/goldphish `
  -v E:\goldphish\goldphish-main\goldphish-main:/opt/goldphish `
  -w /opt/goldphish `
  goldphish python3 -m backtest.gather_samples.fill_false_positive
```

---

## 6. 与论文对应的关键实验

本毕设论文中的主要实验并不是“全链一次性跑完”，而是围绕**局部验证区间**和**阶段性样本集**展开。

### 6.1 局部验证区间

论文中最核心的对照实验使用区间：

- `24144053 <= block_number < 24145053`

该区间用于对比：

- `Transfer-only baseline`
- `协议语义过滤优化`
- `Swap-only`
- `Hybrid`

### 6.2 baseline 结果

在上述区间中，baseline 结果为：

- `total_samples = 2460`
- `false_positive_samples = 382`
- `false_positive_rate = 15.53%`
- `no_fp_samples = 2078`

误报构成为：

- `CoW Swap = 188`
- `odd token = 143`
- `relayer is in exchanges list = 66`
- `tokenlon = 3`

### 6.3 协议语义过滤结果

同一区间下，优化后结果为：

- `total_samples = 2202`
- `false_positive_samples = 125`
- `false_positive_rate = 5.68%`
- `no_fp_samples = 2077`

说明：

- `CoW Swap`、`relayer`、`tokenlon` 类误报在该区间中被完全压掉
- 剩余误报几乎全部是 `odd token`

### 6.4 多事件融合实验结果

- `Swap-only = 0`
- `Hybrid(v2) = 3`
- `Hybrid(v2+v3) = 8`

论文中最终将这一部分定位为：

- **探索性增强实验**
- 说明 `Swap` 更适合作为 `Transfer` 主框架下的辅助语义验证信号，而不是完全替代 `Transfer`

---

## 7. 我在原项目上修改了哪些代码

如果需要向老师或答辩委员说明“本人实际完成了哪些代码工作”，可以重点看下面这些模块。

### 7.1 核心识别与过滤逻辑

- [`backtest/gather_samples/analyses.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/analyses.py)
  - 增加协议语义过滤
  - 增加地址角色过滤
  - 增加交易级非套利协议排除逻辑

### 7.2 `Hybrid` 融合实验

- [`backtest/gather_samples/hybrid.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/hybrid.py)
  - 从严格地址匹配逐步调整为更合理的多层支撑逻辑
  - 支持 exact transition、token pair、exchange address 等多种语义支撑模式

### 7.3 `Swap-only` 实验

- [`backtest/gather_samples/swap_only.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/swap_only.py)
  - 实现结构化 swap 读取与单独实验入口
  - 统一读取 v2 / v3 等结构化 swap 事件

### 7.4 DEX / Pool / Swap 事件抓取扩展

主要在以下 scraper 中扩展了结构化 `swap` 事件：

- [`backtest/gather_samples/fill_known_exchanges/scrapers/uniswapv2.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/fill_known_exchanges/scrapers/uniswapv2.py)
- [`backtest/gather_samples/fill_known_exchanges/scrapers/uniswapv3.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/fill_known_exchanges/scrapers/uniswapv3.py)
- [`backtest/gather_samples/fill_known_exchanges/scrapers/sushiswapv2.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/fill_known_exchanges/scrapers/sushiswapv2.py)
- [`backtest/gather_samples/fill_known_exchanges/scrapers/shibaswap.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/fill_known_exchanges/scrapers/shibaswap.py)
- [`backtest/gather_samples/fill_known_exchanges/scrapers/balancerv2.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/fill_known_exchanges/scrapers/balancerv2.py)
- [`backtest/gather_samples/fill_known_exchanges/scrapers/curvefi.py`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples/fill_known_exchanges/scrapers/curvefi.py)

### 7.5 测试补充

测试主要位于：

- [`tests/test_hybrid.py`](E:/goldphish/goldphish-main/goldphish-main/tests/test_hybrid.py)
- [`tests/test_swap_only.py`](E:/goldphish/goldphish-main/goldphish-main/tests/test_swap_only.py)
- [`tests/test_protocol_semantic_filters.py`](E:/goldphish/goldphish-main/goldphish-main/tests/test_protocol_semantic_filters.py)

---

## 8. 结果查询示例

### 8.1 查询局部区间样本数

```powershell
docker exec -it ethereum-measurement-pg psql -U measure -d eth_measure_db -c "SELECT COUNT(*) AS total_samples FROM sample_arbitrages WHERE block_number >= 24144053 AND block_number < 24145053;"
```

### 8.2 查询局部区间误报数

```powershell
docker exec -it ethereum-measurement-pg psql -U measure -d eth_measure_db -c "SELECT COUNT(DISTINCT safp.sample_arbitrage_id) AS fp_samples FROM sample_arbitrage_false_positives safp JOIN sample_arbitrages sa ON sa.id = safp.sample_arbitrage_id WHERE sa.block_number >= 24144053 AND sa.block_number < 24145053;"
```

### 8.3 查询误报原因分布

```powershell
docker exec -it ethereum-measurement-pg psql -U measure -d eth_measure_db -c "SELECT safp.reason, COUNT(*) FROM sample_arbitrage_false_positives safp JOIN sample_arbitrages sa ON sa.id = safp.sample_arbitrage_id WHERE sa.block_number >= 24144053 AND sa.block_number < 24145053 GROUP BY safp.reason ORDER BY COUNT(*) DESC;"
```

### 8.4 查询 `Hybrid` 样本数

```powershell
docker exec -it ethereum-measurement-pg psql -U measure -d eth_measure_db -c "SELECT COUNT(*) AS total_samples FROM sample_arbitrages_hybrid;"
```

---

## 9. 上传 GitHub 前的建议

如果要把本仓库作为毕设代码仓库上传到 GitHub，建议先整理以下内容。

### 9.1 建议保留

- 源代码
- `Dockerfile`
- `requirements.txt`
- `README.md`
- `tests/`
- 论文生成相关脚本（如果你希望老师看到论文图表与文档是如何生成的）

### 9.2 建议不要上传或单独处理

以下文件通常很大，且不适合作为公开仓库主内容：

- 各类 `.dump` / `.sql` 数据库备份
- `output/` 中的大型中间文件
- 本地临时测试脚本
- 带有个人路径或配额信息的私有配置

建议在提交前检查：

- `.gitignore` 是否覆盖大文件与临时文件
- 是否存在 RPC key、数据库口令、绝对路径等敏感信息

---

## 10. 论文与仓库的关系

本仓库服务于本科毕业设计论文，论文内容主要围绕以下主线展开：

1. 以太坊历史交易数据采集与标准化  
2. 基于 `Transfer` 的交易图建模与 baseline 复现  
3. 协议语义过滤优化  
4. `Swap-only` 与 `Hybrid` 多事件融合探索  
5. 局部区间对照实验与阶段性样本统计分析  

因此，若从论文复现角度阅读本仓库，推荐优先查看：

- [`backtest/gather_samples`](E:/goldphish/goldphish-main/goldphish-main/backtest/gather_samples)
- [`output`](E:/goldphish/goldphish-main/goldphish-main/output)
- [`scripts`](E:/goldphish/goldphish-main/goldphish-main/scripts)

---

## 11. 致谢与说明

本仓库基于开源项目 Goldphish 进行学习、复现与扩展，原项目作者与原始代码结构为本毕业设计提供了重要基础。本人在此基础上完成了与毕业论文直接对应的实验复现、代码修补、协议语义过滤优化、多事件融合探索与论文配套分析工作。

如果你是查看本仓库的老师或同学，建议将其理解为：

- 一个**真实开源项目基础上的毕业设计扩展仓库**
- 而不是从零开始重写的独立系统

这也正是本课题的研究价值所在：在已有链上分析框架基础上，通过工程实现与实验对照，探索更适合真实 DeFi 场景的原子套利识别改进方法。
