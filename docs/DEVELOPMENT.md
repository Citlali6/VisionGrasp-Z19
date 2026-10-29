# 开发与离线验证

## 选择模块

DOFBOT 应用位于 `robot/dofbot/`，Z19 感知位于 `fpga/`、`host/`，新增候选门控位于 `fpga/sort_guard/`。各模块独立验证，修改一个模块不要求启动其他模块。系统关系见[架构](ARCHITECTURE.md)。

普通软件检查使用 Python 3.10 或更新版本及仓库开发依赖；部署兼容性仍以各模块声明为准。DOFBOT 配套环境是 Python 3.10，旧 Z19 语音环境使用 AArch64 / Python 3.7，不要将板端 wheel 安装到 PC。

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -B -m unittest discover -s host/tests -p test_audio.py -v
python -B tools/test_z19_sd.py
```

定稿基线为 DOFBOT 78 项、音频 10 项、SD 格式 9 项。新增 `tests/sort_guard` 的 94 项离线检查使用同一 pytest 入口，因此 pytest 当前共 172 项，连同独立音频与 SD 检查共 191 项 Python 检查。新增合成回放另按下节入口运行；实际运行与版本信息见[验证记录](VALIDATION.md)。

这些检查使用伪设备和固定输入，不启动 ROS 节点、摄像头、串口、语音播放或 FPGA MMIO。安装包可单独生成到临时目录审阅：

```bash
python robot/dofbot/install.py --staging-root /tmp/dofbot-install-review
```

不要执行测试生成的启动脚本。安装器真实部署的前提和外部依赖见[快速开始](QUICKSTART.md)。

Windows 的 `tools/test_prepare_z19_sd.ps1` 覆盖 12 个模拟磁盘守卫场景，使用替身而非真实磁盘。它的 `-Package` 参数必填，需指向预先生成且通过清单校验的离线测试包；阅读脚本参数并准备 fixture 后再运行，不能直接省略参数。仓库结构和文档检查执行 `python .github/scripts/check_repository.py`。

## 新门控离线回放

```bash
python -m fpga.sort_guard.host.replay tests/sort_guard/fixtures/synthetic_stable.jsonl
```

该 JSONL 是标记为 `synthetic_fixture=true` 的合成输入，输出注明 `evidence_level=software_model` 与 `hardware_accessed=false`。回放使用软件寄存器模型，不探测地址、不打开串口，不代表真实相机或机械臂验收。接口和计时语义见 [sort_guard/INTERFACE.md](../fpga/sort_guard/INTERFACE.md)。

## FPGA 检查

颜色模块的三套仿真覆盖 HSV 数值、视频流背压和 AXI-Lite 寄存器行为，使用 Vivado 2020.1；命令、成功标记与输出目录规则见[颜色模块说明](../fpga/color_locator/README.md)。仿真不加载板卡。新增门控的 RTL 测试与 OOC 综合入口位于 `fpga/sort_guard/scripts/`；成功标记、参数及报告以[模块说明](../fpga/sort_guard/README.md)为准。OOC 时钟约束不是板上已测频率，综合资源不等于完整系统布局布线资源。

MIPI 相机源工程要求 Vivado 2020.2_AR75986。保留其原 IP 配置，不为迁就本机工具自动升级或降级。源码引用、构建产物 SHA-256、驱动测试和板端实测是不同检查项，应分别报告。

## 维护定稿版本

运行源码与已验证基线通过 `deployment_manifest.json` 关联，外部依赖由 `external_dependencies.json` 描述。正常的功能演进应同步修改清单和验证记录；仓库整理不能悄悄调整动作参数或检测条件。

状态机、协议、展示模型和进程管理可用离线测试验证；真实 USB 枚举、音频听感、抓取效果和相机标定仍需现场验证。提交前检查相对链接、导入、Shell 语法、来源声明、敏感信息和大文件。CI 仅运行不接触硬件的检查，完整记录入口见[验证结果](VALIDATION.md)。
