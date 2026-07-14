---
name: bsq-jira-query
description: "使用 bsq-jira CLI 工具查询、获取 Jira 任务详情和列表（仅含查询功能）。当你需要了解项目任务、查找 Bug 或阅读需求时触发此技能。"
---

# 🔧 bsq-jira CLI 技能说明 (查询增强版)

本系统已预装并配置好 Jira 命令行工具 `bsq-jira`，已完成认证，无需再次登录，你可直接调用。
**该技能仅限于“只读查询”操作**（如搜索任务、查看详情），禁止使用修改状态或分配等写操作命令。

## 📍 执行路径

请直接使用命令 `bsq-jira`。如果遇到命令未找到(command not found)的情况，可能是因为用户的环境变量 PATH 未加载完全，你可以直接使用软链接的相对路径：
`~/.local/bin/bsq-jira` 或 `$HOME/.local/bin/bsq-jira`

---

## 🔎 核心查询能力

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

### 3. 查看别名库 (`alias list`)

如果你不确定当前可用的别名，可以一键查询所有别名配置：
```bash
bsq-jira alias list
```

---

## 📝 Agent 行为准则与最佳实践

1. **不要猜测 Issue Key**：如果你需要找某个任务，必须先通过 `search` 或别名拉取列表。
2. **关注附件资源**：在读取 `issue show` 的输出时，注意观察“附件”区块。如果需要分析日志或 Excel 数据，可以直接从那里提取下载链接使用 Python 或 curl 进行下载。
3. **复用别名机制**：在使用 `search` 时，尽可能使用 `@别名`，因为其中已经封装了项目 Key（YLZHXT）和各种特定的中文字段，能极大避免 JQL 拼写错误。
4. **组合查询**：别名支持组合，如需指定版本可以拼接：`bsq-jira search "@我的需求当前 AND affectedVersion = 'V2.0.3.7'"`。
