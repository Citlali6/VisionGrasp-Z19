# 事实、证据与性能指标

本页为[芯语智分](../../README.md)的指标唯一入口，产品/技术/复现路线见[项目文档](../README.md)，环境与配置见[配置和部署](../CONFIGURATIONS.md)。下列历史数字与来源保持原归属。

同一数值必须连同条件和证据级别引用。这里的级别描述证据类型，不是比赛评分：**现场**为真实设备记录或现场反馈；**软件**为离线测试/回放；**RTL**为逻辑仿真；**综合**为指定器件及约束的工具报告；**待测**为尚无对应测量。

## 本轮四功能源码（2026-10-30）

| 工程内容 | 可定位源码 | 可报告范围 |
|---|---|---|
| 视频通道校正/HSV/mask | [perception_v2](../../fpga/perception_v2/README.md) | 定点算法、背压、帧参数快照和完整PIO源码 |
| 垃圾识别分类 | [PS模型模块](../../host/app/perception/README.md) | 真实厂商图像调用和业务映射的PS CPU适配；权重、类序和框架资料缺项集中列明 |
| 视觉定位与候选策略 | [coordinates](../../host/app/perception/coordinates.py)、[ROI RTL](../../fpga/perception_v2/rtl/vg_roi_moments_axis.sv)、[guard adapter](../../host/app/perception/guard_adapter.py) | 质心、框恢复、单应算法、默认语义框/可选颜色对应及原GuardClient规则复用；无外部定位精度结论 |
| 音频滤波与噪声抑制 | [audio_frontend](../../fpga/audio_frontend/README.md) | DC/63tap FIR/软门、系数设计和USB PCM→Vosk接口源码；无降噪dB或识别收益结论 |
| 完整工程/软件出口 | [system_pspl](../../fpga/system_pspl/README.md)、[libpspl](../../host/libpspl/README.md) | 新profile、AXI/FIFO、C/ctypes、Tcl、构建入口及PS/VM任务连接 |

上述内容只完成源码与文本/接口审阅，未运行新增代码或工具链。设计100MHz、16kHz采样率、63tap和定点位宽是配置/算法参数；不是Fmax、吞吐或音质测量。下列原有指标保持原版本，不转移给本profile，也不将旧颜色完整设计与旧门控OOC资源当作本次优化前后对比。

## 可直接引用的已有成果

| 内容/指标 | 条件与真实结果 | 证据级别 | 来源 |
|---|---|---|---|
| 语音任务与展示 | 一次唤醒/启动执行一轮，用户确认实物效果及界面正常 | 现场 + 软件 | [DOFBOT 验证](../VALIDATION.md)、[真实截图](../assets/dashboard.png) |
| 抓取调用记录 | 展示启用后记录 3 次抓取回调，另有一次识别超时 | 现场软件记录；不是成功率 | [验证说明](../VALIDATION.md) |
| DOFBOT 软件回归 | 原 65 项 + 协议 4 项 + 安装 9 项，共 78 项通过 | 软件，2026-10-29 定稿基线 | [测试](../../tests/dofbot/)、[部署基线](../../robot/dofbot/deployment_manifest.json) |
| PL 颜色自检 | 16 像素红绿蓝白输入，红/绿/蓝各匹配 4，off 匹配 0 | 现场 | [BOARD](../../fpga/color_locator/BOARD.md) |
| PL 真实帧统计 | 绿色帧 1941：30,097 像素、框 `[422,312,616,599]`；USB/PL 序号相同 | 现场样本，不是识别准确率 | [颜色记录](../log/2026-10-22-pl-color.md) |
| balanced 发布率 | 1280×720 原图，640×360 PL 处理，平均 7.26 fps；浏览器约 7.2 fps | 现场；2026-10-23 指定模式 | [GRID](../../fpga/color_locator/GRID.md)、[性能记录](../log/2026-10-23-grid-preview.md) |
| balanced 采集至发布 | 同上，平均约 187 ms | 现场系统耗时；非 PL 算术延迟 | 同上 |
| 原 hd 发布 | 1280×720 原图及 PL 处理，平均 1.924 fps、采集至发布 567.99 ms | 现场不同模式；分辨率不同 | 同上；不可当作同画质加速比 |
| 网格检查残差 | 样本一 mean/RMS/max 1.03/1.24/2.16 mm；样本二 1.68/1.96/3.05 mm | 现场图内留出交点检查 | [网格记录](../log/2026-10-23-grid-preview.md)；不是外部尺量精度 |
| 坐标播报 | 移动物块后真实请求播报 30.5 cm、19.2 cm；新请求一次播报 | 现场个例 | [播报记录](../log/2026-10-23-coordinate-speech.md) |
| 并发 TTS 影响 | balanced 平时约 7.2 fps，合成时曾短暂降至约 3.6 fps | 现场观察 | 同上 |
| 原颜色链 RTL | HSV 1,024 向量；视频流 2,064 数据拍；AXI 64 像素/四种配置 | RTL，Vivado 2020.1 | [验证](../VALIDATION.md)、[仿真标记](../../deliverables/pl_color_z19/validation/simulation-markers.txt) |
| 原颜色链完整实现 | 1,885 LUT、1,936 FF、0 BRAM、6 DSP；WNS 4.580 ns、WHS 0.017 ns | 原颜色镜像布局布线报告；Vivado 2020.1、XCZU19EG-FFVC1760-2、2026-10-22 | [资源](../../deliverables/pl_color_z19/validation/utilization.rpt)、[时序](../../deliverables/pl_color_z19/validation/timing.rpt) |
| 独立 MIPI 预览 | 1920×1080，757 张不同 JPEG，接收测量 25.1607 fps | 现场；独立相机 profile | [原始记录](../fpga/evidence/2026-10-10/hd-stream-guard30-validation-20261010.json) |

## 原独立候选目标门控的结果

该模块处理候选区域的空间与时序条件，不输出垃圾类别。以下历史独立记录的面积指 `mask_count` 匹配像素数，ROI 使用 PL 像素坐标；抖动指 bbox 四边界相对本段首个合格帧固定锚点的最大绝对差。连续帧指连续提交的合格新帧，序号需严格更新，但不要求相邻数值恰好加一。软件端还需验证来源、任务身份、相机/PL 帧关联和新鲜度；这些元数据并不证明由硬件认证了整幅图像的真实性。新四功能默认语义适配明示使用 PS 检测框面积 `bbox_area_px`，仅复用原规则与数值槽；该适配没有新的运行结果，不能将此处旧颜色测试外推为全类别验证。

| 项目 | 当前可报告内容 | 证据级别/完成状态 |
|---|---|---|
| 输入/输出与规则 | ROI、匹配像素数、连续帧、位置抖动、超时、单次候选许可；最终字段以模块接口为准 | 代码已实现；接口见 [sort_guard](../../fpga/sort_guard/README.md) |
| 软件适配与回放 | 新增 94 项离线检查通过；合成序列 ARM 10→帧 11/12/13→一次消费 | 软件；[接口/回放说明](../../fpga/sort_guard/host/README.md)、[测试](../../tests/sort_guard/)；不是板端结果 |
| RTL 功能覆盖 | 661 次断言检查，418 次 AXI 写、66 次读；记录 AXI 许可 2 次、核心许可 1 次，超时优先级/复位及 external_busy 跨复位保持通过 | RTL，Vivado 2020.1；[结果记录](../../fpga/sort_guard/validation/result.json)，断言次数不是独立场景数或物理样本数 |
| 综合资源 | 866 LUT、949 FF、0 BRAM、0 DSP；XCZU19EG-FFVC1760-2-I | OOC 综合，Vivado 2020.1，Synthesized；[资源报告](../../fpga/sort_guard/validation/reports/utilization.rpt)、[实际结果及哈希](../../fpga/sort_guard/validation/result.json) |
| 综合网表时序 | 综合后施加 10 ns 报告约束，WNS 7.112 ns、WHS 0.061 ns | 综合估计；67 输入/40 输出无 I/O delay、未设置 HD.CLK_SRC；未布局布线，不能作为板上频率；[时序报告](../../fpga/sort_guard/validation/reports/timing_synth_only.rpt) |
| 真实设备端到端延迟 | 上板传输、候选判定、许可读取的总耗时 | 待测 |
| 与现用 DOFBOT 联动 | 统一任务与坐标对应后的分拣闭环 | 待联调；当前不下发动作 |

## 尚需专门采集的数据

| 指标 | 当前状态 | 合适的测量口径 |
|---|---|---|
| 垃圾识别准确率/召回率 | 待测 | 固定类别清单、独立标注样本、光照/遮挡条件与混淆矩阵 |
| 语音识别率/误触发率 | 待测 | 指令次数、说话人、距离、背景噪声、正确/遗漏/误触发计数 |
| 物理抓取与投放成功率 | 待测 | 按类别记录总尝试、夹起、保持、正确投放及失败原因；不能用 SDK 回调代替 |
| 单次任务总耗时 | 待测 | 明确起点为口令接受，终点为返回等待；另列识别/播报/动作阶段 |
| 功耗与能效 | 待测 | 电压、电流、仪表、采样频率、空闲/任务工况 |
| 同等算法/画质的加速比 | 待测 | 相同输入、分辨率、算法输出和计时范围的 CPU/PL 对照 |
| 外部坐标精度 | 待测 | 独立量尺真值、位置覆盖与误差分布；区分图内检查残差 |

## 可复用的贡献表述

“团队完成了颜色感知链的流控与统计接口、候选目标约束、单次语音任务编排、实时展示及部署验证；检测模型、底层 SDK、既有动作和复用 IP 作为外部基础接入。各项实现与性能按照现场、软件、仿真和综合证据分别记录。”
