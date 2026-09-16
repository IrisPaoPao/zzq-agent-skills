---
name: bs-reconciliation-data-cleaner
description: 对账业务(saas-reconciliation-business)按主题清理对账数据技能。给对账主题中文名/theme_id(+可选业务日期范围)，自动解析 theme_id、探测实际有数据的月份(rec_recon_result_YYYYMM 等按月物理分表)，生成删除顺序正确的清理 SQL(逐月分表 DELETE 结果/核对/疑点表 + 任务/进度/日志 + 疑点处理/关联 + 重置疑点策略 progress_date)，或按已验证的事务能力执行。触发场景：用户说"清理对账数据""删除对账主题数据""删对账结果""清掉某主题的对账记录""重新对账前清数据"，或提到 rec_recon_result / rec_check_data / rec_recon_susp / theme_id 清理等。区别于 bs-gateway-dirty-data-cleaner（清的是数据网关 gwb_* 采集脏数据，本 skill 清的是对账 rec_* 业务数据）。
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
- **执行模式**（复用用户已明确的选择，未指定则只生成 SQL）：
  - 生成 SQL 脚本（默认，安全）；或
  - 执行前预检（执行能力须单独验证）。

## 关键约束（必须遵守）

- **连接定位**：实际查库统一使用 `bs-database-query`，先由运行环境和 Nacos 定位 usql 连接名，再确认 schema 与目标表。用户明确提供连接名时复用该选择；不按历史环境猜测，不查不到就换库。
- **Oracle 方言适配（实际数据库类型为 Oracle 时使用）**：
  - 取雪花 id 字符串真值：用 `TO_CHAR(rec_id)`（**不是** MySQL 的 `CAST(rec_id AS CHAR)`）。
  - 列分表/库内表名：查 `user_tables`（列 `table_name`，**大写**），**不是** `information_schema.tables`。
  - `LIKE` 里下划线 `_` 是通配符，匹配真实表名/主题名时加 `ESCAPE '\'` 并把字面下划线写成 `\_`（如 `'REC\_RECON\_RESULT\_%' ESCAPE '\'`）。
  - 表名/列名在 `user_tables`/`user_tab_columns` 里是**大写**（`REC_RECON_RESULT_202606`），但 DELETE/SELECT 语句里大小写不敏感、可照常用小写。
- **按月物理分表（app 侧 ShardingSphere，非 TDSQL 代理）**：`rec_recon_result` / `rec_check_data` / `rec_recon_susp` 是 ShardingSphere 在应用层按 `transaction_date` 分的**物理月表**（如 `rec_recon_result_202506`），**这些物理表在库里真实存在、可直接查询和删除**。
  - **直接对数据库客户端用逻辑表名 `rec_recon_result`（无后缀）查询会报 Table doesn't exist** —— 因为 客户端直连底层 MySQL，绕过了 ShardingSphere，库里没有不带后缀的逻辑表。
  - **必须先探测物理月表名再逐月删**：查 `information_schema.tables` 拿到实际存在的 `_YYYYMM` 物理表，每个月生成一条独立 DELETE。**这是与 `bs-gateway-dirty-data-cleaner` 最大的差异**（网关那边是 TDSQL，用逻辑表名一条范围 DELETE 即可；这里不行）。
- **雪花 id 精度陷阱（致命）**：`theme_id` / `rec_id` 是 19 位雪花 id，JSON 中的大整数会被 JS 浮点截断（末几位失真）。**绝不能用返回的数字 id 拼后续 SQL**。解析主题时必须 `SELECT CAST(rec_id AS CHAR) AS theme_id ...` 取字符串真值，后续所有 SQL 都用该字符串真值（数字列直接写裸数字字面量，MySQL 按数值比较；务必用 CAST 出来的字符串，不要用截断后的数字）。
- **执行能力边界**：生成 SQL 为默认模式；用户要求执行多表清理时，按 `bs-database-query` 核对目标数据库和事务范围，使用同一次 `usql -X -w -q -v ON_ERROR_STOP=1 -1 '<连接名>' < '<脚本路径>'`。0.21.4 禁止用 `-1 -f` 执行事务脚本；先确认事务表和跨分片限制，不支持所需原子性时说明限制，不拆成逐条提交。
- **疑点策略是 UPDATE 不是 DELETE**：`rec_suspicious_strategy` 只重置 `progress_date = NULL`，**不要 DELETE 这张表**（删了会丢策略配置）。
- **日期范围必须贯穿预检与删除**：只有用户要求整主题清理时才单用 `theme_id`；指定日期范围后，COUNT、DELETE 和删除后核对都必须使用相同的 `transaction_date` 左闭右开条件，选择月表不能代替日期过滤。

## Processing Flow / 处理流程

### Step 0：确认目标库
先按 `bs-database-query` 完成环境 → Nacos → usql 连接 → schema/表归属核对，再通过 `usql` 执行下列单条查询。SQL 方言以实际连接类型为准。

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

解析完成后，**展示解析结果**（theme_id / theme / org_id / check_start_date~check_end_date）供用户核对；只有多条候选或目标不一致时才询问，唯一明确的结果继续后续步骤。

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

2) 对三类表分别探测，再取有数据月份的并集。不能仅根据结果表有数据的月份决定是否检查核对/疑点表，否则会漏掉“尚未产生结果”或部分失败留下的数据。

从上一步实际表名中严格筛选 `rec_recon_result_YYYYMM`、`rec_check_data_YYYYMM`、`rec_recon_susp_YYYYMM` 及有效月份。用户指定范围时只取相交月份；未指定时覆盖所有实际存在的月份，不能按主题创建时间排除历史业务数据。表多时按适度批次使用 `UNION ALL`，每行包含真实表名和月份，避免一个结果为零就跳过其他表。

以下示例针对指定日期范围；只生成实际存在表的分支，日期值按目标方言填写：

```sql
SELECT table_name, ym, cnt FROM (
  SELECT 'rec_recon_result_202601' AS table_name, '202601' AS ym, COUNT(*) AS cnt
  FROM rec_recon_result_202601
  WHERE theme_id = :THEME_ID AND transaction_date >= DATE ':DATE_FROM' AND transaction_date < DATE ':DATE_TO'
  UNION ALL
  SELECT 'rec_check_data_202601', '202601', COUNT(*) FROM rec_check_data_202601
  WHERE theme_id = :THEME_ID AND transaction_date >= DATE ':DATE_FROM' AND transaction_date < DATE ':DATE_TO'
  UNION ALL
  SELECT 'rec_recon_susp_202601', '202601', COUNT(*) FROM rec_recon_susp_202601
  WHERE theme_id = :THEME_ID AND transaction_date >= DATE ':DATE_FROM' AND transaction_date < DATE ':DATE_TO'
) counts_by_table WHERE cnt > 0 ORDER BY ym, table_name;
```

保留“表名 + 月份 + 范围 + 行数”的待删清单，据此生成删除，不假设三类表在同一月份都存在。三类月表全为零仍需独立检查请求范围内的任务、日志和疑点处理等非分表数据；全部待处理对象都为空时报告无数据，不生成无意义变更。

### Step 3：确定执行模式
用户已明确要求执行时，在授权范围内继续预检；仅要求脚本或未明确执行时只生成 SQL，不重复询问模式。

### Step 4a：生成 SQL 脚本（默认）
对探测到有数据的每个月，逐月生成分表 DELETE；非分表表各一条。删除顺序见下（先子后主、策略最后 UPDATE）。

下例仅用于用户明确要求“整主题清理”，以月份 `202506`、`202512` 为例（实际按 Step 2 的待删清单替换）。指定日期范围时必须为每张有日期列的表添加同一范围条件，不能直接使用下面的整主题 SQL。`:THEME_ID` 用字符串真值：

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

> 用户指定日期范围时，按月分表的 DELETE 必须加 `AND transaction_date >= DATE ':DATE_FROM' AND transaction_date < DATE ':DATE_TO'`。非分表须核对真实业务日期列，不能把创建时间当业务日期；有匹配日期列则限定范围，没有直接范围字段时说明无法安全按日期直删，不自动扩为整主题删除。疑点策略进度是整主题状态，局部日期清理不自动置空，须明确其重跑影响并取得该范围的授权。

### Step 4b：执行前预检
1. 对每张待删表，使用与最终 DELETE/UPDATE 完全相同的条件执行 `SELECT COUNT(*)`，展示待处理行数。
2. 任一行数异常（全为 0 或异常大）→ 停下让用户复核。
3. 用户明确要求执行后，按 `bs-database-query` 核对事务范围，通过标准输入在单次 usql 事务中执行；不要使用 `-1 -f`，也不要拆成逐条自动提交。执行后核对实际清理和重置结果。
4. 按公共 Skill 在语句后输出带步骤标签的 `ROW_COUNT`，整体事务成功后报告各条已提交的影响行数；失败回滚不能报告为删除成功。
5. 顺序：先按月分表三类，再非分表任务/进度/日志，再疑点处理/关联，最后 `rec_suspicious_strategy` 的 UPDATE。

## 安全护栏（始终生效）

- 任何 DELETE/UPDATE 执行前，必须先展示解析出的 theme_id + 各表预检行数。
- 实际变更必须有用户明确执行授权；复用当前任务已给授权，目标或范围发生变化时重新核对。
- 每个 DELETE 都按 `theme_id` 限定，**绝不裸 `DELETE FROM`**。
- 按月分表只删 Step 2 探测到**实际存在**的物理月表，不凭空拼月份。
- `rec_suspicious_strategy` 永远是 UPDATE progress_date，**绝不 DELETE**。
- 生成脚本模式不执行任何 DML，交付文件放在 `.mixed/deliverables/yyyy-MM-dd/`。

## Notes / 注意事项

1. **目标库**：以公共查询 Skill 核对的环境、usql 连接名和 schema 为准，不使用历史别名推断。
2. **不备份**：本 skill 不做备份，由用户在客户端自行备份后再执行。
3. **不触发对账**：本 skill 只清场 + 重置策略进度，实际重新对账由用户/调度触发。
4. **兄弟 skill 区别**：`bs-gateway-dirty-data-cleaner` 清的是数据网关 `gwb_*` 采集脏数据（TDSQL，逻辑表名）；本 skill 清的是对账 `rec_*` 业务数据（app 侧 ShardingSphere，物理月表逐月删）。
5. **分表后缀**：`_YYYYMM`，分片键 `transaction_date`，ShardingSphere 应用层路由；客户端直连底层库，必须用物理月表名。Oracle 库分表月份范围可能极大（实测 202101~202612 共 72 月），探测时用 `UNION ALL` 批量 COUNT 而非逐张查。
6. **旧版单表**：历史环境曾用 `rec_reconciliation_result` / `rec_transaction_check_data` / `rec_reconciliation_suspicious` 等非分表命名；当前为按月分表版本。若 Step 2 在 information_schema 里发现的是旧命名，按实际表名清理。
