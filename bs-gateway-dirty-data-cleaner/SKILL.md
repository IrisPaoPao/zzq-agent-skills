---
name: bs-gateway-dirty-data-cleaner
description: 数据网关(saas-data-gateway)采集任务脏数据清理 + 重采进度重置技能。给采集任务中文名/id 或场景名/id + 业务日期范围，自动解析 gather_id/system_id/scenario_id、探测实际有数据的月份(gwb_original_*_YYYYMM 物理分表)，生成删除顺序正确的清理 SQL(item→session→batch→data→index)+重采进度重置(gwb_gather_page_record/gwb_gather_log)，或预检后逐条执行。触发场景：用户说"清理脏数据""重新采集""重采""删除采集任务数据""清掉网关数据重采"，或提到 gwb_original / gwb_gather_page_record / 采集断点重置等。区别于 bs-gateway-scene-sql-generator（仅注册场景，不删数据）。
---

# 数据网关脏数据清理 + 重采 / Data Gateway Dirty-Data Cleanup + Re-collect

## Functionality / 功能说明

针对数据网关（saas-data-gateway）某采集任务入库的脏数据，自动完成：**解析采集任务 ID → 探测实际有数据的月份 → 生成/执行清理 SQL（删脏数据 + 重置采集进度），让任务可重新采集回填**。

清理对象与顺序固定（不可乱）：
1. `gwb_original_item_YYYYMM`（明细子表，无 LIST 子表的场景删 0 行）
2. `gwb_data_source_session`（会话，非分表，按 index 的 session_id 定位）
3. `gwb_data_source_batch`（批次，非分表）
4. `gwb_original_data_YYYYMM`（数据主表，分表）
5. `gwb_original_index_YYYYMM`（索引表，分表，最后删）

重采进度重置（默认全量）：
- `gwb_gather_page_record`（断点续采进度，**必须删**，否则重采只从断点往后、不回补历史）
- `gwb_gather_log`（采集日志，展示用，可选，默认清理）

> 详见 `references/table-map.md`：表→列→分片速查、删除顺序理由、`scenario_id` vs `scene_id` 列名陷阱。

## Input / 输入

- **采集任务标识**（二选一，skill 自动判断）：
  - 采集任务中文名（`gwb_gather_config.gather_name`，模糊匹配）或 `rec_id`；或
  - 场景中文名（`gwb_scene.name`）或 `rec_id`，由场景反查该场景下的采集任务让你选。
- **业务日期范围** `:DATE_FROM` ~ `:DATE_TO`（左闭右开，如 `2026-02-01` ~ `2026-06-01`）。
- **执行模式**（每次让你选）：
  - 生成 SQL 脚本（默认，安全）；或
  - 预检 + 逐条执行（不可回滚，需谨慎确认）。

## 关键约束（必须遵守）

- **库别名不写死**：先用 `mcp__bs-jdbc-tool__list_databases` 列出可用库，让用户确认/选目标库（gwb_* 表通常在 `dev-mysql-saas02`，但由用户确认）。
- **TDSQL 分布式库，用逻辑表名让代理自动路由**：目标库是 TDSQL，`gwb_original_{index,data,item}` 按 `transaction_date` 分片。**直接用逻辑表名** `gwb_original_index` / `gwb_original_data` / `gwb_original_item` 查询和删除，加上 `transaction_date` 范围条件，TDSQL 代理会自动路由到对应分片。**绝不能用物理分片名** `gwb_original_index_tdsql_subp202602` 之类——代理会报 `Table does not exist`（实测确认）。`information_schema.tables` 里虽然能看到 `tdsql_subp*` 物理分片名，但那是底层分片、不可直接查询。
- **列名陷阱**：`gwb_original_index` / `gwb_data_source_batch` 用 `scenario_id`；`gwb_original_data` 用 `scene_id`。两者含义一致（都 = `gwb_scene.rec_id`）但列名不同，复制 SQL 时勿混。
- **无事务保护**：`jdbc_query` 是 autoCommit=true，每条立即提交、不可回滚；`jdbc_batch` 当前损坏不可用。所以"预检+执行"模式逐条执行无事务保护，必须先预检 + 用户明确确认。生成脚本模式则建议用户在客户端事务内执行（核对行数再 COMMIT，有疑问 ROLLBACK）。
- **采集任务→场景的关联**：`gwb_gather_config` 无 scene_id 列，需经 `system_id → gwb_docking_system.scene_id → gwb_scene.rec_id` 解析出 `scenario_id`。
- **重采起始日期** = `gwb_gather_config.start_time`；删了 `gwb_gather_page_record` 后下次执行即从 start_time 重头采。
- **雪花 id 精度陷阱（致命）**：`rec_id` / `system_id` 等是 19 位雪花 id，MCP 返回的 JSON 数字会被 JS 浮点截断（如真实 `6203537512649891840` 被显示成 `6203537512649892000`，末 4 位失真）。**绝不能用返回的数字 id 拼后续 SQL**，否则查询条件错误、删错或删不到。解析 ID 时必须额外 `SELECT CAST(rec_id AS CHAR) ...` 取字符串真值，后续所有 SQL 都用字符串真值（数字列直接写裸数字字面量即可，MySQL 会按数值比较；务必用 CAST 出来的字符串，不要用截断后的数字）。

## Processing Flow / 处理流程

### Step 0：确认目标库
调 `list_databases`，列出可用库别名，让用户确认目标库（gwb_* 表所在库）。

### Step 1：解析采集任务 ID
- 若给的是采集任务名/id：
  ```sql
  SELECT CAST(gc.rec_id AS CHAR) AS gather_id, gc.gather_name,
         CAST(gc.system_id AS CHAR) AS system_id, gc.start_time,
         CAST(ds.scene_id AS CHAR) AS scenario_id, ds.system_name, sc.name AS scene_name
  FROM gwb_gather_config gc
  LEFT JOIN gwb_docking_system ds ON ds.rec_id = gc.system_id
  LEFT JOIN gwb_scene sc ON sc.rec_id = ds.scene_id
  WHERE gc.gather_name LIKE '%<名称>%'   -- 或 gc.rec_id = <id>
  ```
  模糊匹配返回多条 → 列出（gather_id / gather_name / system_name）让用户选。
- 若给的是场景名/id：
  ```sql
  SELECT CAST(sc.rec_id AS CHAR) AS scenario_id, sc.name AS scene_name,
         CAST(ds.rec_id AS CHAR) AS system_id, ds.system_name,
         CAST(gc.rec_id AS CHAR) AS gather_id, gc.gather_name
  FROM gwb_scene sc
  LEFT JOIN gwb_docking_system ds ON ds.scene_id = sc.rec_id
  LEFT JOIN gwb_gather_config gc ON gc.system_id = ds.rec_id
  WHERE sc.name LIKE '%<名称>%'   -- 或 sc.rec_id = <id>
  ```
  列出该场景下所有采集任务，让用户选要清理哪个。

> ⚠️ 上面用 `CAST(... AS CHAR)` 是为了拿到雪花 id 的字符串真值（避免 JS 精度丢失）。后续所有 SQL 的 id 条件都用这里的字符串真值。

解析完成后，**展示解析结果**（gather_id / system_id / scenario_id / gather_name / system_name / scene_name / start_time）让用户确认，再继续。

### Step 2：探测实际有数据的月份（用逻辑表 GROUP BY）
直接查逻辑表，按月聚合，确认该任务在哪些月份有数据：
```sql
SELECT DATE_FORMAT(transaction_date,'%Y%m') AS ym, COUNT(*) AS cnt,
       MIN(transaction_date) AS min_d, MAX(transaction_date) AS max_d
FROM gwb_original_index
WHERE scenario_id = :SCENE_ID AND system_id = :SYSTEM_ID
  AND transaction_date >= DATE ':DATE_FROM'
  AND transaction_date <  DATE ':DATE_TO'
GROUP BY DATE_FORMAT(transaction_date,'%Y%m')
ORDER BY ym;
```
- `cnt=0`（无任何行）→ 该范围无数据，提示用户确认范围/任务是否正确，不生成删除。
- 展示各月行数让用户核对，确认无误后再生成/执行删除。

> 删除时不需要逐月拆分——TDSQL 代理按 `transaction_date` 范围自动路由到所有相关分片，一条带范围条件的 DELETE 即可覆盖整个日期范围。GROUP BY 月份仅用于让用户核对数据分布。

### Step 3：让用户选执行模式
- 生成 SQL 脚本（默认）；或
- 预检 + 逐条执行。

### Step 4a：生成 SQL 脚本（默认）
用逻辑表名 + `transaction_date` 范围条件，TDSQL 代理自动路由到所有相关分片，**一组语句覆盖整个日期范围**（不需逐月拆分）。删除顺序固定：

```sql
-- ########## 清理 transaction_date ∈ [:DATE_FROM, :DATE_TO) ##########

-- 预检（各表待删行数）
SELECT COUNT(*) AS item_cnt FROM gwb_original_item
 WHERE pid IN (SELECT rec_id FROM gwb_original_data
               WHERE scene_id=:SCENE_ID AND system_id=:SYSTEM_ID
                 AND transaction_date>=DATE ':DATE_FROM' AND transaction_date<DATE ':DATE_TO');

-- 1) 明细子表（无 LIST 子表的场景删 0 行）
DELETE FROM gwb_original_item
 WHERE pid IN (SELECT rec_id FROM gwb_original_data
               WHERE scene_id=:SCENE_ID AND system_id=:SYSTEM_ID
                 AND transaction_date>=DATE ':DATE_FROM' AND transaction_date<DATE ':DATE_TO');

-- 2) 会话（非分表，按 index 的 session_id 定位）
DELETE FROM gwb_data_source_session
 WHERE rec_id IN (SELECT DISTINCT session_id FROM gwb_original_index
                  WHERE scenario_id=:SCENE_ID AND system_id=:SYSTEM_ID
                    AND transaction_date>=DATE ':DATE_FROM' AND transaction_date<DATE ':DATE_TO');

-- 3) 批次（非分表）
DELETE FROM gwb_data_source_batch
 WHERE scenario_id=:SCENE_ID AND system_id=:SYSTEM_ID
   AND bus_date>=DATE ':DATE_FROM' AND bus_date<DATE ':DATE_TO';

-- 4) 数据主表（分表，逻辑表名自动路由）
DELETE FROM gwb_original_data
 WHERE scene_id=:SCENE_ID AND system_id=:SYSTEM_ID
   AND transaction_date>=DATE ':DATE_FROM' AND transaction_date<DATE ':DATE_TO';

-- 5) 索引表（分表，最后删）
DELETE FROM gwb_original_index
 WHERE scenario_id=:SCENE_ID AND system_id=:SYSTEM_ID
   AND transaction_date>=DATE ':DATE_FROM' AND transaction_date<DATE ':DATE_TO';
```

重采进度重置（默认全量）：
```sql
-- ---- A. 断点续采进度（必须删，否则重采不回补历史）----
DELETE FROM gwb_gather_page_record
 WHERE gather_id=:GATHER_ID AND system_id=:SYSTEM_ID;

-- ---- B. 采集日志（可选，默认清理；按业务日期范围限定）----
DELETE FROM gwb_gather_log
 WHERE gather_id=:GATHER_ID AND system_id=:SYSTEM_ID
   AND bus_start_date>=DATE ':DATE_FROM' AND bus_start_date<DATE ':DATE_TO';
```

脚本头/尾加事务提示：
```sql
-- ⚠️ 执行前：① 已备份 ② 确认本批数据可重新采集 ③ 建议在事务内执行，核对行数无误再 COMMIT，有疑问则 ROLLBACK。
-- START TRANSACTION;  -- (MySQL 客户端)
-- ... 上述 DELETE ...
-- 核对：SELECT COUNT(*) FROM gwb_original_data WHERE scene_id=:SCENE_ID AND system_id=:SYSTEM_ID AND transaction_date>=DATE ':DATE_FROM' AND transaction_date<DATE ':DATE_TO';  -- 应返回 0
-- COMMIT;   -- 行数不符或有疑问则 ROLLBACK;
```

### Step 4b：预检 + 逐条执行
1. 对每个有数据的月份、每个待删表，先 `SELECT COUNT(*)` 展示待删行数。
2. 任一行数异常（为 0 或异常大）→ 停下让用户复核。
3. 用户明确确认后，用 `jdbc_query` 逐条执行 DELETE（autoCommit，不可回滚，明确提示风险）。
4. 每条执行后报告影响行数。

## 安全护栏（始终生效）

- 任何 DELETE 执行前，必须先展示解析出的 ID + 各表预检行数。
- 必须用户明确确认后才执行 DELETE（执行模式）。
- 每个 DELETE 都按 `system_id` + `scenario_id`/`scene_id` + 日期范围限定，**绝不裸 `DELETE FROM`**。
- 生成脚本模式不执行任何 DML，只输出文本。
- 明确标注 `index` 用 `scenario_id`、`data` 用 `scene_id`。

## Notes / 注意事项

1. **目标库**：gwb_* 表通常在 `dev-mysql-saas02`（MySQL saas_02 库），但库别名由用户确认，不写死。
2. **不备份**：本 skill 不做备份，由用户在客户端自行备份后再执行。
3. **不触发采集**：本 skill 只清场 + 重置进度，实际重采由用户/调度触发。
4. **兄弟 skill 区别**：`bs-gateway-scene-sql-generator` 只注册场景（gwb_scene 等 INSERT），不删数据；本 skill 只删数据 + 重置进度。
5. **分表后缀**：`_YYYYMM`，分片键 `transaction_date`，由 ShardingSphere `DateShardingAlgorithm`（pattern `yyyyMM`）生成。
