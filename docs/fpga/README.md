# Z19 FPGA 感知模块

Z19 模块独立于 DOFBOT 分拣运行，包含 USB 颜色定位、语音颜色选择、实体网格坐标及坐标播报，另保留已验证的 MIPI 相机和板卡启动基础。

| 任务 | 入口 |
|---|---|
| 查看新增候选目标门控工程 | [sort_guard](../../fpga/sort_guard/README.md)，独立离线验证，尚未上板 |
| 了解颜色数据流、RTL 接口和离线仿真 | [颜色模块源码](../../fpga/color_locator/README.md)、[中文概览](usb_color_module.md) |
| 使用指定颜色固件与寄存器接口 | [板端操作](../../fpga/color_locator/BOARD.md) |
| 启动语音颜色选择与网格坐标播报 | [网格与播报](../../fpga/color_locator/GRID.md)、[语音协议](../../fpga/color_locator/VOICE.md) |
| 准备板端语音依赖 | [USB 语音资产](../voice/USB_MICROPHONE.md) |
| 运行独立 MIPI 相机 | [相机快速操作](camera_quickstart.md) |
| 理解相机实现和已验证产物 | [Linux 相机](linux_camera0_bringup.md)、[交付与来源](camera_delivery_20261010.md) |
| 准备 Z19 Linux 启动介质 | [SD 基础](linux_sd_bringup.md) |

颜色固件与 MIPI 相机固件是不同配置；使用各自已核验的地址、驱动和产物。CI 与仓库检查不加载 FPGA、不探测真实 MMIO。现场结果和性能口径见[统一验证记录](../VALIDATION.md)。
