# 配置、版本与部署

芯语智分提供固定工位分拣应用、独立 Z19 感知模块和 PS/PL 集成源码。先选择要使用的配置，再准备相应环境；各配置的镜像、地址和验证记录分别对应。

## 选择配置

| 配置 | 版本与状态 | 环境与入口 |
|---|---|---|
| 固定工位分拣（Linux 上位机 + DOFBOT） | 有现场任务与界面记录；安装源固定为 `8a2a6fd544cb6b79e868b8a710dc34b6027c6c8d` 的 15 文件 payload | Ubuntu 22.04、ROS 2 Humble、Python 3.10、SDK、模型和音频；[快速开始](QUICKSTART.md) |
| 独立 Z19 USB 颜色 / 语音 / 网格 | 保留原板端结果和各自发布清单 | Vivado / Vitis 2020.1、对应 Linux 镜像与地址；[颜色模块](../fpga/color_locator/README.md)、[网格](../fpga/color_locator/GRID.md) |
| 独立 MIPI / 裸机相机 | 保留原 bit / XSA 与采集记录 | 硬件源工程使用 Vivado 2020.2_AR75986；历史裸机 ELF 使用 Vitis 2020.1 GCC 与匹配 BSP；[MIPI](../fpga/camera_hw/README.md)、[裸机](../fpga/camera_baremetal/README.md) |
| 独立候选门控 | 有软件、RTL 仿真和 OOC 综合记录 | [sort_guard](../fpga/sort_guard/README.md)；这些结果对应独立模块 |
| Z19 PS/PL 四功能集成工程 | 源码与接口已发布；2026-10-31 完成 Vivado 综合、实现与 bitstream 生成，100 MHz 时序收敛 | Vivado 2020.1、AArch64 Linux / UIO / libpspl、模型契约与 ALSA / Vosk；[工程入口](../fpga/system_pspl/README.md)、[构建记录](../deliverables/fpga_build_20261031/README.md) |

集成工程在 100 MHz 下完成实现，WNS +0.632 ns、WHS +0.010 ns；16 kHz 和 63 tap 分别是采样格式和滤波器长度。帧率、资源与时序数值按配置查阅[验证记录](VALIDATION.md)和[证据矩阵](competition/EVIDENCE_MATRIX.md)。

## 固定工位应用

安装器默认使用 [deliverables/dofbot_demo_20261029/payload](../deliverables/dofbot_demo_20261029/README.md)。该目录保留原始 15 文件及其来源，其中 12 个应用文件按原部署清单校验。开发目录的新 PS/PL 客户端与展示扩展使用独立入口。安装器缺少 payload 或哈希不符时终止；`--source` 可明确选择一份完整的冻结检出。

准备配套虚拟机、普通桌面用户与厂商依赖后，按[快速开始](QUICKSTART.md)安装。外部文件路径、版本与哈希见[外部依赖清单](../robot/dofbot/external_dependencies.json)，应用基线见[部署清单](../robot/dofbot/deployment_manifest.json)。仓库分发应用源码和安装入口；模型、SDK、音频和完整虚拟机按各自来源取得。

运行使用 USB 相机、串口语音模块、USB 声卡和 DOFBOT。保持原相机位置、固定拾取位置与动作参数。唤醒口令为“你好小亚”，回应后说“开始垃圾分拣”；每轮重新唤醒。语音模块提供命令编号，分类播报采用配套音频资源。界面显示任务及已下发动作阶段，物理夹持和投放效果由现场观察确认。

## PS/PL 集成源码的部署条件

该配置由 PS 采集媒体、执行 CPU YOLO / Vosk 并提供任务服务，PL 处理 RGB、HSV、ROI 统计、PCM 滤波和候选规则，VM 客户端组织播报与固定工位动作。完整连接和接口见[系统架构](architecture.md)、[PS 模块](../host/app/perception/README.md)与[VM 接入](../robot/dofbot/pspl.md)。

| 准备项 | 需要对应的内容 |
|---|---|
| 硬件工程与 Linux | 本 profile 的新镜像、设备树、明确 UIO 节点和 map 大小；视频 `0xA1000000`、音频 `0xA1010000`、门控 `0xA1020000`，各 4 KiB |
| 原生库 | 与目标 Linux sysroot、AArch64 ABI 匹配的 libpspl、Python 及依赖；VM x86 库保留为来源环境记录 |
| 语义模型 | 合法权重、真实类别顺序 / YAML、实际框架文件哈希、源与目标版本、预处理和 NMS 参数；按[模型契约](../host/app/perception/contract.example.json)登记，示例中的 `null` / `REQUIRED` 需以真实资料填写 |
| 相机与坐标 | 明确 device、camera_id、图像尺寸、transform_id 和像素空间；工作平面坐标需匹配 calibration_id 与矩阵，固定拾取动作仍使用原工位 |
| 候选规则 | 双端选择相同 `candidate_policy`；默认 `semantic_bbox` 使用同帧语义框面积，`color_association` 使用显式颜色关联与 PL 掩码像素数；缺 guard 配置时仅报告结果 |
| 语音 | 默认 `serial_id` 沿用 VM 串口命令；选 `usb_pcm_pl` 时配置独立 USB PCM、ALSA、PL 音频外设、Vosk 模型与中文词表覆盖 |
| 服务与 VM | 匹配[PS 示例](../host/app/perception/config.example.json)和[VM 示例](../robot/dofbot/pspl_config.example.json)的策略、语音源、服务地址与私有 token；新入口使用独立输出目录及共用机械臂互斥锁 |

权重 / 类序 / YAML、匹配框架与完整源 / 目标环境契约，以及新镜像 / UIO、标定和词典覆盖是当前部署准备项。该配置的完整实现、板级输出与同输入参考比对仍需单独完成。构建步骤见[工程入口](../fpga/system_pspl/README.md)，这里的状态不借用其他配置的验证结论。

## 发布与兼容性

`main` 是唯一长期远端分支。开发使用短期分支和 PR，合并后删除远端 head；阶段源码和历史路线通过 tags、Release 与提交历史保存。本次源码与中英文材料以 [`xinyu-submission-materials-20261030`](https://github.com/Citlali6/VisionGrasp-Z19/tree/xinyu-submission-materials-20261030) 标签固定，实际提交 SHA 按该标签解析。该标签记录材料版本。

历史源码发布 [`track33-source-20261030`](https://github.com/Citlali6/VisionGrasp-Z19/releases/tag/track33-source-20261030) 的预发布身份和指向保持不变；VM 安装源仍是原冻结 payload。本次只新增材料标签，不创建 Release，后续开发文档以当前 `main` 为准。

`ah_camera0`、`/dev/ah_camera0`、`/opt/amazinghand`、`/var/lib/amazinghand` 及原安装目录是已有接口或兼容路径。HSV / BSP、原位流、原报告与许可证按依赖保留。第三方来源见 [THIRD_PARTY](../THIRD_PARTY.md)。
