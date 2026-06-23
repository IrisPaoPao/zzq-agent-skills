---
name: bs-project-run
description: Use when starting, stopping, restarting, logging into, or verifying local BS Java services managed by bs-project-tools/bs-java-run, including starting all projects, checking localhost endpoints, refreshing tokens, resolving port conflicts, and troubleshooting processes/logs.
---

# bs-project-run

## 工具目录

工具目录：`/Users/zhangzhengqing/work/project/bs-project-tools/bs-java-run`

**重要**：如果工具目录不存在，立即停止并询问用户确认目录位置。不回退到旧路径，也不自行搜索目录。

**操作前必读**：在执行任何命令前，先读取工具目录下的 `JAVARUN.md`（服务清单），确认当前可用服务和参数格式。

## 前置条件

`JAVARUN.md` 中要求的运行环境必须满足：
- `JAVA_HOME` 指向的 Java 可执行文件有效
- `mvn` 命令全局可用（Maven）
- Nacos host/namespace 配置正确

**安装方式**：工具目录需先执行 `npm install` 安装依赖（commander + playwright）。

**运行方式**（确保 `bs-java-run` 命令可用）：

```bash
# 方式一：全局安装（推荐，安装后任何目录可用）
cd /Users/zhangzhengqing/work/project/bs-project-tools/bs-java-run
npm link
bs-java-run --version

# 方式二：直接运行（不依赖全局命令，需指定完整路径）
node /Users/zhangzhengqing/work/project/bs-project-tools/bs-java-run/bin/bs-java-run.js --help

# 方式三：添加 alias（临时）
alias bs-java-run='node /Users/zhangzhengqing/work/project/bs-project-tools/bs-java-run/bin/bs-java-run.js'
```

> 如果遇到 `zsh: command not found: bs-java-run`，说明未执行 `npm link` 或未添加 alias，使用方式二或三即可。

## 常用命令

### 统一 CLI 入口

所有操作通过 `bs-java-run` 命令执行，无需 cd 到工具目录，也无需 `./xxx.sh` 脚本。

```bash
bs-java-run --help        # 查看所有命令
bs-java-run --version     # 查看版本
```

### start 启动服务

```bash
bs-java-run start [service] [options]
```

- `[service]`：服务名（如 `saas-data-gateway`），省略时交互式选择
- `-y, --yes`：非交互模式，启动全部服务
- `-s, --skip-build`：跳过 Maven 编译（已编译过或仅改配置）
- `-H, --nacos-host <host>`：覆盖默认 Nacos 地址
- `-N, --nacos-ns <namespace>`：覆盖默认 Nacos 命名空间

**示例**：
```bash
bs-java-run start --yes                          # 启动全部
bs-java-run start saas-data-gateway --yes         # 启动指定服务
bs-java-run start --yes --skip-build              # 启动全部，跳过构建
bs-java-run start --yes -H 172.18.163.52:30003 -N saas-industry-dev
```

### stop 停止服务

```bash
bs-java-run stop [service] [options]
```

- `[service]`：服务名，省略时交互式选择
- `-y, --yes`：非交互模式，停止全部服务
- `-p, --skip-pid`：跳过 PID 文件检查，直接按端口清理

**示例**：
```bash
bs-java-run stop --yes                    # 停止全部
bs-java-run stop saas-data-gateway --yes  # 停止指定服务
```

### restart 重启服务

```bash
bs-java-run restart [service] [options]
```

参数同 `start`。

**示例**：
```bash
bs-java-run restart --yes
bs-java-run restart saas-data-gateway --yes --skip-build
```

### status 查看状态

```bash
bs-java-run status [service]
```

- `[service]`：指定服务名，省略时显示全部

输出：PID 状态、端口监听状态、日志文件路径。

### login 登录获取 Token

```bash
bs-java-run login [options]
```

- `-l, --headless`：无头模式（后台运行，不显示浏览器）
- `-t, --save-token <file>`：保存 token 到指定文件
- `-q, --quiet`：只输出 token 字符串，不输出 JSON

**登录流程**：
1. 确保 `JAVARUN.md` 中有登录配置（地址、账号、密码）
2. 运行 `bs-java-run login --headless`
3. 输出 JSON 格式，取 `token` 字段作为 `Authorization` 请求头值，**不加 Bearer 前缀**
4. Token 会自动缓存到 `~/.bs-java-run/token.json`

**示例**：
```bash
bs-java-run login --headless
bs-java-run login --headless --quiet
bs-java-run login --headless --save-token ~/.bs-token
```

### token 查看缓存 Token

```bash
bs-java-run token [options]
```

- `-q, --quiet`：只输出 token 字符串

用于脚本中获取已缓存的 token，无需重新登录。

**示例**：
```bash
bs-java-run token --quiet
# 输出：eyJhbGciOiJIUzI1NiIs...
```

## 端点验证

```bash
curl -H "Authorization: $(bs-java-run token --quiet)" -H "Function-Page-Id: <pageId>" "http://localhost:<port>/<context-path>/api/..."
```

上下文路径从服务配置或前端 Network 面板请求确认，不要假设。

## 向后兼容

以下旧脚本仍可用（内部自动调用 CLI）：
- `start_services.sh`
- `stop_services.sh`
- `restart_services.sh`
- `status_services.sh`
- `login.sh`

但推荐使用新 CLI 命令 `bs-java-run`。

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
| 启动无输出 | 查看 `logs/<service>.log` 或 `nohup.out`，除非 `LOG_DIR` 环境变量覆盖了日志路径 |
| 启动后消失 | 先 `bs-java-run status` 查状态，再查启动日志找异常栈 |
| Token 过期 code -3 | 重新跑 `bs-java-run login --headless` 刷新 token |
| 服务间调用失败 | 确认 Nacos 注册成功，检查 namespace/host 匹配 |
| bs-java-run 命令未找到 | 确认 `npm install` 已执行，且工具目录在 PATH 中，或使用 `node bin/bs-java-run.js` 直接运行 |
