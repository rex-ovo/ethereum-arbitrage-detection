# 基于交易图与协议语义过滤的以太坊原子套利识别方法研究

## 封面信息

- 题目：基于交易图与协议语义过滤的以太坊原子套利识别方法研究
- 学生姓名：唐睿
- 学号：3220103690
- 学院：待按学校模板填写
- 行政班级：待按学校模板填写
- 指导教师：待按学校模板填写
- 完成时间：2026年5月

## 摘要

去中心化金融快速发展使得链上交易行为呈现出高度开放、可组合和跨协议交互的特征。原子套利作为其中一种典型的链上收益获取行为，通常在单笔交易内完成多次兑换、借贷和资产回流，其执行过程涉及多协议、多事件和高频语义切换。围绕原子套利交易的自动识别问题，本文基于以太坊主网历史数据，研究面向去中心化交易场景的交易数据采集、交易图建模、套利路径识别与识别准确度优化方法。

本文首先结合 `goldphish` 开源项目，对以太坊区块中的 ERC-20 `Transfer` 事件、已知去中心化交易所的 `Swap` 事件、交易回执日志以及若干辅助协议信息进行抓取与结构化整理，并构建统一的交易事件数据集。在此基础上，本文以 Token 为节点、以资产流动关系为边建立交易图模型，通过识别图中的闭环结构发现潜在原子套利样本。针对仅依赖 `Transfer` 事件时容易将 CoW Swap、Tokenlon、Dexible 等协议中的 settlement 合约、relayer 地址和特殊包装行为误识别为 exchange 的问题，本文进一步提出协议语义过滤优化方法，在原有 `Transfer` 主导识别框架上引入交易级协议过滤和地址级角色过滤，从而降低协议特定行为带来的识别偏差。

在局部验证区块区间 `24144053-24145052` 上，原始 baseline 方法共识别候选原子套利样本 2460 笔，误报样本 382 笔，误报率为 15.53%。引入协议语义过滤后，候选样本数降为 2202 笔，误报样本数降为 125 笔，误报率下降至 5.68%，其中 CoW Swap 与 relayer 相关误报均降为 0。在更大范围的阶段性样本中，baseline 已累计识别样本 16178 笔，误报样本 2175 笔，进一步验证了协议型误报和异常 token 转移是当前识别误差的主要来源。为评估多事件融合建模的效果，本文还设计了 `Swap-only` 与 `Hybrid` 两类实验。实验结果表明，仅依赖单协议显式 `Swap` 事件无法支撑有效原子套利识别；而在引入 Uniswap v2 与 Uniswap v3 交换语义后，`Hybrid` 方法可识别 8 笔高置信度样本，说明 `Swap` 事件更适合作为 `Transfer` 主识别框架下的辅助语义验证信号，而非完全替代 `Transfer` 的单一识别基础。

本文的工作表明，面向真实 DeFi 场景的原子套利识别，更适合采用“`Transfer` 高覆盖主框架 + 协议语义过滤 + `Swap` 语义增强”的分层建模思路。该方法能够在有限覆盖损失下显著降低误报，提升原子套利识别结果的可靠性，也为后续开展更大区间验证、人工抽样核验和跨协议扩展奠定了基础。

关键词：以太坊；去中心化金融；原子套利；交易图；协议语义过滤；多事件融合

## Abstract

With the rapid development of decentralized finance, on-chain transactions have become increasingly open, composable, and cross-protocol. Atomic arbitrage is a representative profit-seeking behavior in this environment. It is usually completed within a single transaction and involves multiple swaps, loans, and asset returns across heterogeneous DeFi protocols. This thesis studies atomic arbitrage detection on Ethereum from the perspectives of transaction data collection, graph modeling, arbitrage-path identification, and detection-accuracy optimization.

This work first builds a structured transaction-event dataset from Ethereum mainnet historical data by collecting ERC-20 `Transfer` events, known decentralized exchange `Swap` events, receipt logs, and auxiliary protocol information based on the `goldphish` open-source project. A token-level transaction graph is then constructed, where tokens are modeled as nodes and asset movements are modeled as directed edges. Potential atomic arbitrage opportunities are identified by detecting cycles in the graph. To address the false positives caused by a transfer-only strategy, this thesis further proposes a protocol-semantic filtering method. The optimized method keeps transfer-based identification as the primary framework while introducing transaction-level protocol filtering and address-role filtering to exclude settlement contracts, relayers, wrappers, and other non-exchange entities that frequently lead to semantic misclassification.

On the local evaluation block range `24144053-24145052`, the baseline method identifies 2460 candidate atomic arbitrages, among which 382 are labeled as false positives, corresponding to a false-positive rate of 15.53%. After applying protocol-semantic filtering, the number of candidates decreases to 2202, while false positives drop to 125 and the false-positive rate decreases to 5.68%. In particular, CoW Swap-related and relayer-related false positives are both reduced to zero. On a larger partially processed sample set, the baseline has already identified 16178 candidate samples, further confirming that protocol-specific and odd-token-related behaviors are the major error sources. In addition, this thesis explores `Swap-only` and `Hybrid` detection strategies. The results show that relying solely on explicit swap events from a single protocol is insufficient for effective arbitrage detection, whereas introducing Uniswap v2 and Uniswap v3 swap evidence allows the `Hybrid` method to identify 8 high-confidence samples. This suggests that swap events are more suitable as auxiliary semantic validation signals under a transfer-based framework than as a full replacement for transfer-based identification.

Overall, the results demonstrate that protocol-semantic filtering can significantly improve detection reliability with only limited loss of coverage, and that a practical detection strategy for real DeFi scenarios should combine a transfer-driven high-coverage backbone with protocol-semantic constraints and swap-based semantic enhancement.

Keywords: Ethereum; decentralized finance; atomic arbitrage; transaction graph; protocol-semantic filtering; multi-event fusion

# 1 绪论

## 1.1 研究背景

### 1.1.1 去中心化金融生态的快速扩张

以太坊等智能合约平台的发展推动了去中心化金融生态的快速扩张。围绕代币兑换、流动性提供、借贷清算、聚合交易与闪电贷等场景，链上逐渐形成了可组合程度极高的金融协议网络[1][5]。与传统中心化系统相比，DeFi 交易的执行过程、资产流动路径和合约调用顺序均可在链上公开观测，这为围绕链上金融行为开展数据分析和结构识别提供了天然的数据基础。

### 1.1.2 原子套利与 MEV 的兴起

原子套利是 DeFi 环境中极具代表性的链上收益行为之一。该类交易通常在单笔交易中完成多次兑换、借贷或回流操作，通过利用不同协议之间的价格差、流动性差异或定价不一致，在交易结束时形成净收益[4][6][8]。由于原子套利具有单交易闭环完成、无需承担跨交易持仓风险、执行速度快且依赖精细路径设计等特点，它不仅是理解链上市场效率的重要窗口，也是分析 MEV、路径优化和跨协议交互模式的重要对象[4][8][9]。

### 1.1.3 链上原子套利识别面临的挑战

然而，链上原子套利的自动识别并不容易。一方面，真实交易往往跨越多个协议与合约，既包含显式的 `Swap` 事件，也包含大量普通 `Transfer` 事件、包装合约操作、聚合路由与 settlement 行为。另一方面，不同协议在日志结构、内部记账方式和执行语义上存在明显差异，单纯依赖某一种事件类型进行识别，容易出现遗漏或误判。因此，围绕“如何在真实链上复杂交易环境中更准确地识别原子套利交易”展开研究，具有较强的工程价值和方法意义。

## 1.2 研究意义

### 1.2.1 理论意义

从理论层面看，原子套利识别涉及链上多源事件融合、交易图建模、闭环路径分析和异常样本过滤等问题，是区块链数据分析与图计算方法在金融场景中的典型应用。对该问题进行研究，有助于深化对链上复杂交易结构的理解，并为后续围绕 MEV、流动性竞争和协议协同的研究提供可复用的方法基础。

### 1.2.2 工程意义

从工程实现层面看，现有基于链上事件的套利识别方法往往依赖单一事件类型或较强的协议假设，在真实 DeFi 场景下容易受到协议实现差异的影响。本文通过在 `Transfer` 主识别框架中引入协议语义过滤，对 CoW Swap、Tokenlon、Dexible、relayer、wrapper 等特殊场景进行约束，可为后续构建更稳健的链上交易分析工具提供参考。

### 1.2.3 应用价值

从应用层面看，原子套利识别结果能够服务于 MEV 研究、链上市场行为分析、协议风险评估和策略复现等任务。通过提高候选套利样本的可信度，可以为后续开展更深入的交易行为研究提供更加可靠的数据基础。

## 1.3 研究内容与已完成工作

### 1.3.1 数据采集与标准化处理

本文围绕以太坊主网历史数据开展交易事件采集与标准化处理。重点提取 ERC-20 `Transfer` 事件、去中心化交易所 `Swap` 事件以及与交易回执相关的日志信息，并构建统一的结构化交易事件数据集，为后续交易图分析提供基础数据。

### 1.3.2 交易图建模

本文建立面向原子套利识别的交易图模型。通过将 Token 视为节点、将交易中的资产流动关系抽象为边，可在单笔交易内部还原潜在的闭环结构，并据此开展套利路径检测。

### 1.3.3 baseline 方法复现

本文在现有开源项目基础上，完成了 `Transfer-only` baseline 流程的部署、运行与局部实验，并在真实区块范围上得到了候选套利样本及其误报分布。除识别逻辑本身外，本文还对链上数据抓取过程中的 RPC 稳定性、区块分片和任务续跑进行了针对性工程改进。

### 1.3.4 准确度优化与融合实验

针对 baseline 方法在协议特定行为场景中的误判问题，本文提出协议语义过滤优化方法，并进一步设计了 `Swap-only` 与 `Hybrid` 对比实验，分析不同事件建模方式在覆盖率与准确度上的差异。到目前为止，协议语义过滤已获得最主要的正向结果，而融合实验则形成了对方法边界的有价值补充结论。

## 1.4 论文结构安排

本文共分为六章。第一章为绪论，介绍课题背景、研究意义、主要研究内容与论文结构。第二章介绍与研究相关的关键技术与国内外研究现状，包括以太坊交易机制、ERC-20 事件、去中心化交易协议、原子套利、自动做市商以及现有识别方法存在的问题。第三章围绕数据采集、标准化处理与交易图建模展开，介绍交易数据来源、任务组织方式、存储结构以及面向套利识别的交易图构建方法。第四章介绍原子套利识别方法的实现过程与准确度优化思路，重点说明 baseline 复现、工程稳定性改进、协议语义过滤优化以及 `Swap-only`、`Hybrid` 融合识别探索。第五章给出实验结果与分析，对 baseline 方法和优化方法在局部区间上的识别结果、误报分布、阶段性大样本结构以及融合实验效果进行对比讨论。第六章对全文工作进行总结，并给出后续可进一步开展的改进方向。

# 2 相关技术与研究现状

## 2.1 以太坊交易、日志与代币标准

### 2.1.1 以太坊交易执行机制

以太坊是支持图灵完备智能合约的公有链平台。用户通过发送交易调用智能合约函数，合约执行过程中可能修改链上状态并产生事件日志[1]。对于链上行为分析而言，区块、交易、交易回执与事件日志共同构成了最基本的数据来源。原子套利交易通常发生在单笔交易之内，因此交易级回执信息和日志顺序在恢复套利路径时具有重要作用。

### 2.1.2 ERC-20 `Transfer` 事件

ERC-20 是以太坊上最常见的同质化代币标准，其核心事件 `Transfer` 用于记录代币在地址之间的转移过程[2]。在 DeFi 场景中，绝大多数代币兑换、包装、路由和清算操作都会伴随 `Transfer` 事件，因此 `Transfer` 具有覆盖面广、协议通用性强的优点，是构建链上资产流动关系的重要基础。

### 2.1.3 闪电贷相关标准

闪电贷是原子套利交易的重要资金放大工具之一。它允许用户在单笔交易中临时借入资产，并在交易结束前归还本金与费用，若中途失败则整笔交易回滚。相关接口与交互模式已在 EIP-3156 等标准中得到抽象[3]。在实际链上环境中，闪电贷常与跨池兑换、聚合路由和清算逻辑联合出现，因此在识别原子套利路径时，需要注意区分“融资步骤”和“套利闭环步骤”。

## 2.2 去中心化交易协议与自动做市商机制

### 2.2.1 Uniswap v2 与常数乘积做市

Uniswap v2 采用典型的常数乘积做市机制，交易执行遵循 `x * y = k` 的约束关系[10][11]。该机制具有结构简单、部署广泛的特点，也因此成为许多链上套利研究的重要分析对象。对本文而言，Uniswap v2 的标准化 `Swap` 事件结构有利于直接还原 token 输入输出关系。

### 2.2.2 Uniswap v3 与集中流动性

Uniswap v3 在 v2 基础上引入了集中流动性设计，使流动性提供者可以在特定价格区间提供资金，从而提高资本效率[12][22]。然而，集中流动性也使交易路径和价格响应机制变得更加复杂。在极端市场条件下，v3 的价格准确性和流动性反应能力可能受到挑战[22]，这说明显式 `Swap` 事件虽然语义更强，但并不天然意味着识别任务会变得更简单。

### 2.2.3 聚合器、settlement 与非标准交换行为

除传统 AMM 外，DeFi 生态中还存在大量聚合器、撮合协议和 settlement 合约。例如 CoW Swap 使用统一结算机制完成撮合与清算，而 Tokenlon、Dexible 等协议也可能通过中间合约完成复杂的路径组合。此类协议在链上往往表现为多笔 `Transfer` 的组合，但其核心地址并不一定应被视为 exchange 节点。如果直接使用通用资产流规则进行建模，就容易将其误判为套利闭环的一部分。

## 2.3 原子套利与 MEV 相关研究

### 2.3.1 原子套利与前跑研究

Flash Boys 2.0 是 DeFi 与 MEV 研究中的代表性工作之一，它系统揭示了交易重排、抢跑与链上市场不稳定性问题[4]。此后，大量研究开始关注 AMM 场景下的抢跑、插入攻击与原子套利路径。Frontrunner Jones 进一步从经验角度分析了 Ethereum mempool 中的前跑行为及其收益模式[9]。这些研究说明，原子套利并不是孤立的价格差利用行为，而是和交易排序、区块内竞争、路径路由密切相关。

### 2.3.2 DEX 市场效率研究

围绕去中心化交易所价格效率与套利机会的研究表明，DEX 在高波动市场和跨池定价偏差下经常出现可利用的短时失衡。High-Frequency Trading on Decentralized On-Chain Exchanges 对链上高频交易和套利策略进行了系统分析[7]。An Empirical Study of Market Inefficiencies in Uniswap and SushiSwap 则从市场效率角度展示了循环套利机会和不利成交现象的存在[20]。这些工作说明，以 DEX 为对象开展套利检测具有现实合理性。

### 2.3.3 DeFi 安全与异常交易研究

Attacking the DeFi Ecosystem with Flash Loans for Fun and Profit 展示了闪电贷如何被用于复杂攻击路径构造[6]。Understanding the Security Risks of Decentralized Exchanges by Uncovering Unfair Trades in the Wild 则从不公平交易角度分析了 DEX 的安全风险[21]。这些研究表明，链上复杂路径不仅可能对应正常套利行为，也可能对应利用协议语义缺陷或执行机制偏差的特殊交易，因此在识别任务中引入协议语义约束具有必要性。

## 2.4 自动做市商理论与交易图建模启发

### 2.4.1 CFMM 理论研究

近年来围绕 Constant Function Market Maker 的理论研究不断发展。Improved Price Oracles: Constant Function Market Makers 讨论了 CFMM 的价格预言机性质[13]；Constant Function Market Makers: Multi-Asset Trades via Convex Optimization 从多资产交易优化角度刻画了 CFMM 的可交易空间[15]；The Geometry of Constant Function Market Makers 则从几何视角进一步分析了 CFMM 结构[16]。这些研究从定价机制、路径选择和多资产优化角度为本文理解链上兑换路径提供了理论基础。

### 2.4.2 AMM 综述与流动性提供者行为

Automated Market Makers and Decentralized Exchanges: a DeFi Primer 对自动做市商与 DEX 进行了系统综述[17]；A Theory of Automated Market Makers in DeFi 从更抽象的形式化视角分析了 AMM 的交互模型[18]；Behavior of Liquidity Providers in Decentralized Exchanges 则关注流动性提供者的实际行为特征[19]。这些工作表明，DEX 中的价格形成与流动性迁移具有明显动态性，因此仅凭单一类型事件难以完整表达全部交易语义。

## 2.5 现有识别方法的不足与本文定位

### 2.5.1 `Transfer-only` 方法的优势与局限

当前项目中的 baseline 方法以 `Transfer` 事件为核心，通过解析单笔交易中的代币流入流出关系，推断可能的交换节点，并进一步构造 token 级有向图，再基于闭环检测识别潜在套利路径。该方法的优点在于协议适配范围较广，不依赖单一 DEX 的日志定义，因此具有较强的覆盖能力。

但通过实验可发现，纯 `Transfer` 方法容易将一些并非真实交换节点的地址误识别为 exchange。例如在 CoW Swap 等 settlement 类协议中，交易级执行合约承担了集中清算与结算功能，但其并不应被视为传统意义上的交易池；在部分 relayer 场景下，中继地址也可能因代币支付路径而被错误纳入套利环中；此外，部分 odd token 或包装合约会产生不符合一般交换语义的代币转移模式，从而进一步增加误报。

### 2.5.2 `Swap-only` 方法的覆盖不足

与 `Transfer` 相比，显式 `Swap` 事件具有更强的交换语义，但其覆盖能力受到协议范围、事件结构和采集实现的限制。对于跨协议、多跳或包含特殊合约交互的真实套利路径而言，仅依赖单协议 `Swap` 事件往往无法完整恢复整个闭环。这一点也在本文后续实验中得到了印证。

### 2.5.3 本文的研究定位

基于上述分析，本文并不试图完全抛弃 `Transfer` 主识别框架，而是将工作重点放在两个方向：一是通过协议语义过滤降低 `Transfer-only` 方法中的典型误报；二是将 `Swap` 事件作为辅助语义验证信号，探索高置信度小样本识别路径。这样的定位既符合当前代码基础与实验条件，也更符合真实工程中“先提高可用性，再逐步增强精度”的实现路径。

# 3 数据采集、标准化与交易图建模

## 3.1 数据来源与采集流程

### 3.1.1 原始数据来源

本文实验数据来自以太坊主网历史区块，通过 Web3 节点接口获取区块、交易、回执与日志信息。在实际实验过程中，主要依赖 `WEB3_HOST=wss://mainnet.infura.io/ws/...` 的 WebSocket 接口抓取链上日志。由于以太坊归档节点查询量较大，实验过程中还需要结合本地 PostgreSQL 数据库存储中间结果，以支持重复查询、误报过滤和分阶段分析。

### 3.1.2 事件采集对象

围绕原子套利识别需求，本文重点采集以下几类数据：

1. ERC-20 `Transfer` 事件，用于还原交易内部的资产流动关系；
2. 已知 DEX 的 `Swap` 事件，用于增强交换语义表达；
3. 交易回执及其日志顺序，用于结合单笔交易恢复路径；
4. 已知 exchange 地址、pair 地址与协议标签，用于路径归因和误报过滤。

### 3.1.3 已知交易所与池子信息采集

在 `fill_known_exchanges` 模块中，项目维护了多个 scraper，用于从不同 DEX 协议中提取已知交易池与交换事件信息。除 Uniswap v2、Sushiswap v2 等 v2 类协议外，代码中还包含 Balancer、Curve、DODO、Kyberswap、OneInch、Uniswap v3 等 scraper。虽然本文后续 `Swap-only` 与 `Hybrid` 实验中主要使用了 Uniswap v2/v3 的结构化 `Swap` 数据，但整个 exchange 采集模块为未来扩展多协议融合提供了较好的代码基础。

### 3.1.4 reservation 分片与任务组织

考虑到全区间直接扫描的代价较高，项目采用 reservation 的方式分片抓取区块范围。每个 reservation 负责一个固定的区块片段，任务在数据库中以 `gather_sample_arbitrages_reservations` 的形式管理。该机制使得实验可以分批推进、断点续跑，并适应 API 配额有限、节点偶发中断的现实约束。

## 3.2 数据标准化与存储设计

### 3.2.1 地址、Token 与日志标准化

在数据处理过程中，本文对原始日志进行统一标准化，包括地址格式统一、token 映射、交易哈希与区块号字段对齐以及异常数据过滤等。不同协议中的 token 表示方式在结构化落库后被统一映射到 `tokens` 表中，以便后续在图构建与利润统计中使用统一的 token 标识。

### 3.2.2 核心样本表结构

在 baseline 与优化实验中，核心样本相关表主要包括：

1. `sample_arbitrages`：记录候选套利交易基本信息；
2. `sample_arbitrage_cycles`：记录单个套利样本中的 cycle 信息；
3. `sample_arbitrage_cycle_exchanges` 与 `sample_arbitrage_cycle_exchange_items`：记录 cycle 中的 exchange 结构；
4. `sample_arbitrages_odd_tokens`：记录 odd token 标记结果；
5. `sample_arbitrage_false_positives`：记录误报原因；
6. `sample_arbitrages_no_fp`：记录误报过滤后的样本集。

这些表共同构成了“识别—过滤—分析”的完整数据闭环。

### 3.2.3 `Swap-only` 与 `Hybrid` 的独立结果表

为了避免实验互相污染，本文在探索 `Swap-only` 与 `Hybrid` 方案时，没有直接覆盖 `sample_arbitrages`，而是为不同方法分别建立了独立结果表，如 `sample_arbitrages_swap_only`、`sample_arbitrages_hybrid` 及其对应的 cycle/exchange 子表。这样可以在同一数据库中并行保留多组实验结果，便于后续开展消融实验和结果对照。

## 3.3 交易图模型设计

### 3.3.1 节点与边的定义

本文采用 token-level 图建模方式。图中的节点表示 Token 类型，边表示在单笔交易内部观察到的资产流动或交换关系。对于 baseline 方法而言，边主要由 `Transfer` 推断得到；对于融合方法而言，边还可以由 `Swap` 事件直接给出更高置信度的 token 输入输出语义。

### 3.3.2 候选 exchange 提取

在 `Transfer-only` baseline 中，系统会先根据某地址在同一交易内是否同时出现 token 流入与流出、是否满足单入单出等条件，推断该地址是否可能是 exchange 节点。之后，再根据这些候选 exchange 构造 token 图。这个过程是 baseline 识别能力的重要来源，但也是协议型误报的主要入口之一。

### 3.3.3 闭环检测与利润判断

当 token 图构建完成后，系统会对图中的闭环结构进行检测。若某条路径在图上形成回到起始 token 的闭环，并且结合交易回执分析后能够确认净收益，则该交易被标记为候选原子套利样本。作为图算法基础，项目使用了经典的 elementary circuit 思想来遍历潜在闭环[23]。

### 3.3.4 图模型的局限

虽然 token-level 图模型有利于统一分析不同协议下的资产流动关系，但其表达能力仍受限于底层事件的语义完整性。若底层仅有 `Transfer`，则图中的某些边未必能准确代表“真实交换”；若底层只用单协议 `Swap`，则图往往过于稀疏。因此，如何在图中平衡覆盖率与语义准确性，是本文后续优化工作的核心问题之一。

# 4 原子套利识别方法实现与准确度优化

## 4.1 `Transfer-only` baseline 方法实现

### 4.1.1 baseline 流程概述

baseline 方法的执行入口为 `python3 -m backtest.gather_samples`。程序会首先领取 reservation，对指定区间内的交易日志进行扫描，再从单笔交易的 `Transfer` 行为中恢复资产流路径。识别出的候选套利样本将落入 `sample_arbitrages` 及其关联表中，后续再结合 odd token 和 false positive 过滤模块进行清洗。

### 4.1.2 receipt 解析与 movement 提取

在具体实现层面，baseline 会先通过 Web3 节点获取交易回执，再从回执日志中筛出 ERC-20 `Transfer` 事件，并按地址汇总某一地址的 token 流入流出关系。随后，系统根据地址层面的 movement 模式推断候选 exchange 节点，为后续构图提供输入。

### 4.1.3 cycle 识别与结果落库

当候选 exchange 节点确定后，系统将围绕 token 输入输出关系构建有向图，并在图中检测闭环。若检测到满足条件的 cycle，程序还会记录每个 cycle 中的 exchange 次序、利润 token 和利润数量，并将结果写入 cycle 与 exchange 相关子表，为后续误报分析和收益统计保留足够细节。

### 4.1.4 baseline 的覆盖优势

baseline 的最大优势在于其协议无关性。由于大多数 DeFi 操作最终都会表现为 token 转移，因此 `Transfer-only` 方法在协议覆盖面上明显优于依赖特定 `Swap` 事件的方案。这也是本文后续所有优化工作仍然保留 `Transfer` 主框架的重要原因。

## 4.2 工程稳定性改进

### 4.2.1 WebSocket 断连与退避重试

在实际抓取过程中，WebSocket 连接会出现 `ConnectionClosedError: code = 1006` 等瞬时异常。为降低长时间任务因网络抖动而直接失败的风险，本文在请求层引入了 `backoff` 退避重试机制，使得节点短暂波动时任务能够自恢复继续执行。这一改动并不改变识别算法本身，但显著提高了大区间样本采集的可执行性。

### 4.2.2 `eth_getLogs` 超限拆分

在热门区块范围内，单次 `eth_getLogs` 查询会触发 `query returned more than 10000 results` 的节点限制。为解决这一问题，本文对日志抓取逻辑进行了最小侵入式修补：当指定区块范围内返回结果超限时，自动递归拆分区块区间，直到单次查询结果降到可接受范围。该改动使得原本会在热点区块直接中断的采集流程能够继续推进。

### 4.2.3 receipt 获取重试

除日志查询外，交易回执查询也会遭遇临时 `internal error`。本文对 receipt 获取环节增加了瞬时错误重试逻辑，以提升单笔交易解析的稳定性。虽然这类错误仍可能在 API 配额紧张时出现，但配合 reservation 分片机制后，整体任务的可持续推进能力已有明显改善。

### 4.2.4 单元测试补充

为了验证关键修补逻辑，本文还补充了若干测试脚本，包括 `test_gather_samples_retry.py`、`test_gather_samples_log_split.py`、`test_protocol_semantic_filters.py`、`test_swap_only.py` 和 `test_hybrid.py` 等。这些测试分别覆盖了 RPC 重试、日志拆分、协议过滤和融合识别原型的基础行为，为后续实验提供了最基本的可回归保障。

## 4.3 协议语义过滤优化方法

### 4.3.1 误报来源定位

在局部验证区间 `24144053-24145052` 上，baseline 共识别样本 2460 笔，其中误报 382 笔。误报来源中，CoW Swap 为 188 笔，odd token 为 143 笔，`relayer is in exchanges list` 为 66 笔，Tokenlon 为 3 笔。该结果说明，协议型误报和特殊 token 行为是当前识别精度的主要瓶颈。

### 4.3.2 交易级协议过滤

针对 CoW Swap、Tokenlon、Dexible 等协议型误报，本文在识别入口处增加交易级协议判断逻辑。若交易目标地址属于已知 settlement 或聚合协议执行合约，则不再将其按普通套利交易继续分析。这一改动直接作用于误报源头，是本文最有效的准确度优化之一。

### 4.3.3 地址级角色过滤

除交易级过滤外，本文还在候选 exchange 提取阶段增加地址级角色过滤。通过维护 router、relayer、wrapper、settlement 等地址集合，可以在构图前排除不应作为 exchange 的节点。局部实验中，本文根据真实误报样本额外补入了若干 relayer 地址，使得 `relayer is in exchanges list` 误报从 66 笔降为 0。

### 4.3.4 优化方法的作用边界

需要指出的是，协议语义过滤并没有解决所有误差。优化后剩余的 125 笔误报均来自 odd token，说明当前方法对异常 token 转移模式的前置识别仍然不足。因此，协议语义过滤更适合被理解为一种“优先消除结构性协议误报”的工程优化，而不是完整解决全部误报来源的终极方案。

## 4.4 `Swap-only` 融合识别探索

### 4.4.1 设计思路

为了评估显式 `Swap` 事件在原子套利识别中的作用，本文设计了 `Swap-only` 探索实验。该实验仅使用 `uniswap_v2_swap_events`（后续扩展为统一 swap 证据源的基础）中的 `Swap` 事件来构建 token 图，不再使用 `Transfer` 事件推断 exchange 行为，并在发现闭环后再用 `Transfer` 辅助确认利润方向。

### 4.4.2 实现路径

在代码实现上，本文新增了独立的 `swap_only.py` 入口和对应结果表，使其可以在不污染 baseline 数据的前提下单独运行。该实现首先加载指定区间内包含 `Swap` 事件的交易，再根据 `Swap` 的 token 输入输出关系构图并尝试识别闭环。

### 4.4.3 实验结果与分析

在局部实验区间 `24144053-24145053` 内，共存在 4006 笔至少包含 Uniswap v2 `Swap` 事件的交易。然而，采用 `Swap-only` 方案进行识别时，最终未检测到有效原子套利样本。这说明单协议 `Swap` 事件虽然交换语义更强，但在真实 DeFi 场景中覆盖不足，难以恢复跨协议、多跳或包含特殊合约交互的完整套利路径。

## 4.5 `Hybrid` 融合识别探索

### 4.5.1 `Hybrid(v2)`：`Transfer` 主识别 + v2 语义验证

在 `Swap-only` 基础上，本文进一步设计了 `Hybrid` 融合识别方法。与完全用 `Swap` 主导识别不同，当前 `Hybrid` 方法采用“`Transfer` 主识别 + `Swap` 语义验证”的思路：先使用 baseline 的 `Transfer` 方法识别候选套利样本，再要求该样本中的关键 token 变换至少部分能被真实 `Swap` 事件支撑，从而筛选出一小批语义一致性更强的高置信度样本。

在仅使用 Uniswap v2 证据时，`Hybrid(v2)` 最终识别出 3 笔样本，说明单一协议的交换语义覆盖依然偏窄。

### 4.5.2 `Hybrid(v2+v3)`：扩大 `Swap` 证据源

随后，本文进一步扩展 `fill_known_exchanges` 的 `uniswapv3.py`，将 Uniswap v3 的结构化 `Swap` 事件也纳入统一 swap 证据源，同时调整 `swap_only.py` 与 `hybrid.py`，使其能够统一加载 Uniswap v2 与 Uniswap v3 的 `Swap` 事件进行验证。扩展后，`Hybrid(v2+v3)` 在同一区间内识别出 8 笔样本，覆盖区块范围扩展至 `24144195-24145039`。

### 4.5.3 方法定位

从方法定位上看，当前 `Hybrid` 更适合作为高精度补充识别模块，而不适合作为完全替代 baseline 的主识别方法。其作用在于：在 `Transfer` 提供高覆盖候选样本的基础上，用更强的交换语义筛出一小部分结构清晰、可置信度更高的原子套利交易。

# 5 实验结果与分析

## 5.1 实验设置、数据范围与评价指标

### 5.1.1 实验环境

本文实验基于以太坊主网历史交易数据，在 Docker 容器与 PostgreSQL 数据库环境下完成。链上数据抓取与样本识别主要通过 `python3 -m backtest.gather_samples` 及其相关填充脚本执行，局部融合实验则分别通过 `swap_only.py` 与 `hybrid.py` 的独立入口完成。

### 5.1.2 数据范围

考虑到完整时间窗口的链上抓取成本较高，同时为了保证优化前后结果可比，本文选择区块区间 `24144053-24145052` 作为局部验证区间，对 baseline 方法、协议语义过滤方法和融合识别方法进行对比分析。除此之外，本文还累计收集了更大范围的阶段性 baseline 样本，用于观察样本结构和主要误报来源。

### 5.1.3 评价指标

本文主要采用以下指标评价方法效果：

1. `Total Samples`：候选原子套利样本数；
2. `False Positives`：误报样本数；
3. `False Positive Rate`：误报率；
4. `No-FP Samples`：过滤后保留样本数；
5. 误报原因分布：CoW Swap、odd token、relayer、tokenlon 等。

对于融合实验，还额外关注样本规模、利润 token 分布和路径结构特征，用于评价 `Swap` 语义增强的覆盖能力和保守程度。

## 5.2 `Transfer-only` baseline 结果分析

### 5.2.1 局部验证区间 baseline 结果

在局部验证区间 `24144053-24145052` 上，baseline 方法共识别候选原子套利样本 2460 笔，其中误报样本 382 笔，误报率为 15.53%，误报过滤后保留样本 2078 笔。对误报来源进一步划分可以发现，CoW Swap 误报 188 笔，odd token 误报 143 笔，relayer 被误识别为 exchange 的样本为 66 笔，tokenlon 相关误报为 3 笔。

表 5-1 局部验证区间 baseline 结果

| 指标 | 数值 |
| --- | ---: |
| 候选样本总数 | 2460 |
| 误报样本数 | 382 |
| 误报率 | 15.53% |
| 过滤后样本数 | 2078 |

### 5.2.2 大范围阶段性样本结果

在更大范围的阶段性样本中，baseline 共识别候选样本 16178 笔，误报样本 2175 笔，误报率为 13.44%，过滤后保留样本 14003 笔。该结果表明，即使在更大样本尺度下，baseline 仍具备较强的候选覆盖能力，但误报问题同样显著存在。

表 5-2 阶段性大样本总体统计

| 指标 | 数值 |
| --- | ---: |
| 候选原子套利样本总数 | 16178 |
| 误报样本数 | 2175 |
| 误报率 | 13.44% |
| 过滤后样本数 | 14003 |
| odd token 样本数 | 663 |

### 5.2.3 样本结构与利润 token 分布

从环数分布看，baseline 样本以单环结构为绝对主导：`n_cycles = 1` 的样本共有 14297 笔；`n_cycles = 2` 的样本为 1328 笔；更高环数样本的数量快速下降。这说明在当前识别框架下，大部分候选原子套利表现为结构相对简单的单环或少量多环模式。

从利润 token 分布看，收益高度集中在主流资产，尤其是 `WETH`、`USDC`、`USDT`、`PAXG` 和 `WBTC`。其中 `WETH` 对应的套利周期数量最多，说明链上原子套利收益主要集中于流动性强、市场接受度高的主流资产。

表 5-3 阶段性大样本主要结构统计

| 指标 | 数值 |
| --- | ---: |
| 单环样本数 | 14297 |
| 双环样本数 | 1328 |
| 三环样本数 | 299 |
| WETH 利润样本数 | 9386 |
| USDC 利润样本数 | 1302 |
| USDT 利润样本数 | 1232 |

## 5.3 协议语义过滤对比实验

### 5.3.1 样本规模与误报率变化

引入协议语义过滤后，同一区间内的候选样本数下降为 2202 笔，误报样本数下降为 125 笔，误报率下降至 5.68%，误报过滤后保留样本 2077 笔。与 baseline 相比，误报样本减少了 257 笔，而保留样本仅比 baseline 少 1 笔，说明优化过程主要剔除的是原本会被后处理判定为误报的样本，并未显著损害有效样本保留能力。

### 5.3.2 误报来源变化

优化后，CoW Swap、relayer 和 tokenlon 相关误报全部降为 0，剩余误报全部来自 odd token。这表明协议语义过滤对结构性协议误判具有非常明显的抑制效果，但对异常 token 模式的处理仍需进一步加强。

表 5-4 baseline 与协议语义过滤方法对比

| 方法 | 样本总数 | 误报样本数 | 误报率 | CoW Swap | odd token | relayer | tokenlon | 过滤后样本数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Transfer-only Baseline | 2460 | 382 | 15.53% | 188 | 143 | 66 | 3 | 2078 |
| Ours（协议语义过滤） | 2202 | 125 | 5.68% | 0 | 125 | 0 | 0 | 2077 |

表 5-5 局部验证区间误报来源变化

| 方法 | CoW Swap | odd token | relayer | tokenlon |
| --- | ---: | ---: | ---: | ---: |
| Transfer-only Baseline | 188 | 143 | 66 | 3 |
| Ours（协议语义过滤） | 0 | 125 | 0 | 0 |

### 5.3.3 覆盖损失与收益权衡

从样本规模变化看，协议语义过滤后候选样本相较 baseline 减少了 258 笔，下降比例约为 10.49%。但由于最终保留样本几乎未变，这一损失可以理解为：优化方法主动舍弃了一部分低可信度、协议语义不一致的候选交易，以换取更明显的识别精度提升。对于毕业设计的工程目标而言，这种“有限覆盖损失换显著误报下降”的权衡是合理且有价值的。

## 5.4 多事件融合实验

### 5.4.1 `Swap-only` 结果

在局部实验区间内，`Swap-only` 虽然处理了 4006 笔包含 Uniswap v2 `Swap` 事件的交易，但最终未识别出有效原子套利样本。该结果说明，单协议显式 `Swap` 事件在真实 DeFi 环境中的路径恢复能力有限，难以支撑完整套利识别流程。

### 5.4.2 `Hybrid(v2)` 结果

在仅使用 Uniswap v2 作为 `Swap` 语义来源时，`Hybrid(v2)` 共识别出 3 笔样本。虽然样本数量极少，但这些样本均为单环结构，说明该方法在语义约束较强的前提下确实能够筛出少量高置信度样本。

### 5.4.3 `Hybrid(v2+v3)` 结果

将 `Swap` 证据源扩展至 Uniswap v2 与 Uniswap v3 后，`Hybrid(v2+v3)` 共识别出 8 笔样本，覆盖区块扩展到 `24144195-24145039`。这说明当前 `Hybrid` 的瓶颈不仅在于识别规则本身，更在于结构化 `Swap` 证据源的覆盖范围。随着 v3 事件的纳入，`Hybrid` 开始覆盖到更多语义一致性较强的样本。

### 5.4.4 利润 token 与路径结构分析

`Hybrid(v2+v3)` 的 8 笔样本全部为单环套利，利润 token 分布为：`WETH = 2`、`USDC = 2`、`T-REX = 2`、`USDT = 1`、`SPIKE = 1`。与早期仅识别出偏门资产的结果相比，加入 Uniswap v3 后，`Hybrid` 已开始覆盖部分主流资产样本。此外，相关样本涉及 17 个 exchange 地址，虽然仍集中于少量高频池，但相比 `Hybrid(v2)` 已表现出更高的路径多样性。

表 5-6 `Transfer-only`、`Swap-only` 与 `Hybrid` 融合实验对比

| 方法 | 样本数 | 主要特征 |
| --- | ---: | --- |
| Transfer-only | 2460 | 覆盖高，但误报相对较多 |
| Swap-only | 0 | 交换语义强，但单协议覆盖不足 |
| Hybrid(v2) | 3 | 高置信度样本较少，覆盖范围较窄 |
| Hybrid(v2+v3) | 8 | 高置信度样本增加，覆盖有所改善 |

## 5.5 工作量与工程完成度说明

### 5.5.1 已完成的核心代码工作

围绕本课题，本文已完成的核心工程工作主要包括：

1. 复现并跑通 `goldphish` 项目的原始 baseline 识别流程；
2. 搭建基于 PostgreSQL 的样本存储、误报过滤和阶段性分析环境；
3. 修补 RPC 抖动与 `eth_getLogs` 超限问题，使样本采集能够跨多日持续推进；
4. 完成协议语义过滤的代码修改与局部实验；
5. 实现 `Swap-only` 与 `Hybrid` 两种探索性识别原型；
6. 扩展 Uniswap v3 的结构化 `Swap` 事件支持；
7. 补充了多项测试脚本，用于验证关键修补逻辑与融合实验原型。

### 5.5.2 数据采集与实验执行工作量

除代码改动外，本文还完成了较多实验运维型工作，包括：

1. 对正式实验区间进行分片 reservation 组织与多次断点续跑；
2. 在 API 配额受限条件下分多日推进样本采集；
3. 多次对数据库进行备份、恢复与局部实验重置；
4. 针对不同识别方法分别建立独立结果表，防止实验结果互相污染；
5. 在局部验证区间上反复执行 `gather_samples`、`fill_odd_token_xfers`、`fill_false_positive` 和融合实验脚本，形成可重复对照结果。

### 5.5.3 已完成与待补充工作的边界

为保证论文结论与代码实现一致，本文对“已完成工作”和“后续计划”进行了明确区分。目前已经完成的内容包括 baseline 复现、协议语义过滤优化、局部对比实验、阶段性大样本统计、`Swap-only` 与 `Hybrid(v2+v3)` 融合实验。尚未完成但已明确规划的内容包括：第二个局部区间验证、人工抽样核验、更多协议 `Swap` 事件扩展和更完整的召回率评估。

### 5.5.4 本文工作量的整体体现

从毕业设计角度看，本文的工作量不仅体现在“跑出结果”，更体现在：

1. 完成从数据采集、数据库组织、交易图建模到样本过滤的完整链路；
2. 在现有开源项目基础上针对真实瓶颈进行工程修补与方法扩展；
3. 同时实现并比较了 baseline、协议语义过滤、`Swap-only` 和 `Hybrid` 多条实验路线；
4. 在有限算力与 API 配额条件下，形成了可支撑论文撰写的真实实验数据与分析结果。

## 5.6 结果讨论与不足

### 5.6.1 剩余误差来源：odd token

从当前结果看，协议语义过滤已成功消除了主要的协议型误报，但优化后剩余误报全部集中在 odd token 上。这说明，异常 token 转移模式并不是简单的协议语义问题，而更接近底层资产行为异常问题。未来若要继续提升精度，需要进一步分析 odd token 的共同模式，并尝试将其从后处理阶段前移到识别阶段。

### 5.6.2 数据完整性与外部约束

本文实验受到外部 RPC 节点配额与稳定性的影响，部分大范围数据采集采用了分片式、阶段性推进策略。因此，当前大样本统计应理解为“阶段性实验结果”，而不是对某一连续长区间的完全覆盖。本文在论文中也据此避免夸大实验范围，保证结论与实际完成情况一致。

### 5.6.3 融合识别的当前边界

`Swap-only` 与 `Hybrid` 实验表明，显式 `Swap` 事件在当前阶段更适合作为增强性语义信息，而不适合作为完全替代 `Transfer` 的主识别基础。这一结果虽然意味着融合方法暂未形成大规模主流程替代方案，但也为今后构建“高覆盖主流程 + 高精度辅助筛选”的双层检测框架提供了方向。

# 6 总结与展望

## 6.1 工作总结

本文围绕以太坊链上原子套利识别问题，基于 `goldphish` 开源项目完成了交易数据采集、交易图建模、baseline 方法复现和准确度优化实验。本文首先对 ERC-20 `Transfer` 事件、已知去中心化交易所 `Swap` 事件和交易回执信息进行了抓取与结构化处理，并在此基础上构建了面向原子套利识别的 Token 级交易图。随后，本文复现了基于 `Transfer` 的原子套利识别方法，并在真实区块范围内获得了候选套利样本。

针对 baseline 方法在 CoW Swap、relayer 和 odd token 等场景下误报较多的问题，本文进一步提出协议语义过滤优化方法。实验结果表明，该优化方法能够在有限覆盖损失下显著降低误报率，使局部实验区间内的误报率由 15.53% 下降至 5.68%，同时基本保留了有效样本。与此同时，本文还进一步探索了 `Swap-only` 与 `Hybrid` 两种融合识别思路，验证了单一 `Swap` 事件方法覆盖不足，而在扩展到 Uniswap v2 与 Uniswap v3 证据后，`Hybrid` 方法能够识别出 8 笔高置信度样本，说明 `Swap` 更适合作为 `Transfer` 主识别框架下的辅助语义验证信号。

总体来看，本文已经完成了原子套利识别 baseline 的复现、误报来源定位、协议语义过滤优化实现及局部区间实验验证，并通过多事件融合实验进一步明确了 `Transfer` 与 `Swap` 两类事件在实际识别中的角色分工，为后续进一步扩展识别范围、补充多协议语义和开展更多对比实验打下了基础。

## 6.2 后续展望

### 6.2.1 扩展更多协议的 `Swap` 事件

当前 `Hybrid` 实验已表明，扩大 `Swap` 语义来源能够提升高置信度样本的覆盖能力。后续可进一步统一 Balancer、Curve、DODO 等协议的交换事件表示，以增强跨协议路径恢复能力。

### 6.2.2 完善 odd token 与包装合约前置识别

当前 odd token 仍是优化后最主要的剩余误差来源。后续可围绕异常 token 转移模式、包装合约映射和特殊资产行为开展更细粒度建模，尝试将此类判断从后处理阶段前移到识别阶段。

### 6.2.3 补充更多验证实验

为进一步增强论文结论的稳健性，后续可在新的 1000 个区块局部区间上重复开展 baseline 与协议语义过滤对比实验，并结合人工抽样核验进一步评估过滤规则对真实样本的保留能力。

### 6.2.4 构建更完整的评价体系

除误报率之外，未来还可进一步结合人工标注、交易复现和收益估计等方式，对候选套利样本的真实性进行更深入验证，从而逐步构建更完善的准确率与召回率评价体系。

# 参考文献

[1] Buterin V. A Next-Generation Smart Contract and Decentralized Application Platform[EB/OL]. 2014.

[2] Vogelsteller F, Buterin V. ERC-20: Token Standard[EB/OL]. Ethereum Improvement Proposal 20, 2015.

[3] Ethereum Improvement Proposals. ERC-3156: Flash Loans[EB/OL]. 2021.

[4] Daian P, Goldfeder S, Kell T, et al. Flash Boys 2.0: Frontrunning, Transaction Reordering, and Consensus Instability in Decentralized Exchanges[C]//2020 IEEE Symposium on Security and Privacy. 2020: 910-927.

[5] Werner S M, Perez D, Gudgeon L, et al. SoK: Decentralized Finance (DeFi)[J]. arXiv preprint arXiv:2101.08778, 2021.

[6] Qin K, Zhou L, Gervais A. Attacking the DeFi Ecosystem with Flash Loans for Fun and Profit[C]//Financial Cryptography and Data Security. 2021.

[7] Zhou L, Qin K, Torres C F, et al. High-Frequency Trading on Decentralized On-Chain Exchanges[C]//2021 IEEE Symposium on Security and Privacy. 2021: 428-445.

[8] Liao X, Mamageishvili A, Mittal P. Quantifying Blockchain Extractable Value: How Dark Is the Forest?[C]//2023 IEEE Symposium on Security and Privacy. 2023.

[9] Torres C F, Camino R, State R. Frontrunner Jones and the Raiders of the Dark Forest: An Empirical Study of Frontrunning on the Ethereum Blockchain[C]//USENIX Security Symposium. 2021: 1343-1359.

[10] Angeris G, Kao H T, Chiang R, et al. An Analysis of Uniswap Markets[EB/OL]. arXiv:1911.03380, 2019.

[11] Adams H, Zinsmeister N, Robinson D. Uniswap v2 Core Whitepaper[EB/OL]. 2020.

[12] Adams H, Zinsmeister N, Salem M, et al. Uniswap v3 Core Whitepaper[EB/OL]. 2021.

[13] Angeris G, Chitra T. Improved Price Oracles: Constant Function Market Makers[C]//Proceedings of the 2nd ACM Conference on Advances in Financial Technologies. 2020: 80-91.

[14] Angeris G, Evans A, Chitra T, et al. Optimal Routing for Constant Function Market Makers[EB/OL]. arXiv:2204.05238, 2022.

[15] Angeris G, Agrawal A, Evans A, et al. Constant Function Market Makers: Multi-Asset Trades via Convex Optimization[M]//Handbook on Blockchain. 2022: 415-444.

[16] Angeris G, Chitra T, Diamandis T, et al. The Geometry of Constant Function Market Makers[EB/OL]. arXiv:2308.08066, 2023.

[17] Mohan V. Automated Market Makers and Decentralized Exchanges: a DeFi Primer[J]. Financial Innovation, 2022, 8(1): 20.

[18] Bartoletti M, Chiang J H, Lluch-Lafuente A. A Theory of Automated Market Makers in DeFi[EB/OL]. arXiv:2102.11350, 2021.

[19] Wang Y, Heimbach L, Wattenhofer R. Behavior of Liquidity Providers in Decentralized Exchanges[EB/OL]. arXiv:2105.13822, 2021.

[20] Berg J A, Fritsch R, Heimbach L, et al. An Empirical Study of Market Inefficiencies in Uniswap and SushiSwap[M]//Financial Cryptography and Data Security Workshops. 2023: 238-249.

[21] Chen J, Wang Y, Zhou Y, et al. Understanding the Security Risks of Decentralized Exchanges by Uncovering Unfair Trades in the Wild[C]//2023 IEEE European Symposium on Security and Privacy. 2023.

[22] Heimbach L, Schertenleib E, Wattenhofer R. Exploring Price Accuracy on Uniswap V3 in Times of Distress[C]//Proceedings of the 2022 ACM SIGSAC Conference on Computer and Communications Security. 2022.

[23] Johnson D B. Finding All the Elementary Circuits of a Directed Graph[J]. SIAM Journal on Computing, 1975, 4(1): 77-84.

[24] AAASS554. goldphish[EB/OL]. GitHub repository. https://github.com/AAASS554/goldphish .

# 致谢

在本课题的研究与论文撰写过程中，指导教师在选题、技术路线、实验推进与论文修改方面给予了耐心指导与帮助，在此表示衷心感谢。同时，也感谢家人和同学在整个毕业设计阶段提供的支持与鼓励。本文的实现与实验工作仍有许多不足，恳请各位老师批评指正。
