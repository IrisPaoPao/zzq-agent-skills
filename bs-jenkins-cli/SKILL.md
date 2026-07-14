---
name: bs-jenkins-cli
description: 触发条件：当用户要求触发 Jenkins 构建、查看 Jenkins 任务列表、检查 Jenkins 构建状态，或执行任何与 tax-jenkins 和 saas-jenkins 相关的操作时，请激活并使用此技能。
---

# Jenkins CLI 能力指南

你拥有调用本地 Jenkins CLI (`bsq-jenkins`) 工具来管理和触发 Jenkins 任务的能力。
通过这个能力，你可以在不打开浏览器的情况下，直接在终端中触发构建、查看任务状态和获取任务列表。

## ⚠️ 自动安装指南

如果你在终端中运行 `bsq-jenkins` 时提示 `command not found`，说明该环境尚未安装此工具。
**请主动使用 pipx 进行全局安装**，安装命令如下：

```bash
pipx install -e /Users/zhangzhengqing/work/project/bs-project-tools/bs-jenkins-cli --force
```

安装完成后，工具将全局可用。

## 🔧 配置文件说明

该工具依赖配置文件 `~/.bsq-jenkins.json`，如果运行命令时提示找不到配置文件，请提醒用户参考 `bs-project-tools/bs-jenkins-cli/config.example.json` 在其用户主目录下创建该文件并填入 Jenkins 的账号密码。

## 🚀 核心命令用法

默认情况下，命令在 `saas-jenkins` 上执行。你可以使用 `-s` 参数指定服务器，如 `-s tax-jenkins`。

### 1. 查看任务列表 (`jobs`)
```bash
bsq-jenkins -s tax-jenkins jobs
```
*这会列出指定服务器上的所有任务及其最新状态。*

### 2. 触发任务构建 (`build`)
```bash
bsq-jenkins -s tax-jenkins build <任务名称>
```
*命令默认会阻塞并等待 Jenkins 返回最终的构建结果（成功/失败）。*

**对于多分支流水线（Multibranch Pipeline）的重要提醒：**
在 Jenkins 中，多分支流水线的分支实际上是子任务（Sub-job）。**绝对不要使用 `-p branch=xxx` 的方式传参**。
你必须将路径直接拼接到任务名中：
```bash
# 格式：<主任务名>/job/<分支名>
bsq-jenkins -s tax-jenkins build tax-collect-server/job/1.9.19.7-SNAPSHOT
```

### 3. 查看最新构建状态 (`status`)
```bash
bsq-jenkins -s tax-jenkins status <任务名称>
```
*获取任务最后一次构建的详细信息、持续时间、触发原因等。*
