<MEMCONTENT>
# Working with mem

This project uses **mem** for context management and version control in AI-assisted development.

## First Action

At the start of every session, run:

```bash
mem onboard
```

This gives you everything you need: project info, coding guidelines, active specs, tasks, and recent work logs. The onboard output includes all available commands and project state.

## Core Workflow

1. **`mem onboard`** - Start every session here
2. **`mem task complete "title" "detailed completion notes"`** - Mark a task as complete with notes
3. **`mem log`** - Create work log before completing a spec (after that you should git add commit push too)
4. **`mem spec complete <slug> "detailed commit message"`** - Complete a specification

## Expectations

- **Run `mem onboard` first** - Always start sessions this way
- **Complete tasks immediately** - Mark done as soon as finished, not in batches
- **One task at a time** - Focus on the current task before moving on
- **Document before completing** - Run `mem log` before `mem spec complete`
- **Stay on the active spec** - Don't mix work across multiple specs
- **Do not create specs unless prompted** - Sometimes we will do work out of spec

## Notes

- Do not `cd` into the project directory - your shell is already at the project root
- Do not enter plan mode - `mem` handles planning through specs and tasks
- Do not use external task management tools - use `mem task` instead
</MEMCONTENT>
