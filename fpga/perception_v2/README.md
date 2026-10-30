# 视频预处理与区域一阶矩

`vg_video_axi_top` 是新 `system_pspl` profile 的视频外设入口。PS 发送
RGB888，PL 执行通道校正、HSV 掩码和区域统计，PS 完整回读 RGB 与掩码后
计算质心并交给模型与坐标模块。模型图像不包含高亮、框线或背景压暗。

该模块随四功能集成源码提供，目标环境与发布状态见[配置与部署](../../docs/CONFIGURATIONS.md)。

| 源码 | 输入、计算和输出 |
|---|---|
| `rtl/vg_rgb_affine_axis.sv` | 逐通道 Q8.8 增益、整数偏置、舍入和饱和；一个弹性输出寄存器 |
| `rtl/vg_hsv_mask_axis.sv` | 复用固定版本 HSV 算术，以完整 HSV 范围生成掩码；信用预留和结果 FIFO |
| `rtl/vg_roi_moments_axis.sv` | 透明传递像素，按实际输出消费统计 ROI 内 count、bbox、sum_x、sum_y |
| `rtl/vg_video_axi.sv` | AXI-Lite 寄存器、输入/输出 FIFO、配置提交、完整帧快照 |
| `rtl/vg_video_axi_top.v` | Vivado BD 使用的 Verilog 端口包装与接口属性 |
| `../system_pspl/rtl/vg_axil_regs.sv` | 独立 AW/W 接收和响应保持，读值在 AR 接受时锁存 |
| `../system_pspl/rtl/vg_sync_fifo.sv` | 单时钟 ready/valid FIFO，可同时入队与出队 |

HSV 算术来自未修改的
[`cv_rgb_to_hsv`](../color_locator/vendor/laperex/cv_rgb_to_hsv.sv)，保留其
[MIT 许可](../color_locator/vendor/laperex/LICENSE)和固定来源记录。
信用预留沿用既有 `vg_color_axis` 的方法；旧 profile、寄存器 ABI 和展示行为保留。

## 像素、算术与配置

PIO 输入字低 24 位为 `0xRRGGBB`，bit24=SOF，bit25=EOL，其余位必须为零。
输出保留这些位，并在 bit26 返回颜色掩码，bit31:27 为零。EOL 是行末，
整帧结束由配置尺寸和完整像素数量确定。内部 HSV/统计流使用 bit31 掩码，
AXI 包装在读取输出寄存器时转换到 PIO bit26。

每通道输出为 `clamp(((input*gain+128)>>8)+bias,0,255)`。input 为 uint8，
gain=0..1024，默认 256；bias 为符号扩展的 int32，范围 -255..255，默认零。
乘积使用 19 位无符号数，加舍入常量扩展到 20 位；移位后扩展为有符号
33 位再加 bias。先舍入非负乘积，再加偏置，最后饱和。CONTROL.BYPASS
只旁路通道增益/偏置，HSV 与统计继续工作。

HSV_MIN/MAX 各自按 H[7:0]、S[15:8]、V[23:16] 打包。H 为 0..179；
Hmin>Hmax 表示跨零的色相范围。S/V 为 0..255，要求 min<=max。
宽高均为 1..4096，ROI 四边为图像内的闭区间，ROI 不裁剪输出流。
count 为 32 位，最大 4096²=2²⁴；一阶矩各为 64 位，最坏不超过
2²⁴×4095<2³⁶。count=0 时 bbox 清零，PS 必须返回空质心。

配置分为 staging、pending、active 三份。CONFIG_COMMIT 校验全部 staging，
合格后生成 pending；首个 PIO SOF 写入输入 FIFO 的接受边沿把整个 pending
复制为 active，该帧的增益、偏置、HSV、ROI、尺寸、版本和 bypass 一起生效。
active 保持到快照 ACK，后续提交只改 pending。commit 与 SOF 的配置优先级为：
同周期 SOF 使用边沿前的 pending，新的 commit 用于下一帧。
各计算级在自身接受 SOF 时读取这一冻结配置，首像素使用新参数。

## 寄存器与主机次序

唯一偏移定义是 [`registers.json`](../system_pspl/registers.json)；RTL 使用
对应的 `registers.svh`，主机使用 `host/libpspl` 的 C/Python 定义。
ID 为 `0x56475632`，协议版本为 1，能力位 0..3 表示通道校正、HSV、ROI 一阶矩和 PIO。
全部合法地址为对齐 32 位字；写入要求 WSTRB=0xf。未知地址、非对齐、部分写、
空输出读取和无容量输入写入均返回 SLVERR，无对应数据副作用。

1. 显式打开新 profile 对应的 UIO，核对 ID、版本与 map 尺寸，独占设备。
2. CONTROL=4 清理会话状态，然后写入完整 staging 配置。
3. CONTROL=8|BYPASS 提交，检查 ERROR=0 且 STATUS.CONFIG_VALID=1。
4. CONTROL=1|BYPASS 使能。按 STATUS.INPUT_READY/OUTPUT_VALID 交替写入和回读。
   不假定旧工程的 16 像素批次，也不先写完整帧再读。
5. 完整回读 width×height 个结果，核对 SOF/EOL、累计输入/输出计数差值，等待
   STATUS.SNAPSHOT。FRAME 和 COMPLETE 在首帧均为 1，此后逐帧递增。
6. 读取冻结的 FRAME、COUNT、bbox、SUM_X/Y、VALID 与 CONFIG_VERSION；
   VALID.bit0 表示完整且格式正确，bit1 表示有匹配像素。再次核对 FRAME。
7. 保留 CONTROL 的 enable/bypass，置 bit4 ACK 才允许下一帧开始。

输入和输出计数均从会话 reset 开始累计，按 uint32 回绕，不随 ACK 清零。
CONFIG_VERSION 是 active 的配置编号，冻结至下一帧 SOF。
CLIP_COUNT(0xac) 为会话内发生任意通道饱和的像素数，在 affine 输出真实接受时
每像素至多增加一次，旁路不计数，达到 uint32 最大值后饱和。

首个 SOF 之前的非法 PIO 数据被拒绝。帧内额外 SOF、缺失/多余 EOL 或行长不符
会令该帧无效。接受的输入达到整帧数量后停止进样；实际输出消费达到整帧数量后
才发布快照，快照包含最后一个像素。未完成帧不会发布部分统计。主机超时后应
终止该会话并 reset，不能拼接旧帧继续处理。

ERROR 是 W1C 位集，新错误优先于同周期清除：bit0=配置提交拒绝；
bit1=帧格式错误；bit2=输入写入被拒绝/无容量；bit3=输出空读；
bit4=非法寄存器或 WSTRB/控制操作。非对齐访问由共享 AXI 桥直接以 SLVERR 拒绝。
主机超时是 C 客户端的错误返回，外设没有虚构的 USB/网络端到端计时器。

所有逻辑使用 profile 的同一时钟和同步复位。HSV 核没有 ready/clock-enable，
其标签必须逐周期推进；信用为包含核内数据在内的每个已接受输入预留 FIFO 空间，
只在对应结果实际输出时归还。其余流级按各自 ready/valid 接受数据，背压保持像素
及 SOF/EOL。复位清空有效位、FIFO 和未完成帧，普通帧间 ACK 不复位累计计数。

构建入口和地址计划见 [`system_pspl`](../system_pspl/README.md)，环境准备与配置状态见[配置与部署](../../docs/CONFIGURATIONS.md)。
