# PS Linux PIO 客户端

`src/pspl.c`实现新profile的生产UIO后端，`include/pspl.h`定义C ABI，`python/pspl.py`提供ctypes包装。仅显式 `Device.open()` 加载库和打开配置的 `/dev/uioN`；构造和模块导入不接触硬件。对guard保留原ID/版本核对，不改旧ABI。

open核对sysfs map0大小、显式ID和协议，独占文件锁避免协作进程同时使用；不会枚举或探测地址。MMIO为对齐volatile uint32，AArch64读取前后使用 `dmb osh`，写入前使用 `dmb osh`、写入后使用 `dsb osh` 等待Device存储完成，要求UIO内核映射为非缓存Device内存。写接口随后读取外设错误/guard BUS_FAULT，失败返回EIO；不声称UIO直接向用户态暴露AXI BRESP。普通Python内存不是替代后端。pthread锁保护每次传输；配置调用方还须持有 `Device.lock` 形成完整配置事务。

`pspl_video_process`/`pspl_audio_process`循环先排可读输出，再填可写输入，支持小FIFO与任意合法块长。每次有固定单调时钟截止期限，核对输入/输出计数差；视频另核对每个SOF/EOL、完整帧统计序号、配置版本和有效位，再ACK冻结快照。音频前后须无遗留busy，核对产出样本数；PCM明确为16kHz单声道有符号16位小端。音频状态跨普通块连续。

错误返回负errno；`EPIPE`表示会话不可继续，`ETIMEDOUT`为本机传输截止，`EPROTO`为计数/标记/快照不符，模型无目标与这些错误无关。失败后库标记该流不可复用；上层须reset并重新配置，不能静默返回原始数据。`close`前调用方停止全部工作线程。运行时若内核报告总线故障/映射失效，进程需重建，不能依赖库从任意AXI挂起恢复。

构建定义为 `CMakeLists.txt`，AArch64 toolchain可指定实际 `Z19_SYSROOT`；不会复制VM的x86库。Python源包需要保留仓库 `fpga/system_pspl/registers.json`（寄存器权威定义）。完整profile条件及未来构建命令见[工程入口](../../fpga/system_pspl/README.md)。本轮只文本审阅，未运行CMake/编译器或加载共享库。
