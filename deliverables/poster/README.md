# 芯语智分英文展示海报

交付日期：2026-10-30。单页横版 16:9，按本次需求保留重庆大学校名、校徽与 AMD 元素。

- [可编辑 PowerPoint](Xinyu_SmartSort_Poster_20261030.pptx)：文字、流程节点、架构方框与连接线均为原生对象；照片和标志为图片。
- [打印 PDF](Xinyu_SmartSort_Poster_20261030.pdf)：文字和图形保留矢量；A4 横向打印请选择适合纸张、保持比例。
- [预览 PNG](Xinyu_SmartSort_Poster_20261030.png)：3840 × 2160。

## 素材与设计

以用户提供的 `海报模板.pptx` 为底稿导入，保留 1280 × 720 画布比例与主题，重新组织三栏内容、字体层级及蓝白配色；`智拧易启海报.pptx` 仅供信息层级参考，未借用其成果数据或成员。AMD 标志来自模板，校徽使用既有用户素材 `cqu_logo.png`，保持原比例。

实物主图使用既有 `prototype_cutout.png`（1673 × 940，透明 PNG），保留机械臂、分拣区域、Z19、笔记本及相关外设。该素材的原制作记录注明曾使用 imagegen 清理现场照片背景；本次直接复用，未重新生成硬件。设备细节以原始实物资料为准。用户本次提供的 `09191fe6632834bd9b8c92bb97223703.png` 含已烘焙的棋盘格，故采用对应的透明素材版本。

## 内容来源

文案核对版本：`4e51e5b60daccccb38af0b4bd327502668d9ef72`，即本任务开始时的最新 `main`。

| 海报内容 | 仓库来源 |
|---|---|
| 正式名称、交互口令、固定工位任务流程、应用价值 | [README](../../README.md)、[项目概览](../../docs/overview.md) |
| PS / PL / VM 职责、YOLO / Vosk、RGB / HSV、ROI、一阶矩、63 抽头 FIR | [系统架构](../../docs/architecture.md)、[设计报告](../../report/design_report.md)、[配置说明](../../docs/CONFIGURATIONS.md) |
| 英文文案与展示定位 | [英文文案](../../report/poster_copy_en.md) |
| 演示与源码交付范围 | [证据矩阵](../../docs/competition/EVIDENCE_MATRIX.md)、[验证记录](../../docs/VALIDATION.md) |
| 模块复用与工程教学价值 | [Skill 索引](../../skill/README.md)、[开发协作](../../report/ai_collaboration.md) |

架构区标明四功能源码及职责关系；双向箭头表示 PS / PL 数据交换，不代表执行时序。现有成果写为 VM / DOFBOT 固定工位演示与 PS/PL 源码模块，联合板端集成列于下一步，未新增性能数字或整机验证结论。现用演示语音与新源码中的 Vosk 路径不混同。

未发现可确认的当前成员名单，因此未填写姓名。本版为用户指定的具名展示版；[参赛要求映射](../../docs/competition/requirements_map.md)记录的匿名决赛提交需另行移除校名校徽等身份信息。

## 文件核验

PPTX 结构、尺寸、字体和重新导入检查通过；PowerPoint 16.0 导出并核对全部 79 个文字框，无文本越界。PDF 经独立渲染检查，与 PNG 版面一致。本次检查仅针对海报文件，没有运行项目测试、模型、FPGA 工具或硬件流程。
