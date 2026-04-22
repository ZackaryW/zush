# Cron Scheduling

zush includes a built-in scheduler under self cron.

Cron state files are stored in the active zush config directory:

- cron.json for registrations, jobs, and lifejobs
- cron_completion.jsonl for single-day completion tracking
- cron_plugins.json for plugin-managed cron namespace ownership

## Two-Phase Model

1. Register one reusable command payload.
2. Add one or more cron jobs that reference that registration.

Example:

```bash
zush self cron register nightly-task demo.run region=west
zush self cron add nightly-task "0 2 * * *"
zush self cron list
```

Registrations store command path and stored args/kwargs.
Jobs store schedule and registration target.

Trailing tokens after register <name> <command_path> are stored as command input:

- plain tokens become positional args
- key=value tokens become keyword args

## Detached Execution

Detach is configured on registrations, not jobs:

```bash
zush self cron register nightly-task demo.run --detach
zush self cron add nightly-task "0 2 * * *"
```

Any job or lifejob targeting that registration inherits detach mode.

## Lifejobs

Lifejobs are delayed follower jobs attached to a normal cron job.

Example:

```bash
zush self cron register main-task demo.main
zush self cron register cleanup-task demo.cleanup
zush self cron add main-task "*/5 * * * *"
zush self cron add cleanup-task --lifejob cron-1 --delay 30
```

If the target job runs again before the lifejob fires, zush reschedules the lifejob from the latest target run.

Removing a cron job also removes attached lifejobs.

## Single-Day Completion

Use -sdc or --single-day-complete when an entry should run once per day:

```bash
zush self cron add nightly-task "*/5 * * * *" --single-day-complete
zush self cron add cleanup-task --lifejob cron-1 --delay 30 --single-day-complete
```

Use --day-change HH:MM to shift the effective day boundary:

```bash
zush self cron add nightly-task "*/5 * * * *" --single-day-complete --day-change 06:00
```

## Runtime Controls

Run scheduler loop:

```bash
zush self cron start
```

Simulation controls:

```bash
zush self cron start --scale 60 --mocktime 2026-04-17T10:15:00 --dry-run
```

- --scale advances simulated scheduler time relative to wall clock
- --mocktime sets an initial simulated time
- --dry-run evaluates due entries without executing or persisting state

Catch-up behavior is always enabled. If the scheduler was not running and scheduled occurrences were missed, zush replays the missed cron occurrences on the next scheduler tick.

## Plugin Cron Registration

Plugins can declare cron namespaces and entries that are synced on plugin load.

Example in plugin __zush__.py:

```python
from zush.pluginloader.plugin import Plugin


p = Plugin()
p.group("demo").command("run", callback=lambda: None)
p.group("demo").command("cleanup", callback=lambda: None)

p.cron_namespace(
    "ops",
    register_mode="reinforce",   # once | reinforce
    on_conflict="skip",          # skip
    on_remove="unregister",      # keep | unregister
)

p.cron_register("main", "demo.run")
p.cron_register("cleanup_reg", "demo.cleanup")
p.cron_job("hourly", registration="main", schedule="0 * * * *")
p.cron_lifejob("after", registration="cleanup_reg", target_job="hourly", delay_seconds=45)

ZushPlugin = p
```

Notes:

- Names are automatically namespaced, for example ops.main and ops.hourly.
- on_conflict=skip avoids mutating an already-used namespace.
- register_mode=once keeps existing namespace entries; reinforce rewrites that namespace at load.
- on_remove=unregister removes plugin-owned namespaced entries when the plugin is no longer loaded.
