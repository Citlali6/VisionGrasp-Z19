# Z19 Linux SD 基础

这些工具保存从既有 Z19 系统文件生成可核验启动/恢复包的方法，独立于 DOFBOT 虚拟机。完整系统镜像不随仓库发布，使用者需合法取得与下列 SHA-256 相同的原始文件。

| 输入 | SHA-256 |
|---|---|
| `BOOT.BIN` | `a1719b4dba5ea3520b9498e2063d557f4657e65cf8bf3ecfee72379445553b86` |
| `boot.scr` | `b3767ea01003c31baf90e3b1b541c7e385a5ab5db9952a9d07abbdec1b0d3eac` |
| `image.ub` | `e923606f9e5a428e7e76eb2b40a81415f474d041e980960220bcd2052fd978ad` |
| `rootfs.tar.gz` | `4f05d24af1b04d3490dde9d3526c4119b9d2e08752b2954c96cfe167f57ddf34` |

## 离线生成

使用 Python 3.11 或更新版本，将四个文件放在同一来源目录。输出选择尚不存在的新目录：

```bash
python tools/build_z19_sd.py --source /path/to/z19-inputs --output /path/to/new-sd-package
```

工具校验输入、解析 FIT/FDT 和启动脚本，生成 normal/recovery payload 及 manifest，不访问磁盘设备、不需要 VM。格式和路径测试位于 `tools/test_z19_sd.py`，Windows 准备流程替身测试位于 `tools/test_prepare_z19_sd.ps1`。

## 设备操作边界

`prepare_z19_sd.ps1` 为已经核验且已清空的指定 USB SD 卡设计，按序列号、容量、MBR、扇区大小和系统盘标识检查目标。`-WhatIf` 仅审阅步骤，但仍要求目标满足预检条件；它不是任意 SD 卡的通用烧录器。不能为绕过校验而随意替换设备身份常量。

真正分区、写卡、恢复根文件系统和板卡启动属于另行确认的现场操作；仓库安装和 CI 不执行它们。保留的 `host/scripts/` 包含 Linux 探测、根文件系统安装、恢复初始化及相机加载基础代码。运行前需阅读具体脚本并确认对应板卡、镜像和已有数据。

本次仓库整理仅保留源码与离线检查，不重新写卡或验证冷启动。当前相机的专用固件、设备名和驱动契约见[相机交付基线](camera_delivery_20261010.md)。
