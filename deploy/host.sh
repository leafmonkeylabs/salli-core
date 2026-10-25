#!/bin/sh
# One hosted Salli per person or household, on one machine with Docker:
# the published image and compose.yaml, HTTPS through Caddy, nightly backups.
# docs/hosting.md has the whole guide.
#
#   deploy/host.sh init <dir> <domain> <email> <currency>  set up, start, make the owner
#   deploy/host.sh backup <dir>                            one backup into <dir>/backups
#   deploy/host.sh upgrade <dir>                           back up, pull, restart
#
# The owner's password is read from stdin (`init ... < password-file`), or
# asked for when stdin is a terminal. Nothing here is sent anywhere.
set -eu

here=$(cd "$(dirname "$0")/.." && pwd)
command=${1:-}
dir=${2:-}
[ -n "$command" ] && [ -n "$dir" ] || { sed -n 2,11p "$0" >&2; exit 2; }

# One machine (or VM) per instance: Caddy takes ports 80 and 443.
compose() { docker compose -f "$dir/compose.yaml" --project-directory "$dir" --profile tls "$@"; }

backup() {
  mkdir -p "$dir/backups"
  chmod 700 "$dir/backups"
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  compose exec -T postgres pg_dump --username=salli --format=custom salli > "$dir/backups/$stamp.dump"
  compose exec -T salli tar -C /var/lib/salli -cf - files secrets > "$dir/backups/$stamp.tar"
  # Keep two weeks of nightly backups here; copy them off the machine too.
  find "$dir/backups" -type f -mtime +14 -delete
  echo "Backed up to $dir/backups/$stamp.{dump,tar}"
}

case "$command" in
  init)
    domain=${3:?a domain}
    email=${4:?the owner email}
    currency=${5:?the ledger currency, an ISO 4217 code}
    [ ! -e "$dir/.env" ] || { echo "$dir is already set up" >&2; exit 1; }
    mkdir -p "$dir"
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
    echo "Salli is at https://$domain. Schedule nightly backups:"
    echo "  15 2 * * * $here/deploy/host.sh backup $dir"
    ;;
  backup) backup ;;
  upgrade)
    backup
    cp "$here/compose.yaml" "$dir/compose.yaml"
    compose pull
    compose up -d --wait
    compose exec -T salli salli-server doctor
    ;;
  *) sed -n 2,11p "$0" >&2; exit 2 ;;
esac
