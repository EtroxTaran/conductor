---
description: Create a new project from template
allowed-tools: ["Bash", "Read"]
---

# Create New Project

Create a new project in the `projects/` directory from a template with optional GitHub remote connection.

## Usage

```bash
python scripts/create-project.py <project-name> [--type TYPE] [--remote URL]
```

## Arguments

- `<project-name>`: Name for the new project (letters, numbers, hyphens, underscores)
- `--type`, `-t`: Project type (default: interactive selection)
- `--remote`, `-r`: GitHub remote URL to connect

## Project Types

| Type | Stack | Use Case |
|------|-------|----------|
| `react-tanstack` | React 19 + TanStack (Query/Router/Form/Table) + Shadcn + Vite | Frontend SPA |
| `node-api` | Hono + Zod + Prisma + PostgreSQL | Backend API |
| `nx-fullstack` | Nx monorepo + React frontend + Node backend | Full-stack app |
| `java-spring` | Spring Boot 3 + Gradle + PostgreSQL | Java backend |
| `base` | Minimal template | Custom projects |

## Examples

```bash
# Interactive type selection
python scripts/create-project.py my-app

# Specific type
python scripts/create-project.py my-frontend --type react-tanstack

# Backend API with type
python scripts/create-project.py my-api --type node-api

# Full-stack Nx monorepo
python scripts/create-project.py my-platform --type nx-fullstack

# Java backend
python scripts/create-project.py my-service --type java-spring

# With GitHub remote
python scripts/create-project.py my-api --type node-api --remote git@github.com:user/repo.git

# List existing projects
python scripts/create-project.py --list

# List available templates
python scripts/create-project.py --templates
```

## What Gets Created

### All Project Types

```
projects/<name>/
├── .project-config.json     # Project configuration
├── CLAUDE.md                # Worker Claude context (tech-specific)
├── GEMINI.md                # Gemini reviewer context
├── .cursor/rules            # Cursor reviewer context
├── PRODUCT.md               # Feature spec template (EDIT THIS)
├── README.md                # Project documentation
├── .gitignore               # Git ignore patterns
├── Dockerfile               # Container build
├── docker-compose.yml       # Container orchestration
├── project-overrides/       # Project-specific rule overrides
├── .workflow/               # Workflow state and phases
└── [type-specific files]    # Source code, configs, etc.
```

### Type-Specific Structure

#### react-tanstack
```
├── src/
│   ├── components/ui/       # Shadcn components
│   ├── features/            # Feature modules
│   ├── hooks/               # Shared hooks
│   ├── lib/                 # Utils, API client
│   └── routes/              # TanStack Router
├── tests/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── components.json          # Shadcn config
```

#### node-api
```
├── src/
│   ├── routes/v1/           # API routes
│   ├── middleware/          # Express middleware
│   ├── services/            # Business logic
│   ├── db/                  # Prisma client
│   ├── lib/                 # Utils, logger
│   └── types/               # TypeScript types
├── tests/
├── prisma/schema.prisma
├── package.json
└── tsconfig.json
```

#### nx-fullstack
```
├── apps/
│   ├── web/                 # React frontend
│   └── api/                 # Node backend
├── libs/
│   ├── shared/types/        # Shared TS types
│   ├── shared/utils/        # Shared utilities
│   └── shared/ui/           # Shared components
├── docker/
├── nx.json
├── tsconfig.base.json
└── pnpm-workspace.yaml
```

#### java-spring
```
├── src/main/java/.../
│   ├── controller/          # REST controllers
│   ├── service/             # Business logic
│   ├── repository/          # Data access
│   ├── model/entity/        # JPA entities
│   ├── model/dto/           # DTOs
│   └── exception/           # Error handling
├── src/main/resources/
│   └── application.yml
├── src/test/java/
├── build.gradle.kts
└── settings.gradle.kts
```

## Features

### Git Remote Connection

When `--remote` is provided:
1. Initializes git repository
2. Adds the remote as `origin`
3. Creates initial commit

```bash
python scripts/create-project.py my-api --type node-api --remote git@github.com:user/repo.git
# After creation:
cd projects/my-api && git remote -v
# origin  git@github.com:user/repo.git (fetch)
# origin  git@github.com:user/repo.git (push)
```

### Interactive Type Selection

When `--type` is not provided, you'll be prompted:

```
Select project type:

  1. React + TanStack
     React 19 + TanStack (Query/Router/Form/Table) + Shadcn + Vite
     Use case: Frontend SPA

  2. Node.js API
     Hono + Zod + Prisma + PostgreSQL
     Use case: Backend API

  3. Nx Monorepo
     Nx monorepo + React frontend + Node backend
     Use case: Full-stack app

  4. Java Spring
     Spring Boot 3 + Gradle + PostgreSQL
     Use case: Java backend

  5. Base Template
     Minimal template for generic projects
     Use case: Custom projects

Enter choice (1-5):
```

### Docker Support (ARM64 Compatible)

All templates include:
- Multi-stage Dockerfiles optimized for size
- ARM64/AMD64 compatible base images
- docker-compose.yml with database services
- Health checks configured

```bash
# Build and run
cd projects/<name>
docker compose up -d

# Development mode (hot reload)
docker compose --profile dev up
```

## Next Steps

After creating a project:

1. **Edit the product spec**:
   ```bash
   vim projects/<name>/PRODUCT.md
   ```

2. **Install dependencies**:
   ```bash
   # React/Node
   cd projects/<name> && pnpm install

   # Java
   cd projects/<name> && ./gradlew build
   ```

3. **Start the workflow**:
   ```bash
   /orchestrate --project <name>
   ```

## Notes

- Project names must be unique
- Use `--force` to overwrite existing projects
- Templates include technology-specific agent context
- All templates support the 5-phase workflow
