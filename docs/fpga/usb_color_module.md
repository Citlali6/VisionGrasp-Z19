# USB 相机颜色定位

颜色链路将像素计算放在 Z19 PL，板端 ARM 负责 UVC/JPEG 格式传输和控制，PC 浏览器负责显示与实体网格坐标计算。

```text
USB UVC MJPEG → PS 解码 → RGB888 / AXI-Lite PIO → PL HSV、掩码、计数与全局框
             ← PS 编码和发布 ← PL 结果
浏览器同帧网格映射 → 板面坐标 → PS 中文坐标播报
```

PL 支持红、绿、蓝和关闭配置，在帧起始锁定颜色与阈值。视频流模块保留 SOF/EOL 并处理背压；AXI-Lite 端点提供有限深度流控制、计数和全局包围框。两个 HSV 算术源文件来自 laperex 的 MIT 项目，其版本、校验值和许可证见 [UPSTREAM.json](../../fpga/color_locator/vendor/laperex/UPSTREAM.json)。项目增加流控、接口、传输、展示与验证代码。

## 已验证能力

- 真实 Z19 颜色固件自检通过，USB 相机帧与 PL 结果帧号一致。
- ARM Vosk 根据明确颜色关键词发起请求，只有匹配请求号且采集晚于请求的新帧可形成有效位置。
- balanced 模式保留 1280×720 原图视野，PL 处理 640×360，实测平均发布 7.26 fps，浏览器约 7.2 fps。
- 浏览器依据实体网格建立板面映射；板端对有效中心坐标稳定采样后播报，每请求一次，播报期间隔离麦克风回声。

同色多个目标仍合并为一个全局框。网格、厘米映射和中文识别不在 PL 执行，当前坐标未接入 DOFBOT 动作。降低处理分辨率的吞吐提升不等于全分辨率 720p 加速。

## 复现入口

[源码、仿真与阈值](../../fpga/color_locator/README.md) · [固件及寄存器](../../fpga/color_locator/BOARD.md) · [语音选择](../../fpga/color_locator/VOICE.md) · [网格与播报](../../fpga/color_locator/GRID.md) · [当前交付](../../deliverables/grid_voice_coordinates/README.md)

基线颜色固件和实现报告见 [PL 交付](../../deliverables/pl_color_z19/README.md)。仿真通过范围及现场性能口径见[验证结果](../VALIDATION.md)，不要在身份未知的 PL 镜像上试探颜色寄存器。
