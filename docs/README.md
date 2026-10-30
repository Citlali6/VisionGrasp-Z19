# 芯语智分 · 项目文档

按使用目标选择入口：先了解工作站怎样完成一次任务，再选择对应的配置、模块和开发资料。

| 使用目标 | 阅读入口 |
|---|---|
| 了解项目背景、应用场景与用户流程 | [项目概览](overview.md)、[项目首页](../README.md) |
| 选择配置、核对版本与依赖 | [配置与兼容性](CONFIGURATIONS.md) |
| 安装并使用固定工位分拣应用 | [快速开始](QUICKSTART.md)、[硬件连接](HARDWARE.md)、[VM 应用](../robot/dofbot/README.md) |
| 理解 PS、PL 与 VM 的任务和数据流 | [系统架构](ARCHITECTURE.md)、[设计报告](../report/design_report.md) |
| 开发 Z19 视频、音频与候选规则 | [PS/PL 集成工程](../fpga/system_pspl/README.md)、[FPGA 模块](../fpga/README.md)、[PS 软件](../host/README.md) |
| 配置 PS 服务与可选 VM 客户端 | [PS 服务](../host/app/perception/README.md)、[VM 接口](../robot/dofbot/PSPL.md) |
| 使用独立 Z19 颜色、语音与网格工程 | [感知链文档](fpga/README.md)、[颜色模块](../fpga/color_locator/README.md)、[网格与坐标](../fpga/color_locator/GRID.md) |
| 查看指定版本的验证结果 | [验证记录](VALIDATION.md)、[指标与来源](competition/EVIDENCE_MATRIX.md) |
| 开展二次开发并提交修改 | [开发指南](DEVELOPMENT.md)、[贡献指南](../CONTRIBUTING.md)、[Git 工作流](GIT_WORKFLOW.md) |
| 复用接口与任务设计经验 | [工程技能](../skill/README.md)、[AI 开发协作记录](../report/ai_collaboration.md) |
| 核对第三方来源与许可 | [第三方说明](../THIRD_PARTY.md) |

## 提交附件与维护记录

[提交规范附件](competition/README.md)保留赛事规则、材料映射与英文海报内容；[提交清单](../deliverables/submission/manifest.json)记录源码、配置、依赖和材料路径。分支归档与恢复资料见[维护记录](maintenance/main-only-20261030.md)，此前的源码发布过程见[历史发布记录](maintenance/release-20261030.md)。
