# 字段默认值参考

## auth_temp_function

| 字段 | 类型 | function 默认 | category 默认 | 说明 |
|------|------|---------------|---------------|------|
| rec_id | bigint | 时间戳ID | 时间戳ID | 主键 |
| code | varchar | 业务code | '' | 分类无 code |
| name | varchar | 中文名 | 中文名 | |
| parent_id | bigint | 父功能ID | 父分类ID | |
| enabled | bit(1) | b'1' | b'1' | |
| url | varchar | '' | '' | 一般为空 |
| internal | bit(1) | b'0' | b'0' | |
| category | bit(1) | b'0' | b'1' | **核心区分** |
| leaf | bit(1) | b'1' | b'0' | **核心区分** |
| function_code | varchar | F编号 | F编号 | F + 4位padded |
| description | varchar | NULL | NULL | |
| version | varchar | NULL | '' | 注意分类是空字符串 |
| rec_created_by | varchar | '1' | '1' | |
| rec_created_org | varchar | NULL | NULL | |
| rec_created_time | datetime | now | now | |
| rec_modified_by | varchar | '1' | '1' | |
| rec_modified_org | varchar | NULL | NULL | |
| rec_modified_time | datetime | now | now | |
| rec_version | int | 1 | 1 | |
| deleted | bit(1) | b'0' | b'0' | |
| applicable_version | varchar | ''（或继承父级）| '' | |
| config | varchar | NULL | NULL | |
| display_sort | float | 同级max+1 | NULL | 分类用 NULL |
| mobile_url | varchar | '' | '' | |
| icon | varchar | NULL | NULL | |
| all_check | bit(1) | b'0' | b'0' | |
| icon_url | varchar | NULL | NULL | |

## auth_temp_function_product

| 字段 | 默认 |
|------|------|
| rec_id | 时间戳ID |
| function_id | 新建的 function rec_id |
| product_attribution_code | 克隆参照（常见 'accounting-biz' / 'reconciliation-biz'）|
| 时间字段 | now |
| rec_version | 1 |

## auth_temp_application_function

| 字段 | 默认 |
|------|------|
| rec_id | 时间戳ID |
| app_id | 模板 ID |
| function_id | 新建 function rec_id |
| 时间字段 | now |
| rec_version | 1 |

## auth_temp_permission

| 字段 | 类型 | function 默认 | category 默认 | 说明 |
|------|------|---------------|---------------|------|
| rec_id | bigint | 时间戳ID | 时间戳ID | |
| name | varchar | 中文名 | 中文名 | |
| internal | bit(1) | b'1'（克隆参照）| b'1' | 注意通常 = 1 |
| parent_id | bigint | 模板下父permission | 模板下父permission | |
| open_mode | int | 0（克隆参照）| 0 | |
| display_sort | float | 同级max+1 | NULL | |
| app_id | bigint | 模板 ID | 模板 ID | |
| category | bit(1) | b'0' | b'1' | |
| function_id | bigint | 新 function rec_id | 新 function rec_id | |
| leaf | bit(1) | b'1' | b'0' | |
| applied_range | varchar | '0' | '0' | |
| enabled | bit(1) | b'1' | b'1' | |
| 时间字段 | datetime | now | now | |
| rec_created_by/modified_by | varchar | '1' | '1' | |
| rec_version | int | 1 | 1 | |
| deleted | bit(1) | b'0' | b'0' | |
| config | varchar | NULL | NULL | |
| virtual_flag | bit(1) | b'0' | b'0' | |

## auth_temp_function_item

| 字段 | 默认 |
|------|------|
| rec_id | 时间戳ID |
| code | `{function.code}:{后缀}` 如 `diff:data:auto:writeoff:add` |
| name | 中文按钮名 |
| function_id | 新 function rec_id |
| internal | NULL |
| enabled | b'1' |
| description | NULL |
| 时间字段 | now |
| rec_version | 1 |
| deleted | b'0' |

## auth_temp_permission_item

| 字段 | 默认 |
|------|------|
| rec_id | 时间戳ID |
| permission_id | 新 permission rec_id（每模板一条）|
| function_item_id | 对应 function_item rec_id |
| 时间字段 | now |
| rec_version | 1 |

## auth_temp_group_permission

| 字段 | 默认 |
|------|------|
| rec_id | 时间戳ID |
| group_id | 该模板下的角色 ID（如单位管理员）|
| permission_id | 新 permission rec_id |
| 时间字段 | now |
| rec_version | 1 |

## bit 字段写法对照

| 含义 | SQL 写法 | usql 读出 |
|------|---------|----------|
| 0/false | `b'0'` | 显示空字符或 0 |
| 1/true | `b'1'` | 显示 ASCII 1 字节或 1 |

读 bit 字段时建议加 `+0`：

```sql
SELECT enabled+0, category+0, leaf+0 FROM auth_temp_function WHERE rec_id = ...;
```

## 时间字段格式

`'YYYY-MM-DD HH:MM:SS'`，例如 `'2026-06-16 14:59:36'`。

## 关键 ID 速查（KSYTCommon 体系）

| 名称 | rec_id |
|------|--------|
| 模板：开收一体 KSYTCommon | 5669102018905974829 |
| 模板：用票单位通用 PT0001 | 613015803075231745 |
| 模板：财务智能对账 PT0081 | 6185863378629954932 |
| 模板：财税一体化通用 CSYTHCommon | 4389738154568338352 |
| 模板：差异管理 (function F2991) | 5745853084484898846 |
| 模板：差异处理 (function F1273) | 5158699719040496226 |
| KSYTCommon 单位管理员 | 5669102018905974834 |
| PT0001 单位管理员 | 613015803075231905 |
| PT0081 单位管理员 | 6185863378629954935 |
| CSYTHCommon 单位管理员 | 4389738154568339883 |

⚠️ 这些 ID 是基于 2026-06-16 当时数据，**使用前用 usql 重新校验**。
