---
name: bs-database-script-generator
description: 在 saas-database / tax-database 仓库生成 Groovy Flyway 迁移脚本。覆盖 TDSQL 与 ORACLE 双版本输出、行业应用与运营支撑门户的目录与命名规则、同日序号递增、SQL 到 Groovy 幂等包装、TDSQL ↔ Oracle 方言转换。当用户在 saas-database 或 tax-database 项目中提到"生成数据库脚本""加字段""建表""删索引""导出 groovy 脚本"，或贴出 CREATE TABLE / ALTER TABLE / INSERT 等原始 SQL 让你产出 Flyway 脚本时自动使用；在其他项目中必须等用户明确提及本技能名称后才能使用。作者风格与产品特色规则均通过实时读取相邻脚本动态识别，不预设具名规则。
---

# BS Database Script Generator

## 用途

在 saas-database / tax-database 这类内部仓库里生成可执行的 Groovy Flyway 迁移脚本。原始素材通常是用户贴的一段 SQL（DDL 或 DML），目标是产出符合仓库规范、可重复执行、能在多个数据库厂商上跑的 `.groovy` 文件。

工作的关键是 **从仓库里建立上下文**，而不是凭空套模板。同一个产品下相邻脚本的写法（表空间、注释风格、序号位数、命名习惯）通常已经形成了事实约定，直接复用比"标准答案"更稳。

## 工作流程

1. **确认必要输入**——看「确认输入」一节，缺什么补什么；能从仓库推断的就别问。
2. **按需建立上下文**——下面三种情况才需要扫仓库，否则跳过：
   - 用户没说产品 → `ls 行业应用/temp/` 或 `ls 运营支撑门户/temp/` 找产品列表
   - 用户没说版本号 → 看 `行业应用/business/<product>/` 的最新版本目录
   - 该产品 / 该作者第一次接触 → 读 1–2 个相邻脚本学风格（具体方法见「相邻脚本识别」）
3. **决定文件集合。** 默认 TDSQL 和 Oracle 各一份。多张表按表拆；多类操作（建表 vs 改表 vs 加索引）按操作类型拆；同一张表的多字段、多索引可以合并到一个文件，**但每个字段、每个索引各自一个 `if` 包裹**（原因见硬约束 #1）。
4. **包装与转换。** 选对幂等包装（`missTable` / `missColumn` / `missIndex` / `notExist`），SQL 主体放进 `executeMultiCommand("""...""")`，并按 TDSQL ↔ Oracle 方言转换类型与约束。模板片段在 `references/scenarios.md`，方言映射在 `references/dialects.md`。
5. **回读校验。** 按下文「快速检查清单」过一遍。
6. **回报路径。** 在最终回复里给出生成文件的相对路径或绝对路径。除非用户明确要求验证，**不要**主动跑 `start.bat migrate`。

## 确认输入

最小必要集合（按优先级）：

| 项 | 用户给定 | 能否推断 | 不确定时怎么办 |
|---|---|---|---|
| 产品 / 目录 | 通常会给 | 给了表名时 `grep -rl 'missTable("<table>"' 行业应用/` | 列出仓库已有产品让用户选 |
| 数据库 | 偶尔指定 | 默认双版本（TDSQL + Oracle） | 直接默认 |
| 版本号 | 偶尔给 | 取 `行业应用/business/<product>/` 下最新目录名 | 推断结果跟用户对一下 |
| 作者 | 通常不给 | `git config user.name` | 推断结果跟用户对一下 |
| 操作描述 | SQL 本身已隐含 | 看 SQL 关键词 | 直接从 SQL 摘 |

**原则：** 缺一项问一次，能默认或推断的不问。一次提问尽量合并多个不确定项。

## 硬约束（违反会导致脚本失败、回退异常或生产事故）

这一节是兜底红线，发现冲突时优先于"相邻脚本怎么写就怎么写"。

1. **单 if 单 ALTER。** 每个字段或索引各自一个 `missColumn` / `missIndex` 包裹的 `if`。不要把多条 `ALTER` 塞进同一个 `executeMultiCommand`——第一条成功后断连，后面就再也不会被执行（重试时 `if` 已经是 false）。多个字段可以放在同一个文件里，但每个字段各自独立 if。
2. **不嵌套 if-else。** Groovy 包装层不支持 `if-else` 嵌套；遇到嵌套需求拆成两个独立的 if。
3. **同日同人文件名后缀必须唯一。** 去掉 `_TDSQL` / `_ORACLE` 之后剩余部分（含序号、英文描述、版本号）必须唯一，否则脚本回退会出错。同一天同一个人的多个脚本只通过序号区分。
4. **`executeMultiCommand` 内每条 SQL 以 `;` 结尾；`execute` 内则不能有 `;`。** SQL 注释里也不能含 `;`。
5. **else 分支必须有，且要打 `println`。** 这是排查时定位"为什么没执行"的唯一线索，不能省略。
6. **Oracle 限制：** 不支持 `IF NOT EXISTS`；不能修改主键；字段不支持 `number(*)`；同一条 `ALTER` 里不能同时改类型和默认值——拆成两条。
7. **表名、索引名 ≤ 30 字符；索引名在数据库实例内全局唯一。** 不仅同表内不重复，整个库都不能重复。
8. **不要写裸双引号。** Oracle 对带双引号的标识符大小写敏感，会引发奇怪的查询失败；一律去掉。
9. **TDSQL 建表必须显式 `DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci`。** MySQL 5.7 和 8.0 默认字符集不同，不显式声明会导致数据迁移乱码。
10. **分表脚本生成后用 `wc -c` 验证 < 50 KB**（flyway 上限 65 KB；按年/按月分表经过工具展开会膨胀十几倍，必要时按 if 拆文件）。不分表脚本不用查。

## 仓库目录与命名

- **草稿目录：** 行业产品 → `行业应用/temp/<product>/`；运营产品 → `运营支撑门户/temp/<product>/`。`temp/` 下大多数产品**直接平铺脚本**，不分 `tdsql/oracle` 子目录——直接放在 `temp/<product>/` 即可。
- **归档目录：** `行业应用/business/<product>/<version>/` 是已发布脚本；`行业应用/backup/<product>/<yyyymmdd>/` 是按发布日切走的历史草稿。看相邻脚本时优先看 backup 最新一天。
- **命名格式：**
  ```
  yyyy-MM-dd_姓名_序号__english_summary_TDSQL_[version].groovy
  yyyy-MM-dd_姓名_序号__english_summary_ORACLE_[version].groovy
  ```
  - 序号位数与目标目录现有脚本对齐（多数为两位 `01–99`）。
  - 英文描述简短可识别即可，例如 `create_table_xxx`、`alter_xxx_add_yyy`、`drop_index_xxx`。
  - 版本号方括号包裹：`[1.4.3.0]`，缺省时从 `business/<product>/` 已有版本目录推断最新或下一版本。

## 相邻脚本识别（动态学风格，不写死）

每个作者、每个产品在仓库里都积累了自己的写法约定（注释格式、序号位数、`notExist` 用 `select *` 还是 `select 1`、Oracle 字段是 `VARCHAR2(N)` 还是 `VARCHAR2(N CHAR)`、表空间名、是否分表）。**这些不要靠 skill 写死**，进入流程后实时去仓库读：

1. **找候选脚本**（按优先级取前 1–2 个就够了）：
   ```bash
   # 优先：该产品 backup 最近一天里同作者的脚本
   ls 行业应用/backup/<product>/<最近日期>/ | grep <作者>
   # 次选：该产品 backup 最近几天的任意脚本
   ls 行业应用/backup/<product>/<最近日期>/
   # 兜底：该产品 business 最新版本里的脚本
   ls 行业应用/business/<product>/<最新版本>/
   ```
2. **读 1–2 个**，提取要复用的要素：
   - 头注释格式（双行 `// jira描述` + `// 姓名` vs JavaDoc `/** @author @date @describe */`）
   - 序号位数、`notExist` 写法、Oracle `VARCHAR2(N)` vs `VARCHAR2(N CHAR)`
   - Oracle 表空间名（`grep -hoE 'TABLESPACE [A-Z_]+' <相邻文件>` 抓出来）
   - 表前缀习惯、是否分表、`shardkey` 字段
3. **找不到时**：按基线规范——双行注释 `// jira-id 描述` + `// 姓名`，类型与表空间沿用方言映射的默认值。

**绝不把任何具名作者偏好或具名表空间写进 skill 文件**——会泄露团队信息，也会随成员流动失效。

## 子文档索引

| 何时打开 | 子文档 | 内容 |
|---|---|---|
| 写实际 SQL 片段时 | `references/scenarios.md` | 10 类场景的 TDSQL+Oracle 标准模板（建表、加字段、加/删索引、改类型、改 NOT NULL、INSERT、UPDATE、权限模板版本号、按月分表） |
| 类型转换、表空间问题 | `references/dialects.md` | TDSQL → Oracle 类型映射、DDL 语法差异、Oracle → KingBase/DM/Vastbase 衍生规则 |
| 找产品归属 / 命名约束 | `references/products.md` | 产品发现命令、目录角色（temp/business/backup）、表前缀绑定 |

## 工具方法清单

仓库里 Groovy 脚本可用的判断与执行方法：

| 方法 | 用途 | 备注 |
|---|---|---|
| `executeMultiCommand("""...""")` | 执行多条 SQL | 每条以 `;` 结尾；统一用这个 |
| `execute("...")` | 执行单条 SQL | 末尾不能有 `;`，不支持注释 |
| `missTable(table)` | 表不存在 → true | |
| `missColumn(table, column)` | 字段不存在 → true | |
| `missIndex(table, index)` | 索引不存在 → true | 删索引用 `!missIndex(...)` |
| `notExist(sql)` | 查询无结果 → true | 写法（`select *` 或 `select 1`）按作者历史脚本沿用 |
| `nullable(table, column)` | 字段允许 NULL → true | 改 NOT NULL/NULL 时判断，避免 Oracle "已 null 改 null" 报错 |
| `println(msg)` | 控制台输出 | 仅在 else 分支提示用，不进日志文件 |
| `toBytes(filename)` | 文件转 BLOB | 文件须与脚本同目录 |

## 输出要求

- 回复里明确给出生成的文件路径（绝对路径或带 `行业应用/...` 的仓库相对路径）。
- 引用仓库内文件时遵循 `AGENTS.md` 中的本地 Markdown 链接格式。
- 不要主动执行 Flyway 命令；只有在用户明确要求验证时才跑 `start.bat info` / `start.bat migrate`。

## 快速检查清单（生成完成前自检）

1. 文件名命名格式正确，序号在目标目录里递增且唯一。
2. 头部注释格式与作者历史脚本一致。
3. 每个字段 / 每个索引各自独立 `if`，不堆 ALTER。
4. 没有嵌套 if-else。
5. `executeMultiCommand` 内每条 SQL 以 `;` 结尾；注释里没有 `;`；没有裸双引号。
6. else 分支都有 `println` 提示。
7. TDSQL 建表带 `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci`。
8. Oracle 建表带表空间；类型与默认值不在同一条 ALTER 里；`VARCHAR2(N CHAR)`。
9. 表名、索引名 ≤ 30 字符。
10. 分表脚本 `wc -c` 验证 < 50 KB。
