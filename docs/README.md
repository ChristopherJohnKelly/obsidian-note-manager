# Documentation Index

Welcome to the Obsidian Note Automation documentation. This folder contains comprehensive technical documentation for the dual-pipeline system.

## System Overview

The system provides two complementary pipelines:
- **Ingestion Pipeline** (The Librarian): Processes new notes from Capture folder
- **Maintenance Pipeline** (Night Watchman): Scans vault for quality issues

## Getting Started

### [Setup Guide](setup.md)
Step-by-step instructions for installing and configuring the system on a Raspberry Pi. Covers:
- Prerequisites and requirements
- Docker installation
- GitHub authentication setup
- Environment variable configuration
- Deployment and verification

### [Architecture Overview](architecture.md)
High-level system architecture, data flow, and component interactions. Covers:
- Dual pipeline architecture diagram
- Ingestion and maintenance pipeline flows
- Key components and their roles
- Proposal types and metadata
- Security and authentication

## Reference Documentation

### [Component Documentation](components.md)
Detailed breakdown of each component in the system. Covers:
- Pipeline orchestrators (`main.py`, `vault_maintenance.py`)
- Processing components (`processor.py`, `filer.py`, `fixer.py`, `scanner.py`)
- Shared infrastructure (`llm_client.py`, `context_loader.py`, `indexer.py`)
- Error handling patterns

### [API Reference](api-reference.md)
Technical reference for all classes, functions, and modules. Covers:
- Module documentation
- Function signatures and parameters
- Return values and exceptions
- Environment variables
- Type hints and dependencies

### [Code Registry](code-registry.md)
Comprehensive registry of source files, classes, and methods. Covers:
- File overview table
- Detailed file registry with dependencies
- Dependency graph
- Maintenance guide for common modifications
- Testing checklist

### [Workflow Documentation](workflows.md)
GitHub Actions workflow configuration and execution details. Covers:
- Workflow structure and triggers
- Job configuration and steps
- Environment variables and secrets
- Execution flow
- Monitoring and debugging

## Troubleshooting

### [Troubleshooting Guide](troubleshooting.md)
Common issues, solutions, and debugging tips. Covers:
- Runner registration issues
- Workflow triggering problems
- API errors
- Git operation failures
- Container startup issues
- General debugging techniques

### [Pi Offline Troubleshooting](troubleshooting-pi-offline.md)
Comprehensive guide for Raspberry Pi-specific runner offline issues. Covers:
- Network connectivity diagnostics
- Firewall and proxy issues
- Runner process debugging
- Time synchronization
- DNS resolution problems
- Advanced debugging techniques

### [Git Not Updated Troubleshooting](troubleshooting-git-not-updated.md)
Guide for resolving Git synchronization issues.

### [Runner Update Troubleshooting](troubleshooting-runner-update.md)
Guide for updating the GitHub Actions runner.

## Documentation Guide

### New to the Project?

Start here:
1. **[Setup Guide](setup.md)** - Get the system up and running
2. **[Architecture Overview](architecture.md)** - Understand the dual pipeline design
3. **[Component Documentation](components.md)** - Learn about individual components
4. **[Code Registry](code-registry.md)** - Understand code relationships

### Need to Troubleshoot?

1. **[Troubleshooting Guide](troubleshooting.md)** - Common issues and solutions
2. **[Workflow Documentation](workflows.md)** - Workflow-specific issues
3. **[Pi Offline Troubleshooting](troubleshooting-pi-offline.md)** - Runner connectivity

### Want to Understand the Code?

1. **[Code Registry](code-registry.md)** - File and class relationships
2. **[API Reference](api-reference.md)** - Technical API documentation
3. **[Component Documentation](components.md)** - Component details and responsibilities

### Want to Modify the System?

1. **[Code Registry](code-registry.md)** - Maintenance guide section
2. **[Architecture Overview](architecture.md)** - Understand data flow before changes
3. **[API Reference](api-reference.md)** - Function signatures and parameters

## Quick Links

- [Main README](../README.md) - Project overview
- [Runner Setup README](../runner-setup/README.md) - Docker setup quick start
- [GitHub Workflows](../.github/workflows/) - Workflow definitions

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
