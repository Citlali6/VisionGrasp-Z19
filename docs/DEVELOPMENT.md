# 开发与离线验证

## 选择模块

DOFBOT 应用位于 `robot/dofbot/`，Z19 感知位于 `fpga/`、`host/`。二者各自运行和验收，修改一个模块不要求启动另一个模块。系统关系见[架构](ARCHITECTURE.md)。

普通软件检查使用 Python 3.10 或更新版本及仓库开发依赖；部署兼容性仍以各模块声明为准。DOFBOT 配套环境是 Python 3.10，旧 Z19 语音环境使用 AArch64 / Python 3.7，不要将板端 wheel 安装到 PC。

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -B -m unittest discover -s host/tests -p test_audio.py -v
python -B tools/test_z19_sd.py
```

以上三组当前分别通过 78、10、9 项检查，合计 97 项。根目录 pytest 默认只发现 DOFBOT 测试；音频和 SD 格式检查按独立命令运行。

这些检查使用伪设备和固定输入，不启动 ROS 节点、摄像头、串口、语音播放或 FPGA MMIO。安装包可单独生成到临时目录审阅：

```bash
python robot/dofbot/install.py --staging-root /tmp/dofbot-install-review
```

不要执行测试生成的启动脚本。安装器真实部署的前提和外部依赖见[快速开始](QUICKSTART.md)。

Windows 还可运行 `powershell -NoProfile -File tools/test_prepare_z19_sd.ps1`，验证 12 个模拟磁盘守卫场景；它使用替身，不连接真实磁盘。仓库结构和文档检查执行 `python .github/scripts/check_repository.py`。

## FPGA 检查

颜色模块的三套仿真覆盖 HSV 数值、视频流背压和 AXI-Lite 寄存器行为，使用 Vivado 2020.1；命令、成功标记与输出目录规则见[颜色模块说明](../fpga/color_locator/README.md)。仿真不加载板卡。

MIPI 相机源工程要求 Vivado 2020.2_AR75986。保留其原 IP 配置，不为迁就本机工具自动升级或降级。源码引用、构建产物 SHA-256、驱动测试和板端实测是不同检查项，应分别报告。

## 维护定稿版本

运行源码与已验证基线通过 `deployment_manifest.json` 关联，外部依赖由 `external_dependencies.json` 描述。正常的功能演进应同步修改清单和验证记录；仓库整理不能悄悄调整动作参数或检测条件。

状态机、协议、展示模型和进程管理可用离线测试验证；真实 USB 枚举、音频听感、抓取效果和相机标定仍需现场验证。提交前检查相对链接、导入、Shell 语法、来源声明、敏感信息和大文件。CI 仅运行不接触硬件的检查，完整记录入口见[验证结果](VALIDATION.md)。
