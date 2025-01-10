#!/bin/bash

ACTION=help
ORIG_ARGS=()

NAME=$1
shift

while [[ $# -gt 0 ]]; do
  case $1 in
    --start)
      ACTION=start
      shift
      ;;
    --stop)
      ACTION=stop
      shift
      ;;
    -h|--help)
      ACTION=help
      shift
      ;;
    *)
      ORIG_ARGS+=("$1")
      shift # past argument
      ;;
  esac
done

export BASE_DIR=/tmp/mnsec/$NAME/dovecot

if [ "$ACTION" = "help" ]; then
  echo "USAGE: $0 NAME [OPTIONS]"
  echo ""
  echo "  NAME         Name of the instance where this service will run (usually hostname)"
  echo "  --start      Start this service"
  echo "  --stop       Stop this service"
  echo "  -h|--help    Show this help message and exit"
  exit 0
elif [ "$ACTION" = "stop" ]; then
  kill $(cat $BASE_DIR/master.pid)
  exit 0
fi

rm -rf $BASE_DIR
mkdir -p $BASE_DIR
cp -r /etc/dovecot/* $BASE_DIR/
mv $BASE_DIR/dovecot.conf $BASE_DIR/dovecot2.conf
echo "log_path = /tmp/mnsec/$NAME/dovecot/dovecot.log" >> $BASE_DIR/dovecot2.conf
echo "auth_verbose = yes" >> $BASE_DIR/dovecot2.conf
echo "base_dir = /tmp/mnsec/$NAME/dovecot" >> $BASE_DIR/dovecot2.conf

set -- "${ORIG_ARGS[@]}"

dovecot -c $BASE_DIR/dovecot2.conf $@

sleep 1
