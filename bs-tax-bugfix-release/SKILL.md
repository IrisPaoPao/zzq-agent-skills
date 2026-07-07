---
name: bs-tax-bugfix-release
description: 在 tax 开头的项目（如 tax-collect、tax-lxcloud-collect、tax-used、tax-lxcloud-used、tax-invoice 等）里针对线上已发布版本修 bug 并发版。覆盖完整流程——从有 bug 的 tag 拉修复分支、递增版本号、改代码、精确提交、打 tag 发布，并内建切分支防丢文件、提交防误带、发版前查 maven 确认版本未占用、打 tag 前查 SNAPSHOT、修改被依赖项目时按依赖顺序构建下游等踩坑兜底。当用户在 tax 项目中提到"修 bug 发版""从 tag 拉分支改 bug""打个发版 tag""版本号加一发版"等时自动使用；非 tax 项目需用户明确提及本技能名称后才使用。
---

# tax 项目 bug 修复发版工作流

## 用途

在 tax 开头的项目里，针对线上已发布版本的一个 bug，从对应 tag 拉出修复分支、递增版本号、改代码、提交、打 tag 发布。核心是 **版本号要新、提交要干净、tag 要对得上、不能拖 SNAPSHOT**。

版本号体系通常是 `${revision}`（本仓库版本）+ 依赖版本属性（如 `base.collect.vision`），子模块一律用 `${revision}`，不要硬编码。

## 工作流程

1. **定位有 bug 的 tag**——确认线上跑的版本对应的 tag，`git tag -l '<version>*'` 确认存在，`git show <tag>:pom.xml | grep -E 'revision|vision'` 看该 tag 的版本号和依赖版本。
2. **从 tag 拉新分支**——先 `git branch -a | grep <new-version>` 查远程是否已有同名分支；若已有，看它的版本号和改动是否就绪（可能是别人建好版本号但没修 bug），避免重复创建。没有则 `git checkout -b <new-branch> <tag>`。
3. **递增版本号**——改 pom.xml 的 `revision`（及依赖版本属性）。规则见「版本号规则」。改完 `grep -rn '<old-version>' --include=pom.xml` 确认无硬编码遗漏。
4. **修复 bug**——改代码，`git diff` 复核。
5. **精确提交**——用 `git commit <pathspec> -m '...'` 指定文件提交，`git show --stat HEAD` 确认只含目标文件。提交信息按项目惯例前缀（`fix:` / `chore:` 等）。
6. **打 tag + push**——**先按硬约束 #4/#6 检查所有 pom 无 SNAPSHOT，并完成必要构建验证**，再 `git tag -a <version> -m 'release <version>: ...'`，`git push origin <version>`。若本仓库依赖别的 tax 仓库，同步在对方仓库打 tag。

## 版本号规则

- 版本号三位（如 `1.9.19`）→ 加补丁位 `.1`（`1.9.19.1`）
- 版本号四位（如 `1.9.19.4`）→ 最后一位 +1（`1.9.19.5`）
- **若算出的版本号已被占用**（tag 或 maven 仓库已存在），则在原版本后加补丁位（如 `1.9.19.4` → `1.9.19.4.1`，再被占则 `.2`）
- 发正式版去掉 `-SNAPSHOT` 后缀；开发分支名仍带 `-SNAPSHOT`（分支名带 SNAPSHOT、revision 不带是正常的，两者独立）

## 硬约束（踩坑兜底，违反会丢文件 / 误提交 / 发版冲突）

1. **切分支前先处理 staged 文件。** `git checkout` 切换分支时，staged 的新文件（`A` 状态）可能丢失（git 不一定保留到目标分支）。切前先 `git stash -u` 或 commit。丢了用 `git fsck --lost-found` 找 dangling blob，按文件 magic bytes 筛选恢复（如 PNG 用 `89504e47`）。
2. **提交用 `git commit <pathspec>`，不要 `git add` 后 `git commit`。** index 里可能残留其他 staged 内容，`git commit`（无 pathspec）会把它们一起带上。用 `git commit <file> -m` 只提交指定文件最稳。
3. **发版前查 maven 仓库确认版本号未占用。** 本地 maven 仓库可能在非默认路径（不一定是 `~/.m2`，常见 `worksoft/mavenRepo`），先看 `~/.m2/settings.xml` 的 localRepository。已发布的正式版 maven 不允许覆盖，版本号撞了必须换。
4. **打 tag 前必须确认所有 pom 无 SNAPSHOT。** SNAPSHOT 是开发版，不能进正式 tag。检查 `grep -rni 'snapshot' --include=pom.xml . | grep -v /target/`，根 pom 和子模块都要查（含 `revision`、依赖版本属性如 `base.collect.vision`、`tax.api.server` 等）。有 SNAPSHOT 则先改成对应正式版（并确认该正式版已发布）再打 tag——否则 tag 出来的产物会拖一个开发版依赖。
5. **打 tag 前确认无同名 tag。** `git tag -l <version>`；若已存在且是带 bug 的旧 tag，发版前先和团队确认是否删旧重打。
6. **打 tag 前必须做必要构建验证；触发条件是本次是否修改了被依赖项目。** 无 SNAPSHOT 只是版本检查，不能替代实际构建。先判断本次改动所在仓库是不是会被其他 tax 仓库依赖：如果改的是被依赖项目，则必须先构建该上游项目，再按 pom 依赖拓扑构建所有直接或间接受它新版本影响的下游项目；如果只改了叶子项目且没有其他仓库依赖它，则构建当前项目即可，不扩大到无关仓库。例如链路是 `tax-used` → `tax-lxcloud-used` 且本次改了 `tax-used`，就先构建 `tax-used`，再构建 `tax-lxcloud-used`；链路是 `tax-collect` → `tax-lxcloud-collect` 且本次改了 `tax-collect`，同理先上游再下游。任一项目构建失败、缺包、依赖解析失败或版本未发布，都禁止打 tag / push tag，停止并汇报失败项目、失败命令、缺失依赖坐标或 Maven 摘要，交给人工处理。
7. **工作区可能有其他分支带过来的改动。** 切分支后先 `git status` 看清哪些是本次发版要提交的、哪些是别的工作的，只 `git commit` 前者。

## 命令速查

```bash
# 定位有 bug 的 tag 及其版本号
git tag -l '1.9.19.7*'
git show <tag>:pom.xml | grep -E 'revision|vision'

# 查远程是否已有目标分支
git branch -a | grep <new-version>

# 从 tag 拉分支
git checkout -b <new-branch> <tag>

# 改版本号后查硬编码遗漏
grep -rn '<old-version>' --include=pom.xml . | grep -v /target/

# 精确提交 + 确认
git commit <file1> <file2> -m 'fix: ...'
git show --stat HEAD

# 打 tag 前查 SNAPSHOT（必须无输出才可打 tag）
grep -rni 'snapshot' --include=pom.xml . | grep -v /target/

# 打 tag 前构建验证：
# 1) 总是构建本次修改项目
# 2) 仅当本次修改项目被其他仓库依赖时，再按依赖顺序构建受影响下游
(cd ../<changed-tax-project> && mvn -DskipTests clean package)
(cd ../<affected-downstream-tax-project> && mvn -DskipTests clean package)

# 打 tag + push
git tag -a <version> -m 'release <version>: ...'
git push origin <version>

# 找回切分支丢失的 staged 文件
git fsck --lost-found | grep 'dangling blob'
git cat-file blob <hash> | head -c 4 | xxd -p   # 验 magic bytes
git cat-file blob <hash> > <path>                # 确认后恢复
```
