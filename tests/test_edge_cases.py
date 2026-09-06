"""Edge-case coverage for kodiag.

These tests exercise the trace decorator in both modes (stdout print mode and
file-accumulation mode), the internal helpers, and the generated Markdown/HTML
output. They poke at module-global state (``_call_data``, ``_closed``) and the
current working directory, so every test runs behind the ``clean`` fixture,
which isolates that state and redirects ``kodiag_output/`` into a tmp dir.

Kept in a separate module from ``test_decorators.py`` so the pre-existing test
there is untouched.
"""

import os

import pytest

import kodiag.decorators as dec
from kodiag import trace


@pytest.fixture
def clean(tmp_path, monkeypatch):
    """Isolate global trace state + output directory for a single test.

    Functions decorated in file mode capture their call list at *decoration*
    time via ``setdefault``, so tests must decorate their functions *inside*
    the test body (after this fixture has cleared ``_call_data``).
    """
    saved = dict(dec._call_data)
    dec._call_data.clear()
    dec._closed = False
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    # Restore, and mark closed so the real atexit handler is a no-op and
    # cannot write stray output when the pytest process exits.
    dec._call_data.clear()
    dec._call_data.update(saved)
    dec._closed = True


def _key(name):
    """The normalized _call_data key for a given file_name."""
    return name if name.endswith(".html") else name + ".html"


def _calls(name):
    return dec._call_data[_key(name)]


# --------------------------------------------------------------------------- #
# _safe_serialize
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("val", [1, 1.5, "s", True, False, None])
def test_safe_serialize_primitives_passthrough(val):
    assert dec._safe_serialize(val) is val or dec._safe_serialize(val) == val


def test_safe_serialize_tuple_becomes_list():
    assert dec._safe_serialize((1, 2, 3)) == [1, 2, 3]


def test_safe_serialize_nested_structures():
    src = {"a": [1, (2, 3)], "b": {"c": 4}}
    assert dec._safe_serialize(src) == {"a": [1, [2, 3]], "b": {"c": 4}}


def test_safe_serialize_stringifies_dict_keys():
    assert dec._safe_serialize({1: "a", None: "b"}) == {"1": "a", "None": "b"}


def test_safe_serialize_non_serializable_falls_back_to_repr():
    class Widget:
        def __repr__(self):
            return "<Widget#1>"

    assert dec._safe_serialize(Widget()) == "<Widget#1>"


def test_safe_serialize_set_falls_back_to_repr():
    # sets are not a JSON-primitive nor list/dict -> repr
    out = dec._safe_serialize({1})
    assert isinstance(out, str) and out == repr({1})


# --------------------------------------------------------------------------- #
# _has_error
# --------------------------------------------------------------------------- #

def test_has_error_none_call_is_error():
    assert dec._has_error(None) is True


def test_has_error_with_error_string():
    assert dec._has_error({"error": "boom"}) is True


def test_has_error_without_error():
    assert dec._has_error({"error": None}) is False


# --------------------------------------------------------------------------- #
# Print mode (file_name=None)
# --------------------------------------------------------------------------- #

def test_print_mode_returns_value_and_logs(capsys, clean):
    @trace()
    def add(a, b):
        """Return the sum of two values.
        
        Parameters:
        	a: The first value.
        	b: The second value.
        
        Returns:
        	The sum of `a` and `b`.
        """
        return a + b

    assert add(2, 3) == 5
    out = capsys.readouterr().out
    assert "calling add" in out
    assert "returned 5" in out
    # nothing accumulated in file mode
    assert dec._call_data == {}


def test_print_mode_reraises_and_logs(capsys, clean):
    @trace()
    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        boom()
    out = capsys.readouterr().out
    assert "raised 'nope'" in out


def test_print_mode_bare_trace_without_parens_is_broken():
    # Documents the known-broken bare @trace usage: `add` becomes the inner
    # `decorator`, so calling it with real args is a TypeError. This is the
    # deliberately-unfixed case from test_decorators.py.
    @trace
    def add(a, b):
        """Return the sum of two values.
        
        Parameters:
        	a: The first value.
        	b: The second value.
        
        Returns:
        	The sum of `a` and `b`.
        """
        return a + b

    with pytest.raises(TypeError):
        add(1, 2)


# --------------------------------------------------------------------------- #
# File mode: recording
# --------------------------------------------------------------------------- #

def test_file_mode_records_all_fields(clean):
    @trace("rec.html")
    def add(a, b, label="x"):
        """
        Add two values.
        
        Parameters:
            a: First value.
            b: Second value.
            label: Label accepted without affecting the result.
        
        Returns:
            The sum of a and b.
        """
        return a + b

    assert add(2, 3, label="sum") == 5
    (call,) = _calls("rec.html")
    assert call["name"] == "add"
    assert call["args"] == [2, 3]            # tuple -> list
    assert call["kwargs"] == {"label": "sum"}
    assert call["result"] == 5
    assert call["error"] is None
    assert isinstance(call["elapsed"], float) and call["elapsed"] >= 0


def test_file_mode_appends_html_suffix():
    trace("orders")  # decoration happens below; just show key form
    # normalized key gets .html appended
    assert _key("orders") == "orders.html"
    assert _key("orders.html") == "orders.html"


def test_file_mode_suffix_registered_in_call_data(clean):
    @trace("orders")
    def f():
        return 1

    f()
    assert "orders.html" in dec._call_data
    assert "orders" not in dec._call_data


def test_file_mode_explicit_html_not_doubled(clean):
    @trace("orders.html")
    def f():
        return 1

    f()
    assert "orders.html" in dec._call_data
    assert "orders.html.html" not in dec._call_data


def test_file_mode_reraises_and_records_error(clean):
    @trace("err.html")
    def boom(x):
        """
        Raise a KeyError indicating that the requested value is missing.
        
        Raises:
            KeyError: Always, with the message "missing".
        """
        raise KeyError("missing")

    with pytest.raises(KeyError):
        boom(1)

    (call,) = _calls("err.html")
    assert call["args"] == [1]
    assert call["result"] is None            # never assigned once func raised
    assert call["error"] == "'missing'"      # str(KeyError("missing"))


def test_file_mode_shared_list_preserves_call_order(clean):
    @trace("shared.html")
    def a():
        return "a"

    @trace("shared.html")
    def b():
        raise ValueError("b-fail")

    @trace("shared.html")
    def c():
        return "c"

    a()
    with pytest.raises(ValueError):
        b()
    c()

    names = [x["name"] for x in _calls("shared.html")]
    assert names == ["a", "b", "c"]
    assert [x["error"] is not None for x in _calls("shared.html")] == [False, True, False]


def test_file_mode_serializes_unserializable_args(clean):
    class Widget:
        def __repr__(self):
            return "<W>"

    @trace("obj.html")
    def take(w):
        return w

    take(Widget())
    (call,) = _calls("obj.html")
    assert call["args"] == ["<W>"]           # repr fallback
    assert call["result"] == "<W>"


# --------------------------------------------------------------------------- #
# export_markdown (direct)
# --------------------------------------------------------------------------- #

def _md_call(**over):
    """
    Build a call record for Markdown export tests, applying any supplied field overrides.
    
    Parameters:
    	over: Field values that replace the default call record values.
    
    Returns:
    	dict: A call record containing the function name, arguments, result, error, and elapsed time.
    """
    base = {"name": "f", "args": [], "kwargs": {}, "result": None,
            "error": None, "elapsed": 0.0}
    base.update(over)
    return base


def test_export_markdown_writes_file_and_returns_dir(clean):
    out = dec.export_markdown("report.html", [_md_call(name="f", result=1)])
    assert out == os.path.join("kodiag_output", "report")
    md_path = os.path.join(out, "report.md")
    assert os.path.exists(md_path)
    text = open(md_path, encoding="utf-8").read()
    assert "# Trace Log" in text
    assert "**Flow:**" in text


def test_export_markdown_strips_html_suffix_for_paths(clean):
    out = dec.export_markdown("thing.html", [_md_call()])
    assert out.endswith(os.path.join("kodiag_output", "thing"))
    assert os.path.exists(os.path.join(out, "thing.md"))


def test_export_markdown_flow_marks_errors(clean):
    calls = [_md_call(name="ok"), _md_call(name="bad", error="boom")]
    out = dec.export_markdown("flow.html", calls)
    text = open(os.path.join(out, "flow.md"), encoding="utf-8").read()
    flow = text.splitlines()[-1]
    assert "`ok`" in flow
    assert "`bad*`" in flow


def test_export_markdown_escapes_pipe_in_values(clean):
    calls = [_md_call(name="p", result="a|b|c", error="e | pipe")]
    out = dec.export_markdown("pipe.html", calls)
    text = open(os.path.join(out, "pipe.md"), encoding="utf-8").read()
    assert "a\\|b\\|c" in text
    assert "e \\| pipe" in text
    # every data row keeps exactly 7 columns (8 unescaped separators)
    for line in text.splitlines():
        if line.startswith("| `"):
            assert line.replace("\\|", "").count("|") == 8


def test_export_markdown_missing_key_returns_none(capsys, clean):
    # A call object missing the required 'name' key hits the KeyError branch.
    bad = {"args": [], "kwargs": {}, "result": None, "error": None, "elapsed": 0.0}
    assert dec.export_markdown("bad.html", [bad]) is None
    assert "Missing required data field" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# _card_html
# --------------------------------------------------------------------------- #

def test_card_html_escapes_dangerous_chars(clean):
    call = _md_call(name="<script>alert(1)</script>", args='"q" & <b>',
                    result="<i>", error=None)
    html = dec._card_html(call)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html


def test_card_html_color_reflects_error(clean):
    ok = dec._card_html(_md_call(error=None))
    bad = dec._card_html(_md_call(error="boom"))
    assert "color:gray" in ok
    assert "color:red" in bad


# --------------------------------------------------------------------------- #
# _close_all: full output generation
# --------------------------------------------------------------------------- #

def test_close_all_writes_md_and_html(clean):
    @trace("full.html")
    def f(x):
        return x * 2

    f(21)
    dec._close_all()

    base = os.path.join("kodiag_output", "full")
    assert os.path.exists(os.path.join(base, "full.md"))
    assert os.path.exists(os.path.join(base, "full.html"))

    html = open(os.path.join(base, "full.html"), encoding="utf-8").read()
    assert html.startswith("<!DOCTYPE html>")
    assert "</body></html>" in html


def test_close_all_shields_script_tag_in_json(clean):
    @trace("xss.html")
    def f(s):
        return s

    f("</script><img>")
    dec._close_all()

    html = open(os.path.join("kodiag_output", "xss", "xss.html"),
               encoding="utf-8").read()
    # embedded JSON must not carry a raw closing tag from traced data
    assert "<\\/script><img>" in html


def test_close_all_html_escapes_card_fields(clean):
    @trace("esc.html")
    def f(s):
        return s

    f("<b>bold</b>")
    dec._close_all()

    html = open(os.path.join("kodiag_output", "esc", "esc.html"),
               encoding="utf-8").read()
    assert "&lt;b&gt;bold&lt;/b&gt;" in html


def test_close_all_mermaid_is_valid(clean):
    @trace("mer.html")
    def ok():
        return 1

    @trace("mer.html")
    def bad():
        raise ValueError("x")

    ok()
    with pytest.raises(ValueError):
        bad()
    dec._close_all()

    html = open(os.path.join("kodiag_output", "mer", "mer.html"),
               encoding="utf-8").read()
    mermaid = html.split("function exportMermaid")[1].split("function escapeXml")[0]
    assert '" style="' not in mermaid          # no invalid inline node style
    assert "<br>args:" in mermaid              # line breaks via <br>
    assert "style n" in mermaid                # error styled on its own line


def test_close_all_skips_empty_call_lists(clean):
    @trace("never.html")
    def f():
        return 1
    # f is never called -> key exists with empty list

    dec._close_all()
    assert not os.path.exists(os.path.join("kodiag_output", "never"))


def test_close_all_is_idempotent(clean):
    @trace("once.html")
    def f():
        return 1

    f()
    dec._close_all()

    md_path = os.path.join("kodiag_output", "once", "once.md")
    assert os.path.exists(md_path)

    os.remove(md_path)
    dec._close_all()                           # second call must be a no-op
    assert not os.path.exists(md_path)
