import time
import functools
import json
import atexit

_call_data = {}  # normalized fileName -> list of call dicts

_JSON_PRIMITIVES = (str, int, float, bool, type(None))

def _safe_serialize(val):
    if isinstance(val, _JSON_PRIMITIVES):
        return val
    if isinstance(val, (tuple, list)):
        return [_safe_serialize(v) for v in val]
    if isinstance(val, dict):
        return {str(k): _safe_serialize(v) for k, v in val.items()}
    return repr(val)

def _card_html(call):
    return (
        f'<div style="display:inline-block; vertical-align:middle; border:2px solid #333; border-radius:4px; '
        f'padding:12px 20px; margin:12px; font-family:monospace; background:#f9f9f9; '
        f'box-shadow:3px 3px 0 #aaa; min-width:180px; text-align:center;">'
        f'<div style="font-weight:bold; font-size:1em; border-bottom:1px solid #ccc; padding-bottom:6px; margin-bottom:6px;">{call["name"]}</div>'
        f'<div style="font-size:0.85em;">args: {call["args"]}<br>kwargs: {call["kwargs"]}</div>'
        f'<div style="margin-top:6px; font-size:0.85em;">&#8594; {call["result"]}</div>'
        f'<div style="margin-top:4px; color:gray; font-size:0.75em;">{call["elapsed"]:.4f}s</div>'
        f'</div>\n'
    )

_ARROW = '<div style="display:inline-block; vertical-align:middle; font-size:1.5em; margin:0 4px;">&#8594;</div>\n'

# __CALLS_JSON__ replaced at write time — avoids f-string/JS brace escaping hell.
_FOOTER_TEMPLATE = """\
<style>@media print{#export-bar{display:none}}</style>
<div id="export-bar" style="position:fixed;bottom:0;left:0;right:0;background:#222;padding:10px 20px;display:flex;gap:10px;align-items:center;z-index:999;">
  <button onclick="exportMermaid()" style="padding:8px 16px;background:#4a9eff;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:14px;">Copy Mermaid</button>
  <button onclick="exportDrawio()" style="padding:8px 16px;background:#f76b1c;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:14px;">Download Draw.io</button>
  <button onclick="exportMarkdown()" style="padding:8px 16px;background:#6c757d;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:14px;">Copy Markdown</button>
  <button onclick="window.print()" style="padding:8px 16px;background:#28a745;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:14px;">Print / Save PDF</button>
  <span id="export-msg" style="color:#aaa;font-size:13px;"></span>
</div>
<div style="height:60px"></div>
<script>
var CALLS = __CALLS_JSON__;

function exportMermaid() {
  var lines = ["flowchart LR"];
  for (var i = 0; i < CALLS.length; i++) {
    var c = CALLS[i];
    var label = c.name
      + "\\nargs: " + JSON.stringify(c.args)
      + "\\n\\u2192 " + JSON.stringify(c.result)
      + "\\n" + c.elapsed.toFixed(4) + "s";
    lines.push("  n" + i + '["' + label.replace(/"/g, "'") + '"]');
    if (i < CALLS.length - 1) lines.push("  n" + i + " --> n" + (i + 1));
  }
  navigator.clipboard.writeText(lines.join("\\n")).then(function() {
    var msg = document.getElementById("export-msg");
    msg.textContent = "Mermaid copied to clipboard!";
    setTimeout(function() { msg.textContent = ""; }, 3000);
  });
}

function escapeXml(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function exportDrawio() {
  var W = 180, H = 100, GAP = 60;
  var cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>'];
  for (var i = 0; i < CALLS.length; i++) {
    var c = CALLS[i];
    var label = escapeXml(
      c.name
      + "<br>args: " + JSON.stringify(c.args)
      + "<br>kwargs: " + JSON.stringify(c.kwargs)
      + "<br>→ " + JSON.stringify(c.result)
      + "<br>" + c.elapsed.toFixed(4) + "s"
    );
    cells.push(
      '<mxCell id="' + (i + 2) + '" value="' + label + '"'
      + ' style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="1">'
      + '<mxGeometry x="' + (i * (W + GAP)) + '" y="0" width="' + W + '" height="' + H + '" as="geometry"/>'
      + '</mxCell>'
    );
    if (i < CALLS.length - 1) {
      cells.push(
        '<mxCell id="' + (CALLS.length + i + 2) + '" edge="1"'
        + ' source="' + (i + 2) + '" target="' + (i + 3) + '" parent="1">'
        + '<mxGeometry relative="1" as="geometry"/></mxCell>'
      );
    }
  }
  var xml = '<?xml version="1.0" encoding="UTF-8"?>\\n'
    + '<mxfile>\\n<diagram>\\n<mxGraphModel>\\n<root>\\n'
    + cells.join("\\n")
    + '\\n</root>\\n</mxGraphModel>\\n</diagram>\\n</mxfile>';
  var blob = new Blob([xml], {type: "application/xml"});
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "trace.drawio";
  a.click();
}

function exportMarkdown() {
  var header = "| # | Function | Args | Kwargs | Result | Elapsed |";
  var sep    = "|---|----------|------|--------|--------|---------|";
  var rows = [header, sep];
  var flow = [];
  for (var i = 0; i < CALLS.length; i++) {
    var c = CALLS[i];
    rows.push(
      "| " + (i + 1)
      + " | `" + c.name + "`"
      + " | `" + JSON.stringify(c.args) + "`"
      + " | `" + JSON.stringify(c.kwargs) + "`"
      + " | `" + JSON.stringify(c.result) + "`"
      + " | " + c.elapsed.toFixed(4) + "s |"
    );
    flow.push("`" + c.name + "`");
  }
  var text = "# Trace Log\\n\\n"
    + rows.join("\\n")
    + "\\n\\n**Flow:** " + flow.join(" → ");
  navigator.clipboard.writeText(text).then(function() {
    var msg = document.getElementById("export-msg");
    msg.textContent = "Markdown copied to clipboard!";
    setTimeout(function() { msg.textContent = ""; }, 3000);
  });
}
</script>
</body></html>"""

def _close_all():
    for fileName, calls in _call_data.items():
        if not calls:
            continue
        footer = _FOOTER_TEMPLATE.replace("__CALLS_JSON__", json.dumps(calls))
        with open(fileName, "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html><html><head><meta charset='utf-8'><title>Trace Log</title></head><body>\n")
            for call in calls:
                f.write(_ARROW)
                f.write(_card_html(call))
            f.write(footer)

atexit.register(_close_all)

def trace(fileName=None):
    def decorator(func):
        fn_name = func.__name__
        if fileName:
            key = fileName if fileName.endswith(".html") else fileName + ".html"
            calls = _call_data.setdefault(key, [])

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                print(f"• calling {fn_name}({args}, {kwargs}) •")
                start = time.perf_counter()
                result = func(*args, **kwargs)
                calls.append({
                    "name": fn_name,
                    "args": _safe_serialize(args),
                    "kwargs": _safe_serialize(kwargs),
                    "result": _safe_serialize(result),
                    "elapsed": time.perf_counter() - start,
                })
                return result
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                print(f"• calling {fn_name}({args}, {kwargs}) •")
                start = time.perf_counter()
                result = func(*args, **kwargs)
                print(f">>> {fn_name} returned {result!r} and took {time.perf_counter() - start:.4f}s <<<")
                return result

        return wrapper
    return decorator
