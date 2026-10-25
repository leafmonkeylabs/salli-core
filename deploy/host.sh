#!/bin/sh
# One hosted Salli per person or household, on one machine with Docker:
# the published image and compose.yaml, HTTPS through Caddy, nightly backups.
# docs/hosting.md has the whole guide.
#
#   deploy/host.sh init <dir> <domain> <email> <currency> [--unencrypted-volume]
#                                    set up, start, make the owner
#   deploy/host.sh backup <dir>      one encrypted backup into <dir>/backups
#   deploy/host.sh upgrade <dir>     back up, pull, restart
#
# The owner's password is read from stdin (`init ... < password-file`), or
# asked for when stdin is a terminal. Nothing here is sent anywhere.
# init refuses unless <dir> and Docker's data are on an encrypted volume
# (LUKS), or --unencrypted-volume says you know they aren't. Backups are
# encrypted with age to the public key in <dir>/backup-recipient; the
# secrets are never in them (docs/hosting.md, "Backups").
set -eu

here=$(cd "$(dirname "$0")/.." && pwd)
command=${1:-}
dir=${2:-}
[ -n "$command" ] && [ -n "$dir" ] || { sed -n 2,16p "$0" >&2; exit 2; }

# One machine (or VM) per instance: Caddy takes ports 80 and 443.
compose() { docker compose -f "$dir/compose.yaml" --project-directory "$dir" --profile tls "$@"; }

# Whether the filesystem holding $1 sits on a dm-crypt (LUKS) device.
encrypted() {
  source=$(findmnt -no SOURCE --target "$1" 2>/dev/null) || return 1
  lsblk -nso TYPE "$source" 2>/dev/null | grep -qx crypt
}

backup() {
  recipient="$dir/backup-recipient"
  [ -s "$recipient" ] || {
    echo "No backup without a key: put an age public key (age-keygen -y) in $recipient" >&2
    exit 1
  }
  command -v age >/dev/null || { echo "Backups need age (https://age-encryption.org)" >&2; exit 1; }
  mkdir -p "$dir/backups"
  chmod 700 "$dir/backups"
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  # The data only, encrypted before it touches the disk. The secrets are
  # never in a backup: keep them offline, apart from it (docs/hosting.md).
  compose exec -T postgres pg_dump --username=salli --format=custom salli \
    | age -R "$recipient" > "$dir/backups/$stamp.dump.age"
  compose exec -T salli tar -C /var/lib/salli -cf - files \
    | age -R "$recipient" > "$dir/backups/$stamp.tar.age"
  echo "Backed up to $dir/backups/$stamp.{dump,tar}.age"
  # Old backups go only once this one is off the machine: <dir>/backup-copy,
  # run with the two files, must copy them elsewhere and exit 0.
  if [ -x "$dir/backup-copy" ] && "$dir/backup-copy" "$dir/backups/$stamp.dump.age" "$dir/backups/$stamp.tar.age"; then
    find "$dir/backups" -type f -mtime +14 -delete
  else
    echo "Not copied off the machine ($dir/backup-copy): keeping every backup here" >&2
  fi
}

case "$command" in
  init)
    domain=${3:?a domain}
    email=${4:?the owner email}
    currency=${5:?the ledger currency, an ISO 4217 code}
    [ ! -e "$dir/.env" ] || { echo "$dir is already set up" >&2; exit 1; }
    mkdir -p "$dir"
    if [ "${6:-}" != "--unencrypted-volume" ]; then
      for path in "$dir" "$(docker info -f '{{.DockerRootDir}}')"; do
        encrypted "$path" || {
          echo "$path is not on an encrypted volume (LUKS; docs/hosting.md)." >&2
          echo "Pass --unencrypted-volume to go ahead knowing it isn't." >&2
          exit 1
        }
      done
    fi
    cp "$here/compose.yaml" "$dir/compose.yaml"
    umask 077
    cat > "$dir/.env" <<ENV
SALLI_DOMAIN=$domain
SALLI_PUBLIC_URL=https://$domain
COMPOSE_PROFILES=tls
ENV
    compose up -d --wait
    if [ -t 0 ]; then
      compose exec salli salli-server setup --email "$email" --currency "$currency"
    else
      compose exec -T salli salli-server setup --email "$email" --currency "$currency" --password-stdin
    fi
    compose exec -T salli salli-server doctor
    echo "Salli is at https://$domain; push alerts go every 15 minutes (the push service)."
    echo "Schedule the other jobs (docs/self-host.md#scheduled-jobs) and nightly backups:"
    echo "  15 2 * * * $here/deploy/host.sh backup $dir"
    echo "after putting an age public key in $dir/backup-recipient and an off-machine"
    echo "copy script in $dir/backup-copy. Keep a copy of the secrets offline:"
    echo "  docker compose -f $dir/compose.yaml exec -T salli tar -C /var/lib/salli -cf - secrets"
    ;;
  backup) backup ;;
  upgrade)
    backup
    cp "$here/compose.yaml" "$dir/compose.yaml"
    compose pull
    compose up -d --wait
    compose exec -T salli salli-server doctor
    ;;
  *) sed -n 2,16p "$0" >&2; exit 2 ;;
esac
