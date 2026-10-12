"""Owned USB-debug discovery; emulators never satisfy physical A16 prerequisites."""
from pathlib import Path
import shutil
import subprocess


def connected_a16(root):
    local=Path(root)/'.tools/android/platform-tools/adb'
    adb=str(local) if local.is_file() else shutil.which('adb')
    if not adb:return None
    def call(serial,*args):
        result=subprocess.run([adb,*(['-s',serial] if serial else []),*args],
                              capture_output=True,text=True,timeout=8)
        return result.stdout.strip() if result.returncode==0 else ''
    try:
        rows=call(None,'devices').splitlines()[1:]
        for row in rows:
            values=row.split()
            if len(values)<2 or values[1]!='device' or values[0].startswith('emulator-'):continue
            serial=values[0]
            if call(serial,'shell','getprop','ro.kernel.qemu')=='1':continue
            manufacturer=call(serial,'shell','getprop','ro.product.manufacturer')
            model=call(serial,'shell','getprop','ro.product.model')
            if manufacturer.lower()=='samsung' and model.upper().startswith(('SM-A165','SM-A166')):
                return {'adb':adb,'serial':serial,'model':model,'manufacturer':manufacturer}
    except (OSError,subprocess.TimeoutExpired):pass
    return None
