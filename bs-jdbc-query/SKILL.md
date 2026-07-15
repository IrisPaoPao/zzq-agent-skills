---
name: bs-jdbc-query
description: 通过 bs-jdbc-tool MCP 查询、核对、统计或变更本地 BS 开发数据库。只要用户需要查表、查数据、执行/排查 SQL，或提到 MySQL、Oracle、dev-mysql、dev-oracle、库表名、业务数据或数据库结果，即使没有明确说“数据库”，都必须使用本 Skill；优先调用 mcp__bs_jdbc_tool__*，不得改用 usql、mysql、sqlplus、手工 JDBC 脚本或从配置中提取连接信息。多条相关 SQL 必须使用 jdbc_batch。
---

# BS JDBC Query

## Overview

Use the configured `bs-jdbc-tool` MCP server for every database operation in scope. Never expose passwords or JDBC connection details.

## Workflow

1. If the target database alias is unknown, call `mcp__bs_jdbc_tool__list_databases` first. Do not guess an alias.
2. Before the first operation on a selected database in a task, call `mcp__bs_jdbc_tool__jdbc_test_connection` for that alias.
3. Use `mcp__bs_jdbc_tool__jdbc_query` for exactly one SQL statement. Always use `params` for externally supplied values where possible.
4. Use `mcp__bs_jdbc_tool__jdbc_batch` for two or more related SQL statements; use `onError: "abort"` when atomicity is required.
5. Before `INSERT` / `UPDATE` / `DELETE` / DDL, verify that the requested change, database alias, and filter scope are unambiguous. Do not treat examples or diagnostic queries as authorization to write.

## Result Handling

- Report the selected alias and the query result or affected-row count concisely.
- For a failed query, report the database error and correct the SQL from actual schema evidence; do not silently switch to another connection method.
- When a returned identifier may exceed JavaScript safe-integer precision, query it as text (for example, `CAST(rec_id AS CHAR)`) before reusing it in later statements.
