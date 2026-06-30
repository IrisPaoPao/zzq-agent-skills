---
name: bs-reconciliation-data-cleaner
description: 对账业务(saas-reconciliation-business)按主题清理对账数据技能。给对账主题中文名/theme_id(+可选业务日期范围)，自动解析 theme_id、探测实际有数据的月份(rec_recon_result_YYYYMM 等按月物理分表)，生成删除顺序正确的清理 SQL(逐月分表 DELETE 结果/核对/疑点表 + 任务/进度/日志 + 疑点处理/关联 + 重置疑点策略 progress_date)，或预检后逐条执行。触发场景：用户说"清理对账数据""删除对账主题数据""删对账结果""清掉某主题的对账记录""重新对账前清数据"，或提到 rec_recon_result / rec_check_data / rec_recon_susp / theme_id 清理等。区别于 bs-gateway-dirty-data-cleaner（清的是数据网关 gwb_* 采集脏数据，本 skill 清的是对账 rec_* 业务数据）。
---

# 对账数据清理 / Reconciliation Data Cleanup

## Functionality / 功能说明

针对对账业务（saas-reconciliation-business）某**对账主题（theme）**产生的对账数据，自动完成：**解析 theme_id → 探测实际有数据的月份 → 生成/执行清理 SQL（删对账结果/核对/疑点等数据 + 重置疑点策略进度），让该主题可重新对账回填**。

清理对象分三类（顺序见下）：

**A. 按月分表（物理表 `_YYYYMM`，需逐月清理）**
1. `rec_recon_result_YYYYMM`（对账结果表）
2. `rec_check_data_YYYYMM`（核对数据表）
3. `rec_recon_susp_YYYYMM`（对账疑点表）

**B. 非分表（任务 / 进度 / 日志）**
4. `rec_reconciliation_task`（对账任务）
5. `rec_recon_progress_log`（对账进度日志）
6. `rec_reconciliation_log`（对账日志）
7. `rec_reconciliation_progress`（对账进度）
8. `rec_recon_prog_appe`（对账进度追加）

**C. 非分表（疑点处理 / 关联）**
9. `rec_suspicious_processe_item`（疑点处理项）
10. `rec_suspicious_relate_data`（疑点关联数据）

**D. 重置（非删除）**
11. `rec_suspicious_strategy` → `UPDATE ... SET progress_date = NULL`（疑点策略进度重置，**不是删行**）

> 详见 `references/table-map.md`：表→分表/列→清理方式速查、与数据网关 skill 的区别、雪花 id 精度陷阱。

## Input / 输入

- **对账主题标识**（二选一，skill 自动判断）：
  - 主题中文名（`rec_rulepolicy_theme.theme`，模糊匹配）；或
  - `theme_id`（= `rec_rulepolicy_theme.rec_id`，19 位雪花 id）。
- **业务日期范围**（可选）`:DATE_FROM` ~ `:DATE_TO`（左闭右开，如 `2026-01-01` ~ `2026-07-01`）。
  - **不给范围 = 清理该主题全部月份**（探测出的所有有数据月份）。
- **执行模式**（每次让你选）：
  - 生成 SQL 脚本（默认，安全）；或
  - 预检 + 逐条执行（不可回滚，需谨慎确认）。

## 关键约束（必须遵守）

- **库别名不写死 + 库可能在 Oracle**：先用 `mcp__bs-jdbc-tool__list_databases` 列出可用库，让用户确认/选目标库。**rec_* 对账表既可能在 MySQL（`dev-mysql-saas02`）也可能在 Oracle（`dev-oracle`）**——实测某些测试主题只存在于 Oracle 库。在 saas02 查不到主题时，务必让用户确认是否在 Oracle，再用 Oracle 方言重试（见下「Oracle 方言适配」）。
- **Oracle 方言适配（目标库是 dev-oracle 时必须用）**：
  - 取雪花 id 字符串真值：用 `TO_CHAR(rec_id)`（**不是** MySQL 的 `CAST(rec_id AS CHAR)`）。
  - 列分表/库内表名：查 `user_tables`（列 `table_name`，**大写**），**不是** `information_schema.tables`。
  - `LIKE` 里下划线 `_` 是通配符，匹配真实表名/主题名时加 `ESCAPE '\'` 并把字面下划线写成 `\_`（如 `'REC\_RECON\_RESULT\_%' ESCAPE '\'`）。
  - 表名/列名在 `user_tables`/`user_tab_columns` 里是**大写**（`REC_RECON_RESULT_202606`），但 DELETE/SELECT 语句里大小写不敏感、可照常用小写。
- **按月物理分表（app 侧 ShardingSphere，非 TDSQL 代理）**：`rec_recon_result` / `rec_check_data` / `rec_recon_susp` 是 ShardingSphere 在应用层按 `transaction_date` 分的**物理月表**（如 `rec_recon_result_202506`），**这些物理表在库里真实存在、可直接查询和删除**。
  - **直接对 MCP 用逻辑表名 `rec_recon_result`（无后缀）查询会报 Table doesn't exist** —— 因为 MCP 直连底层 MySQL，绕过了 ShardingSphere，库里没有不带后缀的逻辑表。
  - **必须先探测物理月表名再逐月删**：查 `information_schema.tables` 拿到实际存在的 `_YYYYMM` 物理表，每个月生成一条独立 DELETE。**这是与 `bs-gateway-dirty-data-cleaner` 最大的差异**（网关那边是 TDSQL，用逻辑表名一条范围 DELETE 即可；这里不行）。
- **雪花 id 精度陷阱（致命）**：`theme_id` / `rec_id` 是 19 位雪花 id，MCP 返回的 JSON 数字会被 JS 浮点截断（末几位失真）。**绝不能用返回的数字 id 拼后续 SQL**。解析主题时必须 `SELECT CAST(rec_id AS CHAR) AS theme_id ...` 取字符串真值，后续所有 SQL 都用该字符串真值（数字列直接写裸数字字面量，MySQL 按数值比较；务必用 CAST 出来的字符串，不要用截断后的数字）。
- **无事务保护**：`jdbc_query` 是 autoCommit=true，每条立即提交、不可回滚；`jdbc_batch` 当前不可靠。"预检+执行"模式逐条无事务保护，必须先预检 + 用户明确确认。生成脚本模式则建议用户在客户端事务内执行（核对行数再 COMMIT，有疑问 ROLLBACK）。
- **疑点策略是 UPDATE 不是 DELETE**：`rec_suspicious_strategy` 只重置 `progress_date = NULL`，**不要 DELETE 这张表**（删了会丢策略配置）。
- **按月分表 DELETE 不带 transaction_date 也能删干净**：因为表名本身已按月隔离，单张物理月表内 `WHERE theme_id = :THEME_ID` 即清空该月该主题数据；若用户指定了日期范围，可额外加 `transaction_date` 条件做更精确的范围限定。

## Processing Flow / 处理流程

### Step 0：确认目标库
调 `list_databases`，列出可用库别名，让用户确认目标库（rec_* 表所在库）。**可能是 MySQL（`dev-mysql-saas02`）或 Oracle（`dev-oracle`）**——在一个库查不到主题时，主动让用户确认是否在另一个库。下面 SQL 给出 MySQL / Oracle 两套写法。

### Step 1：解析 theme_id
- 若给的是主题名（**MySQL**）：
  ```sql
  SELECT CAST(rec_id AS CHAR) AS theme_id, theme, tenant_code, org_id, states, check_start_date, check_end_date
  FROM rec_rulepolicy_theme
  WHERE theme LIKE '%<名称>%';
  ```
  **Oracle** 版（`TO_CHAR` 取真值；名称含 `_` 时加 `ESCAPE`）：
  ```sql
  SELECT TO_CHAR(rec_id) AS theme_id, theme, tenant_code, org_id, states, check_start_date, check_end_date
  FROM rec_rulepolicy_theme
  WHERE theme LIKE '%<名称>%' ESCAPE '\';
  ```
  模糊匹配返回多条 → 列出（theme_id / theme / org_id）让用户选。
- 若给的是 theme_id：把上面 `WHERE` 换成 `WHERE rec_id = <theme_id>`。

> ⚠️ 用 `CAST(rec_id AS CHAR)`（MySQL）/ `TO_CHAR(rec_id)`（Oracle）拿雪花 id 字符串真值（避免 JS 精度丢失）。后续所有 SQL 的 theme_id 条件都用这里的字符串真值。

解析完成后，**展示解析结果**（theme_id / theme / org_id / check_start_date~check_end_date）让用户确认，再继续。

### Step 2：探测实际有数据的物理月表
先列出库里实际存在的按月分表，再确认哪些月份对该主题有数据。

1) 列出物理月表（**MySQL**）：
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND (table_name LIKE 'rec_recon_result_%'
    OR table_name LIKE 'rec_check_data_%'
    OR table_name LIKE 'rec_recon_susp_%')
ORDER BY table_name;
```
**Oracle** 版（查 `user_tables`，表名大写，`_` 加 `ESCAPE`）：
```sql
SELECT table_name FROM user_tables
WHERE table_name LIKE 'REC\_RECON\_RESULT\_%' ESCAPE '\'
   OR table_name LIKE 'REC\_CHECK\_DATA\_%' ESCAPE '\'
   OR table_name LIKE 'REC\_RECON\_SUSP\_%' ESCAPE '\'
ORDER BY table_name;
```

2) 定位有数据的月份。**分表数量可能很多（实测 Oracle 库有 72 个月 202101~202612），切忌逐张 COUNT**。用一条 `UNION ALL` 批量 COUNT、只留 `cnt>0`，一次定位：
```sql
SELECT * FROM (
  SELECT '202601' ym, COUNT(*) cnt FROM rec_recon_result_202601 WHERE theme_id = :THEME_ID UNION ALL
  SELECT '202602',     COUNT(*)     FROM rec_recon_result_202602 WHERE theme_id = :THEME_ID UNION ALL
  -- ... 覆盖候选月份（按主题创建时间/日期范围缩小候选，通常近几个月）...
  SELECT '202612',     COUNT(*)     FROM rec_recon_result_202612 WHERE theme_id = :THEME_ID
) WHERE cnt > 0 ORDER BY ym;
```
- 先按主题创建时间 / 用户给的日期范围缩小候选月份（如只扫某一年的 12 个月），避免拼几十条。
- 用 `rec_recon_result_*` 定位到有数据的月份后，对同样月份的 `rec_check_data_*` / `rec_recon_susp_*` 各 COUNT 一次核对行数。
- 若给了日期范围：只取范围覆盖到的月份表，并可在 COUNT/DELETE 中加 `transaction_date` 条件。
- 展示有数据的月份 + 各表行数让用户核对；全为 0 → 提示主题/范围无数据，确认后再决定，不生成删除。

> 月份后缀以**库里实际存在且 cnt>0 的物理表**为准（不同环境月表不同），不要凭空拼月份。

### Step 3：让用户选执行模式
- 生成 SQL 脚本（默认）；或
- 预检 + 逐条执行。

### Step 4a：生成 SQL 脚本（默认）
对探测到有数据的每个月，逐月生成分表 DELETE；非分表表各一条。删除顺序见下（先子后主、策略最后 UPDATE）。

下例以月份 `202506`、`202512` 为例（**实际按 Step 2 探测到的月表替换**），`:THEME_ID` 用字符串真值：

```sql
-- ⚠️ 执行前：① 已备份 ② 确认本主题数据可重新对账 ③ 建议在事务内执行，核对行数无误再 COMMIT，有疑问 ROLLBACK。
-- START TRANSACTION;  -- (MySQL 客户端)

-- ===== A. 按月分表（逐月，月份以库内实际物理表为准）=====
-- 1) 对账结果表
DELETE FROM rec_recon_result_202506 WHERE theme_id = :THEME_ID;
DELETE FROM rec_recon_result_202512 WHERE theme_id = :THEME_ID;
-- 2) 核对数据表
DELETE FROM rec_check_data_202506  WHERE theme_id = :THEME_ID;
DELETE FROM rec_check_data_202512  WHERE theme_id = :THEME_ID;
-- 3) 对账疑点表
DELETE FROM rec_recon_susp_202506  WHERE theme_id = :THEME_ID;
DELETE FROM rec_recon_susp_202512  WHERE theme_id = :THEME_ID;

-- ===== B. 任务 / 进度 / 日志（非分表）=====
DELETE FROM rec_reconciliation_task     WHERE theme_id = :THEME_ID;
DELETE FROM rec_recon_progress_log       WHERE theme_id = :THEME_ID;
DELETE FROM rec_reconciliation_log       WHERE theme_id = :THEME_ID;
DELETE FROM rec_reconciliation_progress  WHERE theme_id = :THEME_ID;
DELETE FROM rec_recon_prog_appe          WHERE theme_id = :THEME_ID;

-- ===== C. 疑点处理 / 关联（非分表）=====
DELETE FROM rec_suspicious_processe_item WHERE theme_id = :THEME_ID;
DELETE FROM rec_suspicious_relate_data   WHERE theme_id = :THEME_ID;

-- ===== D. 疑点策略（重置进度日期，非删除！）=====
UPDATE rec_suspicious_strategy SET progress_date = NULL WHERE theme_id = :THEME_ID;

-- 核对：SELECT COUNT(*) FROM rec_recon_result_202506 WHERE theme_id = :THEME_ID;  -- 应返回 0
-- COMMIT;   -- 行数不符或有疑问则 ROLLBACK;
```

> 若用户指定了日期范围，按月分表的 DELETE 可加 `AND transaction_date >= DATE ':DATE_FROM' AND transaction_date < DATE ':DATE_TO'` 做范围内精确删除；非分表表（任务/进度/日志/疑点处理）一般整主题清理，是否按日期限定由用户确认。

### Step 4b：预检 + 逐条执行
1. 对每张待删表，先 `SELECT COUNT(*) WHERE theme_id = :THEME_ID` 展示待删行数。
2. 任一行数异常（全为 0 或异常大）→ 停下让用户复核。
3. 用户明确确认后，用 `jdbc_query` 逐条执行 DELETE/UPDATE（autoCommit，不可回滚，明确提示风险）。
4. 每条执行后报告影响行数。
5. 顺序：先按月分表三类，再非分表任务/进度/日志，再疑点处理/关联，最后 `rec_suspicious_strategy` 的 UPDATE。

## 安全护栏（始终生效）

- 任何 DELETE/UPDATE 执行前，必须先展示解析出的 theme_id + 各表预检行数。
- 必须用户明确确认后才执行（执行模式）。
- 每个 DELETE 都按 `theme_id` 限定，**绝不裸 `DELETE FROM`**。
- 按月分表只删 Step 2 探测到**实际存在**的物理月表，不凭空拼月份。
- `rec_suspicious_strategy` 永远是 UPDATE progress_date，**绝不 DELETE**。
- 生成脚本模式不执行任何 DML，只输出文本。

## Notes / 注意事项

1. **目标库**：rec_* 表可能在 `dev-mysql-saas02`（MySQL）或 `dev-oracle`（Oracle），库别名由用户确认、不写死。实测某些测试主题只在 Oracle 库；在一个库查不到主题时主动确认是否在另一个库，并切换对应方言（`TO_CHAR` / `user_tables` / `ESCAPE`）。
2. **不备份**：本 skill 不做备份，由用户在客户端自行备份后再执行。
3. **不触发对账**：本 skill 只清场 + 重置策略进度，实际重新对账由用户/调度触发。
4. **兄弟 skill 区别**：`bs-gateway-dirty-data-cleaner` 清的是数据网关 `gwb_*` 采集脏数据（TDSQL，逻辑表名）；本 skill 清的是对账 `rec_*` 业务数据（app 侧 ShardingSphere，物理月表逐月删）。
5. **分表后缀**：`_YYYYMM`，分片键 `transaction_date`，ShardingSphere 应用层路由；MCP 直连底层库，必须用物理月表名。Oracle 库分表月份范围可能极大（实测 202101~202612 共 72 月），探测时用 `UNION ALL` 批量 COUNT 而非逐张查。
6. **旧版单表**：历史环境曾用 `rec_reconciliation_result` / `rec_transaction_check_data` / `rec_reconciliation_suspicious` 等非分表命名；当前为按月分表版本。若 Step 2 在 information_schema 里发现的是旧命名，按实际表名清理。
