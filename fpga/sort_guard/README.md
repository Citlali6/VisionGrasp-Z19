# FPGA 分拣候选门控

本模块把固定工位的候选复核规则实现为可综合 RTL：工位 ROI、匹配像素数、连续新帧、固定锚点位置抖动、超时、busy 撤销和每轮一次的候选许可。它让现有颜色 PL 的统计结果参与后续分拣编排；交付包括**独立外设源码、RTL 仿真、单模块综合与主机适配**，集成工程为其分配独立地址。

## 处理位置与输入边界

```text
已有颜色 PL：HSV / 选定颜色像素数 / 全局包围框
    → PS：核验相机与 PL 帧号、颜色请求、会话、时间戳
    → PS 写新外设的 AXI-Lite 帧影子寄存器 + FRAME_COMMIT
    → 本模块 PL：ROI / 数量 / 固定锚点抖动 / 连续帧 / 周期超时
    → ready → 显式 CONSUME → 一次 permit_pulse + 许可计数与 job
```

新外设没有板端物理地址，也没有加入现有颜色 bit。图中的 PS 提交与新外设连接是待集成方案，不能把离线仿真称为板端系统实测。PS 提供的 valid/fresh 是信任边界；硬件自行检查序号和输入统计约束，但不能验证摄像头数据来源、PS 时间戳或 HTTP 会话的真实性。

当前颜色检测只覆盖所选红、绿或蓝区域，全局 bbox 会合并同色目标。门控适用于可可靠分割的单个候选区域，需要现场设定 ROI、像素数量范围和容差。它不识别垃圾类别、不分离实例、不处理语音、不决定抓取姿态，也不证明物体已抓住或人员已离开。`permit_pulse` 是候选许可事件，不是执行器信号或经认证的安全控制功能。

## 任务边界

- ARM 在空闲、非 busy 且配置有效时锁存参数与基线帧；活动轮次内再次 ARM 被拒绝。
- 新帧必须比基线/上一帧严格更新。重复和倒序帧不增加连续计数，也不延长有效期；支持 32 位自然回绕。
- bbox 必须完整位于闭区间 ROI，匹配像素数必须在配置范围内。后续四个边界相对本段首帧的变化均不超过容差，避免缓慢漂移无限累计。
- 坏的新帧立即撤销 ready；超时、取消和 busy 撤销本轮。超时边界优先于新帧与 CONSUME。
- ready 需要显式 CONSUME 才转为一次事件。成功消费立即结束本轮，重复消费失败；下一轮必须重新 ARM。主机核对 `PERMIT_COUNT` 恰增一次及 `PERMIT_JOB`，不能把 ready 当作已消费许可。

精确周期、错误响应、寄存器和优先级以 [INTERFACE.md](INTERFACE.md) 为准。主机侧另对会话、输入配对与原始统计做校验，见 [host/README.md](host/README.md)。主机软件模型只是逻辑参考，不能替代 RTL 仿真。

## 文件与离线复现

| 路径 | 用途 |
|---|---|
| [rtl/vg_sort_guard_core.sv](rtl/vg_sort_guard_core.sv) | 配置快照、逐帧门控、超时和单次许可核心 |
| [rtl/vg_sort_guard_axi.sv](rtl/vg_sort_guard_axi.sv) | 32 位 AXI4-Lite 接口，独立 AW/W、响应背压、严格地址与 WSTRB 校验 |
| [sim/tb_sort_guard.sv](sim/tb_sort_guard.sv) | AXI 事务与独立 core 精确周期两层测试 |
| [scripts/sim.ps1](scripts/sim.ps1) | Vivado 2020.1 仿真入口，只写全新外部目录 |
| [scripts/synth_ooc.tcl](scripts/synth_ooc.tcl) | `xczu19eg-ffvc1760-2-i` 独立 OOC 综合，不布局布线、不生成 bit、不访问硬件 |
| [host](host/README.md) | 可注入寄存器 transport 的主机客户端与明确标注的离线软件回放 |
| [validation](validation/README.md) | 实际工具结果、可审阅资源/时序/DRC 报告、输入与原始/发布报告哈希；工具运行日志不随仓库分发 |

从仓库根目录运行仿真；`VIVADO_2020_1_BIN` 指向现有 Vivado 2020.1 的 bin：

```powershell
& ./fpga/sort_guard/scripts/sim.ps1 `
  -VivadoBin "$env:VIVADO_2020_1_BIN" `
  -OutputDirectory '../sort-guard-sim-new'
```

也可用 Icarus Verilog，不连接设备：

```bash
iverilog -g2012 -s tb_sort_guard -o /tmp/sort-guard.vvp \
  fpga/sort_guard/rtl/vg_sort_guard_core.sv \
  fpga/sort_guard/rtl/vg_sort_guard_axi.sv \
  fpga/sort_guard/sim/tb_sort_guard.sv
vvp /tmp/sort-guard.vvp
```

成功需出现 `SORT_GUARD_PASS`，失败使用 `$fatal`，另有总超时。Vivado 已通过 661 次断言/响应检查，包含 418 笔写和 66 笔读事务；这不是 661 个独立测试用例，也不构成形式验证。覆盖 AW/W 解耦、B/R 背压、非法地址/部分写、配置快照、错误帧、固定锚点漂移、序号跳跃/回绕、超时竞争、busy/cancel、重复消费、总线复位及外部 busy 跨复位保持。

OOC 综合在仓库外工作目录执行，传入 Tcl 脚本绝对路径和新的报告目录：

```powershell
$script = (Resolve-Path 'fpga/sort_guard/scripts/synth_ooc.tcl').Path
$scratch = New-Item -ItemType Directory '../sort-guard-ooc-new'
Push-Location $scratch.FullName
try {
  & "$env:VIVADO_2020_1_BIN/vivado.bat" -mode batch -source $script `
    -tclargs "$($scratch.FullName)/reports-new"
} finally { Pop-Location }
```

本机 Vivado 2020.1 综合遇到中文源路径时内部崩溃；使用同一源文件的 ASCII 路径可避开。Windows 复现时建议从 ASCII 路径提供这三个输入文件（保留 rtl/scripts 目录关系）并核对哈希。不要覆盖已有日志。10 ns 时钟约束在综合后用于综合网表时序报告；完整实现与时序结果见[四功能构建记录](../../deliverables/fpga_build_20261031/README.md)。

本次实际 OOC 报告为 **866 LUT、949 FF、0 BRAM、0 DSP**，无 latch，综合网表 DRC 为 0 条违规。10 ns 报告约束下 WNS 为 7.112 ns、WHS 为 0.061 ns；有 67 个输入和 40 个输出未设置 I/O delay，工具另提示 `HD.CLK_SRC` 未设置，无法估计时钟延迟/偏斜。因此这些数字只描述本次综合网表，不能当作整板时序收敛或已测工作频率。

接入前仍需独立 BD/地址分配、实际时钟与复位确认、PS 寄存器传输、可信采集会话管理和真实异常试验。本模块不会自动加载固件、更新虚拟机或调用机械臂动作。

源码采用根目录 Apache-2.0。AXI 持有寄存器的组织参考仓库现有 `vg_color_axi`；新模块没有复制或重新声明第三方 HSV 算术为自研。
