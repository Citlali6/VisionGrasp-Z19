# 芯语智分 · VisionGrasp-Z19

**基于 Zynq 软硬件协同的语音视觉分拣工作站**

一句“开始垃圾分拣”，工作站完成一次完整任务：Z19 采集画面，PL 完成像素级预处理，PS 运行检测与语音识别，Linux 上位机按分类结果驱动机械臂完成固定工位投放，界面同步呈现识别、播报与执行阶段。

**听见指令，看清目标，让分类落到行动。**

![固定工位分拣界面](docs/assets/dashboard.png)

*固定工位分拣界面：实时画面、识别结果、语音事件与动作阶段。*

## 一次任务怎样完成

| 阶段 | 位置 | 动作 |
|---|---|---|
| 唤醒 | 语音模块 → PS | 说“你好小亚”，听到回应后说“开始垃圾分拣” |
| 采集 | PS | USB 相机取流，绑定帧序号与采集时间 |
| 像素级处理 | **PL** | RGB 定点增益/偏置 → HSV 掩码 → ROI 计数/包围框/一阶矩 |
| 语义与候选 | PS + **PL** | CPU 检测模型给出类别与框；门控检查面积、连续帧、抖动，给出单次许可 |
| 执行 | Linux 上位机 | 厂商 SDK 完成固定工位抓取、转运、释放 |
| 回显 | 上位机界面 | 识别结果、播报、动作阶段，回到等待 |

一次唤醒对应一次任务，忙碌期间的命令不排队触发下一轮；识别超时或播报失败时，本轮不进入抓取。

## FPGA 在系统里做什么

| 层 | 模块 | 实现 |
|---|---|---|
| 视频预处理 | [`perception_v2`](fpga/perception_v2/README.md) | RGB Q8.8 增益/偏置与饱和、HSV/掩码、ROI 计数/包围框/64 位一阶矩、FIFO 背压、整帧参数快照 |
| 语音前端 | [`audio_frontend`](fpga/audio_frontend/README.md) | DC（Q24.15）、63 抽头 Q1.15 FIR、可选软噪声门、参数提交与样本握手 |
| 候选门控 | [`sort_guard`](fpga/sort_guard/README.md) | ROI/面积、连续合格帧、固定锚点抖动、超时、单次许可 |
| 集成工程 | [`system_pspl`](fpga/system_pspl/README.md) | PS + 三个 PL 端点、统一 100 MHz 时钟、AXI-Lite FIFO/PIO、Linux UIO 设备树片段 |

检测模型与语音识别在 PS 的 CPU 上运行，PL 负责逐像素、逐样本的定点流水。这是本项目的软硬件划分：PS 处理可变模型、词典与系统接口，PL 处理确定精度、确定次序的数据流。

## 已经跑出来的数字

| 指标 | 结果 | 条件 |
|---|---|---|
| 板端发布率 | **7.26 fps** | 1280×720 输入、640×360 PL 处理，2026-10-23 |
| 采集至发布 | **约 187 ms** | 同上，系统耗时，非 PL 算术延迟 |
| MIPI 1080p 采集 | **25.16 fps** | 独立相机 profile，757 帧 / 30.047 s |
| 颜色链完整实现 | 1,885 LUT / 1,936 FF / 6 DSP，WNS 4.580 ns | Vivado 2020.1，XCZU19EG，2026-10-22 |
| 四功能集成工程 | 7,292 LUT / 8,882 FF / 14 DSP，WNS **+0.632 ns** | 100 MHz 完整实现，2026-10-31 |
| 候选门控 | 866 LUT / 949 FF，661 次断言检查通过 | OOC 综合 + RTL 仿真，2026-10-29 |

四功能集成工程的原始资源、时序、DRC 与 bit/XSA 见[构建记录](deliverables/fpga_build_20261031/README.md)；各项数值的条件与来源统一在[证据矩阵](docs/competition/EVIDENCE_MATRIX.md)维护。

## 三套配置

| 配置 | 组成 | 用途 |
|---|---|---|
| 固定工位分拣 | Linux 上位机（Ubuntu 22.04 / ROS 2）+ USB 相机 + 语音模块 + DOFBOT | 现场演示与单次任务闭环 |
| Z19 感知 | Z19 PS/PL + USB 相机/麦克风 | PL 预处理、颜色/网格坐标、语音关键词 |
| 四功能集成 | Z19 PS/PL + 可选上位机客户端 | 集成工程源码、综合实现与 bit/XSA |

三套配置按同一任务模型组织，接口与寄存器定义见对应工程；环境、镜像与依赖的对应关系见[配置与部署](docs/CONFIGURATIONS.md)。

## 快速开始

- [配置与部署](docs/CONFIGURATIONS.md)：环境、版本、依赖与入口
- [快速开始](docs/QUICKSTART.md)：安装并运行固定工位分拣
- [系统架构](docs/architecture.md)：PS、PL 与上位机的分工和数据流
- [验证记录](docs/VALIDATION.md)：板端、软件、RTL、综合四类结果
- [设计报告](report/design_report.md)：背景、原理、划分、优化、复现
- [Skill 技能包](skill/README.md) · [AI 开发协作记录](report/ai_collaboration.md)

## 仓库结构

| 角色 | 位置 |
|---|---|
| src | `fpga/`、`host/`、`robot/` |
| sim | 各模块 `sim/`、`tests/` |
| build | `fpga/system_pspl/` 的 Tcl 入口；生成物在源码树外 |
| board | `deliverables/`、各模块板端说明 |
| data | `docs/fpga/evidence/`、`docs/log/`、各模块验证目录 |
| skill | `skill/` |
| report | `report/` |

## 来源与许可

项目自有代码采用 [Apache-2.0](LICENSE)。工程复用 Yahboom DOFBOT 配套 SDK、模型与动作能力、laperex HSV 算术、ALINX 板卡基础及 AMD IP，并保留历史工程来源。第三方代码、模型、媒体与工具遵循各自许可，取得方式与归属见 [THIRD_PARTY.md](THIRD_PARTY.md)。
