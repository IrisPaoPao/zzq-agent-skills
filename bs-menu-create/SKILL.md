---
name: bs-menu-create
description: 医疗费用/对账平台运营平台 (dev-operations) 菜单创建/新增技能。根据用户提供的菜单名称、code、父菜单，自动查询同级数据、生成 INSERT SQL 脚本（含 function/permission/group_permission 全链路）。触发场景：用户说"创建菜单"、"新增菜单"、"加菜单"、"生成菜单脚本"、"创建菜单SQL"、"导入菜单"，或提到 `auth_temp_function`、`reconciliation:xxx` 类菜单 code、"挂到XX菜单下"等场景，**即使没有明说"创建"也要触发**。注意区别于 bs-menu-export（仅导出已存在菜单）：本技能是新增菜单到运营平台库。
---

# 菜单导入脚本生成

## 这个技能在干什么

运营平台 (dev-operations 库) 是 SaaS 权限菜单的源头模板。新菜单由 5~6 张 `auth_temp_*` 表协作描述：功能模板、应用归属、模板与功能关系、菜单、按钮权限、角色绑定。本技能根据用户的菜单描述，自动**查询同级现状**、**生成全链路 INSERT SQL**，避免人工硬编码 ID 与字段。

最后会生成一份纯 SQL 脚本交给用户，由用户自己粘贴到 Navicat / DBeaver / usql 执行（可能加事务）。**不自动执行写入**，因为运营平台是共享库，写错代价大。

## 数据库连接

| 参数 | 值 |
|------|-----|
| Host | 172.18.163.23 |
| Port | 3306 |
| Database | dev-operations |
| User | root |
| Password | **见 `~/.config/bs-menu/secret.env` 或问用户** |
| 推荐 CLI | `usql` （已安装在 `~/.local/bin/usql`）|
| 备用 CLI | `/opt/homebrew/opt/mysql-client/bin/mysql` |

读取密码（本地配置，不入仓库）：

```bash
DB_PASS=$(grep '^OPERATIONS_DB_PASSWORD=' ~/.config/bs-menu/secret.env 2>/dev/null | cut -d= -f2- | tr -d "'\"")
```

如果文件不存在，**问用户**索取一次，并提示用户创建该文件以便后续复用：

```bash
mkdir -p ~/.config/bs-menu
echo "OPERATIONS_DB_PASSWORD='你的密码'" > ~/.config/bs-menu/secret.env
chmod 600 ~/.config/bs-menu/secret.env
```

usql 连接串模板（密码用环境变量）：

```bash
DB_PASS_ENC=$(python3 -c "import urllib.parse; import os; print(urllib.parse.quote(os.environ['DB_PASS'], safe=''))")
DB_PASS="$DB_PASS" usql "mysql://root:${DB_PASS_ENC}@172.18.163.23:3306/dev-operations?charset=utf8mb4" -c "SELECT ..."
```

或直接对接 usql 别名（推荐 — 把 DSN 存在 usql 配置里）：

```bash
# ~/.usqlrc 增加一次
operations = mysql://root:<urlencoded密码>@172.18.163.23:3306/dev-operations?charset=utf8mb4

# 之后直接用别名
usql operations -c "SELECT ..."
```

注意 `@` 和 `#` 之类特殊字符需 URL 编码（`@` → `%40`，`#` → `%23`）。

## 工作流程

### Step 0：先用 usql 探查，避免重复插入

任何新增请求进来，第一件事是查目标 code / 名字是否已存在。**重复就停止**。

```bash
usql operations -c "
SELECT rec_id, name, code, function_code, parent_id, rec_created_time
FROM auth_temp_function
WHERE code = '<目标code>' OR name = '<目标名称>';"
```

（`operations` 是 usql 别名，连接信息见上面"数据库连接"。如果别名未配置，先按上面说明在 `~/.usqlrc` 配置，或临时用完整连接串）

#### 如果 0 行
继续后续步骤。

#### 如果 ≥ 1 行：必须停止，但**别把诊断塞进 SQL 文件**

错误做法（曾经踩过的）：把所有诊断信息当注释塞进 `<菜单名>_菜单脚本.sql`，文件名误导用户以为有 SQL 可执行，但里面其实全是注释。

正确做法：

1. **不生成 SQL 文件**（任何 .sql 文件都不要写）
2. **生成单独的报告文件**：`<菜单名>_DUPLICATE_REPORT.md`
3. 报告内容包括：
   - 已存在记录的 rec_id、name、code、function_code、parent_id、rec_created_time
   - 已挂载的模板（auth_temp_application_function）
   - 已绑定的角色（auth_temp_group_permission）
   - 父菜单的实际位置（确认是不是用户期望的）
4. 报告末尾**必须明确询问用户**："请确认下一步：A) 删除旧记录重建 B) 修正旧记录字段（生成 UPDATE 脚本）C) 改用新的 code/name D) 取消本次操作"

### Step 1：理解菜单类型与必生成的表

| 类型 | 特征 | 例子 |
|------|------|------|
| `category`（分类菜单） | 像文件夹，无 code，category=1, leaf=0 | "对账管理"、"差异管理" |
| `function`（叶子功能） | 有 code，category=0, leaf=1 | "差异数据自动核销" |
| `function_item`（按钮权限） | 挂在叶子功能下的按钮 | "新增"、"删除"、"导出" |

如果用户没明说，**根据是否提供 code 推断**：有 code → function；没 code 且名字像文件夹 → category；同时还提供按钮列表 → function + 多个 function_item。

#### 每种类型必须生成的表（关键！容易漏 permission）

| 表 | 叶子菜单 (function) | 分类菜单 (category) |
|----|--------------------|---------------------|
| auth_temp_function | ✅ 必须 | ✅ 必须 |
| auth_temp_function_product | ✅ 必须 | ⚠️ 看产品归属，常省略 |
| auth_temp_application_function | ✅ 必须（每个模板一条）| ✅ 必须（每个模板一条）|
| **auth_temp_permission** | **✅ 必须（每个模板一条）** | **✅ 必须（每个模板一条）⚠️ 极易漏！** |
| auth_temp_function_item | 可选（用户给按钮列表才生成）| ❌ 不生成 |
| auth_temp_permission_item | 可选（同 function_item）| ❌ 不生成 |
| auth_temp_group_permission | ✅ 必须 | ⚠️ 通常不绑角色，省略 |

**为什么分类菜单也要 permission**：前端菜单树是从 `auth_temp_permission` 渲染的，而不是 `auth_temp_function`。如果只插 function 不插 permission，菜单树会断层——用户在前端看不到这个分类节点，子菜单也"挂不上"。`auth_temp_function` 是模板抽象层，`auth_temp_permission` 才是真实渲染层。**写脚本时必须显式问自己：分类菜单的 permission 行写了吗？**

### Step 2：用 usql 探查参照功能

参照功能用来"克隆"出新菜单的 product、permission、group_permission 字段，避免漏字段或瞎猜。

**参照功能选择策略**：
- 优先：用户指定的兄弟菜单（最稳）
- 次选：父菜单（适用于按层级新增，但权限/产品归属可能不直接适用）

```bash
# 查参照功能（按 name 精确再模糊）
usql ... -c "SELECT * FROM auth_temp_function WHERE name = '差异数据手动处理' LIMIT 1"

# 拉取它的 5 表关联数据
usql ... -c "
SELECT * FROM auth_temp_function_product WHERE function_id = <参照ID>;
SELECT * FROM auth_temp_application_function WHERE function_id = <参照ID>;
SELECT * FROM auth_temp_permission WHERE function_id = <参照ID>;
SELECT * FROM auth_temp_group_permission WHERE permission_id IN (SELECT rec_id FROM auth_temp_permission WHERE function_id = <参照ID>);
"
```

读字段时注意：

- `bit(1)` 类型用 `field+0 as field` 转成 0/1 阅读，写回时用 `b'0'` / `b'1'`
- 用 `--default-character-set=utf8mb4`（mysql CLI）或 `?charset=utf8mb4`（usql），否则中文乱码
- usql 默认输出对齐表，看 bit 字段时可加 `+0` 转数字

### Step 3：决定父级与同级排序

这一步**不能拍脑袋**，必须查实际数据。曾经踩过的坑：参照功能选了父级，结果新菜单 parent_id 指向了父级而不是父级再上一层；或者 display_sort 写 1，结果与同级 2045/2046/2047 完全脱节。

**parent_id 的判定**：

```
若 type = category 或 参照功能本身就是 category 节点：
  → 新节点 parent = 参照功能的 rec_id
否则（参照功能是 function，新菜单作为它的兄弟）：
  → 新节点 parent = 参照功能的 parent_id
```

**display_sort 的判定**：

```sql
-- function 表
SELECT COALESCE(MAX(display_sort), 0) + 1 FROM auth_temp_function
WHERE parent_id = <目标父级>;

-- permission 表（按每个 app_id 分别计算）
SELECT COALESCE(MAX(display_sort), 0) + 1 FROM auth_temp_permission
WHERE parent_id = <permission父级> AND app_id = <目标app_id>;
```

### Step 4：生成 ID（绝不硬编码）

**为什么不能硬编码**：运营平台真实 ID 用雪花算法，量级是 17~19 位（如 `6785333542047836458`）。如果你硬编一个"远大于 max"的数，运营平台后续录入新菜单的雪花 ID 就会撞上，造成主键冲突、数据回灌失败、甚至误覆盖别人的菜单。

**正确做法**：用当前 unix 时间戳作为 ID 高位，加 4 位序号 + 5 位随机/占位：

```
ts = 当前 unix timestamp（秒，10 位）
id = ts * 1e9 + 序号 * 1e5 + 占位 * 0
```

例：`1781593176` → `1781593176000100001`（function）、`1781593176000200002`（function_product）、依此类推。这样生成的 ID 量级 ~1.78e18，与现实 ID 在同一空间，但因为时间戳更新而单调递增，与历史数据不冲突。

执行前用 usql 验证候选 ID 未占用：

```sql
SELECT rec_id FROM auth_temp_function WHERE rec_id = <候选ID>;
SELECT rec_id FROM auth_temp_permission WHERE rec_id = <候选ID>;
-- ...每张表都查
```

### Step 5：function_code 取下一个可用编号

⚠️ **这一步最容易错**：之前实测多次出现取 F2109 而真实库里 max 已经到 F3670+，导致主键冲突或唯一索引冲突。

`function_code` 是**全表唯一序号**，**不是**同 parent / 同 app_id 内唯一。所以 `SELECT MAX` 时**不能加任何 WHERE**（除了过滤格式）：

```sql
-- ✅ 正确：必须实际跑 usql 执行这条 SQL，看返回值
usql operations -c "
SELECT CONCAT('F', LPAD(MAX(CAST(SUBSTRING(function_code, 2) AS UNSIGNED)) + 1, 4, '0')) AS next_fcode
FROM auth_temp_function
WHERE function_code REGEXP '^F[0-9]+$';"
```

执行结果（例）`next_fcode | F3671`——这才是要用的值。

**绝对不要**：

- ❌ 凭印象写 `F2109` 之类的小值
- ❌ 加 `WHERE parent_id = X` 限制扫描范围
- ❌ 用 `LIKE 'F0%'` 这种只看 F0 开头的过滤
- ❌ 不查直接写一个看起来"小一点没用过的"

**写脚本前必须确认**：你刚才执行 usql 取出的 max 是多少？记下来，新 function_code 是 max+1。如果你不确定 max 的实际值，重跑一次 SELECT。

注意：库里既有 F0001~F3670 这种 4 位 padded 的，也有 F08942 这种长度不一的。**沿用 4 位 padded** 最规范——上面 SQL 的 `LPAD(..., 4, '0')` 即可。

### Step 6：生成最终脚本（纯 SQL）

输出文件名：`{菜单名称}_菜单脚本.sql`

模板见 [references/script_template.md](references/script_template.md)。关键点：

1. **字节字段** 用 `b'0'` / `b'1'`（不是 0/1 也不是 false/true）
2. **NULL 字段** 显式写 `NULL`，不省略
3. **不要包 Groovy `notExist()` / `executeMultiCommand`**，除非用户明确说要 Flyway 风格
4. **顺序很重要**：function → function_product → application_function → permission → permission_item → group_permission → 版本号更新
5. **末尾必须有版本号 +0.01**，否则模板永远不会同步到产品端

```sql
UPDATE auth_temp_application SET template_version = template_version + 0.01 WHERE rec_id = <app_id>;
UPDATE auth_temp_function_version SET template_version = template_version + 0.01;
```

每个 app_id（每个模板）都要执行一次第一行，第二行只需一次。

### Step 7：交付与提示

把 SQL 文件路径告诉用户，并提醒：

- 这是**非幂等**脚本，重复执行会主键冲突
- 建议手工外包 `START TRANSACTION; ... COMMIT;`
- 如果要执行，目标库是 `172.18.163.23:3306/dev-operations`（运营平台）

## 常见请求模式与处理

| 用户说 | 你应该 |
|--------|--------|
| "新增 X 菜单，挂在 Y 下面" | 默认 type=function（因为有 X 名）。Y 用 name 模糊查找。问 code、应用模板、角色（如未给） |
| "导入菜单 reconciliation:diff:auto:writeoff" | 提取 code，反向问名字与父菜单 |
| "和差异数据手动处理同级，加个自动核销" | 参照功能 = "差异数据手动处理"（兄弟）；新菜单 parent = 参照的 parent_id |
| 用户给了一堆按钮："新增、删除、详情、编辑" | 生成 N 条 function_item + N 条 permission_item |
| "对账平台下加个分类叫 XX" | type=category，code 留空，category=1, leaf=0 |

## 字段默认值参考

详见 [references/field_defaults.md](references/field_defaults.md)。核心字段速查：

| 表 | 字段 | function 默认 | category 默认 |
|----|------|---------------|---------------|
| function | enabled | b'1' | b'1' |
| function | category | b'0' | b'1' |
| function | leaf | b'1' | b'0' |
| function | url / mobile_url / applicable_version | '' | '' |
| permission | internal | b'1'（克隆参照）| b'1' |
| permission | open_mode | 0 | 0 |
| permission | applied_range | '0' | '0' |

## 角色绑定 (group_permission)

默认逻辑：

- 如果用户没说，默认绑定**单位管理员**（`group.code = '001'`，每个模板下都有）
- 单位管理员的 group_id 通过 `app_id` 反查：

```sql
SELECT rec_id FROM auth_temp_group WHERE app_id = <模板app_id> AND code = '001';
```

- 如果用户说"和参照菜单一样"，则克隆参照菜单 permission 下所有 group_permission 行

## 多模板支持

新菜单常常要同步到多个应用模板（KSYTCommon / PT0001 / PT0081 / CSYTHCommon）。**每个模板都要重复**：

- 一条 `auth_temp_application_function`
- 一条 `auth_temp_permission`（parent_id 在每个模板下不同，要分别查）
- 一条或多条 `auth_temp_group_permission`
- 一条版本号更新

`auth_temp_function` 和 `auth_temp_function_product` 全局只一条。

各模板的 app_id（用户没指定时）：

```sql
SELECT rec_id, name, code FROM auth_temp_application
WHERE code IN ('KSYTCommon','PT0001','PT0081','CSYTHCommon');
```

## 必查清单（按顺序）

执行前依次确认：

1. ✅ 已用 usql 查过目标 code 不存在；若存在已生成 DUPLICATE_REPORT.md（不是 SQL 文件）
2. ✅ 已找到参照功能并 dump 它的 5 表数据
3. ✅ parent_id 已根据"参照是 category / function"决定
4. ✅ display_sort 取的是同级 max+1（function 和 permission 分别算，permission 还要按 app_id 拆）
5. ✅ function_code 取的是 F + (max+1) padded，**SELECT MAX 时未加 WHERE 限制**
6. ✅ ID 是基于当前时间戳生成，不是硬编码大数
7. ✅ bit 字段用 `b'0'/b'1'`，NULL 显式写
8. ✅ **分类菜单也写了 auth_temp_permission 行**（最容易漏！）
9. ✅ 末尾有版本号 +0.01（每个 app_id 一行）
10. ✅ 已告诉用户脚本路径，不擅自执行写入

## 失败案例（务必避免）

参考 [references/lessons.md](references/lessons.md)，记录了真实踩过的坑（parent_id 错位 5158... vs 5745...、display_sort=1 而非 2048、硬编码 ID 撞 max 等）。
