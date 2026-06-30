# 对账数据清理 — 表→分表/列→清理方式 速查

## 涉及的表

| 表 | 是否分表 | 角色 | 清理方式 | 关联键 |
|---|---|---|---|---|
| `rec_recon_result_YYYYMM` | 按月分表 | 对账结果 | 逐月 DELETE | theme_id、transaction_date |
| `rec_check_data_YYYYMM` | 按月分表 | 核对数据 | 逐月 DELETE | theme_id、transaction_date |
| `rec_recon_susp_YYYYMM` | 按月分表 | 对账疑点 | 逐月 DELETE | theme_id、transaction_date |
| `rec_reconciliation_task` | 非分表 | 对账任务 | DELETE | theme_id |
| `rec_recon_progress_log` | 非分表 | 对账进度日志 | DELETE | theme_id |
| `rec_reconciliation_log` | 非分表 | 对账日志 | DELETE | theme_id |
| `rec_reconciliation_progress` | 非分表 | 对账进度 | DELETE | theme_id |
| `rec_recon_prog_appe` | 非分表 | 对账进度追加 | DELETE | theme_id |
| `rec_suspicious_processe_item` | 非分表 | 疑点处理项 | DELETE | theme_id、transaction_date |
| `rec_suspicious_relate_data` | 非分表 | 疑点关联数据 | DELETE | theme_id、transaction_date |
| `rec_suspicious_strategy` | 非分表 | 疑点策略 | **UPDATE progress_date=NULL（不删！）** | theme_id |
| `rec_rulepolicy_theme` | 非分表 | 对账主题（解析用，不删） | — | rec_id(=theme_id)、theme |

## 解析链（解析 theme_id 用）

```
rec_rulepolicy_theme.rec_id = theme_id          -- 主题主键
rec_rulepolicy_theme.theme  = 主题中文名（模糊匹配）
其余所有 rec_* 业务表 .theme_id = rec_rulepolicy_theme.rec_id
```

主题中文名 → theme_id：
```sql
SELECT CAST(rec_id AS CHAR) AS theme_id, theme, org_id
FROM rec_rulepolicy_theme WHERE theme LIKE '%<名称>%';
```

## 删除顺序（建议）

`结果/核对/疑点(分表) → 任务/进度/日志 → 疑点处理/关联 → 疑点策略(UPDATE)`

- 各表都以 `theme_id` 独立过滤，相互无外键级联，顺序不像网关那样强约束；但建议先删数据明细类、最后做策略 UPDATE，便于核对。
- `rec_suspicious_strategy` 永远最后、且永远是 UPDATE progress_date = NULL，**不能 DELETE**（删了丢策略配置，无法重新对账）。

## 按月分表（app 侧 ShardingSphere，物理月表）

- `rec_recon_result` / `rec_check_data` / `rec_recon_susp` 由 ShardingSphere 在**应用层**按 `transaction_date` 分成物理月表（`_YYYYMM`），物理表在库里**真实存在**。
- **MCP 直连底层 MySQL，绕过 ShardingSphere** → 不存在不带后缀的逻辑表，查 `rec_recon_result`（无后缀）会报 `Table doesn't exist`。
- 必须先查 `information_schema.tables` 拿实际物理月表名，逐月生成独立 DELETE。
- 单张物理月表内 `WHERE theme_id = :THEME_ID` 即清空该月该主题数据；指定日期范围时可加 `transaction_date` 条件做精确限定。

### ★ 与 bs-gateway-dirty-data-cleaner 的关键差异

| | 数据网关 cleaner | 对账 cleaner（本 skill）|
|---|---|---|
| 库类型 | TDSQL 分布式（代理路由）| 普通 MySQL + 应用层 ShardingSphere |
| 分表查询方式 | **逻辑表名** + 范围条件，代理自动路由，一条 DELETE 覆盖全范围 | **物理月表名** 逐月，一月一条 DELETE |
| 物理分片名 | 不可直接查（`tdsql_subp*` 报错）| 物理月表 `_YYYYMM` 必须直接用 |
| 过滤键 | scenario_id/scene_id/system_id + transaction_date | theme_id（+可选 transaction_date）|

## Oracle 库适配（dev-oracle）

实测：部分对账主题只存在于 Oracle 库 `dev-oracle`，且三类表同样按月物理分表（实测 202101~202612 共 72 个月）。Oracle 与 MySQL 的差异：

| 用途 | MySQL（saas02）| Oracle（dev-oracle）|
|---|---|---|
| 雪花 id 取真值 | `CAST(rec_id AS CHAR)` | `TO_CHAR(rec_id)` |
| 列库内表名 | `information_schema.tables` + `table_schema=DATABASE()` | `user_tables`（表名**大写**）|
| LIKE 中的下划线 | 可不转义 | `_` 是通配符，须 `... LIKE 'REC\_RECON\_RESULT\_%' ESCAPE '\'` |
| 表名大小写 | 小写 | 字典里大写，DML 语句中大小写不敏感、可写小写 |

探测有数据月份（分表多时，**禁止逐张 COUNT**，用一条批量）：
```sql
SELECT * FROM (
  SELECT '202601' ym, COUNT(*) cnt FROM rec_recon_result_202601 WHERE theme_id = :THEME_ID UNION ALL
  SELECT '202606',     COUNT(*)     FROM rec_recon_result_202606 WHERE theme_id = :THEME_ID
  -- ... 按主题创建时间/日期范围缩小候选月份 ...
) WHERE cnt > 0 ORDER BY ym;
```
先按主题创建时间或用户给的日期范围把候选月份缩到最小（通常近几个月），再拼 `UNION ALL`。

## 雪花 id 精度陷阱（致命）

- `theme_id` / `rec_id` 是 19 位雪花 id。MCP 返回的 JSON 数字会被 JS 浮点截断（末几位失真）。
- 解析主题时必须 `SELECT CAST(rec_id AS CHAR) AS theme_id ...` 取字符串真值；后续所有 SQL 用字符串真值，**绝不能用返回的截断数字**，否则删错或删不到。

## 日期范围约定

- 用户给 `:DATE_FROM` ~ `:DATE_TO`，**左闭右开**（如 `2026-01-01` ~ `2026-07-01` 表示 1~6 月）。
- **不给范围 = 清理该主题全部有数据月份**（按 Step 2 探测结果）。
- 按月分表 DELETE 可加 `transaction_date >= :DATE_FROM AND transaction_date < :DATE_TO` 精确限定；非分表表是否按日期限定由用户确认（通常整主题清理）。

## 来源

整理自《对账数据清理脚本.md》「按月分表版本 — 根据主题删对账数据」，并核对 saas-reconciliation-business 的 DynamicSqlSupport 表名/列名与 dev-mysql-saas02 实际物理表结构。
