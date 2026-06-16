---
name: bs-database-script-generator
description: 在 saas-database / tax-database 仓库生成 Groovy Flyway 迁移脚本。覆盖 TDSQL 与 ORACLE 双版本输出、行业应用与运营支撑门户的目录与命名规则、同日序号递增、SQL 到 Groovy 幂等包装、TDSQL ↔ Oracle 方言转换。当用户说"生成数据库脚本""加字段""建表""删索引""导出 groovy 脚本"，或贴出 CREATE TABLE / ALTER TABLE / INSERT 等原始 SQL 让你产出 Flyway 脚本时，立刻使用本技能；张政卿的 JavaDoc 风格头注释和 18_data_gateway 产品默认规则都已内置。
---

# BS Database Script Generator

## 用途

在 saas-database / tax-database 这类内部仓库里生成可执行的 Groovy Flyway 迁移脚本。原始素材通常是用户贴的一段 SQL（DDL 或 DML），目标是产出符合仓库规范、可重复执行、能在多个数据库厂商上跑的 `.groovy` 文件。

工作的关键是 **从仓库里建立上下文**，而不是凭空套模板。同一个产品下相邻脚本的写法（表空间、注释风格、序号位数、命名习惯）通常已经形成了事实约定，直接复用比"标准答案"更稳。

## 工作流程

1. **建立上下文。** 读仓库根目录的 `AGENTS.md` 与 `README.md`；定位目标产品（参见 `references/products.md`）和它的 `temp/` 目录；列出该目录里最近 5–10 个 `.groovy` 看注释风格、序号位数、表空间、字符集；查看该产品 `business/<product>/` 下的版本号。
2. **明确输入。** 与用户确认：产品（目录）、数据库（默认 TDSQL+Oracle 双版本）、版本号（缺省从 business 目录的最新版本推断）、作者。如果作者是张政卿，按下文「张政卿默认风格」执行；其他人按基线规范（`// jira-id describe` + `// 姓名` 双行注释）。
3. **决定文件集合。** 默认 TDSQL 和 Oracle 各一份。多张表按表拆；多类操作（建表 vs 改表 vs 加索引）按操作类型拆；同一张表的多字段、多索引可以合并到一个文件，**但每个字段、每个索引各自一个 `if` 包裹**（原因见硬约束 #1）。
4. **包装与转换。** 选对幂等包装（`missTable` / `missColumn` / `missIndex` / `notExist`），然后把 SQL 主体放进 `executeMultiCommand("""...""")`，并按 TDSQL ↔ Oracle 方言转换类型与约束。详细模板见 `references/scenarios.md`，方言映射见 `references/dialects.md`。
5. **回读校验。** 再读一遍生成的文件：命名格式、序号、版本号、作者头、`else` 分支的 `println`、SQL 末尾 `;`、Oracle 表空间。确认与硬约束清单都对得上。
6. **回报路径。** 在最终回复里明确给出生成的文件绝对路径或仓库相对路径，方便用户直接打开。除非用户明确要求验证，**不要**主动跑 `start.bat migrate`。

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
10. **单脚本 < 50 KB（flyway 上限 65 KB）。** 不分表脚本通常没问题；分表脚本经过年/月展开会膨胀十几倍，必要时按 if 拆文件。

## 仓库目录与命名

- **草稿目录：** 行业产品 → `行业应用/temp/<product>/`；运营产品 → `运营支撑门户/temp/<product>/`（具体产品见 `references/products.md`）。`temp/` 下大多数产品**直接平铺脚本**，不分 `tdsql/oracle` 子目录——直接放在 `temp/<product>/` 即可。
- **归档目录：** `行业应用/business/<product>/<version>/` 与 `行业应用/backup/<product>/<yyyymmdd>/`；前者是已发布脚本，后者是按发布日切走的历史草稿。看相邻脚本时优先看 backup 最新一天。
- **命名格式：**
  ```
  yyyy-MM-dd_姓名_序号__english_summary_TDSQL_[version].groovy
  yyyy-MM-dd_姓名_序号__english_summary_ORACLE_[version].groovy
  ```
  - 序号位数与目标目录现有脚本对齐（多数为两位 `01–99`）。
  - 英文描述简短可识别即可，例如 `create_table_xxx`、`alter_xxx_add_yyy`、`drop_index_xxx`。
  - 版本号方括号包裹：`[1.4.3.0]`，缺省时从 `business/<product>/` 已有版本目录推断最新或下一版本。

## 张政卿默认风格（作者识别后启用）

- 头注释用 JavaDoc 风格：
  ```groovy
  /**
   @author 张政卿
   @date 2026.06.16
   @describe <需求说明>
   */
  ```
- 序号两位 `01`、`02`...
- 数据存在性判断用 `notExist("select * from <table> where ...")`（不是 `select 1`）。
- Oracle 用 `VARCHAR2(N CHAR)`（明确字符长度），表空间按场景选 `SAAS_BASIC_TBS`/`SAAS_BASIC_INDEX_TBS`（基础表）或 `SAAS_BUS_TBS`/`SAAS_BUS_INDEX_TBS`（业务表，含 `rec_data_source` 这类大表）。
- 即使用户给的是 MySQL SQL，也只产出 TDSQL 和 Oracle 两套；不生成原版 MySQL 文件。

其他作者：按基线规范使用双行注释 `// jira-id 描述` + `// 姓名`，类型与表空间按相邻脚本保持。

## 18_data_gateway 产品默认规则（与作者无关）

- 输出目录：`行业应用/temp/18_data_gateway/`（平铺）。
- 该产品表前缀通常是 `gwb_`。
- 部分主表是按月分表（如 `gwb_original_data`），有 `shardkey=tenant_code` + 年月 PARTITION；分表脚本要避免单文件超长，必要时按 if 块拆。

## 关键场景速查

详见 `references/scenarios.md`，包含双数据库的标准片段：

- 建表（含表注释、列注释、索引、表空间）
- 加字段（单字段、多字段同文件）
- 加索引、删索引、删唯一约束
- 改字段类型 / 默认值（Oracle 必须拆两条）
- 改字段 NOT NULL / NULL（用 `nullable()` 判断）
- 插入与更新数据
- 权限模板版本号 +0.01（`auth_temp_application` / `auth_temp_function_version`）

## 方言映射速查

详见 `references/dialects.md`，覆盖 TDSQL → Oracle 的类型映射、Oracle → KingBase / DM / Vastbase 的衍生规则、表空间命名约定。

## 工具方法清单

仓库里 Groovy 脚本可用的判断与执行方法：

| 方法 | 用途 | 备注 |
|---|---|---|
| `executeMultiCommand("""...""")` | 执行多条 SQL | 每条以 `;` 结尾；统一用这个 |
| `execute("...")` | 执行单条 SQL | 末尾不能有 `;`，不支持注释 |
| `missTable(table)` | 表不存在 → true | |
| `missColumn(table, column)` | 字段不存在 → true | |
| `missIndex(table, index)` | 索引不存在 → true | 删索引用 `!missIndex(...)` |
| `notExist(sql)` | 查询无结果 → true | 张政卿习惯用 `select *` |
| `nullable(table, column)` | 字段允许 NULL → true | 改 NOT NULL/NULL 时判断，避免 Oracle "已 null 改 null" 报错 |
| `println(msg)` | 控制台输出 | 仅在 else 分支提示用，不进日志文件 |
| `toBytes(filename)` | 文件转 BLOB | 文件须与脚本同目录 |

## 输出要求

- 回复里明确给出生成的文件路径（绝对路径或带 `行业应用/...` 的仓库相对路径）。
- 引用仓库内文件时遵循 `AGENTS.md` 中的本地 Markdown 链接格式。
- 不要主动执行 Flyway 命令；只有在用户明确要求验证时才跑 `start.bat info` / `start.bat migrate`。

## 快速检查清单（生成完成前自检）

1. 文件名命名格式正确，序号在目标目录里递增且唯一。
2. 头部注释格式与作者风格匹配。
3. 每个字段 / 每个索引各自独立 `if`，不堆 ALTER。
4. 没有嵌套 if-else。
5. `executeMultiCommand` 内每条 SQL 以 `;` 结尾；注释里没有 `;`；没有裸双引号。
6. else 分支都有 `println` 提示。
7. TDSQL 建表带 `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci`。
8. Oracle 建表带表空间；类型与默认值不在同一条 ALTER 里；`VARCHAR2(N CHAR)`。
9. 表名、索引名 ≤ 30 字符。
10. 单文件 < 50 KB；分表脚本要心算展开后大小。
