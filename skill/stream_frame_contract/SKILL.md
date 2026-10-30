---
name: stream-frame-contract
description: Define or review ready/valid video pipelines with SOF/EOL, frame-scoped configuration and complete statistics. Use for FPGA pixel-stream integration or frame-identity bugs.
---

# 像素流与帧契约

输入：各级流接口/RTL、像素打包、SOF/EOL 含义、尺寸上限、配置更新方式和主机收发代码。输出：一张逐级消费/推进表、帧快照与错误发布规则，以及具体源码修正或缺项；不要仅输出框图。

1. 列出每级何时接受、推进与发布数据。普通弹性级按 `valid && ready` 更新；自由运行的算术核与标签仍按其真实逐周期语义推进，不能统一冻结。
2. 分清 SOF、行末 EOL 和整帧完成。明确首个 SOF 前的数据、额外 SOF、行长不符、复位和未完成帧如何失效；背压时保持数据、valid 和标签。
3. 把宽高、ROI、阈值、增益/偏置、配置版本作为同一帧快照。写明 commit 与 accepted SOF 同拍的优先级；下游首像素使用所属快照，不能读取下一帧已改写的全局配置。
4. 只在约定的像素消费点累计统计。检查末像素的 next 值进入快照，零 count 返回空坐标，部分帧不冒充完整统计；按尺寸上限推导计数和坐标矩位宽。
5. 让完整回读、统计冻结/ACK 与 camera/session/frame/config 身份对应。模型输入与展示高亮分别标明。

可改参数：像素位宽/打包、尺寸上限、FIFO 深度、ROI、算术延迟、锁存边界和统计消费点。迁移时按目标实现重算容量与位宽；本项目的 4096 上限和 PIO 方案不是通用限制。

失效条件：标签延迟未知、配置快照跨级失配、未消费完整帧、FIFO 容量不足或跨时钟域未处理。遇到这些条件时指出准确模块与缺少的契约，不返回“完整帧有效”。该工作流适用于其他图像流/包统计，不自动解决 DMA 或 CDC。

检查建议：以背压/有效间隙、commit 与 SOF 相邻或同拍、末像素命中、零 count、错误 EOL 和中途复位检查对应不变量；分别记录输入、消费和快照身份。执行范围按当前任务约定，结果附对应源码与配置。

## 经验与证据对应

| 对应步骤 / 经验 | 具体记录 | 支持范围与未覆盖内容 |
|---|---|---|
| 1–2：背压、标签、复位分别按实际推进点检查 | [旧颜色仿真标记](../../deliverables/pl_color_z19/validation/simulation-markers.txt)的 `COLOR_AXIS_PASS`，及[验证记录](../../docs/VALIDATION.md)“视频流”行 | 旧颜色流已覆盖背压、SOF/EOL、复位与保持检查；这是旧 `vg_color_axis` 的 RTL 记录，不证明新 RGB/HSV/ROI 组合已通过 |
| 3：整帧参数保持一致 | 同一标记的 `config_snapshot=PASS`，及[旧颜色流说明](../../fpga/color_locator/README.md)的 accepted SOF 配置语义 | 支持旧颜色配置按帧锁存的经验；新增增益/偏置、pending/active 与跨级首像素的一致性仍需分别核对 |
| 4–5：统计与采集帧身份成对记录 | [2026-10-22 颜色上板记录](../../docs/log/2026-10-22-pl-color.md)中的绿色帧1941，USB/PL序号一致，并保留像素数与全局框 | 支持旧计数/框与实际帧对应的观察；不覆盖新增一阶矩、末像素入快照或冻结 ACK |
| 3–5 的新增机制 | [2026-10-30 源码审阅](../../docs/log/2026-10-30.md)“文本审阅覆盖”，及[四功能视频实现](../../fpga/perception_v2/README.md) | 参数快照、末像素、复位与 ACK 仅有源码/接口推导，没有新仿真、完整实现或板端记录 |

旧记录不覆盖新 profile；本技能尚无独立运行、跨题目或跨板复用证据。运行类检查遵守使用者当前授权。
