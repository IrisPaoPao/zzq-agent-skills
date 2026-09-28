# usql / MySQL 查询踩坑清单（交接用）

环境：usql 0.21.4（xo/usql 自建，含 mysql/oracle/sqlserver/odbc），目标 MySQL 8（连接别名 `menhu_mysql`，172.18.165.164:3306，schema `menhu`）。
推荐 DSN 参数：`?charset=utf8mb4&parseTime=true&loc=Local`（可从驱动层根治时间扫描与 emoji 编码问题）。
以下坑均为本次实测复现，不是文档推断。

## 1. stdin 末尾语句无分号 → 静默不执行（最危险）

```bash
usql -X -w -q -J -v ON_ERROR_STOP=1 menhu_mysql   # stdin 传 SQL
```

- `SELECT 1`（无 `;`）→ stdout 空、**退出码 0**，语句被丢弃，不是报错。
- `SELECT 1;` → 正常返回。
- 多语句时只有**最后一条**受影响，前面的语句正常执行，所以极易漏检。

结论：拼 SQL 时必须保证 `rstrip()` 后以 `;` 结尾再补 `\n`。任何"执行成功"判断不能只看退出码，要核对 stdout/影响行数。

## 2. 缺 `-J` → 输出是文本表格，JSON 解析静默失败

```bash
usql -X -w -q -J -v ON_ERROR_STOP=1 ...   # 有 -J: [{"rid":"82..."}]
usql -X -w -q    -v ON_ERROR_STOP=1 ...   # 无 -J: " rid \n----\n 82... \n(2 rows)"
```

正则 `\[.*\]` 匹配不到时若用 `if m else []` 兜底，会把"查询失败"变成"0 行"，
进而把"已存在"判成"不存在"，导致重复 INSERT 主键冲突或漏插。
结论：JSON 解析失败必须抛错终止，禁止默认空列表。

## 3. `-J` 与 DML 的输出不是 JSON 数组

- `-J` 只对 SELECT 返回 JSON 数组；DDL/DML 返回命令状态文本。
- **不要把 DML 输出直接塞进 JSON 解析器**。
- **推荐做法**：需要影响行数时，紧跟一条 `SELECT ROW_COUNT() AS affected_rows;`：
  ```sql
  UPDATE menhu.oper_openapi_exter_interface SET ... WHERE ...;
  SELECT ROW_COUNT() AS affected_rows;
  ```
  这样输出始终保持为规范 JSON 数组 `[{"affected_rows": 1}]`，解析器逻辑完全统一。
- 若用 usql 变量 `\echo :ROW_COUNT`，输出的纯文本会破坏 JSON 格式，在开启 `-J` 时不建议混合使用。

## 4. 0.21.4 的 `-1 -f` 事务失效 & DDL 隐式提交

- **`-1 -f file.sql` bug**：`handler.Include` 只传连接不传事务，出错前的语句可能已提交。事务脚本**只能**走标准输入：`usql ... -1 < file.sql`，脚本内不再显式写 BEGIN/COMMIT。
- **MySQL DDL 隐式提交（Implicit Commit）**：`-1` 仅对纯 DML（INSERT/UPDATE/DELETE）有效。若脚本内混有 `CREATE TABLE`、`ALTER TABLE`、`TRUNCATE`、`CREATE INDEX` 等 DDL，MySQL 会强制隐式提交之前的事务，无法回滚！迁移脚本必须将 DDL 与 DML 阶段解耦。
- **连接无状态**：每次 CLI 调用是独立连接，不能跨调用组事务、不能依赖会话变量/临时表。

## 5. 19 位 rec_id 精度与 WHERE 索引保护

- **精度截断**：Java/JS/jq 的 Number 无法安全表示 19 位雪花 ID（超 2^53-1）。SELECT 结果集必须 `CAST(rec_id AS CHAR)`，解析和下游传递全程当字符串，禁止过浮点。
- **索引避坑**：写 `WHERE rec_id = 820000000000000001` 或 `WHERE rec_id = '820000000000000001'`（MySQL 会做安全类型转换且走主键/索引）。**严禁在 WHERE 左侧写 `WHERE CAST(rec_id AS CHAR) = ...`**，这会导致索引失效全表扫描！

## 6. 时间列扫描报错

```text
Scan error on column index 4, name "rec_created_time": unsupported Scan,
storing driver.Value type []uint8 into type *time.Time
```

- **根治方案（推荐）**：在连接串 DSN 加参数 `?parseTime=true&loc=Local`，驱动自动将 datetime 转为 time.Time，`-J` 序列化为标准 RFC3339 字符串，无需改 SQL。
- **兜底方案（无法改 DSN 时）**：避免直接 `SELECT *` 包含时间列，手动用 `DATE_FORMAT(rec_created_time, '%Y-%m-%d %H:%i:%s') AS rec_created_time` 或 `CAST(... AS CHAR)` 转字符串。

## 7. 数据模型坑：rec_id 不是单表唯一

`oper_openapi_exter_*` 系列表同一 rec_id 可有多行——`org_id='-1'`（全局）与
`org_id='6271940501925093648'（单位）各一份，主键是 (rec_id, org_id)。
- 存在性判断 `WHERE rec_id = ?` 会把"单位副本存在"当成"全局存在"。
- 删除脚本不带 org 条件时会把全局+单位副本一起删。
之前迁移脚本 `notExist("select * from t where rec_id = X")` 就是这个写法，语义上"任意 org 存在即跳过"，重跑可漏插单位副本。

## 8. 执行顺序敏感与干跑（Dry-Run）标准模式

迁移包常见模式是"先 DELETE 旧重复配置，再 notExist 幂等 INSERT"。
- **顺序坑**：存在性检查必须放在 DELETE **之后**执行，否则按删除前状态判断会全部跳过。
- **干跑不可在内存模拟**：若干跑时跳过真实删除、仅在应用层靠快照判断，结论与真实执行必定不一致。
- **标准干跑范式（事务回滚）**：通过真正的数据库事务跑全流程，最后强制 ROLLBACK，由数据库引擎给出真实的变更与冲突检验：
  ```bash
  usql -X -w -q -J -v ON_ERROR_STOP=1 menhu_mysql << 'EOF'
  BEGIN;
  DELETE FROM menhu.oper_openapi_exter_interface WHERE ...;
  SELECT ROW_COUNT() AS deleted_rows;
  -- 执行 INSERT 逻辑 ...
  SELECT COUNT(*) AS check_after_insert FROM ...;
  ROLLBACK; -- 强制回滚，不产生任何脏数据
  EOF
  ```

## 9. 文件名含方括号被 zsh 当 glob

```bash
wc -l V1.2.2_..._TDSQL_[1.2.2].groovy   # zsh: no matches found
wc -l 'V1.2.2_..._TDSQL_[1.2.2].groovy' # 需引号，或 setopt nonomatch
```

## 10. 同库多 schema

同一实例里 `menhu`（门户）与 `hangye`（行业）都有 `oper_openapi_*` 表，
必须先 `USE menhu;` 或全限定 `menhu.table`，并用 `SELECT DATABASE()` / 
`information_schema.tables` 核对归属，不能默认第一个 schema。

## 通用防护建议

- **输入防御**：每个执行器必须自动补齐末尾 `;` 与 `\n`。
- **输出防御**：强制带 `-J`，必须严格 `json.loads`；一旦解析失败或 stderr 不为空立即异常退出，禁止 `if m else []` 弱容错。
- **精度防御**：所有雪花 ID / 19 位整数在 SELECT 时一律 `CAST(... AS CHAR)`，解析后作为 str 处理；WHERE 条件中保留原始数字字面量，禁止在列上包 CAST。
- **原子性防御**：批量修改走 `usql -1 < script.sql`（标准输入），注意脚本内严禁混杂 DDL 导致隐式提交。
- **干跑防御**：干跑严禁在代码中“脑补/模拟”删除后状态，必须使用 `BEGIN; ...; ROLLBACK;` 真实跑一遍验证行数与约束。

## 附：推荐的防御型 Python 执行封装

其他 Agent 在编写 Python 自动化脚本时，建议直接复用以下防御封装，避免重复踩坑：

```python
import json
import subprocess
from typing import Any, List, Dict

def run_usql_query(sql: str, db_alias: str = "menhu_mysql") -> List[Dict[str, Any]]:
    """
    防御型 usql SELECT 执行器：
    1. 自动补全末尾分号与换行，防止静默丢弃
    2. 强制 -J 输出 JSON，失败立即抛异常
    3. 严格校验退出码与 stderr
    """
    sql_clean = sql.strip()
    if not sql_clean.endswith(";"):
        sql_clean += ";"
    sql_clean += "\n"

    cmd = ["usql", "-X", "-w", "-q", "-J", "-v", "ON_ERROR_STOP=1", db_alias]
    proc = subprocess.run(
        cmd,
        input=sql_clean,
        text=True,
        capture_output=True
    )

    if proc.returncode != 0:
        raise RuntimeError(f"usql 执行失败 (code {proc.returncode}):\n{proc.stderr}\nSQL:\n{sql_clean}")

    stdout = proc.stdout.strip()
    if not stdout:
        return []

    try:
        data = json.loads(stdout)
        if not isinstance(data, list):
            raise ValueError(f"预期 JSON 列表，实际收到: {type(data)}")
        return data
    except json.JSONDecodeError as e:
        raise RuntimeError(f"usql 返回非合法 JSON (可能缺少 -J 或混入 DML 文本输出):\n{stdout}") from e
```
