from __future__ import annotations

import sys

from scripts.feature_harness import (
    HarnessError,
    changed_paths,
    check_allowed_paths,
    check_project_research_gate,
    find_feature,
    load_spec,
    run_checks,
    write_evidence,
)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python3 -m scripts.check_feature <FEATURE_ID>")
        return 2

    spec = load_spec()
    feature = find_feature(spec, sys.argv[1])
    paths = changed_paths()
    try:
        check_project_research_gate(spec, feature)
        check_allowed_paths(feature, paths)
    except HarnessError as error:
        print(error)
        return 1

    results = run_checks(feature)
    evidence = write_evidence(feature, paths=paths, results=results)
    for result in results:
        status = "PASS" if result.returncode == 0 else "FAIL"
        print(f"{status}: {' '.join(result.command)}")
    print(evidence)
    return 0 if results and all(item.returncode == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
