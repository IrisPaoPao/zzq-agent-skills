# zzq-agent-skills

张政卿 ([@IrisPaoPao](https://github.com/IrisPaoPao)) 个人维护的 Claude Code Skills 集合。

每个 skill 是一个独立子目录，包含 `SKILL.md`（必需）和可选的 `references/` `agents/` 等资源。Claude Code 会读取 `SKILL.md` 头部的 YAML frontmatter 决定何时触发，再按需加载子文件。

## 安装

把需要的 skill 拷贝到 `~/.claude/skills/` 即可：

```bash
git clone https://github.com/IrisPaoPao/zzq-agent-skills.git
cp -r zzq-agent-skills/<skill-name> ~/.claude/skills/
```

或者一次安装全部：

```bash
git clone https://github.com/IrisPaoPao/zzq-agent-skills.git ~/.claude/skills-zzq
ln -s ~/.claude/skills-zzq/* ~/.claude/skills/
```

下次开新会话，Claude Code 会自动加载并按 description 触发。

## 当前 skills

| Skill | 用途 |
|---|---|
| [bs-database-script-generator](./bs-database-script-generator/) | 在 saas-database / tax-database 仓库生成 Groovy Flyway 迁移脚本（TDSQL + Oracle 双版本、命名规则、序号递增、SQL → Groovy 幂等包装、方言转换） |
| [bs-menu-export](./bs-menu-export/) | 从运营平台 dev-operations 库导出已存在菜单的 auth_temp_* 全链路脚本 |
| [bs-menu-create](./bs-menu-create/) | 创建/新增运营平台菜单，按同级数据生成纯 SQL，支持分类菜单、叶子菜单、按钮权限、多模板和重复检测 |
| [bs-gateway-scene-sql-generator](./bs-gateway-scene-sql-generator/) | 在 saas-data-gateway 仓库由 groovy 采集脚本生成场景注册 SQL（gwb_scene + gwb_scene_capacity_relation + gwb_context_param），含库内最大 scene_id 查询与工作区预定号扫描的 pre-flight 校验 |
| [bs-gateway-dirty-data-cleaner](./bs-gateway-dirty-data-cleaner/) | 数据网关 saas-data-gateway 采集任务脏数据清理 + 重采进度重置（TDSQL 逻辑表名路由、删除顺序 item→session→batch→data→index、雪花 id 精度陷阱） |
| [bs-reconciliation-data-cleaner](./bs-reconciliation-data-cleaner/) | 对账业务 saas-reconciliation-business 按主题清理对账数据（按月物理分表逐月删 rec_recon_result/check_data/recon_susp + 任务/进度/日志 + 疑点处理/关联，重置 rec_suspicious_strategy.progress_date） |

## 维护

每个 skill 目录下的 `SKILL.md` 是真实生效的内容；`references/` 是按需加载的细节文档。改动 skill 后：

```bash
cd ~/.claude/skills/<skill-name>
# 编辑文件
cd ~/work/zzq-agent-skills
cp -r ~/.claude/skills/<skill-name> ./
git add -A && git commit -m "feat(<skill-name>): xxx"
git push
```

## 许可

仅个人使用与团队内分享，无明确开源许可。
