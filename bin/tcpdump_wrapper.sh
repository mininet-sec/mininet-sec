#!/bin/bash

ACTION=$1
INTF=$2
CAP_FILE=$3
MAX_SIZE=$4

if [ $# -lt 2 ]; then
	echo "USAGE: $0 <start|stop> <INTF> [<CaptureFile> <MAX_SIZE>]"
	exit 0
fi

PID_FILE=/var/run/tcpdump-$INTF.pid
USER=mnsec
test -z $(getent passwd $USER) && USER=nobody
test -z $CAP_FILE && CAP_FILE=/var/tmp/capture-$INTF.pcap
test -z $MAX_SIZE && MAX_SIZE=10


function stop() {
	if [ -f $PID_FILE ]; then
		kill -9 $(cat $PID_FILE) 2>/dev/null
		rm -f $PID_FILE
	fi
}

function start() {
	touch $CAP_FILE
	chown $USER $CAP_FILE
	tcpdump -ni $INTF -s 0 -w $CAP_FILE -Z $USER -U -C $MAX_SIZE -W 1 >/dev/null 2>&1 &
	echo $! > $PID_FILE
}

function status() {
	PID=$(cat $PID_FILE 2>/dev/null)
	if grep -q State /proc/$PID/status 2>/dev/null; then
		echo "running"
	else
		echo "fail"
	fi
}


if [ "$ACTION" = "start" ]; then
  stop
  start
elif [ "$ACTION" = "stop" ]; then
  stop
elif [ "$ACTION" = "status" ]; then
  status
else
	echo "USAGE: $0 <start|stop> <INTF> [<CaptureFile> <MAX_SIZE>]"
fi
