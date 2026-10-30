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

后续检查建议：获得运行授权后，以背压/有效间隙、commit 与 SOF 相邻或同拍、末像素命中、零 count、错误 EOL 和中途复位检查对应不变量；分别记录输入、消费和快照身份。这里只给出场景建议，本轮未新增测试程序或运行这些检查。

来源与证据：旧[颜色流模块](../../fpga/color_locator/README.md)提供既有流控记录；四功能[视频实现](../../fpga/perception_v2/README.md)与[当日源码审阅记录](../../docs/log/2026-10-30.md)补充参数快照、末像素和复位处理。旧记录不覆盖新 profile；本技能尚无独立运行或跨板复用证据。运行类检查遵守使用者当前授权。
