# Z19 USB 语音依赖

当前 Z19 语音功能由板端 ARM 采音、Vosk 颜色关键词识别和 PL 颜色定位组成。语音不是在 PL 上执行；这套板端环境与 DOFBOT 串口语音模块相互独立。

## 配套资产

已验证环境为 Z19 AArch64 Linux / Python 3.7、USB TO AUDIO 声卡、16 kHz 单声道 PCM。`host/app/voice/audio.py` 提供 ALSA 采集与音频格式处理，`fpga/color_locator/host/voice_color.py` 使用它进行流式识别。

复现所需的固定资产来自 [USB 语音包](../../deliverables/voice_usb/README.md)中的 Vosk wheel、`vosk-model-small-cn-0.22`、模型来源与哈希记录，以及[板端原生依赖](../../deliverables/voice_pl_color/README.md)。旧压缩包是冻结的依赖快照；以当前仓库中的颜色入口运行，包内历史命令行应用不属于当前入口。

不要把 AArch64 wheel 或板端运行库安装到 PC，也不要从 Windows 复制 Python 虚拟环境到板卡。wheel 保留其许可文件；模型包保留来源 URL 与校验值，但没有附带模型许可全文，使用前需核对适用条款。中文坐标 TTS 依赖及其再分发边界见[第三方说明](../../THIRD_PARTY.md)。

## 运行入口

先完成[颜色固件和 MMIO 所有者检查](../../fpga/color_locator/BOARD.md)，按[当前网格与播报部署](../../fpga/color_locator/GRID.md)准备原生相机程序及同目录 Python/JavaScript 文件。预览通过 `--voice-assets` 指向已有板端资产目录，`--listen` 决定启动时是否开启麦克风。

```sh
python3 -u preview.py --directory /dev/shm/visiongrasp-grid-fast-20261023 \
  --port 18774 --camera /opt/your-color-release/color_camera --profile balanced \
  --voice-assets /opt/your-verified-voice-assets --listen
```

这里的两个 `/opt/your-...` 路径需替换为按部署说明准备的实际目录。使用模块内 `voice_color.sh` 管理指定语音环境；预览进程会管理自己的采音子进程，不要另起第二个麦克风读取者。

支持明确的红、绿、蓝关键词及停止表达；否定、多颜色歧义、低置信度和部分识别结果不会生成新颜色请求。最新请求必须等待同一请求号的真实新帧，旧画面和旧坐标不能用于新播报。具体阈值及消息字段见[语音接口](../../fpga/color_locator/VOICE.md)。

## 故障检查

在板端已准备的语音原生运行环境中用 `arecord -l` 确认声卡枚举（部分部署的 arecord 不在全局 PATH），核对设备名称、权限和唯一使用者。页面显示最新识别状态及音频电平；麦克风拔出、采音停滞或依赖错误会进入错误状态，不生成虚构识别结果。

程序不保存持续 PCM 录音，最新识别文本保存在 RAM 状态文件中用于展示。坐标播报期间忽略麦克风输入，播报结束后恢复；声音播放成功与现场可听清楚分别验收。该链路只输出颜色和板面坐标，不发送机械臂动作。
