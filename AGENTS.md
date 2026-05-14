# AGENTS.md

# PatchRaptor Agent Operating Rules

PatchRaptor is a production-oriented automation companion for ARK: Survival Ascended server management. Helpful info is found in /docs - read it.

This repository contains operational runtime logic used in real server environments.

The codebase itself is the source of truth.

Agents must derive understanding from implementation, runtime flow, and existing architecture — not assumptions.

---

# Primary Objective

Safely implement verified changes while preserving existing operational behavior.

The goals are:
- correctness
- stability
- maintainability
- regression prevention
- architecture consistency

The goals are NOT:
- unnecessary rewrites
- speculative refactors
- aesthetic cleanup
- abstraction for its own sake

---

# Core Engineering Principles

## Preserve Existing Behavior

Existing functionality is assumed intentional unless explicitly identified otherwise.

Do not:
- simplify complex logic without verification
- remove code because it appears redundant
- replace mature implementations with cleaner abstractions
- rewrite systems outside task scope
- remove compatibility behavior
- alter runtime ordering casually

If behavior appears unusual:
- investigate before modifying
- assume operational or historical reasoning exists

---

## Task Scope Isolation

Only modify systems directly relevant to the requested task.

Avoid:
- opportunistic refactors
- unrelated renaming
- broad formatting changes
- adjacent cleanup
- unnecessary file restructuring
- altering unrelated imports
- changing unrelated logging behavior

Changes outside scope require explicit justification.

---

# Repository Truth Policy

Implementation is authoritative.

Agents must:
- read relevant files completely before editing
- trace execution flow
- verify assumptions against implementation
- inspect caller/callee relationships
- search for existing patterns before creating new ones

Never infer architecture from filenames alone.

If documentation conflicts with implementation:
- implementation wins
- outdated documentation should be flagged
- assumptions must be revalidated against code

---

# Change Verification Requirements

Before finalizing changes, verify:

1. imports remain valid
2. modified execution paths still function
3. existing command flows remain intact
4. config compatibility is preserved
5. async/threading behavior is unaffected
6. logging/error handling remains intact
7. external integrations still receive expected data
8. no unrelated regressions were introduced

Changes are not considered complete until verification is performed.

---

# Regression Prevention Rules

Do not:
- remove fallback logic
- remove retry handling
- remove defensive validation
- remove existing logs without reason
- remove parameters because they appear unused
- collapse multi-stage flows casually
- alter startup order without tracing dependencies

If replacing logic:
- preserve observable behavior
- document behavioral differences explicitly

---

# Architecture Understanding Workflow

Before implementing modifications:

1. identify the task entry point
2. identify upstream callers
3. identify downstream dependencies
4. identify state mutation locations
5. identify config dependencies
6. identify external integrations
7. identify threading/async implications
8. identify persistence implications
9. identify runtime side effects

Agents must establish runtime understanding before editing.

---

# Sensitive Systems

Extra caution is required when modifying:

- license validation
- Windows registry interaction
- Discord bot initialization
- RCON communication
- SteamCMD interaction
- startup/bootstrap flow
- config loading/saving
- scheduler systems
- async/threading systems
- network operations
- production server workflows

Changes in these systems must prioritize:
- backward compatibility
- operational stability
- predictable runtime behavior

---

# Modification Strategy

Preferred order:

1. extend existing implementation
2. reuse existing utilities
3. add isolated helper logic
4. introduce new modules only if justified

Avoid:
- duplicate implementations
- parallel systems
- speculative abstractions
- framework-style rewrites
- architecture drift

Minimal targeted changes are preferred.

---

# Logging Rules

Preserve existing logging patterns.

When adding logs:
- include subsystem context
- include meaningful operational information
- avoid noisy spam logging
- preserve troubleshooting usefulness

Do not remove useful operational logging casually.

---

# Error Handling Rules

Preserve defensive behavior.

Do not:
- silently swallow exceptions
- weaken validation
- remove existing guards
- suppress operational failures

Unexpected states should fail clearly and predictably.

---

# Configuration Rules

Configuration compatibility is critical.

Do not:
- remove existing config keys casually
- break older configurations
- assume new fields exist
- hardcode environment-specific behavior

New config fields should:
- include safe defaults
- preserve backward compatibility
- avoid breaking existing deployments

---

# Async / Threading Rules

PatchRaptor contains operational async/runtime systems.

Do not:
- introduce blocking behavior into async flows
- alter concurrency behavior casually
- change task scheduling order without tracing effects
- remove timeout handling
- remove retry handling

Threading and async modifications require careful dependency tracing.

---

# Development Environment Constraints

## Source Control

Do not assume Git workflows exist.

The repository may not use:
- git branches
- commit history
- pull requests
- automated rollback
- CI/CD pipelines

Agents must therefore:
- avoid risky broad rewrites
- minimize regression risk
- make targeted reversible changes
- clearly document modified files and behaviors

Changes should be easy to manually review and revert if required.

---

# Runtime Environment Reality

PatchRaptor is not executed on the primary development workstation.

Development environment and runtime environments are separate.

## Test Environment

Testing is primarily performed on:
- Windows Server 2022
- Dell R230 system

This environment is used for:
- validation
- integration testing
- runtime verification
- deployment testing

---

## Production Environment

Production runs on:
- separate Windows 11 machine

Production behavior must be treated as operationally critical.

Agents must:
- prioritize runtime stability
- preserve backward compatibility
- avoid assumptions based on local machine state
- avoid introducing environment-specific behavior

---

# Validation Constraints

Agents cannot assume:
- local execution is available
- production infrastructure is accessible
- runtime services are active
- external integrations can be tested locally

Because of this:
- validation should focus on code-path correctness
- changes should be minimally invasive
- operational risk should always be assessed
- manual deployment/testing requirements should be identified clearly

---

# Deployment Philosophy

PatchRaptor changes are deployed manually.

Agents should therefore:
- keep changes isolated
- avoid unnecessary file churn
- avoid massive refactors
- preserve existing operational flows
- clearly identify deployment-sensitive changes

Deployment simplicity and operational predictability are priorities.

---

# Testing Philosophy

Tests validate behavior preservation, not just syntax correctness.

Before completion:
- validate imports
- validate runtime flow
- validate execution paths
- validate integration assumptions
- validate backward compatibility
- validate task scope containment

If tests exist:
- prefer targeted execution first
- avoid modifying unrelated failing tests

---

# Repository Knowledge System

Agents should continuously build understanding of:
- subsystem responsibilities
- runtime flow
- startup ordering
- configuration lifecycle
- state management
- Discord command architecture
- RCON communication flow
- scheduler interactions
- external integrations
- operational dependencies

Reference repository documentation continuously.

---

# Documentation Expectations

Important systems should maintain documentation covering:
- purpose
- responsibilities
- entry points
- dependencies
- runtime behavior
- side effects
- operational risks
- compatibility constraints

---

# Repository Documentation

Agents should reference:
- /docs/repository_map.md
- /docs/architecture.md
- /docs/runtime_flow.md
- /docs/conventions.md
- /docs/subsystems/

These documents provide architectural and operational context.

If implementation conflicts with documentation:
- implementation behavior is authoritative
- documentation drift should be identified

---

# Output Requirements

When completing work, provide:

1. root cause analysis
2. implementation summary
3. files modified
4. reasoning for modifications
5. regression risks
6. validation performed
7. remaining concerns or technical debt

---

# Forbidden Behaviors

Never:
- fabricate APIs or behaviors
- assume implementation details without reading code
- replace production logic with placeholders
- silently remove functionality
- undo unrelated features
- overwrite architecture decisions casually
- perform broad rewrites without approval
- prioritize elegance over operational stability

---

# Final Principle

Understand the existing system before modifying it.

PatchRaptor is a production operational system — not a greenfield demo project.

---

# Operational Tool List

Only use the following tools. These have been verified to work reliably:

## Read-Only Tools
- `read_file` — reads file contents from any path
- `file_glob_search` — finds files by glob pattern (works with both \ and / separators)
- `run_terminal_command` — executes terminal commands in PowerShell shell
- `ls` — lists directory contents (recursive or flat)
- `grep_search` — searches codebase for patterns across the project

## Write Tools
- `edit_existing_file` — edits an existing file with specified changes
- `single_find_and_replace` — finds and replaces string(s) in a file
- `create_new_file` — creates a new file with given filepath and contents

---

# Tool Usage Rules

**CRITICAL**: Do NOT attempt tools outside this list. Previously tested non-working tools include variations of partial tool names or malformed tool identifiers that caused errors. Stick to the exact tool names listed above.