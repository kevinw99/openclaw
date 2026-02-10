# Project Guidelines

## Core Principles

### Critical Thinking & Partnership

- **Validate requests first** - Check for mistakes or wrong assumptions before proceeding
- **Be critical and faithful to the truth** - Don't assume what is asked is always valid
- **Act as a partner, not a yes-man** - Challenge assumptions when needed and provide honest feedback
- **Question unclear or potentially incorrect requests** - Help avoid mistakes

### Comprehensive Problem-Solving

When working on problems or requests:

1. **Understand the full context** - Ask clarifying questions if unclear
2. **Identify root causes** - Don't just fix symptoms
3. **Find related issues** - Look for similar patterns elsewhere
4. **Propose improvements** - Suggest better approaches when appropriate
5. **Document thoroughly** - Make work clear and reproducible

## Task Management

- **Create a task list** for each project or significant work
- **Mark tasks as done** when completed
- **Keep track of progress**
- **Update status.md** when working on specs

## Spec Creation Workflow

For new initiatives, problems, or research:

1. **Auto-generate** requirements.md, design.md, and tasks.md
2. **Proceed directly** to implementation after creating complete spec
3. **Only ask clarification** if problem description is unclear or missing critical information
4. **Create comprehensive specs** covering all aspects systematically

### Spec Directory Naming Convention

All spec directories must be numbered sequentially:

- Format: `##_descriptive-name` (e.g., `01_user-authentication`, `02_api-refactor`)
- Use two-digit zero-padded numbers (01, 02, ... 10, 11, etc.)
- Separate number from name with underscore
- Use kebab-case for descriptive names
- Check existing specs to determine the next available number
- Location: `specs/`

### Spec Directory Structure

Each spec directory should contain:

```
specs/##_spec-name/
├── README.md         # Overview, quick links, completion status
├── requirements.md   # What needs to be done
├── design.md         # How it will be done
├── tasks.md          # Breakdown of work items
└── status.md         # Implementation progress (add when work begins)
```

**status.md** tracks:
- Overall status (Planning/In Progress/Complete/Blocked)
- Completed work with dates
- Remaining work items
- Session notes for context continuity
- How to test/verify locally

**When to update status.md:**
- When starting implementation
- After completing significant milestones
- Before switching to a different task/spec
- When pausing work for later resumption

## Documentation Standards

### Source Attribution & Citations

All documentation with factual information should follow proper citation practices:

1. **Add a References section** to documents with factual claims
   - Location: Bottom of the file
   - Format: Structured list with source type and link

2. **Quote sources precisely**:
   - When citing specific data: Include direct reference in text
   - Link quotes to References section with `[citation-key]` notation
   - Example: `The performance target is 95%+ [ref-benchmark-2025]`

3. **Reference Section Format**:
   ```markdown
   ## References

   ### Internal Sources
   - `[ref-architecture]` Architecture Documentation v2.0
   - `[ref-design-doc]` Design Document for Feature X

   ### External Sources
   - `[ref-docs]` Official Documentation
   - `[ref-best-practices]` Best Practices Guide
   ```

4. **Data Source Metadata** (for research documents):
   - `**Information Reliability**: High | Medium | Low`
   - `**Collection Method**: [How data was gathered]`
   - `**Last Updated**: [Date]`
   - `**Data Gaps**: [What's still needed]`

## Important Reminders

- **Be thorough** - Don't skip steps or important considerations
- **Document everything** - Future work depends on clear documentation
- **Keep it organized** - Maintain consistent naming and structure
- **Track progress** - Use task management to manage work items
- **Be proactive** - Suggest improvements and catch issues early
- **Source all claims** - Factual statements should have traceable sources

## Workflow for New Work

When starting new work:

1. **Clarify requirements** - Ask questions if anything is unclear
2. **Create spec** - Write requirements.md, design.md, tasks.md
3. **Plan tasks** - List work items
4. **Execute systematically** - Complete one task at a time
5. **Document progress** - Update status.md regularly
6. **Review and refine** - Verify everything works as intended

## Use /log Command

At the end of each session, run `/log` to update the work log with:
- User instructions from the session
- Work completed
- Git commits
- Important decisions and notes
