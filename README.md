# zzq-agent-skills

张政卿 ([@IrisPaoPao](https://github.com/IrisPaoPao)) 个人维护的 Claude Code Skills 集合，面向内部 BS（百胜）开发工作流。

每个 skill 是一个独立子目录，包含 `SKILL.md`（必需）和可选的 `references/` `agents/` 等资源。Claude Code 会读取 `SKILL.md` 头部的 YAML frontmatter 决定何时触发，再按需加载子文件。

## 安装

### 安装单个 skill

```bash
git clone https://github.com/IrisPaoPao/zzq-agent-skills.git
cp -r zzq-agent-skills/<skill-name> ~/.claude/skills/
```

### 安装全部（符号链接）

```bash
git clone https://github.com/IrisPaoPao/zzq-agent-skills.git ~/.claude/skills-zzq
ln -s ~/.claude/skills-zzq/* ~/.claude/skills/
```

> 也可配合 [skillshare](https://github.com/anomalyco/skillshare) 跨工具同步（Claude Code、Cursor、OpenCode 等）。

下次开新会话，Claude Code 会自动加载并按 description 触发。

## 当前 skills

### 数据库脚本

| Skill | 用途 |
|---|---|
| [bs-database-script-generator](./bs-database-script-generator/) | 在 saas-database / tax-database 仓库生成 Groovy Flyway 迁移脚本（TDSQL + Oracle 双版本、命名规则、序号递增、SQL → Groovy 幂等包装、方言转换） |

### 菜单管理

| Skill | 用途 |
|---|---|
| [bs-menu-create](./bs-menu-create/) | 创建/新增运营平台菜单，按同级数据生成纯 SQL，支持分类菜单、叶子菜单、按钮权限、多模板和重复检测 |
| [bs-menu-export](./bs-menu-export/) | 从运营平台 dev-operations 库导出已存在菜单的 auth_temp_* 全链路脚本 |

### 数据网关

| Skill | 用途 |
|---|---|
| [bs-gateway-scene-sql-generator](./bs-gateway-scene-sql-generator/) | 在 saas-data-gateway 仓库由 groovy 采集脚本生成场景注册 SQL（gwb_scene + gwb_scene_capacity_relation + gwb_context_param），含库内最大 scene_id 查询与工作区预定号扫描的 pre-flight 校验 |
| [bs-gateway-dirty-data-cleaner](./bs-gateway-dirty-data-cleaner/) | 数据网关 saas-data-gateway 采集任务脏数据清理 + 重采进度重置（TDSQL 逻辑表名路由、删除顺序 item→session→batch→data→index、雪花 id 精度陷阱） |

### 对账数据

| Skill | 用途 |
|---|---|
| [bs-reconciliation-data-cleaner](./bs-reconciliation-data-cleaner/) | 对账业务 saas-reconciliation-business 按主题清理对账数据（按月物理分表逐月删 rec_recon_result/check_data/recon_susp + 任务/进度/日志 + 疑点处理/关联，重置 rec_suspicious_strategy.progress_date） |

### 本地开发运维

| Skill | 用途 |
|---|---|
| [bs-project-run](./bs-project-run/) | 启动、停止、重启、登录或验证由 bs-project-tools/bs-java-run 管理的本地 BS Java 服务（端口检查、token 刷新、进程/日志排查） |
| [bs-jenkins-cli](./bs-jenkins-cli/) | 通过 bsq-jenkins CLI 触发和查看 Jenkins 构建（tax-jenkins / saas-jenkins），无需打开浏览器 |
| [bs-jira-query](./bs-jira-query/) | 通过 bsq-jira CLI 全生命周期管理 Jira 任务（查询详情、修改状态、指派人员、编辑字段），并提供原生、免浏览器登录的附件安全下载能力 |

### 发版流程

| Skill | 用途 |
|---|---|
| [bs-tax-bugfix-release](./bs-tax-bugfix-release/) | 在 tax 项目中针对线上已发布版本修 bug 并发版：从 tag 拉修复分支、递增版本号、改代码、打 tag 发布，内建切分支防丢文件、提交防误带、发版前版本占用检查等踩坑兜底 |

## 目录结构

```
zzq-agent-skills/
├── <skill-name>/
│   ├── SKILL.md          # 必需，frontmatter + 指令正文
│   ├── references/       # 可选，按需加载的细节文档
│   └── agents/           # 可选，子 agent 配置
├── docs/                 # 规划与设计文档（OpenSpec 等）
└── README.md
```

## 维护

每个 skill 目录下的 `SKILL.md` 是真实生效的内容；`references/` 是按需加载的细节文档。改动 skill 后：

```bash
# 1. 在本地 skills 目录编辑（或在本仓库编辑）
# 2. 同步到本仓库后提交
git add -A && git commit -m "feat(<skill-name>): xxx"
git push
```

## 许可

仅个人使用与团队内分享，无明确开源许可。
