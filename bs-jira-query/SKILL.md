---
name: bsq-jira-query
description: "使用 bsq-jira CLI 工具管理、查询 Jira 任务。当需要了解项目任务、查找 Bug、记录处理备注、更新任务进度或修改任务状态时触发此技能。"
---

# 🔧 bsq-jira CLI 技能说明 (查询增强版)

## 🎯 何时触发此技能？
当你遇到以下场景时，请主动调用此技能：
1. **查阅需求与任务**：用户要求你根据某个 Jira 任务（如 `YLZHXT-1234`）的描述来写代码或了解背景。
2. **跟进问题与 Bug**：用户让你去 Jira 看看有没有某个报错的已知 Bug，或者看看分配给自己的任务。
3. **获取业务附件**：需要从 Jira 任务中下载前置的 Excel、设计图、日志等附件资源。
4. **管理与流转任务**：用户要求你更新任务标题、经办人，追加处理备注，或者推动任务状态（如流转至“开发中”或“已完成”）。

---

本系统已预装并配置好 Jira 命令行工具 `bsq-jira`，已完成认证，无需再次登录，你可直接调用。

## 📍 执行路径

请直接使用命令 `bsq-jira`。

**如果遇到命令未找到 (command not found)：**
1. 可能是环境变量 PATH 未加载完全，你可以先尝试使用相对路径：`~/.local/bin/bsq-jira`
2. 如果该路径下也没有，说明当前环境未安装此工具。**你需要主动使用 pipx 在线静默安装它**，执行以下命令：
   ```bash
   pipx install "git+ssh://git@gitee.com/IrisPaoPao/bs-project-tools.git#subdirectory=bs-jira-cli"
   ```
   *(安装成功后，配置和登录状态将自动复用，你可以直接继续后续查询)*

---

## 🔎 核心功能能力

### 1. 搜索 Issue (`search`)

你可以使用原生的 JQL 语句进行查询，或者使用用户预设的高效别名。

**用法 1：使用预设别名（推荐）**
用户已经配置了复杂的 JQL 别名，在查询前加 `@` 即可直接调用。别名也支持尾部拼接其他过滤条件。
```bash
# 查询当前用户的所有需求
bsq-jira search @我的需求当前

# 查询已修复的 Bug
bsq-jira search @已修复bug-59

# 查询所有开发及经办任务
bsq-jira search @my-all
```

**用法 2：利用原生选项组合**
```bash
# 查询分配给我的、状态为打开的任务
bsq-jira search --assigned-to-me --open
```

### 2. 查看 Issue 详情 (`issue show`)

当你获取到具体的 Issue Key（如 `YLZHXT-11299`）后，你可以用 `show` 命令查看任务所有的上下文。

```bash
bsq-jira issue show YLZHXT-11299
```

**说明：**
输出内容包含但不限于：
- 状态、优先级、摘要
- 经办人、报告人、修复版本
- **附件列表**（含附件真实下载 URL 和文件大小）
- 完整的需求/Bug描述文本

### 3. 修改与流转 Issue (`update` / `transition` / `assign`)

如果用户明确要求你更新任务进度或修改任务基本信息，可以使用以下命令：

**更改任务状态 (工作流流转)：**
```bash
# 查看某个任务当前可以流转到哪些目标状态
bsq-jira issue transition YLZHXT-1234 --list

# 执行流转（必需严格按照 --list 中出现的目标状态名称填写）
bsq-jira issue transition YLZHXT-1234 --to "开发中"
bsq-jira issue transition YLZHXT-1234 --to "已完成" --comment "已修复相关问题"
```

**更新基础信息：**
```bash
# 更新摘要或描述
bsq-jira issue update YLZHXT-1234 --summary "新标题" --description "补充描述"

# 更新经办人和优先级
bsq-jira issue update YLZHXT-1234 --assignee "zhangsan" --priority "Highest"
```

**一键指派：**
```bash
# 快捷指派给某个特定人员
bsq-jira issue assign YLZHXT-1234 zhangsan
# 指派给自己 (不接名字默认指派给自己)
bsq-jira issue assign YLZHXT-1234
```

### 4. 查看别名库 (`alias list`)

如果你不确定当前可用的别名，可以一键查询所有别名配置：
```bash
bsq-jira alias list
```

### 5. Jira 备注规范与开发完成收尾

当用户要求“备注处理方案”“记录修复过程”或“开发完成”时，必须先执行 `issue show` 核对任务上下文，再准备备注。备注不得只写“已修复”或只放提交号，至少覆盖以下六类信息；不适用的项目要明确写“无”：

1. **数据库脚本**：是否有脚本；有则写脚本路径/名称和涉及版本，无则写“无”。
2. **微服务与版本**：涉及的微服务、仓库分支、构建版本或发布 tag。
3. **业务功能模块**：具体业务模块、接口或页面范围。
4. **第三方接口**：涉及的外部/第三方接口及调用影响，无则写“无”。
5. **配置项**：新增或调整的配置键及生效范围，无则写“无”。
6. **关键改造**：根因、处理步骤、边界条件和兼容性说明。

建议同时补充可追溯的提交号、测试/联调/部署验证结果和遗留限制。推荐备注结构如下（按实际情况删减，不得编造字段或结果）：

```text
处理方案：
- 根因：...
- 关键改造：...
- 数据库脚本：无 / <路径或脚本名>（<版本>）
- 微服务/版本：<服务>，<分支或 tag>
- 业务功能模块：...
- 第三方接口：无 / ...
- 配置项：无 / ...
- 提交：<commit>
- 验证：<测试、真实接口响应、部署验证或未验证原因>
- 遗留限制：无 / ...
```

若用户要求将任务标记为开发完成，严格按以下顺序执行：

1. `bsq-jira issue transition <KEY> --list`，确认可用的目标状态名称。
2. 使用列表中的精确状态名执行 `bsq-jira issue transition <KEY> --to "开发完成" --comment "<完整处理备注>"`；若实际目标状态不是“开发完成”，以列表返回值为准。
3. 再执行 `bsq-jira issue show <KEY>`，复核状态和备注是否已写入，并在最终回复中报告复核结果。

只要求追加备注、不要求流转状态时，不要擅自执行 `transition`；使用 `bsq-jira comment add <KEY> --body "<完整处理备注>"`，然后用 `bsq-jira comment list <KEY>` 复核写入结果。如需删除错误或冗余的评论，可使用 `bsq-jira comment delete <KEY> <COMMENT_ID> [-y]`（也支持别名 `rm` / `remove`）。

---

## 📝 Agent 行为准则与最佳实践

1. **不要猜测 Issue Key**：如果你需要找某个任务，必须先通过 `search` 或别名拉取列表。
2. **安全、高效地获取附件资源**：在读取 `issue show` 的输出时，注意观察“附件”区块。
   - **严禁**：切勿尝试启动基于浏览器的工具（Browser）去下载，也尽量避免原生使用 curl（会丢失登录态）。
   - **唯一推荐做法**：直接使用原生下载命令：`bsq-jira attachment download '<附件URL>' --dest-dir ./`，它会自动处理 Cookie 与中文文件名。
3. **复用别名机制**：在使用 `search` 时，尽可能使用 `@别名`，因为其中已经封装了项目 Key（YLZHXT）和各种特定的中文字段，能极大避免 JQL 拼写错误。
4. **组合查询**：别名支持组合，如需指定版本可以拼接：`bsq-jira search "@我的需求当前 AND affectedVersion = 'V2.0.3.7'"`。
5. **🔐 登录异常处理**：如果执行任何命令时遇到“未配置”、“凭据过期”或要求重新登录的报错，**请立即停止操作，并在回复中提醒用户**：“发现您的 Jira CLI 未登录或凭据失效，请您亲自在终端中运行 `bsq-jira config init` 完成配置。”（因为涉及到安全密码输入，Agent 不可代为执行）。
6. **任务创建规范**：创建任务时，项目统一且**只能创建到 59-医疗智慧协同**（项目 Key 为 `YLZHXT`），严禁创建到其他项目（如 53、38 等）。经办人默认填入当前登录用户。
