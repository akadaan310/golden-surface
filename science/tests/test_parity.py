import subprocess
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class NumericalParityTests(unittest.TestCase):
    def test_parity_validator_detects_changed_numerical_output(self):
        code="from science.golden_motion.parity import validate_outputs\nimport numpy as np\nassert validate_outputs(np.array([1.,2.]),np.array([1.,2.]))['passed']\nassert not validate_outputs(np.array([1.,2.]),np.array([1.,2.01]))['passed']\n"
        result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
if __name__=='__main__': unittest.main()
