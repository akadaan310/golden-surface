"""Executable statistical controls. Run experiments/classifiers/fusion first."""
import unittest,json
from pathlib import Path
ROOT=Path(__file__).with_name('results')
class StatisticalControls(unittest.TestCase):
 def test_nominal_CSI_and_CFO_negative_control(self):
  r=json.loads((ROOT/'experiments.json').read_text());c=r['csi']
  self.assertGreater(c['nominal_moving']['detection_rate_wilson_95'][0],.9)
  self.assertLess(c['nominal_moving']['mean_detected_absolute_error_mps'],.02)
  self.assertLess(c['strong_common_CFO']['detection_rate_wilson_95'][1],.1)
 def test_failures_remain_in_the_evidence(self):
  r=json.loads((ROOT/'experiments.json').read_text())
  self.assertEqual(r['csi']['independent_antenna_drift_no_hand']['false_positive_rate'],1)
  self.assertEqual(r['csi']['iso_delay_movement']['detection_rate'],0)
  self.assertFalse(r['observability']['one_link']['localizable'])
  self.assertTrue(r['observability']['three_diverse_links']['localizable'])
 def test_RSSI_and_fusion_confounds_not_reported_as_success(self):
  r=json.loads((ROOT/'experiments.json').read_text());self.assertEqual(r['rssi']['coarse_moving']['detection_rate'],0)
  f=json.loads((ROOT/'fusion.json').read_text())['scenarios']
  self.assertGreater(f['acoustic_clock_bias']['fused_position_MAE_m'],.1)
  self.assertEqual(f['unrelated_moving_object']['quality_gated_acoustic_optical_activation'],1)
 def test_session_partitions_and_CSI_RSSI_combination_preserved(self):
  r=json.loads((ROOT/'classifiers.json').read_text());s=r['split'];self.assertEqual(s['participant_count'],0)
  self.assertFalse(set(s['train_sessions'])&set(s['test_sessions']))
  self.assertLess(r['regularized_logistic']['accuracy'],r['regularized_logistic_csi_only']['accuracy'])
  self.assertIn('clustered_session_bootstrap_95',r['regularized_logistic'])
if __name__=='__main__':unittest.main()
