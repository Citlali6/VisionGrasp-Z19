# 文档导航

小亚智分的产品、技术、证据与复现材料从下列入口阅读；参赛规则及缺项以要求映射为准。

| 目的 | 阅读入口 |
|---|---|
| 了解作品并按评审顺序阅读 | [评委导航](competition/judges_guide.md)、[产品说明](competition/product_brief.md) |
| 核对五项评分与七项报告要求 | [要求映射](competition/requirements_map.md)、[参赛资料入口](competition/README.md) |
| 阅读七项设计报告与独立导出数值附录 | [设计报告](../report/design_report.md) |
| 查看四功能源码、PS/PL 接口及环境条件 | [聚合工程](../fpga/system_pspl/README.md)、[FPGA 导航](../fpga/README.md)、[PS 软件](../host/README.md) |
| 查看真实开发协作案例与可复用流程 | [AI 协作记录](../report/ai_collaboration.md)、[Skill 技能包](../skill/README.md) |
| 核对指标、版本和原始证据 | [证据矩阵](competition/EVIDENCE_MATRIX.md)、[验证结果](VALIDATION.md) |
| 核对交付范围、依赖与历史处置 | [提交清单](../deliverables/submission/manifest.json)、[发布清单](competition/release_inventory.md) |
| 准备英文海报 | [英文内容与素材映射](../report/poster_copy_en.md)；尚未套用官方 PPT 模板 |
| 复现冻结 VM 演示或选择新协同入口 | [快速开始](QUICKSTART.md)、[新 PS/PL 可选 VM 入口](../robot/dofbot/PSPL.md) |
| 连接机械臂、相机和语音设备 | [硬件连接](HARDWARE.md) |
| 理解不同配置的任务与数据流 | [系统架构](ARCHITECTURE.md) |
| 开发、测试和提交变更 | [开发指南](DEVELOPMENT.md)、[贡献指南](../CONTRIBUTING.md)、[Git 工作流](GIT_WORKFLOW.md) |
| 查看旧 Z19 颜色/语音/坐标独立成果 | [原感知链导航](fpga/README.md) |
| 查看独立候选目标门控与 MIPI 相机记录 | [门控工程](../fpga/sort_guard/README.md)、[相机快速操作](fpga/camera_quickstart.md) |
| 核对第三方来源和许可 | [第三方说明](../THIRD_PARTY.md) |

四功能源码 profile、冻结 DOFBOT 演示、旧颜色链、独立 MIPI 与门控记录分别保留版本和证据范围。当前安装器默认读取仓库内的[原演示冻结 payload](../deliverables/dofbot_demo_20261029/README.md)，也可显式指定独立冻结检出；新可选入口和源码审阅不继承旧工程的运行结论。退出的实验路线通过发布清单和 Git 历史追溯。
