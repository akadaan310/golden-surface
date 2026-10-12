"""Scientific regression tests. Subprocess isolation permits explicit pre-API red runs."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class AcousticTests(unittest.TestCase):
    def check_script(self, body):
        result = subprocess.run([sys.executable, '-c', 'import numpy as np\nfrom science.golden_motion.model import *\n' + body], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_seeded_forward_model_is_repeatable(self):
        self.check_script("cfg=AcousticConfig(); a=simulate_echo([0,0,.2],[0,0,0],cfg,seed=9); b=simulate_echo([0,0,.2],[0,0,0],cfg,seed=9); assert np.array_equal(a.received,b.received); assert np.linalg.norm(a.received)>0")

    def test_matched_filter_recovers_fractional_delay(self):
        self.check_script("cfg=AcousticConfig(noise_std=0); sig=simulate_echo([0,0,.2137],[0,0,0],cfg); est=estimate_delay(sig,cfg); assert est['valid']; assert abs(est['range_m']-.2137)<.0015, est")

    def test_doppler_sign_changes_when_motion_reverses(self):
        self.check_script("cfg=AcousticConfig(noise_std=0); a=estimate_doppler(simulate_tone([0,0,.4],[0,0,.06],cfg),cfg); b=estimate_doppler(simulate_tone([0,0,.4],[0,0,-.06],cfg),cfg); assert a['frequency_hz']<0<b['frequency_hz']; assert abs(a['radial_velocity_m_s']-.06)<1e-5, a")

    def test_phase_tracks_small_displacement_but_is_ambiguous(self):
        self.check_script("cfg=AcousticConfig(noise_std=0); a=simulate_tone([0,0,.4],[0,0,0],cfg); b=simulate_tone([0,0,.401],[0,0,0],cfg); delta=phase_displacement(a.received[0],b.received[0],cfg); assert abs(delta-.001)<1e-9; assert cfg.sound_speed_m_s/(2*cfg.carrier_hz)<.01")

    def test_scalar_range_cannot_observe_three_dimensions(self):
        self.check_script("p=np.array([.1,.2,.3]); q=np.zeros((1,3)); obs=observability(p,q,q); assert obs['position_rank']==1; assert obs['state_rank']<6; q=np.array([[0,0,0],[.4,0,0],[0,.4,0],[0,0,.4]]); assert observability(p,q,q)['position_rank']==3")

    def test_noise_only_no_hand_is_rejected(self):
        self.check_script("cfg=AcousticConfig(noise_std=.02); sig=simulate_echo([0,0,.2],[0,0,0],cfg,seed=7,hand_present=False); est=estimate_delay(sig,cfg); assert not est['valid'], est")

    def test_reflector_and_wrong_sound_speed_have_real_effect(self):
        self.check_script("cfg=AcousticConfig(noise_std=0); sig=simulate_echo([0,0,.2],[0,0,0],cfg,reflections=[(.09,1.8)]); est=estimate_delay(sig,cfg); assert est['range_m']>.23, est; sig=simulate_echo([0,0,.2],[0,0,0],cfg); bad=estimate_delay(sig,AcousticConfig(sound_speed_m_s=330,noise_std=0)); assert bad['range_m']<.196, bad")

    def test_measured_background_cancels_static_direct_leakage(self):
        self.check_script("cfg=AcousticConfig(leakage_gain=2); background=simulate_echo([0,0,.2],[0,0,0],cfg,seed=22,hand_present=False); absent=simulate_echo([0,0,.2],[0,0,0],cfg,seed=23,hand_present=False); assert estimate_delay(absent,cfg)['valid']; assert not estimate_delay(absent,cfg,background=background)['valid']; hand=simulate_echo([0,0,.2],[0,0,0],cfg,seed=24); est=estimate_delay(hand,cfg,background=background); assert abs(est['range_m']-.2)<.002")

    def test_invalid_phase_cannot_fabricate_zero_motion(self):
        self.check_script("\nfor a,b in [(0j,1j),(1j,complex(float('nan'),0))]:\n try: phase_displacement(a,b); raise AssertionError('invalid phase accepted')\n except ValueError: pass")

    def test_bandwidth_resolution_is_not_reported_as_standard_deviation(self):
        self.check_script("cfg=AcousticConfig(); est=estimate_delay(simulate_echo([0,0,.2],[0,0,0],cfg),cfg); assert 'uncertainty_m' not in est; assert est['bandwidth_resolution_m']>.02")

    def test_clock_drift_is_confounded_with_doppler(self):
        self.check_script("cfg=AcousticConfig(noise_std=0,clock_rate_error=200e-6); tone=simulate_tone([0,0,.3],[0,0,0],cfg); est=estimate_doppler(tone,cfg); assert abs(est['frequency_hz']-3.6)<1e-9; assert abs(est['radial_velocity_m_s']+.0343)<1e-9")

    def test_nonfinite_receive_trace_is_rejected(self):
        self.check_script("cfg=AcousticConfig(); signal=simulate_echo([0,0,.2],[0,0,0],cfg); signal.received[0]=complex(float('nan'),0);\nfor estimator in [estimate_delay,estimate_doppler]:\n try: estimator(signal,cfg); raise AssertionError('nonfinite trace accepted')\n except ValueError: pass")

    def test_nonfinite_and_negative_noise_are_rejected(self):
        self.check_script("\nfor kwargs in ({'noise_std':-1},{'sound_speed_m_s':0},{'sample_rate_hz':1000}):\n try: AcousticConfig(**kwargs); raise AssertionError('invalid config accepted')\n except ValueError: pass\ntry: simulate_echo([0,float('nan'),.2],[0,0,0],AcousticConfig()); raise AssertionError('nan accepted')\nexcept ValueError: pass")


if __name__ == '__main__':
    unittest.main()
