"""Owned loopback diagnostic stream regression: no RF hardware or Wi-Fi traffic."""
import unittest,socket,threading,time,subprocess,sys,tempfile,json
from pathlib import Path
class TCPBudgetTests(unittest.TestCase):
 def test_diagnostic_stream_obeys_total_capture_deadline_and_audits(self):
  listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();port=listener.getsockname()[1]
  def server():
   try:
    conn,_=listener.accept()
    with conn:
     deadline=time.monotonic()+.25
     while time.monotonic()<deadline:
      try:conn.sendall(b'I (10) wifi: diagnostic-only\n')
      except (BrokenPipeError,ConnectionResetError):break
      time.sleep(.005)
   finally:listener.close()
  thread=threading.Thread(target=server,daemon=True);thread.start()
  with tempfile.TemporaryDirectory() as tmp:
   output=Path(tmp)/'capture.jsonl'
   # Process startup excluded by audit: transport budget starts before connect.
   r=subprocess.run([sys.executable,str(Path(__file__).with_name('acquisition.py')),'--tcp',f'127.0.0.1:{port}','--authorized','--output',str(output),'--timeout-seconds','.05'],capture_output=True,text=True,timeout=3)
   self.assertEqual(r.returncode,0,r.stderr)
   audit=Path(str(output)+'.audit.json')
   self.assertTrue(audit.exists(),'bounded capture audit missing')
   a=json.loads(audit.read_text());self.assertLess(a['elapsed_seconds'],.12);self.assertEqual(a['packet_count'],0);self.assertGreater(a['line_count'],0);self.assertEqual(a['stop_reason'],'deadline')
  thread.join(timeout=1)
 def test_line_and_byte_budgets_cover_diagnostics(self):
  import acquisition
  self.assertTrue(hasattr(acquisition,'tcp_lines'),'bounded TCP iterator missing')
  a,b=socket.socketpair();audit={}
  try:
   b.sendall(b'X'*100+b'\n');b.shutdown(socket.SHUT_WR)
   with self.assertRaises(ValueError):list(acquisition.tcp_lines(a,timeout_seconds=1,max_bytes=1000,max_lines=10,max_line_bytes=32,audit=audit))
   self.assertEqual(audit['stop_reason'],'line-budget')
  finally:a.close();b.close()
if __name__=='__main__':unittest.main()
