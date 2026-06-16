# 真实失败案例与教训

## Case 1: parent_id 错位（差异处理 vs 差异管理）

**症状**：用 import.sh 导入"差异数据自动核销"菜单后，新菜单出现在了错误的父级下。

**原因**：用户传 `--parent "差异处理"`，模糊匹配命中了 `5158699719040496226 (F1273 差异处理)`，但这是另一棵树（旧版 sass-system）下的分类节点。真正想要的父级是 `5745853084484898846 (F2991 差异管理)`，对应 KSYTCommon 模板下的菜单。

**教训**：

1. 父级名称如果在多棵树都存在，必须用 **function_code** 或 rec_id 精确指定
2. 查询时多看几行 `WHERE name LIKE '%差异%'` 的结果，识别歧义
3. 找到候选父级后，进一步看它的 `auth_temp_application_function`，确认它在目标模板下也有节点

**预防 SQL**：

```sql
-- 输出多行供人确认
SELECT rec_id, name, code, function_code, parent_id
FROM auth_temp_function
WHERE name LIKE '%<父级关键字>%' OR code LIKE '%<父级关键字>%'
ORDER BY parent_id;
```

如果出现多行，必须问用户是哪一个。

## Case 2: ID 硬编码冲突隐患

**症状**：手写脚本时直接给新菜单分配 `6785333542047900001` 这种"远大于当前 max"的 ID。

**问题**：

1. 看似安全的 max+1 实际上离当前 max（`6785333542047836458`）只差 64,000 不到，运营平台一秒就能录满
2. 真正的雪花 ID 是单调递增的，几个月后就会撞上你写死的值
3. 撞上后是**无声覆盖**——主键已存在的 INSERT 会报错，但如果 deleted=true 的旧记录正好在这个 ID 上，会引发非常诡异的现象

**教训**：永远用**当前时间戳基底**生成 ID，而不是 max+1。时间戳基底 ID 量级 = `当前ts * 1e9` ≈ `1.78e18`，与 ID 算法在同一空间但永远比未来雪花更早分配。

```python
ts = int(time.time())            # 1781593176
function_id = ts * 10**9 + 100001    # 1781593176000100001
```

## Case 3: display_sort = 1 而不是同级最大值+1

**症状**：用 import.sh 时，`display_sort` 被设成 1，但同级菜单已经到 2047，导致新菜单显示在最前面（错乱）。

**原因**：脚本里写了 `display_sort = 1` 作为 fallback，并未真去查同级最大值。

**预防**：每次必须 `SELECT MAX(display_sort) WHERE parent_id = X AND app_id = Y` 实际查询，且 function 表和 permission 表分别算（前者按 parent_id，后者按 parent_id + app_id）。

## Case 4: 漏更新 template_version

**症状**：脚本插入数据后，运营平台界面看得到，但是产品端（医院租户）同步不到新菜单。

**原因**：忘了 `UPDATE auth_temp_application SET template_version = template_version + 0.01`。这个版本号是产品端轮询同步的触发条件，不更新就永不同步。

**预防**：每个脚本末尾必须有：

```sql
UPDATE auth_temp_application SET template_version = template_version + 0.01 WHERE rec_id = <每个app_id>;
UPDATE auth_temp_function_version SET template_version = template_version + 0.01;
```

第一行**每个模板都要执行一次**（不能省）。第二行只需一次。

## Case 5: bit 字段写错（写 0/1 字面量）

**症状**：执行 INSERT 报错 `Data truncation: Data too long for column 'enabled' at row 1`。

**原因**：MySQL bit(1) 字段不接受 `0`/`1` 字面量，必须用 `b'0'` / `b'1'`（或 BIT 字面量 `0x0` / `0x1`）。

**预防**：所有 bit 字段写 `b'0'` 或 `b'1'`，无例外。

## Case 6: 中文乱码

**症状**：脚本生成的中文菜单名插入后变成 `???` 或 `é½îñ`。

**原因**：mysql CLI / usql 连接没指定 utf8mb4。

**预防**：

- mysql CLI: `--default-character-set=utf8mb4`（必须）
- usql: 连接串加 `?charset=utf8mb4`

## Case 7: 重复插入而未先校验

**症状**：库里出现两条同名同 code 的记录，分别来自手写脚本和 import.sh 各自一次的插入。

**原因**：第二次插入前没用 SELECT 校验是否已存在，直接 INSERT。

**预防**：

```sql
-- 必查（应得 0 行）
SELECT rec_id, name, code, function_code, rec_created_time
FROM auth_temp_function
WHERE code = '<目标>' OR name = '<目标>';
```

如果 ≥ 1 行，**停止生成**，向用户报告：

```
⚠️ 库里已存在该菜单：
  rec_id=..., name=..., function_code=..., 创建于 ...

要怎么处理？
  1) 删除旧的，重新插入
  2) 修正旧的字段（生成 UPDATE 语句）
  3) 取消本次操作
```

## Case 8: function_code 用了不规范的 F08942（5 位）

**症状**：库里出现 `F08942` 这种 5 位 function_code，与同级 F3388/F3389/F3390 不一致。

**原因**：脚本生成时没考虑现有数据的 padding 习惯，导致格式不一致。

**预防**：用 4 位 padded 格式（`F + 4 位数字`），与库里大多数记录一致：

```sql
SELECT CONCAT('F', LPAD(MAX(CAST(SUBSTRING(function_code, 2) AS UNSIGNED)) + 1, 4, '0'))
FROM auth_temp_function
WHERE function_code REGEXP '^F[0-9]{4}$';  -- 只看 4 位的
```

## Case 9: function_code 错位（取了 F2106 而真实 max 是 F3670）

**症状**：technique 在 SELECT MAX 时加了 WHERE（如 `WHERE parent_id = X`），结果取出来的 max 只是该 parent 下最大值（如 F2106），但库里全局最大已经到 F3670 了。生成 F2107 又会撞上别处 F2107 的真实记录，造成主键 / 唯一索引冲突。

**原因**：错把 function_code 当成"同 parent 内唯一"。实际上它是**全表唯一序号**。

**预防**：function_code 的 SELECT MAX **不加任何 WHERE**（除了过滤格式）：

```sql
-- ✅ 全局扫描
SELECT CONCAT('F', LPAD(MAX(CAST(SUBSTRING(function_code, 2) AS UNSIGNED)) + 1, 4, '0'))
FROM auth_temp_function
WHERE function_code REGEXP '^F[0-9]+$';

-- ❌ 错误（实测踩过）
SELECT MAX(...) FROM auth_temp_function WHERE parent_id = X;
```

`display_sort` 是同级排序（用 parent_id 做范围）。`function_code` 是全局序号（不加 WHERE）。两者不要混淆。

## Case 10: 分类菜单只插了 function 没插 permission

**症状**：分类菜单插完后，前端菜单树里看不到这个分类，子菜单也"挂不上"——但运营平台后台界面查得到这条 function 记录。

**原因**：忘了 `auth_temp_permission` 也要为分类菜单写一行。`auth_temp_function` 是模板抽象层（菜单元数据），但前端实际渲染读的是 `auth_temp_permission`。如果 permission 树缺失中间节点，子菜单的 parent_id 找不到对应节点，整棵子树就显示不出来。

**预防**：每次写脚本前过一遍清单：

```
function 行写了吗？             ✅
permission 行写了吗？           ⚠️ 容易漏！分类菜单一样要！
application_function 写了吗？   ✅
版本号 +0.01 写了吗？           ✅
```

`auth_temp_permission` 对分类菜单的关键差异：

```sql
-- 分类菜单的 permission 行
INSERT INTO auth_temp_permission
(rec_id, name, internal, parent_id, open_mode, display_sort, app_id,
 category, function_id, leaf, applied_range, enabled, ...)
VALUES
(<id>, '<分类名>', b'1', <模板下父permission的rec_id>, 0, NULL,
 <app_id>, b'1', <function_id>, b'0', '0', b'1', ...);
                                  ^      ^
                              category=1 leaf=0（与叶子菜单相反）
```

**唯一不写 permission 的情况**：`auth_temp_function` 顶层的根分类，且这个根分类没有任何模板挂它。这种情况罕见，普通新增菜单不会遇到。

