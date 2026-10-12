"""Hardware-ready scalar BLE acquisition boundary; no fabricated spatial position."""
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class RSSICalibration:
    tx_power_at_one_m_dbm: float = -59.
    path_loss_exponent: float = 2.
    rssi_std_db: float = 2.
    calibration_id: str = 'synthetic-log-distance-v1'

    def __post_init__(self):
        if not all(math.isfinite(x) for x in (self.tx_power_at_one_m_dbm,self.path_loss_exponent,self.rssi_std_db)) or self.path_loss_exponent<=0 or self.rssi_std_db<=0:
            raise ValueError('invalid calibration')

    def range_estimate(self,rssi_dbm):
        distance=10**((self.tx_power_at_one_m_dbm-rssi_dbm)/(10*self.path_loss_exponent))
        sigma=distance*math.log(10)*self.rssi_std_db/(10*self.path_loss_exponent)
        return distance,sigma

class BLEAdapter:
    """Accept platform scan callback data; source reflects actual acquisition.

    Calibration is optional. Without measured calibration this emits RSSI only.
    An inverse log-distance estimate requires an explicit calibration object and
    remains scalar; it does not localize an uninstrumented hand.
    """
    def __init__(self,device_id,*,source='live',calibration=None):
        if source not in ('live','recorded','synthetic') or not device_id:
            raise ValueError('invalid source/device')
        self.device_id=device_id; self.source=source; self.calibration=calibration
        self.last_timestamp=-1

    def ingest(self,timestamp_ms,rssi_dbm):
        if (not all(math.isfinite(x) for x in (timestamp_ms,rssi_dbm)) or
            timestamp_ms<=self.last_timestamp or timestamp_ms<0 or not -127<=rssi_dbm<=0):
            raise ValueError('invalid or out-of-order BLE measurement')
        measurement={'timestamp':timestamp_ms,'source':self.source,'modality':'ble-rssi',
            'deviceId':self.device_id,'coordinateFrame':'measurement-space',
            'relative':{'kind':'rssi','value':rssi_dbm,'unit':'dBm'},
            'confidence':.5,'uncertainty':[self.calibration.rssi_std_db if self.calibration else 2.],
            'metadata':{'confidenceMeaning':'uncalibrated quality heuristic','requiresInstrumentedTarget':True,'uncertaintyMeaning':'assumed RSSI standard deviation in dB; physically unverified'}}
        if self.calibration:
            distance,sigma=self.calibration.range_estimate(rssi_dbm)
            measurement['metadata']['scalarRangeEstimateM']=distance
            measurement['metadata']['scalarRangeStdM']=sigma
            measurement['calibrationId']=self.calibration.calibration_id
        self.last_timestamp=timestamp_ms
        return measurement
