# 按任务查阅命令

以下 `dev`、`team`、`app` 均为占位名，实际调用前从配置和资源查询确认。写入示例全部是预演；在用户已授权的同一操作上追加 `--execute` 才生效。

## 查询和排查

```bash
bsq-k8s config list
bsq-k8s -p dev login
bsq-k8s -p dev version
bsq-k8s -p dev api-resources
bsq-k8s -p dev get namespaces -o table
bsq-k8s -p dev get deploy -A -o table
bsq-k8s -p dev -n team get pods -l app=app
bsq-k8s -p dev -n team get pods --field-selector status.phase=Pending
bsq-k8s -p dev -n team describe deploy/app
bsq-k8s -p dev -n team events --for pod/app-pod
bsq-k8s -p dev -n team images deploy/app
bsq-k8s -p dev -n team images pod/app-pod
bsq-k8s -p dev -n team logs app-pod -c main --tail 100 --since 600 --timestamps
bsq-k8s -p dev -n team logs app-pod -c init-artifact --previous
bsq-k8s -p dev -n team top pods
bsq-k8s -p dev top nodes
bsq-k8s -p dev -n team can-i patch deployments --name app
```

日志 `--follow` 支持流式读取；空闲读取受 `--timeout` 限制，不保证无限保持连接。`top` 返回 CPU/内存原始量纲；metrics-server 未部署或权限不足就报告限制。资源列表自动读取 continue 分页。

## 部署、镜像和发布

```bash
bsq-k8s -p dev -n team image deploy/app --container business-init --tag artifact-1.2.3
bsq-k8s -p dev -n team image deploy/app --set business-init=registry:7005/team/business:artifact-1.2.3
bsq-k8s -p dev -n team restart deploy/app
bsq-k8s -p dev -n team scale deploy/app --replicas 2
bsq-k8s -p dev -n team pause deploy/app
bsq-k8s -p dev -n team resume deploy/app
bsq-k8s -p dev -n team rollout status deploy/app --wait --wait-timeout 300
bsq-k8s -p dev -n team rollout history deploy/app
bsq-k8s -p dev -n team rollout undo deploy/app --revision 12
```

镜像支持 Deployment/StatefulSet/DaemonSet/CronJob；重启支持前三者；扩缩容不支持 DaemonSet。`rollout status` 支持前三者；`history/undo` 当前只支持 Deployment。OnDelete 策略不会自动删旧 Pod；暂停的 Deployment 不允许直接 restart。CronJob 镜像更新影响后续任务，不更新已有 Job。

## 配置和通用资源

```bash
bsq-k8s -p dev -n team apply -f resources.yaml
bsq-k8s -p dev -n team create -f resources.yaml
bsq-k8s -p dev -n team replace -f resource.yaml
bsq-k8s -p dev -n team patch deploy/app --type merge -f patch.json
bsq-k8s -p dev -n team patch deploy/app --type json -f patch-array.json
bsq-k8s -p dev -n team label deploy/app owner=finance old-label-
bsq-k8s -p dev -n team annotate deploy/app release.example/version=1.2.3
bsq-k8s -p dev -n team env deploy/app --container main -f env.yaml
bsq-k8s -p dev -n team delete job/finished
```

清单支持 YAML 多文档和 `kind: List`；`-f -` 从 stdin 读取。`apply` 更新已有资源使用 Server-Side Apply，不启用 force conflicts；缺失资源用原子 POST 创建，避免并发创建后覆盖。依赖同批新建 Namespace/CRD 的清单按依赖拆批。预演和真实执行之间发生变化会冲突，不能自动覆盖。多资源没有事务，执行失败先查看结果再处理。

环境变量文件为键值对象，`null` 删除；支持 `{valueFrom: {secretKeyRef: {name: ..., key: ...}}}`，其余变量保留。不将明文凭据放 `--set`、命令参数或终端输出。

`api-get /apis/GROUP/VERSION/...` 用于尚未封装的读取，限制在当前连接；不支持 URL 跳转、proxy、exec 或任意写请求。`/readyz`、`/healthz`、`/livez` 原生健康检查需要相应 API 连接；KubeSphere Console 可能未代理这些路径，返回 HTML 时报告限制，不推断集群异常。

## 定时任务和节点

```bash
bsq-k8s -p dev -n team suspend nightly --value true
bsq-k8s -p dev -n team suspend nightly --value false
bsq-k8s -p dev -n team run-job nightly --name nightly-manual-20261022
bsq-k8s -p dev cordon worker-1
bsq-k8s -p dev uncordon worker-1
bsq-k8s -p dev taint worker-1 maintenance=true:NoSchedule
bsq-k8s -p dev taint worker-1 maintenance:NoSchedule-
```

`run-job` 创建新任务，不等于任务完成；查询 Job 状态、Pod 和日志验证结果。节点操作属于集群级操作，先确认节点和影响；NoExecute 污点会影响已有 Pod。无 drain、eviction 或强制删除的隐式动作。
