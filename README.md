Python debugging library consisting of decorator trace functions to write code flow in diagram. Supports exporting to Pdf, Markdown, Drawio, Mermaid. It records function calls with arguments, return values, and elapsed time, then generates an HTML page with interactive buttons for exporting the trace. You can use it for your python projects by installing with `pip install kodiag`. 

![kodiag](https://raw.githubusercontent.com/AtillaErsezen/kodiag/main/image.png)

## Installation

```bash
pip install kodiag
```

## Usage

kodiag exposes a single decorator, `trace`, imported directly from the package:

```python
from kodiag import trace
```

`trace` must always be called with parentheses before decorating a function — `@trace()`, not bare `@trace` — since it takes an optional `fileName` argument that controls whether calls are logged to the console or recorded into an HTML diagram.

### Console tracing — `@trace()`

Called with no arguments, `trace` prints each call to stdout as it happens, along with the return value and elapsed time. Nothing is written to disk.

```python
from kodiag import trace

@trace()
def add(a, b):
    return a + b

add(1, 2)
```

```
• calling add((1, 2), {}) •
>>> add returned 3 and took 0.0000s <<<
```

### Diagram tracing — `@trace("fileName")`

Pass a file name to record every call into an in-memory flow that is written out as an HTML diagram when the program exits (via `atexit`). The `.html` extension is added automatically if omitted.

```python
from kodiag import trace

@trace("trace_output")
def fetch(user_id):
    ...

@trace("trace_output")
def process(data):
    ...

fetch(42)
process({"a": 1})
# trace_output.html is written on interpreter exit
```

Every function decorated with the same `fileName` appends to that file's flow in call order, so you can trace a whole call chain — across multiple functions — into one diagram.

Each recorded call captures:
- function name
- positional args and keyword args
- the return value
- elapsed time (seconds)

Arguments and return values are serialized for the diagram as follows: JSON-safe primitives (`str`, `int`, `float`, `bool`, `None`) pass through as-is, `tuple`/`list`/`dict` are serialized recursively, and anything else falls back to `repr()`.

The generated HTML page renders each call as a card connected by arrows in call order, with an export bar at the bottom offering:
- **Copy Mermaid** — copies a `flowchart LR` diagram to the clipboard
- **Download Draw.io** — downloads a `.drawio` XML file of the flow
- **Copy Markdown** — copies a Markdown table plus a flow summary
- **Print / Save PDF** — opens the browser print dialog (the export bar is hidden in print output)