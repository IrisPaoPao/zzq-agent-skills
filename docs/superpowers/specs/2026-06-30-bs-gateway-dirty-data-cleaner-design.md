# 数据网关脏数据清理 + 重采 skill 设计

> 日期：2026-06-30
> skill 名称：`bs-gateway-dirty-data-cleaner`
> 仓库：`/Users/zhangzhengqing/work/project/zzq-agent-skills`
> 目标项目：`/Users/zhangzhengqing/work/project/vasService/saas-data-gateway`
> 参考文档：`数据网关脏数据清理与重采-通用模板.md`（Obsidian）

## Context / 背景

数据网关（saas-data-gateway）的采集任务入库数据有时出错（字段全 NULL、数据错位等），需要**清掉旧数据 + 重置采集进度**，让任务重新跑回填正确数据。

当前这套清理流程是手工的：要查 `gwb_gather_config` / `gwb_docking_system` / `gwb_scene` 解析出 gather_id / system_id / scenario_id，再按月份分表（`gwb_original_*_YYYYMM`）逐月拼删除 SQL，删除顺序固定（item → session → batch → data → index），最后删采集进度（`gwb_gather_page_record`，断点续采必须删，否则重采不回头补历史）和采集日志（`gwb_gather_log`，可选）。手工易错（列名 `scenario_id` vs `scene_id` 混淆、分表后缀写错、漏删进度导致重采无效）。

本 skill 把这套流程自动化：给采集任务名/id（或场景名/id）+ 业务日期范围，自动解析 ID、探测实际有数据的月份、生成完整清理+重采 SQL 脚本；或预检后逐条执行（用户选择）。

## 目标与非目标

**目标**
- 按中文名/id 解析采集任务（或按场景反查），自动得到 gather_id / system_id / scenario_id。
- 给日期范围，自动探测实际有数据的月份（枚举物理分表，跳过空月份）。
- 生成符合模板的、删除顺序正确的清理 SQL + 重采进度重置 SQL。
- 支持两种执行模式：生成脚本（默认）/ 预检+逐条执行（用户选）。

**非目标**
- 不做备份（由用户在客户端自行备份后再执行）。
- 不修复脏数据本身，只清理+重置进度让任务重采。
- 不触发采集任务实际执行（重采由用户/调度触发，本 skill 只清场）。
- 不接管 ShardingSphere 分片逻辑——MCP 直连物理库，必须用物理分表名。

## 关键约束与事实（来自代码与 MCP 探查）

### 表结构（实体类确认的列名）
- `gwb_gather_config`：`rec_id`(=gather_id)、`gather_name`(中文名)、`system_id`、`start_time`。**无 scene_id 列**，场景经 `system_id → gwb_docking_system.scene_id → gwb_scene.rec_id` 间接关联。
- `gwb_docking_system`：`rec_id`(=system_id)、`system_name`、`scene_id`(=scenario_id)。
- `gwb_scene`：`rec_id`、`name`(中文场景名)。
- `gwb_gather_page_record`：`gather_id`、`system_id`、`bus_start_date`（断点续采进度，**重采必删**）。
- `gwb_gather_log`：`gather_id`、`system_id`、`bus_start_date`（展示用，可选清理）。
- `gwb_data_source_session`：`rec_id`（被 index.session_id 引用，非分表）。
- `gwb_data_source_batch`：`scenario_id`、`system_id`、`bus_date`（非分表）。
- `gwb_original_index_YYYYMM`：`scenario_id`、`system_id`、`transaction_date`(分片键)、`session_id`、`gather_id`。
- `gwb_original_data_YYYYMM`：`scene_id`、`system_id`、`transaction_date`、`data_source_index_id`。
- `gwb_original_item_YYYYMM`：`pid`(→ original_data.rec_id)、`transaction_date`。
- **列名陷阱**：`index` 用 `scenario_id`，`data` 用 `scene_id`，含义一致列名不同。

### 重采机制（GatherServiceImpl）
- 重采起始日期 = `gwb_gather_config.start_time`。
- 要强制完整重采，必须删 `gwb_gather_page_record`（断点），否则只从断点往后采、不回补历史。`gwb_gather_log` 仅展示用，删不删不影响重采逻辑。

### 分表（TDSQL，实测修正）
- 目标库是 **TDSQL 分布式数据库**，`gwb_original_{index,data,item}` 按 `transaction_date` 分片。
- **用逻辑表名查询/删除**：直接用 `gwb_original_index` / `gwb_original_data` / `gwb_original_item` + `transaction_date` 范围条件，TDSQL 代理自动路由到相关分片，无需逐月拆分。
- **不能用物理分片名**（实测确认）：`information_schema.tables` 能看到 `gwb_original_index_tdsql_subp202602`、`..._tdsql_subp_auto_202607`、`gwb_original_data_202506` 等物理分片名，但直接查它们会报 `Proxy ERROR: Table does not exist`。
- 月份探测：查逻辑表 `GROUP BY DATE_FORMAT(transaction_date,'%Y%m')` 看各月行数，仅用于让用户核对数据分布。

> 注：早期设计假设"MCP 直连物理库、必须枚举 `_YYYYMM` 物理分表"，实测证明错误——TDSQL 代理只接受逻辑表名。

### 雪花 id 精度陷阱（实测修正）
- `rec_id` / `system_id` 等 19 位雪花 id，MCP 返回的 JSON 数字会被 JS 浮点截断（实测 `6203537512649891840` → `6203537512649892000`，末 4 位失真）。
- 解析 ID 时必须 `SELECT CAST(rec_id AS CHAR)` 取字符串真值，后续 SQL 用真值，绝不用截断数字。

### MCP 工具能力（bs-jdbc-tool）
- `list_databases`：列出可用库别名。当前有 `dev-mysql`、`dev-mysql-saas02`、`dev-oracle`。**库别名不写死**，skill 运行时列出让用户确认/选目标库（gwb_* 表通常在 dev-mysql-saas02，但由用户确认）。
- `jdbc_query`：单条 SQL，支持 SELECT/INSERT/UPDATE/DELETE/DDL，**autoCommit=true，每条立即提交，不可回滚**。
- `jdbc_batch`：**当前损坏**（`Unknown action: executeBatch`），不可用。所以"预检+执行"模式只能逐条用 jdbc_query，无事务保护。

## 设计

### 1. 入口与 ID 解析
接受两种入口，skill 自动判断：
- **采集任务入口**：给 `gather_name`（中文，模糊匹配）或 `rec_id`。
  - 查 `gwb_gather_config` → 得 `gather_id`(rec_id)、`system_id`、`gather_name`、`start_time`。
  - 联 `gwb_docking_system` by `system_id` → 得 `scenario_id`(scene_id)、`system_name`。
  - 联 `gwb_scene` by `rec_id=scenario_id` → 得 `scene_name`。
- **场景入口**：给 scene `name`（中文）或 `rec_id`。
  - 查 `gwb_scene` → `scenario_id`、`scene_name`。
  - 联 `gwb_docking_system` by `scene_id` → `system_id`、`system_name`。
  - 列 `gwb_gather_config` by `system_id` → 列出该场景下所有采集任务（id+名），让用户选要清理哪个。

模糊匹配返回多条 → 列出（id + 名称 + system_name）让用户选。解析完成后，**先展示解析结果（gather_id/system_id/scenario_id/gather_name/system_name/scene_name）让用户确认**，再继续。

### 2. 月份探测（用逻辑表 GROUP BY）
1. 用户给业务日期范围 `:DATE_FROM` ~ `:DATE_TO`（左闭右开）。
2. 直接查逻辑表按月聚合：
   `SELECT DATE_FORMAT(transaction_date,'%Y%m') ym, COUNT(*) cnt FROM gwb_original_index WHERE scenario_id=:SCENE_ID AND system_id=:SYSTEM_ID AND transaction_date>=DATE ':DATE_FROM' AND transaction_date<DATE ':DATE_TO' GROUP BY ym`
3. 展示各月行数让用户核对；总数为 0 则提示确认范围/任务，不生成删除。

> 删除不需逐月拆分——TDSQL 代理按 `transaction_date` 范围自动路由。月份探测仅用于核对数据分布。删除条件统一用 `transaction_date >= :DATE_FROM AND < :DATE_TO` 范围限定。

### 3. 生成 SQL（删除顺序固定，逻辑表名一组覆盖整个范围）
```sql
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
重采准备（默认全量）：
```sql
-- A. 断点续采进度（必须删，否则重采不回补历史）
DELETE FROM gwb_gather_page_record
 WHERE gather_id=:GATHER_ID AND system_id=:SYSTEM_ID;
-- B. 采集日志（可选，默认清理；按业务日期范围限定）
DELETE FROM gwb_gather_log
 WHERE gather_id=:GATHER_ID AND system_id=:SYSTEM_ID
   AND bus_start_date>=DATE ':DATE_FROM' AND bus_start_date<DATE ':DATE_TO';
```
每段前附 `SELECT COUNT(*)` 预检；脚本头/尾加事务与 COMMIT/ROLLBACK 提示（参照模板文档）。

### 4. 两种执行模式（用户每次选）
- **生成脚本（默认）**：输出完整 SQL 脚本（含预检 COUNT + 事务/COMMIT/ROLLBACK 注释），用户拿去客户端自行执行。最安全，符合文档事务要求。
- **预检+执行**：先用 SELECT COUNT 展示各表待删行数 → 用户明确确认 → 用 jdbc_query 逐条执行 DELETE（autoCommit，不可回滚，明确提示风险）。任一预检行数异常（如为 0 或异常大）则停下让用户复核。

### 5. 安全护栏（始终生效）
- 任何 DELETE 执行前，必须先展示解析出的 ID + 各表预检行数。
- 必须用户明确确认后才执行 DELETE（执行模式）。
- 每个 DELETE 都按 `system_id` + `scenario_id`/`scene_id` + 日期范围限定，绝不裸 `DELETE FROM`。
- 明确标注 `index` 用 `scenario_id`、`data` 用 `scene_id`。
- 生成脚本模式不执行任何 DML，只输出文本。

## 文件结构

```
zzq-agent-skills/bs-gateway-dirty-data-cleaner/
  SKILL.md              # frontmatter + 双语说明 + SQL 模板 + MCP 用法
  references/
    table-map.md        # 表→列→分片 速查 + 删除顺序理由 + 列名陷阱
```

### SKILL.md frontmatter（中文，含触发词，标注与兄弟 skill 区别）
```yaml
---
name: bs-gateway-dirty-data-cleaner
description: 数据网关(saas-data-gateway)采集任务脏数据清理 + 重采进度重置技能。给采集任务中文名/id 或场景名/id + 业务日期范围，自动解析 gather_id/system_id/scenario_id、探测实际有数据的月份(gwb_original_*_YYYYMM 物理分表)，生成删除顺序正确的清理 SQL(item→session→batch→data→index)+重采进度重置(gwb_gather_page_record/gwb_gather_log)，或预检后逐条执行。触发场景：用户说"清理脏数据""重新采集""重采""删除采集任务数据""清掉网关数据重采"，或提到 gwb_original / gwb_gather_page_record / 采集断点重置等。区别于 bs-gateway-scene-sql-generator（仅注册场景，不删数据）。
---
```

## 验证方式

1. **触发验证**：在 saas-data-gateway 项目中说"清理 XX 采集任务的脏数据，重新采集"，确认 skill 被触发。
2. **ID 解析**：给一个真实 gather_name，确认解析出的 gather_id/system_id/scenario_id 与库一致。
3. **月份探测**：给一个跨月范围，确认只列出实际有数据的月份，空月份被跳过并 log。
4. **生成脚本**：确认输出 SQL 删除顺序正确、列名（scenario_id vs scene_id）无误、含预检 COUNT 和事务提示。可将脚本贴回客户端在事务内执行验证。
5. **预检+执行**：在一个可重采的测试任务上跑预检模式，确认先展示行数、需确认才执行、执行后该任务能从 start_time 重采。
6. **安全**：确认任何模式下都不会裸删、都需确认。
