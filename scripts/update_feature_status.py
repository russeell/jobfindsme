from __future__ import annotations

import json
import sys

from scripts.feature_harness import (
    FEATURES_PATH,
    HarnessError,
    evidence_passed,
    find_feature,
    load_spec,
)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python3 -m scripts.update_feature_status <FEATURE_ID> <STATUS>")
        return 2

    feature_id, status = sys.argv[1:]
    spec = load_spec()
    if status not in spec["status_values"]:
        print(f"invalid status: {status}")
        return 2

    feature = find_feature(spec, feature_id)
    if status == "done" and not evidence_passed(feature):
        raise HarnessError(f"{feature_id} has no passing evidence")

    feature["status"] = status
    FEATURES_PATH.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{feature_id} -> {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
