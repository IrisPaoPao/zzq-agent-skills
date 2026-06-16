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
