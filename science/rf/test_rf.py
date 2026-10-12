"""Physical constraints: fail if nuisance becomes motion or scalar becomes position."""
import unittest
import numpy as np
try:
 from kernel import csi_forward, estimate_csi, rssi_forward, estimate_rssi, fisher_geometry, RFConfig
except ImportError:
 csi_forward = estimate_csi = rssi_forward = estimate_rssi = fisher_geometry = RFConfig = None

class RFTests(unittest.TestCase):
 def test_forward_matches_single_path_delay(self):
  self.assertIsNotNone(csi_forward, 'RF complex forward model not implemented')
  c = RFConfig(noise=0, cfo_hz=0, sfo_ppm=0, phase_noise=0, static_amplitude=0, static_paths=(), antenna_count=1)
  t,h,_,mask = csi_forward(c, duration=1, seed=11)
  p=np.array(c.position); length=np.linalg.norm(p-c.tx)+np.linalg.norm(p-c.rx)
  expected=c.amplitude*np.exp(-2j*np.pi*c.frequencies*length/c.light_speed)
  np.testing.assert_allclose(h[0,0],expected,atol=1e-11)
 def test_common_phase_nuisance_is_not_motion(self):
  self.assertIsNotNone(estimate_csi, 'CSI estimator not implemented')
  c=RFConfig(velocity=(0,0,0),cfo_hz=42,phase_noise=.04)
  t,h,_,mask=csi_forward(c,duration=4,seed=2)
  e=estimate_csi(t,h,mask,c)
  self.assertFalse(e['presence']); self.assertNotIn('position',e)
 def test_moving_csi_detected_with_scalar_only(self):
  self.assertIsNotNone(estimate_csi, 'CSI estimator not implemented')
  c=RFConfig(); t,h,_,mask=csi_forward(c,duration=4,seed=1)
  e=estimate_csi(t,h,mask,c)
  self.assertTrue(e['presence']); self.assertNotIn('position',e)
 def test_coarse_rssi_has_independent_inverse_and_no_hand_range(self):
  self.assertIsNotNone(estimate_rssi, 'independent RSSI estimator not implemented')
  t,y=rssi_forward(duration=20,seed=8,moving=False)
  e=estimate_rssi(t,y)
  self.assertNotIn('path_rate_mps',e); self.assertNotIn('position',e)
  self.assertGreater(e['calibrated_link_distance_m'],0)
 def test_single_geometry_rank_does_not_allow_localization(self):
  self.assertIsNotNone(fisher_geometry, 'geometry observability not implemented')
  e=fisher_geometry([(np.array([0,0,0]),np.array([1,0,0]))],np.array([.5,.5,.2]))
  self.assertEqual(e['rank'],1); self.assertFalse(e['localizable'])

if __name__=='__main__': unittest.main()
