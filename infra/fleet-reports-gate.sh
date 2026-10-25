#!/bin/sh
set -eu
mode=${1:?mode required}
station=${2:-}
root=${FLEET_REPORTS_ROOT:-/srv/fleet-reports}
git_shell=${FLEET_GIT_SHELL:-/usr/bin/git-shell}
valid_id() { case "$1" in ''|*[!A-Za-z0-9._-]*) return 1;; *) return 0;; esac; }
case "$mode" in
  write)
    valid_id "$station" || exit 1
    repo="$root/reports-$station.git"
    case "${SSH_ORIGINAL_COMMAND:-}" in
      "git-receive-pack '$repo'"|"git-receive-pack $repo") exec "$git_shell" -c "$SSH_ORIGINAL_COMMAND" ;;
      *) exit 1 ;;
    esac
    ;;
  read)
    command=${SSH_ORIGINAL_COMMAND:-}
    case "$command" in
      "git-upload-pack '$root/reports-"*.git\'|"git-upload-pack $root/reports-"*.git)
        repo=${command#git-upload-pack }
        repo=${repo#\'}
        repo=${repo%\'}
        relative=${repo#"$root/"}
        basename=$relative
        case "$basename" in reports-*.git) ;; *) exit 1;; esac
        station=${basename#reports-}
        station=${station%.git}
        valid_id "$station" || exit 1
        [ -d "$repo" ] || exit 1
        exec "$git_shell" -c "$SSH_ORIGINAL_COMMAND"
        ;;
      *) exit 1 ;;
    esac
    ;;
  *) exit 1 ;;
esac
