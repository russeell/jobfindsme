"""Create a deliberately crashing update ZIP from an audited, fictional CI build."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def broken_archive(source: Path, destination: Path) -> None:
    changed = False
    with (
        zipfile.ZipFile(source) as original,
        zipfile.ZipFile(destination, "w") as output,
    ):
        for item in original.infolist():
            data = original.read(item)
            if item.filename.endswith("/app/dist-electron/main/index.js"):
                data = b"throw new Error('Fictional update startup failure');\n" + data
                changed = True
            output.writestr(item, data)
    if not changed:
        raise RuntimeError("No packaged entry point to exercise")


if __name__ == "__main__":
    broken_archive(Path(sys.argv[1]), Path(sys.argv[2]))
