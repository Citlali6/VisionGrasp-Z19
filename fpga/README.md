# Z19 FPGA 感知模块

| 模块 | 当前能力与入口 |
|---|---|
| [color_locator](color_locator/README.md) | USB 相机 RGB→HSV、颜色掩码、像素统计和全局框；板端语音选色、浏览器网格映射与坐标播报见 [GRID.md](color_locator/GRID.md) |
| [sort_guard](sort_guard/README.md) | 独立 AXI 候选目标门控：区域、匹配像素数、连续帧、超时及单次许可；源码与离线验证，尚未上板 |
| [camera_hw](camera_hw/README.md) | Z19 MIPI 相机硬件输入、已验证 bit/XSA；源工程要求 Vivado 2020.2_AR75986 |
| [camera_baremetal](camera_baremetal/README.md) | 保留相机初始化历史验证输入；当前实时视频使用 [Linux 相机](../host/camera_linux/README.md) |
| [scripts/alinx](scripts/alinx/) | ALINX 板卡 PS 配置；颜色构建使用此共享预设 |

颜色模块使用 Vivado 2020.1；三组离线仿真入口是 `color_locator/scripts/sim.ps1`。
生成物放仓库外的新目录，仿真不连接硬件。

颜色固件与 MIPI 相机固件是独立的 PL 配置，不能同时加载。本 FPGA 链未连接 DOFBOT 动作控制；已验证范围与步骤见 [FPGA 指南](../docs/fpga/README.md)。
