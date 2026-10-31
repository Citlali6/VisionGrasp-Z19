# Z19 FPGA 感知模块

Z19 的 PL 感知链包含 USB 颜色定位、语音颜色选择、实体网格坐标与坐标播报；候选门控、视频预处理与音频前端在四功能集成工程中。MIPI 相机硬件工程与采集记录保留在独立目录。

| 任务 | 入口 |
|---|---|
| 四功能集成工程 | [system_pspl](../../fpga/system_pspl/README.md) |
| 视频预处理与音频前端 | [perception_v2](../../fpga/perception_v2/README.md)、[audio_frontend](../../fpga/audio_frontend/README.md) |
| 候选目标门控 | [sort_guard](../../fpga/sort_guard/README.md) |
| 颜色数据流、RTL 接口与仿真 | [颜色模块](../../fpga/color_locator/README.md) |
| 板端寄存器与固件 | [BOARD](../../fpga/color_locator/BOARD.md) |
| 网格坐标与语音播报 | [GRID](../../fpga/color_locator/GRID.md)、[VOICE](../../fpga/color_locator/VOICE.md) |
| MIPI 相机硬件与采集记录 | [camera_hw](../../fpga/camera_hw/README.md)、[证据](evidence/2026-10-10/README.md) |

颜色固件与 MIPI 相机固件是不同配置，使用各自核验的地址、驱动和产物。现场结果与性能口径见[验证记录](../VALIDATION.md)。
