---
name: bs-project-run
description: Use when starting, stopping, restarting, logging into, or verifying local BS Java services managed by bs-project-tools/bs-java-run, including starting all projects, checking localhost endpoints, refreshing tokens, resolving port conflicts, and troubleshooting processes/logs.
---

# bs-project-run

## 工具目录

工具目录：`/Users/zhangzhengqing/work/project/bs-project-tools/bs-java-run`

**重要**：如果工具目录不存在，立即停止并询问用户确认目录位置。不回退到旧路径，也不自行搜索目录。

**操作前必读**：在执行任何命令前，先读取工具目录下的 `JAVARUN.md`（服务清单）和 `start_services.sh` 脚本，确认当前可用服务和参数格式。

## 前置条件

`JAVARUN.md` 中要求的运行环境必须满足：
- `JAVA_HOME` 指向的 Java 可执行文件有效
- `mvn` 命令全局可用（Maven）
- Nacos host/namespace 配置正确

## 常用命令

**命令使用说明**：所有脚本可使用绝对路径直接执行，无需 cd 到工具目录；如果 cd 到工具目录，也可用 `./start_services.sh` 等相对路径形式。

**权限问题修复**：如果遇到 `Permission denied` 错误，先执行：
```bash
chmod +x /Users/zhangzhengqing/work/project/bs-project-tools/bs-java-run/*.sh
```

### start 启动服务

```bash
/Users/zhangzhengqing/work/project/bs-project-tools/bs-java-run/start_services.sh --service <name|all> [--skip-build] [--nacos-host <host>] [--nacos-ns <namespace>]
```

- `--service <name|all>`：指定服务名或 `all` 启动全部
- `--skip-build`：跳过 Maven 编译（已编译过或仅改配置）
- `--nacos-host/--nacos-ns`：覆盖默认 Nacos 地址和命名空间

### stop 停止服务

```bash
/Users/zhangzhengqing/work/project/bs-project-tools/bs-java-run/stop_services.sh --service <name|all> [--skip-pid]
```

- `--skip-pid`：跳过 PID 文件检查，强制杀进程

### restart 重启服务

```bash
/Users/zhangzhengqing/work/project/bs-project-tools/bs-java-run/restart_services.sh --service <name|all> [--skip-build] [--nacos-host <host>] [--nacos-ns <namespace>]
```

参数同 start。

### status 查看状态

```bash
/Users/zhangzhengqing/work/project/bs-project-tools/bs-java-run/status_services.sh --service <name|all>
```

输出 PID、端口、运行状态。

## 登录流程

1. cd 到工具目录
2. 首次运行先执行 `npm install` — **仅用于 Node 登录脚本和 proto-server.js，不是 Java 服务构建依赖**
3. 执行 `./login.sh --headless`
4. 输出 JSON 格式，取 `token` 字段作为 `Authorization` 请求头值，**不加 Bearer 前缀**

## 端点验证

```bash
curl -H "Authorization: <token>" -H "Function-Page-Id: <pageId>" "http://localhost:<port>/<context-path>/api/..."
```

上下文路径从服务配置或前端 Network 面板请求确认，不要假设。

## proto-server.js

**说明**：这是可选的原型页面/本地 API 代理服务，不是启动 Java 服务的必需步骤。

启动命令：
```bash
node proto-server.js
```

环境变量：
- `PROTO_PORT`：默认 `3456`
- `PROTO_HTML_PATH`：proto HTML 静态文件目录

端点：
- `/login`：登录页面
- `/proxy/<port>/<path>`：端口代理转发

## 服务清单维护

`JAVARUN.md` 维护所有可启动服务的清单，包含服务名、端口、依赖关系、启动顺序、必要环境变量。新增或调整服务时需同步更新此文件。

## 故障排查

| 现象 | 排查步骤 |
|------|----------|
| 端口冲突 | `lsof -i :<port>` 找占用进程，改端口或杀冲突进程 |
| 启动无输出 | 查看工具目录下 `logs/<service>.log` 或 `nohup.out`，除非 `LOG_DIR` 环境变量覆盖了日志路径 |
| 启动后消失 | 先 `status_services.sh` 查状态，再查启动日志找异常栈 |
| Token 过期 code -3 | 重新跑 `login.sh --headless` 刷新 token |
| 服务间调用失败 | 确认 Nacos 注册成功，检查 namespace/host 匹配 |
| Permission denied | 执行 `chmod +x /Users/zhangzhengqing/work/project/bs-project-tools/bs-java-run/*.sh` 给脚本加执行权限 |
