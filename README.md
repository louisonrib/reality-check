Claude Code skills that audit your premises, declare their sources, and break retry loops.

## Installation

### Plugin marketplace

```
/plugin marketplace add louisonrib/louis-on
/plugin install louis-on@louis-on
```

### npx skills

```
npx skills add louisonrib/louis-on
```

## Skills

| Skill | Description |
|-------|-------------|
| [im-dumb](skills/im-dumb) | Forces the agent to treat the factual claims in your request as suspects — checking the load-bearing ones against primary sources before building on them — and to explain each technical term and choice as it goes, so you stay able to follow and verify your own project even outside your expertise. |
| [are-we-doing-things-right](skills/are-we-doing-things-right) | Breaks an endless fail-fix-retry loop by running a five-step stop-and-diagnose protocol before trying again — restates the problem, names the earlier decision most likely at fault, and weighs alternatives outside what's already been tried. |
