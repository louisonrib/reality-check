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
| [im-dumb](skills/im-dumb) | Checks the factual claims folded into your request against primary sources, stops before building on anything that would make the result wrong, and explains technical terms and choices along the way. |
| [are-we-doing-things-right](skills/are-we-doing-things-right) | Runs a five-step stop-and-diagnose protocol before trying again — restates the problem, names the earlier decision most likely at fault, and weighs alternatives outside what's already been tried. Recognizing when you're stuck enough to run it is a judgment call, not a mechanical guarantee. |
