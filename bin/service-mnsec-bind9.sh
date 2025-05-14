#!/bin/bash

# Default values
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
    --reload)
      ACTION=reload
      shift
      ;;
    --add-zone)
      ACTION=add-zone
      shift
      ;;
    --add-reverse-zone)
      ACTION=add-reverse-zone
      shift
      ;;
    --add-entry)
      ACTION=add-entry
      shift
      ;;
    --enable-recursive)
      ACTION=enable-recursive
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

export BASE_DIR=/tmp/mnsec/$NAME/bind9
export PID_FILE=$BASE_DIR/run/named/named.pid


function start() {
	rm -rf $BASE_DIR
	mkdir -p $BASE_DIR/{etc,dev,run/named,var/cache/bind}
	mknod $BASE_DIR/dev/null c 1 3
	mknod $BASE_DIR/dev/random c 1 8
	mknod $BASE_DIR/dev/urandom c 1 9
	chmod 666 $BASE_DIR/dev/{null,random,urandom}
	cp -r /etc/bind $BASE_DIR/etc/
	cp /etc/localtime $BASE_DIR/etc/
	chown bind:bind $BASE_DIR/etc/bind/rndc.key
	chown bind:bind $BASE_DIR/run/named
	chmod 775 $BASE_DIR/{var/cache/bind,run/named}
	chgrp bind $BASE_DIR/{var/cache/bind,run/named}
	cp /usr/share/dns/root.hints $BASE_DIR/etc/bind/
	sed -i 's@/usr/share/dns/root.hints@/etc/bind/root.hints@g'  $BASE_DIR/etc/bind/named.conf.default-zones
	mkdir -p $BASE_DIR/var/log
	chown bind:bind $BASE_DIR/var/log/

	## Adding a testing zone
	cp $BASE_DIR/etc/bind/db.local $BASE_DIR/etc/bind/db.hackinsdn.test
	sed -i 's/localhost/hackinsdn.test/g' $BASE_DIR/etc/bind/db.hackinsdn.test
	cat >>$BASE_DIR/etc/bind/named.conf.local <<EOF
zone "hackinsdn.test" {
        type master;
        file "/etc/bind/db.hackinsdn.test";
};
EOF
	sed -i 's/127.0.0.1/172.16.10.1/g' $BASE_DIR/etc/bind/db.hackinsdn.test
	echo "@	       IN   MX 10   smtp" >> $BASE_DIR/etc/bind/db.hackinsdn.test
	echo "@	       IN   MX 20   smtp-2" >> $BASE_DIR/etc/bind/db.hackinsdn.test
	echo "t1       IN   NS      t1ns" >> $BASE_DIR/etc/bind/db.hackinsdn.test
	echo "t1ns     IN   A       172.16.10.1" >> $BASE_DIR/etc/bind/db.hackinsdn.test
	echo "www      IN   A       203.0.113.56" >> $BASE_DIR/etc/bind/db.hackinsdn.test
	echo "server1  IN   A       203.0.113.99" >> $BASE_DIR/etc/bind/db.hackinsdn.test
	echo "home     IN   A       203.0.113.98" >> $BASE_DIR/etc/bind/db.hackinsdn.test
	echo "webmail  IN   CNAME   www" >> $BASE_DIR/etc/bind/db.hackinsdn.test
	echo "smtp     IN   CNAME   server1" >> $BASE_DIR/etc/bind/db.hackinsdn.test
	echo "smtp-2   IN   A       198.51.99.103" >> $BASE_DIR/etc/bind/db.hackinsdn.test
	echo "vpn      IN   A       198.51.99.9" >> $BASE_DIR/etc/bind/db.hackinsdn.test
	echo "ftp      IN   CNAME   server1" >> $BASE_DIR/etc/bind/db.hackinsdn.test
	/usr/sbin/named -u bind -t $BASE_DIR -L /var/log/bind9.log
}

function reload(){
	rndc reload
}

function add_zone(){
        TEMPLATE=$1
	ZONE=$2
	FILE=$3

	# check if bind9 is running
	if ! rndc status | grep -q "server is up and running"; then
		echo "bind9 is not runnig! Please run --start first"
		exit 0
	fi

	# check if zone name is valid
	if ! echo "$ZONE" | egrep -q "^([a-zA-Z0-9-]+.)+[a-zA-Z0-9]+$"; then
		echo "Invalid Zone name: $ZONE"
		exit 0
	fi
	# check if zone already exists
	if grep -q "\"$ZONE\"" $BASE_DIR/etc/bind/named.conf.local || [ -f $BASE_DIR/etc/bind/db.$ZONE ]; then
		echo "Zone already exists!"
		exit 0
	fi
	# add zone
	if [ -f "$FILE" ]; then
		cp $FILE $BASE_DIR/etc/bind/db.$ZONE
	else
		cp $BASE_DIR/etc/bind/$TEMPLATE $BASE_DIR/etc/bind/db.$ZONE

		if [ $TEMPLATE = "db.local" ]; then
			sed -i "s/localhost/$ZONE/g" $BASE_DIR/etc/bind/db.$ZONE
		fi
	fi
cat >>$BASE_DIR/etc/bind/named.conf.local <<EOF
zone "$ZONE" {
        type master;
        file "/etc/bind/db.$ZONE";
};
EOF
	named-checkzone $ZONE $BASE_DIR/etc/bind/db.$ZONE

	# add DNSSEC validation exception for this zone
	if ! grep -q "validate-except" $BASE_DIR/etc/bind/named.conf.options; then
		sed -i "/dnssec-validation/a\        validate-except {\n        };" $BASE_DIR/etc/bind/named.conf.options
	fi
	sed -i "/validate-except/a\           \"$ZONE\";" $BASE_DIR/etc/bind/named.conf.options
}

function add_entry(){
	ZONE=$1
	shift
	ENTRY=$@

	# check if zone exists
	STATUS=$(rndc zonestatus $ZONE 2>&1)
	if ! grep -q "\"$ZONE\"" $BASE_DIR/etc/bind/named.conf.local || ! [ -f $BASE_DIR/etc/bind/db.$ZONE ]; then
		echo "Zone does not exists!"
		exit 0
	fi
	echo "$ENTRY" >> $BASE_DIR/etc/bind/db.$ZONE
	# TODO: increment serial
	named-checkzone $ZONE $BASE_DIR/etc/bind/db.$ZONE
}

function enable_recursive(){
	# check if bind9 is running
	if ! rndc status | grep -q "server is up and running"; then
		echo "bind9 is not runnig! Please run --start first"
		exit 0
	fi
	echo "Enabling recursive queries"
	sed -i "/recursion/d" $BASE_DIR/etc/bind/named.conf.options
	sed -i "/listen-on-v6/a\        recursion yes;\n        allow-recursion { any; };" $BASE_DIR/etc/bind/named.conf.options
}

if [ "$ACTION" = "start" ]; then
  start
elif [ "$ACTION" = "stop" ]; then
  kill $(cat $PID_FILE)
elif [ "$ACTION" = "reload" ]; then
  reload
elif [ "$ACTION" = "add-zone" ]; then
  add_zone db.local ${ORIG_ARGS[@]}
  reload
elif [ "$ACTION" = "add-reverse-zone" ]; then
  add_zone db.127 ${ORIG_ARGS[@]}
  reload
elif [ "$ACTION" = "add-entry" ]; then
  add_entry ${ORIG_ARGS[@]}
  reload
elif [ "$ACTION" = "enable-recursive" ]; then
  enable_recursive
  reload
else
  echo "USAGE: $0 NAME [OPTIONS]"
  echo ""
  echo "  NAME         Name of the instance where this service will run (usually hostname)"
  echo "  --start      Start this service"
  echo "  --stop       Stop this service"
  echo "  -h|--help    Show this help message and exit"
  echo "  --add-zone ...           Add direct zone (see more information below)"
  echo "  --add-reverse-zone ...   Add reverse zone (see more information below)"
  echo "  --add-entry ...          Add an entry to a zone (see more information below)"
  echo "  --enable-recursive       Enable recursive query from any client"
  echo ""
  echo "--add-zone ZONE [FILE]"
  echo "  ZONE    FQDN (Full Qualified Domain Name) of the zone to be added. Example: xpto.com"
  echo "  FILE    Optional file containing the information to be loaded into the zone. When"
  echo "          not provided, an empty zone will be created."
  echo ""
  echo "--add-reverse-zone ZONE [FILE]"
  echo "  ZONE    Name of the reverse to be added. Example: 113.0.203.in-addr.arpa"
  echo "  FILE    Optional file containing the information to be loaded into the zone. When"
  echo "          not provided, an empty zone will be created."
  echo ""
  echo "--add-entry ZONE ENTRY"
  echo "  ZONE    Name of the zone where the entry will be added"
  echo "  ENTRY   DNS entry to be added on the ZONE. Example: ftp IN A 172.16.0.1"
  exit 0
fi
