# Z19 PS/PL 四功能集成工程 · 构建记录（2026-10-31）

本目录保存 `z19-pspl-four-functions-v1` 在 Vivado 2020.1 下的完整构建结果：综合、实现、时序收敛、DRC 与 bitstream/XSA。构建对象是 [`fpga/system_pspl`](../../fpga/system_pspl/README.md) 中的视频预处理、语音前端与候选门控三个 PL 端点，以及 ALINX Z19 PS 配置。

## 环境与入口

| 项目 | 值 |
|---|---|
| 器件 | `xczu19eg-ffvc1760-2-i` |
| 工具 | Vivado 2020.1（SW Build 2902540） |
| 顶层 | `system_pspl_wrapper` |
| 时钟 | `ps0/pl_clk1`，100 MHz |
| 源码提交 | `4e51e5b` |
| 构建主机 | Windows，Vivado 2020.1 本机批处理 |

```powershell
vivado -mode batch -source fpga/system_pspl/create_project.tcl -tclargs C:/vg/out
vivado -mode batch -source fpga/system_pspl/build_bitstream.tcl `
  -tclargs C:/vg/out/project/z19_pspl_four_functions.xpr C:/vg/out/system_pspl.xsa
```

## 结果

| 指标 | 结果 |
|---|---|
| WNS | **+0.632 ns** |
| WHS | **+0.010 ns** |
| 失败端点 | 0 / 27,352 |
| 估算 Fmax | ≈ 106.7 MHz |
| CLB LUT | 7,292（1.40%） |
| CLB 寄存器 | 8,882（0.85%） |
| CARRY8 | 326 |
| DSP | 14（0.71%） |
| Block RAM | 0 |
| DRC | 52 Warning，0 Critical，0 Error |
| 片上功耗（vectorless 估算） | 4.167 W（动态 2.955 / 静态 1.212） |
| 实现状态 | `write_bitstream Complete!` |

DRC 的 52 条 Warning 全部属于 DSP 输入/输出流水建议（DPIP-2 24 条、DPOP-3 13 条、DPOP-4 14 条）和 1 条无负载信号（RTSTAT-10），没有 Critical 或 Error。功耗是 Vivado vectorless 估算，不是板上测量。

## 产物

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `system_pspl.xsa`（内含 bit） | 1,175,321 B | `3FFC97DA6FB31666E447C4FD8F540261DD73DD31CCC081C13F367AFF6DE23BD7` |
| `system_pspl_wrapper.bit`（XSA 内条目） | 36,343,237 B | `E2DC755C01C67E6E9506CB71A0B9B010C5F7D6A158FFCAC0FA7660935AE71A29` |

`validation/` 保存布局布线后的原始报告：`utilization_placed.rpt`、`timing_summary_routed.rpt`、`drc_routed.rpt`、`power_routed.rpt`。逐文件哈希见 [manifest.json](manifest.json)。

## 复现要点

- 输出目录必须不存在，脚本会拒绝覆盖；构建产物放在源码树之外。
- Windows 下构建路径使用纯 ASCII。Vivado 2020.1 在含中文的路径上会出现 `mhs`/`hwdef` 读取错误，切到 `C:\vg` 后同一套脚本正常完成。
- 工程不导出 PL 引脚，板端通过 PS 的 AXI 地址空间访问三个 4 KiB 端点：视频 `0xA1000000`、音频 `0xA1010000`、门控 `0xA1020000`。

本目录覆盖工具流程结果；板端运行记录按配置分别归档，见[验证记录](../../docs/VALIDATION.md)。
