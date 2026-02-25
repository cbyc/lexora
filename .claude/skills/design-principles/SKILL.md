---
name: design-principles
description: >
  Apply when the user asks to plan, design, architect, or change code that affects
  software structure or design. Enforces XP (Extreme Programming), Clean Code, and
  Clean Architecture principles. Warn and ask for confirmation if a proposed change
  would degrade the codebase against these principles.
---

# XP, Clean Code & Clean Architecture Principles

When planning, designing, or making changes that affect software structure, always apply
the principles below. They are sensible defaults — not optional suggestions.

---

## 1. Extreme Programming (XP) Principles

- **Simple design**: Build the simplest thing that could possibly work. Resist the urge
  to add flexibility, configuration, or abstraction in advance of a concrete need.
  (YAGNI — You Aren't Gonna Need It)
- **Test first**: Design is driven by tests. A feature isn't designed until there is a
  failing test that specifies its behaviour.
- **Refactor mercilessly**: Continuously improve the design. Technical debt is addressed
  incrementally, not deferred. Refactoring is a normal part of every change, not a
  separate task.
- **Small, safe steps**: Changes are small and independently deployable. Avoid big-bang
  rewrites. Each step must leave the system in a working state.
- **Collective ownership**: No module belongs to one person. Code is written to be read
  and changed by anyone on the team.
- **Continuous integration mindset**: Every change integrates cleanly with the existing
  codebase. Do not leave the system in a broken or half-finished state.

---

## 2. Clean Code Principles

- **Meaningful names**: Names reveal intent. Variables, functions, and classes must say
  *what* they are, not *how* they are implemented.
- **Small functions, single responsibility**: A function does one thing, at one level of
  abstraction. If a function needs a comment to explain what a section does, that section
  is a function.
- **No magic numbers or strings**: All constants are named.
- **Avoid deep nesting**: Prefer early returns and guard clauses over nested conditionals.
- **No dead code**: Remove unused code, commented-out code, and speculative TODOs.
- **Don't repeat yourself (DRY)**: Every piece of knowledge has a single, authoritative
  representation. Duplication is a design smell, not a shortcut.
- **Keep it readable**: Code is read far more often than it is written. Optimise for
  the reader, not the writer.

---

## 3. Clean Architecture Principles

- **Dependency rule**: Source code dependencies point inward. The domain and application
  layers know nothing about frameworks, databases, UI, or external services.
- **Ports and adapters**: Business logic depends only on abstractions (protocols/interfaces).
  Concrete implementations (HTTP clients, vector DBs, embedding models) are injected at
  the boundary.
- **Use-case driven**: Application logic lives in use-case / service classes, not in route handlers or infrastructure adapters.
- **Screaming architecture**: The directory structure should communicate what the system
  *does*, not what framework it uses.
- **Testable by default**: The architecture must allow core logic to be tested without
  spinning up any external service. Fakes and in-memory implementations are first-class
  design artefacts.

---

## How to Apply These Principles

### When planning or designing
1. Evaluate every proposed structure against the principles above.
2. Prefer the simpler option. If two designs both satisfy the requirement, choose the one
   with fewer abstractions and less indirection.
3. Name things precisely. Draft names before writing code.
4. Identify the test first, then let it drive the shape of the implementation.

### When reviewing a request for code changes
1. Check whether the change respects the dependency rule and the existing port/adapter
   boundary.
2. Check whether it introduces unnecessary complexity, premature abstraction, or
   duplication.
3. Check whether it can be covered by a unit test without external dependencies.

### If a request would degrade the codebase

**Stop and explain before writing any code.**

Tell the user:
- Which principle(s) the change would violate.
- Why it matters in concrete terms (what future pain it creates).
- What a compliant alternative would look like.
- Then ask: *"Do you want to proceed with the original approach, or use the alternative?"*

Do not silently implement a degrading change. Do not implement it first and warn
afterwards. Always get explicit confirmation before writing code that violates these
principles.
