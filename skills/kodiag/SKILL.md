---
name: kodiag
description: Trace the real runtime call flow, arguments, return values, errors, and timing of a Python program, then read the generated trace to understand what actually happened. Use when debugging a Python program's runtime behavior — which functions ran, in what order, with what inputs/outputs, which raised, and where time went — rather than reasoning about the source statically. Triggers on requests like "why is this returning the wrong value", "trace the call flow", "which function is failing at runtime", "where is the time going".
---

# kodiag — runtime call-flow tracing for Python

`kodiag` is a decorator-based tracer. You add `@trace("<name>.html")` to the
functions you care about, run the program to normal exit, and kodiag writes a
compact Markdown trace you read to see the *actual* call order, arguments,
return values, exceptions, and per-call timing.

Reach for this when static reading of the source isn't enough — when you need
to know what really executed, with what data, in what order.

## The loop

1. **Install** (once per environment):
   ```
   pip install kodiag
   ```

2. **Decorate** the suspect functions. Give every function you want in the
   same trace the **same `file_name`** — they share one call list in call
   order, which is how a multi-function flow becomes one trace.
   ```python
   from kodiag import trace

   @trace("debug.html", precision=3)
   def fetch(...): ...

   @trace("debug.html")
   def process(...): ...
   ```
   - `file_name` (str): base name for the trace. `.html` is appended if absent
     (`"debug"` and `"debug.html"` are the same trace).
   - `precision` (int, default `3`): decimals `elapsed` is rounded to.
   - `@trace()` with **no `file_name`** only prints to stdout — no files. Use a
     `file_name` when you want to read the trace back.
   - **`@trace` without parentheses is wrong** — it passes the function as
     `file_name` and breaks the call. Always call it: `@trace(...)`.

3. **Run the program to a normal exit.** Output is flushed at interpreter exit
   via `atexit`, not per call — if the process is killed or hangs, nothing is
   written. A decorated function that raises **re-raises** after recording, so
   the program's own error behavior is unchanged; the raise is captured in the
   trace.

4. **Read the trace.** Look in
   `kodiag_output/<name>/<name>.md` first — it's the cheap, token-efficient
   read. Paths are relative to the process's working directory at exit. Only
   open the sibling `.html` (a visual card diagram) if a human needs the
   picture; don't read it for programmatic inspection.

5. **Clean up.** Remove the `@trace` decorators (and the `from kodiag import
   trace` import if now unused) once you've gotten what you need — don't leave
   tracing in the user's source. `kodiag_output/` is a generated artifact
   directory; don't edit or commit it.

## Reading the Markdown trace (`kodiag_output/<name>/<name>.md`)

Fixed schema, one row per recorded call in call order:

```
# Trace Log

| # | Function | Args | Kwargs | Result | Error | Elapsed |
|---|----------|------|--------|--------|-------|---------|
| 1 | `fetch`   | `[42]`         | `{}` | `{"id": 42}` | `null`               | `0.012s` |
| 2 | `process` | `[{"id": 42}]` | `{}` | `null`       | `"KeyError: 'name'"` | `0.001s` |

**Flow:** `fetch` → `process*`
```

- `#` — 1-indexed call order for this `file_name`.
- `Function` — the decorated function's `__name__`.
- `Args` / `Kwargs` — JSON-serialized inputs as received.
- `Result` — JSON return value. `null` means the call returned `None` **or**
  it raised — check `Error` (and the `*` in the Flow line) to tell them apart.
- `Error` — JSON `str(exception)` if it raised, else `null`. The original
  exception was re-raised to the caller.
- `Elapsed` — seconds, rounded to `precision`, suffixed `s`.
- **Flow** line — call order joined by arrows; a call that raised is suffixed
  with `*` (e.g. `` `process*` ``).

Values that aren't JSON-serializable are recorded as their `repr(...)`.

> **Security and privacy:** Captured `Args`, `Kwargs`, `Result`, `Error`, and
> `repr(...)` output may contain credentials, tokens, or personal data. Avoid
> tracing sensitive code, and secure or delete `kodiag_output/` after reviewing
> generated traces.

## What to surface

Don't dump the whole table. Report:
1. The full **Flow** line first — it's the one-glance shape of the run.
2. Then the highest-signal rows: anything with a non-null `Error`, and the
   rows with the largest `Elapsed`.

## Gotchas

- No output dir? The program hasn't exited normally yet, no function with that
  `file_name` was ever called, or a different name was used than expected —
  check the call sites (`grep -rn '@trace(' `) to confirm the name.
- Re-running the same program with the same `file_name` **overwrites** the
  previous `kodiag_output/<name>/` — there's no history.
