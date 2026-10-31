# 板端中文语音 → PL 颜色定位

## 当前方案

用户在2026-10-22明确选择先完成 **ARM语音识别 + PL定位**，随后要求允许根据
语音关键词推断目标，不必严格匹配完整句式。本阶段只选择颜色、显示定位结果。

```text
USB TO AUDIO → Z19 PS ALSA / 16kHz mono PCM → Vosk中文小模型
  → PS颜色关键词与否定/歧义过滤 → 带request_id的颜色请求
USB UVC → PS格式转换 → 现有PL HSV/颜色掩码/像素统计/全局框
  → PS读取真实PL结果并传输 → PC显示原图、高亮图和PL像素坐标
```

**ASR和关键词推断位于板端ARM，不是PL语音识别。** 颜色识别、计数和包围框在
现有CLR1硬件中完成，未换bit、未改AXI寄存器，不由电脑计算目标位置。
本页说明语音与颜色联动。2026-10-23 新增实体网格标定、板面中心坐标和 USB 喇叭中文播报，当前启动入口见 [GRID.md](GRID.md)。

## 关键词约定

- “拿取红色物品”“想要那个红色的”“红色” → 选择红色区域。
- 绿色、蓝色同理；也支持“绿的”“蓝的”等明确颜色表达。
- “停止”“停止识别”“停止定位”“停止抓取”“暂停” → 停止定位并清空有效坐标。
- 含否定词、多个不同颜色或无颜色关键词 → 不产生新选择。
- 按颜色词的Vosk词置信度过滤，默认最低0.65；不从partial结果触发任务。
- 根据用户要求，允许一句话中其他词未识别而颜色关键词明确时选择颜色。
  这是有限颜色关键词推断，不是开放式自然语言理解，更不是安全机械臂动作授权。

模型仍使用现有 `vosk-model-small-cn-0.22`。运行时按模型实际词表筛选空格分词的
动态关键词语法，含红绿蓝、否定表达、停止和[unk]分支。没有下载语音大模型。

## 新增文件及接口

- `host/color_control.py`：PS侧关键词解析、跨进程文件锁、原子颜色请求与结果格式化。
- `host/voice_color.py`：独占自己的ALSA采音子进程，Vosk流式识别和RAM状态更新。
- `host/voice_color.sh`：复用既有板端AArch64/Python3.7语音环境及其独立ALSA运行库。
- `host/preview.py`：开启/暂停麦克风，显示识别文字和PL定位位置，管理自己的子进程。
- `host/color_camera.c`：保留16像素PIO快速路径，增加请求标记和采集时间检查。

RAM数据目录（本次沿用 `/dev/shm/visiongrasp-pl-color-20261022`）：

| 文件 | 用途 |
|---|---|
|control.json|最新意图：request_id、颜色、阈值、来源、请求单调时钟时间|
|control.txt|`color min_s min_v request_id requested_monotonic`，C传输读取；旧三字段格式仍可读|
|control.lock|语音和手动请求跨进程互斥，不与PL MMIO所有权锁混用|
|voice.json|最新ASR状态/文本/置信度/音频电平，仅RAM保存|
|status.json|真实PL坐标/帧号与PS传输元数据，包括request_id和captured_monotonic|

`request_id`是PS传输元数据，不是PL完成语音识别的证据。PL帧号与USB帧号仍由
原生客户端核验。最新请求必须等到匹配request_id、颜色、且采集时间晚于请求的
完整新帧，才能显示有效坐标。零匹配、过期、断流、编号不符均不显示旧坐标。
网页预载同帧图像后再更新其坐标，避免新框坐标配旧画面。

语音未知/低置信度不改当前选择；需清除已有选择请明确说“停止”。暂停/异常退出
仅清除该语音进程自己最后发出的请求；若用户之后手动选择了颜色，语音退出不覆盖它。

## 板端启动

保留已有颜色固件的加载守卫与native自检流程，见[上板说明](BOARD.md)。
以下启动命令不提供刷机入口。不能在未知PL镜像上直接运行MMIO程序。

当前部署目录 `/opt/visiongrasp-voice-color-20261022`，依赖已验证语音资料目录
`/opt/visiongrasp-voice-echo-verified-20261022` 中的 `.venv`、`native`、
`host/app/voice/audio.py`和 `host/models/vosk-model-small-cn-0.22`。
不能把Windows虚拟环境复制到板端，也不应向PC安装这些AArch64运行库。

离线依赖组合与原生程序按当前颜色链准备。
必须同时复制本目录 host 下的 color_control.py、voice_color.py、voice_color.sh、
preview.py、coordinate_speech.py、grid_overlay.js 和新版相机程序，不能只替换旧版 preview.py。
新版默认balanced，需要可选JPEG_DIVISOR参数；本页旧交付二进制不支持此参数。
应使用当前颜色链的二进制或重新编译当前 C 源码。
预览 RAM 目录需事先创建；以下为旧smooth画质示例，当前推荐启动命令见GRID.md。

```sh
cd /opt/visiongrasp-voice-color-20261022
gcc -O2 -std=c11 -Wall -Wextra -Werror color_camera.c -ljpeg -pthread -o color_camera
python3 -u preview.py --directory /dev/shm/visiongrasp-pl-color-20261022 \
  --port 18774 --camera /opt/visiongrasp-voice-color-20261022/color_camera \
  --profile smooth --voice-assets /opt/visiongrasp-voice-echo-verified-20261022 --listen
```

不加 `--listen` 则默认麦克风暂停，可在网页开启。通过已有SSH本地转发8774→18774
查看页面，仍需要自己的 SSH 认证；代码中不保存凭据。

只使用现有模型与本地运行库，不经网络ASR，不保存PCM录音或完整语音日志。
`voice.json`仅保留最新文本用于现场确认。关闭服务器停止其管理的采音和相机进程。
语音进程用独占锁避免多实例，麦克风拔出/音频停滞会显示错误。

## 验收状态

Python 3.7 语法、板端GCC零警告构建、语音环境入口已核对。
已恢复真实相机采集，麦克风设备为 `plughw:CARD=Device,DEV=0`。
初版完整句过滤未能接受用户首次语音：ASR只返回低置信度单字，未伪造成功结果。
随后按用户要求切换颜色关键词语法，加载165条模型词表有效表达。
用户随后确认“已经自动定位红色”。同时回读状态中，红色请求来源为 `voice`，
文本为“红色”，request_id为8312515278；对应真实PL帧20456返回
包围框 `[405,108,508,196]`、4377个匹配像素，相机与PL帧号一致。
这是该帧的现场结果，不是固定坐标或精度标定结论。

后续只读回读也捕获到“拿取 绿色 物品”的语音请求8531050836，PL帧26393
返回 `[225,231,352,359]`、11938个匹配像素，相机/PL帧号一致，约5.89fps。
随后识别文本“不要 拿 红色 物品”被拒绝，没有替换先前绿色请求。
这证明了本次已观察到的关键词联动；停止、蓝色以及噪声环境的真人验收仍待补充。

现场服务继续保持运行，未为更新页面提示而重启。当前源码新增的关键词提示和输入峰值
显示将在下一次正常启动服务后生效，不影响已在运行的关键词识别与PL定位。

旧 `deliverables/pl_color_z19` 的r3交付包是冻结的纯颜色版本，**不包含后续语音联动新增代码**。
