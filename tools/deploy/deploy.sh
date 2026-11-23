#!/bin/sh
# Build the site and copy it to the web server over SSH.
#
#   tools/deploy/deploy.sh deploy@10.8.0.1:/opt/www/talhatabak.com
#   DEPLOY_TARGET=deploy@10.8.0.1:/opt/www/talhatabak.com tools/deploy/deploy.sh
#
# Run by .github/workflows/deploy.yml; works the same from your computer.
# rsync must be installed on both sides. Files in the target folder that
# are not in the new build are deleted.
set -eu

case "${1-}" in -h | --help) sed -n '2,9p' "$0" | cut -c3-; exit 0 ;; esac

target=${1:-${DEPLOY_TARGET:-}}
case "$target" in
  ?*:/?*) ;;
  *) echo "usage: $0 SERVER:/path/to/site   (or set DEPLOY_TARGET; see --help)" >&2; exit 1 ;;
esac

cd "$(dirname "$0")/../.."
hugo --gc --minify
# -c: compare by content, so files a new build didn't change are not sent again
rsync -rlcz --delete --chmod=D755,F644 public/ "$target/"
echo "Deployed to $target"
