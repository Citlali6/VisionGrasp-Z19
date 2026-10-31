# 3.3 初级组要求与提交材料映射

本页按《全国大学生嵌入式芯片与系统设计竞赛'2026 FPGA 创新设计赛道选题指南（AMD）》整理，定位为 **3.3 自主选题赛道、初级组**。报名资格以赛事报名审核为准。

## 规则来源

| 项目 | 核对依据 |
|---|---|
| 附件标识 | 用户提供的 28 页 PDF；原件不在本仓库重分发 |
| SHA-256 | `c6ad82acd4f7bdcd13bd412e232ed85d05f2a87dd5e2cdd04f9d219f88b569fc` |
| 3.3 正文 | PDF 物理页 22—25，对应印刷页 19—22 |
| 五项权重 | 3.3.5.5；PDF 物理页 25、印刷页 22 |
| 英文海报 | 第六部分“其它”；PDF 物理页 28、印刷页 25 |
| 公告入口 | [赛事官网](http://www.fpgachina.cn/) |

## 五项评分材料

| 评测项 | 权重 | 材料入口 |
|---|---:|---|
| 创新性与应用价值 | 30 | [产品定位](../overview.md)、[报告第 1 节](../../report/design_report.md#section-background)、[贡献与来源](../../THIRD_PARTY.md) |
| 性能与资源优化效果 | 20 | [证据矩阵](EVIDENCE_MATRIX.md)、[报告第 4 节](../../report/design_report.md#section-optimization) |
| 功能正确性与设计完整性 | 20 | [系统工程](../../fpga/system_pspl/README.md)、[构建记录](../../deliverables/fpga_build_20261031/README.md)、[验证记录](../VALIDATION.md) |
| 大模型协作与技能包 | 15 | [AI 协作记录](../../report/ai_collaboration.md)、[Skill](../../skill/README.md)、[报告第 5—6 节](../../report/design_report.md#section-ai) |
| 文档质量与可复现性 | 15 | [项目文档](../README.md)、[报告第 7 节](../../report/design_report.md#section-reproduce) |

## 七项设计报告内容

| 3.3.5.3 要求 | 对应章节 | 关联材料 |
|---|---|---|
| 选题背景与创新点、前人工作 | [1. 背景与创新](../../report/design_report.md#section-background) | 产品简介、Yahboom/TOMRA/AMP 一手资料、第三方边界 |
| 设计原理与功能框图 | [2. 原理与框图](../../report/design_report.md#section-principle) | 产品功能、分拣配置、四功能工程连接 |
| 软硬件划分依据与接口设计 | [3. 划分与接口](../../report/design_report.md#section-partition) | PS/PL/上位机分工、像素/PCM 格式、AXI/FIFO、配置快照与任务协议 |
| 优化过程与性能/资源前后对比 | [4. 优化与证据](../../report/design_report.md#section-optimization)、[数值附录](../../report/design_report.md#appendix-a) | 配置取舍与同范围比较条件 |
| 大模型协作记录、纠错轨迹、工作流 | [5. AI 协作](../../report/design_report.md#section-ai)、[协作记录](../../report/ai_collaboration.md) | 实际任务出处、AI 输出、人工审阅与修正提交 |
| Skill 提炼、效果证据与边界 | [6. Skill 提炼](../../report/design_report.md#section-skill) | 四个可复用工作流及其来源、失效条件 |
| 从零复现的操作步骤 | [7. 复现说明](../../report/design_report.md#section-reproduce) | 版本选择、依赖、构建、配置与运行入口 |

## 其他提交条件

| 条款 | 要求 | 对应交付 |
|---|---|---|
| 3.3.1.1、3.3.3.2 | 初级组器件范围、声明具体型号 | Z19，`xczu19eg-ffvc1760-2-i`，UltraScale+ |
| 3.3.2 | RTL、HLS、PS 软件及其组合均可 | RTL + PS Linux UIO/PIO 组合 |
| 3.3.3.1 | 推荐 Vivado/Vitis 2026.1 或 2025.2；其他版本需说明并提供复现脚本 | 颜色链与四功能工程使用 Vivado 2020.1，保留 ALINX PS/IP 配置；构建入口与完整构建记录见[构建记录](../../deliverables/fpga_build_20261031/README.md) |
| 3.3.3.2、3.3.5.1 | 板上跑通、实测输出、参考比对、综合/实现报告 | Z19 颜色/语音/网格链有板端记录；四功能集成工程完成综合、实现与 bitstream 生成，报告与哈希见构建记录 |
| 3.3.3.3 | 强烈要求 GitHub/Gitee 开源，采用可再分发许可 | 仓库与 Apache-2.0 项目代码；模型、SDK、媒体及第三方 IP 沿用各自许可 |
| 3.3.5.2 | Skill 放入 `skill/`，含适用范围、用法、失效条件及效果依据 | [Skill 入口](../../skill/README.md)与四项工作流 |
| 3.3.2、3.3.5.2 | 通用 PYNQ Skill 另行加分 | 本项目采用 RTL + Linux UIO/PIO，不将 UIO 客户端称作 PYNQ Overlay |
| 3.3.5.4 | 推荐 `src/sim/build/board/data/skill/report` 结构 | 根 [README 工程目录](../../README.md#仓库结构)逐项列出实际位置 |
| 第六部分 | 决赛自主选题队伍按 AMD 模板制作一页英文 PPT 海报 | [英文内容稿](../../report/poster_copy_en.md)及素材映射 |

## 文件命名

目录与文件使用英文，正文使用中文。`README.md`、`SKILL.md`、`CMakeLists.txt`、`Makefile` 等工具约定名保留原样，与指南推荐结构中的示例一致。
