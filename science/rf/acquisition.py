"""ESP-CSI signed-IQ serial/TCP pipeline with explicit fixture provenance.

No capture is started by import, tests, or default CLI use. Live collection needs
--authorized and an explicitly named owned device/port. This is not Wi-Fi sniffing.
"""
import csv,json,time,math,socket,contextlib,argparse
from pathlib import Path
import numpy as np
DEFAULT_HEADER='type,id,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,sig_len,rx_format,len,first_word,data'.split(',')
class TimestampMapper:
 def __init__(self,epoch_ms=None):
  self.epoch_ms=time.time()*1000 if epoch_ms is None else epoch_ms;self.last=None;self.wrap=0;self.origin=None
 def map(self,micros):
  if not 0<=micros<2**32:raise ValueError('ESP timestamp must be unsigned32 microseconds')
  if self.last is not None and micros<self.last:
   if self.last-micros>2**31:self.wrap+=2**32
   else:raise ValueError('out-of-order timestamp; record separately instead of reordering silently')
  self.last=micros;unwrapped=micros+self.wrap
  if self.origin is None:self.origin=unwrapped
  return self.epoch_ms+(unwrapped-self.origin)/1000

def parse_esp_csi(line,header=DEFAULT_HEADER,clock=None,fixture=False,chip='esp32-legacy-int8',receipt_ms=None):
 if len(line)>100000:raise ValueError('CSI line exceeds bounded parser size')
 fields=next(csv.reader([line.strip()]))
 if not fields or fields[0]!='CSI_DATA':return None
 if len(fields)!=len(header):raise ValueError('CSI CSV field count differs from declared official firmware header')
 d=dict(zip(header,fields));samples=json.loads(d['data']);declared=int(d['len'])
 if not isinstance(samples,list) or len(samples)!=declared or len(samples)%2:raise ValueError('CSI declared byte/value length mismatch or odd IQ count')
 if chip!='esp32-legacy-int8':raise ValueError('newer chips/forced-LLTF 12bit packing require explicit validated format; never decode silently')
 if any(isinstance(v,bool) or not isinstance(v,int) or not -128<=v<=127 for v in samples):raise ValueError('legacy CSI must contain signed int8 I/Q')
 invalid=int(d.get('first_word',d.get('first_word_invalid','0')))
 if invalid not in (0,1):raise ValueError('first-word flag must be0/1')
 if invalid:samples=samples[4:]
 if not samples:raise ValueError('no valid IQ after first-word removal')
 clock=clock or TimestampMapper();ts=clock.map(int(d['local_timestamp']))
 # ESP-IDF explicitly gives imaginary byte followed by real byte.
 csi=[{'re':samples[i+1],'im':samples[i]} for i in range(0,len(samples),2)]
 return {'timestamp':ts,'device_timestamp_us':int(d['local_timestamp']),'receipt_timestamp_ms':receipt_ms if receipt_ms is not None else (ts if fixture else time.time()*1000),'sequence':int(d.get('id',d.get('seq','0'))),'rssi_dbm':int(d['rssi']),'channel':int(d['channel']),'antenna':int(d.get('ant','0')),'csi':csi,'source':'synthetic' if fixture else 'recorded','physical_acquired':False,'evidence':{'adapter':'esp-csi-serial-csv','chip_format':chip,'first_word_removed':bool(invalid),'firmware_header':header,'fixture':fixture,'clock':'first-receipt-epoch + unwrapped local microseconds; no inter-device synchronization established'}}

def calibrate(records,calibration_id='empty-room-001'):
 r=list(records)
 if len(r)<5:raise ValueError('at least five baseline packets required')
 n=len(r[0]['csi'])
 if any(len(v['csi'])!=n or v['channel']!=r[0]['channel'] for v in r):raise ValueError('do not mix channel or IQ layout in calibration')
 mag=np.array([[math.hypot(z['re'],z['im']) for z in v['csi']] for v in r]);sd=np.maximum(.5,np.std(mag,axis=0))
 return {'id':calibration_id,'source':r[0]['source'],'physical_acquired':all(v['physical_acquired'] for v in r),'channel':r[0]['channel'],'count':len(r),'amplitude_mean':mag.mean(axis=0).tolist(),'amplitude_std':sd.tolist(),'absolute_range_calibrated':False,'coherent_multiantenna':False}

def single_antenna_presence(records,calibration):
 """ESP32 stock receiver lacks simultaneous coherent dual antenna CSI. Amplitude only."""
 r=list(records)
 if len(r)<5:return {'presence':False,'quality':'unobservable','confidence':0.,'coordinate_frame':'measurement-space'}
 if any(v['channel']!=calibration['channel'] for v in r):raise ValueError('calibration channel changed')
 mag=np.array([[math.hypot(z['re'],z['im']) for z in v['csi']] for v in r]);mean=np.asarray(calibration['amplitude_mean']);sd=np.asarray(calibration['amplitude_std'])
 if mag.shape[1]!=len(mean):raise ValueError('calibration CSI shape changed')
 score=float(np.median(np.abs(mag-mean)/sd));return {'presence':score>3,'motion_score':float(min(1,score/6)),'confidence':None,'quality':'degraded','coordinate_frame':'measurement-space','source':r[0]['source'],'warnings':['amplitude anomaly only; gain/shadowing confounded','no coherent dual antennas: no CFO-independent Doppler/radial velocity','baseline threshold requires physical false-activation calibration']}

def record(records,path,label='unlabeled',calibration_id=None,max_packets=10000,audit=None):
 count=0
 with Path(path).open('w') as f:
  for item in records:
   if count>=max_packets:break
   d={**item,'label':label,'calibration_id':calibration_id};d['evidence']={**d.get('evidence',{}),'original_source':item['source'],'recording_format':'golden-motion-esp-csi-v1'}
   f.write(json.dumps(d,separators=(',',':'))+'\n');count+=1
   if audit is not None:audit['packet_count']=count;audit['physical_packets_received']=item.get('source')=='live' or audit.get('physical_packets_received',False)
 return count

def replay(path,max_packets=10000):
 with Path(path).open() as f:
  for i,line in enumerate(f):
   if i>=max_packets:break
   if len(line)>100000:raise ValueError('bounded replay row exceeded')
   d=json.loads(line)
   if d.get('source') not in ('synthetic','live','recorded'):raise ValueError('missing provenance')
   # Replaying acquisition changes transport, never scientific provenance.
   d['evidence']={**d.get('evidence',{}),'replayed':True,'original_source':d.get('evidence',{}).get('original_source',d['source'])};yield d

def lines_from_stream(stream,fixture=True,epoch_ms=0,live=False):
 header=DEFAULT_HEADER;clock=TimestampMapper(epoch_ms)
 for line in stream:
  if line.startswith('type,'):header=next(csv.reader([line]));continue
  d=parse_esp_csi(line,header,clock,fixture)
  if d:
   if live:d['source']='live';d['physical_acquired']=True
   yield d

def tcp_lines(sock,timeout_seconds=10,max_bytes=2_000_000,max_lines=10000,max_line_bytes=16384,audit=None,started=None):
 """Total deadline and diagnostic-inclusive budgets, before CSV parsing."""
 audit=audit if audit is not None else {};started=time.monotonic() if started is None else started;deadline=started+timeout_seconds;buffer=b''
 audit.update(byte_count=0,line_count=0,stop_reason='eof',budget_seconds=timeout_seconds)
 try:
  while True:
   remaining=deadline-time.monotonic()
   if remaining<=0:audit['stop_reason']='deadline';return
   sock.settimeout(remaining)
   try:chunk=sock.recv(min(4096,max_bytes-audit['byte_count']+1))
   except socket.timeout:audit['stop_reason']='deadline';return
   if not chunk:
    if buffer:raise ValueError('incomplete final CSV line')
    return
   audit['byte_count']+=len(chunk)
   if audit['byte_count']>max_bytes:audit['stop_reason']='byte-budget';raise ValueError('TCP byte budget exceeded including diagnostics')
   buffer+=chunk
   while b'\n' in buffer:
    line,buffer=buffer.split(b'\n',1);audit['line_count']+=1
    if len(line)>max_line_bytes:audit['stop_reason']='line-budget';raise ValueError('TCP line length budget exceeded')
    if audit['line_count']>max_lines:audit['stop_reason']='line-count-budget';raise ValueError('TCP line count budget exceeded including diagnostics')
    if time.monotonic()>=deadline:audit['stop_reason']='deadline';return
    yield line.decode('utf8',errors='strict')
   if len(buffer)>max_line_bytes:audit['stop_reason']='line-budget';raise ValueError('TCP incomplete line budget exceeded')
 finally:audit['elapsed_seconds']=time.monotonic()-started

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path);p.add_argument('--tcp');p.add_argument('--serial');p.add_argument('--baud',type=int,default=921600);p.add_argument('--authorized',action='store_true');p.add_argument('--output',type=Path,required=True);p.add_argument('--label',default='unlabeled');p.add_argument('--fixture',action='store_true');p.add_argument('--max-packets',type=int,default=500);p.add_argument('--timeout-seconds',type=float,default=10);p.add_argument('--max-bytes',type=int,default=2_000_000);p.add_argument('--max-lines',type=int,default=10000);p.add_argument('--max-line-bytes',type=int,default=16384)
 args=p.parse_args()
 if not 1<=args.max_packets<=10000 or not 0<args.timeout_seconds<=120 or not 1<=args.max_bytes<=16_000_000 or not 1<=args.max_lines<=100000 or not 1<=args.max_line_bytes<=100000:p.error('capture budget exceeded')
 if sum(x is not None for x in (args.input,args.tcp,args.serial))!=1:p.error('choose exactly one explicitly named source')
 if (args.tcp or args.serial) and not args.authorized:p.error('owned/operator+participant-authorized hardware flag required')
 if args.input:
  with args.input.open() as stream:record(lines_from_stream(stream,fixture=args.fixture,epoch_ms=0),args.output,args.label,max_packets=args.max_packets)
 elif args.tcp:
  host,port=args.tcp.rsplit(':',1)
  started=time.monotonic();audit={'adapter':'explicit-authorized-tcp','packet_count':0,'physical_packets_received':False}
  try:
   with socket.create_connection((host,int(port)),timeout=args.timeout_seconds) as sock:
    stream=tcp_lines(sock,args.timeout_seconds,args.max_bytes,args.max_lines,args.max_line_bytes,audit,started)
    try:
     audit['packet_count']=record(lines_from_stream(stream,fixture=False,epoch_ms=time.time()*1000,live=True),args.output,args.label,max_packets=args.max_packets,audit=audit)
     if audit['packet_count']>=args.max_packets:audit['stop_reason']='packet-budget'
     audit['physical_packets_received']=audit['packet_count']>0
    finally:stream.close()
  except Exception as exc:
   audit['error']=str(exc);raise
  finally:
   audit['elapsed_seconds']=time.monotonic()-started
   Path(str(args.output)+'.audit.json').write_text(json.dumps(audit,indent=2)+'\n')
 else:
  try:import serial
  except ImportError:p.error('optional pyserial required only for explicit physical serial capture')
  with serial.Serial(args.serial,args.baud,timeout=args.timeout_seconds) as s:
   def lines():
    deadline=time.monotonic()+args.timeout_seconds
    while time.monotonic()<deadline:
     b=s.readline()
     if b:yield b.decode('utf8',errors='strict')
   record(lines_from_stream(lines(),fixture=False,epoch_ms=time.time()*1000,live=True),args.output,args.label,max_packets=args.max_packets)
if __name__=='__main__':main()
