# Z19 已验证相机硬件平台

本目录归档实际 Linux 相机 0 使用的硬件文件，以及学长提供的四路相机工程输入。
设备 `xczu19eg-ffvc1760-2-i`，原工程为 **Vivado 2020.2_AR75986**。
归档没有修改原 BD、XDC、RTL、IP 参数或供应方文件。

## 内容与功能

| 路径 | 功能/用途 |
|---|---|
| `validated/camera.xsa` | 已使用的平台导出；用于核对 PS/PL 地址、时钟和 Vitis standalone BSP |
| `validated/design_1_wrapper.bit` | Linux/JTAG 相机实测使用的同一 bit，保留可部署基线 |
| `project/mipi_dp.xpr` | 原始工程配置快照，含历史外部路径；不是可移植启动入口 |
| `project/mipi_dp.srcs/.../design_1.bd` | PS、四路 CSI、Bayer/Gamma、VDMA、AXI、时钟复位和地址配置 |
| `project/mipi_dp.srcs/constrs_1/new/*.xdc` | 原工程使用的五份板级约束，保留全部原值 |
| `project/repo/mipi/` | BD 实际依赖的 CSI、Digilent Bayer/Gamma 三个自定义 IP及全部 fileset 输入 |
| `project/.../*.xci` | 原 IP 配置，包括生成/派生参数；不自动修正六帧/三帧差异 |
| `scripts/create_project.tcl` | 将输入复制到新目录，再创建可编辑工程；不综合、不升级 IP、不下载 |
| `manifest.json` | 输入分组、来源、逐文件 SHA256 与已验证 bit 的边界 |

不归档 Vivado cache/run/DCP、仿真波形、RDMA/ERNIC 未使用 IP或系统镜像。
供应方源文件和版权注释逐字节保留；Digilent 核的 MIT 声明在对应 VHDL 中。
ALINX/Xilinx 等供应方文件保留各自来源与原有声明，不将其标为本项目原创 Apache 代码。

## 已完成与限制

相机 0：真实 1920×1080 图像、Linux 十分钟采集、约 25 fps 1080p 视频、停止/故障恢复通过。
地址为 VDMA `0xA0060000`、Gamma `0xA0040000`、GPIO `0xA0080000`。
bit 的 store 索引实际为 0/1/2，部分导出派生元数据写六帧；保留差异并按实测三帧处理。
不要使用另一份手控制 bit、原 SD 内 PL 或其他平台导出替换此文件。

**本次没有在匹配的 Vivado 2020.2 中重新综合/实现这个源工程。**
源文件依赖和 hash 已核对；不宣称从归档重建出的 bit 与实测 bit 相同。
第二路/四路并发、相机自动冷启动、光学质量/标定、手控制集成仍未验收。

## 打开源工程

使用匹配工具，目标目录必须不存在；脚本把 source 和 generated 分开：

```powershell
vivado -mode batch -source fpga/camera_hw/scripts/create_project.tcl -tclargs ../camera-hw-new-build
```

本机现有 Vivado 2020.1 会被版本检查拒绝，不能通过自动降级或升级 IP 绕过。
生成工程后应在 2020.2 核对 BD、IP 状态、DRC/时序和 bit，再另行上板验收。
既有测试可继续使用 `validated/`，无需重新综合。

## Linux firmware 转换

在新建临时目录复制 `validated/design_1_wrapper.bit` 为 `camera.bit`，创建 BIF：

```text
all:
{
  [destination_device=pl] camera.bit
}
```

运行已有 Bootgen：`bootgen -image camera.bif -arch zynqmp -process_bitstream bin`。
raw bin 预期 SHA256：`e25e9bc7fd4c2008c7a198a91bc4937716b333259d08da7ed777d8ffe9b3384b`。
只在驱动无占用、配套检查通过后使用仓库 loader 加载；操作见
[相机快速操作](../../docs/fpga/camera_quickstart.md)。
