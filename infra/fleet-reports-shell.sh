#!/bin/sh
set -eu
[ "$#" -eq 2 ] || exit 1
[ "$1" = "-c" ] || exit 1
case "$2" in
  "/usr/local/libexec/fleet-reports-gate read") exec /bin/sh -c "$2" ;;
  "/usr/local/libexec/fleet-reports-gate write "*)
    station=${2#"/usr/local/libexec/fleet-reports-gate write "}
    case "$station" in ''|*[!A-Za-z0-9._-]*) exit 1;; esac
    [ "$2" = "/usr/local/libexec/fleet-reports-gate write $station" ] || exit 1
    exec /bin/sh -c "$2"
    ;;
  *) exit 1 ;;
esac
