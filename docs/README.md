# Documentation Index

Welcome to the Obsidian Note Automation documentation. This folder contains comprehensive technical documentation for the system.

## 📖 Getting Started

### [Setup Guide](setup.md)
Step-by-step instructions for installing and configuring the system on a Raspberry Pi. Covers:
- Prerequisites and requirements
- Docker installation
- GitHub authentication setup
- Environment variable configuration
- Deployment and verification

### [Architecture Overview](architecture.md)
High-level system architecture, data flow, and component interactions. Covers:
- System architecture diagram
- Key components and their roles
- Data flow through the system
- Technology stack
- Security and authentication

## 🔧 Reference Documentation

### [Component Documentation](components.md)
Detailed breakdown of each component in the system. Covers:
- Application components (`main.py`, `processor.py`, etc.)
- Infrastructure components (`Dockerfile`, `entrypoint.sh`, etc.)
- Workflow components (GitHub Actions)
- Component interactions
- Error handling patterns

### [API Reference](api-reference.md)
Technical reference for all classes, functions, and modules. Covers:
- Module documentation
- Function signatures and parameters
- Return values and exceptions
- Environment variables
- Type hints and dependencies

### [Workflow Documentation](workflows.md)
GitHub Actions workflow configuration and execution details. Covers:
- Workflow structure and triggers
- Job configuration and steps
- Environment variables and secrets
- Execution flow
- Monitoring and debugging

## 🐛 Troubleshooting

### [Troubleshooting Guide](troubleshooting.md)
Common issues, solutions, and debugging tips. Covers:
- Runner registration issues
- Workflow triggering problems
- API errors
- Git operation failures
- Container startup issues
- General debugging techniques

## 📚 Documentation Guide

### New to the Project?

Start here:
1. **[Setup Guide](setup.md)** - Get the system up and running
2. **[Architecture Overview](architecture.md)** - Understand how it works
3. **[Component Documentation](components.md)** - Learn about individual components

### Need to Troubleshoot?

1. **[Troubleshooting Guide](troubleshooting.md)** - Common issues and solutions
2. **[Workflow Documentation](workflows.md)** - Workflow-specific issues

### Want to Understand the Code?

1. **[API Reference](api-reference.md)** - Technical API documentation
2. **[Component Documentation](components.md)** - Component details and responsibilities

## 🔗 Quick Links

- [Main README](../README.md) - Project overview
- [Runner Setup README](../runner-setup/README.md) - Docker setup quick start
- [GitHub Workflows](../.github/workflows/) - Workflow definitions

## 📝 Documentation Standards

All documentation follows these standards:

- **Clear Structure**: Organized with headers and sections
- **Code Examples**: Includes practical examples where relevant
- **Error Messages**: Documents common error messages and solutions
- **Cross-References**: Links between related documentation
- **Consistent Format**: Uses markdown with code blocks and tables

---

**Note**: If you find any issues or have suggestions for improving the documentation, please open an issue on the repository.
