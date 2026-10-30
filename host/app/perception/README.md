# PS 垃圾识别、定位与任务服务

`detector.py` 调用实际 `ultralytics.YOLO(..., task='detect')` CPU 后端。读取的厂商 `garbage_identify.py` 与 `single_garbage_identify.py` 哈希和缺失资料集中于 [model_sources.json](model_sources.json)。PS 不导入厂商模块，避免其模块级模型加载、ROS 初始化和机械臂串口副作用。类别的真实顺序来自匹配权重的 `model.names`；[class_mapping.py](class_mapping.py) 只保存已核对的业务映射，不把其排列当神经网络 class ID。

输入是无标注 RGB888。原图线性缩放至视频 profile 尺寸后送 PL，配置明确选择 `pl_rgb` 或 `raw_rgb` 作为分类输入。两者均保留原始/处理图的 SHA-256 和像素空间身份。厂商外层先缩放至 640×480 BGR，再交给 Ultralytics。内部 letterbox、RGB tensor、除以255和 NMS 由匹配的后端执行；后处理解析真实 post-NMS `N×6` boxes 并仅撤销外层缩放，不重复 NMS。

`ModelManifest.read()` 要求真实权重哈希、顺序类别、源环境与目标环境、实现文件哈希及预处理契约。`Detector.load()` 才显式初始化并核对实际权重类别及模型 stride。缺模型、缺 manifest、缺后端或契约不符均为异常；只有成功调用真实模型后返回的空 boxes 才是无目标。当前缺失权重、类别 YAML、框架修改与环境资料，不能据目录 `yolov11` 推断结构或填写部署事实。

模型部署契约的完整结构见 [contract.example.json](contract.example.json)。这是供填写真资料的**不完整示例**，所有 `null` 与 `REQUIRED` 必须补齐，不能直接作为可运行清单。示例中的固定输入/输出字段说明这个适配器接受的 NumPy/Results 接口，不能据此宣称配套框架内部行为已经核对。实际依赖需求如下：

| 字段/资料 | 来源和使用规则 |
|---|---|
| weights_sha256、names、names_sha256 | 合法配套 `best.pt`、匹配训练 YAML/既有权重类别记录；业务映射的16项排列不能替代真实模型类序。未来加载时再次比较 `model.names` |
| framework_files | 填写实际源树中的相对路径→SHA-256，覆盖真实加载器、预测器、letterbox/归一化、NMS、默认配置及模型定义/本地修改。不假定某版本目录布局或固定五/六文件集合；入册与运行核对同一清单，实际导入入口也必须在其中 |
| source_environment | VM 的真实 machine、Python、OS，以及至少 `ultralytics/torch/numpy/cv2` 的库版本，保留为来源记录；匹配后端还依赖哪些库应按实际源代码补充 |
| target_environment | 单独记录 Z19 AArch64 Linux 的 machine、Python、OS、libc name/version 和实际库版本；`versions` 由入册工具从这里复制，未来显式加载按目标记录核对；新增库使用真实可导入模块名与 `__version__` |
| compatibility_notes | 记录源与目标的版本差异、AArch64 原生依赖来源和移植选择。VM 的 x86 二进制不能作为目标库；相同 Python 包版本也不证明 ABI 兼容。加载错误会传播，不把登记清单当板端运行验收 |
| image_size、model_stride | 填写真正预测器内层 `imgsz` 与实际模型最大 stride，尺寸按该 stride 对齐；不再默认640或32。原程序外层640×480是另一项已核对的操作。未来加载核对实际 stride |
| iou、max_detections | 从匹配的框架默认值/调用配置取得实际 NMS 参数，不填猜测的0.7或300。原调用中已明确的置信度固定保留0.65 |
| preprocess | 标明输入RGB、后端BGR uint8 HWC、外层缩放、batch、张量颜色/布局/dtype/归一化、实际 letterbox_fill/rect，以及后端已完成NMS和 `xyxy/conf/class` 输出。内部操作由同一哈希固定的真实后端完成，不在外层重复执行；不能默认填充值114 |

`cv2` 使用库的 `__version__` 核对，兼容真实环境采用系统 OpenCV 的安装方式，不强制要求名为 `opencv-python` 的 wheel 分发。目标 Python/libc 记录对应未来显式加载时的 `platform.python_version()` 与 `platform.libc_ver()`；这轮没有执行这些目标采集或初始化操作。

未来取得资料后，使用 [enroll_model.py](enroll_model.py) 从匹配 YAML、权重、源树及 `visiongrasp.vm-backend-contract/1` JSON 写出 `visiongrasp.ps-model-manifest/1`。工具只哈希/读取文件、不反序列化或推理，创建输出前调用与运行加载共用的 `ModelManifest.from_data()` 完整校验；拒绝覆盖已有清单。入册本身也没有在本轮运行。模型类别、stride 与原生库实际能否成功加载，仍属于以后另行授权的运行步骤。

`CoordinateMapper` 分别返回检测框中心与颜色匹配像素质心。零 count 返回空坐标。像素→工作平面矩阵必须绑定 camera_id、transform_id、image_size、calibration_id，输出限于 `table_xy_mm`。无匹配标定时保留像素及原因。现有网格矩阵先归一化输入并输出归一化板面；`import_legacy_normalized_grid()` 显式组合尺寸换算，不能直接当像素→毫米矩阵。

任务候选通过双端显式核对的 `candidate_policy` 选择，不把颜色当作垃圾类别：

| 策略 | 候选与计数依据 | 颜色作用 |
|---|---|---|
| `semantic_bbox`（示例默认） | 同帧唯一真实语义框 → 包含该连续矩形的闭区间整数框；`bbox_area_px=(xmax-xmin+1)*(ymax-ymin+1)` | PL mask/颜色质心/连通区对应独立报告，零颜色或多个颜色区域不否决语义候选 |
| `color_association`（显式颜色工位） | 唯一语义目标与唯一且包含于框内的PL连通区域 → `pl_mask_pixels` | 指定颜色是必要场景条件；零mask或歧义返回不适用/不确定 |

两种模式继承既有 `GuardClient` 和PL门控的ROI、数值计数范围、连续新帧、固定锚点抖动、超时和一次消费。新 `SemanticGuardClient` 只替换PS输入校验，使用 `visiongrasp.ps-semantic-candidate/1` / `Z19_PS_CPU_YOLO`，绑定模型、标签、类别、相机、transform与配置；不伪造旧PL颜色状态，也不修改旧RTL/寄存器ID/ABI。原寄存器 `mask_count` 的数值槽在此模式明示承载PS框面积，颜色模式仍为真实PL掩码数。语义框面积不是分割面积或PL统计。

默认语义分支不复制/清零颜色关联掩码、不计算连通区域；`association` 保留稳定字段 `state=not_requested, reason=semantic_bbox_policy`。完整PL计算、整帧回读、统计/来源合法性检查和独立颜色质心仍保留。颜色模式才调用 `associate_color()`；这次仅移除不必要调用，没有实测加速比。

标签、配置或模型改变取消本段并重新累计；来源失配、多目标或超时不许可。ARM帧是基线，后续 `required` 个合格新帧才累计就绪；一个已消费许可对应一次固定工位任务，不是机械安全联锁。缺guard配置只报告结果而不产生许可，不自动绕过门控。

未来显式入口为 `python -m host.app.perception.service --config <private-config.json>`。构造不打开设备；`Runtime.open()` 才初始化 V4L2、UIO、真实模型及可选音频。配置至少包含：

完整配置结构见 [PS 示例](config.example.json) 和 [VM 示例](../../../robot/dofbot/pspl_config.example.json)。所有 `REQUIRED` 都必须由部署者填写；示例无有效设备节点、凭据、权重或登记清单，直接使用会明确报错。1280×720→640×360 的逆像素中心映射为 `[2,0,0.5,0,2,0.5,0,0,1]`。HSV、面积范围、抖动和2秒门控周期均为设计参数；绿色阈值仅配置颜色统计，默认语义任务不要求绿色。门控周期按新profile的100MHz目标时钟换算，不是运行耗时测量。语义模式读取 `min_bbox_area/max_bbox_area`，颜色模式读取 `min_mask/max_mask`，不混用单位。

双端 `voice_source` 必须一致；`serial_id` 保留VM原串口事件源，只有显式改为 `usb_pcm_pl` 并填写音频配置才启用PS音频链。两种模式均为“你好小亚”唤醒、回应后“开始垃圾分拣”启动；USB仅支持当前中文任务词表，串口原编号/语言语义保留。命令编号不是PCM，不经过PL FIR。服务默认绑定回环地址，跨VM使用须显式填写Z19接口地址。

| 配置 | 内容 |
|---|---|
| camera | `device` 持久 by-id 路径、`camera_id`、width、height、fps |
| video | libpspl 路径、明确 UIO、width/height、HSV、ROI、gain/bias、config_version；与新 profile 对应 |
| model_manifest | 合法取得依赖后实际登记的 manifest 路径 |
| input_source | `pl_rgb` 或 `raw_rgb`，写入结果来源 |
| candidate_policy | `semantic_bbox` 或 `color_association`，与VM配置及每轮任务/结果一致 |
| capture_space_id / transform_id | 原图、线性缩放后像素空间名称 |
| pixel_to_capture | cv2.resize 逆映射 `[sx,0,(sx-1)/2,0,sy,(sy-1)/2,0,0,1]`，sx=原宽/处理宽；其他变换拒绝 |
| calibration | 可选；camera_id、transform_id、image_size、calibration_id、coordinate_frame=`table_xy_mm`、pixel_to_table_mm、table_bounds_mm |
| guard | 新profile的明确UIO/lib、roi、required、jitter、timeout_cycles、max_age_s；语义模式需min_bbox_area/max_bbox_area；颜色模式需color、min_s/min_v及min_mask/max_mask且ROI/阈值与PL一致；可省略但不会产生许可 |
| voice | `voice_source` 默认 `serial_id`；选 `usb_pcm_pl` 时填写音频模块要求的全部配置，服务启动独立采音/PL/Vosk 线程 |
| http | 明确 bind、port、token_file；token至少32字符，不提交仓库 |

HTTP POST `/task` 启动新task_id（20秒内），`/result` 读取最新同帧语义/颜色/许可，`/cancel` 撤销，`/voice` 读取受限语音事件，`/voice/boundary` 确认USB语音清理边界，`/preview` 提供独立相机旁路，`/stop` 退出。所有请求为JSON+Bearer，单报文上限2MiB、连接读写超时3秒、最多8个处理线程；JPEG上限512KiB。语音边界确认截止设为8秒，客户端请求截止为10秒，迟到或未确认即报错，不接纳旧事件；这不是资源清理函数的严格全调用耗时保证。

新VM会话接收语音前和每轮输入清理时，USB模式要求生产端关闭旧arecord及管道、丢弃在途PCM、重建滤波会话并重置ASR，再确认递增boundary_id。旧语音事件不得跨此边界重标为新事件，从而避免忙碌期间的口令延后结束并触发下一轮。串口模式仍按原输入缓冲/代际规则处理。清理是未来运行时的显式操作，本轮未执行。

旁路明确标记 `source=ps_camera_preview,pl_processed=false`，在待机/播报/动作期间仍读取新采集帧，不调用模型或产生许可。采集/网络失败使预览离线或过期，不循环旧图冒充LIVE。跨机器传生产端数据年龄，接收端叠加请求和解码时间检查时效；本地换算时间是保守估计，不是精确跨机采集延迟。

取消与超时在传输/推理调用之间检查，取消后的推理结果丢弃。CPU 模型调用不做不安全的线程强杀；若底层驱动/模型阻塞，服务停止接收新任务且退出时不关闭仍被工作线程使用的 MMIO。相机断流/音频断流会明确报错，滤波/ASR 会话不与新会话拼接。

VM 的独立入口见 [pspl_entry.py](../../../robot/dofbot/pspl_entry.py) 与 [pspl_client.py](../../../robot/dofbot/pspl_client.py)。它复用原 `Session` 的唤醒/启动、准备先于识别、播报完成后抓取顺序，独立新 cycle 接受一次真实候选许可，避免把旧三帧门槛套在一个已消费许可上。`detect()` 保留 `(frame,msg)`，`msg` 中位置按已核对厂商 `(b,-a)` 数值约定转为稳定性代理，绝不作为毫米标定或任意位置抓取坐标。原启动器、现场 VM、动作参数与模型均未替换。

新入口的展示、状态/图片回调及日志配置见 [PS/PL展示说明](../../../robot/dofbot/PSPL.md)。它使用单独输出根目录和原机械臂互斥锁，复用现有发布器/只读窗口；原窗口默认仍核对原部署进程。新任务状态与图像归新会话，不混入原实测记录。

PIO逐像素往返、PS缩放和CPU YOLO均可能决定端到端瓶颈。5秒传输截止可配置；它不保证帧率或吞吐。本轮没有执行性能判断实验，原7.26fps仅归旧颜色profile。

本轮只完成源码与文本/接口审阅；没有导入、编译、运行、模型推理、音频验证、服务启动或设备操作。新功能没有性能测量结果。
