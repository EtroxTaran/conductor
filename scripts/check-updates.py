#!/usr/bin/env python3
"""Check for available updates to meta-architect projects.

This script checks if updates are available for projects and displays
what changes would be applied.

Usage:
    python scripts/check-updates.py --project my-app
    python scripts/check-updates.py --all
    python scripts/check-updates.py --remote
"""

import argparse
import json
import sys
from pathlib import Path


def get_root_dir() -> Path:
    """Get the meta-architect root directory."""
    script_dir = Path(__file__).parent
    return script_dir.parent.resolve()


# Add orchestrator to path
sys.path.insert(0, str(get_root_dir()))

from orchestrator.update_manager import UpdateManager, format_update_check


def check_single_project(manager: UpdateManager, project_name: str, json_output: bool = False) -> bool:
    """Check updates for a single project.

    Args:
        manager: UpdateManager instance
        project_name: Name of the project
        json_output: Whether to output as JSON

    Returns:
        True if updates are available
    """
    update_info = manager.check_updates(project_name)

    if json_output:
        print(json.dumps(update_info.to_dict(), indent=2))
    else:
        print(format_update_check(update_info))

    return update_info.updates_available


def check_all_projects(manager: UpdateManager, json_output: bool = False) -> int:
    """Check updates for all projects.

    Args:
        manager: UpdateManager instance
        json_output: Whether to output as JSON

    Returns:
        Number of projects with updates available
    """
    projects_dir = manager.projects_dir
    if not projects_dir.exists():
        print("No projects directory found.")
        return 0

    projects = [d for d in projects_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]

    if not projects:
        print("No projects found.")
        return 0

    results = []
    updates_count = 0

    for project_dir in sorted(projects):
        project_name = project_dir.name
        update_info = manager.check_updates(project_name)
        results.append(update_info.to_dict())

        if update_info.updates_available:
            updates_count += 1

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        print("\n" + "=" * 60)
        print("Project Update Status")
        print("=" * 60)

        for result in results:
            status = "NEEDS UPDATE" if result["updates_available"] else "Up to date"
            current = result["current_version"]
            latest = result["latest_version"]

            if result["updates_available"]:
                print(f"\n  {result['project_name']}")
                print(f"    Current: {current} -> Latest: {latest}")
                if result["is_breaking_update"]:
                    print("    ⚠️  Breaking update!")
            else:
                print(f"\n  {result['project_name']}: {status} ({current})")

        print("\n" + "-" * 60)
        print(f"Summary: {updates_count}/{len(results)} projects need updates")

    return updates_count


def check_remote_updates(manager: UpdateManager, json_output: bool = False) -> bool:
    """Check for remote meta-architect updates.

    Args:
        manager: UpdateManager instance
        json_output: Whether to output as JSON

    Returns:
        True if remote updates are available
    """
    result = manager.check_remote_updates()

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print("\n" + "=" * 60)
        print("Remote Update Check")
        print("=" * 60)
        print(f"\n  Current version: {result.get('current_version', 'unknown')}")

        if result.get("error"):
            print(f"  Error: {result['error']}")
        elif result.get("has_remote_updates"):
            print("  Status: Remote updates available")
            print("\n  Run 'git pull origin main' to update meta-architect,")
            print("  then run 'python scripts/sync-project-templates.py --all'")
        else:
            print("  Status: Up to date with remote")

    return result.get("has_remote_updates", False)


def main():
    parser = argparse.ArgumentParser(
        description="Check for available updates to meta-architect projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/check-updates.py --project my-app
  python scripts/check-updates.py --all
  python scripts/check-updates.py --remote
  python scripts/check-updates.py --all --json
        """,
    )

    parser.add_argument(
        "--project", "-p",
        type=str,
        help="Project name to check",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Check all projects",
    )
    parser.add_argument(
        "--remote", "-r",
        action="store_true",
        help="Check for remote meta-architect updates",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    if not args.project and not args.all and not args.remote:
        parser.print_help()
        sys.exit(1)

    root_dir = get_root_dir()
    manager = UpdateManager(root_dir)

    exit_code = 0

    if args.remote:
        has_updates = check_remote_updates(manager, args.json)
        if has_updates:
            exit_code = 1

    if args.all:
        updates_count = check_all_projects(manager, args.json)
        if updates_count > 0:
            exit_code = 1

    if args.project:
        # Check project exists
        project_dir = manager.projects_dir / args.project
        if not project_dir.exists():
            print(f"Error: Project '{args.project}' not found")
            sys.exit(1)

        has_updates = check_single_project(manager, args.project, args.json)
        if has_updates:
            exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
