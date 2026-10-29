# Z19 板端公共组件

此目录服务于独立 FPGA 感知链。DOFBOT 分拣程序及其 Ubuntu 虚拟机依赖位于 [robot/dofbot](../robot/dofbot/README.md)，二者分别安装。

| 目录 | 用途 |
|---|---|
| [app/voice/audio.py](app/voice/audio.py) | 当前颜色指令链使用的 ALSA 采音、PCM/WAV 转换；导入时不打开声卡 |
| [requirements-voice.txt](requirements-voice.txt) | 板端 Vosk 0.3.45 依赖；离线模型和 ARM64 wheel 见 [准备说明](../docs/voice/USB_MICROPHONE.md) |
| [camera_linux](camera_linux/README.md) | 独立 Z19 MIPI 相机 0 驱动、采集和预览 |
| [scripts](scripts/) | Z19 SD/Linux 基础检查、恢复和相机加载工具；按 [FPGA 文档](../docs/fpga/README.md)手动使用 |
| [tests/test_audio.py](tests/test_audio.py) | 不访问设备的采音异常处理与 PCM 转换检查 |

当前颜色语音入口为 [fpga/color_locator](../fpga/color_locator/GRID.md)。`ah_camera0`、`/opt/amazinghand` 等既有设备名和部署路径保留兼容，不代表另有灵巧手控制入口。
