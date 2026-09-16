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

先区分三个字段：

- `gwb_scene.rec_id`：场景主键，模板变量为 `{scene_rec_id}`。
- `gwb_scene.scene_code`：业务编码，模板变量为 `{scene_code}`，不能用它替代主键。
- 关系表、参数表的 `scene_id`：外键，始终填写对应场景的 `{scene_rec_id}`。

### Step 1: 核对场景与业务编码

先按 `bs-database-query` Skill 核对 usql 连接、schema 与表归属。已有场景按用户给的编码或主键查出 `rec_id` 字符串真值，复用它并跳过场景 INSERT；不要重新生成主键。

新场景先核对当前项目的编码约定。若采用连续数字编码，MySQL 可用：

```sql
SELECT CAST(COALESCE(MAX(CAST(scene_code AS UNSIGNED)), 0) AS CHAR) AS max_scene_code
FROM gwb_scene WHERE scene_code REGEXP '^[0-9]+$';
```

仅对 `scene_code` 从最大数值加一开始选取候选值；非数字编码遵循当前项目约定，不强制转数字。主键采用项目已有 ID 生成方式，检查字段类型、范围、候选 ID 占用及本批唯一性；没有可用生成方式时保留占位符并说明待补，不用随机 19 位数冒充雪花 ID。

### Step 2: 核对工作区待执行脚本的预留值

使用 `rg --files -g '*.sql' -g '*.groovy'` 找出本任务有关的待执行脚本，包括 `.mixed/deliverables/`。按 `INSERT INTO gwb_scene` 的列清单与 VALUES 对应关系，分别提取 `scene_code` 和 `rec_id`，不能假设第一列就是业务编码，也不能扫描所有表的第一列当作场景编号。多行或表达式不能可靠解析时直接阅读脚本，不报告已自动完成检查。

从数据库最大业务编码加一开始，跳过待执行脚本已使用的编码，并把本批分配值加入预留集合。例如库中最大编码为 1042，脚本预留 1043、1044，则下一编码为 1045。主键另外核对，所有关系外键复用场景主键。预检不构成并发号段锁定，执行前仍需核对唯一约束与候选值是否被占用。

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
VALUES ({scene_rec_id}, 'system', 'system', '{current_time}', 'system', 'system', '{current_time}', 1, '{system_type}', '{scene_name}', 'active', 'http', '{scene_code}', 'v1.0', 1, 1, NULL);
```

### Table 2: gwb_scene_capacity_relation (Capability Script Mapping Table / 能力脚本映射表)
```sql
INSERT INTO gwb_scene_capacity_relation (rec_id, rec_created_by, rec_created_org, rec_created_time, rec_modified_by, rec_modified_org, rec_modified_time, rec_version, scene_id, capability_name, capability_code, script_type, capability_script)
VALUES ({relation_rec_id}, 'system', 'system', '{current_time}', 'system', 'system', '{current_time}', 1, {scene_rec_id}, '{capability_name}', '{capability_code}', 'groovy', 'capability/{script_filename}');
```

### Table 3: gwb_context_param (Context Parameter Table / 上下文参数表)
```sql
INSERT INTO gwb_context_param (rec_id, rec_created_by, rec_created_org, rec_created_time, rec_modified_by, rec_modified_org, rec_modified_time, rec_version, scene_id, context_key_name, context_key, context_value, context_sort, param_type, required, source_type, source_id, group_id, group_sort)
VALUES ({param_rec_id}, 'system', 'system', '{current_time}', 'system', 'system', '{current_time}', 1, {scene_rec_id}, '{param_name_cn}', '{param_key}', NULL, '{sort}', 0, 1, 1, NULL, NULL, NULL);
```

## Capability Code Mapping / 能力编码映射

以下为历史映射参考；生成时以当前项目 `CapabilityCodeEnum` 与脚本 `type()` 返回值为准，不能把历史清单当作完整枚举：
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

复用用户已给信息和上述核对结果，只询问仍影响语义的缺失项：场景是新增还是复用、业务编码规则、所属 `system_type`。展示最终 `{scene_rec_id}` 与 `{scene_code}` 的对应关系，不要求重复确认已明确的信息。

## Example Output / 示例输出

以下仅展示“已有场景 rec_id=1032”的关联写法；1032 不是从 scene_code 推断的值。新场景应增加场景 INSERT，并在所有外键处使用其实际主键。示例 ID 与时间不可直接复用。

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

1. **目标数据库**：以 `bs-database-query` 核对的 usql 连接名和 schema 为准。
2. 主键保持整数精度，并沿用当前项目 ID 生成机制；每个关系/参数记录使用独立主键，外键统一引用场景主键。
3. Time uses current time / 时间使用当前时间
4. 只输出 SQL，不包装 Flyway 脚本；写入 `.mixed/deliverables/yyyy-MM-dd/`。生成脚本不执行 DML。
5. Auto-read and parse after user provides script path / 用户提供脚本路径后，自动读取并解析
