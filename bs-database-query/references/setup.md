# usql 安装与连接配置

上游项目：[xo/usql](https://github.com/xo/usql)。使用其 CLI 与现成数据库驱动，不维护自研执行器或兼容旧 MCP 的包装层。

## 安装与驱动

先检查 `command -v usql`、`usql --version`、`usql --help` 和 `usql -X -c '\drivers'`，避免覆盖已有安装。普通发行包与自行编译版本包含的驱动可能不同；“已安装 usql”不代表支持 ODBC。

当前本机使用上游 v0.21.4 源码构建，包含 `mysql oracle sqlserver sqlite3 odbc`，入口为 `~/.local/bin/usql`。版本文件放在 `~/.local/share/usql/0.21.4-odbc/`。保留此前 pipx 安装的原始二进制，便于回退；不要直接覆盖包管理器维护的目标文件。

IRIS 通过 ODBC 接入同一个 usql 命令。需安装匹配 CPU 架构的 ODBC Driver Manager 和 InterSystems IRIS 驱动。当前 macOS arm64 使用 [InterSystems 驱动分发](https://intersystems-community.github.io/iris-driver-distribution/) 中的 `ODBC-2026.2.0.221.0-macos.tar.gz`，驱动位于 `~/.local/share/intersystems/odbc-2026.2.0.221.0/`，使用 `libirisodbcuw35.so` Unicode 驱动和随包提供的 unixODBC。该目录是运行依赖，不能当作临时文件删除。

重建时读取上游对应版本 BUILD 文档和 Go 要求。该版本使用 `go build -tags 'no_base mysql oracle sqlserver sqlite3 odbc'`，ODBC 需要 CGO、C 编译器、unixODBC 头文件和动态库。本机 arm64 头文件还需 `CGO_CFLAGS` 中指定 `-DSIZEOF_LONG_INT=8` 及头文件目录，`CGO_LDFLAGS` 指向库目录；构建后将库引用改为实际安装路径并重新 ad-hoc 签名。完整本机命令记录在本次迁移交付报告中。不要改写上游执行逻辑或默默省略 ODBC。

## 原生配置与凭据

macOS 默认配置：`~/Library/Application Support/usql/config.yaml`。Linux 通常为 `$XDG_CONFIG_HOME/usql/config.yaml` 或 `~/.config/usql/config.yaml`；自定义路径使用当前 help 支持的 `--config`。先核对当前操作系统和版本，不把 macOS 路径套到所有环境。

本机使用 usql 原生 YAML 保存命名连接；IRIS ODBC 额外使用 `~/.odbc.ini` 保存不含凭据的 DSN，执行 Agent 命令时需设置 `ODBCINI="$HOME/.odbc.ini"`（程序调用时通过子进程环境传入），否则 macOS 上的 unixODBC 可能找不到用户 DSN。凭据仍在 usql 私有配置中，**不是系统 keyring**。目录权限 `0700`，文件及备份 `0600`，禁止提交仓库、输出完整文件、通过命令行传入带密码的 URL。别名仅用字母、数字和下划线；历史别名中的连字符迁为下划线，迁移报告记录映射。清单读取只输出别名与驱动名。

配置支持 URL 和 `[driver, native DSN]` 两种形式。以下只有占位符，不可直接执行：

```yaml
connections:
  example_mysql:
    - mysql
    - 'USER:PASSWORD@tcp(HOST:3306)/DATABASE?charset=utf8mb4&timeout=10000ms&tls=preferred'
  example_oracle: 'oracle://USER:URL_ENCODED_PASSWORD@HOST:1521/SERVICE?CONNECTION+TIMEOUT=10'
  example_sqlserver: 'sqlserver://USER:URL_ENCODED_PASSWORD@HOST:1433?database=DATABASE&encrypt=true&TrustServerCertificate=true&connection+timeout=10'
  example_iris:
    - odbc
    - 'DSN=example_iris;UID=USER;PWD=PASSWORD;'
```

IRIS 配套的 `~/.odbc.ini` 只保存目标信息，不重复保存凭据：

```ini
[example_iris]
Driver=/ABSOLUTE/PATH/libirisodbcuw35.so
Protocol=TCP
Host=HOST
Port=1972
Namespace=NAMESPACE
```

执行时使用 `ODBCINI="$HOME/.odbc.ini" usql ...`，无需自建执行器或修改全局 shell 环境。两个配置文件权限均为 `0600`；已有 ODBC DSN 按名称增量合并，不能覆盖其他连接。

实际值按各驱动规则编码，不把 URL 百分号转义套到原生 DSN。含分号、花括号或首尾空格的凭据需先确认厂商驱动支持的转义方式。参数名参照 [InterSystems ODBC 文档](https://docs.intersystems.com/irislatest/csp/docbook/DocBook.UI.Page.cls?KEY=BNETODBC_parms)。示例中的 TLS/证书设置不是所有环境的默认要求，应保留经过核对的来源策略。

迁移或新增连接：

1. 仅读取已授权来源，在内存中处理凭据；先展示别名、类型、增加或冲突的脱敏摘要。
2. 检查规范化别名是否冲突；保留未涉及配置，不覆盖同名不同目标。
3. JDBC 参数逐项映射，包括字符集、时区、SID/service、TLS、证书和超时；记录不能等价迁移的部分。
4. 先备份已有配置，采用临时文件和原子替换，文件及备份权限均为 `0600`；临时调试输出不得包含凭据。
5. 用只读 SQL 核对来源目标、元数据、中文、NULL、大整数、精确金额、空结果和错误退出码。迁移本身不授权真实业务 DML/DDL；写入与回滚行为可在临时本地 SQLite 库验证。

## 已核对的 0.21.4 差异

- **MySQL/TDSQL**：使用原生 `mysql` DSN 列表配置。该版本 URL 解析会强制附加 `sql_mode=ansi`、`parseTime=true`、`loc=Local`；原生 DSN 可避免改变服务端 SQL 模式。本机连接验证已确认 session/global SQL mode 一致。
- MySQL 使用 `charset=utf8mb4`、按原配置映射 `connectTimeout`/`socketTimeout` 为 `timeout`/`readTimeout`/`writeTimeout`；未指定连接超时时本次设 10 秒。`tls=preferred` 允许服务端不支持 TLS 时回退，不代表已验证强制加密；源配置要求更强策略时必须保留。
- MySQL 本次没有开启 `parseTime`，日期按驱动原始值处理；JDBC `serverTimezone` 和 `zeroDateTimeBehavior=convertToNull` 不等价迁移，涉及零日期、时区、时间类型时需专项核对，不宣称完全兼容。
- **Oracle**：当前使用 go-ora 驱动、service name 连接，连接超时 10 秒；它不是 JDBC 或 python-oracledb。SID、钱包和其他认证需求按实际驱动文档处理。
- **SQL Server**：使用 sqlserver 驱动，映射 database、encrypt、TrustServerCertificate 和 connection timeout；网络可达与认证成功须分别验证。
- **IRIS**：当前已验证的组合是 `libirisodbcuw35.so`、原生 DSN 和显式 `ODBCINI`，通过连接、namespace、元数据、中文、NULL、大整数与金额字符串、空结果及错误退出码检查；远端 DML/DDL 和事务未测试。此前无 DSN 的连接串出现 Access Denied，改为 DSN 后成功；`libirisodbcur6435.so` 的中文探针失真，换用 Unicode 驱动后通过。不能仅凭 Access Denied 判定密码错误。
- IRIS 使用 `SELECT $NAMESPACE` 核对 namespace；本次 `DATABASE()` 返回 NULL，不能用它替代 namespace 校验。ODBC 元命令支持有限，表结构优先查 `INFORMATION_SCHEMA`。
- 事务选项 `-1` 和 `ON_ERROR_STOP=1` 必须配合标准输入执行脚本，已在临时 SQLite 验证正常提交、失败回滚和中止后续语句；0.21.4 的 `-1 -f` 已复现未回滚问题，上游 `handler.Include` 只传递连接而未传递事务；禁止将该组合用于需要原子性的操作。不能据此替代远端数据库、分布式事务或 DDL 隐式提交规则的核对。

同步 Skill、停用旧 MCP、删除旧源码和卸载 sqlit 是不同操作。旧源码、配置和 sqlit 安装保留作回溯；不再作为当前数据库调用入口。
