# Embedding zush

zush can be mounted as a subcommand group inside another Click application.

```python
from pathlib import Path

import click

from zush import create_zush_group
from zush.configparse.config import Config
from zush.core.storage import DirectoryStorage
from zush.mocking.storage import temporary_storage


app = click.Group("myapp")

app.add_command(create_zush_group(), "zush")

storage = DirectoryStorage(Path("/myapp/data/zush"))
config = Config(envs=[Path("/my/envs")], env_prefix=["zush_"])
app.add_command(create_zush_group(config=config, storage=storage), "zush")

app.add_command(
    create_zush_group(
        config=config,
        storage=storage,
        system_commands={
            "doctor": click.Command("doctor", callback=lambda: click.echo("host diagnostics")),
        },
    ),
    "zush",
)

with temporary_storage() as temp_storage:
    app.add_command(create_zush_group(config=config, storage=temp_storage), "temp-zush")
```

Factory signature:

```python
create_zush_group(name="zush", config=None, storage=None, mock_path=None, system_commands=None)
```

## Built-in self Commands

The self group is reserved for zush core commands:

- self map
- self config
- self diagnostics
- self toggle
- self services
- self cron

Plugins may add controlled self commands through Plugin.system_command(...). Built-in names above remain reserved and cannot be overridden.
