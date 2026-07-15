from kodiag import trace

def test_trace(capsys):
    @trace
    def add(a, b):
        return a + b

    result = add(1, 2)
    assert result == 3
    captured = capsys.readouterr()
    assert "add" in captured.out

