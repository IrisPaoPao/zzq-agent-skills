---
name: bs-menu-export
description: 医疗费用系统菜单脚本导出技能。根据菜单名称查询数据库（dev-operations），生成可导入的菜单脚本，支持幂等执行。触发场景：用户说"导出菜单脚本"、"生成XX菜单的脚本"、"菜单导出"。
---

# 菜单脚本导出

## 数据库连接

| 参数 | 值 |
|------|-----|
| Host | 172.18.163.23 |
| Port | 3306 |
| Database | dev-operations |
| User | root |
| Password | **见 `~/.config/bs-menu/secret.env` 或问用户** |
| JDBC URL | jdbc:mysql://172.18.163.23:3306/dev-operations?useUnicode=true;characterEncoding=utf-8;serverTimezone=GMT%2B8 |
| MySQL CLI | /opt/homebrew/opt/mysql-client/bin/mysql |
| 连接参数 | `--default-character-set=utf8mb4`（必须，否则中文乱码） |

读取密码（本地配置，不入仓库）：

```bash
DB_PASS=$(grep '^OPERATIONS_DB_PASSWORD=' ~/.config/bs-menu/secret.env 2>/dev/null | cut -d= -f2- | tr -d "'\"")
```

若配置不存在，向用户询问密码，或提示创建：

```bash
mkdir -p ~/.config/bs-menu
echo "OPERATIONS_DB_PASSWORD='你的密码'" > ~/.config/bs-menu/secret.env
chmod 600 ~/.config/bs-menu/secret.env
```

## 导出流程

### Step 1: 查询功能模板

```bash
DB_PASS=$(grep '^OPERATIONS_DB_PASSWORD=' ~/.config/bs-menu/secret.env 2>/dev/null | cut -d= -f2- | tr -d "'\"")
mysql -h 172.18.163.23 -P 3306 -u root -p"${DB_PASS}" dev-operations --default-character-set=utf8mb4 -e "
SELECT rec_id, name, code, function_code, parent_id
FROM auth_temp_function
WHERE name LIKE '%XXX%';
"
```

找到 `rec_id`（即 `function_id`）后，继续查询链路数据。

### Step 2: 查询完整链路数据

```bash
DB_PASS=$(grep '^OPERATIONS_DB_PASSWORD=' ~/.config/bs-menu/secret.env 2>/dev/null | cut -d= -f2- | tr -d "'\"")
mysql -h 172.18.163.23 -P 3306 -u root -p"${DB_PASS}" dev-operations --default-character-set=utf8mb4 -e "
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
"
```

### Step 3: 生成脚本

根据查询结果，生成 SQL 脚本文件。脚本命名规范：`{菜单名称}_菜单脚本.sql`

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

### 脚本格式规范

```sql
-- ================================================================
-- {菜单名称} - 菜单导出脚本
-- 生成时间: {YYYY-MM-DD}
-- 模板: {模板名称} rec_id={app_id}
-- ================================================================

-- 1. auth_temp_function 功能模板
if(notExist(\"select * from auth_temp_function where rec_id = {rec_id}\")){
    executeMultiCommand(\"\"\"
INSERT INTO `auth_temp_function`(...) VALUES (...);
    \"\"\")
}else {
    println(\"table auth_temp_function exist rec_id = {rec_id}\");
}

-- [继续其他表...]

-- 必须添加版本号更新语句，否则模板不会同步
if(!notExist(\"SELECT * FROM auth_temp_application WHERE rec_id =?\", [\"{app_id}\"])){
    executeMultiCommand(\"\"\"
update auth_temp_application set template_version=template_version+0.01 where rec_id={app_id};
update auth_temp_function_version set template_version=template_version+0.01;
    \"\"\")
}else {
    println(\"table auth_temp_application no exist rec_id = {app_id}， skip this update execute\")
}
```

### 关键规则

- **关系表判断禁止用 `rec_id`**，必须用业务字段组合判断（如 `app_id = X AND function_id = Y`）
- **必须用 `notExist()` 做前置检查**，支持幂等执行
- **必须更新版本号**（`template_version+0.01`），否则模板不会同步
- **字节字段**（enabled、deleted等）用 `b'0'` 或 `b'1'`
- **NULL 字段**显式写 `NULL`，不省略

### 脚本存放路径

生成的脚本文件保存到工作区，命名格式：`{菜单名称}_菜单脚本.sql`

## 参考

完整的查询字段和数据模板可参考技能目录下的 `references/menu_script_template.md`。
