# 第三方组件与来源

VisionGrasp-Z19 的项目自有代码使用根目录 [Apache-2.0](LICENSE)。此许可不重新许可第三方源文件、工具、固件、模型或媒体；各组件保留原作者声明和适用条款。

## DOFBOT 运行依赖

| 组件 | 使用方式与来源 | 仓库中的处理 |
|---|---|---|
| Yahboom DOFBOT SE SDK、检测与动作模块、ROS 逆解服务 | 配套 Ubuntu 22.04 / ROS 2 Humble 虚拟机中已安装的厂商运行环境 | 不复制发布；按 [外部依赖清单](robot/dofbot/external_dependencies.json)核对路径、版本与关键文件 SHA-256 |
| 垃圾识别模型、中文分类播报音频 | 与上述部署相匹配的现有权重和媒体 | 不随仓库分发，不声明为团队训练或录制；复现者从其合法配套资料准备 |
| ROS 2、OpenCV、PyQt5、pyserial、NumPy、mpg123 等 | 运行环境中的独立软件包 | 沿用各项目许可证和安装版本；安装器不自动升级这些组件 |
| 语音模块串口帧与类别映射 | 已验证模块协议适配 | 仓库保留帧解析和映射，删除未使用的手机 APP 控制入口 |

本项目实现单次任务状态机、输入隔离、播报完成门控、唯一相机旁路、只读实时展示、动作指令阶段观测及启动安装管理。底层检测、逆解与既有执行动作不表述为团队独立开发。相关运行代码的版本基线见 [部署清单](robot/dofbot/deployment_manifest.json)。

## FPGA 与板卡基础

| 来源 | 保留内容 | 许可与记录 |
|---|---|---|
| laperex 的颜色转换实现 | 两个未修改的 RGB→HSV 类型/算术源文件 | [MIT 许可证](fpga/color_locator/vendor/laperex/LICENSE)和 [UPSTREAM.json](fpga/color_locator/vendor/laperex/UPSTREAM.json)固定上游提交与文件哈希 |
| ALINX / Xilinx Zynq UltraScale+ 平台 | Z19 PS 配置、板卡约束、生成 IP 配置及平台代码 | 保留源文件版权与工具/IP 条款；不是根 Apache-2.0 的统一授权对象 |
| 既有 MIPI 相机工程及其中的 Digilent / David Shah MIPI IP | 相机工程配置、传感器接口、色彩处理与经过验证的构建产物 | 保留各源文件头部声明、IP 元数据与 [相机 manifest](fpga/camera_hw/manifest.json)；重建工具版本见[相机说明](fpga/camera_hw/README.md) |
| 历史工程来源 Tom-mr33/AmazingHand-based-on-FPGA | 仍保留的板卡、相机与基础工程来源链 | 原始来源与 Git 历史继续保留；移除废弃手部应用不消除这些代码的来源 |

项目新增的流量控制、颜色选择与统计接口、AXI-Lite 桥接、板端传输、显示及测试在对应源码中维护。第三方 HSV 算术、原始相机工程和厂商 IP 不作为本项目自研成果。上游仓库只用于来源追溯，不是当前项目的提交目标。

## Z19 离线语音与播报

当前颜色语音链使用 Vosk 及 `vosk-model-small-cn-0.22`，在板端 ARM 上识别颜色关键词；采音依赖 ALSA。冻结的 [USB 语音资产包](deliverables/voice_usb/README.md)保存模型来源、依赖 wheel、哈希及 wheel 内的许可，当前仅复用所需音频基础与依赖资产。模型来源记录含官方 URL 与哈希，但冻结包中没有模型许可全文；使用和再分发前需核对模型的适用条款。板端原生运行库与其来源记录见[语音颜色交付](deliverables/voice_pl_color/README.md)。

坐标播报依赖 Piper 与已验证的中文模型。模型原始记录中的 Dataset License 为 `Unknown`，仓库保留来源与校验记录，不附带该权重或本地 Piper 发行包；复现者需自行取得适用许可。具体记录见[坐标播报交付](deliverables/grid_voice_coordinates/README.md)。

发布前新增或替换第三方组件时，应记录实际来源、准确版本、完整许可和文件校验值；无法确认再分发许可的材料保留为外部依赖。
