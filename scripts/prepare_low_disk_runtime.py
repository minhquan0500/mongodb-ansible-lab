import urllib.request,json,tarfile,os,shutil,subprocess
from pathlib import Path
active=subprocess.check_output(['docker','ps','--quiet','--filter','label=com.docker.compose.project=mongodb-ansible-lab'], text=True)
if active.strip():
    raise SystemExit('FAIL: project containers are running; do not replace an active runtime')
project=Path(__file__).resolve().parents[1]
base_dir=project/'.runtime'
root=Path(os.environ.get('MONGO_RUNTIME_ROOT', str(base_dir/'rootfs'))).resolve()
root.mkdir(parents=True, exist_ok=True)
root.chmod(0o755)
base='https://registry-1.docker.io/v2/library/mongo/'
token=json.load(urllib.request.urlopen('https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/mongo:pull'))['token']
def request(path):
 return urllib.request.urlopen(urllib.request.Request(base+path,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json'}))
m=json.load(request('manifests/sha256:0a83b2f824b29c94c5284a49b018db2e3166d9879d1edda5cce545d899ef2bbb'))
if 'manifests' in m:
 digest=next(x['digest'] for x in m['manifests'] if x.get('platform',{}).get('architecture')=='amd64' and x['platform'].get('os')=='linux')
 m=json.load(request('manifests/'+digest))
for layer in m['layers']:
 print('extract',layer['digest'],flush=True)
 with request('blobs/'+layer['digest']) as stream, tarfile.open(fileobj=stream,mode='r|gz') as tar:
  for member in tar:
   name=member.name.lstrip('./')
   if not name or '..' in Path(name).parts:continue
   dest=root/name
   if Path(name).name.startswith('.wh.'):
    target=dest.parent/Path(name).name[4:]
    if target.exists():
     if target.is_dir():shutil.rmtree(target)
     else:target.unlink()
    continue
   # Official image paths are trusted; no ownership changes on host.
   try:tar.extract(member,root,filter='fully_trusted',set_attrs=False)
   except FileExistsError:pass
   if not member.issym() and not member.islnk():
    try:dest.chmod(member.mode)
    except FileNotFoundError:pass
print('extracted',flush=True)

# Tiny filesystem image shares read-only official binaries; data volumes stay separate.
import subprocess
skeleton=base_dir/'skeleton'
skeleton.mkdir(parents=True, exist_ok=True)
skeleton.chmod(0o755)
for directory in ['data','data/db','data/configdb','run','tmp','proc','sys','dev','root','var','var/lib']:
    d=skeleton/directory
    d.mkdir(parents=True, exist_ok=True)
    d.chmod(0o1777 if directory=='tmp' else 0o755)
for name in ['bin','sbin','lib','lib64','usr']:
    link=skeleton/name
    if not link.is_symlink():link.symlink_to('/runtime/'+name)
shutil.rmtree(skeleton/'etc', ignore_errors=True)
shutil.copytree(root/'etc', skeleton/'etc', symlinks=True)
archive=base_dir/'skeleton.tar'
with tarfile.open(archive,'w') as tar:tar.add(skeleton, arcname='.')
with archive.open('rb') as stream:
    subprocess.run(['docker','import','--change','LABEL lab.owner=mongodb-ansible-lab','--change','ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin','-','mongodb-ansible-lab-runtime:6.0.26'], stdin=stream, check=True)
print('Prepared runtime at '+str(root))
print('Set MONGO_RUNTIME_ROOT to this path before using docker-compose.low-disk.yml')
