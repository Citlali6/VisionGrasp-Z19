# 小亚智分 · 评委阅读入口

作品：**基于 Z19 PS/PL 协同设计的语音视觉垃圾分拣工作站**。申报方向为 AMD FPGA 创新设计赛道 3.3 自主选题初级组，资格按实际队员信息确认。

| 阅读入口 | 用途 |
|---|---|
| [产品首页](../../README.md)、[产品说明](product_brief.md) | 了解固定工位用户、一次语音分类任务、教学与科普场景，以及与厂商教程/工业方案的关系 |
| [四功能工程](../../fpga/system_pspl/README.md) | 查看 PS 采集/CPU 模型/坐标/ASR、PL 视频/音频/候选规则、AXI-Lite FIFO/PIO 与 VM 任务接口 |
| [系统架构](../ARCHITECTURE.md) | 分开阅读现用 VM 演示、独立 Z19 颜色链及新源码 profile 的连接 |
| [成果与证据矩阵](EVIDENCE_MATRIX.md) | 唯一指标表：每项数值附原版本、条件与来源，区分现场记录、独立仿真/OOC 和源码审阅 |
| [设计报告](../../report/design_report.md) | 按指南七项内容阅读背景、原理、划分、优化、AI 协作、Skill 和从零复现 |
| [要求映射](requirements_map.md) | 对照五项评分、七项报告和上板/海报等要求，查看已有材料与尚缺条件 |
| [开发协作案例](../../report/ai_collaboration.md)、[技能包](../../skill/README.md) | 查看真实提交/审计形成的纠错摘要，以及帧、寄存器、任务边界和只读观察的可复用流程 |
| [复现配置选择](../QUICKSTART.md)、[提交清单](../../deliverables/submission/manifest.json) | 先选冻结演示或新源码，再核对对应提交、环境、脚本、产物与许可证 |

## 团队贡献与复用基础

| 基础来源 | 本项目组织的工程 |
|---|---|
| Yahboom 机构、检测/分类教程、配套模型与 ROS/SDK 动作 | 单次任务、播报完成门控、忙碌输入隔离、控制与展示解耦、版本化部署；新可选客户端仍调用原固定工位动作 |
| laperex HSV 算术、ALINX PS 配置、AMD IP | 视频包装、RGB 校正、ROI/一阶矩、音频定点链、FIFO/AXI 事务、快照及 C/Python 接口；保留依赖原许可 |
| YOLO 与 Vosk 运行库 | 从真实厂商调用提取模型契约，分离来源与目标环境，建立受限语音事件和同帧任务协议；语义网络在 PS CPU |

详细归属和许可见 [THIRD_PARTY](../../THIRD_PARTY.md)，算法/接口入口见 [FPGA](../../fpga/README.md)、[PS 软件](../../host/README.md)和[机械臂](../../robot/dofbot/README.md)。以上是工程贡献边界，不是原创率或性能排名。

## 材料与版本的边界

现用演示安装的文件来自 `8a2a6fd544cb6b79e868b8a710dc34b6027c6c8d`，保存为独立[冻结payload](../../deliverables/dofbot_demo_20261029/README.md)，匹配原部署清单；当前安装器和测试均明确使用该来源，新源码及可选界面不替换它。新四功能 profile 尚缺合法权重/类序、目标环境、新镜像/UIO、匹配标定、ASR 词典覆盖和联合运行结果，不能以旧独立结果证明其已上板完成。

[英文海报内容稿](../../report/poster_copy_en.md)提供匿名英文文案与真实素材对应，取得官方 PPT 模板后再排版。[发布清单](release_inventory.md)记录分支/PR、历史资料、恢复备份和命名兼容。当前收尾在 `source/track33-closeout-20261030`；main 未整合，原因是创建 PR/推送 main 会自动执行本轮禁止的工程检查。

本轮仅做源码、接口、文件引用与 Git 交付审阅；没有新运行结果或新构建产物。
