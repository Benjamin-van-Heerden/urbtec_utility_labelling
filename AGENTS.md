<MEMCONTENT>
# Working with mem

This project uses **mem** for context management and version control in AI-assisted development.

## First Action

At the start of every session, run:

```bash
mem onboard
```

This gives you everything you need: project info, coding guidelines, active specs, tasks, and recent work logs. The onboard output includes all available commands and project state.

## Expectations

- **Run `mem onboard` first** - Always start sessions this way
- **One task at a time** - Focus on the current task before moving on
- **Stay on the active spec** - Don't mix work across multiple specs
- **Do not create specs unless prompted** - Sometimes we will do work out of spec

## Memories

Memories are short, atomic notes about patterns, conventions, or preferences in the codebase.
They are shown during onboard so every session has access to accumulated project knowledge.

- **When the user asks you to remember something** — create a memory with `mem memory new "title" "content"`
- **When you notice a useful pattern** — suggest creating a memory, but only create it if the user agrees
- Do not use external memory tools (e.g. Claude Code's auto-memory) — use `mem memory` instead

## Notes

- Do not `cd` into the project directory - your shell is already at the project root
- Do not enter plan mode - `mem` handles planning through specs and tasks
- Do not use external task management tools - use `mem task` instead
- When running any mem command *ALWAYS* allow for at least 60 seconds of execution time (the github api can hang)
- `mem log` is not an interactive command and takes no arguments. When prompted to "Create a log" or "Let's log" you should simply run `mem log` and follow the instructions
- When working in the context of a spec (inside a worktree directory), you are ABSOLUTELY NEVER allowed to perform mutating action on the main repo directory in any way shape or form. No git operations, if any merge or rebase fails inside a spec, you must resolve the issues inside that spec!
- Do not add your name or the fact that you co-authored something to any commit messages. Commit messages should be clean and descriptive, no extra information.
- Do not run `mem onboard` arbitrarily - it's output can be very large and typically within the scope of a session it won't provide any additional information. The purpose of the onboard command is just to sync version control and build *initial* context.
- The outputs produced by the mem commands are to be strictly adhered to. Especially in the cases where mem instructs you to stop and give feedback. This is important to keep a human in the loop.
</MEMCONTENT>


