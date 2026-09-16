"""Core engine for saas-database script organizing, validation, archiving, and rollback."""

from __future__ import annotations

import base64
import contextlib
import datetime as dt
import difflib
import json
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RECEIPT_FILENAME = ".organize_receipt.json"

FILE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<author>.+?)_(?P<order>\d{2,3})_{1,2}"
    r"(?P<stem>.+)_(?P<source>ORACLE|TDSQL)_\[(?P<version>[^\]]+)\]\."
    r"(?P<ext>sql|groovy)$",
    re.IGNORECASE,
)
JAR_FILE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}_.+_\d{2,3}__.+_(?:ORACLE|TDSQL)_\[[^\]]+\]\.(?:sql|groovy)$",
    re.IGNORECASE,
)
OUTPUT_RE = re.compile(r"^V[^_]+_\d+_00_(?P<number>\d+)__")
ASSIGNMENT_RE = re.compile(r"(?m)^\s*(?P<key>[A-Za-z][A-Za-z0-9_]*)\s*=\s*\"(?P<value>[^\"]*)\"")

JAVA_BRIDGE_SOURCE = """\
import com.bosssoft.nontax3.saas.sql.translate.factory.SqlTransformFactory;
import com.bosssoft.nontax3.saas.sql.translate.domain.response.Response;
import com.bosssoft.nontax3.saas.sql.translate.domain.response.SQLResponse;
import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

public class SqlTransformCli {
    private static final Map<String, String> fileCache = new HashMap<>();

    private static String readFile(String path) throws Exception {
        if (!fileCache.containsKey(path)) {
            byte[] bytes = Files.readAllBytes(Paths.get(path));
            fileCache.put(path, new String(bytes, StandardCharsets.UTF_8));
        }
        return fileCache.get(path);
    }

    private static void processSingle(String id, String filePath, String shardingFilePath, String checkRuleFilePath, String source, String target, SqlTransformFactory factory) {
        System.out.println("--- BEGIN ITEM " + id + " ---");
        try {
            String fileContent = readFile(filePath);
            String shardingContent = readFile(shardingFilePath);
            String checkRuleContent = readFile(checkRuleFilePath);

            Response<Object> response = factory.transFrom(fileContent, shardingContent, checkRuleContent, source, target);
            if (response == null) {
                System.out.println("CODE=500");
                System.out.println("MSG=null response from factory");
            } else {
                System.out.println("CODE=" + response.getCode());
                if ("200".equals(response.getCode()) && response.getData() != null) {
                    if (response.getData() instanceof SQLResponse) {
                        SQLResponse sqlResp = (SQLResponse) response.getData();
                        String targetSql = sqlResp.getTargetSql();
                        String shardingYml = sqlResp.getShardingYml();
                        Boolean subAndNotCreate = sqlResp.getSubAndNotCreate();

                        if (targetSql != null) {
                            String b64Sql = Base64.getEncoder().encodeToString(targetSql.getBytes(StandardCharsets.UTF_8));
                            System.out.println("TARGET_B64=" + b64Sql);
                        }
                        if (shardingYml != null) {
                            String b64Yml = Base64.getEncoder().encodeToString(shardingYml.getBytes(StandardCharsets.UTF_8));
                            System.out.println("SHARDING_B64=" + b64Yml);
                        }
                        System.out.println("SUB_AND_NOT_CREATE=" + (subAndNotCreate != null && subAndNotCreate));
                    }
                } else {
                    System.out.println("MSG=" + response.getData());
                }
            }
        } catch (Throwable t) {
            t.printStackTrace(System.err);
            System.out.println("CODE=500");
            System.out.println("MSG=" + t.getMessage());
        }
        System.out.println("--- END ITEM " + id + " ---");
    }

    public static void main(String[] args) {
        if (args.length == 0) {
            System.err.println("Usage: SqlTransformCli --batch <batchFile> OR <filePath> <shardingFilePath> <checkRuleFilePath> <source> <target>");
            System.exit(1);
        }
        try {
            SqlTransformFactory factory = new SqlTransformFactory();
            if ("--batch".equals(args[0]) && args.length >= 2) {
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(new FileInputStream(args[1]), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        line = line.trim();
                        if (line.isEmpty() || line.startsWith("#")) continue;
                        String[] parts = line.split("\\\\t");
                        if (parts.length >= 6) {
                            processSingle(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], factory);
                        }
                    }
                }
            } else if (args.length >= 5) {
                processSingle("0", args[0], args[1], args[2], args[3], args[4], factory);
            } else {
                System.err.println("Invalid arguments");
                System.exit(1);
            }
        } catch (Throwable t) {
            t.printStackTrace(System.err);
            System.exit(1);
        }
    }
}
"""


class OrganizeError(RuntimeError):
    pass


@dataclass(frozen=True)
class Script:
    path: Path
    platform: str
    business: str
    date: str
    author: str
    order_text: str
    order: int
    stem: str
    source: str
    version: str
    ext: str
    child: str | None = None

    @property
    def group_key(self) -> tuple[str, str, int, str, str, str]:
        return (self.date, self.author, self.order, self.stem, self.version, self.ext)


@dataclass(frozen=True)
class Group:
    scripts: tuple[Script, ...]
    platform: str
    business: str
    version: str
    child: str | None


def resolve_database_root(explicit_path: Path | None) -> Path:
    if explicit_path:
        root = explicit_path.expanduser().resolve()
        if not root.is_dir():
            raise OrganizeError(f"specified database root not found: {root}")
        return root

    env_path = os.environ.get("SAAS_DATABASE_ROOT")
    if env_path:
        root = Path(env_path).expanduser().resolve()
        if root.is_dir():
            return root

    # Check current directory and parents
    cwd = Path.cwd().resolve()
    for directory in (cwd, *cwd.parents):
        if (directory / "行业应用").is_dir() and (directory / "运营支撑门户").is_dir():
            return directory

    # Known common default path
    default_known = Path("/Users/zhangzhengqing/work/project/V4/saas-database").resolve()
    if default_known.is_dir() and (default_known / "行业应用").is_dir():
        return default_known

    raise OrganizeError(
        "cannot auto-detect saas-database root. Please specify with --database-root <path> "
        "or set SAAS_DATABASE_ROOT environment variable."
    )


def read_assignments(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise OrganizeError(f"cannot read config: {path}: {error}") from error
    return {match.group("key"): match.group("value") for match in ASSIGNMENT_RE.finditer(text)}


def split_list(value: str | None) -> list[str]:
    return [item.strip().lower() for item in (value or "").split(",") if item.strip()]


def parse_script(path: Path, platform: str, business: str, child: str | None) -> Script:
    match = FILE_RE.match(path.name)
    if not match:
        raise OrganizeError(
            f"invalid script filename: {path}\n"
            "Expected format: YYYY-MM-DD_author_order__stem_source_[version].(sql|groovy)"
        )
    values = match.groupdict()
    return Script(
        path=path,
        platform=platform,
        business=business,
        date=values["date"],
        author=values["author"],
        order_text=values["order"],
        order=int(values["order"]),
        stem=values["stem"],
        source=values["source"].upper(),
        version=values["version"],
        ext=values["ext"].lower(),
        child=child,
    )


def project_child(relative: Path, explicit: str | None) -> str | None:
    if explicit:
        return explicit.replace("\\", "/").strip("/") or None
    if len(relative.parts) > 1 and not re.fullmatch(r"\d{8}", relative.parts[0]):
        return relative.parts[0]
    return None


def inferred_project_child(relative: Path) -> str | None:
    if len(relative.parts) > 1 and not re.fullmatch(r"\d{8}", relative.parts[0]):
        return relative.parts[0]
    return None


def discover(
    root: Path,
    platform_filter: str,
    business_filter: str | None,
    version_filter: str | None,
    child_filter: str | None,
) -> list[Script]:
    platforms = (("industry", "行业应用"), ("operate", "运营支撑门户"))
    scripts: list[Script] = []
    for platform, directory in platforms:
        if platform_filter not in ("all", platform):
            continue
        temp_root = root / directory / "temp"
        if not temp_root.is_dir():
            continue
        for business_dir in sorted(item for item in temp_root.iterdir() if item.is_dir()):
            if business_filter and business_dir.name != business_filter:
                continue
            for path in sorted(item for item in business_dir.rglob("*") if item.is_file()):
                if path.suffix.lower() not in {".sql", ".groovy"}:
                    continue
                relative = path.relative_to(business_dir)
                actual_child = inferred_project_child(relative) if business_dir.name == "07_projectized" else None
                normalized_filter = child_filter.replace("\\", "/").strip("/") if child_filter else None
                if normalized_filter and business_dir.name == "07_projectized" and actual_child and actual_child != normalized_filter:
                    continue
                child = project_child(relative, normalized_filter) if business_dir.name == "07_projectized" else None
                script = parse_script(path, platform, business_dir.name, child)
                if version_filter and script.version != version_filter:
                    continue
                scripts.append(script)
    return scripts


def groups(scripts: list[Script]) -> list[Group]:
    grouped: dict[tuple[str, str, str, str | None, tuple[str, str, int, str, str, str]], list[Script]] = {}
    for script in scripts:
        key = (script.platform, script.business, script.version, script.child, script.group_key)
        grouped.setdefault(key, []).append(script)
    result = [
        Group(tuple(sorted(items, key=lambda item: (item.source, item.path.name))), key[0], key[1], key[2], key[3])
        for key, items in grouped.items()
    ]
    return sorted(result, key=lambda item: item.scripts[0].group_key)


def require_command(command: str) -> None:
    if shutil.which(command) is None:
        raise OrganizeError(f"required command not found on PATH: {command}")


def java_classpath(platform_root: Path) -> tuple[Path, str]:
    require_command("java")
    java_root = platform_root / "tool" / "java"
    if not java_root.is_dir():
        raise OrganizeError(f"Java dependency directory not found: {java_root}")
    jars = sorted(java_root.glob("sql-translate*.jar"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not jars:
        raise OrganizeError(f"translation JAR not found under {java_root}")
    dependencies = os.pathsep.join([str(jars[0]), str(java_root / "*")])
    return jars[0], dependencies


@contextlib.contextmanager
def jar_script_path(script: Script):
    """Give the JAR its canonical filename while preserving the source path."""
    if JAR_FILE_RE.fullmatch(script.path.name):
        yield script.path
        return
    with tempfile.TemporaryDirectory(prefix="saas-database-script-") as directory:
        normalized = Path(directory) / (
            f"{script.date}_{script.author}_{script.order_text}__{script.stem}_"
            f"{script.source}_[{script.version}].{script.ext}"
        )
        shutil.copyfile(script.path, normalized)
        yield normalized


def bridge_command(platform_root: Path) -> list[str]:
    """Ensure SqlTransformCli is compiled and return its invocation command."""
    require_command("javac")
    _, dependencies = java_classpath(platform_root)

    cache_dir = Path(tempfile.gettempdir()) / "zzq_saas_database_sql_transform_cli"
    cache_dir.mkdir(parents=True, exist_ok=True)
    source_file = cache_dir / "SqlTransformCli.java"
    class_file = cache_dir / "SqlTransformCli.class"

    source_file.write_text(JAVA_BRIDGE_SOURCE, encoding="utf-8")

    if not class_file.exists() or class_file.stat().st_mtime < source_file.stat().st_mtime:
        result = subprocess.run(
            ["javac", "-encoding", "UTF-8", "-cp", dependencies, "-d", str(cache_dir), str(source_file)],
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise OrganizeError(f"failed to compile Java bridge:\n{result.stdout}{result.stderr}")

    return ["java", "-Dfile.encoding=UTF-8", "-cp", os.pathsep.join((str(cache_dir), dependencies)), "SqlTransformCli"]


def validate(script: Script, platform_root: Path, database_root: Path) -> None:
    jar, _ = java_classpath(platform_root)
    check_rule = platform_root / "tool" / "config" / "check-rule.yml"
    sharding = database_root / "行业应用" / "saas-sharding.yml.vm"
    for required in (check_rule, sharding):
        if not required.is_file():
            raise OrganizeError(f"required configuration file not found: {required}")
    with jar_script_path(script) as input_path:
        command = [
            "java",
            "-Dfile.encoding=UTF-8",
            "-cp",
            f"{jar}{os.pathsep}{platform_root / 'tool' / 'java'}{os.sep}*",
            "com.bosssoft.nontax3.saas.sql.translate.server.SqlCheckRunner",
            str(input_path),
            str(sharding),
            str(check_rule),
            script.source,
        ]
        result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode or "Exception" in (result.stdout + result.stderr):
        details = (result.stdout + result.stderr).strip()
        raise OrganizeError(f"validation failed for {script.path}:\n{details}")


def execute_batch_transform(
    tasks: list[dict[str, Any]],
    platform_root: Path,
) -> dict[str, tuple[str, str | None, bool]]:
    """Execute multiple dialect transformations in a single JVM invocation."""
    if not tasks:
        return {}

    bridge = bridge_command(platform_root)
    lines = []
    for t in tasks:
        line = f"{t['id']}\t{t['file_path']}\t{t['sharding']}\t{t['check_rule']}\t{t['source']}\t{t['target']}"
        lines.append(line)

    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix="saas_batch_in_", delete=False) as f:
        batch_in_path = f.name
        f.write("\n".join(lines) + "\n")

    try:
        cmd = bridge + ["--batch", batch_in_path]
        result = subprocess.run(cmd, text=True, capture_output=True)
    finally:
        Path(batch_in_path).unlink(missing_ok=True)

    if result.returncode:
        raise OrganizeError(f"batch translation failed:\n{result.stderr.strip()}")

    # Parse results
    results: dict[str, tuple[str, str | None, bool]] = {}
    current_id: str | None = None
    item_lines: list[str] = []

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("--- BEGIN ITEM "):
            current_id = line.replace("--- BEGIN ITEM ", "").replace(" ---", "").strip()
            item_lines = []
        elif line.startswith("--- END ITEM "):
            if current_id is not None:
                values: dict[str, str] = {}
                for iline in item_lines:
                    if "=" in iline:
                        k, v = iline.split("=", 1)
                        values[k] = v
                code = values.get("CODE")
                if code != "200":
                    msg = values.get("MSG", "Unknown translation error")
                    raise OrganizeError(f"translation failed for task {current_id}: {msg}")
                try:
                    target_sql = base64.b64decode(values.get("TARGET_B64", "")).decode("utf-8")
                    sharding_yaml = base64.b64decode(values.get("SHARDING_B64", "")).decode("utf-8") if values.get("SHARDING_B64") else None
                except Exception as err:
                    raise OrganizeError(f"failed to decode translation result for task {current_id}: {err}") from err
                sub_and_not_create = values.get("SUB_AND_NOT_CREATE", "false").lower() == "true"
                results[current_id] = (target_sql, sharding_yaml, sub_and_not_create)
                current_id = None
        elif current_id is not None:
            item_lines.append(line)

    # Check if all tasks were completed
    for t in tasks:
        if t["id"] not in results:
            raise OrganizeError(f"missing translation result for task {t['id']}")

    return results


def next_sequence_for_target(
    root: Path, platform: str, business: str, version: str, child: str | None, target: str,
) -> int:
    directory = migration_general(root, platform, business, version, child) / target
    highest = 0
    if directory.is_dir():
        for path in directory.iterdir():
            if not path.is_file():
                continue
            match = OUTPUT_RE.match(path.name)
            if match:
                highest = max(highest, int(match.group("number")))
    return highest + 1


def migration_general(root: Path, platform: str, business: str, version: str, child: str | None) -> Path:
    directory = "行业应用" if platform == "industry" else "运营支撑门户"
    path = root / directory / "nontax-flyway-db" / "nontax-flyway-db-1.0.3" / "config" / "nontax" / "db" / "migration" / business / version
    return path / child / "general" if child else path / "990000_product" / "general"


def business_directory(root: Path, business: str, child: str | None) -> Path:
    path = root / "行业应用" / "business" / business
    return path / child if child else path


def product_code(script: Script) -> str:
    return script.child.split("_", 1)[0] if script.child and "_" in script.child else "990000"


def output_name(script: Script, sequence: int) -> str:
    return f"V{script.version}_{product_code(script)}_00_{sequence:02d}__{script.stem}_{script.source}_[{script.version}].{script.ext}"


def schema_table(schema: Path, business: str) -> str:
    if schema.is_file():
        match = re.search(r"(?im)^\s*INSERT\s+INTO\s+([A-Z0-9_]+_SCHEMA_VERSION)\b", schema.read_text(encoding="utf-8-sig"))
        if match:
            return match.group(1)
    if business == "01_standard":
        return "NONTAX_SCHEMA_VERSION"
    table = business.split("_", 1)[1].upper() if "_" in business else business.upper()
    return re.sub(r"[^A-Z0-9]+", "_", table).strip("_") + "_SCHEMA_VERSION"


def schema_line(table: str, script: Script, sequence: int) -> str:
    description = f"{script.stem.replace('_', ' ')} {script.source} [{script.version}]"
    filename = output_name(script, sequence)
    return (
        f"INSERT INTO {table} (installed_rank, version, description, type, script, checksum, "
        f"installed_by, installed_on, execution_time, success) SELECT max(installed_rank)+1, "
        f"'{script.version}.{product_code(script)}.00.{sequence:02d}', '{description}', 'CUSTOM', '{filename}', 0, "
        f"CURRENT_USER(), CURRENT_TIMESTAMP(), 0, 1 from {table};\n"
    )


def plan(
    database_root: Path,
    all_groups: list[Group],
    date: str,
) -> tuple[dict[Path, bytes], list[tuple[Path, Path]], list[dict[str, Any]], str | None, str | None]:
    writes: dict[Path, bytes] = {}
    moves: list[tuple[Path, Path]] = []
    schema_lines: dict[Path, list[str]] = {}
    schema_appends: list[dict[str, Any]] = []
    sequences: dict[tuple[str, str, str, str | None, str], int] = {}
    sharding_path = database_root / "行业应用" / "saas-sharding.yml.vm"
    original_sharding = sharding_path.read_text(encoding="utf-8") if sharding_path.is_file() else None
    updated_sharding: str | None = None

    # Step 1: Gather all required translation tasks across groups and run them in batch!
    # Tasks grouped by platform
    platform_tasks: dict[str, list[dict[str, Any]]] = {}
    temp_dir = Path(tempfile.mkdtemp(prefix="saas_organize_canonical_"))

    try:
        for group in all_groups:
            platform_root = database_root / ("行业应用" if group.platform == "industry" else "运营支撑门户")
            config = read_assignments(platform_root / "tool" / "config" / "sys-config.table")
            targets = {
                "TDSQL": split_list(config.get("tdsqlDatabaseDirList")),
                "ORACLE": split_list(config.get("oracleDatabaseDirList")),
            }
            check_rule = platform_root / "tool" / "config" / "check-rule.yml"

            for current in group.scripts:
                if current.source not in targets or not targets[current.source]:
                    raise OrganizeError(f"no target dialect configured for {current.source}: {current.path}")

                # Ensure canonical path
                if JAR_FILE_RE.fullmatch(current.path.name):
                    c_path = current.path
                else:
                    c_path = temp_dir / (
                        f"{current.date}_{current.author}_{current.order_text}__{current.stem}_"
                        f"{current.source}_[{current.version}].{current.ext}"
                    )
                    if not c_path.exists():
                        shutil.copyfile(current.path, c_path)

                for target in targets[current.source]:
                    task_id = f"{group.platform}::{current.path.name}::{target}"
                    platform_tasks.setdefault(group.platform, []).append({
                        "id": task_id,
                        "file_path": str(c_path),
                        "sharding": str(sharding_path),
                        "check_rule": str(check_rule),
                        "source": current.source,
                        "target": target,
                    })

                # If industry TDSQL, also need TDSQL transform for legacy business/ check
                if group.platform == "industry" and current.source == "TDSQL":
                    legacy_task_id = f"{group.platform}::{current.path.name}::TDSQL_LEGACY"
                    platform_tasks.setdefault(group.platform, []).append({
                        "id": legacy_task_id,
                        "file_path": str(c_path),
                        "sharding": str(sharding_path),
                        "check_rule": str(check_rule),
                        "source": current.source,
                        "target": "TDSQL",
                    })

        # Step 2: Run batch transform per platform
        batch_results: dict[str, tuple[str, str | None, bool]] = {}
        for plat, tasks in platform_tasks.items():
            plat_root = database_root / ("行业应用" if plat == "industry" else "运营支撑门户")
            batch_results.update(execute_batch_transform(tasks, plat_root))

        # Step 3: Construct output plan and paths
        for group in all_groups:
            platform_root = database_root / ("行业应用" if group.platform == "industry" else "运营支撑门户")
            config = read_assignments(platform_root / "tool" / "config" / "sys-config.table")
            targets = {
                "TDSQL": split_list(config.get("tdsqlDatabaseDirList")),
                "ORACLE": split_list(config.get("oracleDatabaseDirList")),
            }
            sequence_base = (group.platform, group.business, group.version, group.child)
            generated_sequences: dict[tuple[str, str], int] = {}

            for current in group.scripts:
                for target in targets[current.source]:
                    task_id = f"{group.platform}::{current.path.name}::{target}"
                    target_sql, sharding_yaml, _ = batch_results[task_id]

                    if group.platform == "industry" and sharding_yaml and original_sharding is not None and sharding_yaml != original_sharding:
                        if updated_sharding is not None and updated_sharding != sharding_yaml:
                            raise OrganizeError("translation returned conflicting sharding YAML updates")
                        updated_sharding = sharding_yaml

                    sequence_key = (*sequence_base, target)
                    sequence = sequences.setdefault(
                        sequence_key,
                        next_sequence_for_target(
                            database_root, group.platform, group.business, group.version, group.child, target,
                        ),
                    )
                    sequences[sequence_key] += 1
                    generated_sequences[(current.path.name, target)] = sequence

                    destination = migration_general(
                        database_root, group.platform, group.business, group.version, group.child,
                    ) / target / output_name(current, sequence)

                    if destination in writes or destination.exists():
                        raise OrganizeError(f"output already exists: {destination}")
                    writes[destination] = target_sql.encode("utf-8")

                # Legacy business/ folder support for industry TDSQL
                if group.platform == "industry" and current.source == "TDSQL":
                    legacy_task_id = f"{group.platform}::{current.path.name}::TDSQL_LEGACY"
                    legacy_sql, sharding_yaml, sub_and_not_create = batch_results[legacy_task_id]

                    if sharding_yaml and original_sharding is not None and sharding_yaml != original_sharding:
                        if updated_sharding is not None and updated_sharding != sharding_yaml:
                            raise OrganizeError("translation returned conflicting sharding YAML updates")
                        updated_sharding = sharding_yaml

                    if not sub_and_not_create:
                        tdsql_target = "tdsql" if "tdsql" in targets[current.source] else targets[current.source][0]
                        business_sequence = generated_sequences.get((current.path.name, tdsql_target))
                        if business_sequence is None:
                            raise OrganizeError(f"TDSQL output was not generated for {current.path}")
                        legacy = business_directory(database_root, group.business, group.child) / group.version / output_name(current, business_sequence)
                        if legacy.exists():
                            raise OrganizeError(f"output already exists: {legacy}")
                        writes[legacy] = legacy_sql.encode("utf-8")

                        schema = business_directory(database_root, group.business, group.child) / "schema_version.sql"
                        t_line = schema_line(schema_table(schema, group.business), current, business_sequence)

                        # Idempotent check: check if already in file
                        existing_text = schema.read_text(encoding="utf-8-sig") if schema.is_file() else ""
                        ver_str = f"'{current.version}.{product_code(current)}.00.{business_sequence:02d}'"
                        if ver_str not in existing_text and output_name(current, business_sequence) not in existing_text:
                            schema_lines.setdefault(schema, []).append(t_line)

            for current in group.scripts:
                backup = platform_root / "backup" / group.business
                if group.child:
                    backup /= group.child
                backup /= Path(date) / current.path.name
                if backup.exists():
                    raise OrganizeError(f"backup destination already exists: {backup}")
                moves.append((current.path, backup))

        for schema, lines in schema_lines.items():
            original = schema.read_bytes() if schema.exists() else b""
            separator = b"" if not original or original.endswith(b"\n") else b"\n"
            writes[schema] = original + separator + "".join(lines).encode("utf-8")
            schema_appends.append({
                "file": str(schema.relative_to(database_root)),
                "lines": lines,
            })

        if updated_sharding is not None:
            writes[sharding_path] = updated_sharding.encode("utf-8")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return writes, moves, schema_appends, original_sharding, updated_sharding


def _checked_path(root: Path, path: Path) -> Path:
    """仅允许仓库内的普通文件路径，拒绝软链接及目录穿越。"""
    path = Path(os.path.abspath(path))
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise OrganizeError(f"path outside database root: {path}") from error
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise OrganizeError(f"symlink is not supported: {current}")
    if path == root or (path.exists() and not path.is_file()):
        raise OrganizeError(f"expected a regular file: {path}")
    return path


def _read_optional(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _digest(content: bytes | None) -> str | None:
    return hashlib.sha256(content).hexdigest() if content is not None else None


def _atomic_write(path: Path, content: bytes) -> None:
    """先在同目录写完整临时文件，替换时保留既有文件权限。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _apply_file_states(
    changes: dict[Path, bytes | None], before: dict[Path, bytes | None],
    modes: dict[Path, int] | None = None,
) -> None:
    """写入、移动和收据共用恢复边界；发生异常则逆序恢复已触及的文件。"""
    touched: list[Path] = []
    original_modes = {path: path.stat().st_mode & 0o777 for path in changes if path.exists()}
    try:
        for path, content in changes.items():
            if _read_optional(path) != before[path]:
                raise OrganizeError(f"file changed during operation: {path}")
            touched.append(path)
            if content is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, content)
                if modes and path in modes:
                    path.chmod(modes[path])
    except Exception as error:
        failures = []
        for path in reversed(touched):
            try:
                if before[path] is None:
                    path.unlink(missing_ok=True)
                else:
                    _atomic_write(path, before[path])
                    path.chmod(original_modes[path])
            except Exception as recovery_error:
                failures.append(f"{path}: {recovery_error}")
        if failures:
            raise OrganizeError("rollback incomplete; preserve current files: " + "; ".join(failures)) from error
        raise


def apply_plan(
    database_root: Path,
    writes: dict[Path, bytes],
    moves: list[tuple[Path, Path]],
    schema_appends: list[dict[str, Any]],
    original_sharding: str | None,
    updated_sharding: str | None,
    metadata: dict[str, Any],
) -> None:
    """保存可校验的前后状态，将收据写入失败也纳入归档恢复范围。"""
    root = database_root.resolve()
    receipt_path = _checked_path(root, root / RECEIPT_FILENAME)
    changes: dict[Path, bytes | None] = {}
    modes: dict[Path, int] = {}
    for destination, content in writes.items():
        changes[_checked_path(root, destination)] = content
    for source, backup in moves:
        source = _checked_path(root, source)
        backup = _checked_path(root, backup)
        if source == backup or source in changes or backup in changes or backup.exists():
            raise OrganizeError(f"conflicting archive paths: {source} -> {backup}")
        content = source.read_bytes()
        # 先落备份，再删除源稿；逆序恢复时先还原源稿。
        changes[backup] = content
        modes[backup] = source.stat().st_mode & 0o777
        changes[source] = None
    if receipt_path in changes:
        raise OrganizeError("plan must not modify the receipt directly")
    before = {path: _read_optional(path) for path in changes}
    previous_receipt = _read_optional(receipt_path)
    receipt = {
        "format_version": 2,
        "timestamp": dt.datetime.now().isoformat(),
        "metadata": metadata,
        "files": [{
            "path": str(path.relative_to(root)),
            "before": base64.b64encode(before[path]).decode("ascii") if before[path] is not None else None,
            "before_mode": path.stat().st_mode & 0o777 if before[path] is not None else None,
            "after_sha256": _digest(content),
        } for path, content in changes.items()],
    }
    changes[receipt_path] = json.dumps(receipt, ensure_ascii=False, indent=2).encode("utf-8")
    before[receipt_path] = previous_receipt
    _apply_file_states(changes, before, modes)


def undo_last_organize(database_root: Path) -> None:
    """先检查全部归档后状态；任何冲突都不执行部分撤销。"""
    root = database_root.resolve()
    receipt_path = _checked_path(root, root / RECEIPT_FILENAME)
    if not receipt_path.is_file():
        raise OrganizeError(f"no {RECEIPT_FILENAME} found in {root}. Nothing to undo.")
    receipt_bytes = receipt_path.read_bytes()
    try:
        receipt = json.loads(receipt_bytes)
        if not isinstance(receipt, dict) or receipt.get("format_version") != 2:
            raise OrganizeError("legacy receipt has no content checksums; automatic undo refused. Review and restore files manually.")
        changes: dict[Path, bytes | None] = {}
        modes: dict[Path, int] = {}
        before: dict[Path, bytes | None] = {}
        conflicts = []
        for item in receipt["files"]:
            relative = Path(item["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise OrganizeError(f"invalid receipt path: {relative}")
            path = _checked_path(root, root / relative)
            if path == receipt_path or path in changes:
                raise OrganizeError(f"duplicate or reserved receipt path: {relative}")
            content = _read_optional(path)
            expected = item["after_sha256"]
            if expected is not None and (not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected)):
                raise OrganizeError(f"invalid content checksum: {relative}")
            if _digest(content) != expected:
                conflicts.append(str(relative))
            before[path] = content
            changes[path] = base64.b64decode(item["before"], validate=True) if item["before"] is not None else None
            if changes[path] is not None:
                mode = item["before_mode"]
                if type(mode) is not int or not 0 <= mode <= 0o777:
                    raise OrganizeError(f"invalid file mode: {relative}")
                modes[path] = mode
        if conflicts:
            raise OrganizeError("undo refused: files changed or missing: " + ", ".join(conflicts))
        # 只撤销最近一次整理，不递归保存历史收据或扩大到更早批次。
        changes[receipt_path] = None
        before[receipt_path] = receipt_bytes
    except OrganizeError:
        raise
    except Exception as error:
        raise OrganizeError(f"invalid receipt; no files changed: {error}") from error
    _apply_file_states(changes, before, modes)
    print(f"Undo complete! Restored previous contents of {len(changes) - 1} file path(s).")


def print_sharding_diff(original: str, updated: str, path: str) -> None:
    diff = list(difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=3,
    ))
    if diff:
        print(f"\n--- Planned changes to {path} ---")
        for line in diff:
            sys.stdout.write(line)
        print("----------------------------------------\n")
