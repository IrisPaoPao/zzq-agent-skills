# 场景模板速查

每个场景给出 TDSQL 与 Oracle 的标准片段。直接复制改实际表名 / 字段名 / 注释即可，但要先确认硬约束清单（见 SKILL.md）。

## 1. 建表

### TDSQL
```groovy
if (missTable("table_name")) {
    executeMultiCommand("""
        CREATE TABLE table_name (
            rec_id bigint(20) NOT NULL COMMENT '主键',
            tenant_code bigint(20) NOT NULL COMMENT '租户编码',
            ...
            rec_version int(11) DEFAULT 0 COMMENT '版本号',
            PRIMARY KEY (rec_id) USING BTREE,
            UNIQUE INDEX uk_xxx_yyy(col1, col2) USING BTREE,
            INDEX idx_xxx_zzz(col3, col4) USING BTREE
        ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '业务说明';
    """)
} else {
    println("table table_name already exist ...");
}
```

### Oracle
```groovy
if (missTable("table_name")) {
    executeMultiCommand("""
        CREATE TABLE table_name (
            rec_id NUMBER(20) NOT NULL,
            tenant_code NUMBER(20) NOT NULL,
            ...
            rec_version NUMBER(11) DEFAULT 0,
            PRIMARY KEY (rec_id)
        ) TABLESPACE <DATA_TBS>;
        COMMENT ON TABLE table_name IS '业务说明';
        COMMENT ON COLUMN table_name.rec_id IS '主键';
        COMMENT ON COLUMN table_name.tenant_code IS '租户编码';
        ...

        CREATE UNIQUE INDEX uk_xxx_yyy ON table_name (col1 ASC, col2 ASC) TABLESPACE <INDEX_TBS>;
        CREATE INDEX idx_xxx_zzz ON table_name (col3 ASC, col4 ASC) TABLESPACE <INDEX_TBS>;
    """)
} else {
    println("table table_name already exist ...");
}
```

表空间名（`<DATA_TBS>` / `<INDEX_TBS>`）从该产品最近的 Oracle 脚本里抓——基础字典与业务大表通常用不同表空间，沿用相邻同类型表的写法即可。

## 2. 加字段（多字段合并到一个文件）

每个字段各自独立 if，避免某条断连后剩下的列再也加不上。

### TDSQL
```groovy
if (missColumn("table_name", "col_a")) {
    executeMultiCommand("""
        ALTER TABLE table_name ADD COLUMN col_a TINYINT NOT NULL DEFAULT 0 COMMENT '说明 a';
    """)
} else {
    println("column col_a already exist in table_name ...");
}

if (missColumn("table_name", "col_b")) {
    executeMultiCommand("""
        ALTER TABLE table_name ADD COLUMN col_b BIGINT DEFAULT NULL COMMENT '说明 b';
    """)
} else {
    println("column col_b already exist in table_name ...");
}
```

### Oracle
```groovy
if (missColumn("table_name", "col_a")) {
    executeMultiCommand("""
        ALTER TABLE table_name ADD (col_a NUMBER(4) DEFAULT 0 NOT NULL);
        COMMENT ON COLUMN table_name.col_a IS '说明 a';
    """)
} else {
    println("column col_a already exist in table_name ...");
}

if (missColumn("table_name", "col_b")) {
    executeMultiCommand("""
        ALTER TABLE table_name ADD (col_b NUMBER(20) DEFAULT NULL);
        COMMENT ON COLUMN table_name.col_b IS '说明 b';
    """)
} else {
    println("column col_b already exist in table_name ...");
}
```

## 3. 加索引

### TDSQL
```groovy
if (missIndex("table_name", "idx_xxx")) {
    executeMultiCommand("""
        ALTER TABLE table_name ADD INDEX idx_xxx (col1, col2) USING BTREE;
    """)
} else {
    println("index idx_xxx already exist in table_name ...");
}
```

### Oracle
```groovy
if (missIndex("table_name", "idx_xxx")) {
    executeMultiCommand("""
        CREATE INDEX idx_xxx ON table_name (col1 ASC, col2 ASC) TABLESPACE <INDEX_TBS>;
    """)
} else {
    println("index idx_xxx already exist in table_name ...");
}
```

加唯一索引前必须先确认数据已经唯一，否则在生产环境会执行失败——这点没法靠脚本兜底，需要在改表设计时就保证。

## 4. 删索引 / 删唯一约束

### TDSQL（索引和唯一约束都用 `DROP INDEX`）
```groovy
if (!missIndex("table_name", "idx_xxx")) {
    executeMultiCommand("""
        ALTER TABLE table_name DROP INDEX idx_xxx;
    """)
} else {
    println("index idx_xxx already removed from table_name ...");
}
```

### Oracle（普通索引用 `DROP INDEX`，唯一约束用 `DROP CONSTRAINT`）
```groovy
if (!missIndex("table_name", "idx_xxx")) {
    executeMultiCommand("""
        DROP INDEX idx_xxx;
    """)
} else {
    println("index idx_xxx already removed ...");
}

// 唯一约束（约束名通常是 UK_ 开头）
if (!missIndex("table_name", "uk_xxx")) {
    executeMultiCommand("""
        ALTER TABLE table_name DROP CONSTRAINT uk_xxx;
    """)
} else {
    println("constraint uk_xxx already removed from table_name ...");
}
```

## 5. 改字段类型 / 默认值

Oracle 不能在一条 ALTER 里同时改类型和默认值，必须拆两条。

### TDSQL
```groovy
// MySQL 风格 MODIFY COLUMN
executeMultiCommand("""
    ALTER TABLE table_name MODIFY COLUMN col_a VARCHAR(100) DEFAULT '100' COMMENT '说明';
""")
```

### Oracle（拆两条）
```groovy
executeMultiCommand("""
    ALTER TABLE table_name MODIFY (col_a VARCHAR2(100 CHAR));
""")
executeMultiCommand("""
    ALTER TABLE table_name MODIFY (col_a DEFAULT '100');
""")
```

## 6. 改字段 NOT NULL / NULL

用 `nullable()` 防止 Oracle 报「已经是 NULL，无法再改成 NULL」。

```groovy
if (!nullable("table_name", "col_a")) {
    executeMultiCommand("""
        ALTER TABLE table_name MODIFY col_a NULL;
    """)
} else {
    println("column col_a on table_name is already nullable ...");
}
```

## 7. 插入数据

### TDSQL / Oracle 通用
```groovy
if (notExist("select * from sys_config where fkey = 'xxx'")) {
    executeMultiCommand("""
        INSERT INTO sys_config (fid, fkey, fvalue, fmemo)
        VALUES ('100001', 'xxx', '1', '说明');
    """)
} else {
    println("sys_config row with fkey=xxx already exists ...");
}
```

带参数版本（避免 SQL 注入式问题）：

```groovy
if (notExist("select * from sys_config where fkey = ?", ["xxx"])) {
    execute("""INSERT INTO sys_config (fid, fkey, fvalue) VALUES (?, ?, ?)""",
            ["100001", "xxx", "1"])
} else {
    println("sys_config row with fkey=xxx already exists ...");
}
```

## 8. 更新数据

```groovy
if (!notExist("select * from sys_config where fkey = 'xxx' and fvalue = '0'")) {
    executeMultiCommand("""
        UPDATE sys_config SET fvalue = '1' WHERE fkey = 'xxx' AND fvalue = '0';
    """)
} else {
    println("sys_config row already in target state, skip update ...");
}
```

## 9. 权限模板版本号 +0.01

提交权限模板变更时容易遗漏的步骤——版本号不变，行业端不会同步过去。

```groovy
// 应用模板版本号
executeMultiCommand("""
    UPDATE auth_temp_application
       SET template_version = template_version + 0.01
     WHERE rec_id = 613015803075231745;
""")

// 功能模板版本号
executeMultiCommand("""
    UPDATE auth_temp_function_version SET template_version = template_version + 0.01;
""")
```

## 10. 分表（按月）

按月分表的建表脚本仅 TDSQL 一侧需要写 PARTITION。Oracle 一侧通常按普通表建。

```groovy
if (missTable("xxx_data")) {
    executeMultiCommand("""
        CREATE TABLE xxx_data (
            ...
            PRIMARY KEY (rec_id, tenant_code),
            INDEX idx_xxx (tenant_code, bus_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='源数据'
        shardkey=tenant_code PARTITION BY RANGE ( month(bus_date) )
        (
            PARTITION p202601 VALUES LESS THAN (202602),
            ...
            PARTITION p202612 VALUES LESS THAN (202701)
        );
    """)
} else {
    println("table xxx_data already exist ...");
}
```

分表表的字段 / 索引名不得包含全表名（忽略大小写）；自定义命名要给后续的工具留下 `_${monthSuffix}` / `_${yearSuffix}` 替换空间。
