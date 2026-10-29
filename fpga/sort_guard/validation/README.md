# 独立 RTL 与 OOC 验证证据

[result.json](result.json)记录 2026-10-29 的实际 Vivado 2020.1 结果、测试输入哈希和边界。完整仿真运行日志、检查点与失败重试日志保存在仓库外；下列可审阅的技术报告随源码保留：

- [资源报告](reports/utilization.rpt)：综合网表 866 LUT、949 FF、0 BRAM、0 DSP、0 latch。
- [综合网表时序报告](reports/timing_synth_only.rpt)：综合后施加 10 ns 时钟约束，WNS 7.112 ns、WHS 0.061 ns；原样保留 67 个输入/40 个输出无 I/O delay 的检查和具体时序路径。
- [综合网表 DRC](reports/drc_synth_only.rpt)：默认检查规则下 0 条违规；不是整板实现 DRC。

发布报告仅删除 Host 标题行、去掉 Command 行中的临时输出路径前缀、清除行末空白并统一为 LF，去掉文件末尾多余空行且保留一个结尾换行；没有删除技术章节或调整数字。原始报告和发布报告分别记录 SHA-256，二者不是同一文件。模块 `.gitattributes` 对记录哈希的源码、脚本、接口和发布报告设置 `-text`，固定字节，避免 Windows 检出换行转换影响校验。

Vivado 另在运行日志提示 `HD.CLK_SRC` 未设置，无法估计 OOC 时钟延迟与偏斜。10 ns 是综合网表报告约束，不是板上实测时钟。本次没有 placement、routing、bitstream、地址分配、FPGA 加载或机械臂联调；报告通过不代表已测 100 MHz、吞吐提升、视觉精度或动作安全性。

成功仿真标记为 `SORT_GUARD_PASS checks=661 axi_writes=418 axi_reads=66 axi_permits=2 core_permits=1 timeout_priority=PASS reset=PASS`。这是 testbench 中的断言/响应检查总数，不是独立用例数或形式验证证明。使用同一源码重复运行应产生同一标记，工具报告时间、主机标题或绝对路径不同可能导致原始报告哈希不同。

两次以中文路径执行 OOC 时 Vivado 内部 `TclStackFree` 崩溃；改用指向同一外部审计目录的临时 ASCII 路径后，同一 RTL 和综合约束完成构建。原失败记录保留，临时映射已撤销；没有借重试改变设计或删减约束。
