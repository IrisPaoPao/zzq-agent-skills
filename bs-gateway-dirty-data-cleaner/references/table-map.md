# 数据网关清理 — 表→列→分片 速查

## 涉及的表

| 表 | 是否分表 | 角色 | 关联键 |
|---|---|---|---|
| `gwb_original_index_YYYYMM` | 分表 | 原始数据索引（幂等） | scenario_id、system_id、transaction_date、session_id、gather_id |
| `gwb_original_data_YYYYMM` | 分表 | 原始数据主表 | scene_id、system_id、transaction_date、data_source_index_id |
| `gwb_original_item_YYYYMM` | 分表 | 原始数据明细（LIST 子表） | pid → original_data.rec_id、transaction_date |
| `gwb_data_source_session` | 非分表 | 数据源会话 | rec_id ← index.session_id |
| `gwb_data_source_batch` | 非分表 | 数据源批次 | scenario_id、system_id、bus_date |
| `gwb_gather_page_record` | 非分表 | 断点续采进度（**重采必删**） | gather_id、system_id、bus_start_date |
| `gwb_gather_log` | 非分表 | 采集日志（展示用，可选清理） | gather_id、system_id、bus_start_date |
| `gwb_gather_config` | 非分表 | 采集任务配置 | rec_id(=gather_id)、gather_name、system_id、start_time |
| `gwb_docking_system` | 非分表 | 对接系统 | rec_id(=system_id)、system_name、scene_id |
| `gwb_scene` | 非分表 | 场景 | rec_id(=scenario_id)、name |

## 列名陷阱（最易错）

- `gwb_original_index` 用列名 **`scenario_id`**
- `gwb_original_data` 用列名 **`scene_id`**
- `gwb_data_source_batch` 用列名 **`scenario_id`**

三者含义一致（都 = `gwb_scene.rec_id`），但列名不同。复制 SQL 时勿混。

## 关联链（解析 ID 用）

```
gwb_gather_config.rec_id  = gather_id
gwb_gather_config.system_id → gwb_docking_system.rec_id = system_id
gwb_docking_system.scene_id → gwb_scene.rec_id = scenario_id(=scene_id)
gwb_original_index.scenario_id  = gwb_scene.rec_id
gwb_original_data.scene_id      = gwb_scene.rec_id
gwb_original_index.gather_id    = gwb_gather_config.rec_id
gwb_original_index.session_id   = gwb_data_source_session.rec_id
gwb_original_index.batch_id     = gwb_data_source_batch.rec_id
gwb_original_data.data_source_index_id = gwb_original_index.rec_id
gwb_original_item.pid           = gwb_original_data.rec_id
```

> 注意：`gwb_gather_config` 无 scene_id 列，场景只能经 `system_id → gwb_docking_system.scene_id` 间接得到。

## 删除顺序理由（固定，不可乱）

`item → session → batch → data → index`

- `item` 先删：其删除依赖 `data` 的 pid（子查询 `pid IN (SELECT rec_id FROM gwb_original_data_...)`），所以必须在 `data` 删除之前。
- `session` 删除依赖 `index` 的 session_id（子查询 `rec_id IN (SELECT session_id FROM gwb_original_index_...)`），故 `index` 必须在 `session` 之后删。
- `index` 最后删：其它删除的子查询都依赖它。

## 分表（TDSQL，用逻辑表名）

- 目标库是 **TDSQL 分布式数据库**，`gwb_original_{index,data,item}` 按 `transaction_date` 分片。
- **查询/删除一律用逻辑表名** `gwb_original_index` / `gwb_original_data` / `gwb_original_item`，加 `transaction_date` 范围条件，TDSQL 代理自动路由到相关分片。一条带范围条件的语句即覆盖整个日期范围，**无需逐月拆分**。
- **绝不能用物理分片名**（实测确认）：
  - `information_schema.tables` 里能看到 `gwb_original_index_tdsql_subp202602`、`gwb_original_index_tdsql_subp_auto_202607`、`gwb_original_data_202506` 等物理分片名；
  - 但直接 `SELECT ... FROM gwb_original_index_tdsql_subp202602` 会报 `Proxy ERROR: Table does not exist`。这些是底层分片，不可直接查询。
- 月份探测：直接查逻辑表 `GROUP BY DATE_FORMAT(transaction_date,'%Y%m')` 看各月行数，用于让用户核对数据分布（不用于决定物理表名）。

## 雪花 id 精度陷阱（致命）

- `rec_id` / `system_id` 等是 19 位雪花 id。MCP 返回的 JSON 数字会被 JS 浮点截断：实测 `system_id` 真值 `6203537512649891840` 被返回成 `6203537512649892000`，末 4 位失真。
- 解析 ID 时必须 `SELECT CAST(rec_id AS CHAR) ...` 取字符串真值；后续所有 SQL 用字符串真值，**绝不能用返回的截断数字**，否则删错或删不到。

## 重采机制（GatherServiceImpl）

- 重采起始日期 = `gwb_gather_config.start_time`。
- `gwb_gather_page_record` = 断点续采进度。execute 时按 gather_id 查到它就从其 `bus_start_date` 往后采；查不到才从配置 `start_time` 重头。
  - ★ **不删这条进度，重采只会从断点往后，不会回头补历史月份** → 要重采历史数据必须删它。
- `gwb_gather_log` = 采集记录/日志，仅前端展示，代码不据此跳过日期 → 可选清理。

## 日期范围约定

- 用户给 `:DATE_FROM` ~ `:DATE_TO`，**左闭右开**（如 `2026-02-01` ~ `2026-06-01` 表示 2/3/4/5 四个月）。
- 删除条件统一用 `transaction_date >= :DATE_FROM AND transaction_date < :DATE_TO` 范围限定（而非单点 `=:BUS_DATE`），更贴合用户给的范围。
