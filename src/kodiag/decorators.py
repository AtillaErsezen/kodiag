import atexit
import functools
import html
import json
import os
import time

from .constants import _ARROW, _FOOTER_TEMPLATE, _JSON_PRIMITIVES

_call_data = {}  # normalized file_name -> list of call dicts


def export_markdown(filename: str, calls: list):
    """
    Create a Markdown trace table and save it under the ``kodiag_output`` directory.
    
    Parameters:
        filename (str): Output name, optionally ending in ``.html``.
        calls (list): Call records containing function names, arguments, results,
            errors, and elapsed times.
    
    Returns:
        str: Path to the output directory when the file is written successfully.
        None: If a call record is missing required data or file output fails.
    """

    # --- Markdown Header Setup ---
    header = "| # | Function | Args | Kwargs | Result | Error | Elapsed |"
    sep = "|---|----------|------|--------|--------|-------|---------|"
    rows = []
    flow = []

    for i, c in enumerate(calls):
        # 1. Construct the table row content (data elements)
        try:
            row_content = [
                str(i + 1),
                c['name'],
                json.dumps(c.get('args', None)),
                json.dumps(c.get('kwargs', {})),
                json.dumps(c.get('result', None)),
                json.dumps(c.get('error')), # None -> null when key missing/unset
                f"{c['elapsed']}s"
            ]
        except KeyError as e:
            print(f"Warning: Missing required data field {e} in a call object.")
            return None

        # Escape '|' so a traced value doesn't break the table columns,
        # then wrap each piece of content in markdown backticks (`).
        escaped = [item.replace("|", "\\|") for item in row_content]
        formatted_row = " | ".join(f"`{item}`" for item in escaped)
        rows.append(f"| {formatted_row} |")

        # 2. Build the flow string indicator
        if c.get('error'):
            flow.append(f'`{c["name"]}*`') # '*' indicates error path
        else:
            flow.append(f"`{c['name']}`")

    # --- Assemble Final Markdown Text ---
    text = "# Trace Log\n\n"
    text += "\n".join([header, sep] + rows)
    text += "\n\n**Flow:** " + " → ".join(flow)

    # --- File Saving Logic ---
    name_stripped = filename.removesuffix(".html")
    output_dir = os.path.join("kodiag_output", name_stripped)
    file_path = os.path.join(output_dir, f"{name_stripped}.md")

    try:
        # 1. Ensure the output folder exists
        os.makedirs(output_dir, exist_ok=True)

        # 2. Write the content to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"SUCCESS! Markdown saved to: {os.path.abspath(file_path)}")
        return output_dir #output path returned for easier use inside html print
    except Exception as e:
        print(f"FATAL ERROR: Could not save file '{file_path}'. Reason: {e}")
        return None

def _safe_serialize(val):
    """
    Convert a value into a JSON-compatible representation.
    
    Parameters:
    	val: The value to serialize.
    
    Returns:
    	The original JSON-compatible value, a recursively serialized sequence or dictionary, or a string representation for unsupported values.
    """
    if isinstance(val, _JSON_PRIMITIVES):
        return val
    if isinstance(val, (tuple, list)):
        return [_safe_serialize(v) for v in val]
    if isinstance(val, dict):
        return {str(k): _safe_serialize(v) for k, v in val.items()}
    return repr(val)

#TODO remove indexes from md output table? can be driven from flow output
def _has_error(call):
    """Determine whether a traced call represents an error.
    
    Parameters:
        call (dict or None): The recorded call data to inspect.
    
    Returns:
        bool: `true` if the call is missing or contains an error, `false` otherwise.
    """
    return call is None or call["error"] is not None

def _card_html(call):
    """Generate an HTML card containing a traced call's name, arguments, result, error, and elapsed time."""
    color = "red" if _has_error(call) else "gray"
    name = html.escape(str(call["name"]))
    args = html.escape(str(call["args"]))
    kwargs = html.escape(str(call["kwargs"]))
    result = html.escape(str(call["result"]))
    error = html.escape(str(call["error"]))
    return (
        f'<div style="display:inline-block; vertical-align:middle; border:2px solid #333; border-radius:4px; '
        f'padding:12px 20px; margin:12px; font-family:monospace; background:#f9f9f9; '
        f'box-shadow:3px 3px 0 #aaa; min-width:180px; text-align:center;">'
        f'<div style="font-weight:bold; font-size:1em; border-bottom:1px solid #ccc; padding-bottom:6px; margin-bottom:6px;">{name}</div>'
        f'<div style="font-size:0.85em;">args: {args}<br>kwargs: {kwargs}</div>'
        f'<div style="margin-top:6px; font-size:0.85em;">&#8594; {result}</div>'
        f'<div style="margin-top:6px; font-size:0.85em; color:{color}">&#8594; error: {error}</div>'
        f'<div style="margin-top:4px; color:gray; font-size:0.75em;">{call["elapsed"]}s</div>'
        f'</div>\n'
    )

_closed = False
def _close_all(): #idempotency as a safety net
    """
    Finalize all recorded traces by writing their Markdown and HTML output files.
    
    The operation runs at most once and reports file-export failures without raising them.
    """
    global _closed
    if _closed:
        return
    _closed = True
    for file_name, calls in _call_data.items():
        if not calls:
            continue
        output_dir = export_markdown(file_name, calls)
        if output_dir is None:
            continue # export_markdown already printed the failure reason

        html_path = os.path.join(output_dir, file_name)
        try:
            # JSON embedded in a <script> block must not contain a literal "</" or a
            # traced value like "</script>" would prematurely close the script tag.
            calls_json = json.dumps(calls).replace("</", "<\\/")
            footer = _FOOTER_TEMPLATE.replace("__CALLS_JSON__", calls_json)
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write("<!DOCTYPE html><html><head><meta charset='utf-8'><title>Trace Log</title></head><body>\n")
                for call in calls:
                    f.write(_ARROW)
                    f.write(_card_html(call))
                f.write(footer)
        except Exception as e:
            print(f"FATAL ERROR: Could not save file '{html_path}'. Reason: {e}")

atexit.register(_close_all)

def trace(file_name=None, precision=3):
    """
    Decorate a function to trace its calls to a file or the console.
    
    Parameters:
        file_name (str | None): Output filename for recorded call data; when omitted, trace information is printed.
        precision (int): Number of decimal places used for elapsed-time values.
    
    Returns:
        A decorator that records or prints function calls, results, elapsed times, and errors.
    
    Raises:
        Exception: Re-raises any exception raised by the decorated function.
    """
    def decorator(func):
        fn_name = func.__name__
        if file_name:
            key = file_name if file_name.endswith(".html") else file_name + ".html"
            calls = _call_data.setdefault(key, [])

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                result = None
                try:
                    start = time.perf_counter()
                    result = func(*args, **kwargs)
                    elapsed = time.perf_counter() - start
                except Exception as e:
                    elapsed = time.perf_counter() - start
                    calls.append({
                        "name": fn_name,
                        "args": _safe_serialize(args),
                        "kwargs": _safe_serialize(kwargs),
                        "result": _safe_serialize(result),
                        "elapsed": round(elapsed, precision),
                        "error": str(e)
                    })
                    raise

                calls.append({
                    "name": fn_name,
                    "args": _safe_serialize(args),
                    "kwargs": _safe_serialize(kwargs),
                    "result": _safe_serialize(result),
                    "elapsed": round(elapsed, precision),
                    "error": None
                })
                return result
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                print(f"• calling {fn_name}({args}, {kwargs}) •")
                result = None
                try:
                    start = time.perf_counter()
                    result = func(*args, **kwargs)
                    elapsed = time.perf_counter() - start
                except Exception as e:
                    elapsed = time.perf_counter() - start
                    print(f">>> {fn_name} raised '{e}' and took {elapsed:.{precision}f}s <<<")
                    raise
                print(f">>> {fn_name} returned {result!r} and took {elapsed:.{precision}f}s <<<")
                return result

        return wrapper
    return decorator
