#!/usr/bin/env python3
"""Docker execution uses stdin for credentials; never prints raw MongoDB errors."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

NODES = [f'mongo{i}' for i in range(1, 6)]
PROJECT = 'mongodb-ansible-lab'

def preflight(require_key=True):
    for node in NODES:
        result = subprocess.run(['docker', 'container', 'inspect', node], capture_output=True, text=True)
        if result.returncode == 0:
            labels = json.loads(result.stdout)[0]['Config'].get('Labels') or {}
            if labels.get('com.docker.compose.project') != PROJECT or labels.get('com.docker.compose.service') != node:
                raise RuntimeError(f'Container name conflict: {node}; refusing to modify it')
    if require_key and not Path('.secrets/rs0.key').is_file():
        volumes = subprocess.run(['docker', 'volume', 'ls', '--quiet', '--filter', 'label=com.docker.compose.project='+PROJECT], capture_output=True, text=True, check=True)
        if volumes.stdout.strip():
            raise RuntimeError('Existing project volumes but keyfile absent; restore the original keyfile before deploying')
    print('PASS: project ownership/name checks')

USER = os.environ.get('MONGO_ADMIN_USER', 'labadmin')
PASSWORD = os.environ.get('MONGO_ADMIN_PASSWORD', '')

def mongo(node, body):
    prefix = 'const u=' + json.dumps(USER) + ';const p=' + json.dumps(PASSWORD) + ';const a=db.getSiblingDB("admin");\n'
    script = prefix + '''function auth(){try{const r=a.auth(u,p);return r===1 || r.ok===1;}catch(e){return false;}}
try { const result=(()=>{\n''' + body + '''\n})(); print('LABJSON:'+JSON.stringify(result)); }
catch(e){ print('LABJSON:'+JSON.stringify({ok:false,code:e.code||0})); }
'''
    proc = subprocess.run(['docker', 'exec', '-i', node, 'mongosh', '--quiet', '--host', '127.0.0.1', '--file', '/dev/stdin'], input=script, text=True, capture_output=True, timeout=25)
    for line in proc.stdout.splitlines():
        if line.startswith('LABJSON:'):
            return json.loads(line[8:])
    return {'ok': False, 'code': 'docker-or-shell-failure'}

def initialize():
    result = mongo('mongo1', '''auth();
try {const s=rs.status(); return {ok:s.ok===1,changed:false};}
catch(e){if(e.code!==94) throw e;}
const r=rs.initiate({_id:'rs0',members:[1,2,3,4,5].map((n)=>({_id:n-1,host:'mongo'+n+':27017',votes:1,priority:n===1?2:1}))});
return {ok:r.ok===1,changed:true};''')
    if not result.get('ok'):
        raise RuntimeError('init failed (check credentials or replica configuration), code='+str(result.get('code')))
    print('CHANGED: rs.initiate' if result.get('changed') else 'OK: replica set already initialized')

def bootstrap():
    for _ in range(60):
        for node in NODES:
            result = mongo(node, '''if(auth()) return {ok:true,changed:false};
if(!a.hello().isWritablePrimary) return {ok:false};
a.createUser({user:u,pwd:p,roles:[{role:'root',db:'admin'}]},{w:'majority',wtimeout:30000});
return {ok:true,changed:true};''')
            if result.get('ok'):
                print('CHANGED: initial administrator created' if result.get('changed') else 'OK: administrator authenticated')
                return
        time.sleep(2)
    raise RuntimeError('bootstrap failed: no writable primary or credentials do not match existing user')

VERIFY = '''if(!auth()) return {ok:false,code:'authentication'};
const s=rs.status(), c=rs.conf(), v=a.runCommand({buildInfo:1}).version;
const expected=[1,2,3,4,5].map(n=>'mongo'+n+':27017').sort();
const primary=s.members.filter(m=>m.state===1).length;
const secondary=s.members.filter(m=>m.state===2).length;
const valid=s.ok===1 && s.set==='rs0' && s.members.length===5 && primary===1 && secondary===4
 && s.members.every(m=>m.health===1) && c.members.length===5
 && c.members.every(m=>m.votes===1 && !m.arbiterOnly)
 && JSON.stringify(c.members.map(m=>m.host).sort())===JSON.stringify(expected)
 && /^6\\.0\\./.test(v);
return {ok:valid,version:v,set:s.set,primary,secondary,members:s.members.map(m=>({name:m.name,state:m.stateStr,health:m.health}))};'''

def verify():
    preflight(require_key=False)
    for node in NODES:
        state = subprocess.run(['docker', 'inspect', '--format', '{{.State.Running}}', node], capture_output=True, text=True)
        if state.returncode or state.stdout.strip() != 'true':
            raise RuntimeError(node + ' is absent or not running')
    last = {}
    for _ in range(60):
        last = {node: mongo(node, VERIFY) for node in NODES}
        if all(result.get('ok') for result in last.values()):
            for node, result in last.items():
                print(f"PASS: {node}: MongoDB {result['version']}, rs0, 5 voting data members, 1 PRIMARY, 4 SECONDARY, all healthy")
            print(json.dumps(last['mongo1'], indent=2))
            return
        time.sleep(2)
    # Only print our explicit projection, never raw MongoDB output or exception text.
    print(json.dumps(last, indent=2))
    raise RuntimeError('cluster health checks failed')

if __name__ == '__main__':
    try:
        action = sys.argv[1]
        if action != 'preflight' and len(PASSWORD) < 16:
            raise RuntimeError('MONGO_ADMIN_PASSWORD must contain at least 16 characters')
        {'preflight': preflight, 'init': initialize, 'bootstrap': bootstrap, 'verify': verify}[action]()
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            print('FAIL: '+str(exc), file=sys.stderr)
        else:
            print('FAIL: operation failed ('+type(exc).__name__+')', file=sys.stderr)
        sys.exit(1)
