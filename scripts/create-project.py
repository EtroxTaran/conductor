#!/usr/bin/env python3
"""Create a new project from template.

This script creates a new project directory inside projects/ using the
specified template type. Projects inherit their context files from templates
and include Docker/docker-compose configurations.

Usage:
    python scripts/create-project.py <project-name> [--type TYPE] [--remote URL]
    python scripts/create-project.py my-app --type react-tanstack
    python scripts/create-project.py my-api --type node-api --remote git@github.com:user/repo.git
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# Available project types
PROJECT_TYPES = {
    "react-tanstack": {
        "name": "React + TanStack",
        "description": "React 19 + TanStack (Query/Router/Form/Table) + Shadcn + Vite",
        "use_case": "Frontend SPA"
    },
    "node-api": {
        "name": "Node.js API",
        "description": "Hono + Zod + Prisma + PostgreSQL",
        "use_case": "Backend API"
    },
    "nx-fullstack": {
        "name": "Nx Monorepo",
        "description": "Nx monorepo + React frontend + Node backend",
        "use_case": "Full-stack app"
    },
    "java-spring": {
        "name": "Java Spring",
        "description": "Spring Boot 3 + Gradle + PostgreSQL",
        "use_case": "Java backend"
    },
    "base": {
        "name": "Base Template",
        "description": "Minimal template for generic projects",
        "use_case": "Custom projects"
    }
}


def get_root_dir() -> Path:
    """Get the meta-architect root directory."""
    script_dir = Path(__file__).parent
    return script_dir.parent.resolve()


def prompt_project_type() -> str:
    """Interactive prompt for project type selection."""
    print("\nSelect project type:\n")
    types = list(PROJECT_TYPES.items())

    for i, (key, info) in enumerate(types, 1):
        print(f"  {i}. {info['name']}")
        print(f"     {info['description']}")
        print(f"     Use case: {info['use_case']}\n")

    while True:
        try:
            choice = input("Enter choice (1-5): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(types):
                selected = types[idx][0]
                print(f"\nSelected: {PROJECT_TYPES[selected]['name']}\n")
                return selected
        except (ValueError, IndexError):
            pass
        print("Invalid choice. Please enter a number between 1-5.")


def run_command(cmd: list[str], cwd: Optional[Path] = None) -> tuple[bool, str]:
    """Run a shell command and return success status and output."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def init_git_repo(project_dir: Path, remote_url: Optional[str] = None) -> bool:
    """Initialize git repository and optionally add remote."""
    # Initialize git
    success, output = run_command(["git", "init"], cwd=project_dir)
    if not success:
        print(f"  Warning: Failed to initialize git: {output}")
        return False
    print("  Initialized git repository")

    # Add remote if provided
    if remote_url:
        success, output = run_command(
            ["git", "remote", "add", "origin", remote_url],
            cwd=project_dir
        )
        if not success:
            print(f"  Warning: Failed to add remote: {output}")
            return False
        print(f"  Added remote: {remote_url}")

    # Create initial commit
    success, _ = run_command(["git", "add", "."], cwd=project_dir)
    if success:
        success, _ = run_command(
            ["git", "commit", "-m", "Initial project setup from template"],
            cwd=project_dir
        )
        if success:
            print("  Created initial commit")

    return True


def copy_skeleton_files(template_dir: Path, project_dir: Path, substitutions: dict) -> None:
    """Copy and process skeleton files from template."""
    skeleton_dir = template_dir / "skeleton"
    if not skeleton_dir.exists():
        return

    for src_path in skeleton_dir.rglob("*"):
        if src_path.is_file():
            # Get relative path from skeleton dir
            rel_path = src_path.relative_to(skeleton_dir)

            # Handle .template extension
            if src_path.suffix == ".template":
                dst_name = rel_path.with_suffix("")  # Remove .template
            else:
                dst_name = rel_path

            dst_path = project_dir / dst_name

            # Create parent directories
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # Process template substitutions
            try:
                content = src_path.read_text()
                for key, value in substitutions.items():
                    content = content.replace(key, value)
                dst_path.write_text(content)
                print(f"  Created: {dst_name}")
            except UnicodeDecodeError:
                # Binary file - copy as-is
                shutil.copy2(src_path, dst_path)
                print(f"  Created: {dst_name}")


def create_type_specific_structure(project_dir: Path, project_type: str) -> None:
    """Create type-specific directory structure."""
    if project_type == "react-tanstack":
        # React project structure
        dirs = [
            "src/components/ui",
            "src/features",
            "src/hooks",
            "src/lib",
            "src/routes",
            "tests/components",
            "public",
        ]
    elif project_type == "node-api":
        # Node API structure
        dirs = [
            "src/routes/v1",
            "src/middleware",
            "src/services",
            "src/db",
            "src/lib",
            "src/types",
            "tests/routes",
            "tests/services",
            "prisma",
        ]
    elif project_type == "nx-fullstack":
        # Nx monorepo structure
        dirs = [
            "apps/web/src",
            "apps/api/src",
            "libs/shared/types/src",
            "libs/shared/utils/src",
            "libs/shared/ui/src",
            "libs/web/data-access/src",
            "libs/api/data-access/src",
            "libs/api/domain/src",
            "tools/scripts",
            "docker",
        ]
    elif project_type == "java-spring":
        # Java Spring structure
        dirs = [
            "src/main/java/com/example/config",
            "src/main/java/com/example/controller",
            "src/main/java/com/example/service",
            "src/main/java/com/example/repository",
            "src/main/java/com/example/model/entity",
            "src/main/java/com/example/model/dto",
            "src/main/java/com/example/exception",
            "src/main/resources",
            "src/test/java/com/example",
            "gradle/wrapper",
        ]
    else:
        # Base template - generic structure
        dirs = ["src", "tests"]

    for dir_path in dirs:
        (project_dir / dir_path).mkdir(parents=True, exist_ok=True)


def create_project(
    name: str,
    project_type: str = "base",
    remote_url: Optional[str] = None,
    force: bool = False
) -> bool:
    """Create a new project from template.

    Args:
        name: Project name (will be used as directory name)
        project_type: Type of project (react-tanstack, node-api, nx-fullstack, java-spring, base)
        remote_url: Optional GitHub remote URL
        force: Overwrite existing project if it exists

    Returns:
        True if successful, False otherwise
    """
    root_dir = get_root_dir()
    projects_dir = root_dir / "projects"
    templates_dir = root_dir / "project-templates"

    project_dir = projects_dir / name
    template_dir = templates_dir / project_type

    # Validate template exists
    if not template_dir.exists():
        print(f"Error: Template '{project_type}' not found at {template_dir}")
        available = [d.name for d in templates_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        print(f"Available templates: {', '.join(available)}")
        return False

    # Check if project already exists
    if project_dir.exists():
        if not force:
            print(f"Error: Project '{name}' already exists at {project_dir}")
            print("Use --force to overwrite")
            return False
        print(f"Removing existing project: {project_dir}")
        shutil.rmtree(project_dir)

    # Create project directory
    print(f"Creating project: {name}")
    print(f"  Type: {PROJECT_TYPES.get(project_type, {}).get('name', project_type)}")
    print(f"  Location: {project_dir}")

    project_dir.mkdir(parents=True)

    # Create workflow directories
    (project_dir / "project-overrides").mkdir()
    (project_dir / ".cursor").mkdir()
    (project_dir / ".workflow" / "phases" / "planning").mkdir(parents=True)
    (project_dir / ".workflow" / "phases" / "validation").mkdir(parents=True)
    (project_dir / ".workflow" / "phases" / "implementation").mkdir(parents=True)
    (project_dir / ".workflow" / "phases" / "verification").mkdir(parents=True)
    (project_dir / ".workflow" / "phases" / "completion").mkdir(parents=True)
    (project_dir / ".workflow" / "progress").mkdir(parents=True)

    # Create type-specific directory structure
    create_type_specific_structure(project_dir, project_type)

    # Create .project-config.json
    config = {
        "project_name": name,
        "project_type": project_type,
        "template": project_type,
        "template_version": "1.0.0",
        "created_at": datetime.now().isoformat(),
        "last_synced": datetime.now().isoformat(),
        "remote_url": remote_url,
        "overrides": {
            "claude": "project-overrides/claude.md",
            "gemini": "project-overrides/gemini.md",
            "cursor": "project-overrides/cursor.md"
        }
    }

    config_path = project_dir / ".project-config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  Created: .project-config.json")

    # Create initial workflow state
    state = {
        "project_name": name,
        "project_type": project_type,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "current_phase": 0,
        "iteration_count": 0,
        "phases": {
            "planning": {"status": "pending", "attempts": 0},
            "validation": {"status": "pending", "attempts": 0},
            "implementation": {"status": "pending", "attempts": 0},
            "verification": {"status": "pending", "attempts": 0},
            "completion": {"status": "pending", "attempts": 0}
        },
        "context": None,
        "git_commits": []
    }

    state_path = project_dir / ".workflow" / "state.json"
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)
    print(f"  Created: .workflow/state.json")

    # Create empty override files
    for agent in ["claude", "gemini", "cursor"]:
        override_path = project_dir / "project-overrides" / f"{agent}.md"
        override_path.write_text(f"# Project-Specific Rules for {agent.title()}\n\n<!-- Add project-specific rules here -->\n")
        print(f"  Created: project-overrides/{agent}.md")

    # Process and copy template files
    sync_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Extract package name for Java projects
    package_name = name.replace("-", "").replace("_", "").lower()

    substitutions = {
        "{{PROJECT_NAME}}": name,
        "{{SYNC_DATE}}": sync_date,
        "{{CREATION_DATE}}": sync_date,
        "{{PROJECT_TYPE}}": project_type,
        "{{PROJECT_OVERRIDES}}": "",  # Will be filled by sync script
        "{{PACKAGE}}": f"com.{package_name}",
        "{{PACKAGE_PATH}}": f"com/{package_name}",
    }

    # Copy and process CLAUDE.md.template
    claude_template = template_dir / "CLAUDE.md.template"
    if claude_template.exists():
        content = claude_template.read_text()
        for key, value in substitutions.items():
            content = content.replace(key, value)
        (project_dir / "CLAUDE.md").write_text(content)
        print(f"  Created: CLAUDE.md")

    # Copy and process GEMINI.md.template
    gemini_template = template_dir / "GEMINI.md.template"
    if gemini_template.exists():
        content = gemini_template.read_text()
        for key, value in substitutions.items():
            content = content.replace(key, value)
        (project_dir / "GEMINI.md").write_text(content)
        print(f"  Created: GEMINI.md")

    # Copy and process .cursor/rules.template
    cursor_template = template_dir / ".cursor" / "rules.template"
    if cursor_template.exists():
        content = cursor_template.read_text()
        for key, value in substitutions.items():
            content = content.replace(key, value)
        (project_dir / ".cursor" / "rules").write_text(content)
        print(f"  Created: .cursor/rules")

    # Copy and process PRODUCT.md.template
    product_template = template_dir / "PRODUCT.md.template"
    if product_template.exists():
        content = product_template.read_text()
        for key, value in substitutions.items():
            content = content.replace(key, value)
        (project_dir / "PRODUCT.md").write_text(content)
        print(f"  Created: PRODUCT.md")

    # Copy and process README.md.template
    readme_template = template_dir / "README.md.template"
    if readme_template.exists():
        content = readme_template.read_text()
        for key, value in substitutions.items():
            content = content.replace(key, value)
        (project_dir / "README.md").write_text(content)
        print(f"  Created: README.md")

    # Copy skeleton files if they exist
    copy_skeleton_files(template_dir, project_dir, substitutions)

    # Create .gitignore for project (type-specific)
    gitignore_content = get_gitignore_content(project_type)
    (project_dir / ".gitignore").write_text(gitignore_content)
    print(f"  Created: .gitignore")

    # Initialize git and optionally add remote
    print()
    init_git_repo(project_dir, remote_url)

    print()
    print(f"Project '{name}' created successfully!")
    print()
    print("Next steps:")
    print(f"  1. Edit projects/{name}/PRODUCT.md with your feature specification")
    print(f"  2. Run: /orchestrate --project {name}")
    if project_type == "react-tanstack":
        print(f"  3. cd projects/{name} && pnpm install")
    elif project_type == "node-api":
        print(f"  3. cd projects/{name} && pnpm install && pnpm prisma generate")
    elif project_type == "nx-fullstack":
        print(f"  3. cd projects/{name} && pnpm install && pnpm nx reset")
    elif project_type == "java-spring":
        print(f"  3. cd projects/{name} && ./gradlew build")
    print()

    return True


def get_gitignore_content(project_type: str) -> str:
    """Get type-specific .gitignore content."""
    base_content = """# Environment
.env
.env.local
.env.*.local
*.local

# IDE
.idea/
.vscode/
*.swp
*.swo

# Workflow artifacts (keep state, ignore large outputs)
.workflow/phases/*/output/

# OS
.DS_Store
Thumbs.db
"""

    if project_type in ("react-tanstack", "node-api"):
        return base_content + """
# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*

# Build
dist/
build/
.cache/

# Testing
coverage/
.nyc_output/

# Vite
*.local

# TypeScript
*.tsbuildinfo
"""
    elif project_type == "nx-fullstack":
        return base_content + """
# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*

# Nx
.nx/
dist/
tmp/

# Build
build/
.cache/

# Testing
coverage/
.nyc_output/

# TypeScript
*.tsbuildinfo
"""
    elif project_type == "java-spring":
        return base_content + """
# Gradle
.gradle/
build/
!gradle/wrapper/gradle-wrapper.jar

# Java
*.class
*.jar
*.war
*.ear
*.logs
*.log

# IntelliJ
out/
*.iml
.idea/

# Eclipse
.classpath
.project
.settings/
"""
    else:
        return base_content + """
# Python
__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
.coverage
htmlcov/
*.egg-info/
.mypy_cache/

# Node
node_modules/
npm-debug.log*

# Build
dist/
build/
"""


def list_projects() -> None:
    """List all existing projects."""
    root_dir = get_root_dir()
    projects_dir = root_dir / "projects"

    if not projects_dir.exists():
        print("No projects directory found.")
        return

    projects = [d for d in projects_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]

    if not projects:
        print("No projects found.")
        return

    print("Existing projects:\n")
    for project in sorted(projects):
        config_path = project / ".project-config.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            ptype = config.get("project_type", config.get("template", "unknown"))
            created = config.get("created_at", "unknown")[:10]
            remote = config.get("remote_url", "")

            type_info = PROJECT_TYPES.get(ptype, {}).get("name", ptype)
            print(f"  {project.name}")
            print(f"    Type: {type_info}")
            print(f"    Created: {created}")
            if remote:
                print(f"    Remote: {remote}")
            print()
        else:
            print(f"  {project.name} (no config)\n")


def list_templates() -> None:
    """List available project templates."""
    print("Available project templates:\n")
    print(f"  {'Template':<16} {'Stack':<45} {'Use Case'}")
    print(f"  {'-'*16} {'-'*45} {'-'*20}")

    for key, info in PROJECT_TYPES.items():
        print(f"  {key:<16} {info['description']:<45} {info['use_case']}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Create a new project from template",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Project Types:
  react-tanstack   React 19 + TanStack + Shadcn + Vite
  node-api         Hono + Zod + Prisma + PostgreSQL
  nx-fullstack     Nx monorepo (React + Node)
  java-spring      Spring Boot 3 + Gradle

Examples:
  python scripts/create-project.py my-app                      # Interactive type selection
  python scripts/create-project.py my-app --type react-tanstack
  python scripts/create-project.py my-api --type node-api --remote git@github.com:user/repo.git
  python scripts/create-project.py --list                      # List projects
  python scripts/create-project.py --templates                 # List templates
        """
    )

    parser.add_argument(
        "name",
        nargs="?",
        help="Project name (will be used as directory name)"
    )
    parser.add_argument(
        "--type", "-t",
        choices=list(PROJECT_TYPES.keys()),
        help="Project type (default: interactive selection)"
    )
    parser.add_argument(
        "--remote", "-r",
        metavar="URL",
        help="GitHub remote URL to connect"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing project"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List existing projects"
    )
    parser.add_argument(
        "--templates",
        action="store_true",
        help="List available templates"
    )

    args = parser.parse_args()

    if args.list:
        list_projects()
        return

    if args.templates:
        list_templates()
        return

    if not args.name:
        parser.print_help()
        sys.exit(1)

    # Validate project name
    if not args.name.replace("-", "").replace("_", "").isalnum():
        print(f"Error: Invalid project name '{args.name}'")
        print("Project name must contain only letters, numbers, hyphens, and underscores")
        sys.exit(1)

    # Interactive type selection if not specified
    project_type = args.type
    if not project_type:
        try:
            project_type = prompt_project_type()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            sys.exit(1)

    success = create_project(
        args.name,
        project_type=project_type,
        remote_url=args.remote,
        force=args.force
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
