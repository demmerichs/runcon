import ast
import sys
from pathlib import Path

path = Path(sys.argv[-1])

aggr_test_data = {"PASSED": 0, "FAILED": 0}
aggr_coverages = []

test_files = path.rglob("*/test_results.txt")
for tfile in test_files:
    with tfile.open("r") as fin:
        data = ast.literal_eval(fin.read())
        assert set(aggr_test_data) == set(data)

        for k in data:
            aggr_test_data[k] += data[k]


cov_files = path.rglob("*/coverage_result.txt")
for cfile in cov_files:
    with cfile.open("r") as fin:
        data = fin.read().strip()
        assert data[-1] == "%"
        aggr_coverages.append(int(data[:-1]))

result_envs = {"TESTS_%s" % k: v for k, v in aggr_test_data.items()}
result_envs["TESTS_COLOR"] = ["success", "critical"][
    aggr_test_data["FAILED"] > 0
]  # type: ignore[assignment]
result_envs["COVERAGE"] = sum(aggr_coverages) // len(aggr_coverages)
print("\n".join("%s=%s" % t for t in result_envs.items()))
