# Z19 USB 摄像头 → 真实 PL 颜色识别 → 电脑显示

已验证的 bit、BIN、XSA、原生程序和报告见
[交付验证目录](../../deliverables/pl_color_z19/validation/)。恢复本轮版本无需先重新综合。

## 本轮已验证

2026-10-22，用户明确授权上板验证。硬件：ALINX Z19 XCZU19EG，Linux
5.4.0-xilinx-v2020.2，USB Camera0bda:9143 `/dev/video0`。实际720p MJPEG帧经过
PS解码为RGB，送PL执行HSV/阈值/高亮/像素统计，再由PS编码JPEG传到电脑。
电脑没有颜色算法。`/dev/video1`是该摄像头的元数据节点。

- 真实 PL 自检：16像素红绿蓝白图，每种颜色匹配4像素；关闭检测匹配0，
  输出RGB、高亮、计数验证通过，标记 `COLOR_BOARD_SELFTEST_PASS`。
- 第一张真实1280×720相机图：红色13001匹配像素，全局框[645,229,792,379]，
  PIO往返约833.170ms。网页视觉核查红色方块明亮，其余区域压暗。
- 连续处理约0.83–0.86秒/帧，约1帧/秒，不是30fps。包含大量MMIO往返，
  不是PL的纯流水线延迟。采集请求10fps，但显示丢弃旧帧以减少积压。
- 修复 `VIDIOC_QBUF` 清空用户缓冲描述符序号的问题：在归还USB缓冲前保存序号，
  将其写入PL并回读；网页显示相同的相机序号与PL序号。
- 不启动语音、不访问机械臂。该独立PL镜像不包含旧MJC1或旧MIPI设计。

## 可复现构建

源码目录为本目录，生成物必须放仓库外的**新目录**。构建依赖已存在的
`../scripts/alinx/ps_config.tcl`，不修改它。此共享配置与已验证构建使用的 PS 配置逐字节一致。

```powershell
$script = (Resolve-Path 'fpga/color_locator/scripts/build_board.tcl').Path
$scratch = New-Item -ItemType Directory '../color-board-scratch-new'
Push-Location $scratch.FullName
try {
  & "$env:VIVADO_2020_1_BIN/vivado.bat" -mode batch -source $script `
    -tclargs "$($scratch.FullName)/output-new"
} finally { Pop-Location }
```

先将 `VIVADO_2020_1_BIN` 设置为 Vivado 2020.1 的 `bin` 目录。
从仓库外工作目录执行；成功要求 `COLOR_BOARD_BUILD_PASS`，同时检查timing/DRC。
导出 `color.bit`、`color.xsa` 和报告；不用2020.2相机BD、不调用旧工程生成物。
Verilog顶层壳用于兼容2020.1不支持SystemVerilog模块作为BD引用顶层的限制。

在另一新目录复制color.bit，创建以下ASCII `color.bif`，在该目录运行Bootgen：

```text
all:
{
 [destination_device=pl] color.bit
}
```

```powershell
& "$env:VITIS_2020_1_BIN/bootgen.bat" -image color.bif -arch zynqmp -process_bitstream bin
Get-FileHash color.bit.bin -Algorithm SHA256
```

将 `VITIS_2020_1_BIN` 设置为 Vitis 2020.1 的 `bin` 目录；生成物留在新建外部目录。
实际raw BIN SHA256：
`901f2f1fc6a812c25ed92e64f05bc5f15fc87c0ea417b9c3d26ce18454ebeb29`。
源代码重建后的哈希可能不同，必须重新计算并核查，不能套用此哈希。

## 板端部署与运行

本次目录 `/opt/visiongrasp-pl-color-20261022`；RAM预览目录
`/dev/shm/visiongrasp-pl-color-20261022`。后者重启丢失；只保留最近4组图像。
上传自己的已审核BIN到 `/lib/firmware/visiongrasp-color-20261022-<hash前缀>.bin`，
不要覆盖原固件、BOOT.BIN或SD/eMMC启动文件。

加载前须确保没有旧PL用户/驱动：loader核对板型软件基线、哈希、PL0≈200MHz、
PL1≈100MHz、旧相机驱动和独占锁。**manager operating只证明配置状态，不证明IP身份。**
确认正确镜像加载后才运行native32自检；不能先读未知PL地址。复位后必须重新确认配置，
不要运行历史Python mmap探测脚本。

```sh
cd /opt/visiongrasp-pl-color-20261022
gcc -O2 -std=c11 -Wall -Wextra -Werror color_camera.c -ljpeg -pthread -o color_camera
sh load_color.sh /lib/firmware/visiongrasp-color-20261022-<hash前缀>.bin <完整SHA256>
./color_camera --selftest
./color_camera /dev/video0 1280 720 /dev/shm/visiongrasp-pl-color-20261022 100000
```

最后参数是帧数上限；Ctrl+C正常退出，设备卡死不能假定用户态超时能够中断AXI事务。
本次端点对所有AXI请求有限响应，错误访问设sticky错误位；仍不能保障未知固件安全。
板端已具有GCC/libjpeg，无需向PC安装板端依赖。

另一板端会话运行：

```sh
python3 -u preview.py --directory /dev/shm/visiongrasp-pl-color-20261022 --port 18774
```

HTTP只监听板子127.0.0.1。电脑通过SSH本地转发8774→板端127.0.0.1:18774，
打开 `http://127.0.0.1:8774/`。本轮由受主机密钥校验的SSH连接转发，无防火墙修改。
不在代码中保存SSH密码。会话/隧道停止、断网、重启后页面不再实时刷新，
需重新建立连接；不是开机自启服务。

## 诊断寄存器

只适用本镜像，AXI4-Lite native32，base **0xA0000000**，range **4KiB**。
数据读写必须32位对齐、完整WSTRB；不要64位/逐字节MMIO。

| 偏移 | 用途 |
|---|---|
|0x000/0x004|ID0x31524c43（CLR1）/版本0x00010001|
|0x008|写1清流水线、统计、错误；保留配置|
|0x00c|color[1:0]：0关闭/1红/2绿/3蓝；minS[15:8]、minV[23:16]|
|0x010/0x014|宽1..1280/高1..720；空闲时配置|
|0x018|bit0可写像素/bit1可读结果/bit2错误/bit3帧完成|
|0x01c/0x028|输入接受计数/输出读取计数|
|0x020|写0x00RRGGBB像素|
|0x024|读处理像素并弹出，bit31匹配、低24位PL高亮后的RGB|
|0x02c|匹配像素数|
|0x030/0x034/0x038/0x03c|xmin/xmax/ymin/ymax，含端点，零像素时读0|
|0x040|相机帧序号，空闲时写，读回验证对应帧|

C程序当前每批最多送16像素再取16结果，匹配本固件的16项FIFO。配置按帧生效。
框是**所有选中颜色像素的全局外包框**，多个同色物体会合并。PL 镜像不包含连通域、
抓取点或运动控制。[网格映射](GRID.md)在浏览器端使用该框中心计算板面坐标；
不等于机械臂标定。HSV默认阈值仍需按照明校准。

## 卡顿优化后的运行方式与实测

上述首版约1fps数据保留作基线。随后按用户要求优化，**没有重刷或修改PL固件**：

1. 原生32位与每次访问的屏障均保留；使用16像素空到空批次，减少状态查询。
   这是针对本版AXI桥/6级流水线/16项FIFO的专用路径，不可套用未知IP。
   小于8像素的末尾批次仍逐项检查输出有效位。每帧校验错误位、计数和序号。
2. USB线程持续取帧并及时归还V4L2缓冲，处理线程只取最新一张压缩图，
   不再让PL处理占用相机取帧循环。请求30fps仅为采集设置，不冒充实际处理帧率。
3. 网页80ms轮询，原图和PL图预载完成后成对显示，不堆积请求；支持画质切换。

真实PL `--benchmark`：720p与640×480各四种颜色，共4915200像素，逐像素、
匹配计数全部通过；`--selftest`亦通过。独立基准720p往返456.7–462.6ms，
640×480为152.0–152.6ms。实际并发采集时略慢，以下表为准。

| 模式 | 发布速率 | 采集时间戳到板端发布 | MMIO/PL往返 |
|---|---|---|---|
|流畅640×480，24张独立采样|均值5.76fps|均值221.43ms，203.80–238.17ms|均值157.42ms|
|高清1280×720，10张独立采样|均值1.93fps|均值561.76ms，547.73–573.44ms|均值471.32ms|

上述延迟不包含后续网络和屏幕显示，帧率是板端发布速率。没有测量显示器实际
光学端到端延迟，也没有宣称30fps。网页帧序号和PL回读在这些样本中全部一致。

使用网页管理采集时，**不要同时手工运行上面的color_camera摄像头命令**：

```sh
python3 -u preview.py --directory /dev/shm/visiongrasp-pl-color-20261022 --port 18774 \
  --camera /opt/visiongrasp-pl-color-20261022/color_camera --profile smooth
```

`--profile hd`为720p。网页可切两种分辨率；只终止由该服务器创建的相机子进程，
等待其退出后再启动新进程；五秒未退出则拒绝启动第二个实例，不强杀未知进程。
进程有互斥锁。关闭服务器会停止它管理的相机进程，不改变FPGA配置。
首次部署前仍须加载检查过的镜像并通过native自检；`--camera`不提供刷机捷径。

本次运行保留原始程序用于回退：新程序名 `color_camera-fast-r3`，
新服务器名 `preview-r3.py`，均位于上述/opt目录，不覆盖旧可执行文件。
外部性能样本 `latency-smooth-r3.json`、`latency-hd-r3.json`保存在本机验证目录。
