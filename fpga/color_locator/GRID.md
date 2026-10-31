# 亚克力板实体网格坐标与流畅预览

用户确认板面左上P1=(0,0)，+X向右、+Y向下；有效区40x30cm，粗格10cm、细格2cm。
交点检测和多点透视映射由浏览器执行；颜色HSV、目标框、匹配计数继续由真实FPGA PL计算。
不是在图像上生成等距网格。只标局部线条可见的交点，遮挡/模糊/反光可造成漏检。

`grid_overlay.js`须与`preview.py`放在同一目录。四角标记仅用于确定粗格行列相位，
实际采用至少10个实体粗格交点，保留5个不参与拟合的检查点；内部误差过大即回退像素显示。
用户确认的尺寸不等于外部计量精度，当前未校正镜头畸变；坐标不授予机械臂运动许可。
页面默认cm，可切mm、2cm数字密度和保存标定报告。

## 流畅坐标模式（当前默认）

先按[上板守卫](BOARD.md)确认已验证颜色镜像和唯一PL使用者，再运行源码对应的新版程序。
这组命令不提供自动刷机：

```sh
gcc -O2 -std=c11 -Wall -Wextra -Werror color_camera.c -ljpeg -pthread -o color_camera
mkdir -p /dev/shm/visiongrasp-grid-fast-20261023
python3 -u preview.py --directory /dev/shm/visiongrasp-grid-fast-20261023 \
  --port 18774 --camera /自己的版本目录/color_camera --profile balanced \
  --voice-assets /自己的已有语音资料目录
```

完整语音文件与依赖见[语音说明](VOICE.md)，不加`--listen`保持麦克风暂停。
只运行图像可省略`--voice-assets`。通过自己的SSH认证将电脑8774转发到板端18774。
不要同时另起摄像头或MMIO客户端。

| 模式 | 原图 / 实际PL处理尺寸 | 实测表现 |
|---|---|---|
|balanced|1280x720 / 640x360|平均7.26fps发布，页面实际约7.2fps；采集至发布平均187ms|
|hd|1280x720 / 1280x720|优化前平均1.92fps；采集至发布平均568ms|
|smooth|640x480 / 640x480|保留旧模式，实际相机视野可能裁切，网格标定可能不可用|

balanced保留完整720p原图用于标定，libjpeg以半尺寸解码供PL处理；小颜色目标的细节
分辨率低于hd。它不是720p全分辨率PL提速，未达到30fps。显示原图和处理图来自同一USB帧。
状态`width/height/bbox/mask_count`使用PL像素；`capture_width/capture_height`是原图尺寸。
网页已分别标明原图、PL尺寸和实际显示fps，不把USB请求30fps或板端发布fps当屏幕帧率。

网格脚本与 balanced 模式属于当前颜色链；固件与寄存器说明见 [BOARD.md](BOARD.md)。

## 语音指令后播报坐标

部署时还需同目录的`coordinate_speech.py`及更新后的`voice_color.py`；使用已有
语音资料目录内的`neural-tts/piper/piper`、`zh_CN-huayan-medium.onnx`和配置，以及native aplay。
当前功能只复用已装资源，不会下载模型或向系统安装库。
带`--voice-assets`启动后播报默认开启；加`--listen`才自动开启麦克风，也可用网页开启。

说“拿取红色物品”或“红色”：ASR请求→真实PL颜色框→浏览器同帧有效标定→板端重算中心→
稳定3帧后由微雪USB喇叭播报“红色物品，横坐标……厘米，纵坐标……厘米”。每次请求一次。
播报时排空并忽略麦克风音频，结束后0.9s恢复识别。页面可暂停语音或关闭“定位后播报坐标”。
页面需保持打开；关闭页面或标定失败不会凭旧坐标发起新播报。
中心是PL全局包围框中心，同色多物体仍合并；不是抓取坐标或安全机械臂控制功能。

坐标显示保留一位阿拉伯数字小数；送入Piper的独立`tts_text`先转为中文数字，
例如`20.6`读“二十点六”、`0.6`读“零点六”、`40.0`读“四十点零”。
避免中文前端吞掉小数点，计算值和网页显示不变；该转换只用于0～40cm板面坐标。
