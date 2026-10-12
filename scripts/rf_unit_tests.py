"""Unit/acquisition tests precede experiments; statistics validate fresh outputs later."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def cases(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite): yield from cases(item)
        else: yield item

suite=unittest.defaultTestLoader.discover(str(ROOT/'science/rf'),pattern='test_*.py')
unit=unittest.TestSuite(c for c in cases(suite) if not c.id().startswith('test_statistics.'))
result=unittest.TextTestRunner(verbosity=2).run(unit)
raise SystemExit(not result.wasSuccessful())
