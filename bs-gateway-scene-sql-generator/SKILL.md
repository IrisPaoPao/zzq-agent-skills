---
name: bs-gateway-scene-sql-generator
description: 在 saas-data-gateway 仓库由 Groovy 采集脚本路径生成数据网关场景与能力注册的 INSERT SQL（gwb_scene + gwb_scene_capacity_relation + gwb_context_param）。触发场景：用户说"注册场景""生成场景注册脚本""新增网关场景""给这个采集脚本生成 gwb_scene INSERT""场景能力关系/上下文参数脚本"，或提到 gwb_scene / gwb_scene_capacity_relation / gwb_context_param 注册等。区别于 bs-gateway-dirty-data-cleaner（只注册场景、不删数据）。
---

# BS Gateway Scene SQL Generator / 网关场景SQL生成器

## Functionality / 功能说明

Read Groovy script files, automatically extract capability information and context parameters, and generate INSERT SQL statements.

读取 Groovy 脚本文件，自动提取能力信息和上下文参数，生成 INSERT SQL 语句。

## Input / 输入

User provides Groovy script path, for example / 用户提供 Groovy 脚本路径，例如:
```
/Users/zhangzhengqing/work/project/vasService/saas-data-gateway/saas-data-gateway-core/src/main/resources/capability/IcbcFileGatherCapability.groovy
```

## Pre-Flight Checks / 前置校验（必须执行）

在执行生成前，先完成以下 2 步以防止 scene_id 冲突：

### Step 1: 查库获取下一个空闲 scene_id

目标库别名固定为 `dev-mysql-saas02`（MySQL saas_02 库）。

```sql
SELECT MAX(CAST(scene_code AS UNSIGNED)) AS max_id FROM gwb_scene;
```
取到当前最大 scene_id，从 `max_id + 1` 开始编排。

### Step 2: 扫描工作区已预定的 scene_id

用户项目根目录下的 `.sql` 文件中可能已经有待执行的场景注册脚本（如 `gateway_scene_insert.sql`），这些场景还未入库，但 ID 已被预定。

```bash
grep -oP "VALUES\s*\(\K\d+" *.sql | sort -n | uniq
# 或者更精确的：找 gwb_scene INSERT 中的 rec_id
grep -oP "INSERT INTO gwb_scene[^;]+VALUES\s*\(\K\d+" *.sql 2>/dev/null | sort -n
```

把 Step 1 的 `max_id + 1` 与 Step 2 扫描到的预定 ID 做并集，取最小值开始。

> **示例**：库里最大 scene_id=1042，工作区 sql 有预定号 1043、1044，则从 1045 开始编。

## Processing Flow / 处理流程

1. Read Groovy script file / 读取 Groovy 脚本文件
2. Extract the following information / 提取以下信息:
   - `getName()` → Capability name / 能力名称
   - `type()` → Capability code (CapabilityCodeEnum) / 能力编码
   - `dockingParamsJson()` → Context parameter list / 上下文参数列表
3. Generate INSERT SQL (including 3 tables) / 生成 INSERT SQL (包含 3 张表)

## Output / 输出

Generate INSERT SQL for 3 tables / 生成 3 张表的 INSERT SQL:

### Table 1: gwb_scene (Scene Table / 场景表)
```sql
INSERT INTO gwb_scene (rec_id, rec_created_by, rec_created_org, rec_created_time, rec_modified_by, rec_modified_org, rec_modified_time, rec_version, system_type, name, trigger_mode, protocol_type, scene_code, scene_version, scene_type, status, pay_method)
VALUES ({snowflake_id}, 'system', 'system', '{current_time}', 'system', 'system', '{current_time}', 1, '{system_type}', '{scene_name}', 'active', 'http', '{scene_code}', 'v1.0', 1, 1, NULL);
```

### Table 2: gwb_scene_capacity_relation (Capability Script Mapping Table / 能力脚本映射表)
```sql
INSERT INTO gwb_scene_capacity_relation (rec_id, rec_created_by, rec_created_org, rec_created_time, rec_modified_by, rec_modified_org, rec_modified_time, rec_version, scene_id, capability_name, capability_code, script_type, capability_script)
VALUES ({snowflake_id}, 'system', 'system', '{current_time}', 'system', 'system', '{current_time}', 1, {scene_id}, '{capability_name}', '{capability_code}', 'groovy', 'capability/{script_filename}');
```

### Table 3: gwb_context_param (Context Parameter Table / 上下文参数表)
```sql
INSERT INTO gwb_context_param (rec_id, rec_created_by, rec_created_org, rec_created_time, rec_modified_by, rec_modified_org, rec_modified_time, rec_version, scene_id, context_key_name, context_key, context_value, context_sort, param_type, required, source_type, source_id, group_id, group_sort)
VALUES ({snowflake_id}, 'system', 'system', '{current_time}', 'system', 'system', '{current_time}', 1, {scene_id}, '{param_name_cn}', '{param_key}', NULL, '{sort}', 0, 1, 1, NULL, NULL, NULL);
```

## Capability Code Mapping / 能力编码映射

CapabilityCodeEnum mapping from `type()` method / 从 `type()` 方法提取的枚举映射:
- PAGE_GATHER → '101' (分页明细采集)
- PREPAY_ACCOUNT_LIST → '102' (预交金账户查询)
- PREPAY_ACCOUNT_CLEAR → '103' (预交金账户清零)
- DAILY_CLEAR_PREPAY_DETAIL → '104' (预交金清零日终明细)
- IMPORT_FILE_GATHER → '105' (导入文件明细采集)
- LINKONG_ORDER_DETAIL → '106' (联空订单详情查询)
- ORDER_DETAIL → '107' (三方对账订单详情查询)
- ACCOUNTING_PUSHED → '108' (记账推送)
- ACCOUNTING_ACCOUNTED → '109' (记账入账)
- REIMBURSEMENT → '110' (报销采集)
- PREPAY_REFUND_APPLY → '111' (HRP预交金退款申请)
- PREPAY_STATUS_QUERY → '112' (HRP预交金付款状态查询)
- DATA_TOTAL_CHECK → '113' (商保直赔结算对总账)
- DATA_DETAIL_CORRECT → '114' (商保直赔结算明细更正)
- PREPAY_EXTRA_ATTACH → '116' (HRP预交金退款申请额外附件)
- PREPAY_ACCOUNT_CORRECT_LIST → '117' (预交金账户列表查询)

## Interactive Input / 交互式输入

Skill needs to confirm with user / Skill 需要向用户确认:
1. **scene_id**: 基于 Pre-Flight Checks 算出的起始号，向用户确认（不要凭空猜测或问空白问题）/ Scene ID, derived from Pre-Flight Checks
2. **scene_code**: Scene code (usually same as scene_id) / 场景编码 (通常与 scene_id 相同)
3. **system_type**: System type (e.g., '01005') / 系统类型
4. **Whether to INSERT gwb_scene**: Skip if scene already exists / 是否需要 INSERT gwb_scene，如果是已有场景则跳过

## Example Output / 示例输出

```sql
-- gwb_scene_capacity_relation / 能力脚本映射表
INSERT INTO gwb_scene_capacity_relation (rec_id, rec_created_by, rec_created_org, rec_created_time, rec_modified_by, rec_modified_org, rec_modified_time, rec_version, scene_id, capability_name, capability_code, script_type, capability_script)
VALUES (5852466621997638103, 'system', 'system', '2026-05-27 10:00:00', 'system', 'system', '2026-05-27 10:00:00', 1, 1032, 'ICBC File Gathering', '101', 'groovy', 'capability/IcbcFileGatherCapability.groovy');

-- gwb_context_param / 上下文参数表
INSERT INTO gwb_context_param (rec_id, rec_created_by, rec_created_org, rec_created_time, rec_modified_by, rec_modified_org, rec_modified_time, rec_version, scene_id, context_key_name, context_key, context_value, context_sort, param_type, required, source_type, source_id, group_id, group_sort)
VALUES (6252466610017526580, 'system', 'system', '2026-05-27 10:00:00', 'system', 'system', '2026-05-27 10:00:00', 1, 1032, 'File Protocol(ftp/sftp)', 'protocol', NULL, '1', 0, 1, 1, NULL, NULL, NULL);

INSERT INTO gwb_context_param (rec_id, rec_created_by, rec_created_org, rec_created_time, rec_modified_by, rec_modified_org, rec_modified_time, rec_version, scene_id, context_key_name, context_key, context_value, context_sort, param_type, required, source_type, source_id, group_id, group_sort)
VALUES (6352466610017526581, 'system', 'system', '2026-05-27 10:00:00', 'system', 'system', '2026-05-27 10:00:00', 1, 1032, 'File Server Address', 'host', NULL, '2', 0, 1, 1, NULL, NULL, NULL);

-- ... more parameters / 更多参数
```

## Notes / 注意事项

1. **目标数据库**: `dev-mysql-saas02`(MySQL saas_02 库,bs-jdbc-tool 配置别名)。
2. Snowflake ID uses randomly generated 19-digit numbers / 雪花ID 使用随机生成的 19 位数字
3. Time uses current time / 时间使用当前时间
4. Only output SQL, no Flyway script wrapper / 只输出 SQL，不包装 Flyway 脚本
5. Auto-read and parse after user provides script path / 用户提供脚本路径后，自动读取并解析
