#!/bin/bash

PORT=22
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
    -P|--port)
      PORT=$2
      shift
      shift
      ;;
    *)
      ORIG_ARGS+=("$1")
      shift # past argument
      ;;
  esac
done

BASEDIR=/tmp/mnsec/$NAME/ssh

if [ "$ACTION" = "help" ]; then
  echo "USAGE: $0 NAME [OPTIONS]"
  echo ""
  echo "  NAME         Name of the instance where this service will run (usually hostname)"
  echo "  --start      Start this service"
  echo "  --stop       Stop this service"
  echo "  -P|--port    Port to listen for connections"
  echo "  -h|--help    Show this help message and exit"
  exit 0
elif [ "$ACTION" = "stop" ]; then
  kill $(cat $BASEDIR/sshd.pid)
  exit 0
fi

rm -rf $BASEDIR
mkdir -p $BASEDIR
mkdir -p /run/sshd

ssh-keygen -q -f $BASEDIR/ssh_host_rsa_key -N '' -t rsa
ssh-keygen -q -f $BASEDIR/ssh_host_dsa_key -N '' -t dsa

cat << EOF > $BASEDIR/sshd_config
Port $PORT
HostKey $BASEDIR/ssh_host_rsa_key
HostKey $BASEDIR/ssh_host_dsa_key
AuthorizedKeysFile  .ssh/authorized_keys
ChallengeResponseAuthentication no
UsePAM yes
Subsystem   sftp    /usr/lib/ssh/sftp-server
PidFile $BASEDIR/sshd.pid
EOF

set -- "${ORIG_ARGS[@]}"

/usr/sbin/sshd -f $BASEDIR/sshd_config $@

sleep 1
