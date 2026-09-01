---
name: bs-jdbc-query
description: 通过 bs-jdbc-tool MCP 查询、核对、统计或变更本地 BS 开发数据库。只要用户需要查表、查数据、执行/排查 SQL，或提到 MySQL、Oracle、dev-mysql、dev-oracle、库表名、业务数据或数据库结果，即使没有明确说“数据库”，都必须使用本 Skill；优先调用 mcp__bs_jdbc_tool__*。未指定别名时，必须先由项目运行环境和 Nacos 数据源定位目标库，不得猜测。多条相关 SQL 必须使用 jdbc_batch。
---

# BS JDBC Query

## Overview

Use the configured `bs-jdbc-tool` MCP server for every database operation in scope. Never expose passwords, tokens, accounts, complete JDBC URLs, or other sensitive connection details. Do not use a local SQL client, manual JDBC script, or a configuration file to bypass `bs-jdbc-tool`.

## Database Location Prerequisite

Apply this procedure to every query, investigation, or SQL request whose database alias is not explicitly specified. A database name, repository name, historical result, or familiar alias is not evidence of the target database.

1. Identify the current workspace and its runtime environment before listing or selecting an alias. For an aggregate workspace, first read `.bs-java-run/JAVARUN.md` and `.bs-java-run/JAVARUN.local.md`; confirm the selected environment, Nacos host, and namespace. Use the `bs-project-run` workflow when JavaRun configuration or environment selection is involved. If the environment is missing, ambiguous, or the user has not selected one of several environments, stop and ask the user; never default to `dev` or `test`.
2. Use the selected project's supported runtime-environment mechanism to read the relevant Nacos configuration. Establish the service/project and, where applicable, tenant or industry environment. Inspect datasource or dynamic-datasource configuration and retain only the database/schema name or datasource name needed for matching. Do not reveal or persist sensitive connection values.
3. Call `mcp__bs_jdbc_tool__list_databases` and map a returned alias only when the Nacos evidence explicitly identifies a matching database, schema, or datasource. If the mapping is not unique, treat it as unresolved.
4. Call `mcp__bs_jdbc_tool__jdbc_test_connection` for the mapped alias. Then use read-only SQL to confirm the current database/schema (for example, `DATABASE()` on MySQL or the database-specific current-schema expression) and that the requested table exists. Check that its prefix, core tables, or metadata actually belong to the current project.
5. Perform the requested operation only after this chain is established: runtime environment -> Nacos datasource -> JDBC alias -> current schema -> project table ownership.

Stop and ask which database to use if any link cannot be verified: the environment is unknown; Nacos has no relevant datasource; datasource-to-alias mapping fails or is ambiguous; the target table is absent; or the table clearly belongs to a different project.

If the user explicitly supplies an alias, use that alias without Nacos location, but still test its connection and confirm the current schema and target-table existence before querying. Adding or changing an alias/connection is a configuration write: require explicit authorization, prefer an already verified definition for the same instance, and validate it afterward with `list_databases` and `jdbc_test_connection`.

## Workflow

1. Complete **Database Location Prerequisite** when the user has not explicitly supplied a database alias.
2. Before the first operation on a selected database in a task, call `mcp__bs_jdbc_tool__jdbc_test_connection` for that alias.
3. Use `mcp__bs_jdbc_tool__jdbc_query` for exactly one SQL statement. Always use `params` for externally supplied values where possible.
4. Use `mcp__bs_jdbc_tool__jdbc_batch` for two or more related SQL statements; use `onError: "abort"` when atomicity is required.
5. Before `INSERT` / `UPDATE` / `DELETE` / DDL, verify that the requested change, database alias, and filter scope are unambiguous. Do not treat examples or diagnostic queries as authorization to write.

## Result Handling

- State whether the environment mapping was verified by Nacos and database checks, supplied by the user but not yet verified by Nacos or database checks, or could not be confirmed and required user input. Report the selected alias and the query result or affected-row count concisely, without sensitive connection details.
- For a failed query, report the database error and correct the SQL from actual schema evidence; do not silently switch to another connection method.
- When a returned identifier may exceed JavaScript safe-integer precision, query it as text (for example, `CAST(rec_id AS CHAR)`) before reusing it in later statements.
