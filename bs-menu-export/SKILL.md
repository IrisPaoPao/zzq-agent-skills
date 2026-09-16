---
name: bs-menu-export
description: 医疗费用系统菜单脚本导出技能。根据菜单名称查询已核对的运营平台数据库，生成纯 SQL 或用户指定的 Flyway Groovy 菜单脚本。触发场景：用户说"导出菜单脚本"、"生成XX菜单的脚本"、"菜单导出"。
---

# 菜单脚本导出

## 数据库连接与查询入口

实际查库统一使用 `bs-database-query` Skill 的环境定位和 `usql` 流程。用户未指定连接名时先核对运行环境与 Nacos 数据源，不根据“运营平台”或历史别名猜库。确认当前 schema 与 `auth_temp_*` 表归属后复用该连接。

下列代码块是 SQL 模板；按目标数据库填写并正确转义参数后，每条查询单独执行：

```bash
usql -X -w -q -J -v ON_ERROR_STOP=1 '<已核对连接名>' -f '<单条查询.sql的绝对路径>'
```

以下 SQL 展示业务关系；执行前展开 `SELECT *` 的实际列，将要复用的主键和外键列显式转为字符串。为便于分别解析 JSON，多个 SELECT 示例分别调用；执行前在 SQL 中按目标方言添加合理行数限制。

雪花 ID 查询为字符串，避免 JSON 数字经 JavaScript 解析后失真。MySQL 使用 `CAST(rec_id AS CHAR)`；其他方言遵循公共查询 Skill。凭据使用 usql 原生私有配置（权限 0600）；不输出配置内容，不把带凭据的连接串放入命令行。

## 导出流程

### Step 1: 查询功能模板

```sql
SELECT rec_id, name, code, function_code, parent_id
FROM auth_temp_function
WHERE name LIKE '%XXX%';
```

找到 `rec_id`（即 `function_id`）后，继续查询链路数据。

### Step 2: 查询完整链路数据

```sql
-- 功能模板
SELECT * FROM auth_temp_function WHERE rec_id = {function_id};

-- 功能归属（4.5.2.0+）
SELECT * FROM auth_temp_function_product WHERE function_id = {function_id};

-- 模板功能关系
SELECT af.*, ta.name as app_name, ta.code as app_code
FROM auth_temp_application_function af
LEFT JOIN auth_temp_application ta ON af.app_id = ta.rec_id
WHERE af.function_id = {function_id};

-- 模板菜单
SELECT p.*, ta.name as app_name
FROM auth_temp_permission p
LEFT JOIN auth_temp_application ta ON p.app_id = ta.rec_id
WHERE p.function_id = {function_id};

-- 角色菜单关系
SELECT gp.*, tg.name as group_name
FROM auth_temp_group_permission gp
LEFT JOIN auth_temp_group tg ON gp.group_id = tg.rec_id
WHERE gp.permission_id IN (SELECT rec_id FROM auth_temp_permission WHERE function_id = {function_id});

-- 功能项
SELECT * FROM auth_temp_function_item WHERE function_id = {function_id};

-- 菜单功能项关系
SELECT pi.*, tf.name as function_item_name
FROM auth_temp_permission_item pi
LEFT JOIN auth_temp_function_item tf ON pi.function_item_id = tf.rec_id
WHERE pi.permission_id IN (SELECT rec_id FROM auth_temp_permission WHERE function_id = {function_id});
```

### Step 3: 生成脚本

默认生成纯 SQL：`{菜单名称}_菜单脚本.sql`，只包含目标数据库可执行的 SQL。用户明确要求 Flyway/Groovy 时生成 `.groovy`，按目标迁移仓库的命名规则与相邻脚本包装。生成脚本不执行写入。

## 脚本生成规范

### 必查表清单

按顺序检查以下表，**只生成有数据的表**：

1. `auth_temp_function` — 功能模板
2. `auth_temp_function_item` — 功能项（通常无数据）
3. `auth_temp_function_product` — 功能归属（4.5.2.0+版本）
4. `auth_temp_application_function` — 模板功能关系
5. `auth_temp_permission` — 模板菜单
6. `auth_temp_permission_item` — 菜单功能项关系（通常无数据）
7. `auth_temp_group_permission` — 角色菜单关系

### 脚本格式与重复执行

- **纯 SQL（默认）**：写明确列名的 INSERT 和必要的版本 UPDATE，不使用 `if`、`notExist`、`executeMultiCommand`。默认仅供首次导入，重复执行可能冲突或再次增加版本号，不能声称整体幂等。
- **Groovy（用户指定）**：在 `.groovy` 内使用 `notExist()` 防止重复插入；代码字符串直接使用普通引号，不能把字面 `\"` 写到源码中。外层注释用 `//`，SQL 内注释用 `--`。参考 [references/menu_script_template.md](references/menu_script_template.md)。
- **重复执行边界**：防重复 INSERT 不等于整个脚本幂等。版本更新按仓库已验证方案处理；若每次执行都 `+0.01`，交付时必须说明这个副作用，不能承诺可无限重跑。用户要求整体幂等时，先确认运行器支持的变更跟踪/执行记录方式，再生成条件版本更新，不臆造 Groovy API。

### 数据规则

- 关系表的重复判断使用实际业务唯一键，例如 `app_id + function_id`；不要只按导出记录的 `rec_id` 判断关系不存在。
- 源库的 `app_id`、父节点、角色和功能 ID 不保证在目标库相同。跨环境导入须核对目标映射；没有目标核对时明确脚本前置条件，不擅自创造映射或覆盖已有菜单。
- 有菜单变更时更新受影响的应用模板版本；全局功能模板版本一次交付更新一次，不能按每个模板重复增加。
- 字节、NULL、时间与字符串按目标方言和真实列定义序列化。查询中的 `app_name` 等辅助展示列不写入业务表。

### 脚本存放路径

默认保存到 `.mixed/deliverables/yyyy-MM-dd/`；用户指定迁移仓库时按该仓库草稿目录规则保存 `.groovy`，不修改已发布迁移。

## 参考

完整的查询字段和数据模板可参考技能目录下的 `references/menu_script_template.md`。
