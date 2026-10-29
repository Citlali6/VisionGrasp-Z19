# Z19 网格坐标、流畅预览与语音坐标播报

2026-10-23现场版本。适用已验证的ALINX Z19、AArch64 Linux、Python3.7、USB UVC摄像头
和微雪USB TO AUDIO。不是Windows可执行程序或完整SD系统镜像。

## 内容与源码

- `color_camera`：从正在运行的板端版本取得的AArch64原生程序，包含可选JPEG_DIVISOR参数。
- `manifest.json`：本程序、配套源码和说明文件的大小/SHA256；文本按Git中的LF字节校验。
- `tts-assets-manifest.json`：已有中文Piper资源的固定来源、版本、大小及SHA256，仅为出处记录。
- [全部配套源码](../../fpga/color_locator/host/)：`color_camera.c`、`color_control.py`、
  `coordinate_speech.py`、`grid_overlay.js`、`preview.py`、`voice_color.py`、`voice_color.sh`。
- [启动与功能说明](../../fpga/color_locator/GRID.md)、
  [网格与性能记录](../../docs/log/2026-10-23-grid-preview.md)、
  [真实语音与小数播报记录](../../docs/log/2026-10-23-coordinate-speech.md)。

本交付复用[原颜色固件](../pl_color_z19/README.md)，未修改PL寄存器或位流。
ASR/TTS在Z19 ARM运行；颜色HSV/计数/全局框在真实PL；实体网格与多点透视映射在浏览器。

## 在现有已验证板端环境中运行

1. 按[上板守卫](../../fpga/color_locator/BOARD.md)确认颜色镜像、PS初始化和独占PL使用者。
   `operating`不能替代镜像身份核对；本说明不自动刷机或打开未知MMIO。
2. 新建自己的部署目录，将上述七个配套源码文件与本目录`color_camera`一起复制进去；
   不要覆盖正在运行的目录。将本程序设为可执行；也可在板端用下面命令重建：

   ```sh
   gcc -O2 -std=c11 -Wall -Wextra -Werror color_camera.c -ljpeg -pthread -o color_camera
   ```

3. 复用现有语音资料目录，以下以现场已验证路径为例。所需目录结构为：

   ```text
   voice-assets/
     .venv/bin/python                     # ARM64 Python3.7 / Vosk0.3.45
     host/app/voice/audio.py              # 既有USB采音实现
     host/models/vosk-model-small-cn-0.22/
     native/                             # 独立ALSA工具和库
     neural-tts/piper/piper
     neural-tts/piper/espeak-ng-data/
     neural-tts/piper/lib*.so*            # 同一Piper发行包的库
     neural-tts/zh_CN-huayan-medium.onnx
     neural-tts/zh_CN-huayan-medium.onnx.json
   ```

   ASR模型/wheel来源见[原语音离线包](../voice_usb/README.md)，native ALSA见
   [补充运行库](../voice_pl_color/README.md)。中文Piper资源不在这两个旧包内；
   本目录只保存资源出处清单，未上传权重或Piper发行包。
   原Huayan模型卡的Dataset License为Unknown，本轮仅复用已有本地验证资源，
   不能宣称仓库已包含可自由再分发的中文语音权重或已验证全新系统一键安装。
   不要把Windows虚拟环境或ARM64库装到PC，不要替换板端系统库。

4. 正常停止之前预览后，在新的部署目录启动唯一实例：

   ```sh
   mkdir -p /dev/shm/visiongrasp-grid-voice
   python3 -u preview.py --directory /dev/shm/visiongrasp-grid-voice \
     --port 18774 --camera "$(pwd)/color_camera" --profile balanced \
     --voice-assets /opt/visiongrasp-voice-echo-verified-20261022 --listen
   ```

   不加`--listen`保持麦克风暂停，网页仍可手动开启。使用自己的SSH认证把电脑8774
   转发到板端127.0.0.1:18774，在浏览器打开http://127.0.0.1:8774/。
   页面需保持打开以计算当前标定；识别颜色目标后，稳定三个独立帧才播报一次。
   没有目标、标定失效、超出板面或合成期间目标明显移动时不播报旧坐标。

## 已观察结果与边界

- 720p原图保持完整视野；balanced送PL处理的尺寸为640x360，约7.26fps板端发布、
  页面约7.2fps；原1280x720全分辨率PL约1.92fps。神经语音合成时帧率可能暂降。
- 用户确认板面40x30cm、左上P1=(0,0)、大格10cm、小格2cm，X向右、Y向下。
  只显示可见实体交点；保留五个拟合外检查点。内部残差不等于外部绝对测量精度。
- 真人语音曾触发红色和绿色PL定位；红色目标移动后播报坐标同步变化。
  小数播报先转中文，20.6→“二十点六”，页面继续显示数字。
- 播放时暂不识别麦克风输入，结束后恢复，避免播报颜色词反触发。
- 中心为PL全局包围框中心，同色多物体会合并；未校正镜头畸变，未驱动机械臂。

录音、相机现场画面、账号凭据、工具授权文件和运行RAM目录均不在交付中。旧交付快照保持原样，
其中旧相机二进制不能与本版preview.py混用。
