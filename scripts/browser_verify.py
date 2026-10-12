"""Bounded production-browser verification. Starts/stops only its own local server."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness.process import execute, _stop


def main():
    url='http://127.0.0.1:3001'
    log=(ROOT/'artifacts/web-production-server.txt').open('w')
    server=subprocess.Popen(['npm','run','start','--workspace','@golden-motion/web','--','--port','3001'],
                            cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    evidence=[]
    try:
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            if server.poll() is not None: raise RuntimeError('Production server exited')
            try:
                with urlopen(url,timeout=2) as response:
                    if response.status==200: break
            except Exception: time.sleep(.2)
        else: raise RuntimeError('Production server not ready within budget')
        env_before=os.environ.get('GM_WEB_URL')
        os.environ['GM_WEB_URL']=url
        try:
            for command in [['node','apps/web/tests/browser.mjs'],
                            ['node','apps/web/tests/relay-browser.mjs'],
                            ['node_modules/.bin/tsx','scripts/browser_transport.ts']]:
                result=execute(command,ROOT,120,6144,1024**2)
                evidence.append({'command':command,**result})
                print(result['output'][-3000:])
                if result['returncode']!=0 or result['error']:
                    raise RuntimeError('Browser check failed; preserved exact output')
        finally:
            if env_before is None:os.environ.pop('GM_WEB_URL',None)
            else:os.environ['GM_WEB_URL']=env_before
        source=ROOT/'apps/web/test-results'
        for name in ['desktop.png','mobile.png','rf.png','browser.json','relay-browser.json']:
            if (source/name).exists():shutil.copyfile(source/name,ROOT/'artifacts'/('web-'+name))
        (ROOT/'artifacts/browser-verification.json').write_text(json.dumps({'passed':True,
            'build':'production','url':url,'camera':'Chromium synthetic test camera; not physical hand accuracy',
            'checks':evidence},indent=2)+'\n')
        return 0
    except Exception as error:
        (ROOT/'artifacts/browser-verification.json').write_text(json.dumps({'passed':False,
            'build':'production','error':str(error),'checks':evidence},indent=2)+'\n')
        print(str(error));return 1
    finally:
        _stop(server);log.close()


if __name__=='__main__':raise SystemExit(main())
