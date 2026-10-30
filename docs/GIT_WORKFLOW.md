# Git 与发布工作流

唯一开发仓库是 `Citlali6/VisionGrasp-Z19`。`main` 是经过检查的公共基线，所有更新通过 PR 合并。

## 开始工作

```bash
git remote get-url origin
git status --short
git branch --show-current
git fetch origin
git worktree add -b feature/your-change ../visiongrasp-your-change origin/main
```

核对远程指向正确仓库后，在新工作树进行修改。原工作树的未提交内容、旧分支和归档保持不动。避免复用一个含他人修改的目录来完成无关任务。

启用当前克隆的本地保护钩子：

```bash
git config --local core.hooksPath .githooks
```

钩子拒绝直接更新远程 `main`；它是本地误操作保护，不能替代 GitHub 分支规则。

## 提交与 PR

按当前任务授权选择检查，审阅 `git diff`、未跟踪文件和暂存差异。当前源码发布阶段禁止运行测试/仿真/编译等流程；经所有者单独批准，PR/main自动CI仅做标准Git文本、路径和冻结来源核对，原运行类CI保留手动且本轮不触发。以后获得运行授权时再执行相关检查并保留真实结果。只暂存本任务路径，使用聚焦提交，推送同名分支后正常创建以 `main` 为目标的 PR。

PR 说明应让未参与对话的读者理解：原问题、最终行为、涉及模块、验证结果和未覆盖的限制。文档清理不能改写旧实测结果；功能与依赖变化必须说明。

## 合并

检查目标分支、最终差异、冲突状态与所有适用检查后，由有权限的维护者通过 PR 合并。项目允许零强制外部审批；欢迎代码审阅，但不能虚构已经发生的 Review/Approve。自动化代理需有当前任务中的合并授权；已有授权不需重复索取。

不直接推送 `main`，不强推，不重写历史，不自动删除远程分支、旧 Issue 或 PR。不要使用 `--no-verify`、更换远程或修改保护规则绕过限制。仓库发布与硬件部署是独立操作：合并本身不授权机械臂运动、FPGA 加载或覆盖现用虚拟机。
