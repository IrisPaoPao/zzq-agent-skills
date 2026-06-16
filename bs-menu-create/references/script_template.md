# SQL 脚本模板

## 完整模板（KSYTCommon 单模板，叶子功能，单角色绑定）

```sql
-- ================================================================
-- {菜单名称} - 菜单导入脚本
-- 生成时间: {YYYY-MM-DD HH:MM:SS}
-- 模板: {模板中文名} ({模板code})  app_id={app_id}
-- 父级功能: {父功能名称} {父function_code}  rec_id={父functionId}
-- 父级菜单: {父permission名称}  rec_id={父permissionId}
-- 参照功能: {参照功能名称}  rec_id={参照functionId}
-- 角色绑定: {角色名}  group_id={groupId}
-- ID 策略: 时间戳 {ts} + 序号 + 占位
-- ================================================================

-- 1. auth_temp_function 功能模板
INSERT INTO `auth_temp_function`
(`rec_id`, `code`, `name`, `parent_id`, `enabled`, `url`, `internal`, `category`, `leaf`, `function_code`, `description`, `version`, `rec_created_by`, `rec_created_org`, `rec_created_time`, `rec_modified_by`, `rec_modified_org`, `rec_modified_time`, `rec_version`, `deleted`, `applicable_version`, `config`, `display_sort`, `mobile_url`, `icon`, `all_check`, `icon_url`)
VALUES
({funcId}, '{code}', '{菜单名}', {父functionId}, b'1', '', b'0', b'0', b'1', '{F编号}', NULL, NULL, '1', NULL, '{now}', '1', NULL, '{now}', 1, b'0', '', NULL, {显示顺序}, '', NULL, b'0', NULL);

-- 2. auth_temp_function_product 功能归属
INSERT INTO `auth_temp_function_product`
(`rec_id`, `function_id`, `product_attribution_code`, `rec_created_by`, `rec_created_org`, `rec_created_time`, `rec_modified_by`, `rec_modified_org`, `rec_modified_time`, `rec_version`)
VALUES
({prodId}, {funcId}, '{产品归属code}', '1', NULL, '{now}', '1', NULL, '{now}', 1);

-- 3. auth_temp_application_function 模板功能关系
INSERT INTO `auth_temp_application_function`
(`rec_id`, `app_id`, `function_id`, `rec_created_by`, `rec_created_org`, `rec_created_time`, `rec_modified_by`, `rec_modified_org`, `rec_modified_time`, `rec_version`)
VALUES
({appFuncId}, {app_id}, {funcId}, '1', NULL, '{now}', '1', NULL, '{now}', 1);

-- 4. auth_temp_permission 模板菜单
INSERT INTO `auth_temp_permission`
(`rec_id`, `name`, `internal`, `parent_id`, `open_mode`, `display_sort`, `app_id`, `category`, `function_id`, `leaf`, `applied_range`, `enabled`, `rec_created_by`, `rec_created_org`, `rec_created_time`, `rec_modified_by`, `rec_modified_org`, `rec_modified_time`, `rec_version`, `deleted`, `config`, `virtual_flag`)
VALUES
({permId}, '{菜单名}', b'1', {父permId}, 0, {permission显示顺序}, {app_id}, b'0', {funcId}, b'1', '0', b'1', '1', NULL, '{now}', '1', NULL, '{now}', 1, b'0', NULL, b'0');

-- 5. auth_temp_group_permission 角色菜单关系
INSERT INTO `auth_temp_group_permission`
(`rec_id`, `group_id`, `permission_id`, `rec_created_by`, `rec_created_org`, `rec_created_time`, `rec_modified_by`, `rec_modified_org`, `rec_modified_time`, `rec_version`)
VALUES
({gpId}, {groupId}, {permId}, '1', NULL, '{now}', '1', NULL, '{now}', 1);

-- 6. 升级版本号（必须，否则模板不会同步到产品端）
UPDATE auth_temp_application SET template_version = template_version + 0.01 WHERE rec_id = {app_id};
UPDATE auth_temp_function_version SET template_version = template_version + 0.01;
```

## 分类菜单（category）模板

主要差异：

```sql
-- function 行
-- code = ''（空）
-- category = b'1'
-- leaf = b'0'
INSERT INTO `auth_temp_function`
(...)
VALUES
({funcId}, '', '{分类名}', {父Id}, b'1', '', b'0', b'1', b'0', '{F编号}', ..., NULL, ...);

-- permission 行
-- category = b'1'
-- leaf = b'0'
INSERT INTO `auth_temp_permission`
(...)
VALUES
({permId}, '{分类名}', b'1', {父permId}, 0, NULL, {app_id}, b'1', {funcId}, b'0', '0', b'1', ...);

-- 分类节点通常不绑角色
-- 不需要 function_product（看用户场景）
```

## 多模板扩展模板

每个额外模板要追加：

```sql
-- 追加 application_function（每模板一条）
INSERT INTO `auth_temp_application_function` (...) VALUES ({新appFuncId}, {另一app_id}, {funcId}, ...);

-- 追加 permission（每模板一条，parent_id 不同）
INSERT INTO `auth_temp_permission` (...) VALUES ({新permId}, '{菜单名}', b'1', {该模板下的父permId}, 0, {该模板下的显示顺序}, {另一app_id}, ...);

-- 追加 group_permission（每模板一条，绑该模板下的单位管理员）
INSERT INTO `auth_temp_group_permission` (...) VALUES ({新gpId}, {该模板的group_id}, {新permId}, ...);

-- 追加版本号更新（每模板一行）
UPDATE auth_temp_application SET template_version = template_version + 0.01 WHERE rec_id = {另一app_id};
```

`auth_temp_function` / `auth_temp_function_product` 全局只一条，不重复。

## 按钮权限（function_item + permission_item）模板

如果用户提供了按钮列表（如 "新增:add,删除:delete"）：

```sql
-- 每个按钮一条 function_item
INSERT INTO `auth_temp_function_item`
(`rec_id`, `code`, `name`, `function_id`, `internal`, `enabled`, `description`, `rec_created_by`, `rec_created_org`, `rec_created_time`, `rec_modified_by`, `rec_modified_org`, `rec_modified_time`, `rec_version`, `deleted`)
VALUES
({itemId}, '{菜单code}:{按钮suffix}', '{按钮名}', {funcId}, NULL, b'1', NULL, '1', NULL, '{now}', '1', NULL, '{now}', 1, b'0');

-- 每个按钮一条 permission_item（每个 permission/模板都要重复）
INSERT INTO `auth_temp_permission_item`
(`rec_id`, `permission_id`, `function_item_id`, `rec_created_by`, `rec_created_org`, `rec_created_time`, `rec_modified_by`, `rec_modified_org`, `rec_modified_time`, `rec_version`)
VALUES
({piId}, {permId}, {itemId}, '1', NULL, '{now}', '1', NULL, '{now}', 1);
```

## ID 序号分配建议

| 表 | 序号 |
|----|------|
| function | 0001 |
| function_product | 0002 |
| function_item[i] | 0010 + i |
| application_function[k] | 0100 + k |
| permission[k] | 0200 + k |
| permission_item[k][i] | 0300 + k*100 + i |
| group_permission[k] | 0400 + k |

`k` 是模板序号，`i` 是按钮序号。这样不同表 ID 不会撞，便于排查。
