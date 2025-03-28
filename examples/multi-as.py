#!/usr/bin/env python3

"""
multi_as.py: Scenario with multiple ASNs, firewall, host, NetTAP, SDN switches
"""

import sys
import socket
import time
import os
from mnsec.topo import Topo
from mnsec.net import Mininet_sec
from mnsec.cli import CLI
from mnsec.nodelib import IPTablesFirewall, NetworkTAP
from mnsec.apps.app_manager import AppManager
from mnsec.k8s import K8sPod

from mininet.node import RemoteController
from mininet.nodelib import LinuxBridge
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.util import run

def resolve_name(name):
    for _ in range(60):
        try:
            return socket.gethostbyname(name)
        except:
            time.sleep(2)
    raise TimeoutError(f"timeout while waiting for IP address of '{name}'")

class NetworkTopo( Topo ):
    """The topology definition."""
    def build(self):
        ####################
        ## AS 100
        ####################
        r101 = self.addHost('r101', ip='10.10.0.1/24', mynetworks=[], group="AS100", posX=179.12, posY=257.28)

        h101 = self.addHost('h101', ip='192.168.10.1/24', defaultRoute='via 192.168.10.254', group="AS100", dns_nameservers="172.16.50.3", posX=171.25, posY=348.24)
        h102 = self.addHost('h102', ip='192.168.10.2/24', defaultRoute='via 192.168.10.254', group="AS100", posX=124.07, posY=480.65)
        h103 = self.addHost('h103', ip='192.168.10.3/24', defaultRoute='via 192.168.10.254', group="AS100", posX=183.64, posY=454.71)

        srv101 = self.addHost('srv101', ip='172.16.10.1/24', defaultRoute='via 172.16.10.254', apps=[{"name": "http", "port": 80}, {"name": "https", "port": 443}, {"name": "dns", "port": 53}, {"name": "ssh", "port": 22}], group="AS100", posX=57.83, posY=396.56)
        srv102 = self.addHost('srv102', ip='172.16.10.2/24', defaultRoute='via 172.16.10.254', apps=[{"name": "smtp", "port": 25, "username": "teste", "password": "hackinsdn"}, {"name": "ssh", "port": 22}], group="AS100", posX=62.56, posY=470.10)
        srv103 = self.addHost('srv103', ip='172.16.10.3/24', defaultRoute='via 172.16.10.254', group="AS100", posX=192.10, posY=394.22)

        rules_v4_as100 = {
            "filter": [
                ':INPUT DROP',
                ':OUTPUT ACCEPT',
                ':FORWARD DROP',
                '-A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT',
                '-A INPUT -p icmp -j ACCEPT',
                '-A INPUT -s 192.168.10.0/24 -p udp --dport 53 -j ACCEPT',
                '-A INPUT -s 172.16.10.0/24 -p udp --dport 53 -j ACCEPT',
                '-A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT',
                '-A FORWARD -p icmp -j ACCEPT',
                '-A FORWARD -s 192.168.10.0/24 -p udp --dport 53 -j ACCEPT',
                '-A FORWARD -s 192.168.10.0/24 -p tcp -m multiport --dports 80,443 -j ACCEPT',
                '-A FORWARD -s 192.168.10.0/24 -d 172.16.10.0/24 -j ACCEPT',
                '-A FORWARD -s 172.16.10.0/24 -p udp --dport 53 -j ACCEPT',
                '-A FORWARD -d 172.16.10.1 -p tcp -m multiport --dports 80,443 -j ACCEPT',
                '-A FORWARD -d 172.16.10.1 -p udp -m multiport --dports 53 -j ACCEPT',
                '-A FORWARD -d 172.16.10.1 -p udp -m multiport --dports 123 -j DROP',
                '-A FORWARD -d 172.16.10.1 -p udp -m multiport --dports 500 -j ACCEPT',
                '-A FORWARD -d 172.16.10.2 -p tcp -m multiport --dports 25,143,110,587,993,995 -j ACCEPT',
                '-A FORWARD -d 172.16.10.3 -p tcp -m multiport --dports 22,80,443 -j ACCEPT',
                '-A FORWARD -j REJECT',
            ],
            "nat": [
                #'-A POSTROUTING -o fw0-eth99 -j MASQUERADE',
            ]
        }

        fw101 = self.addFirewall('fw101', rules_v4=rules_v4_as100, defaultRoute='via 10.10.0.1', mynetworks=["192.168.10.0/24", "172.16.10.0/24"], group="AS100", posX=98.40, posY=326.86)

        s101 = self.addSwitch('s101', cls=LinuxBridge, group="AS100", posX=115.96, posY=403.87)

        self.addLink(s101, h101)
        self.addLink(s101, h102)
        self.addLink(s101, h103)
        self.addLink(s101, srv101)
        self.addLink(s101, srv102)
        self.addLink(s101, srv103)
        self.addLink(s101, fw101, ipv4_node2="192.168.10.254/24")
        self.addLink(s101, fw101, ipv4_node2="172.16.10.254/24")
        self.addLink(r101, fw101, ipv4_node2="10.10.0.254/24")

        ####################
        ## AS 200
        ####################
        r201 = self.addHost('r201', ip='10.20.20.1/24', mynetworks=[], group="AS200", posX=284.26, posY=228.88)
        r202 = self.addHost('r202', ip='10.20.20.2/24', mynetworks=[], group="AS200", posX=448.33, posY=226.83)

        h201 = self.addHost('h201', ip='192.168.20.1/24', defaultRoute='via 192.168.20.254', group="AS200", posX=461.31, posY=303.97)

        kytos = self.addHost('kytos', ip=None, cls=K8sPod, image="hackinsdn/kytos:allinone", args=["-E"], env=[{"name": "MONGO_USERNAME", "value": "kytos"}, {"name": "MONGO_PASSWORD", "value": "kytos"}, {"name": "MONGO_DBNAME", "value": "kytos"}, {"name": "MONGO_HOST_SEEDS", "value": "127.0.0.1:27017"}], publish=["6653:6653", "8181:8181"], img_url="https://raw.githubusercontent.com/mininet-sec/mininet-sec/refs/heads/main/mnsec/assets/kytos-ng-icon.png", group="AS200", posX=273.40, posY=475.89)

        ids201 = self.addHost('ids201', ip=None, cls=K8sPod, image="hackinsdn/suricata:latest", env=[{"name": "SURICATA_IFACE", "value": "ids201-eth0"}, {"name": "SURICATA_HOME_NET", "value": "192.168.20.0/24,172.16.20.0/24"}], group="AS200", posX=341.68, posY=473.26)

        srv201 = self.addHost('srv201', ip='172.16.20.1/24', defaultRoute='via 172.16.20.254', group="AS200", posX=453.87, posY=479.01)

        secflood1 = self.addHost('secflood1', ip='192.168.20.10/24', routes=[("192.168.0.0/16", "192.168.20.254"), ("172.16.0.0/16", "192.168.20.254")], publish=["8443:443"], cls=K8sPod, image="hackinsdn/secflood:latest", env=[{"name": "SECFLOOD_INTF_INSIDE", "value": "secflood1-eth0"}, {"name": "SECFLOOD_GW_INSIDE", "value": "192.168.20.254"}, {"name": "SECFLOOD_INTF_OUTSIDE", "value": "secflood1-eth1"}], group="AS200", posX=448.45, posY=385.65)

        rules_v4_as200 = {
            "filter": [
                ':INPUT ACCEPT',
                ':OUTPUT ACCEPT',
                ':FORWARD ACCEPT',
            ],
            "nat": [
            ]
        }

        fw201 = self.addFirewall('fw201', rules_v4=rules_v4_as200, defaultRoute='via 10.20.0.1', mynetworks=["192.168.20.0/24", "172.16.20.0/24"], group="AS200", posX=291.72, posY=315.94)

        s201 = self.addSwitch('s201', group="AS200", posX=367.29, posY=285.56)
        s202 = self.addSwitch('s202', group="AS200", posX=400.56, posY=452.08)
        s203 = self.addSwitch('s203', group="AS200", posX=364.44, posY=386.75)
        s204 = self.addSwitch('s204', cls=LinuxBridge, group="AS200", posX=289.40, posY=386.38)

        self.addLink(r201, r202)
        self.addLink(s201, h201)
        self.addLink(s201, secflood1)
        self.addLink(s202, srv201)
        self.addLink(s203, fw201, ipv4_node2="192.168.20.254/24")
        self.addLink(s203, fw201, ipv4_node2="172.16.20.254/24")
        self.addLink(s201, s203)
        self.addLink(s202, s203)
        self.addLink(fw201, r201, ipv4_node1="10.20.0.254/24", ipv4_node2="10.20.0.1/24")
        self.addLink(s203, ids201)
        self.addLink(s204, fw201, ipv4_node2="10.20.1.1/24")
        self.addLink(s204, ids201, ipv4_node2="10.20.1.2/24")
        self.addLink(s204, kytos, ipv4_node2="10.20.1.3/24")

        ####################
        ## AS 300
        ####################
        r301 = self.addHost('r301', ip='10.30.0.1/24', mynetworks=[], group="AS300", posX=551.32, posY=316.87)

        h301 = self.addHost('h301', ip='192.168.30.1/24', defaultRoute='via 192.168.30.254', group="AS300", posX=627.75, posY=299.52)
        h302 = self.addHost('h302', ip='192.168.30.2/24', defaultRoute='via 192.168.30.254', group="AS300", posX=719.43, posY=259.25)
        h303 = self.addHost('h303', ip='192.168.30.3/24', defaultRoute='via 192.168.30.254', group="AS300", posX=683.84, posY=209.64)

        srv301 = self.addHost('srv301', ip='172.16.30.1/24', defaultRoute='via 172.16.30.254', group="AS300", posX=704.85, posY=318.41)

        rules_v4_as300 = {
            "filter": [
                ':INPUT ACCEPT',
                ':OUTPUT ACCEPT',
                ':FORWARD ACCEPT',
            ],
            "nat": [
            ]
        }

        fw301 = self.addFirewall('fw301', rules_v4=rules_v4_as300, defaultRoute='via 10.30.0.1', mynetworks=["192.168.30.0/24", "172.16.30.0/24"], group="AS300", posX=547.98, posY=223.21)

        s301 = self.addSwitch('s301', cls=LinuxBridge, group="AS300", posX=621.68, posY=220.83)

        self.addLink(s301, h301)
        self.addLink(s301, h302)
        self.addLink(s301, h303)
        self.addLink(s301, srv301)
        self.addLink(s301, fw301, ipv4_node2="192.168.30.254/24")
        self.addLink(s301, fw301, ipv4_node2="172.16.30.254/24")
        self.addLink(r301, fw301, ipv4_node2="10.30.0.254/24")

        ####################
        ## AS 400
        ####################
        r401 = self.addHost('r401', ip='10.40.40.1/30', mynetworks=["192.168.40.0/24"], group="AS400", posX=558.36, posY=418.30)
        r402 = self.addHost('r402', ip='10.40.40.2/30', mynetworks=["172.16.40.0/24"], group="AS400", posX=700.52, posY=422.00)

        h401 = self.addHost('h401', ip='192.168.40.1/24', defaultRoute='via 192.168.40.254', group="AS400", posX=540.55, posY=471.86)

        srv401 = self.addHost('srv401', cls=K8sPod, image="hackinsdn/vuln-ssl-heartbleed:latest", ip="172.16.40.1/24", defaultRoute="via 172.16.40.254", group="AS400", posX=647.53, posY=480.82)

        self.addLink(r401, r402)
        self.addLink(r401, h401, ipv4_node1="192.168.40.254/24")
        self.addLink(r402, srv401, ipv4_node1="172.16.40.254/24")
        self.addLink(r401, secflood1, ipv4_node1="10.40.40.5/30", ipv4_node2="10.40.40.6/30")

        ####################
        ## AS 500
        ####################
        r501 = self.addHost('r501', ip='172.16.50.254/24', mynetworks=["172.16.50.0/24"], group="AS500", posX=791.27, posY=376.31)
        r502 = self.addHost('r502', ip='172.16.50.253/24', mynetworks=["172.16.50.0/24"], group="AS500", posX=785.14, posY=470.72)

        srv501 = self.addHost('srv501', ip='172.16.50.1/24', defaultRoute='via 172.16.50.254', apps=[{"name": "http", "port": 80}, {"name": "https", "port": 443}], group="AS500", posX=866.28, posY=292.85)
        srv502 = self.addHost('srv502', ip='172.16.50.2/24', defaultRoute='via 172.16.50.254', group="AS500", posX=795.97, posY=288.68)
        srv503_postStart = [
            "service-mnsec-bind9.sh srv503 --start",
            "service-mnsec-bind9.sh srv503 --enable-recursion",
            "service-mnsec-bind9.sh srv503 --add-zone hackinsdn.com",
            "service-mnsec-bind9.sh srv503 --add-entry hackinsdn.com \"iodine IN A 172.16.50.2\"",
            "service-mnsec-bind9.sh srv503 --add-entry hackinsdn.com \"testetun IN NS iodine\"",
        ]
        srv503 = self.addHost('srv503', ip='172.16.50.3/24', defaultRoute='via 172.16.50.254', group="AS500", postStart=srv503_postStart, posX=867.15, posY=473.60)

        s501 = self.addSwitch('s501', cls=LinuxBridge, group="AS500", posX=857.91, posY=367.15)

        self.addLink(s501, srv501, cls=TCLink, bw=10)
        self.addLink(s501, srv502)
        self.addLink(s501, srv503)
        self.addLink(s501, r501)
        self.addLink(s501, r502)
        self.addLink(r501, r502, ipv4_node1="10.50.50.1/24", ipv4_node2="10.50.50.2/24")

        ##############################
        ## Inter-AS links
        ##############################
        self.addLink(r101, r201, ipv4_node1="10.10.20.1/24", ipv4_node2="10.10.20.2/24")
        self.addLink(r202, r401, ipv4_node1="10.20.40.1/24", ipv4_node2="10.20.40.2/24")
        self.addLink(r301, r401, ipv4_node1="10.30.40.1/24", ipv4_node2="10.30.40.2/24")
        self.addLink(r301, r501, ipv4_node1="10.30.50.1/24", ipv4_node2="10.30.50.2/24")
        self.addLink(r402, r502, ipv4_node1="10.40.50.1/24", ipv4_node2="10.40.50.2/24")


if __name__ == '__main__':
    setLogLevel( 'info' )
    info( 'Starting Mininet-Sec\n' )
    net = Mininet_sec(
        topo=NetworkTopo(),
        controller=lambda name: RemoteController(name, ip="127.0.0.1", port=6653),
    )
    net.start()

    net.routingHelper()

    CLI( net )

    net.stop()
