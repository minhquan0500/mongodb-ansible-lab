#!/usr/bin/env bash
# Full deployment/verification evidence; no Docker teardown or secret output.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${MONGO_ADMIN_USER:=labadmin}"
: "${MONGO_ADMIN_PASSWORD:?Export MONGO_ADMIN_PASSWORD (at least 16 characters)}"
export MONGO_ADMIN_USER MONGO_ADMIN_PASSWORD
for binary in docker ansible-playbook ansible-galaxy python3 openssl; do
  command -v "$binary" >/dev/null || { echo "FAIL: missing $binary" >&2; exit 1; }
done
mkdir -p logs
stamp=$(date +%Y%m%d-%H%M%S)
run_dir="logs/run-$stamp"
mkdir -p "$run_dir"
run() {
  local file=$1
  shift
  "$@" 2>&1 | tee "$run_dir/$file"
}
run dependencies.log bash -c 'date -Is; cat /etc/os-release; free -h; df -h .; docker version; docker compose version; ansible --version; ansible-galaxy collection list'
run syntax-deploy.log ansible-playbook --syntax-check playbooks/deploy.yml "$@"
run syntax-verify.log ansible-playbook --syntax-check playbooks/verify.yml "$@"
run deploy.log ansible-playbook playbooks/deploy.yml "$@"
run containers.log docker compose -p mongodb-ansible-lab ps
run verify.log ansible-playbook playbooks/verify.yml "$@"
run check-cluster.log bash scripts/check_cluster.sh
for n in mongo{1..5}; do docker inspect --format '{{.Name}} {{.Id}} {{.State.StartedAt}}' "$n"; done > "$run_dir/before-rerun.log"
run idempotency.log ansible-playbook playbooks/deploy.yml "$@"
for n in mongo{1..5}; do docker inspect --format '{{.Name}} {{.Id}} {{.State.StartedAt}}' "$n"; done > "$run_dir/after-rerun.log"
diff -u "$run_dir/before-rerun.log" "$run_dir/after-rerun.log" | tee "$run_dir/container-diff.log"
python3 - "$run_dir/idempotency.log" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
if not re.search(r'localhost\s+:.*changed=0\s+unreachable=0\s+failed=0', text):
    sys.exit('FAIL: expected changed=0 unreachable=0 failed=0')
print('PASS: deployment idempotency (changed=0, no container recreation/restart)')
PY
run verify-after-rerun.log bash scripts/check_cluster.sh
printf 'PASS: full run complete. Evidence: %s\n' "$run_dir"
