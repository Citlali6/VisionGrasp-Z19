# Z19 MIPI 相机快速操作

此入口用于已经部署验证相机环境的 Z19：FL0214/IMX214 相机 0、Linux `5.4.0-xilinx-v2020.2`、指定相机固件与 `ah_camera0` 驱动。它独立于 USB 颜色定位及 DOFBOT 相机。

## 启动板端预览

确认没有其他进程使用 PL/相机，核对[硬件产物](../../fpga/camera_hw/README.md)与[Linux 驱动要求](../../host/camera_linux/README.md)，在板端运行：

```sh
cd /opt/amazinghand/camera0-linux-hd-20261010
sh /opt/amazinghand/bin/load_z19_camera0.sh \
  /lib/firmware/amazinghand-camera-28e1e3e7-20261010.bin ./ah_camera0.ko
python3 start_preview.py
```

加载器会检查固件哈希、模块 ABI、活动使用者、时钟及相关 PS 接口。若检查不通过，先排除配置不一致，不绕过守卫。加载会改变当前 PL 配置，不能与颜色固件混用。

## 在电脑查看

从仓库根目录运行：

```bash
python host/camera_linux/view_camera.py
```

浏览器打开 `http://127.0.0.1:8766/`。工具固定转发至已验证地址 `192.28.14.153:9000`；`--port` 只调整电脑监听端口。若板卡地址不同，可用下面的直连方式，或审阅并修改转发工具中的目标地址。它转发相机 HTTP 接口，不更改电脑全局代理。网络可直达时，也可以打开 `http://YOUR_Z19_ADDRESS:9000/`。

当前预览是原生 **1920×1080 MJPEG**。页面支持全屏、状态及手动焦距 0–1023；焦距数值是执行器位置，不是自动对焦或距离测量。

## 关闭与再次启动

页面停止按钮结束采集；电脑转发程序按 `Ctrl+C` 关闭，板端服务仍可能存在。需要关闭板端服务时，按启动器输出核对进程身份并发送正常停止信号。服务会停止其拥有的采集进程、释放 DMA 缓冲；不要凭旧 PID 终止不相关进程。

相机模块名 `ah_camera0`、设备名 `/dev/ah_camera0` 与 `/opt/amazinghand/` 部署路径是兼容接口，保留这些名称不代表继续使用废弃手部应用。验证指标见[相机记录](linux_camera0_bringup.md)。
