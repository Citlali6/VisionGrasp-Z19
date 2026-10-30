# 可复用工程技能

本目录对应指南 3.3.5.2，提供从本项目源码审阅和返修中提炼的工作流。它们帮助下一支队伍建立接口、状态和证据契约；YOLO、Vosk 与 PL 的运行分工另见[系统架构](../docs/ARCHITECTURE.md)。开发过程的提示词出处、AI 输出和人工纠错见[大模型协作记录](../report/ai_collaboration.md)。

| 技能 | 适用输入与产出 | 具体旧记录支撑的经验 |
|---|---|---|
| [stream-frame-contract](stream_frame_contract/SKILL.md) | 视频流 RTL、尺寸和配置 → 握手/帧/统计契约与需修正的位置 | [旧颜色仿真标记](../deliverables/pl_color_z19/validation/simulation-markers.txt)的 `COLOR_AXIS_PASS`：背压、复位、帧内配置快照；对应步骤1–3 |
| [register-contract](register_contract/SKILL.md) | 寄存器清单、RTL/C/Python、传输说明 → 一致性表、主机事务次序与失败处理 | [旧门控结果](../fpga/sort_guard/validation/result.json)的 `simulation.coverage`：AW/W 先后、B/R 停顿、非法/部分写、ARM 快照；对应步骤1–3 |
| [voice-task-boundary](voice_task_boundary/SKILL.md) | 语音源、任务状态机、事件/缓存链 → 生产端边界与一次任务适配 | [DOFBOT 验证](../docs/VALIDATION.md)“单轮任务”及原语音状态机检查：一次唤醒/任务、忙碌输入隔离；对应步骤1–2，不能外推为 USB PCM/ASR 验证 |
| [readonly-observability](readonly_observability/SKILL.md) | 设备所有者、控制进程、预览/日志/UI → 只读旁路和身份一致的观测契约 | [DOFBOT 验证](../docs/VALIDATION.md)“摄像头及界面”“初次/重复启动”及陈旧画面检查：设备所有权、单实例与旧画面拒绝；对应步骤1、4 |

各技能的“经验与证据对应”表进一步列出原记录条目、它支持的具体判断及未覆盖的新机制。旧记录验证的是对应旧实现；新帧快照、通用 AXI/FIFO、USB 边界与远端 JPEG 身份等修订仍以[当日审阅记录](../docs/log/2026-10-30.md)和源码为依据，不继承旧实现的通过结论。

在任意代码助手中提供目标工程、这份技能文件及任务范围，例如：

```text
按 skill/voice_task_boundary/SKILL.md 审阅我的语音任务入口。
输入：语音采集与事件代码、任务状态机、消息格式、缓存位置。
输出：跨任务旧输入的可能路径、边界确认协议、最小源码修改。
本次只读源码，不运行采集、模型、测试或设备。
```

先补齐技能所需的真实输入，再按其中的流程工作。缺文件、未确认的坐标/计数含义或未知设备映射应作为具体缺项返回，不能用猜测值补成结果。可改参数与失效条件在各技能中单独列出；使用者的当前授权决定能否运行检查、访问设备或发布。

这些是随仓库交付的技能文档，没有安装到全局技能目录。文件夹按本轮清单使用下划线，frontmatter 的 `name` 使用连字符；按上表的实际 `SKILL.md` 路径读取即可。`README.md` 和 `SKILL.md` 保留指南示例及技能入口约定的文件名，不声称因此获得其他历史命名豁免。

当前证据分两层：旧颜色链、DOFBOT 及门控已有记录仍属于[证据矩阵](../docs/competition/EVIDENCE_MATRIX.md)中的对应版本；四功能修订及本目录仅经过源码/接口/文档审阅。没有运行技能初始化器、校验器或独立行为评估，也没有证据证明这些技能已在陌生队伍、其他板卡或其他题目中复用成功。复用效果仍需在以后获得授权并实际使用时记录。

本项目使用 UIO/PIO。这四项技能不提供 PYNQ Overlay 或 DMA 实现，不申报通用 PYNQ Skill 的额外效果。
