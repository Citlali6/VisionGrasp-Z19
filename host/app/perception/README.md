# PS 垃圾识别、定位与任务服务

`detector.py` 调用实际 `ultralytics.YOLO(..., task='detect')` CPU 后端。读取的厂商 `garbage_identify.py` 与 `single_garbage_identify.py` 哈希和缺失资料集中于 [model_sources.json](model_sources.json)。PS 不导入厂商模块，避免其模块级模型加载、ROS 初始化和机械臂串口副作用。类别的真实顺序来自匹配权重的 `model.names`；[class_mapping.py](class_mapping.py) 只保存已核对的业务映射，不把其排列当神经网络 class ID。

输入是无标注 RGB888。原图线性缩放至视频 profile 尺寸后送 PL，配置明确选择 `pl_rgb` 或 `raw_rgb` 作为分类输入。两者均保留原始/处理图的 SHA-256 和像素空间身份。厂商外层先缩放至 640×480 BGR，再交给 Ultralytics。内部 letterbox、RGB tensor、除以255和 NMS 由匹配的后端执行；后处理解析真实 post-NMS `N×6` boxes 并仅撤销外层缩放，不重复 NMS。

`ModelManifest.read()` 要求真实权重哈希、顺序类别、精确版本、实现文件哈希及预处理契约。`Detector.load()` 显式初始化并核对实际权重类别。缺模型/后端是异常；真实空 boxes 才是无目标。当前缺失权重、类别 YAML、框架修改与环境资料，不能据目录 `yolov11` 推断结构或伪造 manifest。未来可在合法取得依赖后使用 [enroll_model.py](enroll_model.py) 从匹配 YAML、权重及 `visiongrasp.vm-backend-contract/1` JSON 写出部署 manifest；该工具本轮没有运行。

`CoordinateMapper` 分别返回检测框中心与颜色匹配像素质心。零 count 返回空坐标。像素→工作平面矩阵必须绑定 camera_id、transform_id、image_size、calibration_id，输出限于 `table_xy_mm`。无匹配标定时保留像素及原因。现有网格矩阵先归一化输入并输出归一化板面；`import_legacy_normalized_grid()` 显式组合尺寸换算，不能直接当像素→毫米矩阵。

目标对应采用保守条件：同相机/会话/帧、仅一个语义目标、ROI 内 PL mask 仅一个8连通区域、颜色区域完全位于语义框。多个同色区、多个语义目标或信息不足返回不确定。`CandidateGuard` 把完整同帧统计转为原协议，复用既有 `GuardClient` 的连续帧、固定锚点、超时和一次消费机制。标签变化或对应失效取消本段；一个已消费许可对应一个固定工位任务，不是机械安全联锁。

未来显式入口为 `python -m host.app.perception.service --config <private-config.json>`。构造不打开设备；`Runtime.open()` 才初始化 V4L2、UIO、真实模型及可选音频。配置至少包含：

完整配置结构见 [PS 示例](config.example.json) 和 [VM 示例](../../../robot/dofbot/pspl_config.example.json)。所有 `REQUIRED` 都必须由部署者填写；示例无有效设备节点、凭据、权重或登记清单，直接使用会明确报错。1280×720→640×360 的逆像素中心映射为 `[2,0,0.5,0,2,0.5,0,0,1]`。示例 HSV、像素数、抖动和2秒门控周期是可修改设计参数，未从现场噪声、目标或性能测量获得；颜色编号2只是该任务的绿色筛选标签，不能代替垃圾语义。门控周期按新 profile 的100MHz目标时钟换算。双端 voice_source 必须一致；`serial_id` 保留 VM 原串口事件源，只有显式改为 `usb_pcm_pl` 并填写音频配置时才启用 PS 音频链。服务默认只绑定回环地址，跨 VM 使用时须显式填写 Z19 接口地址。

| 配置 | 内容 |
|---|---|
| camera | `device` 持久 by-id 路径、`camera_id`、width、height、fps |
| video | libpspl 路径、明确 UIO、width/height、HSV、ROI、gain/bias、config_version；与新 profile 对应 |
| model_manifest | 合法取得依赖后实际登记的 manifest 路径 |
| input_source | `pl_rgb` 或 `raw_rgb`，写入结果来源 |
| capture_space_id / transform_id | 原图、线性缩放后像素空间名称 |
| pixel_to_capture | cv2.resize 逆映射 `[sx,0,(sx-1)/2,0,sy,(sy-1)/2,0,0,1]`，sx=原宽/处理宽；其他变换拒绝 |
| calibration | 可选；camera_id、transform_id、image_size、calibration_id、coordinate_frame=`table_xy_mm`、pixel_to_table_mm、table_bounds_mm |
| guard | 新 profile 的明确 UIO/lib；color、min_s/min_v、roi、min_mask/max_mask、required、jitter、timeout_cycles、max_age_s；可省略但不会产生许可 |
| voice | `voice_source` 默认 `serial_id`；选 `usb_pcm_pl` 时填写音频模块要求的全部配置，服务启动独立采音/PL/Vosk 线程 |
| http | 明确 bind、port、token_file；token至少32字符，不提交仓库 |

HTTP POST `/task` 启动新 task_id（20秒内），`/result` 读取状态与最新同帧语义/颜色/许可、`/cancel` 撤销、`/voice` 读取受限语音事件、`/stop` 请求退出。所有请求为 JSON+Bearer，单报文上限2MiB、单连接3秒、最多8个处理线程；预览 JPEG 上限512KiB。运行期间不执行任意识别文本或调用电机。跨机器只传生产端数据年龄；接收端叠加本次请求耗时检查新鲜度。

取消与超时在传输/推理调用之间检查，取消后的推理结果丢弃。CPU 模型调用不做不安全的线程强杀；若底层驱动/模型阻塞，服务停止接收新任务且退出时不关闭仍被工作线程使用的 MMIO。相机断流/音频断流会明确报错，滤波/ASR 会话不与新会话拼接。

VM 的独立入口见 [pspl_entry.py](../../../robot/dofbot/pspl_entry.py) 与 [pspl_client.py](../../../robot/dofbot/pspl_client.py)。它复用原 `Session` 的唤醒/启动、准备先于识别、播报完成后抓取顺序，独立新 cycle 接受一次真实候选许可，避免把旧三帧门槛套在一个已消费许可上。`detect()` 保留 `(frame,msg)`，`msg` 中位置按已核对厂商 `(b,-a)` 数值约定转为稳定性代理，绝不作为毫米标定或任意位置抓取坐标。原启动器、现场 VM、动作参数与模型均未替换。

本轮只完成源码与文本/接口审阅；没有导入、编译、运行、模型推理、音频验证、服务启动或设备操作。新功能没有性能测量结果。
