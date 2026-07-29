---
name: bs-project-run
description: 管理由 bs-project-tools/bs-java-run 托管的本地 BS Java 服务，并获取、读取或刷新本地开发 Token。只要任务涉及本地服务启动、停止、构建、重启、状态、日志、端口冲突、localhost 接口验证，或登录、获取、读取、刷新 Token（即使用户未提及 bs-java-run），都必须使用本 Skill；服务操作优先 `bs-java-run` CLI，不得自行拼启动命令或退回旧 shell 脚本；Token 必须经 `bs-java-run login` 或 `bs-java-run token` 获取，不得手工调用登录接口、解析配置文件或直接读取 Token 缓存文件。
---

# bs-project-run

## 工具目录

工具目录：`/Users/zhangzhengqing/work/project/bs-project-tools/bs-java-run`

**重要**：如果工具目录不存在，立即停止并询问用户确认目录位置。不回退到旧路径，也不自行搜索目录。

**操作前必读**：在执行任何命令前，先读取工具目录下的 `JAVARUN.md`（共享规则）和 `JAVARUN.local.md`（本机实际服务、环境与账号配置）。`JAVARUN.local.md` 不存在或未配置目标服务/环境时，停止并提示用户初始化，不要猜测服务名、端口、Nacos 或账号。不要输出登录账号、密码等敏感值。

## 前置条件

运行环境必须满足：
- `BS_JAVA_HOME` 或 `JAVARUN.local.md` 的“java 环境地址”指向有效 Java 可执行文件
- `mvn` 命令全局可用（Maven）
- Nacos host/namespace 配置正确
- 内网数据库、Nacos 或 Oracle 连接异常时，先检查全局代理/`NO_PROXY` 是否放行内网地址

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

### build 构建服务

```bash
bs-java-run build [service] [options]
```

- `[service]`：服务名（如 `saas-data-gateway`），省略时交互式选择
- `-y, --yes`：非交互模式，构建全部服务

**示例**：
```bash
bs-java-run build --yes                    # 构建全部
bs-java-run build saas-data-gateway --yes  # 构建指定服务
```

**依赖缺失处理红线**：如果构建失败原因是 Maven 依赖解析失败、制品/版本不存在、仓库不可达、缺少三方或内部依赖，不要尝试修改 `pom.xml`、替换 jar、执行临时依赖修复或反复换参数重试。立即停止当前启动/构建任务，保留并汇报缺失依赖坐标、仓库地址、错误摘要和失败命令，交给人工排查。

### start 启动服务

```bash
bs-java-run start [service] [options]
```

- `[service]`：服务名（如 `saas-data-gateway`），省略时交互式选择
- `-y, --yes`：非交互模式，启动全部服务
- `-b, --build`：启动前先执行 Maven 构建（默认不构建）
- `-H, --nacos-host <host>`：覆盖默认 Nacos 地址
- `-N, --nacos-ns <namespace>`：覆盖默认 Nacos 命名空间
- `-T, --startup-timeout <seconds>`：覆盖启动等待超时时间，默认 420 秒
- `-e, --env <name>`：选择统一运行环境；旧 `--profile` 可兼容使用，二者不同会失败
- `-J, --java-opt=<arg>`：追加最高优先级 JVM 参数，可重复指定

**示例**：
```bash
bs-java-run start --yes                           # 启动全部，不自动构建
bs-java-run start saas-data-gateway --yes          # 启动指定服务，不自动构建
bs-java-run start --yes --build                    # 构建后启动全部
bs-java-run start --yes --startup-timeout 600      # 启动等待 600 秒
bs-java-run start saas-data-gateway --env dev --yes
bs-java-run start saas-data-gateway --env dev --java-opt=-Xmx1g --java-opt=-Ddebug=true
```

> `start` 现在默认只启动已有构建产物；只有明确加 `--build` 才会构建。旧的 `--skip-build` 仅作为隐藏兼容参数保留，不作为推荐用法。

### up 构建并启动服务

```bash
bs-java-run up [service] [options]
```

`up` 等价于先构建再启动，适合代码刚改完、需要一次性构建并启动的场景。启动指定服务时会自动补齐其传递依赖，并按拓扑正序等待就绪。

**示例**：
```bash
bs-java-run up --yes
bs-java-run up saas-data-gateway --yes
```

### stop 停止服务

```bash
bs-java-run stop [service] [options]
```

- `[service]`：服务名，省略时交互式选择
- `-y, --yes`：非交互模式，停止全部服务
- `-p, --skip-pid`：跳过 PID 文件检查，直接按端口清理
- `-c, --cascade`：显式级联停止正在运行的反向依赖服务
- `-f, --force`：允许清理 UUID 不匹配的 PID 或非本工具端口占用进程

**示例**：
```bash
bs-java-run stop --yes                    # 停止全部
bs-java-run stop saas-data-gateway --yes  # 停止指定服务
bs-java-run stop saas-zhsf-base --cascade --yes
```

### restart 重启服务

```bash
bs-java-run restart [service] [options]
```

重启会先计算目标服务及其传递依赖，按全逆序停止、全正序启动；需要重建时显式加 `--build`。`--force` 仅透传到停止阶段，`--cascade` 仅控制反向依赖范围。

**示例**：
```bash
bs-java-run restart --yes
bs-java-run restart saas-data-gateway --yes
bs-java-run restart saas-data-gateway --yes --build
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
- `-e, --env <name>` / `-a, --account <name>`：明确选择同一环境中的账号

**登录流程**：
1. 确保 `JAVARUN.local.md` 中有目标环境和账号配置
2. 运行 `bs-java-run login --env <env> --account <account> --headless`
3. 输出 JSON 格式，取 `token` 字段作为 `Authorization` 请求头值，**不加 Bearer 前缀**
4. 默认仅记住上次使用的账号名，不缓存 Token

**示例**：
```bash
bs-java-run login --env dev --account dev-admin --headless
bs-java-run login --env dev --account dev-admin --headless --quiet
bs-java-run login --env dev --account dev-admin --headless --save-token ~/.bs-token
```

### token 重新获取 Token

```bash
bs-java-run token [options]
```

- `-q, --quiet`：只输出 token 字符串

每次执行都会以无头浏览器重新登录获取 Token；`--quiet` 成功时 stdout 有且仅有 Token，失败诊断写入 stderr。

**示例**：
```bash
bs-java-run token --env dev --account dev-admin --quiet
# 输出：eyJhbGciOiJIUzI1NiIs...
```

## 端点验证

```bash
curl -H "Authorization: $(bs-java-run token --env <env> --account <account> --quiet)" -H "Function-Page-Id: <pageId>" "http://localhost:<port>/<context-path>/api/..."
```

上下文路径从服务配置或前端 Network 面板请求确认，不要假设。

## 向后兼容

以下旧脚本仍可用（内部自动调用 CLI）：
- `build_services.sh`
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

`JAVARUN.md` 维护共享配置规则与语法；`JAVARUN.local.md` 维护本机服务、端口、依赖关系、环境、账号和私有覆盖。新增或调整本机服务时更新 local 文件，不把密码、绝对路径或私有 Nacos 配置提交到仓库。

JVM 参数按六层合并：CLI `--java-opt` > `JAVA_OPTS` > 环境×服务覆盖 > 服务专属 > 环境通用 > 全局默认。`server.port`、`loader.path`、`file.encoding`、`bs.javarun.instance` 由工具保留，不要在配置或 `--java-opt` 中覆盖。

统一启动等待时间由 `BS_STARTUP_TIMEOUT` 或 `--startup-timeout` 控制，默认 420 秒。这个时间只是启动脚本等待端口就绪的上限；如果服务提前监听端口，脚本会提前结束，后续业务可以马上调用。

### 综合收费四项目

工作区：`/Users/zhangzhengqing/work/project/zhsf-all`。

| 项目 | JavaRun 服务名 | 端口 | 处理方式 |
|------|----------------|------|----------|
| `saas-zhsf-component` | — | — | 公共 Maven 组件，无 server 模块；在项目根目录执行 `mvn install -DskipTests`，不使用 `bs-java-run` 启动。 |
| `saas-zhsf-base` | `saas-zhsf-base` | `18080` | 基础信息服务。 |
| `saas-zhsf-voucher-adapter` | `saas-zhsf-voucher-adapter` | `18081` | 凭证适配服务。 |
| `saas-zhsf-business` | `saas-zhsf-business` | `18082` | 业务服务。 |

先按本机 `JAVARUN.local.md` 确认这些服务是否已配置依赖。`up` / `restart` 指定业务服务会自动补齐传递依赖，不再手工假设固定端口、固定 Ribbon 路由或固定启动顺序。

```bash
cd /Users/zhangzhengqing/work/project/zhsf-all/saas-zhsf-component
mvn install -DskipTests

bs-java-run up saas-zhsf-business --env <env> --yes
```

`bs-java-run` 以服务定义端口覆盖项目 `bootstrap.yml`，不要修改业务仓库端口。Nacos、Feign、网关和 JVM 路由以所选 `--env` 的最终配置为准；验证或排障使用：

```bash
bs-java-run status saas-zhsf-base
bs-java-run status saas-zhsf-voucher-adapter
bs-java-run status saas-zhsf-business
bs-java-run restart saas-zhsf-voucher-adapter --yes --build
bs-java-run stop saas-zhsf-business --yes
```

## 故障排查

| 现象 | 排查步骤 |
|------|----------|
| 端口冲突 | 先 `bs-java-run status <service>`；本工具进程用 `bs-java-run stop <service>`，基础服务受反向依赖保护时显式加 `--cascade`。非本工具进程默认不杀，只有用户明确授权时加 `--force`。 |
| 启动无输出 | 查看 `logs/<service>.log` 或 `nohup.out`，除非 `LOG_DIR` 环境变量覆盖了日志路径 |
| 启动后消失 | 先 `bs-java-run status` 查状态，再查启动日志找异常栈 |
| 启动结果和实际端口状态不一致 | 工具只扫描本次启动后的增量日志；保留当前日志现场，先查看日志和 `bs-java-run status`，不要为了重试自动删除日志 |
| 改了 Java 代码但启动仍是旧行为 | `start/restart` 默认不构建；先跑 `bs-java-run build <service> --yes`，或直接用 `bs-java-run up <service> --yes` |
| Maven 依赖解析失败/制品缺失 | 停止任务并汇报缺失依赖坐标、仓库地址、错误摘要和失败命令，交给人工排查；不要自行改依赖、替换 jar 或做临时修复 |
| 提示缺少网关 Groovy/脚本资源 | 先判断是否是依赖/制品缺失；如果是则停止任务交给人工，否则再考虑重新构建对应模块或全量构建 |
| 数据库/Nacos/Oracle 连接超时 | 检查全局代理、`NO_PROXY`/`no_proxy`、Nacos host/namespace，以及内网地址是否被代理劫持 |
| Token 过期 code -3 | 重新跑 `bs-java-run login --headless` 刷新 token |
| 服务间调用失败 | 确认 Nacos 注册成功，检查 namespace/host 匹配 |
| bs-java-run 命令未找到 | 确认 `npm install` 已执行，且工具目录在 PATH 中，或使用 `node bin/bs-java-run.js` 直接运行 |
