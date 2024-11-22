#!/usr/bin/env python3

"""
multi_as.py: Scenario with multiple ASNs, firewall, host, NetTAP, SDN switches
"""

import sys
import socket
import time
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
        r101 = self.addHost('r101', ip='10.10.0.1/24', mynetworks=[])

        h101 = self.addHost('h101', ip='192.168.10.1/24', defaultRoute='via 192.168.10.254')
        h102 = self.addHost('h102', ip='192.168.10.2/24', defaultRoute='via 192.168.10.254')
        h103 = self.addHost('h103', ip='192.168.10.3/24', defaultRoute='via 192.168.10.254')

        srv101 = self.addHost('srv101', ip='172.16.10.1/24', defaultRoute='via 172.16.10.254')
        srv102 = self.addHost('srv102', ip='172.16.10.2/24', defaultRoute='via 172.16.10.254')
        srv103 = self.addHost('srv103', ip='172.16.10.3/24', defaultRoute='via 172.16.10.254')

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
                '-A FORWARD -s 172.16.10.0/24 -p udp --dport 53 -j ACCEPT',
                '-A FORWARD -d 172.16.10.1 -p tcp -m multiport --dports 80,443 -j ACCEPT',
                '-A FORWARD -d 172.16.10.2 -p tcp -m multiport --dports 25,143,110 -j ACCEPT',
            ],
            "nat": [
                #'-A POSTROUTING -o fw0-eth99 -j MASQUERADE',
            ]
        }

        fw101 = self.addFirewall('fw101', rules_v4=rules_v4_as100, defaultRoute='via 10.10.0.1', mynetworks=["192.168.10.0/24", "172.16.10.0/24"])

        s101 = self.addSwitch('s101')

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
        r201 = self.addHost('r201', ip='10.20.20.1/24', mynetworks=[])
        r202 = self.addHost('r202', ip='10.20.20.2/24', mynetworks=[])

        h201 = self.addHost('h201', ip='192.168.20.1/24', defaultRoute='via 192.168.20.254')

        ids201 = self.addHost('ids201', cls=K8sPod, image="hackinsdn/suricata:latest", env=[{"name": "SURICATA_IFACE", "value": "ids201-eth0"}, {"name": "SURICATA_HOME_NET", "value": "192.168.20.0/24,172.16.20.0/24"}])

        srv201 = self.addHost('srv201', ip='172.16.20.1/24', defaultRoute='via 172.16.20.254')

        secflood1 = self.addHost('secflood1', ip='192.168.20.10/24', routes=[("192.168.0.0/16", "192.168.20.254"), ("172.16.0.0/16", "192.168.20.254")], publish=["8443:443"], cls=K8sPod, image="hackinsdn/secflood:latest", env=[{"name": "SECFLOOD_INTF_INSIDE", "value": "secflood1-eth0"}, {"name": "SECFLOOD_GW_INSIDE", "value": "192.168.20.254"}, {"name": "SECFLOOD_INTF_OUTSIDE", "value": "secflood1-eth1"}])

        rules_v4_as200 = {
            "filter": [
                ':INPUT ACCEPT',
                ':OUTPUT ACCEPT',
                ':FORWARD ACCEPT',
            ],
            "nat": [
            ]
        }

        fw201 = self.addFirewall('fw201', rules_v4=rules_v4_as200, defaultRoute='via 10.20.0.1', mynetworks=["192.168.20.0/24", "172.16.20.0/24"])

        s201 = self.addSwitch('s201')
        s202 = self.addSwitch('s202')
        s203 = self.addSwitch('s203')

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

        ####################
        ## AS 300
        ####################
        r301 = self.addHost('r301', ip='10.30.0.1/24', mynetworks=[])

        h301 = self.addHost('h301', ip='192.168.30.1/24', defaultRoute='via 192.168.30.254')
        h302 = self.addHost('h302', ip='192.168.30.2/24', defaultRoute='via 192.168.30.254')
        h303 = self.addHost('h303', ip='192.168.30.3/24', defaultRoute='via 192.168.30.254')

        srv301 = self.addHost('srv301', ip='172.16.30.1/24', defaultRoute='via 172.16.30.254')

        rules_v4_as300 = {
            "filter": [
                ':INPUT ACCEPT',
                ':OUTPUT ACCEPT',
                ':FORWARD ACCEPT',
            ],
            "nat": [
            ]
        }

        fw301 = self.addFirewall('fw301', rules_v4=rules_v4_as300, defaultRoute='via 10.30.0.1', mynetworks=["192.168.30.0/24", "172.16.30.0/24"])

        s301 = self.addSwitch('s301', cls=LinuxBridge)

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
        r401 = self.addHost('r401', ip='10.40.40.1/30', mynetworks=["192.168.40.0/24"])
        r402 = self.addHost('r402', ip='10.40.40.2/30', mynetworks=[])

        h401 = self.addHost('h401', ip='192.168.40.1/24', defaultRoute='via 192.168.40.254')

        self.addLink(r401, r402)
        self.addLink(r401, h401, ipv4_node1="192.168.40.254/24")
        self.addLink(r401, secflood1, ipv4_node1="10.40.40.5/30", ipv4_node2="10.40.40.6/30")

        ####################
        ## AS 500
        ####################
        r501 = self.addHost('r501', ip='172.16.50.254/24', mynetworks=["172.16.50.0/24"])
        r502 = self.addHost('r502', ip='172.16.50.253/24', mynetworks=["172.16.50.0/24"])

        srv501 = self.addHost('srv501', ip='172.16.50.1/24', defaultRoute='via 172.16.50.254')
        srv502 = self.addHost('srv502', ip='172.16.50.2/24', defaultRoute='via 172.16.50.254')
        srv503 = self.addHost('srv503', ip='172.16.50.3/24', defaultRoute='via 172.16.50.254')

        s501 = self.addSwitch('s501', cls=LinuxBridge)

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
        controller=lambda name: RemoteController(name, ip=resolve_name(sys.argv[1]), port=6653),
    )
    net.start()

    AppManager(net, [net.get("srv501")], "http")
    AppManager(net, [net.get("srv501")], "https")

    net.routingHelper()

    CLI( net )

    net.stop()
