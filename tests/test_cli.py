import json

import numpy as np
import pandas as pd

from bunu.cli import main


def test_cli_check_exit_codes(tmp_path, capsys):
    good, bad = tmp_path / "good.csv", tmp_path / "bad.csv"
    pd.DataFrame({"a": range(50)}).to_csv(good, index=False)
    pd.DataFrame({"a": [1.0, np.inf] * 25}).to_csv(bad, index=False)
    bad2 = tmp_path / "bad2.csv"
    pd.DataFrame({"a": [str(i) for i in range(59)] + ["x"], "b": 1, "id": range(60)}).to_csv(bad2, index=False)
    assert main(["check", str(good), "--fail-on", "high"]) == 0
    assert main(["check", str(bad2), "--fail-on", "medium"]) == 1
    assert main(["check", str(bad2), "--fail-on", "high"]) == 0
    assert main(["check", str(tmp_path / "missing.csv")]) == 2


def test_cli_json_snapshot_compare(tmp_path, capsys):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    pd.DataFrame({"x": range(100)}).to_csv(a, index=False)
    pd.DataFrame({"x": range(100)}).assign(y=1).to_csv(b, index=False)
    snap = tmp_path / "a.json"
    assert main(["snapshot", str(a), "-o", str(snap)]) == 0
    capsys.readouterr()
    assert main(["compare", str(snap), str(b), "--json", "--fail-on", "medium"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["columns_added"] == ["y"]
    assert main(["explain", str(a)]) == 0
