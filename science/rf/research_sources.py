"""Recheck cited public metadata/docs/papers without retaining full source copies.
Uses inherited proxy/TLS trust. Never downloads dataset/code archives, performs
Wi-Fi acquisition, or reads private accounts. Initial evidence remains immutable.
"""
import urllib.request,json,time,hashlib,pathlib,concurrent.futures,argparse
ROOT=pathlib.Path(__file__).parent

def fetch(pair):
 key,old=pair;url=old['url'];record={'url':url,'checked_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'scope':'public documentation, metadata or publication; no dataset archive','physical_tested':False}
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'GOLDEN-MOTION-research/0.1'})
  with urllib.request.urlopen(req,timeout=20) as response:
   payload=response.read(16_000_000);record.update(status=response.status,final_url=response.url,content_type=response.headers.get('Content-Type'),bytes_read=len(payload),bounded_prefix=len(payload)==16_000_000,sha256=hashlib.sha256(payload).hexdigest())
 except Exception as exc:record.update(status='unavailable',error=str(exc))
 return key,record

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--include-unavailable',action='store_true');args=p.parse_args();sources=json.loads((ROOT/'results/source-verification.json').read_text())
 permitted={key:value for key,value in sources.items() if args.include_unavailable or value['status']==200}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:result=dict(pool.map(fetch,permitted.items()))
 (ROOT/'results/rechecked-source-verification.json').write_text(json.dumps(result,indent=2)+'\n')
 for key,value in result.items():print(key,value['status'],value.get('bytes_read'))
if __name__=='__main__':main()
