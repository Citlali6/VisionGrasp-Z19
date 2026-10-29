# 相机交付基线 · 2026-10-10

仓库保留相机 0 实际使用的 FPGA 产物、源工程输入、Linux 驱动、采集/预览程序及精简实测证据。

| 内容 | 位置 |
|---|---|
| 原始工程、BD/XCI/XDC、依赖 IP | [fpga/camera_hw](../../fpga/camera_hw/README.md) |
| 逐文件来源和 SHA-256 | [硬件 manifest](../../fpga/camera_hw/manifest.json) |
| 已验证 `.bit` 与 `.xsa` | [validated](../../fpga/camera_hw/validated/) |
| 驱动、采集、预览、电脑转发工具 | [host/camera_linux](../../host/camera_linux/README.md) |
| 已验证模块和可执行文件 | [Linux validated](../../host/camera_linux/validated/README.md) |
| 运行指标、异常检查与部署哈希 | [证据索引](evidence/2026-10-10/README.md) |

相机 bit SHA-256：

```text
28e1e3e7963ff12f57848998cf2695dcca139c3f519c5f020daf90dec4dc35ae
```

同一 bit 经 Bootgen 转为 raw BIN 的 SHA-256：

```text
e25e9bc7fd4c2008c7a198a91bc4937716b333259d08da7ed777d8ffe9b3384b
```

源工程来自既有四路相机工程，要求 **Vivado 2020.2_AR75986**；版权、来源及上游 IP 声明保留。当前验证覆盖相机 0，未验收四路并发、自动冷启动或与当前机械臂联动。归档源码没有在本次仓库整理中重新综合，不能声称新构建产物与已验证 bit 等价。

操作入口见[相机快速操作](camera_quickstart.md)。本交付不包含完整系统镜像、原始图像、持续运行日志或访问凭据。
