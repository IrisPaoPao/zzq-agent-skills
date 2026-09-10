"""Command line interface for bsq-sql-organize."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from bs_database_script_organizer.organizer import (
    OrganizeError,
    apply_plan,
    discover,
    groups,
    plan,
    print_sharding_diff,
    resolve_database_root,
    undo_last_organize,
    validate,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bsq-sql-organize",
        description="Organize and archive saas-database migration scripts (replicates 数据库脚本工具.exe)",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="undo the last organize operation and restore original scripts to temp/",
    )
    parser.add_argument(
        "--database-root",
        type=Path,
        help="saas-database checkout root (auto-detected if omitted)",
    )
    parser.add_argument(
        "--platform",
        choices=("industry", "operate", "all"),
        default="all",
        help="target platform: industry (行业应用), operate (运营支撑门户), or all",
    )
    parser.add_argument(
        "--business",
        help="only process one temp business directory (e.g. 01_standard, 04_complex_charge)",
    )
    parser.add_argument(
        "--all-businesses",
        action="store_true",
        help="allow processing multiple business directories without explicitly specifying --business",
    )
    parser.add_argument(
        "--product-child",
        help="projectized child directory (for example 350001_law); filters or names projectized output",
    )
    parser.add_argument(
        "--version",
        help="only process one script version (e.g. 1.3.31, 3.0.8.4, 4.6.2.0)",
    )
    parser.add_argument(
        "--date",
        help="backup directory date in YYYYMMDD (defaults to today)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and transform without changing files",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="show detailed plan output and unified diffs",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    database_root = resolve_database_root(args.database_root)
    if not database_root.is_dir():
        raise OrganizeError(f"saas-database checkout not found: {database_root}")

    if args.undo:
        undo_last_organize(database_root)
        return 0

    if not args.date:
        backup_date = dt.date.today().strftime("%Y%m%d")
    else:
        if not re.fullmatch(r"\d{8}", args.date):
            raise OrganizeError("--date must use YYYYMMDD format")
        try:
            dt.datetime.strptime(args.date, "%Y%m%d")
        except ValueError as error:
            raise OrganizeError("--date must be a valid calendar date in YYYYMMDD") from error
        backup_date = args.date

    scripts = discover(database_root, args.platform, args.business, args.version, args.product_child)
    if not scripts:
        print("No temp scripts found matching the specified criteria.")
        return 0

    # Multi-business safety check
    unique_businesses = sorted(set(s.business for s in scripts))
    if not args.business and not args.all_businesses:
        if len(unique_businesses) > 1:
            biz_list = ", ".join(unique_businesses)
            raise OrganizeError(
                f"Multiple business directories found with temp scripts: [{biz_list}].\n"
                f"To prevent accidental archiving of other teams' drafts, please specify --business <name>.\n"
                f"Or use --all-businesses if you explicitly intend to process all businesses together."
            )
        elif len(unique_businesses) == 1:
            print(f"Auto-selected sole business: {unique_businesses[0]}")

    groups_to_process = groups(scripts)

    print(f"Discovered {len(scripts)} temp script(s) in {len(groups_to_process)} group(s). Validating...")
    for script in scripts:
        platform_root = database_root / ("行业应用" if script.platform == "industry" else "运营支撑门户")
        validate(script, platform_root, database_root)

    print("Validation passed. Planning migrations and archiving (Batch mode)...")
    writes, moves, schema_appends, orig_sharding, upd_sharding = plan(database_root, groups_to_process, backup_date)

    if upd_sharding and orig_sharding and upd_sharding != orig_sharding:
        if args.verbose or args.dry_run:
            print_sharding_diff(orig_sharding, upd_sharding, "行业应用/saas-sharding.yml.vm")

    if args.verbose or args.dry_run:
        print("\n--- Planned writes ---")
        for path in sorted(writes.keys()):
            rel = path.relative_to(database_root)
            print(f"  [+] {rel}")
        print("\n--- Planned backups ---")
        for src, dst in moves:
            src_rel = src.relative_to(database_root)
            dst_rel = dst.relative_to(database_root)
            print(f"  [>] {src_rel} -> {dst_rel}")
        print("----------------------\n")

    if args.dry_run:
        print(f"[DRY-RUN] Validated {len(scripts)} scripts in {len(groups_to_process)} groups.")
        print(f"[DRY-RUN] Would write {len(writes)} files and archive {len(moves)} files.")
        return 0

    metadata = {
        "platform": args.platform,
        "business": args.business or (unique_businesses[0] if len(unique_businesses) == 1 else "all"),
        "version": args.version or "all",
        "date": backup_date,
    }
    apply_plan(database_root, writes, moves, schema_appends, orig_sharding, upd_sharding, metadata)
    print(f"Successfully organized {len(scripts)} scripts in {len(groups_to_process)} groups.")
    print(f"Wrote {len(writes)} files and archived {len(moves)} files to backup.")
    print(f"Receipt recorded in {RECEIPT_FILENAME}. To undo this operation, run with --undo.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except OrganizeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
