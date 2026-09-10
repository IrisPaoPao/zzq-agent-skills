---
name: bs-database-script-organizer
description: 在 saas-database 仓库中整理与归档 Flyway 数据库迁移脚本（复刻 数据库脚本工具.exe）。自动扫描 temp 目录下的待交付脚本，调用官方 SQL 翻译引擎极速批处理校验语法与分表规则，生成多方言版本（TDSQL、MySQL、DRDS、Oracle、DM、Kingbase 等），编排 Flyway 递增版本序号，更新 schema_version.sql 与分表配置，并将源脚本安全归档至 backup/ 目录。支持 --dry-run 预检、--undo 一键撤销还原与多业务防误触拦截。当用户在 saas-database 仓库提到"整理脚本""归档数据库脚本""跑脚本工具""脚本入库""分配版本号""撤销归档"时自动调用。
---

# BS Database Script Organizer

## 用途

在 `saas-database` 仓库中将开发人员放置在 `temp/` 目录下的草稿脚本整理为正式交付的 Flyway 迁移脚本，并归档源文件。
本工具完整复刻了 Windows 下的 `行业应用/tool/数据库脚本工具.exe` 与 `运营支撑门户/tool/数据库脚本工具.exe`，原生支持 macOS / Linux / Windows，且支持全局 CLI `bsq-sql-organize` 与 `--undo` 一键撤销回退。

## 安装方式

### 方式 1：通过 Git 远程直接安装（推荐）
```bash
pipx install git+https://github.com/IrisPaoPao/zzq-agent-skills.git#subdirectory=bs-database-script-organizer --force
# 或使用 pip：
# pip install git+https://github.com/IrisPaoPao/zzq-agent-skills.git#subdirectory=bs-database-script-organizer
```

### 方式 2：本地仓库安装
进入技能目录执行：
```bash
./install.sh
```

安装完成后，在终端任意路径下均可直接运行全局命令 `bsq-sql-organize`（或使用本地入口 `./bin/bs-sql-organize`）。

## 快速运行命令

```bash
# 1. 针对指定业务和版本进行预检预览（强烈推荐，输出计划与分表 Diff，不改动任何文件）
bsq-sql-organize --platform <industry|operate> --business <business-directory> --version <program-version> --dry-run --verbose

# 2. 确认无误后执行正式整理与归档
bsq-sql-organize --platform <industry|operate> --business <business-directory> --version <program-version>

# 3. 发现整理内容有误时：一键撤销并还原源脚本（后悔药）
bsq-sql-organize --undo
```

### CLI 参数说明

| 参数 | 说明 | 示例 | 默认值 |
|---|---|---|---|
| `--undo` | **一键撤销**上次归档：自动删除生成物、移回 backup 源文件至 temp、还原 schema_version | `bsq-sql-organize --undo` | - |
| `--platform` | 目标运行侧平台：`industry`（行业应用）、`operate`（运营支撑门户）或 `all` | `--platform industry` | `all` |
| `--business` | 业务目录名称（`temp/` 下的子目录） | `--business 13_certificate` | 全部业务（有防误触保护） |
| `--all-businesses` | 明确允许跨多个业务目录批量整理（未指定 `--business` 且检测到多个业务草稿时必需） | `--all-businesses` | 关闭 |
| `--version` | 待处理的脚本程序版本号 | `--version 1.3.31` | 全部版本 |
| `--product-child` | 项目化业务子目录（仅用于 `07_projectized`） | `--product-child 350001_law` | 无 |
| `--date` | 归档到 `backup/` 的备份目录日期（YYYYMMDD） | `--date 20260909` | 当天日期 |
| `--dry-run` | 仅执行扫描、校验与方言转换，输出计划，**不修改任何文件** | `--dry-run` | 关闭 |
| `--verbose`, `-v` | 输出详细计划列表与分表 YAML Unified Diff | `-v` | 关闭 |
| `--database-root` | `saas-database` 仓库根路径 | `--database-root /path/to/saas-database` | 自动检测 |

## 标准工作流程

### 1. 确认上下文与前置检查
- 确认当前处于 `saas-database` 仓库规范分支（通常为 `huazhi` 分支）。
- 确认用户要整理的目标范围：
  - 运行侧（`industry` 行业应用 或 `operate` 运营支撑门户）
  - 业务目录（如 `01_standard`、`04_complex_charge` 等）
  - 程序版本（如 `1.3.31`、`3.0.8.4` 等）

### 2. 必须先执行 `--dry-run` 预览
在执行任何真实写入或移动前，**必须**先带 `--dry-run --verbose` 执行一次：
```bash
bsq-sql-organize --platform <platform> --business <business> --version <version> --dry-run --verbose
```
核对：
1. `SqlCheckRunner` 校验是否通过（语法规范、命名格式、分表规则）。
2. 生成的目标方言列表（TDSQL、MySQL、DRDS、Oracle、DM、Kingbase 等 13+ 种）是否完整。
3. 编排的 Flyway 序号 `V{version}_{product}_00_{seq}__...` 是否紧跟现有序号。
4. 归档的目标路径是否正确（`backup/<business>/[child]/<YYYYMMDD>/`）。
5. 若有分表规则变化，检查控制台打印的 `saas-sharding.yml.vm` Unified Diff。

### 3. 正式整理并归档
经用户确认或核对无误后，去掉 `--dry-run` 参数执行实际整理：
```bash
bsq-sql-organize --platform <platform> --business <business> --version <version>
```

### 4. 出现错误或需修改时：一键撤销
如果整理后发现脚本业务内容写错、漏加字段或需要修改：
```bash
bsq-sql-organize --undo
```
工具会根据现场收据文件自动删除所有生成的 Flyway 与 business 文件、还原 `schema_version.sql`、并将原始草稿文件毫秒级恢复到 `temp/<business>/` 目录，供您直接再次编辑。

## 硬约束与安全保护

1. **先 `--dry-run` 预览**：严禁在未 `--dry-run` 验证的情况下直接执行正式整理，避免因脚本存在语法错误或序号冲突导致脏写入。
2. **多业务防误触拦截**：未指定 `--business` 时，若检测到多个业务目录存在草稿，CLI 会主动拦截并列出业务清单，杜绝误动他人草稿。
3. **极速批处理（Batch Mode）**：内置 Java 桥接采用内存单进程批处理模式，将全部方言的校验转换耗时压缩至 1 秒以内。
4. **事务与收据保护**：整理失败自动事务回滚现场；整理成功记录 `.organize_receipt.json`，确保随时可无损 `--undo`。
