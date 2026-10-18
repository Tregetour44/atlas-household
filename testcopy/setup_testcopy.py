"""Start a throwaway Home Assistant test copy in Docker and onboard it (portable; any OS with Docker and Python 3.11+).

  python testcopy/setup_testcopy.py           # from the repo root

- Container 'atlas-ha-test', HA 2026.8.0, port 127.0.0.1:18123 only, config in ./devha-config (git-ignored), demo devices only.
- Onboarding creates a test-only owner with a RANDOM password and a long-lived token. Both are written only to ./devha-config/
  (.atlas-test-password, .atlas-test-token), which is git-ignored. Never commit them, print them or reuse them anywhere.
- Then run: python -I tests/run_testcopy.py
"""
import json
import pathlib
import secrets
import shutil
import subprocess
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = ROOT / 'devha-config'
BASE = 'http://127.0.0.1:18123'
IMAGE = 'ghcr.io/home-assistant/home-assistant:2026.8.0'


def http(method, path, body=None, form=None, token=None):
    data, headers = None, {}
    if body is not None:
        data, headers['Content-Type'] = json.dumps(body).encode(), 'application/json'
    if form is not None:
        data, headers['Content-Type'] = urllib.parse.urlencode(form).encode(), 'application/x-www-form-urlencoded'
    if token:
        headers['Authorization'] = f'Bearer {token}'
    with urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, method=method, headers=headers), timeout=60) as r:
        return json.loads(r.read() or b'null')


def main():
    CFG.mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'testcopy/configuration.yaml', CFG / 'configuration.yaml')
    (CFG / 'custom_components').mkdir(exist_ok=True)
    if not (CFG / 'automations.yaml').exists():
        (CFG / 'automations.yaml').write_text('[]' + chr(10))      # the configuration includes it (the route tests save automations)
    if subprocess.run(['docker', 'inspect', 'atlas-ha-test'], capture_output=True).returncode != 0:
        subprocess.run(['docker', 'run', '-d', '--name', 'atlas-ha-test', '-p', '127.0.0.1:18123:8123', '-v', f'{CFG}:/config',
                        '-e', 'TZ=Australia/Sydney', IMAGE], check=True)
    for _ in range(120):
        try:
            steps = http('GET', '/api/onboarding')
            break
        except Exception:      # noqa: BLE001
            time.sleep(2)
    else:
        raise SystemExit('the test copy did not start')
    if not any(s['step'] == 'user' and not s['done'] for s in steps):
        print('onboarding already done; token in devha-config/.atlas-test-token')
        return
    pw = secrets.token_urlsafe(24)
    (CFG / '.atlas-test-password').write_text(pw)
    client = f'{BASE}/'
    u = http('POST', '/api/onboarding/users', {'client_id': client, 'name': 'Atlas test', 'username': 'atlastest', 'password': pw, 'language': 'en'})
    tok = http('POST', '/auth/token', form={'grant_type': 'authorization_code', 'code': u['auth_code'], 'client_id': client})['access_token']
    http('POST', '/api/onboarding/core_config', {}, token=tok)
    http('POST', '/api/onboarding/analytics', {}, token=tok)
    http('POST', '/api/onboarding/integration', {'client_id': client, 'redirect_uri': f'{BASE}/?auth_callback=1'}, token=tok)
    # A long-lived token needs the websocket API; HA's own Python (with aiohttp) does it inside the container. The short-lived token goes in
    # through stdin, never on a command line or in a file.
    script = ('import asyncio,aiohttp,sys\n'
              'async def m():\n'
              ' t=sys.stdin.read().strip()\n'
              ' async with aiohttp.ClientSession() as s, s.ws_connect("http://localhost:8123/api/websocket") as w:\n'
              '  await w.receive_json(); await w.send_json({"type":"auth","access_token":t}); await w.receive_json()\n'
              '  await w.send_json({"id":1,"type":"auth/long_lived_access_token","client_name":"Atlas coordinator tests","lifespan":3650})\n'
              '  r=await w.receive_json(); sys.stdout.write(r["result"])\n'
              'asyncio.run(m())\n')
    r = subprocess.run(['docker', 'exec', '-i', 'atlas-ha-test', 'python3', '-c', script], input=tok, capture_output=True, text=True, check=True)
    (CFG / '.atlas-test-token').write_text(r.stdout.strip())
    n = len(http('GET', '/api/states', token=r.stdout.strip()))
    print(f'onboarded; token stored in devha-config/ (git-ignored); demo entities: {n}')


if __name__ == '__main__':
    main()
