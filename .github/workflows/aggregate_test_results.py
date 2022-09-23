import ast
import sys
from pathlib import Path

path = Path(sys.argv[-1])

rfiles = path.rglob("*/test_results.txt")

aggr_data = {"PASSED": 0, "FAILED": 0}

for rfile in rfiles:
    with rfile.open("r") as fin:
        data = ast.literal_eval(fin.read())
        assert set(aggr_data) == set(data)

        for k in data:
            aggr_data[k] += data[k]

aggr_data["COLOR"] = ["success", "critical"][
    aggr_data["FAILED"] > 0
]  # type: ignore[assignment]
print("\n".join("TESTS_%s=%s" % t for t in aggr_data.items()))
