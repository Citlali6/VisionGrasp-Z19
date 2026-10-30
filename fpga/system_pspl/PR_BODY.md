# Add Z19 PS/PL video, perception and PCM source profile

新增独立Z19 PS/PL源码profile：PL执行RGB增益/偏置、HSV掩码、ROI计数/包围框/坐标矩，以及DC、63tap FIR和可配置软门；PS通过有序UIO/PIO完整收发，执行真实CPU YOLO适配、坐标/目标对应、Vosk受限命令和HTTP任务接口。可选VM入口复用原一次任务及固定工位动作，现用部署保持原入口。

新增AXI-Lite解耦握手、FIFO、单一寄存器定义、C/ctypes客户端、Vivado工程Tcl、Linux设备树源片段、AArch64构建入口及比赛材料。模型调用和业务映射源自已有厂商备份；权重、实际模型类序/YAML和框架精确版本仍为受控外部依赖，缺失/不符明确报错。

质量工作仅含文本/接口/数值边界/引用及Git差异审阅。按本轮用户约束，未执行新增代码、模型/系数生成、编译、仿真、综合、实现、上板、设备联调或性能验证；没有新bit/XSA/ELF及性能结论。历史结果仍归原版本。

当前PR会触发 `ci.yml` 的 `fpga_guard` RTL仿真。因此本文件是PR正文草稿，实际仅推送 `source/pspl-four-functions-20261030`；须在允许相应验证且符合分支保护时再创建PR，不能把本分支交付记为main合入。
