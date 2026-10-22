---
name: bs-k8s
description: 通过 bsq-k8s CLI 和 HTTP API 管理 KubeSphere、Kubernetes，查询资源/日志/事件、定位容器版本、重启、升级、扩缩容、回滚及操作配置与定时任务。用户要求 K8s 或 KubeSphere 运维、部署排查和版本调整时使用；本地 JavaRun 与 Jenkins 构建分别使用对应技能。
---

# Kubernetes / KubeSphere 运维

使用 `bsq-k8s`，全程通过 HTTP，不打开浏览器。源 CLI 在 `bs-project-tools/bs-k8s-cli`，源 Skill 在 `zzq-agent-skills/bs-k8s`；不修改已安装副本。完整参数以 `bsq-k8s --help` 和子命令帮助为准；按任务读取 [commands.md](references/commands.md)。

## 定位与连接

1. 先 `command -v bsq-k8s`。本地维护时缺少命令可在已找到的 CLI 源目录运行 `python3 -m bs_k8s.cli`，或 `pipx install -e /实际路径/bs-project-tools/bs-k8s-cli`。不要猜测源码位置或远端安装地址。
2. 用 `config list` 查看连接元数据；结合用户指定环境确定 `--profile`。默认连接不代表用户本次目标，存在多个可能环境时先只读核对，不猜生产/测试环境。配置默认位于 `~/.config/bsq-k8s/config.json`，也可通过 `BS_K8S_CONFIG` 或 `--config` 指定。
3. `-p PROFILE login` / `version` 验证认证和平台。配置缺失时 `config add` 支持无回显输入、`--password-env`、`--password-stdin`、`--token-env`、`--token-stdin`。不在源码、命令参数或文档中写真实密码/Token，不展示配置文件与会话缓存正文。配置和缓存要求 0600。
4. 查 `get namespaces`、`get deployments -A`、`api-resources` 确认真实名称。命名空间资源明确传 `-n NAMESPACE`，避免依赖默认空间；`-A` 仅用于查询。资源同名或跨组歧义时使用 `--api-version`。

## 按意图执行

- **只看、探索、定位问题**：只读资源/镜像/事件/日志/状态。必要时可用默认 dry-run 验证变更请求，不加 `--execute`。
- **更新版本或重启**：先读取精确工作负载及 `images`，确认模块、容器、当前镜像、目标 tag、拉取策略和副本/发布策略，再运行专用写命令做预演。用户已明确授权且范围一致时，在预演通过后加 `--execute`，无需重复询问。仅要求生成方案或工具，不构成实际集群变更授权。
- **回滚**：先 `rollout history`，确认目标 revision 后预演 `rollout undo --revision N`。它恢复完整 Pod 模板，包括初始化镜像、环境变量与挂载；ConfigMap/Secret 外部内容不随之恢复。不把模糊的“上一版本”映射为猜测的镜像。
- **配置、网络、存储、RBAC、CRD**：通过资源发现核对作用域与 API 版本，再用 YAML/JSON 文件驱动 `apply/create/replace/patch/delete`。优先局部更新；`replace` 是完整替换。敏感配置通过私有文件输入，避免进入会话输出。
- **节点和调度**：`cordon/uncordon/taint` 默认预演。`NoExecute` 污点可能驱逐 Pod；删除 Namespace/PVC、缩容到 0 等必须在用户授权的具体范围内。

## Java 聚合服务的版本定位

业务制品经常来自 `initContainers[*].image`，主容器只运行通用 JDK。必须先 `images deployment/NAME`，按精确容器名定位业务模块；不能把 JDK tag 当作业务版本。`image --container NAME --tag TAG` 自动在普通/初始化容器中精确匹配；digest 或改仓库用 `--set NAME=完整镜像`。多个模块可重复 `--set`，一次变更同一个 Pod 模板。

聚合服务中更新一个模块会重建整个 Pod，同 Pod 的其他模块也会重启。相同 SNAPSHOT tag 的重启是否拉到新镜像取决于每个容器的 `imagePullPolicy`；不能承诺重启一定获取新制品。目标 tag 是否存在、制品是否构建成功需要另行核对；API dry-run 不验证镜像仓库。

## 变更与验证边界

- 所有资源写命令默认 server-side `dryRun=All`，只有 `--execute` 才真实生效；真实执行也先预演。输出 `persisted:false` 表示未变更。`--execute` 是技术开关，不替代用户授权。
- 命令用 UID/resourceVersion 防止覆盖并发修改。401、403、409、网络失败或超时后不盲目重试写请求，先读实际状态；401 可 `login --refresh` 后只读核对。批量清单跨资源没有事务，失败时报告已执行项和失败位置。
- `can-i` 在 KubeSphere 下可能检查的是代理服务账号，并不证明平台账号的完整权限。实际目标的服务端预演通过才证明该请求被接收。
- 实际变更后运行 `rollout status ... --wait`，再看 Pod 的初始化状态、实际 `imageID`、就绪与事件；必要时调用已知业务健康接口。分别报告“API 提交”“Pod 发布”“业务验证”；PATCH/预演成功都不等于端到端成功。
- 默认资源输出会隐藏 Secret/ConfigMap 正文、内联环境变量、命令参数和注解。只有任务确需敏感字段时显式 `--show-sensitive`，通过受控管道或私有文件处理，不能原样打印到会话。日志是原始文本，读取时限定容器、时间和行数，摘录前脱敏。
- 当前工具不支持 exec/attach/cp/port-forward、drain/eviction、客户端证书或 kubeconfig exec 插件认证。遇到此类请求明确工具边界，核对可用 kubectl 与相应授权，不用浏览器绕过。
