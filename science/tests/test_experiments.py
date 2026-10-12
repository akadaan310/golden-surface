import json
import subprocess
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

class ComparativeTests(unittest.TestCase):
    def run_behavior(self, body):
        code='import numpy as np\nfrom science.golden_motion.experiments import *\nfrom science.golden_motion.adapters import *\n'+body
        result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_optical_projection_preserves_scale_ambiguity(self):
        self.run_behavior("a=synthetic_optical([.1,.05,.4],seed=1,noise_std=0); b=synthetic_optical([.2,.1,.8],seed=1,noise_std=0); assert np.allclose(a['image'],b['image']); assert 'position' not in a; assert a['coordinateFrame']=='camera-image-normalized'")

    def test_common_fusion_beats_anchored_optical_prior(self):
        self.run_behavior("r,f=run_common_experiment(); m=r['GM-004']; assert m['fused_position_rmse_m']<m['optical_anchored_prior_position_rmse_m']; assert r['GM-001']['scalar_only_position_rmse_m'] is None; assert len(f['frames'])>=100; assert f['source']=='synthetic'")

    def test_ble_adapter_rejects_nonfinite_stale_and_out_of_range(self):
        self.run_behavior("a=BLEAdapter('ble-1'); m=a.ingest(1000,-65); assert m['relative']['unit']=='dBm'; assert 'position' not in m;\nfor ts,rssi in [(999,-60),(1100,float('nan')),(1200,3)]:\n try: a.ingest(ts,rssi); raise AssertionError('bad sample accepted')\n except ValueError: pass")

    def test_fusion_rank_is_computed_from_sensor_jacobians(self):
        self.run_behavior("r=fusion_observability([.1,.05,.4]); assert r['rankRange']==1; assert r['rankOptical']==2; assert r['rankCombined']==3; assert len(r['combinedSingularValues'])==3")

    def test_state_filter_does_not_predict_before_initial_sample(self):
        self.run_behavior("from science.golden_motion.model import filter_range_velocity\nt=np.arange(20)*.03; truth=.25+.04*t; state=filter_range_velocity(truth,np.full(20,.04),.03); assert np.max(np.abs(state[:,0]-truth))<1e-12, state[0]")

    def test_range_state_filter_reduces_constant_velocity_noise(self):
        self.run_behavior("from science.golden_motion.model import filter_range_velocity\nrng=np.random.default_rng(42); t=np.arange(150)*.03; truth=.25+.04*t; r=truth+rng.normal(0,.01,len(t)); v=.04+rng.normal(0,.01,len(t)); filtered=filter_range_velocity(r,v,.03,.01,.01)[:,0]; assert np.sqrt(np.mean((filtered[10:]-truth[10:])**2))<np.sqrt(np.mean((r[10:]-truth[10:])**2))")

if __name__=='__main__': unittest.main()
