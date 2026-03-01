# CLAUDE.md

This file provides guidance for AI assistants working in this repository.

## Project Overview

**Reisetagebuch** (German: "Travel Diary") is a project for creating travel diaries with automatic website generation ("Tagebuch für Reisen mit automatischer Website Generierung").

**Current status:** Early-stage / skeleton. Only a README and MIT license exist. No source code, dependencies, or infrastructure have been implemented yet.

## Repository Structure

```
Reisetagebuch/
├── .git/          # Git metadata
├── LICENSE        # MIT License (Copyright 2026)
├── README.md      # Project description (German)
└── CLAUDE.md      # This file
```

## Tech Stack

Not yet defined. The project intent is a travel diary tool with automatic website generation. When the stack is chosen, document it here (e.g., frontend framework, backend language, database, static site generator).

## Development Workflow

### Branching

- Default branch: `master`
- Remote tracking branch: `origin/main`
- Feature branches follow the pattern: `claude/<description>-<id>`

### Git Conventions

- Use descriptive commit messages in the imperative mood (e.g., "Add initial project structure")
- Branch names should be lowercase with hyphens
- Push feature branches with: `git push -u origin <branch-name>`

### Getting Started

Since no source code exists yet, initial setup steps will depend on the chosen tech stack. When a stack is defined, document the following here:

1. Prerequisites and installation steps
2. How to install dependencies
3. How to start the development server
4. How to run tests
5. How to build for production

## Testing

No test framework has been configured. When tests are added, document:
- The testing framework used
- How to run the full test suite
- How to run individual tests
- Where test files are located

## Configuration

No configuration files exist yet. When added, document:
- Required environment variables (use a `.env.example` as reference)
- Any required external services
- Database setup steps

## Code Conventions

No conventions established yet. When the project matures, define and document:
- Linting rules and formatter settings
- Naming conventions
- File/directory organization patterns
- Language-specific style guides

## Key Decisions to Document

When the project progresses, record architectural decisions here:
- Choice of tech stack and rationale
- Data model for travel diary entries
- Website generation approach (static site generator, SSR, etc.)
- Deployment strategy

## License

MIT — see [LICENSE](./LICENSE) for details.
