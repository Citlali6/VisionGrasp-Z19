# 小亚智分：配置选择与复现入口

先选择实际配置，再准备环境。下面所有安装/构建/运行命令供未来使用者按各配置执行，本次收尾没有运行。

| 配置 | 源码与复现方式 | 使用条件 |
|---|---|---|
| 现用VM/DOFBOT固定工位演示 | 下文冻结提交 `8a2a6fd544cb6b79e868b8a710dc34b6027c6c8d`；使用原安装器/启动器 | 原Ubuntu22.04/ROS2/SDK/模型/音频环境；保留现场配置 |
| 原Z19颜色/语音/网格 | [颜色工程](../fpga/color_locator/README.md)、[网格](../fpga/color_locator/GRID.md) | 该profile自己的镜像/地址/环境，独立于演示 |
| 四功能源码profile | [system_pspl](../fpga/system_pspl/README.md) → [PS软件](../host/app/perception/README.md) → [VM新入口](../robot/dofbot/PSPL.md) | 新XSA/镜像/UIO、合法模型契约、目标依赖/相机标定等；源码未联合运行 |

收尾候选分支为 `source/track33-closeout-20261030`。它含可选新展示所需的接口扩展；原 `deployment_manifest.json` 保持2026-10-29字节基线，安装器仍严格核对。因此候选文件不能冒充该冻结安装包，下面的旧演示安装需单独检出指定提交。不要修改清单掩盖版本差异，也不要把新入口覆盖到现用VM。

## 冻结演示的适用环境

- Ubuntu 22.04、ROS 2 Humble，使用已验证的 yahboom 配套虚拟机和普通桌面用户。
- 配套机械臂 SDK、识别源码/模型、中文音频及逆解服务已安装。
- Python 3、PyQt5、OpenCV、pyserial、mpg123、PulseAudio 与 ROS 依赖可用。
- 外部文件路径与校验值见[依赖清单](../robot/dofbot/external_dependencies.json)，项目文件基线见[部署清单](../robot/dofbot/deployment_manifest.json)。

本仓库提供应用源码与部署入口，不提供完整虚拟机或从空白 Ubuntu 安装全部厂商环境的脚本。不要将 Windows Python 环境复制到虚拟机。

## 首次从仓库安装

```bash
git clone --depth 1 https://github.com/Citlali6/VisionGrasp-Z19.git
cd VisionGrasp-Z19
git fetch origin 8a2a6fd544cb6b79e868b8a710dc34b6027c6c8d
git checkout --detach 8a2a6fd544cb6b79e868b8a710dc34b6027c6c8d
bash robot/dofbot/install.sh --check
bash robot/dofbot/install.sh
```

预检核对项目文件、依赖和运行状态。安装生成启动/停止脚本及桌面入口，不启动程序、不连接串口、不加载 FPGA，也不调整音量；运行中的应用会阻止覆盖。更新前先等任务完成，再使用停止入口退出。

维护者可通过 `--staging-root PATH` 验证隔离安装布局；该模式不操作真实桌面或运行环境。详细行为见[组件说明](../robot/dofbot/README.md)。

## 每次重新上电

1. 给机械臂上电，启动虚拟机并登录 Ubuntu 桌面。
2. 在 VMware「虚拟机 → 可移动设备」中连接机械臂 USB、语音 USB、摄像头与 USB 声卡，具体设备见[硬件连接](HARDWARE.md)。
3. 双击桌面 **启动垃圾分拣 · 实时展示**，或执行：

```bash
bash ~/启动垃圾分拣.sh
```

显示就绪后可按回车关闭启动终端，保留虚拟机和桌面会话运行。F11 切换展示窗口全屏。

## 一轮分拣

将物块放到已验证的固定拾取位置并移开手，说 **“你好小亚”**；等 **“在的”** 回应后，再说 **“开始垃圾分拣”**。

程序准备观察姿态，识别稳定目标，先播报物品/类别，再执行抓取投放。完成后必须重新唤醒才能开始下一轮。任务期间说出的新命令不会在本轮结束后补执行。未找到稳定目标时本轮结束，不启动抓取。

界面显示实时图像、识别物品、投放类别、语音事件和动作指令阶段。语音模块输出命令编号，因此记录不是麦克风逐字转写；播报文案依据现有音频映射。原声中的“有毒/湿/干垃圾”分别对应界面的“有害/厨余/其他垃圾”。

## 停止与检查

```bash
bash ~/停止垃圾分拣.sh
bash ~/启动垃圾分拣.sh status
bash ~/启动垃圾分拣.sh check
```

关闭展示窗口只关闭显示，后台仍可响应语音；再次运行启动命令会打开或激活同一个窗口。停止入口在动作进行中会要求等待本轮完成，不强制中断动作。

默认应用目录为 `/home/yahboom/codex_voice_sorting_20261029`，运行记录位于其 `records` 子目录。重复启动不会产生第二份控制程序。

## 常见情况

| 表现 | 检查方式 |
|---|---|
| 提示设备缺失 | 确认 USB 已连接到虚拟机，而非 Windows 主机 |
| 设备被占用 | 退出同一设备上的其他控制服务或 Jupyter 程序，再启动 |
| 没有播报 | 检查 C-Media 声卡已透传、Ubuntu 已登录、声音未静音 |
| 窗口离线或画面过期 | 查看终端提示、`records/runtime.log` 与 `records/dashboard.log` |
| 唤醒后过久再说启动无效 | 重新唤醒，并在回应后及时说启动口令 |
| 识别超时 | 检查物块位置、标签朝向、光照和遮挡，保持原有标定与相机位置 |

演示时 USB 声卡曾设置为 **75%**；这是现场配置记录，安装器不会覆盖用户音量。机械臂动作阶段表示已下发指令的进度，不能代替传感器对实际夹持或投放结果的确认。
