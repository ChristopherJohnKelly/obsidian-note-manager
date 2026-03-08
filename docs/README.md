# Documentation Index

Welcome to the Obsidian Note Automation documentation. This folder contains comprehensive technical documentation for the dual-pipeline system built on Clean Architecture (`src_v2/`).

## System Overview

The system provides two complementary pipelines:
- **Ingestion Pipeline** (The Librarian): Processes new notes from Capture folder, files approved proposals
- **Maintenance Pipeline** (Night Watchman): Scans vault for quality issues, generates fix proposals

**Three Modes**: Manual (human-only), Asynchronous Automation (Night Watchman), Event-Driven Ingestion (Librarian).

## Getting Started

### [Setup Guide](setup.md)
Step-by-step instructions for installing and configuring the system on a Raspberry Pi. Covers:
- Prerequisites and requirements
- Docker installation
- GitHub authentication setup
- Environment variable configuration (from repo root)
- Deployment and verification

### [Architecture Overview](architecture.md)
High-level system architecture, data flow, and component interactions. Covers:
- Tri-part architecture (Data & Orchestration, Execution Hardware, Application Engine)
- GitOps boundary (Python mutates files; workflows handle Git)
- Ingestion and maintenance pipeline flows
- Key components (src_v2 Clean Architecture)
- Proposal types and metadata
- Security and authentication

## Reference Documentation

### [Component Documentation](components.md)
Detailed breakdown of each component in the system. Covers:
- Entry points (ingest_runner, cron_runner, cli)
- Use cases (IngestionService, FilerService, MaintenanceService, LibrarianService, AssistantService)
- Core (domain models, ports, response_parser, vault_utils)
- Infrastructure adapters (ObsidianFileSystemAdapter, GeminiAdapter)
- Error handling patterns

### [API Reference](api-reference.md)
Technical reference for classes, functions, and modules. Covers:
- src_v2 module documentation
- Function signatures and parameters
- Environment variables
- Type hints and dependencies

### [Code Registry](code-registry.md)
Comprehensive registry of source files, classes, and methods. Covers:
- File overview table (src_v2 Clean Architecture)
- Dependency graph
- Maintenance guide for common modifications
- Testing checklist

### [Workflow Documentation](workflows.md)
GitHub Actions workflow configuration and execution details. Covers:
- Workflow structure and triggers
- Source: `example/workflows/` (templates copied to vault repo)
- Job configuration and steps
- Environment variables and secrets
- Execution flow

### [Ingest Deployment](ingest-deployment.md)
How to deploy the ingestion pipeline to your obsidian-notes repository.

## Troubleshooting

### [Troubleshooting Guide](troubleshooting.md)
Consolidated guide for common issues and solutions. Covers:
- Runner not appearing / offline
- Workflow not triggering
- Git / workflow issues (repo not updated)
- Runner update / Docker issues
- Gemini API errors
- Container startup issues
- General debugging techniques

## Documentation Guide

### New to the Project?

Start here:
1. **[Setup Guide](setup.md)** - Get the system up and running
2. **[Architecture Overview](architecture.md)** - Understand the tri-part design and GitOps boundary
3. **[Component Documentation](components.md)** - Learn about src_v2 components
4. **[Code Registry](code-registry.md)** - Understand code relationships

### Need to Troubleshoot?

1. **[Troubleshooting Guide](troubleshooting.md)** - Common issues and solutions
2. **[Workflow Documentation](workflows.md)** - Workflow-specific issues

### Want to Understand the Code?

1. **[Code Registry](code-registry.md)** - File and class relationships (src_v2)
2. **[API Reference](api-reference.md)** - Technical API documentation
3. **[Component Documentation](components.md)** - Component details and responsibilities

### Want to Modify the System?

1. **[Code Registry](code-registry.md)** - Maintenance guide section
2. **[Architecture Overview](architecture.md)** - Understand data flow before changes
3. **[API Reference](api-reference.md)** - Function signatures and parameters

## Quick Links

- [Main README](../README.md) - Project overview
- [Example Workflows](../example/workflows/) - Workflow templates (copy to vault repo `.github/workflows/`)

## Key Concepts

### Proposal Workflow

```
Raw Note → Processing → Proposal (Review Queue) → Approval → Final Location
                              ↓
                    User sets librarian: file
```

### Maintenance Workflow

```
Vault Scan → Quality Score → Proposal (Review Queue) → Approval → Updated Note
     ↓                              ↓
  7-day cooldown           User reviews & approves
```

### Key Metadata Fields

| Field | Purpose | Used By |
|-------|---------|---------|
| `librarian: review` | Proposal awaiting review | Filer (skips) |
| `librarian: file` | Approved, ready to execute | Filer (processes) |
| `target-file` | Original file path (maintenance) | Filer (update mode) |
| `files-to-create` | List of output paths | Filer (creates) |

## Documentation Standards

All documentation follows these standards:

- **Clear Structure**: Organized with headers and sections
- **Code Examples**: Includes practical examples where relevant
- **Error Messages**: Documents common error messages and solutions
- **Cross-References**: Links between related documentation
- **Consistent Format**: Uses markdown with code blocks and tables

---

**Note**: If you find any issues or have suggestions for improving the documentation, please open an issue on the repository.
