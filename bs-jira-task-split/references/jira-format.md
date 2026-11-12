# Jira 字段与参考格式

## 参考需求 YLZHXT-22813

2026-10-20 只读核对结果，用作风格与关联结构示例；任务状态、人员和字段设置需实时复查。

- 后端样例：YLZHXT-24247、YLZHXT-24248、YLZHXT-24249。
- 前端样例：YLZHXT-24252、YLZHXT-25481。
- 任务类型是独立“编码任务”，`parent` 为空。
- 后端描述采用“需求、范围、数据 / 接口变更、联调与验收、工时说明、设计附件”。
- 前端描述主要写页面及交互范围，可以简洁，不要求照搬后端字段。
- 示例后端预估是 6h、前端有 8h；仅学习字段的写法。本用户当前要求每项不超过 4h，以本次预算为准。
- 示例任务中存在 `outwardIssue = 需求 Key`、类型 `Blocks` 的链接，需求侧看到 `inwardIssue = 编码任务 Key`。使用同样结构时，创建链接请求的 `inwardIssue` 填任务、`outwardIssue` 填需求，并在写入后检查实际返回方向。

## 补查 CLI 未展示的字段

先定位 `bsq-jira` 的 Python 解释器及实际包路径，阅读 `jira_cli.main`、`jira_cli.client` 的相关方法。下面接口写法已在参考案例中核对，不硬编码安装目录、凭据或本机地址：

```python
from jira_cli.main import _create_client

client = _create_client()
issue = client.get_issue("YLZHXT-xxxxx")
fields = issue["fields"]
meta = client._request("GET", "/issue/createmeta", params={
    "projectKeys": "YLZHXT",
    "issuetypeNames": "编码任务",
    "expand": "projects.issuetypes.fields",
})
link_types = client._request("GET", "/issueLinkType")
```

使用精确字段选择输出，禁止打印客户端、session、认证配置或完整响应。

2026-10-20 当前创建元数据中：

| 业务名称 | 字段快照 | 值示例 |
|---|---|---|
| 开发预估时间 | `customfield_11133`，字符串 | `4h` |
| 编码任务类型 | `customfield_11147`，单选 | 后端任务、pc前端任务、移动端任务 |
| 开发人员 | `customfield_10204`，用户 | 与 assignee 分开，未明确指定不填写 |
| 模块 | `components` | 05-数电发票、06-智慧收单等 |

这些 ID 只是定位线索，使用前必须从当前创建元数据按名称和 schema 唯一匹配。此环境的创建元数据未提供 `timetracking`，因此不能把工时写进不存在的创建字段。

优先使用 CLI 建单。需扩展字段时，在当前元数据确认可写后使用结构化字典：

```python
created = client.create_issue(fields_payload)
task_key = created["key"]  # 立即保存，后续关联失败时使用此 Key 恢复。
client._request("POST", "/issueLink", json={
    "type": {"name": verified_link_type},
    "inwardIssue": {"key": task_key},
    "outwardIssue": {"key": requirement_key},
})
verified = client.get_issue(task_key)
```

仅在明确建单授权范围内执行最后一段。字段结构、项目、组件和链接方向预检失败时停止，不能静默省略工时或链接。单独增加任务间依赖链接也需要任务范围确有该依赖，不为格式完整而自动增加。

## 服务归属校验示例

YLZHXT-18942 的入账预警扫描归属 `tax-lxcloud-invoice-used`（lx-used）。`CollectJobExecuteWarningJob` 位于 collect 业务服务，不能作为该需求的通知调度入口。应在 lx-used 增加入账统一通知任务，失败及超时扫描由该任务调度；消息 SDK 的复用与调度任务的跨服务复用要分别判断。
