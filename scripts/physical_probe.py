"""Inventory a connected actual Galaxy A16; never marks hand sensing validated."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness.hardware import connected_a16


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--install',action='store_true',help='Install/launch the commissioned instrument on connected A16')
    args=parser.parse_args();device=connected_a16(ROOT)
    if device is None:
        print('No actual Galaxy A16 detected; physical capability/gesture validation pending.');return 3
    def adb(*argv):
        result=subprocess.run([device['adb'],'-s',device['serial'],*argv],
                              capture_output=True,text=True,timeout=60,check=True)
        return result.stdout.strip()
    properties={name:adb('shell','getprop',prop) for name,prop in {
        'androidVersion':'ro.build.version.release','apiLevel':'ro.build.version.sdk',
        'build':'ro.build.display.id','socModel':'ro.soc.model','socManufacturer':'ro.soc.manufacturer',
        'boardPlatform':'ro.board.platform','hardware':'ro.hardware'}.items()}
    result={'timestamp':datetime.now(timezone.utc).isoformat(),'source':'physical',
            'model':device['model'],'manufacturer':device['manufacturer'],
            'deviceIdHash':hashlib.sha256(device['serial'].encode()).hexdigest(),
            'properties':properties,'platformSensorService':adb('shell','dumpsys','sensorservice')[:32000],
            'installed':False,'handSensingValidation':'pending controlled calibration and negative controls',
            'audioBandwidth':'not measured','cameraAccuracy':'not measured','wifiCsi':'not established by this probe'}
    if args.install:
        result['installOutput']=adb('install','-r',str(ROOT/'artifacts/golden-motion-debug.apk'))
        result['launchOutput']=adb('shell','am','start','-W','-n','com.goldenmotion/.MainActivity')
        result['installed']=True
    path=ROOT/'artifacts/physical-a16-capabilities.json'
    path.write_text(json.dumps(result,indent=2)+'\n');print(str(path));return 0


if __name__=='__main__':raise SystemExit(main())
