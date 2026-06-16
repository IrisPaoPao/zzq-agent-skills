# 菜单脚本生成参考

## 各表关键字段说明

### auth_temp_function（功能模板）
| 字段 | 说明 |
|------|------|
| rec_id | 主键，32位整数 |
| code | 功能编码 |
| name | 功能名称 |
| parent_id | 父级功能ID |
| function_code | 功能码（如 F3553） |
| applicable_version | 适用版本 |
| display_sort | 排序号 |

### auth_temp_function_product（功能归属，4.5.2.0+）
| 字段 | 说明 |
|------|------|
| rec_id | 主键 |
| function_id | 功能ID |
| product_attribution_code | 产品归属编码（如 accounting-biz） |

### auth_temp_application_function（模板功能关系）
| 字段 | 说明 |
|------|------|
| rec_id | 主键 |
| app_id | 模板ID |
| function_id | 功能ID |

### auth_temp_permission（模板菜单）
| 字段 | 说明 |
|------|------|
| rec_id | 主键（菜单ID） |
| name | 菜单名称 |
| parent_id | 父级菜单ID |
| app_id | 所属模板ID |
| function_id | 关联功能ID |
| open_mode | 打开方式 |
| display_sort | 排序号 |

### auth_temp_group_permission（角色菜单关系）
| 字段 | 说明 |
|------|------|
| rec_id | 主键 |
| group_id | 角色ID |
| permission_id | 菜单ID |

## 完整脚本示例

以 `医疗费用月度结算数据采集` 为例：

```sql
-- ================================================================
-- 医疗费用月度结算数据采集 - 菜单导出脚本
-- 生成时间: 2026-04-25
-- 模板: 开收一体模板 (KSYTCommon) rec_id=5669102018905974829
-- ================================================================

-- 1. auth_temp_function 功能模板
if(notExist("select * from auth_temp_function where rec_id = 6597847327540881365")){
    executeMultiCommand("""
INSERT INTO `auth_temp_function`(`rec_id`, `code`, `name`, `parent_id`, `enabled`, `url`, `internal`, `category`, `leaf`, `function_code`, `description`, `version`, `rec_created_by`, `rec_created_org`, `rec_created_time`, `rec_modified_by`, `rec_modified_org`, `rec_modified_time`, `rec_version`, `deleted`, `applicable_version`, `config`, `display_sort`, `icon`, `all_check`, `icon_url`) VALUES (6597847327540881365, 'insurance:settlement:collect', '医疗费用月度结算数据采集', 5745852912686202980, b'0', '', b'0', b'0', b'0', 'F3553', NULL, NULL, '623717693345759233', NULL, '2026-04-16 09:56:22', '623717693345759233', NULL, '2026-04-16 09:56:22', 1, b'0', '', NULL, 1739, '', b'0', NULL);
    """)
}else {
    println("table auth_temp_function exist rec_id = 6597847327540881365");
}

-- 2. auth_temp_function_product 功能归属表（4.5.2.0+版本需要）
if(notExist("select * from auth_temp_function_product where function_id = 6597847327540881365")){
    executeMultiCommand("""
INSERT INTO `auth_temp_function_product`(`rec_id`, `function_id`, `product_attribution_code`, `rec_created_by`, `rec_created_org`, `rec_created_time`, `rec_modified_by`, `rec_modified_org`, `rec_modified_time`, `rec_version`) VALUES (6597847327540881366, 6597847327540881365, 'accounting-biz', '623717693345759233', NULL, '2026-04-16 09:56:22', '623717693345759233', NULL, '2026-04-16 09:56:22', 1);
    """)
}else {
    println("table auth_temp_function_product exist function_id = 6597847327540881365");
}

-- 3. auth_temp_application_function 模板功能关系
if(notExist("select * from auth_temp_application_function where app_id = 5669102018905974829 and function_id = 6597847327540881365")){
    executeMultiCommand("""
INSERT INTO `auth_temp_application_function`(`rec_id`, `app_id`, `function_id`, `rec_created_by`, `rec_created_org`, `rec_created_time`, `rec_modified_by`, `rec_modified_org`, `rec_modified_time`, `rec_version`) VALUES (6651570393386313930, 5669102018905974829, 6597847327540881365, '1', NULL, '2026-04-24 16:33:02', '1', NULL, '2026-04-24 16:33:02', 1);
    """)
}else {
    println("table auth_temp_application_function exist app_id = 5669102018905974829 and function_id = 6597847327540881365");
}

-- 4. auth_temp_permission 模板菜单
if(notExist("select * from auth_temp_permission where rec_id = 6597847327540882846")){
    executeMultiCommand("""
INSERT INTO `auth_temp_permission`(`rec_id`, `name`, `internal`, `parent_id`, `open_mode`, `display_sort`, `app_id`, `category`, `function_id`, `leaf`, `applied_range`, `enabled`, `rec_created_by`, `rec_created_org`, `rec_created_time`, `rec_modified_by`, `rec_modified_org`, `rec_modified_time`, `rec_version`, `deleted`, `config`, `virtual_flag`) VALUES (6597847327540882846, '医疗费用月度结算数据采集', NULL, 6241965375321280306, 0, 2185, 5669102018905974829, b'0', 6597847327540881365, b'0', '0', b'0', '623717693345759233', NULL, '2026-04-16 09:58:26', '623717693345759233', NULL, '2026-04-16 09:58:26', 1, b'0', NULL, b'0');
    """)
}else {
    println("table auth_temp_permission exist rec_id = 6597847327540882846");
}

-- 5. auth_temp_group_permission 角色菜单关系（单位管理员角色）
if(notExist("select * from auth_temp_group_permission where permission_id = 6597847327540882846 and group_id = 5669102018905974834")){
    executeMultiCommand("""
INSERT INTO `auth_temp_group_permission`(`rec_id`, `group_id`, `permission_id`, `rec_created_by`, `rec_created_org`, `rec_created_time`, `rec_modified_by`, `rec_modified_org`, `rec_modified_time`, `rec_version`) VALUES (6651570393386315110, 5669102018905974834, 6597847327540882846, '1', NULL, '2026-04-24 16:34:43', '1', NULL, '2026-04-24 16:34:43', 1);
    """)
}else {
    println("table auth_temp_group_permission exist permission_id = 6597847327540882846 and group_id = 5669102018905974834");
}

-- 更新应用模板、功能模板版本号，必须添加
if(!notExist("SELECT * FROM auth_temp_application WHERE rec_id =?", ["5669102018905974829"])){
    executeMultiCommand("""
update auth_temp_application set template_version=template_version+0.01 where rec_id=5669102018905974829;
update auth_temp_function_version set template_version=template_version+0.01;
    """)
}else {
    println("table auth_temp_application no exist rec_id = 5669102018905974829， skip this update execute")
}
```

## 常见问题

**Q: 功能项表没有数据需要生成吗？**
A: 不需要。只生成有数据的表。

**Q: 关系表判断条件怎么选？**
A: 禁止用 rec_id 判断关系是否存在，必须用业务字段组合判断。例如 `app_id = X AND function_id = Y`。

**Q: 字节字段怎么写？**
A: MySQL 中 `b'0'` 表示 false，`b'1'` 表示 true。

**Q: NULL 字段怎么处理？**
A: 显式写出 NULL，不要省略字段也不要留空。
