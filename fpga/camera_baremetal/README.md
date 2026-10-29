# Z19 standalone 相机历史验证归档

本目录保留此前通过 JTAG 验证的 CAM0 程序及构建输入，用于追溯相机初始化。
**当前高清实时视频使用 [Linux 实现](../../host/camera_linux/README.md)**，不运行此 ELF。
standalone 程序需要配套 A53 BSP、FSBL/PS 初始化和相机硬件平台，不能作为 Linux 可执行文件。

## 文件与功能

| 文件/函数 | 功能 |
|---|---|
| `src/main.c: transfer/reg_write/reg_read` | PS I2C 传感器寄存器访问及错误检查 |
| `src/main.c: dma_prepare` | 为既有 VDMA 设置 1920×1080、三帧缓冲及采集参数 |
| `src/main.c: main` | 初始化 CAM0、手动镜头位置，更新 DDR 帧与供 JTAG 读取的全局状态 |
| `src/sensor_table.h` | 历史成功使用的 89 项 IMX214 寄存器表 |
| `camera.ld` | 对应 A53 standalone 链接地址与段布局 |
| `build.ps1` | 使用已有 BSP/GCC，在全新目录编译 ELF/map 并生成 hash 清单 |
| `build/validated-live-v2/` | 与这里源码对应的历史 live_v2 ELF、hash 和 JTAG 测量结果 |
| `build/archive-check/` | 更早的独立 ELF/map/符号归档，不能与 live_v2 混用 |

原输入逐字节保留，不为补充说明改写已经成功的源文件；功能说明放在本文件。
目录内 `.gitattributes` 仅对这些历史输入保留换行和空白，避免 clone 后 hash 变化。

## 验证边界

live_v2 曾取得真实 1080p 采集图像，JTAG 小预览约 1.3 fps（80 帧、约 57.22 秒）。
这不是 Linux 1080p MJPEG 的约 25 fps 指标。第二路曾超时，未宣称双路成功。
历史 ELF SHA256 为 `7d41ee6e72f7f7f1c7b8a501ad2b9c24c4e28670a50aba6732e2addcb7e9f232`。
`archive-check` 的 ELF 为另一份二进制；其符号地址只用于对应 ELF。
重编译会受工具/BSP/调试源路径影响，不承诺重建 ELF 与历史 ELF 字节相同。

## 编译

已有 BSP 必须来自配套 [camera.xsa](../camera_hw/validated/camera.xsa) 的 A53 standalone domain；
准备 Vitis 平台/BSP 后，将 `CAMERA_BSP` 设置为匹配 BSP 的绝对路径，
`VITIS_AARCH64_GCC` 设置为 Vitis 2020.1 的 `aarch64-none-elf-gcc.exe` 路径：

```powershell
& ./fpga/camera_baremetal/build.ps1 `
  -BspDirectory "$env:CAMERA_BSP" `
  -GccPath "$env:VITIS_AARCH64_GCC" `
  -OutputDirectory '../camera-baremetal-new-build'
```

输出目录必须不存在；脚本不会覆盖 BSP、源文件或历史归档，也不连接板卡。
本次重新编译仅验证源码/BSP 可链接，不替代上板验收。
