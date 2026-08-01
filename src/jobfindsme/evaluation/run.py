"""Compatibility entry: ``python -m jobfindsme.evaluation.run``.

Real CLI lives in jobfindsme.evaluation.cli.
"""

from jobfindsme.evaluation.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
