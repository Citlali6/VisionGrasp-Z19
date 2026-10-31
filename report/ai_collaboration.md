# 大模型协作与纠错记录

本页对应指南 3.3.3.1、3.3.5.3 中的开发协作要求：记录人如何向 AI 提交工程任务、审阅输出、纠正判断并形成可复用经验。产品运行时的 YOLO、Vosk、PL 算子与 VM SDK 分工属于[系统架构](../docs/architecture.md)，不是这里所说的大模型协作；产品没有因此部署运行时 LLM。

## 记录范围与可复核来源

以下四例是**依据提交整理的案例摘要**。会话 `turn_context.model` 记录为 `gpt-6.1-sol`，不以提交作者字段认定代码完全由 AI 独立完成。摘要保留初次交付、集中返修和安装契约遗漏中的真实错误与修正。

| 来源 | 可确认的信息 | 保留方式 |
|---|---|---|
| 用户提供的《Codex 总执行提示词：Z19 PS/PL 四功能工程补充与源码交付》，2026-10-30 | 四项实际源码任务、接口/来源要求与执行边界；相关条款见下列各例 | 用户本地原件；公开工程说明见[四功能入口](../fpga/system_pspl/README.md) |
| 用户提供的《VisionGrasp-Z19 四功能工程审计报告》，2026-10-30 | 对初次输出的审阅意见与集中返修方向；下文只节选实际文字 | 用户本地原件，未将个人附件路径或完整聊天库公开 |
| [初次源码交付 9dc4df9](https://github.com/Citlali6/VisionGrasp-Z19/commit/9dc4df9cce400b9fe9c8400fe991a690e465d663) | 可以复核 AI 辅助开发的实际输出文件及初始不足 | Git 历史，固定 SHA |
| [源码修订 8a76e84](https://github.com/Citlali6/VisionGrasp-Z19/commit/8a76e84c99a3e62677a0cfe831979ff36e0555d5) | 候选策略、语音边界、展示回调和模型契约的具体修订 | Git 差异，固定 SHA |
| [说明修订 7cf7513](https://github.com/Citlali6/VisionGrasp-Z19/commit/7cf7513a42d5b5f3b3c66eec1e950786b6478b83) | 修订缘由与范围 | Git 历史 |

下方案例按实际任务消息、AI 输出与人工修正整理；未公开整套会话库、内部推理或工具凭据。每个案例的提交与源码路径均可复核。

<a id="case-color-policy"></a>
## 案例一：语义候选与颜色约束

- **原任务/提示词出处**：四功能总提示词第5.4节要求颜色候选与语义目标有明确对应关系，第8.2节要求新客户端保持一次任务语义。
- **AI 输出及问题**：[9dc4df9 的 guard_adapter.py](https://github.com/Citlali6/VisionGrasp-Z19/blob/9dc4df9cce400b9fe9c8400fe991a690e465d663/host/app/perception/guard_adapter.py)将候选许可统一放在 `association.state == associated` 之后；指定颜色像素为空时，即使语义模型给出唯一目标也无法进入该许可路径。
- **人工审阅依据**：用户审计明确指出：“现有方案不适合未经场景约束就作为全部 16 种垃圾的统一抓取门槛。” 判断重点是规则的适用范围，不能把“没有指定颜色”解释成“没有合法语义目标”。
- **修正提交**：8a76e84 将默认策略改为 `semantic_bbox`，以明示的 PS 检测框面积复用既有 GuardClient/PL 连续帧规则；`color_association` 仅显式颜色工位使用。服务、消息与客户端同时检查策略和 `count_basis`，PS 框面积不冒充 PL mask 像素数。本轮收尾进一步将颜色专用掩码复制/连通区域分析限制在颜色分支；默认分支保留结构化 `association.state=not_requested`、`reason=semantic_bbox_policy`。源码见[service.py](../host/app/perception/service.py)、[guard_adapter.py](../host/app/perception/guard_adapter.py)和[客户端](../robot/dofbot/pspl_client.py)。
- **形成的经验**：先定义候选规则适用的证据类型，再连接动作许可；保守检查也可能因使用范围错误而排除有效目标。该例进入[寄存器与 PIO 契约技能](../skill/register_contract/SKILL.md)的字段/副作用/语义核对流程。
- **证据层级**：修订提交和源码路径可复核；该例的结论限于接口与候选路径。

<a id="case-voice-boundary"></a>
## 案例二：统一口令并清除跨任务旧语音

- **原任务/提示词出处**：四功能总提示词第2.3、6.5、8.2节区分 USB PCM 与串口编号，要求同一任务单一语音源、断流清理和原有唤醒/启动行为。
- **AI 输出及问题**：[9dc4df9 的 usb_pcm_pl.py](https://github.com/Citlali6/VisionGrasp-Z19/blob/9dc4df9cce400b9fe9c8400fe991a690e465d663/host/app/voice/usb_pcm_pl.py)采用“小助手”唤醒词；接收代际与最终 PCM 块年龄也不足以排除忙碌期半句在任务结束后才完成 ASR 的路径。
- **人工审阅依据**：用户审计说明现用演示以“你好小亚”唤醒，并要求保留原有唤醒和任务行为。工程交叉审阅进一步沿采集管道、滤波历史、ASR 片段及网络事件追踪缓存，识别到仅清接收队列或仅 Reset ASR 的遗漏。
- **修正提交**：8a76e84 统一“你好小亚”→中文 wake1、“开始垃圾分拣”→现用 start92，保留原 Session 的语言/编号规则。USB 增加 `/voice/boundary`：生产线程中断旧采集、丢弃在途 PCM、关闭旧管道、重建滤波会话并 Reset ASR，新采集启动后才确认 `boundary_id`。服务和 VM 核对边界，旧事件不改贴新代际。见[生产端](../host/app/voice/usb_pcm_pl.py)、[接口说明](../fpga/audio_frontend/README.md)。
- **形成的经验**：任务边界必须跨过所有拥有缓存的生产环节，不能只看最后一条消息。输出为[语音任务边界技能](../skill/voice_task_boundary/SKILL.md)。
- **证据层级**：标准口令依据[现用快速开始](../docs/QUICKSTART.md)及保留的部署记录；新 USB 边界的结论限于源码与接口。

<a id="case-readonly-observability"></a>
## 案例三：新入口继承控制，也要接回观测

- **原任务/提示词出处**：四功能总提示词第8节要求新 PS 服务与现用 VM 形成完整软件出口，同时保留原现场入口、相机所有权及一次任务顺序。
- **AI 输出及问题**：[9dc4df9 的 pspl_entry.py](https://github.com/Citlali6/VisionGrasp-Z19/blob/9dc4df9cce400b9fe9c8400fe991a690e465d663/robot/dofbot/pspl_entry.py)继承 Session 的主流程，却没有接入原 `save` 和 `recognized` 回调。用户审计指出：“它是新增协同方案的软件完整性问题。”
- **人工判断与继续纠错**：新入口应提供独立输出目录、状态和识别图片，UI 不能另开控制设备。源码交叉审阅又发现，编码期间读取最新来源/代际会给旧 JPEG 配上新身份，因此图像与元数据必须在同一快照中取出并随实际发布一起提交。
- **修正提交**：8a76e84 连接 Session 回调，新增[pspl_display.py](../robot/dofbot/pspl_display.py)并复用原发布器/窗口接口；PS `/preview` 提供明确标记的原始采集旁路。记录绑定 PID、start ticks、boot ID 和运行会话，图像发布元数据保留所属来源/代际。7cf7513 同步了新旧预览的表达范围。
- **形成的经验**：继承控制状态机不等于完整继承可观测性；旁路展示也需要一致性契约。输出为[只读观测技能](../skill/readonly_observability/SKILL.md)。
- **证据层级**：原 DOFBOT 展示记录属于原部署；新适配的结论限于源码与接口。

<a id="case-model-contract"></a>
## 案例四：把模型来源记录与目标部署条件分开

- **原任务/提示词出处**：四功能总提示词第4.1—4.3节要求取得真实调用链、保留前后处理与类别顺序来源，不把 VM x86 二进制或环境假设移植成 AArch64 事实。
- **AI 输出及问题**：[9dc4df9 的 model_manifest.py](https://github.com/Citlali6/VisionGrasp-Z19/blob/9dc4df9cce400b9fe9c8400fe991a690e465d663/host/app/perception/model_manifest.py)存在未由实际后端取得的内层尺寸、stride、IoU、max_det 和 letterbox 假设，也未充分分开来源与目标环境。
- **人工审阅依据**：用户审计指出：“这些信息本轮没有取得。” 工程审阅据此保留未登记参数，并要求入册与运行读取共用同一清单规则，不能让一个模板看起来已可直接部署。
- **修正提交**：8a76e84 分开 VM 来源环境与 AArch64 Linux 目标 Python/libc/库版本；未知参数在[契约示例](../host/app/perception/contract.example.json)保留为 `null`，要求真实权重、类序和框架文件哈希。入册/加载统一检查，未来显式加载再次核对类别及实际 stride，依赖错误与成功空检测保持区别。见[模型清单](../host/app/perception/model_manifest.py)、[入册工具](../host/app/perception/enroll_model.py)、[调用后端](../host/app/perception/detector.py)。
- **形成的经验**：来源、接口支持范围和目标运行条件分别登记；不知道的参数必须成为可定位条目。它补充[寄存器契约技能](../skill/register_contract/SKILL.md)的单一事实来源方法；像素/坐标输入关系另见[帧契约技能](../skill/stream_frame_contract/SKILL.md)。
- **证据层级**：确认的是契约与错误路径的源码修订；模型与目标环境按清单登记。

## 从纠错到技能交付

这轮实际工作流是：用户给出范围与执行边界 → Codex 辅助编写源码 → 用户提供外部审计 → 对具体分支做交叉源码审阅 → 集中修订并保留提交 → 将共性判断提炼到[skill/](../skill/README.md)。四功能返修代码提交为8a76e84，说明提交为7cf7513；本轮收尾继续做材料和有限源码修订，不重写这些历史提交。

AI 的作用体现在接口实现、跨文件对应和候选修订；人工审阅负责确认场景、部署语义、证据归属和授权范围。上述记录保留了初次输出的问题与修正。源码审阅与技能文档不转述为识别率、响应时间或资源优化；运行成果从[证据矩阵](../docs/competition/EVIDENCE_MATRIX.md)按其版本引用。

## 后续审计：安装来源与测试契约

安装契约案例记录了对 19a09b9 的审计与修正。此前只在文档要求检出 8a2a6fd，未同步当前安装器/测试默认源，导致两个新 Dashboard 文件与原清单冲突。修订提交 `2176fbca057a42a530e0ca981bdaf63f4c628b77` 将原15文件保存在独立冻结payload，当前安装器与测试共同选择该源，并精确断言拒绝原因；原manifest哈希不改写。逐文件Git blob/哈希支持来源一致性，该例的安装与测试入口以提交差异记录。该例说明源码、运行清单、安装源和测试fixture必须对应同一版本，仅补操作说明不足以闭合交付契约。
