# 3.3 初级组要求与提交材料映射

本页按用户提供的《全国大学生嵌入式芯片与系统设计竞赛'2026 FPGA 创新设计赛道选题指南（AMD）》整理，定位为 **3.3 自主选题赛道、初级组**。队员学历/年级尚未在本轮核验，实际资格以报名审核为准；混合年级队伍按指南规定的最高年级/学历归组。

## 规则来源

| 项目 | 本轮核对依据 |
|---|---|
| 附件标识 | 用户提供的 28 页 PDF；原件不在本仓库重分发 |
| SHA-256 | `c6ad82acd4f7bdcd13bd412e232ed85d05f2a87dd5e2cdd04f9d219f88b569fc` |
| 3.3 正文 | PDF 物理页 22—25，对应印刷页 19—22 |
| 五项权重 | 3.3.5.5；PDF 物理页 25、印刷页 22 |
| 英文海报 | 第六部分“其它”；PDF 物理页 28、印刷页 25 |
| 公告入口 | [赛事官网](http://www.fpgachina.cn/)；后续条件以实际取得的《评分细则》及公告为准 |

本轮核对的是上述用户附件，不以其他网页版本替换它。原有 DOCX 模板中的摘要/章节字数属于另一份模板的历史提取，不能写成该指南 3.3 的字数限制。当前[设计报告](../../report/design_report.md)按已确认的七项内容组织。

## 五项评分材料

| 3.3.5.5 评测项 | 权重 | 本作品的材料入口 | 需要保持的判断范围 |
|---|---:|---|---|
| 创新性与应用价值 | 30 | [产品定位](../overview.md)、[报告第1节](../../report/design_report.md#section-background)、[贡献与来源](../../THIRD_PARTY.md) | 教学/固定桌面交互工位；课程基础、厂商模型/SDK 与团队新增工程分开归属 |
| 性能与资源优化效果 | 20 | [证据矩阵](EVIDENCE_MATRIX.md)、[报告第4节](../../report/design_report.md#section-optimization) | 旧颜色不同分辨率配置是系统取舍；原颜色完整实现与门控 OOC 资源不构成优化前后对比 |
| 功能正确性与设计完整性 | 20 | [系统工程](../../fpga/system_pspl/README.md)、[报告第2—3节](../../report/design_report.md#section-principle)、原部署与模块记录 | 四功能源码、旧独立模块记录和现用 VM 演示分别核查；新 profile 无完整板级验证结论 |
| 大模型协作与技能包 | 15 | [AI协作记录](../../report/ai_collaboration.md)、[Skill](../../skill/README.md)、[报告第5—6节](../../report/design_report.md#section-ai) | 使用真实提示词/审计/提交来源；提交摘要不冒充完整逐字对话；运行时 YOLO/Vosk 分工不是开发协作记录 |
| 文档质量与可复现性 | 15 | [项目文档](../README.md)、[报告第7节](../../report/design_report.md#section-reproduce)、[发布清单](../../deliverables/submission/manifest.json) | 当前安装器/测试共同选择独立冻结payload，新PS/PL入口使用开发源码；明确版本/环境与外部条件 |

权重用于材料组织，不用于预测得分或保证奖项。测试/断言次数、提交数和文件数不作为识别性能指标。

## 七项设计报告内容

| 3.3.5.3 要求 | 对应报告 | 关联材料 |
|---|---|---|
| 选题背景与创新点、前人工作 | [1.背景与创新](../../report/design_report.md#section-background) | 产品简介、Yahboom/TOMRA/AMP 一手资料、第三方边界 |
| 设计原理与功能框图 | [2.原理与框图](../../report/design_report.md#section-principle) | 产品功能、现用演示、四功能源码连接分别画图 |
| 软硬件划分依据与接口设计 | [3.划分与接口](../../report/design_report.md#section-partition) | PS/PL/VM 分工、像素/PCM 格式、AXI/FIFO、配置快照与任务协议 |
| 优化过程与性能/资源前后对比 | [4.优化与证据](../../report/design_report.md#section-optimization)、[数值附录](../../report/design_report.md#appendix-a) | 配置取舍和同范围比较条件；附录从固定证据矩阵转录并附SHA/blob/文件哈希，未取得的对比留为缺项 |
| 大模型协作记录、纠错轨迹、工作流 | [5.AI协作](../../report/design_report.md#section-ai)、[原始摘录](../../report/ai_interaction_excerpt.md) | 11条实际用户/助手消息、日期/角色/原文本哈希及模型字段；不公开整套聊天库，原始与案例摘要分开 |
| Skill 提炼、效果证据与边界 | [6.Skill提炼](../../report/design_report.md#section-skill) | 四个可复用工作流及其来源、失效条件；新 Skill 无跨题目运行收益声明 |
| 从零复现的操作步骤 | [7.复现说明](../../report/design_report.md#section-reproduce) | 版本选择→合法依赖→构建/设备条件→配置→未来运行/记录；本轮不执行 |

## 其他提交条件与当前对应

| 指南条款 | 条件 | 对应交付或明确缺项 |
|---|---|---|
| 3.3.1.1、3.3.3.2 | 初级组器件范围、声明具体型号 | Z19，`xczu19eg-ffvc1760-2-i`，属于 UltraScale+；不是强制 PYNQ-Z2/KR260。年级资格由报名流程确认 |
| 3.3.2 | RTL、HLS、PS 软件及其组合均可；PYNQ 推荐 | 当前采用 RTL+PS Linux UIO/PIO；未将 UIO 客户端称作 PYNQ Overlay |
| 3.3.3.1 | 推荐 Vivado/Vitis 2026.1 或 2025.2；其他版本需说明并提供复现脚本 | 颜色/新 profile 固定 2020.1，独立 MIPI 有自己的 2020.2_AR75986 条件；原因和执行范围集中于系统工程表；没有推荐版本复现记录 |
| 3.3.3.2、3.3.5.1 | 板上跑通、实测输出、参考比对、综合/实现报告 | 已有旧颜色、独立 MIPI 和 VM 演示的各自记录；四功能 profile 的新 bit/XSA、完整实现报告、板级输出和同输入参考比对尚缺；旧记录不能替代 |
| 3.3.3.3 | 强烈要求 GitHub/Gitee 开源，采用可再分发许可 | 仓库与 Apache-2.0 项目代码；模型、SDK、媒体及第三方 IP 沿用各自许可，不以根许可覆盖外部材料 |
| 3.3.5.2 | 普通 Skill 放入 `skill/`，含适用范围、用法、失效条件及效果依据 | [Skill入口](../../skill/README.md)与四项工作流；这是要求提交的材料 |
| 3.3.2、3.3.5.2 | 通用 PYNQ Skill 另行加分 | 本轮不申报已经完成的 PYNQ Skill，不为加分临时更换数据通路；该加分方向与普通 Skill 提交要求分开 |
| 3.3.5.4 | 推荐 `src/sim/build/board/data/skill/report` 结构；可保留其他组织方式并给映射 | 设计源码对应 `fpga/`、`host/`、`robot/`；仿真对应各模块的 `sim/`；构建入口在 `fpga/system_pspl/` 与 `host/libpspl/`，生成物放源码树外；板端产物与数据见 `deliverables/` 及其 manifest；技能与报告分别在 `skill/`、`report/` |
| 3.3.5.4 | 文件名要求纯英文小写等；示例同时使用 `README.md` | 普通新文件使用小写英文；GitHub/工具入口、第三方和历史名称差异及处置见[收尾清单](../maintenance/release-20261030.md)，未声称取得额外豁免 |
| 第六部分 | 决赛自主选题队伍按 AMD 模板制作一页英文 PPT 海报，不含队伍信息，A4 彩印 | [英文内容稿](../../report/poster_copy_en.md)及素材映射已准备；官方 PPT 模板未取得，尚无模板成品 |

本轮只交付源码小修、材料与 Git 整理，没有新增执行类结果。当前材料可以说明已实现的工程及历史证据，尚不能据此宣布四功能 profile 已满足完整上板/实测提交条件。
