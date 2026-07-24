---
name: bs-tax-bugfix-release
description: 在 tax 开头的项目（如 tax-collect、tax-lxcloud-collect、tax-used、tax-lxcloud-used、tax-invoice 等）里针对线上已发布版本修 bug 并发版。覆盖完整流程——确认目标发布线（用户指定既有 *-SNAPSHOT 分支时以该分支为唯一依据、不新建分支）、按位数递增版本号（保持位数只递增最后一位）、改代码、精确提交、打 tag 发布，并内建切分支防丢文件、提交防误带、发版前查 maven 确认版本未占用、打 tag 前查 SNAPSHOT、修改被依赖项目时按依赖顺序构建下游等踩坑兜底。当用户在 tax 项目中提到"修 bug 发版""从 tag 拉分支改 bug""直接在既有 SNAPSHOT 分支改 bug 发版""打个发版 tag""版本号加一发版"等时自动使用；非 tax 项目需用户明确提及本技能名称后才使用。
---

# tax 项目 bug 修复发版工作流

## 用途

在 tax 开头的项目里，针对线上已发布版本的一个 bug，确认目标发布线、递增版本号、改代码、提交、打 tag 发布。核心是 **发布线要对、版本号要新且位数不变、提交要干净、tag 要对得上、不能拖 SNAPSHOT**。

两种入口：

- **用户指定了既有 `*-SNAPSHOT` 分支**（如"直接在 1.9.22-SNAPSHOT 上修并发版"）：以该分支为**唯一**发布线依据，在该分支上修，**不新建分支**。
- **用户未指定现成发布分支**：从有 bug 的 tag 拉修复分支。

版本号体系通常是 `${revision}`（本仓库版本）+ 依赖版本属性（如 `base.collect.vision`），子模块一律用 `${revision}`，不要硬编码。

## 工作流程

1. **确认目标发布线与版本基线**——
   - **用户指定既有 `*-SNAPSHOT` 分支时**：先 `git fetch origin <target-branch> --tags`，再 `git tag --merged origin/<target-branch> --sort=-v:refname` 找出**该分支已包含**的最高正式 tag，然后 `git show <tag>:pom.xml | grep -E 'revision|vision'` 核对该 tag 的 POM 版本，以此为版本基线。**不得**用其他分支的 tag、全仓库最高 tag、或 Maven 中不属于该发布线的版本来推断新版本。
   - **用户未指定现成发布分支时**：定位有 bug 的 tag——确认线上跑的版本对应的 tag，`git tag -l '<version>*'` 确认存在，`git show <tag>:pom.xml | grep -E 'revision|vision'` 看该 tag 的版本号和依赖版本，以此为版本基线。
2. **准备分支**——
   - **用户指定既有 SNAPSHOT 分支时，不要新建分支**：不要从 tag 新拉分支；在隔离 worktree 中检出该已有分支（`git worktree add ../<wt-dir> <target-branch>`），进入后先 `git pull --ff-only` 同步远程最新提交再开工。
   - **用户未指定现成发布分支时**，才从目标 tag 拉新分支：先 `git branch -a | grep <new-version>` 查远程是否已有同名分支；若已有，看它的版本号和改动是否就绪（可能是别人建好版本号但没修 bug），避免重复创建。没有则 `git checkout -b <new-branch> <tag>`。
3. **递增版本号**——以第 1 步确定的版本基线，按「版本号规则」改 pom.xml 的 `revision`（及依赖版本属性）。改完 `grep -rn '<old-version>' --include=pom.xml` 确认无硬编码遗漏。
4. **修复 bug**——改代码，`git diff` 复核。
5. **精确提交**——**提交前先 `git pull`**（既有分支场景用 `git pull --ff-only`）；若 pull 冲突、失败或需要选择 merge/rebase 策略，停止并询问用户。再用 `git commit <pathspec> -m '...'` 指定文件提交，`git show --stat HEAD` 确认只含目标文件。提交信息按项目惯例前缀（`fix:` / `chore:` 等）。
6. **打 tag + push**——**先按硬约束 #4/#5/#6 检查所有 pom 无 SNAPSHOT、tag 在 Git 与 Maven 均未占用且 revision 与 tag 一致、并完成必要构建验证**，再 `git tag -a <version> -m 'release <version>: ...'`，`git push origin <version>`。若本仓库依赖别的 tax 仓库，同步在对方仓库打 tag。

## 版本号规则

**版本基线**：目标发布线已包含的最高正式 tag（按工作流程第 1 步确定）。不是全仓库最高 tag，也不是其他分支的 tag。

**保持基线位数，只递增最后一位**：

- 基线三位（如 `1.9.22`）→ 允许新增一个补丁位：`1.9.22.1`（**唯一**允许增加位数的情形）
- 基线四位（如 `1.9.22.4`）→ 只递增第四位：`1.9.22.5`
- 基线五位（如 `1.9.22.4.1`）→ 只递增第五位：`1.9.22.4.2`
- 基线六位同理：只递增第六位，前面所有版本位保持不变

**候选版本被占用时**（Git tag 或 Maven 仓库已存在）：**保持版本位数不变**，继续递增最后一位，直到得到未占用版本。**严禁**因为基线 tag 已存在就新增版本位：

- ✅ 基线 `1.9.22.4`（已存在）→ 下一个版本 `1.9.22.5`；若 `1.9.22.5` 也被占 → `1.9.22.6`
- ❌ 基线 `1.9.22.4`（已存在）→ `1.9.22.4.1`（错误：基线 tag 已存在不是新增版本位的理由）

**案例**：目标分支 `1.9.22-SNAPSHOT`，`git tag --merged origin/1.9.22-SNAPSHOT` 得出该分支已包含的最高 tag 为 `1.9.22.4` → 正确下一个版本为 **`1.9.22.5`**，错误版本是 `1.9.22.4.1`。即使其他分支存在 `1.9.22.3.1`，也不能影响本发布线的递增结果——基线只看目标分支已包含的 tag。

发正式版去掉 `-SNAPSHOT` 后缀；开发分支名仍带 `-SNAPSHOT`（分支名带 SNAPSHOT、revision 不带是正常的，两者独立）。

## 硬约束（踩坑兜底，违反会丢文件 / 误提交 / 发版冲突）

1. **切分支前先处理 staged 文件。** `git checkout` 切换分支时，staged 的新文件（`A` 状态）可能丢失（git 不一定保留到目标分支）。切前先 `git stash -u` 或 commit。丢了用 `git fsck --lost-found` 找 dangling blob，按文件 magic bytes 筛选恢复（如 PNG 用 `89504e47`）。
2. **提交用 `git commit <pathspec>`，不要 `git add` 后 `git commit`。** index 里可能残留其他 staged 内容，`git commit`（无 pathspec）会把它们一起带上。用 `git commit <file> -m` 只提交指定文件最稳。
3. **发版前查 maven 仓库确认版本号未占用。** 本地 maven 仓库可能在非默认路径（不一定是 `~/.m2`，常见 `worksoft/mavenRepo`），先看 `~/.m2/settings.xml` 的 localRepository。已发布的正式版 maven 不允许覆盖，版本号撞了必须换。
4. **打 tag 前必须确认所有 pom 无 SNAPSHOT。** SNAPSHOT 是开发版，不能进正式 tag。检查 `grep -rni 'snapshot' --include=pom.xml . | grep -v /target/`，根 pom 和子模块都要查（含 `revision`、依赖版本属性如 `base.collect.vision`、`tax.api.server` 等）。有 SNAPSHOT 则先改成对应正式版（并确认该正式版已发布）再打 tag——否则 tag 出来的产物会拖一个开发版依赖。
5. **打 tag 前必须完成 tag / 版本一致性硬校验。** 必须同时满足：
   - POM 中的 `revision` 与待创建 tag **完全一致**；
   - 待创建 tag 在 **Git 和 Maven 仓库中都不存在**（`git tag -l <version>` 无输出，且按硬约束 #3 查 maven 未占用）。

   若候选 tag 已存在，按「版本号规则」保持位数、递增最后一位，生成下一个候选版本并改回 POM 后**重新校验**，不得跳过。**不得覆盖、删除或重打既有 tag**；如确实需要删除 tag，必须由用户明确指定要删除的**精确 tag 名称**，不能根据推测删除。
6. **打 tag 前必须做必要构建验证；触发条件是本次是否修改了被依赖项目。** 无 SNAPSHOT 只是版本检查，不能替代实际构建。先判断本次改动所在仓库是不是会被其他 tax 仓库依赖：如果改的是被依赖项目，则必须先构建该上游项目，再按 pom 依赖拓扑构建所有直接或间接受它新版本影响的下游项目；如果只改了叶子项目且没有其他仓库依赖它，则构建当前项目即可，不扩大到无关仓库。例如链路是 `tax-used` → `tax-lxcloud-used` 且本次改了 `tax-used`，就先构建 `tax-used`，再构建 `tax-lxcloud-used`；链路是 `tax-collect` → `tax-lxcloud-collect` 且本次改了 `tax-collect`，同理先上游再下游。任一项目构建失败、缺包、依赖解析失败或版本未发布，都禁止打 tag / push tag，停止并汇报失败项目、失败命令、缺失依赖坐标或 Maven 摘要，交给人工处理。
7. **工作区可能有其他分支带过来的改动。** 切分支后先 `git status` 看清哪些是本次发版要提交的、哪些是别的工作的，只 `git commit` 前者。

## 命令速查

```bash
# 用户指定既有 SNAPSHOT 分支：找该分支已包含的最高正式 tag（版本基线）
git fetch origin <target-branch> --tags
git tag --merged origin/<target-branch> --sort=-v:refname | head -5
git show <tag>:pom.xml | grep -E 'revision|vision'

# 用户指定既有 SNAPSHOT 分支：隔离 worktree 检出已有分支（不要新建分支），先 ff-only 同步
# 注意：若该分支已在本地检出（主 worktree 或其他 worktree），git worktree add 会报 already checked out；
# 此时直接在已有检出目录里 git pull --ff-only 开工即可，不必强建 worktree。
git worktree add ../<wt-dir> <target-branch>
cd ../<wt-dir> && git pull --ff-only

# 定位有 bug 的 tag 及其版本号（仅用户未指定现成发布分支时）
git tag -l '1.9.19.7*'
git show <tag>:pom.xml | grep -E 'revision|vision'

# 查远程是否已有目标分支
git branch -a | grep <new-version>

# 从 tag 拉分支（仅用户未指定现成发布分支时）
git checkout -b <new-branch> <tag>

# 改版本号后查硬编码遗漏
grep -rn '<old-version>' --include=pom.xml . | grep -v /target/

# 精确提交 + 确认
git commit <file1> <file2> -m 'fix: ...'
git show --stat HEAD

# 打 tag 前查 SNAPSHOT（必须无输出才可打 tag）
grep -rni 'snapshot' --include=pom.xml . | grep -v /target/

# 打 tag 前确认同名 tag 不存在（必须无输出才可打 tag）
git tag -l <version>

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
