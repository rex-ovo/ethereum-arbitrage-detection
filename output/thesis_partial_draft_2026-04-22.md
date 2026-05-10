# 基于交易图与协议语义过滤的以太坊原子套利识别方法研究

## 封面信息

- 题目：基于交易图与协议语义过滤的以太坊原子套利识别方法研究
- 学生姓名：唐睿
- 学号：3220103690
- 学院：待按学校模板填写
- 行政班级：待按学校模板填写
- 指导教师：待按学校模板填写
- 完成时间：2026年

## 摘要

去中心化金融快速发展使得链上交易行为呈现出高度开放、可组合和跨协议交互的特征，原子套利作为其中一种典型的链上收益获取行为，具有交易过程复杂、执行速度快、涉及协议多样等特点。围绕原子套利交易的自动识别问题，本文基于以太坊主网历史数据，研究面向去中心化交易场景的交易数据采集、交易图建模、套利路径识别与识别准确度优化方法。

本文首先结合 `goldphish` 开源项目，对以太坊区块中的 ERC-20 `Transfer` 事件、已知去中心化交易所的 `Swap` 事件以及相关交易回执信息进行抓取与整理，并构建统一的结构化交易事件数据集。在此基础上，本文以 Token 为节点、以交易中的资产流动关系为边构建交易图模型，通过识别图中的闭环结构来发现潜在原子套利交易。针对仅依赖 `Transfer` 事件进行识别时容易产生误报的问题，本文进一步提出协议语义过滤优化方法，在原有 `Transfer` 主导识别框架上引入交易级协议过滤和地址级角色过滤，对 CoW Swap、Tokenlon、Dexible 等特殊协议交易以及 relayer、settlement、wrapper 等非交换节点进行约束，从而降低协议特定行为带来的识别偏差。

在局部验证区块区间 `24144053-24145052` 上，原始 baseline 方法共识别候选原子套利样本 2460 笔，误报样本 382 笔，误报率为 15.53%。引入协议语义过滤后，候选样本数降为 2202 笔，误报样本数降为 125 笔，误报率下降至 5.68%，其中 CoW Swap 与 relayer 相关误报均降为 0。进一步地，本文还设计了 `Swap-only` 与 `Hybrid` 两类融合识别实验。实验表明，仅依赖单协议显式 `Swap` 事件无法支撑有效样本识别，而将 `Swap` 事件作为 `Transfer` 主识别框架下的辅助语义验证信号，可以筛选出少量高置信度样本。实验结果说明，基于协议语义过滤的优化方法能够在有限覆盖损失下显著降低误报，提升原子套利识别结果的可靠性。

关键词：以太坊；去中心化金融；原子套利；交易图；协议语义过滤

## Abstract

With the rapid development of decentralized finance, on-chain transaction behaviors have become highly open, composable, and cross-protocol. Atomic arbitrage is a representative profit-seeking behavior in this environment, featuring complex execution logic, high time sensitivity, and strong dependence on multiple DeFi protocols. This thesis studies atomic arbitrage detection on Ethereum from the perspectives of transaction data collection, graph modeling, arbitrage-path identification, and accuracy optimization.

This work first builds a structured dataset from Ethereum mainnet historical data by collecting ERC-20 `Transfer` events, known decentralized exchange `Swap` events, and transaction receipts based on the `goldphish` open-source project. A transaction graph is then constructed where tokens are modeled as nodes and asset movements are modeled as directed edges. Potential atomic arbitrage opportunities are identified by detecting cycles in the graph. To address the false positives caused by a transfer-only strategy, this thesis further proposes a protocol-semantic filtering method. The optimized method keeps transfer-based identification as the primary framework while introducing transaction-level protocol filtering and address-role filtering, thereby excluding settlement contracts, relayers, wrappers, and other non-exchange entities that frequently lead to semantic misclassification.

On the local evaluation block range `24144053-24145052`, the baseline method identifies 2460 candidate atomic arbitrages, among which 382 are labeled as false positives, corresponding to a false-positive rate of 15.53%. After applying protocol-semantic filtering, the number of candidates decreases to 2202, while false positives drop to 125 and the false-positive rate decreases to 5.68%. In particular, CoW Swap-related and relayer-related false positives are both reduced to zero. In addition, this thesis explores `Swap-only` and `Hybrid` detection strategies. The results show that relying solely on explicit swap events from a single protocol is insufficient for effective arbitrage detection, while using swap events as auxiliary semantic validation signals under a transfer-based framework can identify a small set of high-confidence samples. These results demonstrate that protocol-semantic filtering can significantly improve detection reliability with only limited loss of coverage.

Keywords: Ethereum; decentralized finance; atomic arbitrage; transaction graph; protocol-semantic filtering

# 1 绪论

## 1.1 研究背景

以太坊等智能合约平台的发展推动了去中心化金融生态的快速扩张。围绕代币兑换、流动性提供、借贷清算、聚合交易与闪电贷等场景，链上形成了大量可组合的金融协议。与传统中心化交易系统相比，去中心化金融中的交易执行、资产流动与合约调用过程全部公开记录在区块链账本中，这为开展链上行为分析提供了重要的数据基础。

原子套利是 DeFi 环境中具有代表性的交易行为之一。该类交易通常在单笔交易内完成多次兑换、借贷或资金流转，通过利用不同协议间的价格差、流动性差异或资产定价偏差，在交易结束时获得净收益。由于原子套利具有单笔交易内闭环完成、无需承担跨交易持仓风险等特点，其识别与分析不仅能够帮助理解链上市场效率，也有助于研究交易路由、协议交互与 MEV 行为等问题。

然而，链上原子套利的自动识别并不容易。一方面，真实交易往往跨越多个协议与合约，既包含显式的 `Swap` 事件，也包含大量普通 `Transfer` 事件、包装合约操作、聚合路由与 settlement 行为。另一方面，不同 DeFi 协议在日志结构和内部记账方式上存在明显差异，单纯依赖某一种事件类型进行识别，容易出现遗漏或误判。因此，围绕“如何在真实链上复杂交易环境中更准确地识别原子套利交易”展开研究，具有较强的工程价值和研究意义。

## 1.2 研究意义

本文研究的意义主要体现在以下几个方面。

首先，从理论与方法层面看，原子套利识别涉及链上多源事件融合、交易图建模、闭环路径分析和异常样本过滤等问题，是区块链数据分析与图计算方法在金融场景中的典型应用。对该问题进行研究，有助于深化对链上复杂交易结构的理解。

其次，从工程实现层面看，现有基于链上事件的套利识别方法往往依赖单一事件类型或较强的协议假设，在真实 DeFi 场景下容易受到协议实现差异的影响。本文通过在 `Transfer` 主识别框架中引入协议语义过滤，对 CoW Swap、relayer、wrapper 等特殊场景进行约束，可以为后续构建更稳健的链上交易分析工具提供参考。

最后，从应用层面看，原子套利识别结果能够服务于 MEV 研究、链上市场行为分析、协议风险评估与策略复现等任务。通过提高候选套利样本的可信度，可以为后续开展更深入的交易行为研究提供更加可靠的数据基础。

## 1.3 研究内容

结合开题报告和当前已经完成的项目实现，本文的主要研究内容包括以下四个方面。

第一，围绕以太坊主网历史数据开展交易事件采集与标准化处理。重点提取 ERC-20 `Transfer` 事件、去中心化交易所 `Swap` 事件以及与交易回执相关的日志信息，并构建统一的数据存储结构，为后续交易图分析提供基础数据。

第二，建立面向原子套利识别的交易图模型。本文将 Token 视为节点，将交易中不同资产之间的流动关系抽象为边，通过对交易内部资产流的分析构建闭环检测基础。

第三，复现并实现基于 `Transfer` 事件的原子套利识别方法。在现有开源项目基础上，完成 baseline 流程的部署、运行与局部实验，并在真实区块范围上得到候选套利样本及其误报分布。

第四，针对 baseline 方法在协议特定行为场景中的误判问题，提出协议语义过滤优化方法，并进一步设计 `Swap-only` 与 `Hybrid` 对比实验，分析不同事件建模方式在覆盖率与准确度上的差异。

## 1.4 论文结构安排

本文共分为六章，各章内容安排如下。

第一章为绪论，介绍课题背景、研究意义、主要研究内容与论文结构。

第二章介绍与研究相关的关键技术，包括以太坊交易机制、ERC-20 事件、去中心化交易协议、原子套利及现有识别方法存在的问题。

第三章围绕数据采集与交易图建模展开，介绍交易数据来源、数据标准化过程以及面向套利识别的交易图构建方法。

第四章介绍原子套利识别方法的实现过程与准确度优化思路，重点说明 baseline 复现、协议语义过滤优化及 `Swap-only`、`Hybrid` 探索实验的设计。

第五章给出实验结果与分析，对 baseline 方法和优化方法在局部区间上的识别结果、误报分布和融合实验效果进行对比讨论。

第六章对全文工作进行总结，并给出后续可进一步开展的改进方向。

# 2 相关技术与问题分析

## 2.1 以太坊交易与 ERC-20 事件

以太坊是一种支持图灵完备智能合约的公有链平台。用户通过发送交易调用智能合约函数，合约执行过程中可能修改链上状态并产生事件日志。对于链上行为分析而言，区块、交易、回执与事件日志共同构成了最基本的数据来源。

ERC-20 是以太坊上最常见的同质化代币标准。其核心事件 `Transfer` 用于记录代币在地址之间的转移过程，通常包含发送方、接收方和转账数量等信息。在 DeFi 场景中，几乎所有代币交换、包装、清算和路由操作都会伴随 `Transfer` 事件。因此，`Transfer` 事件具有覆盖面广、协议通用性强的优点，是构建链上资产流动关系的重要基础。

但与此同时，仅依赖 `Transfer` 事件也存在明显局限。因为 `Transfer` 只描述代币的移动结果，并不直接说明该移动对应的是交换、包装、内部结算还是其他协议逻辑。对于聚合器、settlement 合约和内部记账类协议而言，单纯依据 `Transfer` 事件容易错误推断交换关系，进而导致套利识别结果偏差。

## 2.2 去中心化交易协议与原子套利

去中心化交易协议是 DeFi 中最核心的基础设施之一。不同协议通过自动做市商、订单撮合或 Vault 内部记账等方式完成资产兑换。以 Uniswap v2 为代表的 AMM 协议通常会在交易执行时发出明确的 `Swap` 事件，这类事件能直接反映代币输入输出关系与交换池地址，因此在语义上比 `Transfer` 更接近真实的交换行为。

原子套利通常表现为：在单笔交易内，交易发起者或相关执行合约通过一系列兑换操作，使得某种代币最终回到初始持有方并实现净增益。从图结构角度看，这一过程通常对应于一条或多条闭环路径。若仅从资产流视角进行抽象，原子套利可以被表示为“若干 token 边构成的闭环，且路径起点和终点在利润结算意义上相同”。

然而，真实原子套利并不总是发生在单一协议内部。很多交易会跨越多个 DEX、包装合约与聚合协议，因此套利路径的恢复不仅依赖交换事件本身，也需要结合资产转移的上下文信息进行辅助分析。

## 2.3 现有识别方法及不足

当前项目的 baseline 方法以 `Transfer` 事件为核心，通过解析单笔交易中的代币流入流出关系，推断可能的交换节点，并进一步构造 token 级有向图，再基于闭环检测识别潜在套利路径。该方法的优点在于协议适配范围较广，不依赖单一 DEX 的日志定义，因而具有较强的覆盖能力。

但通过实验可发现，纯 `Transfer` 方法容易将一些并非真实交换节点的地址误识别为 exchange。例如，在 CoW Swap 等 settlement 类协议中，交易级执行合约承担了集中清算与结算功能，但其并不应被视为传统意义上的交易池；在部分 relayer 场景下，中继地址也可能因代币收付路径而被错误纳入套利环中。此外，部分 odd token 或包装合约会产生不符合一般交换语义的代币转移模式，从而进一步增加误报。

另一方面，仅依赖显式 `Swap` 事件的方案虽然具备更强的交换语义，但其覆盖能力又受到协议范围和事件统一性的限制。特别是在跨协议、多跳和复杂路由场景下，单一协议的 `Swap` 事件往往不足以恢复完整套利路径。因此，如何在覆盖能力与识别准确度之间取得平衡，是当前原子套利识别中需要重点解决的问题。

# 3 数据采集与交易图建模

## 3.1 数据来源与采集流程

本文的实验基础建立在 `goldphish` 开源项目之上。该项目面向以太坊历史套利分析，主要包含历史样本抓取、交易路径分析和交易所建模等模块。结合本文任务，重点使用了 `backtest/gather_samples` 相关流程对交易数据进行抓取与整理。

在数据采集阶段，本文主要使用以下几类链上数据：

1. 区块与交易基本信息，用于确定区块范围、交易哈希、gas 消耗及交易执行上下文。
2. ERC-20 `Transfer` 事件，用于描述交易内的资产流动关系。
3. 已知去中心化交易协议的 `Swap` 事件，用于补充显式交换语义。
4. 交易回执与日志信息，用于恢复单笔交易中的完整事件序列。

项目运行依赖 PostgreSQL 数据库存储中间结果，并通过 WebSocket RPC 节点访问以太坊历史数据。针对公共 RPC 提供商在日志查询数量和连接稳定性上的限制，本文在实现过程中对日志查询与回执请求增加了重试与范围切分机制，以提高样本抓取的连续性和稳定性。

## 3.2 数据标准化与结构化存储

在原始链上日志基础上，本文对不同来源的交易事件进行了统一整理。对于 `Transfer` 事件，统一抽取代币地址、发送方、接收方和数量信息；对于 `Swap` 事件，则额外记录交易池地址、输入输出代币及对应数量。通过数据库表结构对这些事件进行规范化存储，可以在后续分析中通过交易哈希将不同事件类型对齐到同一笔交易内部。

为了支持原子套利识别，项目还维护了与样本相关的多张结果表，例如候选套利样本表、套利环表、环中 exchange 表、误报标签表和 odd token 标签表等。这样既便于记录原始检测结果，也便于在后处理阶段开展误报分析与策略对比。

## 3.3 面向套利识别的交易图建模

本文采用基于 Token 的交易图建模方式。对于单笔交易中的候选交换行为，将输入代币和输出代币分别视为有向边的起点与终点，从而在 token 层面构造有向图。若图中存在闭环，则说明交易内部可能出现“某类代币经过一系列交换后重新回到起始状态”的结构，这正是原子套利的重要图特征。

在 baseline 方法中，交换边主要通过 `Transfer` 事件推断得到。具体而言，若某地址在同一笔交易内对某一种代币表现为净流入、对另一种代币表现为净流出，则该地址可能被视为一个候选交换节点。将所有候选交换节点形成的 token 变换关系汇总后，即可在图中开展闭环检测。

这种建模方式的优点是协议无关性较强，只要代币转移被记录为 ERC-20 `Transfer` 事件，就有机会被纳入分析。但其缺点在于：图中的边是否真实对应某次交换，往往仍需结合协议语义进一步验证。

# 4 原子套利识别方法实现与准确度优化

## 4.1 Transfer-only baseline 方法实现

本文首先复现了 `goldphish` 中基于 `Transfer` 事件的原子套利识别流程。该流程在读取单笔交易回执后，提取其中所有 ERC-20 `Transfer` 事件，并统计各地址在不同代币上的流入流出情况。之后，通过筛选满足“单一代币流入、单一代币流出”条件的候选地址，构造 token 之间的交换边，并利用闭环检测算法识别可能的套利路径。若候选路径能够形成 token 闭环，并满足利润方向上的净增益条件，则将其记录为候选原子套利样本。

为了让 baseline 能够在真实 RPC 环境中稳定运行，本文对样本抓取过程进行了工程改造：一是使用带自动重连能力的 Web3 连接方式替换原始 provider；二是对交易回执查询加入重试逻辑；三是对 `Transfer` 事件日志查询加入递归切分策略，以绕开公共节点的单次日志返回数量上限。这些改造不改变 baseline 的识别逻辑本身，但显著提高了实验过程的可执行性。

## 4.2 协议语义过滤优化

在 baseline 复现基础上，本文重点开展了识别准确度优化。通过对误报样本进行分析可以发现，误报主要集中于三类来源：第一类是 CoW Swap 等 settlement 协议交易，这类交易的执行合约容易在资产流层面被误识别为交换节点；第二类是 relayer 或代理类地址被错误纳入 exchange 集合；第三类是 odd token 或包装合约产生的异常转账模式。

针对上述问题，本文提出了协议语义过滤优化方法，主要包括以下两个层面的改进。

第一，交易级协议过滤。在识别入口处，对交易目标地址进行协议语义判断。若交易属于已知的 CoW Swap、Tokenlon、Dexible 等 settlement 或聚合类协议交易，则不再将其继续作为普通套利交易进行分析。这样可以从源头上减少将清算和撮合交易误识别为原子套利的情况。

第二，地址级角色过滤。在候选 exchange 提取阶段，对已知 router、relayer、wrapper、settlement 等地址进行排除，避免这些并非真实交换池的地址被纳入闭环图构建。特别是在局部实验中，本文进一步根据误报样本统计结果补充了若干真实出现的 relayer 地址，从而增强了地址角色过滤的有效性。

该优化方法的核心思想并非完全抛弃 `Transfer` 主导识别，而是在保留其覆盖能力的前提下，引入协议语义约束来抑制典型误报来源。

## 4.3 Swap-only 融合识别探索

为了进一步评估显式 `Swap` 事件在原子套利识别中的作用，本文设计了 `Swap-only` 探索实验。该实验仅使用 `uniswap_v2_swap_events` 中记录的 `Swap` 事件来构建 token 图，不再使用 `Transfer` 事件推断 exchange 行为，并在发现闭环后再用 `Transfer` 辅助确认利润方向。

在局部实验区间 `24144053-24145053` 内，共存在 4006 笔至少包含 Uniswap v2 `Swap` 事件的交易。然而，采用 `Swap-only` 方案进行识别时，最终未检测到有效原子套利样本。该结果表明，仅依赖单协议的显式 `Swap` 事件虽然具有更强的交换语义，但在真实 DeFi 场景中覆盖能力明显不足，难以恢复跨协议、多跳或包含特殊合约交互的完整套利路径。

## 4.4 Hybrid 融合识别探索

在 `Swap-only` 基础上，本文进一步设计了 `Hybrid` 融合识别方法。与将 `Swap` 作为主构图边的方案不同，当前 `Hybrid` 方法采用“`Transfer` 主识别 + `Swap` 语义验证”的思路：首先使用 baseline 的 `Transfer` 方法识别候选套利样本，再要求该候选样本中的至少一个 exchange 地址能够被真实 `Swap` 事件支持，从而筛选出一小批语义一致性更强的高置信度样本。

在同一局部实验区间内，`Hybrid` 方法最终识别出 3 笔高置信度原子套利样本。这 3 笔样本分别位于区块 `24144600`、`24145017` 和 `24145039`，均为单环套利结构，利润 token 主要为 `T-REX` 和 `SPIKE`。实验结果说明，将 `Swap` 事件作为 `Transfer` 框架下的辅助语义约束，比完全依赖 `Swap` 事件更具可行性；但在当前实现阶段，`Hybrid` 更适合作为高精度补充筛选模块，而不适合完全替代高覆盖的 baseline 方法。

# 5 实验结果与分析

## 5.1 实验设置与数据范围

本文实验基于以太坊主网历史交易数据，在 Docker 容器与 PostgreSQL 数据库环境下完成。考虑到完整时间窗口的链上抓取成本较高，同时为了保证优化前后结果可比，本文选取区块区间 `24144053-24145052` 作为局部验证区间，对 baseline 方法与不同优化方法进行对比分析。

在局部对比之外，本文也完成了更大范围的阶段性样本抓取。在已处理样本中，baseline 共识别候选原子套利样本 16178 笔，误报样本 2175 笔，误报率为 13.44%，其中 CoW Swap、odd token 与 relayer 相关误报占据主要部分。这一阶段性结果为后续局部验证区间上的优化设计提供了依据。

## 5.2 Baseline 与协议语义过滤方法对比

在局部验证区间 `24144053-24145052` 上，baseline 方法共识别候选原子套利样本 2460 笔，其中误报样本 382 笔，误报率为 15.53%，误报过滤后保留样本 2078 笔。对误报来源进行进一步划分可以发现，CoW Swap 误报 188 笔，odd token 误报 143 笔，relayer 被误识别为 exchange 的样本为 66 笔，tokenlon 相关误报为 3 笔。

在引入协议语义过滤优化后，同一区间内的候选样本数下降为 2202 笔，误报样本数下降为 125 笔，误报率降为 5.68%，误报过滤后保留样本 2077 笔。进一步分析误报原因可知，剩余误报全部来自 odd token，CoW Swap、relayer 与 tokenlon 相关误报均降为 0。由此可见，本文提出的协议语义过滤方法对协议特定误判具有显著抑制作用。

从样本规模变化来看，协议语义过滤后的候选样本数相较 baseline 减少了 258 笔，下降比例约为 10.49%。然而，误报过滤后两者保留的有效样本数几乎一致，baseline 为 2078 笔，优化方法为 2077 笔，仅相差 1 笔。这表明，优化过程主要剔除的是原本会被后处理判定为误报的候选样本，并未显著损害真正有效套利样本的保留能力。换言之，该方法在牺牲少量覆盖率的同时，换取了明显的精度提升。

表 5-1 给出了 baseline 与协议语义过滤优化方法的对比结果。

| 方法 | 样本总数 | 误报样本数 | 误报率 | CoW Swap | odd token | relayer | tokenlon | 过滤后样本数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Transfer-only Baseline | 2460 | 382 | 15.53% | 188 | 143 | 66 | 3 | 2078 |
| Ours（协议语义过滤） | 2202 | 125 | 5.68% | 0 | 125 | 0 | 0 | 2077 |

## 5.3 Transfer-only、Swap-only 与 Hybrid 融合实验对比

为了进一步分析不同事件建模方式对识别结果的影响，本文设计了 `Transfer-only`、`Swap-only` 和 `Hybrid` 三组对比实验。

其中，`Transfer-only` 即当前 baseline 及其协议语义过滤方法所在的主框架，具有较高的覆盖能力；`Swap-only` 仅依赖单协议显式 `Swap` 事件进行识别；`Hybrid` 则在 `Transfer` 主识别基础上引入 `Swap` 语义验证，用于筛选高置信度样本。

实验结果表明，在局部区间内，`Swap-only` 方法虽然处理了 4006 笔包含 Uniswap v2 `Swap` 事件的交易，但最终未识别出有效原子套利样本。这说明单协议 `Swap` 事件覆盖不足，难以恢复真实链上复杂套利路径。相比之下，`Hybrid` 方法共识别出 3 笔高置信度样本，均为单环结构，且其 exchange 地址组合具有较强重复性，说明当前 `Hybrid` 版本更倾向于筛选结构清晰、语义一致性强的少量样本，而不追求与 `Transfer-only` 相同的覆盖规模。

从方法定位上看，`Transfer-only` 适合作为高覆盖检测框架，`Swap-only` 语义更强但覆盖明显不足，而 `Hybrid` 则适合作为一种高精度补充识别策略。三者的对比结果进一步说明，在当前数据条件下，完全以 `Swap` 替代 `Transfer` 并不可行，更合理的方向是在 `Transfer` 主识别框架中引入 `Swap` 语义和协议语义约束。

表 5-2 给出了三种方法在局部实验中的识别结果概况。

| 方法 | 样本数 | 主要特征 |
| --- | ---: | --- |
| Transfer-only | 2460 | 覆盖高，但误报相对较多 |
| Swap-only | 0 | 交换语义强，但单协议覆盖不足 |
| Hybrid | 3 | 高置信度样本较少，适合作为补充筛选 |

## 5.4 结果讨论

综合上述实验可以看出，本文工作的核心贡献并不在于完全替代 `Transfer` 主识别框架，而在于通过协议语义过滤显著降低其中最主要的协议型误报来源。CoW Swap 与 relayer 误报在优化后被完全消除，说明交易级协议过滤与地址级角色过滤对于真实链上复杂交易的语义纠偏是必要的。

另一方面，`Swap-only` 和 `Hybrid` 的探索结果也表明，显式 `Swap` 事件在当前阶段更适合作为补充性验证信号，而不是唯一的识别依据。这是因为很多真实交易涉及跨协议交互、包装合约、异常 token transfer 或未统一抽象的交换事件，仅凭单协议的 `Swap` 数据难以完整恢复套利路径。因此，在后续工作中，更可行的方向是继续在 `Transfer` 主框架上引入更丰富的协议语义、更多协议的标准化 `Swap` 事件，以及对特殊合约交互模式的识别。

# 6 总结与展望

## 6.1 工作总结

本文围绕以太坊链上原子套利识别问题，基于 `goldphish` 开源项目完成了交易数据采集、交易图建模、baseline 方法复现和准确度优化实验。本文首先对 ERC-20 `Transfer` 事件、已知去中心化交易所 `Swap` 事件和交易回执信息进行了抓取与结构化处理，并在此基础上构建了面向原子套利识别的 token 级交易图。随后，本文复现了基于 `Transfer` 的原子套利识别方法，并在真实区块范围内获得候选套利样本。

针对 baseline 方法在 CoW Swap、relayer 和 odd token 等场景下误报较多的问题，本文进一步提出协议语义过滤优化方法。实验结果表明，该优化方法能够在有限覆盖损失下显著降低误报率，使局部实验区间内的误报率从 15.53% 下降到 5.68%。此外，本文还进一步探索了 `Swap-only` 与 `Hybrid` 两种融合识别思路，验证了单一 `Swap` 事件方法覆盖不足，而 `Swap` 更适合作为 `Transfer` 主识别框架下的辅助语义验证信号。

总体来看，本文已经完成了原子套利识别 baseline 的复现、误报来源定位、协议语义过滤优化实现及局部区间实验验证，为后续进一步扩展识别范围、补充多协议语义和开展更多对比实验打下了基础。

## 6.2 后续展望

虽然本文已经完成了当前阶段的主要工作，但仍有若干方向值得继续深入。

第一，可以继续扩展标准化 `Swap` 事件的协议范围。当前实验中的 `Swap-only` 与 `Hybrid` 主要使用了 Uniswap v2 的 `Swap` 数据，后续可考虑进一步统一 Uniswap v3、Balancer、Curve 等协议的交换事件表示，以增强跨协议路径恢复能力。

第二，可以继续完善 odd token 与包装合约的前置识别逻辑。当前 odd token 误报仍然是优化后剩余的主要误差来源，后续可进一步分析此类交易的共同模式，并将其前移到识别阶段进行过滤。

第三，可以在更大时间窗口和更完整区块范围上开展持续实验。当前局部对比实验已经验证了优化方法的有效性，但若要形成更全面的统计结论，仍需在更长时间范围内继续收集并分析样本。

第四，可以进一步结合交易复现、收益估计和更多人工校验方式，对候选套利样本的真实性进行更深入验证，从而构建更完善的准确率与召回率评价体系。

以上工作将有助于进一步提升原子套利识别方法的适用性和可靠性。

