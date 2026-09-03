#!/usr/bin/env sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1

cd "$PROJECT_DIR"

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

python3 -m unittest discover -s tests
python3 -m compileall -q src tests

set +e
no_login_output=$(python3 -m mailmate_cli --cookie-jar "$tmp_dir/no-login-cookies.txt" --no-login --json inspect 198843 2>&1)
no_login_code=$?
set -e
if [ "$no_login_code" -ne 77 ]; then
  printf '%s\n' "$no_login_output"
  printf 'Expected no-login smoke to exit 77, got %s\n' "$no_login_code" >&2
  exit 1
fi
printf '%s\n' "$no_login_output" | grep -q '"auth_required"'

set +e
apply_guard_output=$(python3 -m mailmate_cli --json abandon 198843 --apply 2>&1)
apply_guard_code=$?
set -e
if [ "$apply_guard_code" -ne 2 ]; then
  printf '%s\n' "$apply_guard_output"
  printf 'Expected apply guard to exit 2, got %s\n' "$apply_guard_code" >&2
  exit 1
fi

set +e
doctor_output=$(python3 -m mailmate_cli --json doctor 2>&1)
doctor_code=$?
set -e
if [ "$doctor_code" -ne 0 ] && [ "$doctor_code" -ne 77 ]; then
  printf '%s\n' "$doctor_output"
  printf 'Expected doctor to exit 0 or 77, got %s\n' "$doctor_code" >&2
  exit 1
fi
printf '%s\n' "$doctor_output" | grep -q '"checks"'

python3 -m mailmate_cli \
  --json \
  --audit-log "$tmp_dir/audit.jsonl" \
  init \
  --config "$tmp_dir/config.json" \
  --env-sample "$tmp_dir/env.sample" \
  --state-dir "$tmp_dir/state" \
  | grep -q '"createdConfig": true'

set +e
run_output=$(
  python3 -m mailmate_cli \
    --cookie-jar "$tmp_dir/no-login-run-cookies.txt" \
    --no-login \
    --json \
    --audit-log "$tmp_dir/audit.jsonl" \
    --lock-file "$tmp_dir/run.lock" \
    run \
    --config examples/config.example.json \
    2>&1
)
run_code=$?
set -e
if [ "$run_code" -ne 77 ]; then
  printf '%s\n' "$run_output"
  printf 'Expected no-login run smoke to exit 77, got %s\n' "$run_code" >&2
  exit 1
fi
printf '%s\n' "$run_output" | grep -q '"auth_required"'
if [ -e "$tmp_dir/run.lock" ]; then
  printf 'Expected no-login run smoke to clean lock file\n' >&2
  exit 1
fi

printf '{"timestamp":"2026-06-23T00:00:00+00:00","command":"run","rows":[{"decision":"skipped"}]}\n' > "$tmp_dir/audit.jsonl"
python3 -m mailmate_cli \
  --json \
  --audit-log "$tmp_dir/audit.jsonl" \
  status \
  | grep -q '"runs": 1'

python3 -m mailmate_cli \
  launch-agent \
  --program "$PROJECT_DIR/bin/mailmate" \
  --plist-path "$tmp_dir/com.vec.mailmate-cli.run.plist" \
  --print \
  | grep -q '<key>ProgramArguments</key>'

python3 -m mailmate_cli \
  launch-agent \
  --program "$PROJECT_DIR/bin/mailmate" \
  --run-yes \
  --print \
  | grep -q '<string>--yes</string>'

set +e
no_login_list_output=$(python3 -m mailmate_cli --cookie-jar "$tmp_dir/no-login-cookies.txt" --no-login --json list 2>&1)
no_login_list_code=$?
set -e
if [ "$no_login_list_code" -ne 77 ]; then
  printf '%s\n' "$no_login_list_output"
  printf 'Expected no-login list smoke to exit 77, got %s\n' "$no_login_list_code" >&2
  exit 1
fi
printf '%s\n' "$no_login_list_output" | grep -q '"auth_required"'

set +e
no_login_read_output=$(python3 -m mailmate_cli --cookie-jar "$tmp_dir/no-login-cookies.txt" --no-login --json read 198843 2>&1)
no_login_read_code=$?
set -e
if [ "$no_login_read_code" -ne 77 ]; then
  printf '%s\n' "$no_login_read_output"
  printf 'Expected no-login read smoke to exit 77, got %s\n' "$no_login_read_code" >&2
  exit 1
fi
printf '%s\n' "$no_login_read_output" | grep -q '"auth_required"'

set +e
open_guard_code=$(python3 -m mailmate_cli --json open 198843 --apply 2>&1 >/dev/null; echo $?)
archive_guard_code=$(python3 -m mailmate_cli --json archive 198843 --apply 2>&1 >/dev/null; echo $?)
set -e
if [ "$open_guard_code" -ne 2 ]; then
  printf 'Expected open apply guard to exit 2, got %s\n' "$open_guard_code" >&2
  exit 1
fi
if [ "$archive_guard_code" -ne 2 ]; then
  printf 'Expected archive apply guard to exit 2, got %s\n' "$archive_guard_code" >&2
  exit 1
fi

set +e
no_login_open_output=$(python3 -m mailmate_cli --cookie-jar "$tmp_dir/no-login-cookies.txt" --no-login --json open 198843 2>&1)
no_login_open_code=$?
no_login_download_output=$(python3 -m mailmate_cli --cookie-jar "$tmp_dir/no-login-cookies.txt" --no-login --json download 198843 2>&1)
no_login_download_code=$?
no_login_archive_output=$(python3 -m mailmate_cli --cookie-jar "$tmp_dir/no-login-cookies.txt" --no-login --json archive 198843 2>&1)
no_login_archive_code=$?
set -e
if [ "$no_login_open_code" -ne 77 ]; then
  printf 'Expected no-login open smoke to exit 77, got %s\n' "$no_login_open_code" >&2
  exit 1
fi
if [ "$no_login_download_code" -ne 77 ]; then
  printf 'Expected no-login download smoke to exit 77, got %s\n' "$no_login_download_code" >&2
  exit 1
fi
if [ "$no_login_archive_code" -ne 77 ]; then
  printf 'Expected no-login archive smoke to exit 77, got %s\n' "$no_login_archive_code" >&2
  exit 1
fi

python3 -m mailmate_cli \
  --profile profile2 \
  --json \
  init \
  --config "$tmp_dir/profiles/profile2/config.json" \
  --env-sample "$tmp_dir/profiles/profile2/env.sample" \
  --state-dir "$tmp_dir/profiles/profile2" \
  | grep -q '"createdConfig": true'

printf 'verification ok\n'
