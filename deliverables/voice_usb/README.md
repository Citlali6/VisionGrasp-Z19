# Z19 离线语音依赖快照

适用设备：ALINX Z19 的 AArch64 Linux、Python 3.7，麦克风为微雪 **USB TO AUDIO**。

## 下载与内容

- [完整离线包 voice_usb_package_20261018_v2.zip](voice_usb_package_20261018_v2.zip)：约 48.5 MiB，在 GitHub 文件页点击下载原始文件。
- [SHA256 校验文件](voice_usb_package_20261018_v2.zip.sha256)。
- [完整安装和使用说明](../../docs/voice/USB_MICROPHONE.md)。

压缩包冻结于 2026-10-18，包含中文 Vosk 模型、15 个离线依赖 wheel、依赖 hash 锁文件、模型来源记录、逐文件 manifest，以及当时的采音源码。当前颜色指令和网格播报使用其中的模型、wheel 与 `audio.py`，配套系统库见[音频运行库](../voice_pl_color/README.md)。

快照保持原 SHA256，以便核验已部署环境。包内历史通用命令 CLI 不作为当前入口；不要运行其中的 `python -m app.voice` 或 `voice_usb.sh`。当前可维护代码为 [audio.py](../../host/app/voice/audio.py) 和 [颜色语音链](../../fpga/color_locator/VOICE.md)。[打包工具](../../tools/package_voice_usb.py)只收录现用采音组件与外部依赖，不再收录历史 CLI。各 wheel 保留其许可文件；模型 README 与 `model_provenance.json` 保留原文和来源，集中说明见[第三方依赖](../../THIRD_PARTY.md)。

## 当前使用方式与验证边界

按[依赖准备说明](../../docs/voice/USB_MICROPHONE.md)创建专用目录和板端虚拟环境；当前程序由 `fpga/color_locator/host/preview.py --voice-assets ...` 或 `voice_color.sh` 启动。不能将 ARM64 wheel 装进 DOFBOT 的 Ubuntu 虚拟机环境。

2026-10-22 至 23 的现场版本已验证真人颜色指令、真实 PL 定位与坐标播报，见[当前网格交付](../grid_voice_coordinates/README.md)。这些结果来自已有板端环境，不代表在全新 SD 系统上完成过一键安装。语音识别在 Z19 ARM 上运行；本包不含 FPGA 加载器、机械臂控制器或完整系统镜像。
