![kodiag](https://raw.githubusercontent.com/AtillaErsezen/kodiag/main/kodiag_logo.png)

Python debugging library consisting of decorator trace functions to write code flow in diagram. Supports exporting to Pdf, Markdown, Drawio, Mermaid. It records function calls with arguments, return values, and elapsed time, then generates an HTML page with interactive buttons for exporting the trace. You can use it for your python projects by installing with `pip install kodiag`. 

![kodiag](https://raw.githubusercontent.com/AtillaErsezen/kodiag/main/output_image.png)

## Installation

```bash
pip install kodiag
```

### Claude Code plugin

kodiag also ships a Claude Code plugin — a `kodiag` Skill that teaches Claude
how to add `@trace(...)`, run your program, and read the generated trace back
to debug runtime behavior. It's a separate install from the `pip` package
above; the plugin uses the package, it doesn't replace it.

```
/plugin marketplace add https://github.com/AtillaErsezen/kodiag.git
/plugin install kodiag@kodiag
```

## Usage

kodiag exposes a single decorator, `trace`, imported directly from the package:

```python
from kodiag import trace
```

`trace` must always be called with parentheses before decorating a function — `@trace()`, not bare `@trace` — since it takes two optional arguments:

- `file_name` (default `None`): controls whether calls are logged to the console or recorded into a diagram/table on disk.
- `precision` (default `3`): number of decimal places elapsed time is rounded to.

Both tracing modes record/print the exception if the wrapped function raises, then **re-raise** it — the decorated function's own error behavior is unchanged, and the exception is still visible to your caller.

### Console tracing — `@trace()`

Called with no `file_name`, `trace` prints each call to stdout as it happens, along with the return value (or raised exception) and elapsed time. Nothing is written to disk.

```python
from kodiag import trace

@trace()
def add(a, b):
    return a + b

add(1, 2)
```

```
• calling add((1, 2), {}) •
>>> add returned 3 and took 0.000s <<<
```

### File tracing — `@trace("file_name")`

Pass a file name to record every call into an in-memory flow that is written to disk when the program exits normally (via `atexit`). The `.html` suffix is added to the key automatically if omitted, then stripped back off to name the output folder.

```python
from kodiag import trace

@trace("orders")
def fetch(user_id):
    ...

@trace("orders")
def process(data):
    ...

fetch(42)
process({"a": 1})
# written on interpreter exit:
#   kodiag_output/orders/orders.html
#   kodiag_output/orders/orders.md
```

Every function decorated with the same `file_name` appends to that file's flow in call order, so you can trace a whole call chain — across multiple functions — into one report. Output only appears once the process exits normally; a killed process won't flush it.

Each recorded call captures:
- function name
- positional args and keyword args
- the return value (`null`/`None` if the call raised)
- the error, if the call raised (`null` otherwise) — result and error are independent fields, not mutually exclusive, so a call can carry a partial result *and* an error if the function captured a value before raising
- elapsed time in seconds, rounded to `precision` decimal places

Arguments and return values are serialized as follows: JSON-safe primitives (`str`, `int`, `float`, `bool`, `None`) pass through as-is, `tuple`/`list`/`dict` are serialized recursively, and anything else falls back to `repr()`.

Two files are written per `file_name`, both under `kodiag_output/<file_name>/`:

- **`<file_name>.md`** — a Markdown table (`# | Function | Args | Kwargs | Result | Error | Elapsed`) plus a **Flow** line (call names joined by `→`, with a raised call suffixed `*`). This is the cheapest way to inspect a trace programmatically or paste it somewhere.
- **`<file_name>.html`** — the same data rendered as a chain of cards connected by arrows, colored red where a call raised. A fixed bottom bar offers:
  - **Copy Mermaid** — copies a `flowchart LR` diagram to the clipboard
  - **Download Draw.io** — downloads a `.drawio` XML file of the flow
  - **Print / Save PDF** — opens the browser print dialog (the export bar is hidden in print output)

Re-running with the same `file_name` overwrites the previous output — there's no history across runs.