---
name: register-contract
description: Reconcile a register-map authority with RTL, C/Python clients and an explicit UIO/PIO transaction protocol. Use for AXI-Lite register integration and partial-transfer failures.
---

# 寄存器与 PIO 事务契约

输入：权威偏移/位字段定义、RTL 端点、C/Python 客户端、地址 profile、设备树和设备打开约定。输出：字段一致性表、配置/收发/快照次序、失败状态与最小修订。没有真实地址来源时先报告缺项，不扫描 MMIO。

1. 为每项列出偏移、宽度/符号、读写权限、复位值、副作用、WSTRB 策略及错误响应；选择一个权威定义，其他语言作为投影或读取方。
2. 检查 AW/W 能独立到达，B/R 响应在停顿时保持，写入/弹出副作用只发生一次。空读、满写、非法/非对齐地址和部分写要有明确行为。
3. 规定 staging→校验 commit→生效边界，以及 disable/reset/bypass/ACK 的组合约束。多字统计必须冻结或前后复核序号，不能拼接跨帧字段。
4. 用“输出可读则排出、输入可写则填入”的推进方式审阅大块 PIO 传输；检查数量、顺序、身份、模计数回绕和截止时间，避免先写满整帧/整块才读。
5. 核对 C 的对齐32位 MMIO、目标架构屏障、UIO 身份/协议/map 尺寸与独占约定。超时或数量错误使会话失效，复位/重配置后再用；缺硬件不返回模拟结果。

可改参数：地址/尺寸、ABI 版本、FIFO 深度、超时、计数宽度和配置切换边界。屏障与映射属性依目标 OS/架构确定，不把普通 Python 内存视图当成完整 MMIO 契约。

失效条件：定义不一致、响应或副作用重复、旧输出残留、地址归属不明、跨字快照不一致。具体列出冲突值与引用文件；不得通过修改另一 profile 的 ABI 隐藏问题。可复用于传感器/加速器寄存器与有限 FIFO 端点；DMA、缓存一致性和新驱动需要另外的实际实现。

后续检查建议：获得授权后覆盖 AW/W 先后与分离、响应停顿、不同 WSTRB、空读/满写、大于 FIFO 的数据块、计数回绕和传输超时；判断副作用次数、完整收发及会话失效规则。投影生成入口见 `fpga/system_pspl/generate_contract.py`。

## 经验与证据对应

| 对应步骤 / 经验 | 具体记录 | 支持范围与未覆盖内容 |
|---|---|---|
| 1–2：独立通道、响应保持及错误访问不能遗漏 | [旧颜色标记](../../deliverables/pl_color_z19/validation/simulation-markers.txt)的 `COLOR_AXI_PASS`；[旧门控结果](../../fpga/sort_guard/validation/result.json)的 `simulation.coverage` 中 AW/W 先后、B/R 停顿、非法地址/只读写入/full WSTRB、复位清理条目 | 支持旧端点对这些事务情形的 RTL 检查经验；两者不是新通用 AXI 桥/FIFO 的运行结果 |
| 3：配置提交与后续读取必须有原子边界 | 同一门控结果的 `configuration validation and ARM snapshot` 条目 | 支持旧候选按 ARM 锁存配置的经验，不证明新视频 SOF、生效 commit 或统计 ACK 实现正确 |
| 4–5：MMIO 宽度、屏障和批次必须匹配实际端点 | [旧颜色板端说明](../../fpga/color_locator/BOARD.md)“诊断寄存器”及低延迟优化记录：native32、访问屏障、与原 FIFO 容量匹配的专用空到空批次，并校验计数/序号 | 旧固件有真实自检/基准记录；经验是先确认 IP、容量和收发契约，不能把旧专用批次照搬到未知 IP 或新动态收排路径 |
| 新单一定义、动态 PIO 与失败会话 | [统一清单](../../fpga/system_pspl/registers.json)、[通用 AXI 桥](../../fpga/system_pspl/rtl/vg_axil_regs.sv)、[C/ctypes 客户端](../../host/libpspl/README.md)、[构建记录](../../deliverables/fpga_build_20261031/README.md) | 新投影一致性、错误/超时路径与 100 MHz 实现结果见对应提交与报告；投影生成入口为 `fpga/system_pspl/generate_contract.py` |

本技能尚无独立运行、跨题目或跨板复用效果记录。旧端点的检查不能代替新端点或新目标平台的验证。
