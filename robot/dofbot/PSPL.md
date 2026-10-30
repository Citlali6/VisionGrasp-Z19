# 可选 PS/PL 分拣入口与展示

该入口属于[四功能源码 profile](../../fpga/system_pspl/README.md)，配置与冻结演示的选择见[快速开始](../../docs/QUICKSTART.md)。原部署安装器应在 `8a2a6fd` 独立检出中使用；当前源码的可选界面扩展不改写原冻结文件哈希，也不由原安装器覆盖现场。

`pspl_entry.py` 使用 Z19 PS 服务的真实检测结果和一次 PL 候选许可，复用现有
`Session` 的一次唤醒/启动、准备先于识别、分类播报完成后抓取投放的顺序。
`candidate_policy` 默认选择 `semantic_bbox`；颜色对应模式须显式选择并满足其场景条件。
固定拾取姿态、厂商分类动作和 SDK 源码哈希保留，像素/平面定位结果不直接输入机械臂逆解。

默认部署仍使用原 `standalone_runtime.py`、启动器和输出位置。可选入口使用同一个
`/tmp/dofbot-standalone-voice.lock`，因此更换输出目录不会允许两个程序同时拥有机械臂。
原入口和新入口必须选择其中之一运行，本轮没有替换、停止或启动任何现场程序。

USB PCM 模式在接收线程启动前、任务开始和任务结束边界请求 PS 确认新的采音/滤波/ASR 代际。
它会丢弃旧 PCM 与未完成的识别内容，防止忙碌期间说出的口令在下一轮重新生效。
串口模式保持原来的本地输入清理和 Session generation 检查。

## 配置与未来入口

从 [pspl_config.example.json](pspl_config.example.json) 准备私有配置。填写实际 PS 地址、
私有 token 文件、相机/像素空间、语音来源及候选策略。`runtime_root` 必须为独立的绝对目录，
第一次使用时为空；后续仅接受本入口标记过的输出目录。它必须位于源码/安装目录之外，不能覆盖原 `records` 或
`dofbot-voice-preview`，包含已解析符号链接的实际目标。`open_viewer=true` 时显式打开
下面的只读窗口，默认 false。SDK/音频依赖和 ROS 环境仍须按现有 VM 配置准备。

以下是未来运行命令，本轮没有执行：

```bash
/usr/bin/python3 -B /absolute/path/robot/dofbot/pspl_entry.py --config /private/vm-pspl.json
/usr/bin/python3 -B /absolute/path/robot/dofbot/pspl_display.py --runtime-root /home/yahboom/codex_pspl_runtime
```

第一条不带 `--execute` 时不初始化机械臂 SDK或发送机械臂动作，但会连接所选语音源、
请求真实 PS 任务并按现有流程播报。将来明确启用机械臂时，使用同一个新入口的
`--execute`；应先停止其他控制实例并遵守现场设备授权。不能在本轮据这些命令启动程序。

## 状态、图像与日志

| 输出 | 内容和身份 |
|---|---|
| `runtime_root/records/bootstrap.json` | 真实 PID、进程 start_ticks、系统 boot_id、命令、入口路径、VM 运行 UUID、启动时间 |
| `runtime_root/records/status.json` | 现有 Session 状态、事件、generation、类别、动作调用次数、PS task/session/frame 与策略 |
| `runtime_root/preview/latest.jpg`、`live.json` | 实际远端相机旁路、源 PS 会话/帧、VM 发布序号、运行 UUID、generation、年龄与错误 |
| `runtime_root/records/cycle-NNN-detection.jpg/.json` | 接受许可时收到的 PS 识别图，以及同帧检测、配置、策略、类别和来源身份 |
| `runtime_root/sessions/UUID/` | 每次 VM 运行的独立 bootstrap/status、事件 JSONL、识别图和来源 JSON、实际 SDK 串口写入记录 |

状态保存和 `recognized` 图像回调已接入 `RemoteSession`。图片保存的是 VM 实际收到的
PS 预览，来源 JSON 保留其原图像空间和模型输入选择；它不是另一次模型测量。
SDK 写入记录包含实际返回字节数，动作阶段沿用 `ArmObserver/observe_sdk`，只表示已下发指令。
回调结束、串口写入和 UI 动画都不表示物理抓取成功。

`pspl_display.py` 直接复用现有 `PreviewPublisher`、`ArmObserver`、`dashboard_model.load_view`
及 `Dashboard` 小部件。模型和窗口增加了可选注入参数，默认参数仍使用原运行进程检查、
原路径和原展示行为。新适配器单独核对新入口、PID/start_ticks/boot_id、当前运行 UUID，
窗口锁也位于独立输出目录；它不改写默认窗口的进程判定。

预览通过受认证的只读 PS `/preview` 旁路独立轮询，每秒最多 8 次，不消费控制识别帧，
不修改任务、模型或候选状态，不打开 VM 本地相机。画面来源明确为 `ps_camera_preview`，
`pl_processed=false`：这是 PS 采集画面，不能将它称为 PL 图像处理效果。
分类实际输入与结果另由识别图和同帧来源 JSON 标识。

LIVE 同时要求实际新图像、生产端年龄和 VM 接收耗时满足新鲜度约束、图像与元数据序号一致、
运行 UUID/generation 匹配且无预览错误。VM 时间只与 VM 时间比较；生产端仅传年龄，
不直接相减两台机器的单调时钟。重复/冻结画面不会因轮询重新变成 LIVE。
JPEG 的来源帧与 generation 随同一缓存快照锁定，编码期间到达的新图不会改写旧 JPEG 的身份。
预览失败只影响显示旁路，停止窗口不会停止控制；控制异常通过 Session 状态和任务日志呈现。

本次仅进行源码、接口、路径及差异审阅，没有导入、运行、设备操作或新增验证。
