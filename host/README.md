# 小亚智分 · Z19 PS 软件索引

PS负责采集/解码、完整PIO收发、CPU垃圾模型、坐标解释、Vosk和有界任务接口。先读[四功能工程](../fpga/system_pspl/README.md)的环境表，再按下列入口阅读。VM机械臂软件位于 [robot/dofbot](../robot/dofbot/README.md)，两个运行环境分别准备。

| 目录 | 用途 |
|---|---|
| [app/perception](app/perception/README.md) | 真实模型后端、前后处理/业务类别、CoordinateMapper、候选策略、HTTP服务与配置样例 |
| [模型契约](app/perception/contract.example.json) | 来源权重/类序/框架与AArch64目标Python/libc/库分别登记；未知项为null，不是可运行配置 |
| [libpspl](libpspl/README.md) | C有序UIO MMIO、FIFO交替收发、ctypes绑定及AArch64 CMake入口；没有隐式设备探测或DMA后端 |
| [app/voice/usb_pcm_pl.py](app/voice/usb_pcm_pl.py) | 独立USB PCM→PL滤波→PS Vosk→受限事件；生产端清理边界与VM代际配合 |
| [app/voice/pl_frontend.py](app/voice/pl_frontend.py) | 完整FIR系数配置、PCM块收发、状态/超时传播；普通块不复位滤波状态 |
| [app/voice/audio.py](app/voice/audio.py) | 当前颜色指令链使用的 ALSA 采音、PCM/WAV 转换；导入时不打开声卡 |
| [requirements-voice.txt](requirements-voice.txt) | 板端 Vosk 0.3.45 依赖；离线模型和 ARM64 wheel 见 [准备说明](../docs/voice/USB_MICROPHONE.md) |
| [camera_linux](camera_linux/README.md) | 独立 Z19 MIPI 相机 0 驱动、采集和预览 |
| [scripts](scripts/) | Z19 SD/Linux 基础检查、恢复和相机加载工具；按 [FPGA 文档](../docs/fpga/README.md)手动使用 |
| [tests/test_audio.py](tests/test_audio.py) | 不访问设备的采音异常处理与 PCM 转换检查 |

分类与ASR在PS，不表述为PL神经网络。`semantic_bbox` 默认不执行颜色连通域分析，颜色对应为显式选项；原始显示旁路标为 `pl_processed=false`。权重/环境等缺项明确报错，预览不作为任务许可。

原颜色语音入口仍为 [fpga/color_locator](../fpga/color_locator/GRID.md)。`ah_camera0`、`/opt/amazinghand` 保留设备/部署兼容作用；相机驱动与脚本属于独立profile或基础支持，不另列灵巧手控制路线。本轮只整理源码入口，未执行服务、导入验证、模型、采音或设备访问。
