# 数据库方言映射

仓库里 TDSQL 和 Oracle 是基准；KingBase / DM / Vastbase / GaussDB / GBase8c 都是 Oracle 基准衍生而来。常规需求只生成 TDSQL + Oracle，其他厂商由后续工具脚本派生。

## TDSQL → Oracle 类型映射

| TDSQL / MySQL                      | Oracle                       | 备注                                              |
|------------------------------------|------------------------------|---------------------------------------------------|
| `tinyint`                          | `NUMBER(4)`                  | 0/1 状态位也走这个                                |
| `smallint`                         | `NUMBER(6)`                  |                                                   |
| `int` / `integer`                  | `NUMBER(11)`                 |                                                   |
| `bigint`                           | `NUMBER(20)`                 |                                                   |
| `decimal(p, s)`                    | `NUMBER(p, s)`               |                                                   |
| `float` / `double`                 | `NUMBER` 或 `BINARY_DOUBLE`  | 沿用相邻脚本                                      |
| `varchar(n)`                       | `VARCHAR2(n CHAR)`           | 加 `CHAR` 修饰，按字符算长度                      |
| `char(n)`                          | `CHAR(n CHAR)`               |                                                   |
| `text`                             | `VARCHAR2(4000)` 或 `CLOB`   | 仓库习惯用 `VARCHAR2(4000)`，过大才用 `CLOB`      |
| `longtext` / `mediumtext`          | `CLOB`                       |                                                   |
| `date`                             | `DATE`                       |                                                   |
| `datetime` / `timestamp`           | `DATE` 或 `TIMESTAMP`        | 看相邻脚本，多数产品用 `DATE`                     |
| `blob` / `longblob`                | `BLOB`                       |                                                   |
| `json`                             | `VARCHAR2(4000)` 或 `CLOB`   | 仓库没有 JSON 列，按字符串存                      |

## DDL 语法差异

| 操作                  | TDSQL                                                              | Oracle                                                                                  |
|---------------------- |--------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| 加字段                | `ALTER TABLE t ADD COLUMN c VARCHAR(64) DEFAULT NULL COMMENT '..'` | `ALTER TABLE t ADD (c VARCHAR2(64 CHAR) DEFAULT NULL); COMMENT ON COLUMN t.c IS '..'`   |
| 改类型                | `ALTER TABLE t MODIFY COLUMN c VARCHAR(100)`                       | `ALTER TABLE t MODIFY (c VARCHAR2(100 CHAR))`                                           |
| 改默认值              | `ALTER TABLE t MODIFY COLUMN c VARCHAR(100) DEFAULT 'x'`           | 拆两条：先改类型，再 `ALTER TABLE t MODIFY (c DEFAULT 'x')`                             |
| 改 NOT NULL / NULL    | `ALTER TABLE t MODIFY COLUMN c VARCHAR(100) NOT NULL`              | `ALTER TABLE t MODIFY c NULL` / `ALTER TABLE t MODIFY c NOT NULL`（用 `nullable()` 判） |
| 删字段                | `ALTER TABLE t DROP COLUMN c`                                      | `ALTER TABLE t DROP COLUMN c`                                                           |
| 加索引                | `ALTER TABLE t ADD INDEX idx_x (col1) USING BTREE`                 | `CREATE INDEX idx_x ON t (col1 ASC) TABLESPACE <INDEX_TBS>`                              |
| 加唯一索引            | `ALTER TABLE t ADD UNIQUE INDEX uk_x (col1) USING BTREE`           | `CREATE UNIQUE INDEX uk_x ON t (col1 ASC) TABLESPACE <INDEX_TBS>`                        |
| 删索引                | `ALTER TABLE t DROP INDEX idx_x`                                   | `DROP INDEX idx_x`                                                                      |
| 删唯一约束            | `ALTER TABLE t DROP INDEX uk_x`                                    | `ALTER TABLE t DROP CONSTRAINT uk_x`                                                    |
| 表注释                | 行内 `COMMENT = '..'`                                              | 表外 `COMMENT ON TABLE t IS '..'`                                                       |
| 列注释                | 字段定义后 `COMMENT '..'`                                          | 表外 `COMMENT ON COLUMN t.c IS '..'`                                                    |

## Oracle 表空间约定

仓库里 Oracle 建表 / 建索引必须显式指定表空间。**表空间名各产品不一样，绝不要写死**——进入流程后从该产品最近的 Oracle 脚本里读：

```bash
grep -hoE 'TABLESPACE [A-Z_]+' 行业应用/business/<product>/<version>/*.groovy | sort -u
```

通常会得到一对：数据表空间（建表时 `... TABLESPACE <DATA_TBS>`）和索引表空间（建索引时 `... TABLESPACE <INDEX_TBS>`）。同一产品内不同业务级别（基础字典 vs 大流水表）的表空间可能不同——按相邻同类型表的写法沿用最稳。

不确定时，直接看该产品最近建的同类型 Oracle 表用了什么表空间——表空间一致比"理论正确"重要。

## Oracle 衍生 → KingBase / DM / Vastbase

仓库里这三家基本由工具从 Oracle 脚本派生，无需手写。规则：

- **Oracle → Oracle 提交：** `VARCHAR2(N)` 写成 `VARCHAR2(N CHAR)`（已经是 CHAR 形式则保留）。
- **Oracle → KingBase：** `VARCHAR2(N)` → `VARCHAR2(N CHAR)`；`to_clob(...)` 函数需要替换为 KingBase 等价写法。
- **Oracle → DM：** `VARCHAR2(N)` → `VARCHAR2(N CHAR)`。
- **Oracle → Vastbase / GaussDB / GBase8c：** 主要靠 Navicat 等工具批量转，类型保持兼容。

如果用户特别要求生成 KingBase / DM 脚本，先写 Oracle 版本作为基准，再做上述替换。

## TDSQL 衍生 → MySQL / DRDS

- **不分表：** TDSQL 脚本可直接当 MySQL / DRDS 用，无需修改。
- **分表：** 工具会按 `sharding.yml` 把分表脚本展开，`MySQL` 一侧把 `_${monthSuffix}` / `_${yearSuffix}` / `_${numSuffix}` 替换实表名；`DRDS` 一侧改用 `DBPARTITION BY YYYYMM(...)` 子句。

## SQL 自身的约束

- **注释里不能有 `;`：** `executeMultiCommand` 会按 `;` 拆 SQL，注释里多一个分号就会把后半段当下一条 SQL 执行。
- **不要写裸双引号：** Oracle 把双引号包裹的标识符当大小写敏感的精确匹配。MySQL 可以接受但建议统一去掉。
- **TDSQL 字符集必须显式：** `DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci`。
- **表名 / 索引名 ≤ 30 字符：** Oracle 限制；同一实例索引名全局唯一。
- **`number(*)` 不可用：** Oracle 列定义时必须给精度。
- **不要把多条 `ALTER` 塞进一个 `executeMultiCommand`：** 第一条成功后断连，剩下的不会重试（重试时外层 `if` 已经为 false）。
