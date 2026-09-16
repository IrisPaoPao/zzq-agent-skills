---
name: bs-database-query
description: 使用 usql CLI 查询、核对和统计 BS 数据库中的真实数据与表结构，并执行用户已授权的增删改、建表、改表及索引操作。适用于实际查库、排查业务数据或执行 SQL；纯 SQL 编写、解释和离线代码审查不要求连接数据库。未明确连接名时，先由项目运行环境和 Nacos 数据源定位连接，禁止猜库。
---

# BS 数据库操作

统一使用上游 `usql`，不依赖自研 JDBC MCP 或自建执行器。业务 Skill 负责表关系与业务范围，本 Skill 负责连接定位、SQL 调用和结果处理。支持的 SQL 取决于目标数据库、驱动和账户权限。

## 环境与连接定位

1. 用户明确指定连接名时选择该连接，继续核对当前 schema 和目标表；不要重复询问已明确的信息。usql 别名只使用字母、数字和下划线；旧别名中的 `-` 迁移为 `_`，必须核对配置映射，不能仅替换名称后猜目标。
2. 未指定连接名时，先确认项目运行环境。聚合工作区读取 `.bs-java-run/JAVARUN.md` 与 `.bs-java-run/JAVARUN.local.md`，按 `bs-project-run` 流程确认环境、Nacos 地址和 namespace。不得默认选择 dev/test。
3. 经项目支持的配置读取方式检查对应 Nacos datasource/dynamic-datasource，将数据库/schema、服务及租户归属与 usql 保存的连接匹配。敏感值仅在本机内存中比对，不输出或另存，不放入命令参数。
4. 按 [references/setup.md](references/setup.md) 定位原生私有配置；清单只展示别名和驱动。不要直接打印配置、完整 DSN 或可能带凭据的连接信息。
5. 用只读 SQL 确认连接可用、当前库/schema 和目标表归属。MySQL 使用 `SELECT DATABASE()`；Oracle 使用 `SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM dual`；SQL Server 使用 `SELECT DB_NAME(), SCHEMA_NAME()`；IRIS 使用 `SELECT $NAMESPACE` 核对 namespace，并从 `INFORMATION_SCHEMA.TABLES` 核对 SQL schema 和目标表。IRIS namespace 不等于 SQL schema。
6. 环境不明、映射不唯一、目标表缺失或归属不符时询问具体缺失信息；不按历史别名猜测，不在多个库间碰运气。

首次完成“运行环境 → Nacos 数据源 → usql 连接名 → 当前库/schema → 项目表归属”核对后，同一任务可复用结果；切换环境或连接时重新核对。连接迁移时针对来源配置的测试不等于完成业务项目归属核对。

## CLI 入口

```bash
usql --version
usql --help

# 非交互执行单条查询；在 SQL 中按目标方言限制行数
usql -X -w -q -J -v ON_ERROR_STOP=1 '<已核对连接名>' -c 'SELECT ...'

# 复杂 SQL 使用文件，避免 shell 展开 SQL 中的特殊字符
usql -X -w -q -J -v ON_ERROR_STOP=1 '<已核对连接名>' -f '<查询.sql的绝对路径>'

# IRIS：显式指定 DSN 文件；SQL 单引号避免 shell 展开 $NAMESPACE
ODBCINI="$HOME/.odbc.ini" usql -X -w -q -J -v ON_ERROR_STOP=1 \
  '<已核对 IRIS 连接名>' -c 'SELECT $NAMESPACE AS current_namespace'

# 用户已授权的多语句 DML，在同一连接和事务中执行
usql -X -w -q -v ON_ERROR_STOP=1 -1 '<已核对连接名>' < '<已核对变更.sql的绝对路径>'
```

- `-X` 禁止加载启动脚本；`-w` 禁止交互询问密码；`-q` 减少提示；`-J` 输出查询 JSON；`ON_ERROR_STOP=1` 保证遇错停止并返回非零状态，不能省略。连接别名是位置参数，`-c` 是 SQL，`-f` 是 SQL 文件。
- 查询需要结构化结果时，每次一条 SELECT 最容易解析。`-f` 支持多语句脚本；多个结果集会连续输出，不能把整个 stdout 当成一个 JSON 数组。
- 每次 CLI 调用建立独立连接。不能分次调用 `BEGIN`、DML、`COMMIT` 组成事务，也不能跨调用依赖会话变量或临时表。相关操作需要相同会话时放在同一脚本执行；需要事务时走标准输入，见下文版本限制。
- 先按日期、机构等业务条件缩小范围，再查询必要列。默认探查最多取 100 行，使用目标方言的 `LIMIT`、`TOP` 或 `FETCH FIRST`；usql 没有 `--limit`。需要总数时另查 COUNT。
- SQL 文件按工作区 `AGENTS.md` 放入 `.mixed/temp/yyyy-MM-dd/`，不得写入凭据。不要将用户文本直接拼入 shell；按目标方言校验、转义 SQL 值。usql 变量替换不等于 JDBC 参数绑定，业务模板中的占位符必须先正确填充。
- 通过调用端的进程超时约束等待，例如 Python `subprocess.run(..., timeout=30)`；工具提前返回 session ID 不等于已终止进程。客户端被终止不保证服务端已取消；写入超时后先核对结果，不自动重试。

## 结果与失败处理

- 同时检查退出码、stderr 和 stdout；成功退出且结果符合预期才报告成功，不把错误或空 stdout 当成“0 行”。错误摘要脱敏，不能回显账号、密码、主机或完整连接串。
- usql 0.21.4 的单条 SELECT 在 `-J` 下返回行对象数组，空结果为 `[]`。DDL/DML 可能返回命令状态而不是 JSON 数组；执行后通过只读查询核对结构或实际影响，不能仅凭无报错断言业务正确。
- 达到取数上限时标记可能截断；查询结果中的列名大小写按实际数据库处理。
- 19 位 ID 在 SQL 内转换成字符串：MySQL `CAST(rec_id AS CHAR)`，Oracle `TO_CHAR(rec_id)`，SQL Server/IRIS `CAST(rec_id AS VARCHAR(30))`。后续解析和条件生成保持字符串，不经 JavaScript Number 转换。
- 精确金额必要时按方言转换为字符列；不要将浮点近似值当作数据库原始金额。日期、时区、零日期和二进制字段按当前驱动核对，不承诺与 JDBC 完全相同。
- 区分安装、连接验证、schema 验证和真实业务查询。驱动存在但网络不通时明确报告连接未验证，不伪装类型或自动换库。

## 写入与结构变更

查询、SQL 示例和脚本生成不构成写入授权。用户明确要求 INSERT/UPDATE/DELETE、CREATE/ALTER/DROP TABLE、索引等操作时，在已授权范围内执行；先核对目标、条件/对象、现有结构、影响范围与权限，不额外重复索取已有授权。

- 单条变更也可能自动提交；执行前完成范围检查，执行后核对实际结果。
- `-q` 会隐藏 DML 命令状态；需要逐条影响行数时，在对应语句后单独一行写 `\echo step_1 :ROW_COUNT` 等明确标签。该值是上一条语句的驱动影响行数，回滚后不能当作已提交行数；整体事务成功后再报告提交结果。
- 多语句 DML 优先使用同一次 `-1 -v ON_ERROR_STOP=1 < 文件`，也可由调用端将 SQL 文件内容传给 stdin。**0.21.4 的 `-1 -f` 存在已复现的事务失效问题**：文件执行创建的 handler 未继承事务，出错前语句可能已提交；事务脚本禁止使用 `-f` 或 `\i` 引入文件。脚本不要再含 `BEGIN`、`COMMIT`、`ROLLBACK` 或切换连接命令。失败必须停止，事务内变更回滚；仍需核对目标驱动、表引擎和分布式事务限制。
- `-1` 使用数据库事务，不会让非事务表、跨分片限制或隐式提交语句获得原子性。MySQL、Oracle 等数据库的 DDL 可能隐式提交，不能承诺建表/改表可以随 DML 一起回滚。
- 建表和改表执行目标数据库原生 DDL，usql 不翻译方言，也不生成 Flyway 版本；需要迁移脚本时继续使用对应业务 Skill。
- 无法保证任务要求的原子性时说明具体限制并交付脚本，不静默降级为逐条提交。未经核对不自动补偿删除或重新执行已部分生效的变更。

## 安装与维护

缺少命令、驱动或连接配置时，读取 [references/setup.md](references/setup.md)。按名称增量配置，保留既有连接，禁止猜测凭据、覆盖冲突或全量替换。

本 Skill 接替旧 `bs-jdbc-query`。源仓库统一维护本入口；移除旧 Skill 安装入口并同步安装副本的操作按用户既有工作流执行，业务 Skills 统一引用本 Skill。
