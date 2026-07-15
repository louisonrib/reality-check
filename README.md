For people who move with AI faster than they can double-check it — catch the wrong turn before you build on it, and climb out of the loop when you're already stuck.

Claude Code skills that audit your premises, declare their sources, and break retry loops.

## Installation

### Plugin marketplace

```
/plugin marketplace add louisonrib/lucid
/plugin install lucid@lucid
```

### npx skills

```
npx skills add louisonrib/lucid
```

## Skills

| Skill | Description |
|-------|-------------|
| [im-dumb](skills/im-dumb) | Forces the agent to treat the factual claims in your request as suspects — checking the load-bearing ones against primary sources before building on them — and to explain each technical term and choice as it goes, so you stay able to follow and verify your own project even outside your expertise. |
| [are-we-doing-things-right](skills/are-we-doing-things-right) | Breaks an endless fail-fix-retry loop by running a five-step stop-and-diagnose protocol before trying again — restates the problem, names the earlier decision most likely at fault, and weighs alternatives outside what's already been tried. |
