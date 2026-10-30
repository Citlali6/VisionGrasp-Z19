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

后续检查建议：获得授权后覆盖 AW/W 先后与分离、响应停顿、不同 WSTRB、空读/满写、大于 FIFO 的数据块、计数回绕和传输超时；判断副作用次数、完整收发及会话失效规则。这里没有生成或运行测试，也没有执行投影生成器。

来源与证据：[统一寄存器定义](../../fpga/system_pspl/registers.json)、[通用 AXI 桥](../../fpga/system_pspl/rtl/vg_axil_regs.sv)、[C/ctypes 客户端](../../host/libpspl/README.md)及[源码审阅记录](../../docs/log/2026-10-30.md)。`generate_contract.py` 是已有未来入口，本轮没有运行；新定义一致性只记为文本审阅，不能据此声称总线功能或时序通过。
