---
name: bs-project-run
description: 使用 bs-java-run CLI 管理已托管的本地 BS Java 服务与聚合工作区，执行构建、启动、停止、重启、状态诊断、历史查询及反馈，并通过 login/token 获取开发 Token。适用于这些服务的运行、登录和 localhost 接口验证；通用 Token 解释、其他产品登录或非托管项目不触发。
---

# bs-project-run

使用本 Skill 前先确定目标是聚合工作区还是工具目录配置。所有运行、登录和状态操作都通过 bs-java-run CLI；不要直接拼接 Java 命令或猜端口、依赖、Nacos、账号和上下文路径。

## 工具和配置定位

工具目录固定为：

/Users/zhangzhengqing/work/project/tools_and_skills/bs-project-tools/bs-java-run

先确认目录存在，并读取工具目录的 JAVARUN.md；普通工具模式还要读取可选的 JAVARUN.local.md。若使用已生成的工作区，先检查目标根目录的 javarun、.bs-java-run/JAVARUN.md 和 .bs-java-run/JAVARUN.local.md。

运行环境、服务、端口、WAR 路径、依赖、账号和 Nacos 必须来自当前配置。配置缺失、服务未托管或环境不明确时停止，提示 workspace init/update 或补齐配置。不要输出密码、Cookie、Token、完整 JVM 参数或其他敏感配置。

安装和直接调用：

```bash
cd /Users/zhangzhengqing/work/project/tools_and_skills/bs-project-tools/bs-java-run
npm install
npm link
bs-java-run --version

node /Users/zhangzhengqing/work/project/tools_and_skills/bs-java-run/bin/bs-java-run.js --help
```

运行前置条件是有效 JDK、全局可用的 Maven、可连接当前环境的 Nacos 和登录接口。Java 根目录可来自 BS_JAVA_HOME 或当前模式的 JAVARUN.local.md。内网连接异常时先检查代理和 NO_PROXY。

## 两种配置模式

### 工作区模式

使用 --workspace <directory>、BS_JAVARUN_WORKSPACE 或工作区根目录的 javarun 时，配置目录严格为目标目录下的 .bs-java-run。工作区读取不到配置时直接失败，不回退工具目录配置。

```bash
bs-java-run workspace init /path/to/aggregate
cd /path/to/aggregate

./javarun doctor
./javarun update
./javarun update --configure
./javarun update --configure --replace-all
./javarun status
./javarun up <service> --env <env> --yes
./javarun smoke <service> --env <env> --build
```

workspace init 会扫描直接的 Maven server 项目，交互收集运行环境、Nacos、登录接口和可用用户；密码无回显。它生成 javarun、.bs-java-run/JAVARUN.md、私有配置模板、清单和忽略规则。doctor 只校验 Java、Maven、配置和构建产物，缺少 WAR 只告警，不构建、不启动、不修改文件。

workspace update 重新扫描服务并刷新托管配置。update --configure 先备份共享和私有配置，展示已脱敏差异后原子写入；默认按名称合并，未录入的环境和账户保留。只有 --replace-all 才删除未重新录入的环境或账户，并要求交互式二次确认。smoke 会真实启动服务，默认只回收本次启动实例；只有明确指定 --keep-running 才保留。

工作区默认把日志放在 .bs-java-run/logs，把 PID 放在工作区运行目录，把历史放在 .bs-java-run/history。生成的 javarun 记录了 CLI 路径；路径失效时用可用的 bs-java-run 重新执行 workspace init 或 workspace update。

### 普通工具模式

未指定工作区时才读取工具目录 JAVARUN.md 和 JAVARUN.local.md。普通模式的历史没有持久化工作区时只保存在当前进程内，后续 CLI 不能查询。不要把工作区模式误写成会回退工具目录。

## 命令工作流

### build

```bash
bs-java-run build [service] --yes
```

构建实际执行 Maven mvn -q -DskipTests clean package。build 成功只证明产物生成，不证明 Java 进程、端口、Spring readiness 或业务接口正常。

当错误属于 Maven 依赖解析、坐标/版本不存在、仓库不可达或缺少内部/第三方制品时，保留缺失坐标、仓库线索、失败命令和日志位置并停止。不要改 pom.xml、替换 jar、临时改版本或盲目重试。普通 Java 编译失败也只按构建失败报告，不把它包装成启动成功。

### start 和 up

```bash
bs-java-run start <service> --env <env> --yes
bs-java-run start <service> --env <env> --yes --build
bs-java-run up <service> --env <env> --yes
```

start、up、restart 必须由 --env、--profile 或 BS_ENV 选择运行环境。start 默认不构建，只启动已有 WAR；--build 才构建。up 总是先构建再启动，并按拓扑顺序补齐传递依赖、等待服务就绪。--nacos-host、--nacos-ns 和重复的 --java-opt 是显式运行时覆盖。

start/up 的 --reuse-dependencies 只复用自动补齐的依赖，不复用用户明确选择的目标服务。复用同时要求本工具 PID/实例 UUID 归属、PID 存活、端口归属、环境已知、ready 标记成立和启动 fingerprint 一致。fingerprint 包含服务 realpath、端口、运行环境、Nacos host/namespace 和 JVM 参数键值；摘要只显示非敏感路径、端口、环境、Nacos 标识和 JVM 参数键名。目标端口被占用仍然失败。

ready 必须有本次启动增量日志中的 Started ... in ... seconds、当前 PID 存活且拥有端口，并通过 5 秒稳定观察窗口。旧日志、孤立 PID、仅端口监听或一次 curl 成功都不能单独证明当前实例 ready。

### dry-run 和 JSON

dry-run 只解析配置、依赖和端口，不能构建、启动、停止或杀进程。命令形式：

```bash
bs-java-run start <service> --env <env> --dry-run --json
bs-java-run up <service> --env <env> --dry-run --json
bs-java-run restart <service> --env <env> --dry-run --json
bs-java-run stop <service> --dry-run --json
```

start/up 计划包含 command、dryRun、environment、build、reuseDependencies 和 services；每项服务包含 name、port、role、portOccupied、action、fingerprint、fingerprintSummary。action 可能是 start、reuse 或 blocked-port。restart 另外包含 stopOrder 和 startOrder；stop 包含 service、cascade、force、blockedBy、services 和 stopOrder。

实际 start/up/stop/restart 加 --json 时，stdout 只有一个结果对象 command、dryRun:false、code、outcome；内部人类日志被截留。

### stop 和 restart

```bash
bs-java-run stop <service> --yes
bs-java-run stop <service> --cascade --yes
bs-java-run stop <service> --force --yes
bs-java-run restart <service> --env <env> --yes
bs-java-run restart <service> --env <env> --yes --build --cascade
```

stop 默认只处理可以证明属于本工具的实例；PID 文件、实例 UUID 或端口归属不匹配时拒绝清理。--force 才允许处理非本工具 PID 或残留端口，使用前先检查 status 和端口 PID。--cascade 才把正在运行的反向依赖加入范围。

restart 先冻结目标范围，再全逆序停止、全正序启动。--build 只影响启动前构建，--force 只透传停止阶段，--cascade 控制反向依赖范围。重启计划和服务状态不能代替业务验证。

### status

```bash
bs-java-run status
bs-java-run status <service>
bs-java-run status --json
```

status --json 返回 command、environment 以及每个服务的 service、port、pid、pidState、portState、portPids、log、running、readiness、environment、pidEnvironment、expectedEnvironment、environmentStatus、fingerprint、fingerprintMatch。running、PID 和端口状态是进程证据；readiness 还要求 ready 标记。environmentStatus 用于识别 known、mismatch、unknown 和 stopped；fingerprintMatch 用于发现配置漂移。status 不是 HTTP 或业务健康检查。

### login 和 token

```bash
bs-java-run login --env <env> --account <account> --headless
bs-java-run token --env <env> --account <account> --quiet
```

login/token 使用当前配置模式的账号。token 每次重新登录，不缓存 Token；--quiet 成功时 stdout 只有 Token，失败诊断走 stderr。向接口发送 Authorization 时按目标接口要求使用返回值，不要未经确认擅自添加 Bearer。默认只保留最近账户名，不输出密码、Cookie 或 Token；需要文件时才显式使用 login --save-token <file>。

localhost 接口验证前，从配置或真实 Network 请求确认上下文路径、页面标识和业务参数。将构建成功、进程/端口 ready、curl 结果和业务结果分开报告，不能把构建或 status 结果称为 E2E。

## 历史和反馈

有工作区时，下列 runtime 命令创建并持久化 run：build、start、up、stop、restart、login、token、workspace init、workspace update、workspace smoke。status、doctor、history、feedback 只读或追加记录，不创建新 run。

查询：

```bash
bs-java-run history
bs-java-run history --limit 50 --service <service>
bs-java-run history --failed --json --workspace <directory>
bs-java-run history --run-id <uuid>
```

history 参数是 -n/--limit（默认 20）、--service、--failed、--run-id/--runId、--json 和 --workspace。普通模式逐行摘要；过滤错误和告警写 stderr。--json 的 stdout 是 store.list 完整对象 records、truncated、queryError、storageWarning。

feedback 的 runId 可用位置参数或 --run-id/--runId 指定，故障描述必须从 stdin 读取固定 JSON：

```bash
printf '%s\n' '{"phenomenon":"服务启动后退出","steps":["查看 status","检查本次启动日志"],"verification":"确认端口和日志","confidence":"confirmed"}' \
  | bs-java-run feedback --run-id <uuid> --json --workspace <directory>
```

输入只允许 phenomenon、steps、verification、confidence 四个字段；phenomenon/verification 每项最多 1000 字符，steps 为 1 到 20 项且每项最多 1000 字符，confidence 只能是 confirmed 或 suspected，整个输入不超过 64 KiB。凭据样式文本会脱敏。成功 JSON 含 runId、saved、storageWarning；普通模式成功输出一行，错误写 stderr。

历史记录默认保留 30 天、总量不超过 20 MiB、单记录不超过 256 KiB，目录 0700、文件 0600。记录不保存原始命令行、密码、Token、Cookie、实例 UUID 或完整 JVM 参数。历史查询先定位 runId 和失败阶段，再检查对应日志和 status JSON，最后用 feedback 记录可复现现象、步骤和验证；历史只是线索，不能替代当前现场。

## 配置规则

JVM 参数按四层合并：环境参数组 < 环境服务专属参数 < JAVA_OPTS < CLI --java-opt。每个参数组必须有明确环境名，不支持全局或 common 组。工具保留 server.port、loader.path、file.encoding、bs.javarun.instance 等关键参数，不要从配置或 --java-opt 覆盖。

启动等待默认 420 秒，可由 BS_STARTUP_TIMEOUT 或 --startup-timeout 覆盖；它只是等待上限，不是业务健康检查。LOG_DIR 可覆盖日志目录。环境选择使用配置中的 Nacos host/namespace 和登录连接，不按服务名猜测。

## 故障诊断顺序

1. 确认配置模式和来源。工作区检查根目录 javarun、.bs-java-run/JAVARUN.md、.bs-java-run/JAVARUN.local.md；普通模式检查工具目录的两个 JAVARUN 文件。
2. 执行 status --json，核对 PID 存活、端口 PID、environmentStatus、fingerprintMatch 和日志路径。未知进程不要先杀。
3. 执行 history --failed --service <service> --json，必要时按 runId 查看阶段和 errorCategory，再检查该 run 的本次日志。
4. 启动失败时检查增量日志中的 Started 行、Spring 上下文异常、Bean 定义冲突和缺失 Bean。常见冲突会归类 bean-conflict，缺失 Bean/依赖会归类 bean-missing；分类仅用于定位，必须结合完整日志。
5. Maven 依赖解析失败时保留坐标、仓库、命令和日志，停止自动修复。
6. 端口冲突时先检查 status 和端口 PID；start 不会杀进程，stop 默认不处理非本工具进程，确认后才使用 --force。

所有结论都要区分构建、启动进程、端口/ready、HTTP 请求和业务结果。
