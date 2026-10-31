# DOFBOT 2026-10-29 冻结安装源

`payload/` 保存提交 [`8a2a6fd544cb6b79e868b8a710dc34b6027c6c8d`](https://github.com/Citlali6/VisionGrasp-Z19/tree/8a2a6fd544cb6b79e868b8a710dc34b6027c6c8d/robot/dofbot) 中的15个原始文件：12个应用文件、原部署清单、外部依赖清单及历史README。文件来源与原字节由该 Git 提交固定。局部 `.gitattributes` 禁止Git对payload转换换行，保持冻结字节。

当前 [安装器](../../robot/dofbot/install.py) 默认从该payload读取文件，按原 `deployment_manifest.json` 的 `files` 校验12个应用文件；当前开发目录中的新展示接口不进入原演示安装。安装器本身在当前源码目录维护，没有复制进payload。安装报告中的 `source` 记录实际选用的目录。缺失或校验失败会终止，不回退到开发目录。

未来获授权复现时，可以从当前仓库使用默认入口；也可用 `--source /path/to/frozen-checkout/robot/dofbot` 明确指定一份独立冻结检出。`--source` 目录须直接包含全部15个文件，沿用同一文件名列表、校验和环境检查，不会放宽原安装要求。隔离演练示例：

```bash
python robot/dofbot/install.py --staging-root /tmp/dofbot-install-review
python robot/dofbot/install.py --source /path/to/frozen-checkout/robot/dofbot --staging-root /tmp/dofbot-install-review
```

正式VM环境、外部依赖和启动流程见 [当前说明](../../robot/dofbot/README.md)。本目录不包含模型、厂商SDK、分类音频、完整VM或新PS/PL服务；这些依赖的来源与许可仍见 [THIRD_PARTY.md](../../THIRD_PARTY.md)。现有部署不因保存payload或修改安装源选择而更新。

`payload/README.md` 是保留原字节的历史快照，其相对链接按原 `robot/dofbot/` 位置解释，原安装脚本也不在payload内。阅读历史内容请使用上面的固定提交链接；不要把该快照当作当前仓库的新安装入口。

2026-10-30仅复制Git原始字节并核对路径、清单、Git blob和SHA256，修改安装器与测试源码；没有执行安装器、导入工程、测试或设备流程。历史运行与验证结论仍属于原版本。
