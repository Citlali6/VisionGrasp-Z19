# 相机实测证据

这些 JSON 保存各项实际测试指标，不含原始图像或凭据。

| 文件 | 证据范围 |
|---|---|
| `hd-stream-guard30-validation-20261010.json` | PC 30 秒高清接收；每张 JPEG 解码及 1920×1080 尺寸检查，757 个不同帧、25.16 fps |
| `camera0-hd-fault-validation-20261010.json` | 高清版本 SIGSTOP/SIGCONT/SIGKILL、stale/503、停止/重启及 DMA halt |
| `camera0-linux-10min-validation.json` | 600 秒原采集，599 条每秒样本；错误/空样本/hash 与正常退出 |
| `linux-camera-deployment.json` | 最终部署时源文件/ELF/模块 hash，另一次正常 60 秒采集指标与后续事项 |

部署清单中的 README hash 指部署当时的板端副本；交付时补充了本仓库文档入口，
其余已验证 Linux 程序源码未修改。仓库 `validated/` 二进制与该清单一致。
高清接收测试有复制/忙碌丢弃计数；没有缺失已发布序号不代表没有丢弃采集帧。
正常 60 秒测试的零丢弃不能覆盖其他测试时段。VDMA 轮转次数也不是无丢帧传感器 FPS。
原始实验日志、图像及诊断文件保留在本机 `tmp/z19-linux-camera-20261010` 与板端持久日志目录。
