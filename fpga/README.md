# 小亚智分 · Z19 PS/PL 工程索引

从[四功能集成工程](system_pspl/README.md)了解职责、数据流、寄存器、地址与构建入口。它连接硬件像素/PCM算子与PS软件，机械臂执行由VM客户端编排。各配置的工具版本、镜像与部署状态见[配置与兼容性](../docs/CONFIGURATIONS.md)。

| 模块 | 当前能力与入口 |
|---|---|
| [system_pspl](system_pspl/README.md) | 四功能源码profile，视频/音频/既有门控共享目标逻辑时钟；AXI-Lite FIFO/PIO、Tcl、Linux设备树源片段及源码清单 |
| [perception_v2](perception_v2/README.md) | RGB定点通道校正、HSV掩码、ROI计数/框/一阶矩、背压和完整帧统计 |
| [audio_frontend](audio_frontend/README.md) | DC、63tap Q1.15 FIR、可选软门、参数提交和完整PCM收发 |
| [color_locator](color_locator/README.md) | USB 相机 RGB→HSV、颜色掩码、像素统计和全局框；板端语音选色、浏览器网格映射与坐标播报见 [GRID.md](color_locator/GRID.md) |
| [sort_guard](sort_guard/README.md) | 独立 AXI 候选目标门控：区域、匹配像素数、连续帧、超时及单次许可；源码与离线验证，尚未上板 |
| [camera_hw](camera_hw/README.md) | Z19 MIPI 相机硬件输入、已验证 bit/XSA；源工程要求 Vivado 2020.2_AR75986 |
| [camera_baremetal](camera_baremetal/README.md) | 保留相机初始化历史验证输入；当前实时视频使用 [Linux 相机](../host/camera_linux/README.md) |
| [scripts/alinx](scripts/alinx/) | ALINX 板卡 PS 配置；颜色构建使用此共享预设 |

PS配置来自 [scripts/alinx](scripts/alinx/)，HSV共享核保留固定来源与MIT许可。颜色固件、MIPI镜像和四功能profile分别管理；原结果与测量条件见[证据矩阵](../docs/competition/EVIDENCE_MATRIX.md)，检查入口见[开发指南](../docs/DEVELOPMENT.md)。
