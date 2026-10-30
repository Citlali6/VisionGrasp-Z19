# 发布范围、历史引用与恢复清单

本页汇总2026-10-30收尾时的文件、分支和PR处置，不把Git清单或备份核对称为工程运行验证。起始远端 `main=8a2a6fd544cb6b79e868b8a710dc34b6027c6c8d`；继承四功能源码 `7cf7513a42d5b5f3b3c66eec1e950786b6478b83`，在独立 `source/track33-closeout-20261030` 收尾。新的报告和导航不替换现场程序。

## 文件与配置分层

| 类别 | 保留入口/来源 | 本轮处置 |
|---|---|---|
| 产品与四功能主线 | [产品首页](../../README.md)、[PS/PL聚合工程](../../fpga/system_pspl/README.md)、`fpga/perception_v2/`、`fpga/audio_frontend/`、`host/libpspl/`、`host/app/perception/` | 作为当前技术入口；PS CPU承担垃圾语义/ASR，PL承担像素/PCM和候选规则；默认语义模式不要求绿色 |
| 现用演示基线 | [DOFBOT](../../robot/dofbot/README.md)、[部署清单](../../robot/dofbot/deployment_manifest.json)、[原现场记录](../VALIDATION.md) | 原串口语音、固定拾取、播报完成后动作、UI与环境保留。原安装器使用匹配部署清单的 `8a2a6fd` 检出；新可选入口与展示不能冒充原冻结安装文件 |
| 共享依赖/BSP/第三方 | `fpga/color_locator/vendor/laperex/`、`fpga/scripts/alinx/`、[第三方说明](../../THIRD_PARTY.md) | HSV源码/来源/许可和Z19 PS配置仍被当前工程引用；不因旧名称删除或改归属 |
| 历史独立硬件profile | [颜色链](../../fpga/color_locator/README.md)、[MIPI工程](../../fpga/camera_hw/README.md)、[裸机相机](../../fpga/camera_baremetal/README.md)、`deliverables/`、原门控[验证索引](../../fpga/sort_guard/validation/README.md) | 保留原工具版本、地址、产物、哈希与结果；降为明确的独立配置入口，不能拼成新四功能镜像或新性能结论 |
| 已退出产品路线 | 旧 `pc/`、RoArm、MuJoCo、MJC1/HIL、SCS/灵巧手相关旧分支 | 当前发布树不恢复整套旧应用。提交、PR、已有恢复引用和仓库外bundle保留；关键词命中不等于可删除 |
| 用途未决/仍在工作 | 其他工作树的未提交内容、未纳入当前主线的独有提交 | 保留原树和分支；不自动stash、reset、搬迁、部署或把他人修改混入收尾 |

`ah_camera0`、`/dev/ah_camera0`、`/opt/amazinghand` 和 `/var/lib/amazinghand` 是已有驱动/设备/部署兼容标识；保留其技术含义，不全仓替换。中文桌面入口属于现用部署产物，与公开仓库文件命名分开判断。

## 分支/PR盘点与动作边界

收尾开始读取实际远端41个heads、20个本地分支、15个工作树；本地远端跟踪SHA与 `ls-remote` 一致。[完整远端清单](branch_inventory.csv)逐行给出SHA、相对main的关系、patch-equivalence、当前仓库PR和是否被工作树使用，不包含个人目录或未提交文件内容。清单是删除前快照；后续正常推送收尾分支会新增交付head，不应据此误报原分支已清理。

`ahead_main` 是未被main祖先关系包含的提交数；`patch_unique/patch_equivalent` 是 `git cherry` 对非merge提交的补丁比较，不等于功能独有/已经集成判定。没有当前仓库PR号的分支不冒配上游旧PR身份。

| 盘点分类 | 远端数 | 处置 |
|---|---:|---|
| main / 当前四功能源码 | 1 / 1 | 保留；main正常整合前不移除源码交付分支 |
| 同名分支仍绑定工作树 | 5 | 全部保留，包含PR34；清洁工作树也不自动拆除 |
| 已为main祖先、无工作树 | 16 | 内容冗余已确认；远端分支命中现有CI的push过滤，暂缓删除 |
| 补丁等价、无工作树、命中CI过滤 | 4 | 保留原历史；不以API/UI删除绕过触发风险 |
| 非祖先且仍有不同补丁、无工作树 | 13 | 已备份，保留待来源/用途审阅，不批量合并旧路线 |
| `plan`：一个补丁等价提交、无工作树 | 1 | 建立恢复标签后仍保留远端head，不试验分支删除事件 |

当前唯一工作流 `ci.yml` 对PR及指定分支push执行软件检查和FPGA仿真。GitHub文档说明分支删除的push事件涉及默认分支SHA回退；因此远端清理不能仅靠“分支已合并”判断是否符合本轮禁跑约束。[push事件说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#push)、[分支/标签过滤说明](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)。本轮不修改CI/保护，也不发PR触发运行。

以下4条本地引用已逐条核对SHA、main祖先关系及没有工作树使用后，以 `git branch -d` 删除；再次读取本地引用确认均已不存在。其远端heads继续保留：

| 本地分支 | 删除前SHA |
|---|---|
| `chore/workspace-cleanup-20261021` | `9c0acde74d659ecb44ab9b75fad5db99dd83de20` |
| `feature/pc-demo-issue18` | `24fc34d610046bcb74efd61026d9227532a9870c` |
| `feature/pc-sdk-issue14` | `5ee9936a30ca913ef8a0438c1e7272cb943b5677` |
| `feature/roarm-r0-onsite-query-issue30` | `7b1163ed8ad734f5bf0ba31aaf4ac18291935273` |

`plan@e625341676c83495b3fb225b31064b3fcf1fbb18` 的补丁ID `0b884b6e5dc8ce360e96e7dbd4290b312960aa79` 与main中的 `2835603a895881c8ecb43eaef991634eb76ac74e` 相同；提交身份仍不同。已建立并正常推送注释标签 `archive/20261030/plan`，标签对象 `86743168741c8b35eb7084227b3dff15fe95e3d8`，远端解引用仍为上述原提交。推送前重新核对plan的远端SHA及标签无冲突，目标提交不存在工作流；当前CI只配置分支push过滤，没有标签、create或delete触发。本次归档标签1个、本地删除4条、远端heads删除0条；plan的远端head继续保留。

## PR34保留的价值与当前状态

只读核对当前仓库20个PR：19个已关闭且合并，只有[PR34](https://github.com/Citlali6/VisionGrasp-Z19/pull/34)仍为open draft。已关闭/已合并PR保持原历史，不删除评论或改写为新路线。PR34的唯一新增提交为 `2631240f2b6dd26181ce539b25f655624e22c9b4`；其工作树还有2个已跟踪修改和1个未跟踪文件，故保留PR及分支，不能因当前产品不用RoArm就推定这些工作无价值或无人继续。

可提炼的经验已有固定来源，供Skill引用，不把旧 `pc/` 恢复为当前应用：

- [独立检查点方法](https://github.com/Citlali6/VisionGrasp-Z19/blob/2631240f2b6dd26181ce539b25f655624e22c9b4/pc/visiongrasp/vision/measurement.py)：拟合点与至少5个检查点分离，检查中心/边缘覆盖、重复点，并记录逐点和mean/RMS/max误差；图内检查不自动成为外部精度。
- [相机操作卡](https://github.com/Citlali6/VisionGrasp-Z19/blob/2631240f2b6dd26181ce539b25f655624e22c9b4/docs/lab/2026-10-22/ISSUE33_CAMERA_CARD.md)：实际量尺、固定相机/裁切/焦距、冻结帧、像素与板面坐标、畸变和物块高度视差分别记录；设计尺寸不当实测。
- [桌面→基座预览](https://github.com/Citlali6/VisionGrasp-Z19/blob/2631240f2b6dd26181ce539b25f655624e22c9b4/pc/visiongrasp/vision/robot_base.py)：刚体映射、工具参考偏移及误差预算只产生计划预览，保持 `robot_xyz_mm=None` 与无运动许可；不外推为新系统抓取坐标。

7份相关源码/操作卡已另存仓库外小型静态ZIP并逐一核对Git blob；旧报告中的测试/失败仍归旧版本，本轮没有重跑。

## 恢复材料与未提交工作保护

恢复材料位于所有者本机的仓库外“验证记录/track33-closeout-20261030/branch_inventory”目录，不公开上传原始bundle、个人路径CSV或工作树备份。

| 恢复材料 | 内容与核对 |
|---|---|
| `refs_pre_cleanup.bundle` | 77个引用、完整历史；256,437,345 B；SHA-256 `81907317206a5b2f26c0e8b0a9f5f5301b7f85d25ba661241daec1102722e2f1`；`git bundle verify` 返回0且报告complete history；可达缺失对象为0 |
| `refs_before.csv`、`remote_branches_inventory.csv`、`local_branches_inventory.csv`、`worktree_inventory.csv` | 本地/远端引用、完整SHA、祖先/补丁关系、工作树及处置条件；用于后续恢复和删除前再次比较 |
| `dirty_worktrees/`及两个backup manifest | 9个既有脏工作树的382份未跟踪文件、48份跟踪文件快照，以及各树的working/index二进制patch和原status；复制文件与来源SHA-256一致。包含issue36已有暂存修改 |
| `pr34_useful_static_sources.zip`及 `pr34_static_manifest.csv` | 7份固定版本资料；18,370 B；SHA-256 `1b8f7e9bdb57f5fa098b2ebfae7c358a9a082d2e6a7a33b3c406e892a90be0b2` |
| `pr_states.json`、`backup_files_sha256.csv` | PR状态读取与备份文件大小/哈希清单；不作为运行结果 |

Bundle保护提交和引用，不能替代未提交文件备份。新收尾工作树自己的正在编写文件不混入上述旧工作备份。被忽略的构建/历史输出目录未复制，其原目录完整保留；旧深层输出有长路径警告，不宣称扫描或备份了全部ignored产物。

需要恢复时，先核对bundle哈希，再使用 `git bundle list-heads` 找到原引用；在独立恢复仓库/分支取回目标SHA。未提交内容按对应HEAD、index patch、working patch及原文件快照恢复，保留原暂存/未暂存区别。不要将备份整体覆盖现场部署或当前收尾工作树。

## 文件命名清单

在起始 `7cf7513a` 的379个跟踪路径中，68个路径含大写，中文和空格路径均为0；完整逐项清单保存在仓库外 `filename_inventory.csv`。按用途分为20个工具/仓库入口、22个第三方/BSP/相机兼容路径、7个冻结证据入口、19个已有交叉引用文档/构建入口。本轮新建普通文档采用小写英文；不为排版批量改工程、产物或厂商内部标识。

指南的命名文字要求与其 `README.md` 示例存在差异。保留 `README.md`、`AGENTS.md`、`LICENSE`、`CMakeLists.txt`、`Makefile` 及技能格式要求的 `SKILL.md` 是工具/引用兼容选择，不宣称赛方已给予额外豁免。下列19个已有项目文档/构建入口继续保留原名与链接：

```text
CONTRIBUTING.md
docs/ARCHITECTURE.md
docs/DEVELOPMENT.md
docs/GIT_WORKFLOW.md
docs/HARDWARE.md
docs/QUICKSTART.md
docs/VALIDATION.md
docs/competition/DESIGN_DETAILS.md
docs/competition/EVIDENCE_MATRIX.md
docs/competition/MATERIALS.md
docs/competition/TECHNICAL_OUTLINE.md
docs/voice/USB_MICROPHONE.md
fpga/color_locator/BOARD.md
fpga/color_locator/GRID.md
fpga/color_locator/VOICE.md
fpga/sort_guard/INTERFACE.md
fpga/system_pspl/PR_BODY.md
host/camera_linux/Makefile
robot/dofbot/PSPL.md
```

另外49项由上述分类和原清单逐项保留：各层README、LICENSE/来源文件，以及相机工程中的 `QSFP.xdc`、`AXI_BayerToRGB`、`AXI_GammaCorrection`、`LineBuffer.vhd`、`StoredGammaCoefs.vhd` 及对应XCI/XGUI路径。其名称可能被IP元数据、脚本或冻结哈希引用，未获得重建依据时不重命名。历史中文附件曾存在于旧提交，但未出现在本次起始跟踪树中，不为制造“清理完成”重新写入或删除历史。

本轮允许的质量工作限于Git元数据/补丁关系、复制/哈希、路径/文本和接口审阅。没有执行工程程序、测试、模型、滤波系数、仿真、编译、工具链、设备或现场部署。


## 本轮发布与 main 状态

本轮小修提交为 `0aa5adc6917d58b4a50d9e93d375d28d5b2f9a1e`：默认 `semantic_bbox` 不再复制掩码/清零ROI或调用颜色连通分析，返回稳定 `not_requested/semantic_bbox_policy`；显式颜色模式及完整PL数据读回/校验保留。消费者只在颜色模式要求 `associated`，默认分支字段兼容。

收尾分支继承原四功能的2个返修提交及全部有效源码，新增产品导航、七项报告、四项Skill、真实AI开发案例和发布清单。旧PR34的独立检查点/坐标预览经验以固定提交引用及私有静态副本保留，不移植旧整套pc应用。其余独有分支不未经判断全量合并。

只读查询得到main保护 `enforce_admins=true`、所需批准数0、`required_status_checks=null`，仓库rulesets为空；这不是“没有保护”，也不虚构必需检查。有效 `.githooks/pre-push` 和默认hooks中的同内容钩子只阻止直推main，不运行工程检查。本轮没有改钩子、CI或保护。唯一active工作流为 `.github/workflows/ci.yml`，全部PR触发软件测试与FPGA仿真，main push同样触发；这与本轮禁跑约束冲突。因此不创建收尾PR、不更新PR34、不合入main。main仍为起始完整SHA。最终收尾提交以Git交付分支和提交manifest记录的内容快照为准。

### 待条件满足后使用的 PR 正文草稿

标题：`小亚智分：3.3初级组参赛材料与四功能源码收尾`

> 固定工位分拣作品缺少统一的产品与技术入口，且默认语义候选仍做不必要的颜色关联。本变更继承四功能源码，移除该冗余调用，以产品首页、配置矩阵、七项报告、四个Skill及证据索引组织参赛交付。
>
> PS负责采集/CPU模型/坐标/ASR，PL负责像素/音频/候选规则，VM保留原固定工位动作。现用演示安装固定至8a2a6fd；新源码独立配置，不改冻结哈希或现场部署。已有结果保持原版本和条件。
>
> 审阅范围为源码、消费者接口、文件引用、哈希及Git元数据；按用户禁跑要求未执行测试、仿真、编译、工具链、模型、设备或CI。新profile的模型、目标环境、镜像/UIO、标定、ASR及联合结果仍为条件，详见manifest和要求映射。
>
> 本正文未在GitHub创建PR，合并前须解决自动执行检查与禁跑约束的冲突，并遵守实际保护规则。

后续可讨论将文档/文本检查与运行类验证分层、工程仿真显式触发，并使required checks对应真实内容；这是需单独决定的建议，本轮未激活、未制造成功状态。
