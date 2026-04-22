# Runtime Globals and Services

## Runtime Globals

zush exposes a process-local runtime object store at zush.core.runtime.g.

Use it to share live objects during one zush process, for example:

- schedulers
- clients
- registries
- in-memory service handles

Helper-based plugins can register objects:

```python
from zush.pluginloader.plugin import Plugin


p = Plugin()
p.provide("scheduler", object())
ZushPlugin = p
```

For lazy creation, use provide_factory(...):

```python
from zush.pluginloader.plugin import Plugin


def build_scheduler():
    return object()


p = Plugin()
p.provide_factory("scheduler", build_scheduler)
ZushPlugin = p
```

Objects in zush.core.runtime.g are not persisted to disk.

## Service-Aware Providers

Factories may accept plugin runtime as the first argument.

When a provider depends on a service, declare that dependency directly:

```python
from zush.pluginloader.plugin import Plugin


def build_client(runtime):
    return MyClient(runtime)


def close_client(client):
    client.close()


p = Plugin()
p.provide_factory(
    "client",
    build_client,
    service="web",
    recreate_on_restart=True,
    teardown=close_client,
)
ZushPlugin = p
```

With this setup:

- zush ensures web is ready before first provider creation
- the provider is rebuilt after web restarts or stops
- the previous provider instance is passed to teardown before replacement

## Detached Services

Plugins can declare detached subprocess-backed services:

```python
import sys
from zush.pluginloader.plugin import Plugin


p = Plugin()
p.service(
    "web",
    [sys.executable, "-m", "flask", "run"],
    auto_restart=True,
)

ZushPlugin = p
```

Built-in control surface:

```bash
zush self services web --start
zush self services web --status
zush self services web --restart
zush self services web --stop
```

Services may supply a custom control interface implementing start(runtime), stop(runtime), restart(runtime), and status(runtime). zush uses these first and falls back to OS termination when terminate_fallback is true.

Health checks can return:

- True or False
- (True, "message") or (False, "message")

A full example is available in playground/README.md under zush_provider_service_demo.
