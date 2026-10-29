# 候选门控主机适配与离线回放

本目录处于**源码与离线验证阶段**。它把现有颜色 PL 的帧统计整理成候选门控寄存器事务，提供可注入 transport 的 Python 客户端与软件模型。没有板端 MMIO 地址、串口控制、网络连接、FPGA 加载或机械臂动作接口；没有修改当前虚拟机。寄存器定义见 [INTERFACE.md](../INTERFACE.md)。

`ready` 表示当前候选满足所配置的帧统计约束；成功 `CONSUME` 表示寄存器记录了一次许可事件。这些结果仅可用于未来抓取前的复核设计，不等于垃圾类别识别、机械臂可达性、安全规划或真实抓取成功。

## 直接运行离线例子

在仓库根目录使用 Python 3.10 或更新版本，只需要标准库：

```bash
python -m fpga.sort_guard.host.replay tests/sort_guard/fixtures/synthetic_stable.jsonl
python -m pytest -q tests/sort_guard
```

示例文件是人工构造的 **synthetic fixture**：ARM 以序号 10 为基线，提交 11、12、13 三帧，再消费一次。输出每行明确包含 `evidence_level="software_model"`、`hardware_accessed=false`，最后一行的 `permit_count=1` 是软件模型结果。它不是板端记录或机械臂联调证据。异常输入会停止回放并返回退出码 2。

JSONL 中每行的 `op` 可以是 `arm`、`frame`、`consume`、`advance`、`busy`、`cancel` 或 `reset`。前三者携带 `status`、`identity` 和 `producer_now`；ARM 另需 `config` 与非零 `job_id`。`advance` 的 `cycles` 只推进软件逻辑时间。示例 `timeout_cycles=1000` 是模型输入，没有隐含板卡时钟频率，也不表示 1000 毫秒。

## 输入来源和时间边界

解析器依据现有 [preview.py](../../color_locator/host/preview.py) 的 `/status` 与 [target_view](../../color_locator/host/color_control.py) 格式校验：

- `source` 标签、健康相机状态、完整请求和 target；相机帧与 PL 帧序号必须相等。
- 颜色、请求编号、饱和度/亮度阈值与当前 request 必须一致，帧采集时间不能早于请求。
- `width/height`、bbox 边界与类型、像素数必须有效；`mask_count` 不能超过 bbox 覆盖像素数。零目标的 `not_found` 帧会正常提交，让硬件撤销已有 ready。
- `age_s` 与生产端时间戳同时检查；默认最大年龄 2 秒，也限制采集到复核的总年龄。布尔值不能冒充整数，NaN/无穷值不能冒充时间。
- ARM 绑定相机、会话、请求、颜色、图像尺寸与阈值。帧序号按 32 位串行比较严格更新，允许跳帧和自然回绕；倒序、重复、时间回退和会话变化撤销本轮。

**现有 `/status` 没有 `camera_id/session_id`。** 调用方必须从可信的采集进程管理上下文提供 `StreamIdentity(camera_id, session_id)`，例如明确设备身份与本次采集进程代际。换设备、重启采集或生产端时钟重置必须更换会话并重新 ARM。解析器要求 `camera_running=true`；当前没有受管相机状态的接口不能直接作为合格输入。

`producer_now`、`captured_monotonic`、`published_monotonic` 与 `requested_monotonic` 必须来自**同一个生产端单调时钟**。不能用 PC 的 `time.monotonic()` 直接减板卡的单调时间。现阶段不提供网络取数与跨机时钟证明实现。JSON 中的 `source`、`camera_id` 等字符串本身也不能证明数据真实或提供认证；离线例子中的这些字段都是测试输入。

## 客户端接口

`GuardClient(transport)` 构造时不读写任何寄存器。transport 由调用方显式提供 `read32(offset)`、`write32(offset, value)`；后者必须按顺序执行完整 32 位写，并在收到总线响应后返回，对 SLVERR、超时等抛异常。不得给尚未部署此 IP 的设备绑定地址。主机必须独占该接口，不能让多个进程并发 ARM/COMMIT/CONSUME。

1. `initialize()` 只读核验 ID、版本和状态。身份确认之前发生错误不会尝试写 CANCEL，也不能调用 `cancel()` 写未知设备。
2. `arm(status, identity=..., now=..., config=Config(...), job_id=...)` 校验输入，写完整配置，快照最后观察帧作为基线，再核验 ARM 结果。基线帧不会被计入连续帧。超时配置必须显式提供周期数；真实接入时须根据已确认的时钟换算。
3. `feed(...)` 校验新帧后写完整影子寄存器，最后一次 `FRAME_COMMIT` 原子提交，并核验 job/sequence。任何不匹配的输入会撤销本轮，不把上一帧 ready 留给后续消费。
4. `consume(...)` 再次复核**最后一帧的原始统计和当前新鲜度**，读取 ready，再发 CONSUME；只有许可计数恰增一次且许可 job 匹配才返回 `Permit`。若有更新帧，应先 `feed` 再消费。返回的 Permit 不执行任何动作。
5. `set_busy(True)` 撤销本轮；解除 busy 不恢复旧任务。`cancel()` 显式撤销；`recover()` 重新验证设备身份，撤销并清总线故障后初始化。总线故障后的撤销只是尽力执行，不能把通信失败当成已确认的硬件停止。

客户端拒绝本实例重复 job，也检查硬件保留的最近 job。上层管理器仍须保证跨进程重启的 job 分配不复用旧任务。板端复位、时钟或 transport 映射变化后须重新核验身份、会话和基线，不能续用旧许可。

## 软件模型的范围

`SoftwareGuard` 实现寄存器层面的 ROI、像素面积、固定首帧锚点抖动、稳定帧数、超时、busy 和单次许可规则。`advance(cycles)` 显式推进时间；普通寄存器访问不消耗模拟时钟。它**不是 AXI 总线周期模型**，不能证明真实事务耗时、背压、时钟收敛或板端性能。真实可综合 RTL 与总线验证由独立仿真覆盖。

测试覆盖输入缺失/畸形、帧配对、目标一致性、过期、序号回绕、会话更换、复位、部分写失败、未知设备读失败无回写、ARM 基线、CONSUME 确认、零目标撤销、固定锚点漂移、边界超时和模型回放。所有测试都不连接真实硬件。
