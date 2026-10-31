# 开发指南

围绕一次分拣任务选择要修改的层次：PL 处理像素、PCM 和候选规则，PS 完成采集、模型、坐标与任务服务，VM 组织分类播报和机械臂动作。先阅读[系统架构](architecture.md)及[配置与兼容性](CONFIGURATIONS.md)，再进入对应模块。

## 模块与版本

| 开发目标 | 入口 |
|---|---|
| 视频定点计算、ROI 与帧统计 | [perception_v2](../fpga/perception_v2/README.md) |
| 音频 DC、FIR、软门及样本流控 | [audio_frontend](../fpga/audio_frontend/README.md) |
| 候选区域、连续帧与一次许可 | [sort_guard](../fpga/sort_guard/README.md) |
| AXI-Lite、FIFO、UIO 与 C/Python 传输 | [集成工程](../fpga/system_pspl/README.md)、[libpspl](../host/libpspl/README.md) |
| 模型契约、坐标与 PS 任务服务 | [perception](../host/app/perception/README.md) |
| 任务状态、播报、动作接口与只读展示 | [DOFBOT](../robot/dofbot/README.md)、[可选 PS/PL 客户端](../robot/dofbot/pspl.md) |

默认安装器与安装测试使用同一份[冻结 payload](../deliverables/dofbot_demo_20261029/README.md)。开发源码中的可选接口独立演进；修改开发目录不会改变冻结安装源。调整冻结基线时，应作为单独的版本更新核对部署清单与依赖。

## 软件检查

普通软件检查使用 Python 3.10 或更新版本及仓库开发依赖。板端原生包必须与 AArch64 目标环境匹配，不能直接安装到 PC 或复制 VM 的 x86 库。

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -B -m unittest discover -s host/tests -p test_audio.py -v
```

上述检查使用伪设备和固定输入。历史检查结果及其源码版本见[验证记录](VALIDATION.md)；新增用例应记录自己的执行结果。

安装器可生成隔离布局，便于审阅安装文件与用户脚本：

```bash
python robot/dofbot/install.py --staging-root /tmp/dofbot-install-review
```

该模式不操作真实桌面或设备。配套环境的正式安装步骤见[快速开始](QUICKSTART.md)。

## 候选规则回放

```bash
python -m fpga.sort_guard.host.replay tests/sort_guard/fixtures/synthetic_stable.jsonl
```

此 JSONL 使用合成输入，输出标记 `evidence_level=software_model`、`hardware_accessed=false`。回放通过软件寄存器模型观察候选规则；真实外设接入另按[接口说明](../fpga/sort_guard/INTERFACE.md)核对来源、寄存器、帧序和计时单位。

## FPGA 工具与检查

颜色工程使用 Vivado 2020.1，三套仿真覆盖 HSV 数值、视频背压和 AXI-Lite 事务；命令、成功标记与输出目录见[颜色模块](../fpga/color_locator/README.md)。候选门控的 RTL 仿真与 OOC 综合入口位于 `fpga/sort_guard/scripts/`，条件及结果见[模块文档](../fpga/sort_guard/README.md)。

四功能集成源码同样采用 Vivado 2020.1 配置。独立 MIPI 相机工程要求 Vivado 2020.2_AR75986，保留原 IP 与 BSP。输出放在源码目录之外，并为每项记录对应的源码、工具、配置和报告阶段。

## CI 与提交

`source_review.yml` 在 PR 与主线更新时自动核对 Git 文本、必需路径和冻结文件来源。`ci.yml` 保留软件检查和 RTL 仿真，通过 `workflow_dispatch` 手动执行；维护者按变更范围选择运行检查。两类流程分别报告结果。

按[Git 工作流](git_workflow.md)从最新 `main` 创建短期分支，经差异审阅、适用检查和 PR 合并后删除远端功能分支。真实设备、FPGA 镜像及现场应用的更新需有明确的目标配置与操作授权；仓库合并与现场部署分别管理。
