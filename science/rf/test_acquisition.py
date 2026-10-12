import unittest
try:
 from acquisition import parse_esp_csi,TimestampMapper,calibrate,record,replay
except ImportError:parse_esp_csi=TimestampMapper=calibrate=record=replay=None
from pathlib import Path
import tempfile
HEADER='type,id,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,sig_len,rx_format,len,first_word,data'
LINE='CSI_DATA,0,02:00:00:00:00:01,-50,11,1,0,0,0,0,0,0,0,0,-95,0,1,0,1000000,0,128,0,8,1,"[0,0,0,0,-2,3,4,-5]"'
class Tests(unittest.TestCase):
 def test_official_signed_iq_order_and_invalid_first_word(self):
  self.assertIsNotNone(parse_esp_csi,'ESP-CSI acquisition parser missing')
  d=parse_esp_csi(LINE,HEADER.split(','),TimestampMapper(epoch_ms=0),fixture=True)
  self.assertEqual(d['csi'],[{'re':3,'im':-2},{'re':-5,'im':4}]);self.assertEqual(d['source'],'synthetic');self.assertFalse(d['physical_acquired'])
 def test_timestamp_wrap_is_monotonic(self):
  self.assertIsNotNone(TimestampMapper,'clock mapper missing');m=TimestampMapper(epoch_ms=0)
  a=m.map(2**32-10);b=m.map(10);self.assertGreater(b,a);self.assertAlmostEqual(b-a,.020)
 def test_odd_length_and_wrong_declared_length_rejected(self):
  self.assertIsNotNone(parse_esp_csi,'parser missing')
  with self.assertRaises(ValueError):parse_esp_csi(LINE.replace('8,1,','7,1,'),HEADER.split(','),TimestampMapper(epoch_ms=0),fixture=True)
 def test_replay_preserves_fixture_provenance(self):
  self.assertIsNotNone(record,'recorder missing')
  d=parse_esp_csi(LINE,HEADER.split(','),TimestampMapper(epoch_ms=0),fixture=True)
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'r.jsonl';record([d],p,label='empty-room',calibration_id='test');r=list(replay(p))
   self.assertEqual(r[0]['source'],'synthetic');self.assertEqual(r[0]['evidence']['original_source'],'synthetic')
if __name__=='__main__':unittest.main()
