# Z19 语音关键词与 USB 相机 PL 定位交付

源码和现场证据见 [VOICE.md](../../fpga/color_locator/VOICE.md)。本目录保留 2026-10-22
使用的 AArch64 音频运行库及相机可执行程序。当前网格与播报使用[后续交付](../grid_voice_coordinates/README.md)的程序；这些均不是 Windows 程序，不替换系统库。

- `native-payload.tar.gz`：已有板端语音环境使用的独立 Debian ARM64 运行库快照，
  含 ALSA 工具、依赖及其版权文件。保留历史 eSpeak 组件，但当前关键词功能不调用它。
- `native-manifest.json`：原始包版本、上游下载位置、包 SHA256、适用架构信息。
  来源为 Debian archive；各组件许可在 tar 中 `usr/share/doc/*/copyright`，
  对应源码可按 manifest 的 Source/Package 与 Version 在同一归档的 pool 中取得。
- `color_camera`：2026-10-22 在 Z19 编译并实际运行的相机/PL 传输程序，保留为阶段验证产物；不支持后续 balanced 模式的 `JPEG_DIVISOR` 参数。
- `manifest.json`：本目录文件及联动源码的 SHA256。旧 r3 包的 native 程序是历史版本，
  本程序新增 request_id 与采集时间元数据，PL 固件保持相同。

## 离线准备（仅与已验证板端环境相同的 Linux/AArch64/Python3.7）

1. 从[已有语音离线包](../voice_usb/README.md)取得模型和 wheel，使用仓库现用 `host/app/voice/audio.py`，
   在板端新的专用目录解压为 `host/`、`wheels/` 等结构。按该包说明在板端创建
   `.venv` 并离线安装依赖；不要复制 Windows 虚拟环境。
2. 在此专用目录新建 `native/`，用 `tar -xzf /路径/native-payload.tar.gz -C native`
   解压独立库。解压前核对 SHA256；不要解压到 `/`、不要运行 apt/dpkg 覆盖板端系统。
3. 按[当前网格交付](../grid_voice_coordinates/README.md)新建程序目录，将仓库
   `fpga/color_locator/host/` 中的 `color_control.py`、`voice_color.py`、`voice_color.sh`、
   `preview.py`、`coordinate_speech.py`、`grid_overlay.js`、`color_camera.c` 全部复制进去。
   使用 `deliverables/grid_voice_coordinates/color_camera`，或在板端编译当前 C 源码。
   不把本目录的阶段二进制与当前 `preview.py` 混用。启用坐标播报还需按该交付准备
   已验证 Piper 运行库与中文模型；本目录的 ALSA 运行库包不包含这些 TTS 资源。
4. FPGA 使用[已验证颜色固件](../pl_color_z19/README.md)，先按其守卫流程核对板端
   Linux/PS 初始化与镜像身份。加载固件不是本语音脚本的自动行为。
5. 按 [GRID.md](../../fpga/color_locator/GRID.md)启动，将 `--voice-assets`
   指向步骤1、2组成的语音资料目录；先建立指定的 `/dev/shm/` 预览目录。
   运行程序可能需要 `chmod +x color_camera`。相机和麦克风都须独占使用。

本轮沿用已安装语音环境完成真人验证；以上是根据已验证目录依赖整理的复现步骤，
尚未在另一块全新系统上完成重新安装验收。内核 USB 音频/UVC、Python venv、libjpeg、
glibc 等系统条件仍须满足，不包含整个 SD 系统镜像。

已确认红色真人联动，回读也观察到绿色请求和 PL 位置。语音在 PS ARM，颜色掩码、
像素统计和全局包围框在 PL。同色多物体会合并；没有机械臂运动控制。
不包含账号凭据、工具授权文件、私人画面或录音；保留第三方运行库的版权和许可文件。
