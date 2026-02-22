# Design: Full Context AI Personal Assistant

## Overview

This design leverages OpenClaw's existing infrastructure to create a Full Context AI Personal Assistant. The approach is **configuration-first**, maximizing the use of existing capabilities rather than building new systems. The assistant achieves "full context" through:

1. **Structured Workspace Organization** - Files and directories that capture all user context
2. **Memory Architecture** - Multi-layered memory with semantic search
3. **Persona Configuration** - Consistent identity across all interactions
4. **Workflow Skills** - Specialized modes for different collaboration types
5. **Proactive Systems** - Heartbeat and cron for autonomous assistance

---

## Architecture

### System Context

```
                                    User
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
            ▼                         ▼                         ▼
       WhatsApp                  Telegram                   Discord
       Slack                      Signal                    iMessage
       WebChat                   Voice Wake                 Canvas
            │                         │                         │
            └─────────────────────────┼─────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────┐
                    │         OpenClaw Gateway        │
                    │       (Control Plane)           │
                    │   ws://127.0.0.1:18789          │
                    └─────────────────────────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
            ▼                         ▼                         ▼
    ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
    │   Session    │         │   Memory     │         │    Tools     │
    │   Manager    │         │   System     │         │   Runtime    │
    └──────────────┘         └──────────────┘         └──────────────┘
            │                         │                         │
            └─────────────────────────┼─────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────┐
                    │       Agent Workspace           │
                    │   ~/.openclaw/workspace/        │
                    │                                 │
                    │  ├── AGENTS.md                  │
                    │  ├── SOUL.md                    │
                    │  ├── USER.md                    │
                    │  ├── IDENTITY.md                │
                    │  ├── MEMORY.md                  │
                    │  ├── TOOLS.md                   │
                    │  ├── HEARTBEAT.md               │
                    │  ├── memory/                    │
                    │  │   └── YYYY-MM-DD.md          │
                    │  ├── projects/                  │
                    │  │   └── <project-name>/        │
                    │  └── skills/                    │
                    │      └── <skill>/SKILL.md       │
                    └─────────────────────────────────┘
```

### Component Design

#### 1. Workspace Structure (Full Context Storage)

```
~/.openclaw/workspace/
├── AGENTS.md              # Behavioral instructions (customize from template)
├── SOUL.md                # Personality and values
├── IDENTITY.md            # Name, emoji, theme, avatar
├── USER.md                # Comprehensive user profile
├── MEMORY.md              # Curated long-term memories
├── TOOLS.md               # Local tool configurations
├── HEARTBEAT.md           # Proactive check tasks
├── BOOTSTRAP.md           # First-run setup (delete after)
│
├── memory/                # Daily logs
│   ├── YYYY-MM-DD.md      # Daily interaction logs
│   └── heartbeat-state.json
│
├── projects/              # Project contexts
│   ├── project-alpha/
│   │   ├── README.md      # Project overview
│   │   ├── context.md     # Active context and decisions
│   │   ├── tasks.md       # Current tasks
│   │   ├── notes.md       # Working notes
│   │   └── archive/       # Completed work
│   └── project-beta/
│       └── ...
│
├── reference/             # Persistent reference materials
│   ├── people/            # Important contacts
│   │   └── <name>.md
│   ├── processes/         # Standard procedures
│   └── templates/         # Reusable templates
│
├── skills/                # Workspace skills
│   ├── project-manager/
│   │   └── SKILL.md
│   └── learning/
│       └── SKILL.md
│
└── .git/                  # Version control
```

#### 2. Memory Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Memory Layers                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 1: Session Context (Ephemeral)                           │
│  ├── Current conversation messages                               │
│  ├── Active tool results                                         │
│  └── Compacted to Layer 2 when context limit reached            │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 2: Daily Memory (memory/YYYY-MM-DD.md)                   │
│  ├── All significant interactions                                │
│  ├── Decisions made                                              │
│  ├── Tasks completed                                             │
│  └── Consolidated to Layer 3 periodically                        │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 3: Long-term Memory (MEMORY.md)                          │
│  ├── Curated important facts                                     │
│  ├── User preferences                                            │
│  ├── Key decisions and rationale                                 │
│  └── Semantic search enabled                                     │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 4: Project Memory (projects/<name>/context.md)           │
│  ├── Project-specific context                                    │
│  ├── Design decisions                                            │
│  ├── Technical choices                                           │
│  └── Loaded when project is active                               │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 5: Reference Memory (USER.md, reference/*)               │
│  ├── User profile (always loaded)                                │
│  ├── Key contacts                                                │
│  ├── Standard processes                                          │
│  └── Templates                                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 3. Data Flow

```
User Message → Channel → Gateway → Session
                                      │
                                      ▼
                         ┌────────────────────────┐
                         │   Context Assembly     │
                         ├────────────────────────┤
                         │ 1. SOUL.md (who I am)  │
                         │ 2. USER.md (who you are)│
                         │ 3. Today's memory      │
                         │ 4. Yesterday's memory  │
                         │ 5. MEMORY.md (main)    │
                         │ 6. Active project ctx  │
                         └────────────────────────┘
                                      │
                                      ▼
                         ┌────────────────────────┐
                         │   Memory Search        │
                         │   (if needed)          │
                         ├────────────────────────┤
                         │ • Vector similarity    │
                         │ • BM25 keyword match   │
                         │ • Hybrid scoring       │
                         └────────────────────────┘
                                      │
                                      ▼
                         ┌────────────────────────┐
                         │   LLM Processing       │
                         │   (Claude Opus 4.5)    │
                         └────────────────────────┘
                                      │
                                      ▼
                         ┌────────────────────────┐
                         │   Tool Execution       │
                         │   (if needed)          │
                         ├────────────────────────┤
                         │ • File read/write      │
                         │ • Memory search        │
                         │ • Shell commands       │
                         │ • Browser              │
                         │ • Custom skills        │
                         └────────────────────────┘
                                      │
                                      ▼
                         ┌────────────────────────┐
                         │   Memory Update        │
                         ├────────────────────────┤
                         │ • Update daily log     │
                         │ • Update project ctx   │
                         │ • Flag for MEMORY.md   │
                         └────────────────────────┘
                                      │
                                      ▼
                         Response → Channel → User
```

---

## Technical Approach

### Approach 1: Full Custom Build (Rejected)
**Description**: Build all components from scratch

**Pros**:
- Complete control over every aspect
- Optimized for specific use case

**Cons**:
- Enormous development effort
- Duplicates existing OpenClaw functionality
- Maintenance burden
- Slower time to value

### Approach 2: Configuration-First (Chosen)
**Description**: Maximize use of existing OpenClaw capabilities through configuration and workspace organization

**Pros**:
- Rapid implementation
- Leverages battle-tested code
- Automatic updates with OpenClaw
- Focus on value-add customization

**Cons**:
- Some limitations from existing design
- May need future feature requests for gaps

### Chosen Approach

**Configuration-First** is selected because OpenClaw already provides ~80% of required functionality. Implementation focuses on:

1. **Workspace organization** - Structure files for full context
2. **Configuration tuning** - Optimize openclaw.json for personal assistant use
3. **Custom skills** - Add specialized workflows where needed
4. **Memory strategy** - Design capture and consolidation patterns

---

## Implementation Details

### Technology Stack

- **Runtime**: Node.js 22+ (OpenClaw requirement)
- **Framework**: OpenClaw Gateway
- **Language**: Markdown (workspace), JSON (config), TypeScript (skills)
- **LLM**: Anthropic Claude Opus 4.5 (recommended)
- **Embeddings**: OpenAI text-embedding-3-small or Gemini
- **Storage**: Local filesystem + SQLite (memory index)

### Key Components

#### Component 1: Enhanced USER.md
- **Purpose**: Comprehensive user profile
- **Interface**: Markdown file read at session start
- **Content Structure**:

```markdown
# USER.md - About Your Human

## Identity
- **Name**: [Full name]
- **Preferred Name**: [What to call them]
- **Pronouns**: [Pronouns]
- **Timezone**: [TZ]

## Background
### Personal History
- [Key life events, background]

### Professional Background
- **Current Role**: [Title, Company]
- **Skills**: [Key skills]
- **Career History**: [Brief history]

## Preferences
### Communication Style
- [Formal/casual, brevity preferences, etc.]

### Work Patterns
- **Peak Hours**: [When most productive]
- **Meeting Days**: [Preferred meeting days]
- **Focus Time**: [When to not disturb]

### Interests
- [Personal interests, hobbies]

## Current Context
### Active Projects
- [Project 1]: [Brief status]
- [Project 2]: [Brief status]

### Upcoming Events
- [Important dates]

### Current Focus
- [What they're working on now]

## Relationships
### Key Contacts
- [Name]: [Relationship, context]

## Notes
[Additional context]
```

#### Component 2: Project Directory Structure
- **Purpose**: Isolated context for each project
- **Interface**: Directory with standardized files
- **Structure**:

```markdown
projects/<project-name>/
├── README.md       # Overview, goals, stakeholders
├── context.md      # Active working context
├── tasks.md        # Current tasks and status
├── decisions.md    # Key decisions and rationale
├── notes.md        # Working notes
└── archive/        # Completed work
```

#### Component 3: HEARTBEAT.md Configuration
- **Purpose**: Proactive assistance triggers
- **Interface**: Checklist-style configuration
- **Example**:

```markdown
# HEARTBEAT.md - Proactive Checks

## Daily Checks (Morning, ~8am user time)
- [ ] Check calendar for today and tomorrow
- [ ] Summarize unread important emails
- [ ] Review project deadlines this week

## Periodic Checks (Every 4 hours)
- [ ] Check for urgent emails
- [ ] Monitor project blockers

## Weekly Review (Sunday evening)
- [ ] Summarize week's accomplishments
- [ ] Preview next week's schedule
- [ ] Update MEMORY.md with week's learnings

## Quiet Hours
- No proactive messages: 23:00 - 08:00

## State File
memory/heartbeat-state.json
```

### Configuration (openclaw.json)

```json5
{
  agent: {
    model: "anthropic/claude-opus-4-5",
  },
  agents: {
    defaults: {
      workspace: "~/.openclaw/workspace",
      thinkingLevel: "high",
      memorySearch: {
        enabled: true,
        provider: "openai",
        model: "text-embedding-3-small",
        sources: ["memory", "sessions"],
        experimental: { sessionMemory: true },
        query: {
          hybrid: {
            enabled: true,
            vectorWeight: 0.7,
            textWeight: 0.3
          }
        },
        extraPaths: ["projects", "reference"]
      },
      compaction: {
        reserveTokensFloor: 25000,
        memoryFlush: {
          enabled: true,
          softThresholdTokens: 5000
        }
      }
    }
  },
  messages: {
    responsePrefix: "auto"
  },
  heartbeat: {
    enabled: true,
    intervalMinutes: 30
  }
}
```

### API Design

No new APIs needed. Leverage existing OpenClaw tools:

- `memory_search` - Semantic search across all memory
- `memory_get` - Retrieve specific memory content
- `bash` - Shell execution
- `read` / `write` / `edit` - File operations
- `browser_*` - Web browsing
- `sessions_*` - Multi-agent coordination
- `cron_*` - Scheduled tasks

### Data Model

#### User Profile (USER.md)
```typescript
interface UserProfile {
  identity: {
    name: string;
    preferredName: string;
    pronouns?: string;
    timezone: string;
  };
  background: {
    personal: string;
    professional: {
      currentRole: string;
      skills: string[];
      history: string;
    };
  };
  preferences: {
    communicationStyle: string;
    workPatterns: {
      peakHours: string;
      meetingDays: string[];
      focusTime: string;
    };
    interests: string[];
  };
  currentContext: {
    activeProjects: Array<{name: string; status: string}>;
    upcomingEvents: string[];
    currentFocus: string;
  };
  relationships: Array<{name: string; relationship: string; context: string}>;
}
```

#### Project Context (projects/<name>/context.md)
```typescript
interface ProjectContext {
  name: string;
  status: "active" | "paused" | "completed";
  overview: string;
  goals: string[];
  stakeholders: string[];
  currentPhase: string;
  recentDecisions: Array<{date: string; decision: string; rationale: string}>;
  blockers: string[];
  nextSteps: string[];
}
```

---

## Error Handling

- **Memory search failures**: Fall back to keyword search, log error
- **LLM unavailable**: Queue messages, notify user when back online
- **File write failures**: Retry with exponential backoff, alert user
- **Context overflow**: Trigger compaction, preserve critical context

---

## Testing Strategy

- **Unit Tests**: N/A (configuration-focused)
- **Integration Tests**: Verify memory search returns relevant results
- **E2E Tests**: Full conversation flow with context retrieval
- **Manual Testing**: Daily use with feedback capture

---

## Security Considerations

### Data Protection
- All data stays on local filesystem
- Memory index stored locally in SQLite
- No cloud sync without explicit configuration

### Access Control
- OpenClaw pairing system for channel access
- Allowlist configuration for who can interact
- Elevated bash mode requires explicit enablement

### Privacy
- MEMORY.md only loaded in main session (not groups)
- Sensitive data flagged in USER.md with visibility rules
- No data exfiltration per SOUL.md guidelines

---

## Performance Considerations

### Targets
- Memory search: < 2 seconds
- Context assembly: < 1 second
- Total response time: < 5 seconds (excluding LLM thinking)

### Optimizations
- Hybrid search (vector + BM25) for better recall
- Embedding cache to avoid re-computation
- Session memory indexing for recent context
- SQLite with sqlite-vec for fast vector operations

---

## Migration / Rollout Plan

### Phase 1: Basic Setup (Day 1)
1. Configure workspace with enhanced structure
2. Create USER.md with initial profile
3. Set up memory search
4. Configure channels

### Phase 2: Memory Population (Week 1)
1. Import existing notes/context to MEMORY.md
2. Create project directories for active work
3. Configure HEARTBEAT.md

### Phase 3: Tuning (Week 2-4)
1. Refine USER.md based on interactions
2. Adjust memory consolidation patterns
3. Add custom skills as needed

### Phase 4: Steady State (Ongoing)
1. Regular memory maintenance
2. Project context updates
3. Periodic USER.md refresh

---

## References

### Internal Sources
- `[ref-workspace-ts]` /Users/kweng/AI/openclaw/src/agents/workspace.ts
- `[ref-memory-tool]` /Users/kweng/AI/openclaw/src/agents/tools/memory-tool.ts
- `[ref-memory-docs]` /Users/kweng/AI/openclaw/docs/concepts/memory.md
- `[ref-agents-template]` /Users/kweng/AI/openclaw/docs/reference/templates/AGENTS.md
- `[ref-soul-template]` /Users/kweng/AI/openclaw/docs/reference/templates/SOUL.md
- `[ref-user-template]` /Users/kweng/AI/openclaw/docs/reference/templates/USER.md

### External Sources
- `[ref-openclaw-docs]` https://docs.openclaw.ai

---

**Last Updated**: 2026-02-01
