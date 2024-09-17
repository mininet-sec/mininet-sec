#!/bin/bash

apt-get update
apt-get install -y iputils-ping net-tools tcpdump x11-xserver-utils xterm iperf socat telnet tmux git iptables-persistent bridge-utils nmap hping3 mininet iperf3 hydra iproute2 python3-pip libpq-dev openvswitch-testcontroller curl d-itg
python3 -m pip install --break-system-packages .
service openvswitch-switch start
