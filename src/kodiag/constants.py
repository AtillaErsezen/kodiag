_FOOTER_TEMPLATE = """\
<style>@media print{#export-bar{display:none !important;}}</style>
<div id="export-bar" style="position:fixed;bottom:0;left:0;right:0;background:#222;padding:10px 20px;display:flex;gap:10px;align-items:center;z-index:999;">
  <button onclick="exportMermaid()" style="padding:8px 16px;background:#4a9eff;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:14px;">Copy Mermaid</button>
  <button onclick="exportDrawio()" style="padding:8px 16px;background:#f76b1c;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:14px;">Download Draw.io</button>
  <button onclick="window.print()" style="padding:8px 16px;background:#28a745;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:14px;">Print / Save PDF</button>
  <span id="export-msg" style="color:#aaa;font-size:13px;"></span>
</div>
<div style="height:60px"></div>
<script>
var CALLS = __CALLS_JSON__;

function exportMermaid() {
  var lines = ["flowchart LR"];
  var styleLines = [];
  for (var i = 0; i < CALLS.length; i++) {
    var c = CALLS[i];
    // Mermaid uses <br> for line breaks (raw newlines break node parsing),
    // and node styling goes on a separate `style nX ...` line, not inline.
    var label = c.name
      + "<br>args: " + JSON.stringify(c.args)
      + "<br>\\u2192 " + JSON.stringify(c.result)
      + "<br>\\u2192 " + JSON.stringify(c.error)
      + "<br>" + c.elapsed + "s";
      lines.push("  n" + i + '["' + label.replace(/"/g, "'") + '"]');
      if (c.error) styleLines.push("  style n" + i + " color:red");
      if (i < CALLS.length - 1) lines.push("  n" + i + " --> n" + (i + 1));
  }
  navigator.clipboard.writeText(lines.concat(styleLines).join("\\n")).then(function() {
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
    var errorStyle = '';
    if (c.error) {
      // Add red style if error exists.
      errorStyle = 'fontColor=red; stroke=#cc3;';
    }
    var label = escapeXml(
      c.name
      + "<br>args: " + JSON.stringify(c.args)
      + "<br>kwargs: " + JSON.stringify(c.kwargs)
      + "<br>→ " + JSON.stringify(c.result)
      + "<br>error: " + JSON.stringify(c.error)
      + "<br>" + c.elapsed + "s"
    );
    cells.push(
      '<mxCell id="' + (i + 2) + '" value="' + label + '"'
      + ' style="rounded=1;whiteSpace=wrap;html=1;' + errorStyle + ';" vertex="1" parent="1">'
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

</script>
</body></html>"""

_ARROW = '<div style="display:inline-block; vertical-align:middle; font-size:1.5em; margin:0 4px;">&#8594;</div>\n'

_JSON_PRIMITIVES = (str, int, float, bool, type(None))
