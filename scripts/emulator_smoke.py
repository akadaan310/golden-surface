#!/usr/bin/env python3
"""Bounded, emulator-only APK/UI smoke probe. Never targets physical devices.

Usage: python3 scripts/emulator_smoke.py --timeout 300
The APK must contain its JS bundle; this probe does not start Metro or a relay.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default=str(ROOT / '.tools/android/platform-tools/adb'))
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--apk', type=Path, default=ROOT / 'artifacts/golden-motion-debug.apk')
    parser.add_argument('--timeout', type=float, default=300, help='Total wall-time budget in seconds')
    parser.add_argument('--deadline-utc', help='Optional absolute UTC deadline, e.g. 2026-10-12T10:49:05+00:00')
    parser.add_argument('--stop-owned-emulator', action='store_true', help='Kill this confirmed emulator after evidence collection')
    args = parser.parse_args()
    out = ROOT / 'artifacts'
    # Each invocation owns a new evidence directory; a blocked rerun cannot
    # accidentally expose screenshots or XML from an earlier successful run.
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    evidence = out / 'emulator-smoke' / run_id
    evidence.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    deadline = started + max(1, args.timeout)
    if args.deadline_utc:
        absolute = datetime.fromisoformat(args.deadline_utc.replace('Z', '+00:00'))
        deadline = min(deadline, started + (absolute-datetime.now(timezone.utc)).total_seconds())
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'serial': args.serial,
              'scope': 'Android emulator only; no physical audio, RF, camera or Galaxy A16 validation',
              'budgetSeconds': args.timeout, 'status': 'blocked', 'reason': None,
              'deadlineUtc': args.deadline_utc,
              'apk': str(args.apk), 'checks': {}, 'commands': [], 'bootSamples': []}
    report['evidenceDirectory'] = str(evidence.relative_to(ROOT))
    confirmed = False

    def run(argv, timeout=12, name=None, binary=False, cleanup=False):
        remaining = deadline - time.monotonic()
        limit = min(timeout, remaining) if not cleanup else min(timeout, 5)
        if limit <= 0:
            raise TimeoutError('Total emulator smoke budget exhausted')
        try:
            result = subprocess.run([args.adb, '-s', args.serial, *argv],
                                    capture_output=True, timeout=limit)
            stdout, stderr, code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, code = exc.stdout or b'', exc.stderr or b'', 124
        entry = {'args': argv, 'exitCode': code, 'elapsedSeconds': round(time.monotonic()-started, 2)}
        if name:
            path = evidence / name
            path.write_bytes(stdout if binary else stdout + stderr)
            entry['evidence'] = str(path.relative_to(ROOT))
        if not binary:
            entry['output'] = (stdout+stderr).decode(errors='replace')[-3000:]
        report['commands'].append(entry)
        return code, stdout.decode(errors='replace') if not binary else stdout

    def shell(command, **kwargs):
        return run(['shell', command], **kwargs)

    def snapshot(label, screenshot=True):
        dumped, message = shell('uiautomator dump /sdcard/gm-smoke.xml', timeout=20)
        if dumped:
            raise RuntimeError('UI hierarchy dump failed for '+label+': '+message[-300:])
        code, xml = run(['exec-out', 'cat', '/sdcard/gm-smoke.xml'], name=label+'.xml')
        if screenshot:
            run(['exec-out', 'screencap', '-p'], name=label+'.png', binary=True, timeout=15)
        if code or not xml.lstrip().startswith('<?xml'):
            raise RuntimeError('UI hierarchy unavailable for '+label)
        return ET.fromstring(xml)

    def texts(tree):
        return ' '.join(n.get('text', '')+' '+n.get('content-desc', '') for n in tree.iter('node'))

    def matching(tree, text):
        return [n for n in tree.iter('node') if text.lower() in
                (n.get('text', '')+' '+n.get('content-desc', '')).lower()]

    def seek(tree, text, direction='down', attempts=14):
        for attempt in range(attempts+1):
            if matching(tree, text):
                return tree
            if attempt == attempts:
                break
            bounds = [list(map(int,re.findall(r'\d+',n.get('bounds','')))) for n in tree.iter('node')]
            width = max((b[2] for b in bounds if len(b)==4), default=320)
            height = max((b[3] for b in bounds if len(b)==4), default=640)
            y1,y2 = (height-90,140) if direction=='down' else (140,height-90)
            shell(f'input swipe 20 {y1} 20 {y2} 180')
            tree = snapshot(f'scroll-{text.replace(" ", "-")}-{attempt}', screenshot=False)
        raise RuntimeError('UI control not found after scrolling: '+text)

    def tap(tree, text):
        for node in tree.iter('node'):
            if text.lower() in (node.get('text', '')+' '+node.get('content-desc', '')).lower():
                points = re.findall(r'\d+', node.get('bounds', ''))
                if len(points) == 4:
                    x1,y1,x2,y2 = map(int, points)
                    shell(f'input tap {(x1+x2)//2} {(y1+y2)//2}')
                    return
        raise RuntimeError('UI control not found: '+text)

    def toggle(tree, label):
        labels = matching(tree,label)
        switches = [n for n in tree.iter('node') if n.get('class')=='android.widget.Switch']
        if not labels or not switches:
            raise RuntimeError('Switch unavailable for '+label)
        label_bounds = list(map(int,re.findall(r'\d+',labels[0].get('bounds',''))))
        label_y = (label_bounds[1]+label_bounds[3])/2
        def distance(node):
            b=list(map(int,re.findall(r'\d+',node.get('bounds',''))))
            return abs((b[1]+b[3])/2-label_y)
        target=min(switches,key=distance)
        x1,y1,x2,y2=map(int,re.findall(r'\d+',target.get('bounds','')))
        shell(f'input tap {(x1+x2)//2} {(y1+y2)//2}')

    try:
        if not re.fullmatch(r'emulator-\d+', args.serial):
            raise RuntimeError('Refusing non-emulator serial')
        while time.monotonic() < deadline-25:
            code, qemu = shell('getprop ro.kernel.qemu')
            if code == 0 and qemu.strip() == '1':
                confirmed = True
                break
            if code == 0 and qemu.strip():
                raise RuntimeError('ro.kernel.qemu is not 1; refusing install, clear, or lifecycle mutations')
            print(json.dumps({'emulatorConfirmed':False,'elapsedSeconds':round(time.monotonic()-started,1)}),flush=True)
            time.sleep(min(5,max(0,deadline-25-time.monotonic())))
        report['emulatorConfirmed'] = confirmed
        if not confirmed:
            raise RuntimeError('ro.kernel.qemu is not 1; refusing install, clear, or lifecycle mutations')
        report['apkBytes'] = args.apk.stat().st_size
        report['apkSha256'] = hashlib.sha256(args.apk.read_bytes()).hexdigest()
        shell('getprop ro.build.fingerprint; getprop ro.build.version.sdk; getprop ro.kernel.qemu.avd_name; getprop ro.boot.qemu.avd_name; uptime', name='provenance.txt')
        shell('service list', name='initial-services.txt')
        run(['logcat', '-d', '-b', 'system', '-s', 'SystemServer', 'PackageManager', 'Watchdog', 'AndroidRuntime'],
            name='boot-systemserver.txt')
        # Reserve enough of the total budget to collect final evidence.
        while time.monotonic() < deadline-25:
            code, state = shell('getprop sys.boot_completed; service check package; service check activity')
            ready = code == 0 and state.startswith('1') and state.count('found') == 2 and 'not found' not in state
            report['bootSamples'].append({'elapsedSeconds': round(time.monotonic()-started, 2), 'state': state.strip()})
            print(json.dumps({'bootReady': ready, 'elapsedSeconds': round(time.monotonic()-started, 1)}), flush=True)
            if ready:
                break
            time.sleep(min(10, max(0, deadline-25-time.monotonic())))
        else:
            report['checks']['androidBoot'] = 'blocked'
            raise RuntimeError('Android boot budget exhausted: boot_completed/package/activity not ready')
        report['checks']['androidBoot'] = 'passed'
        code, installed = run(['install', '-r', str(args.apk)], timeout=55, name='install.txt')
        if code or 'Success' not in installed:
            raise RuntimeError('APK installation failed')
        report['checks']['install'] = 'passed'
        code, launch = shell('am start -W -n com.goldenmotion/.MainActivity', timeout=40, name='launch.txt')
        if code or 'Error' in launch:
            raise RuntimeError('MainActivity launch failed')
        for launch_attempt in range(3):
            tree = snapshot('launch-'+str(launch_attempt))
            if 'GOLDEN MOTION' in texts(tree):
                break
            time.sleep(min(2,max(0,deadline-time.monotonic())))
        else:
            raise RuntimeError('React Native app heading not rendered')
        report['checks']['reactNativeRender'] = 'passed'
        tree = seek(tree, 'Start session')
        tap(tree, 'Start session')
        tree = snapshot('synthetic-running')
        if 'Synthetic hand running' not in texts(tree):
            raise RuntimeError('Synthetic start status not visible')
        report['checks']['syntheticStart'] = 'passed'
        tree = seek(tree,'Intent gate')
        toggle(tree,'Intent gate')
        tree = snapshot('intent-enabled')
        if not any(n.get('checked')=='true' for n in tree.iter('node') if n.get('class')=='android.widget.Switch'):
            raise RuntimeError('Intent switch did not become checked')
        report['checks']['intentToggle'] = 'passed'
        tree = seek(tree,'Record events')
        toggle(tree,'Record events')
        tree = seek(tree,'Start session',direction='up')
        tap(tree,'Start session')
        # Synthetic measurements emit semantic events independently of physical hardware.
        time.sleep(min(4,max(0,deadline-time.monotonic())))
        tree = snapshot('recording-running',screenshot=False)
        tap(tree, 'Stop all')
        tree = snapshot('synthetic-stopped')
        if 'Stopped. Hardware resources released.' not in texts(tree):
            raise RuntimeError('Synthetic stop status not visible')
        report['checks']['syntheticStop'] = 'passed'
        tree = seek(tree,'Record events')
        count = re.search(r'Record events\s*[·•]\s*(\d+)/256',texts(tree))
        if not count or int(count.group(1))<1:
            raise RuntimeError('No semantic events recorded during synthetic session')
        report['recordedEventCount'] = int(count.group(1))
        tap(tree,'Replay events')
        tree = snapshot('replay-events')
        if not re.search(r'\brecorded\s*·',texts(tree),re.IGNORECASE):
            raise RuntimeError('Recorded provenance not visible during replay')
        tree = seek(tree,'Start session',direction='up')
        if 'Recorded semantic replay.' not in texts(tree):
            raise RuntimeError('Replay status not visible')
        report['checks']['recordReplay'] = 'passed'
        shell('input keyevent KEYCODE_HOME')
        shell('am start -W -n com.goldenmotion/.MainActivity', timeout=30)
        tree = snapshot('foreground-return')
        report['checks']['backgroundLifecycle'] = 'passed' if 'Paused:' in texts(tree) else 'not-confirmed'
        # Reset only the app's camera grant on this confirmed emulator, so this
        # negative test cannot accidentally start an already-authorized camera.
        shell('pm revoke com.goldenmotion android.permission.CAMERA',name='camera-revoke.txt')
        shell('pm clear-permission-flags com.goldenmotion android.permission.CAMERA user-set user-fixed')
        code,permissions = shell('dumpsys package com.goldenmotion',name='app-permissions.txt')
        if code or not re.search(r'android\.permission\.CAMERA:\s*granted=false',permissions):
            raise RuntimeError('Camera permission not confirmed revoked; skipping media request')
        tree = seek(tree,'Camera image motion',direction='up')
        tap(tree,'Camera image motion')
        tree = seek(snapshot('camera-selected',screenshot=False),'Start session')
        tap(tree,'Start session')
        tree = snapshot('camera-permission-dialog')
        denied = next((label for label in ["Don't allow",'Don’t allow','Deny'] if matching(tree,label)),None)
        if denied:
            tap(tree,denied)
            tree = snapshot('camera-permission-denied')
            if 'Permission denied. Acquisition did not start.' not in texts(tree):
                raise RuntimeError('Camera permission denial did not prevent acquisition')
            report['checks']['permissionDenial'] = 'passed'
        else:
            # Existing emulator permission grants can skip this prompt. Never start
            # media acquisition solely to manufacture a permission-denial result.
            tree = seek(tree,'Stop all',direction='up')
            tap(tree,'Stop all')
            report['checks']['permissionDenial'] = 'not-confirmed-no-dialog'
        code,pid = shell('pidof com.goldenmotion')
        if code or not pid.strip():
            raise RuntimeError('App process exited during UI validation')
        code,logs = run(['logcat','-d','--pid='+pid.strip().split()[0],'-v','threadtime'],name='app-logcat.txt')
        if code or re.search(r'FATAL EXCEPTION|ReactNativeJS.*(?:TypeError|ReferenceError|SyntaxError|Invariant Violation)',logs):
            report['checks']['noJavaScriptCrash'] = 'failed'
            raise RuntimeError('App logcat contains a runtime crash or could not be read')
        report['checks']['noJavaScriptCrash'] = 'passed'
        report['status'] = 'passed'
        report['reason'] = 'Emulator UI rendered; synthetic start/stop, intent toggle and semantic recording/replay verified. Optional checks are listed individually.'
    except (OSError, RuntimeError, TimeoutError, ET.ParseError) as exc:
        if report['checks'].get('androidBoot') == 'passed':
            report['status'] = 'failed'
        report['reason'] = str(exc)
    finally:
        for check in ['androidBoot','install','reactNativeRender','syntheticStart','syntheticStop','intentToggle','recordReplay','permissionDenial','backgroundLifecycle','noJavaScriptCrash']:
            report['checks'].setdefault(check, 'not-run')
        if confirmed:
            try:
                shell('getprop sys.boot_completed; service check package; service check activity; uptime', name='final-boot-state.txt')
                run(['logcat','-d','-t','600','-v','threadtime'],name='final-logcat.txt')
                run(['exec-out','screencap','-p'],name='final-screen.png',binary=True)
            except TimeoutError:
                pass
            if args.stop_owned_emulator:
                run(['emu','kill'], name='emulator-shutdown.txt', cleanup=True)
        report['elapsedSeconds'] = round(time.monotonic()-started,2)
        (out/'emulator-validation.json').write_text(json.dumps(report,indent=2)+'\n')
        lines = ['# Android emulator validation', '', '**Status:** '+report['status'], '', report['reason'] or '', '',
                 'Scope: '+report['scope'], '', '| Check | Result |', '|---|---|']
        lines += [f'| {key} | {value} |' for key,value in report['checks'].items()]
        lines += ['', f'Serial: `{args.serial}`. Emulator confirmed: `{confirmed}`.',
                  f'Wall time: {report["elapsedSeconds"]} s; budget: {args.timeout} s.',
                  '', 'Command results, APK hash, boot samples and evidence paths are in `emulator-validation.json`.']
        (out/'emulator-validation.md').write_text('\n'.join(lines)+'\n')
        print(json.dumps({'status':report['status'],'reason':report['reason'],'report':'artifacts/emulator-validation.json'}),flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
