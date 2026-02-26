Run ruff format and ruff check before committing. Only commit if linting passes; otherwise report the issues and stop.

## Steps

1. Run `uv run ruff format .` to auto-format all files.
2. Run `uv run ruff check .` to lint.
   - If there are lint errors, print them and **stop** — do not commit.
3. Run `git diff HEAD` to read the full diff of every change since the last commit, including untracked new files (`git status --short` to spot them, then read each with the Read tool). Understand *what* changed and *why* — this covers both Claude's edits and any manual changes made outside this conversation.
4. Draft a commit message using **Conventional Commits** style:
   - Format: `<type>(<optional scope>): <short description>`
   - Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `style`, `perf`
   - Keep the subject line under 72 characters.
   - Do **not** list filenames in the message.
   - Use the imperative mood ("add", "fix", "update", not "added" or "fixes").
5. Stage all changes: `git add -A`
6. Commit with the drafted message.
7. Show the resulting `git log --oneline -1` to confirm the commit.
