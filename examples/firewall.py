#!/usr/bin/env python3

"""
firewall-legacynet.py: Scenario with Linux Firewall, Client hosts and servers

This example leverages the IPTablesFirewall node (Linux standard firewall),
which also works as a router for hosts (clients firewall zone) and servers
(DMZ firewall zone), a typical scenario for many organizations. Furthermore,
we also simulate 'Internet' services by instantiating a new host on the
outside Firewall zone. Legacy switches (LinuxBridge) is used to connect the
hosts and the Firewall.
"""

from mnsec.topo import Topo
from mnsec.net import Mininet_sec
from mnsec.cli import CLI
from mnsec.nodelib import IPTablesFirewall, NetworkTAP
from mnsec.apps.app_manager import AppManager

from mininet.node import NullController
from mininet.nodelib import LinuxBridge
from mininet.log import setLogLevel, info
from mininet.util import run

class NetworkTopo( Topo ):
    """A scenario with IPTables firewall, servers and client hosts."""
    def build(self):
        h1 = self.addHost('h1', ip='192.168.1.101/24', defaultRoute='via 192.168.1.1')
        h2 = self.addHost('h2', ip='192.168.1.102/24', defaultRoute='via 192.168.1.1')
        h3 = self.addHost('h3', ip='192.168.1.103/24', defaultRoute='via 192.168.1.1')
        lo1 = self.addHost('lo1')

        srv1 = self.addHost('srv1', ip='10.0.0.1/24', defaultRoute='via 10.0.0.254')
        srv2 = self.addHost('srv2', ip='10.0.0.2/24', defaultRoute='via 10.0.0.254')

        # default route via Firewall to make things easier
        outside = self.addHost('o1', ip='203.0.113.1/24', defaultRoute='via 203.0.113.200')

        rules_v4 = {
            "filter": [
                ':INPUT DROP',
                ':OUTPUT ACCEPT',
                ':FORWARD DROP',
                '-A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT',
                '-A INPUT -p icmp -j ACCEPT',
                '-A INPUT -s 192.168.1.0/24 -p udp --dport 53 -j ACCEPT',
                '-A INPUT -s 10.0.0.0/24 -p udp --dport 53 -j ACCEPT',
                '-A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT',
                '-A FORWARD -p icmp -j ACCEPT',
                '-A FORWARD -s 192.168.1.0/24 -p tcp -m multiport --dports 80,443 -j ACCEPT',
                '-A FORWARD -d 10.0.0.1 -p tcp -m multiport --dports 80,443 -j ACCEPT',
                '-A FORWARD -d 10.0.0.2 -p tcp -m multiport --dports 25,143,110 -j ACCEPT',
                '-A FORWARD -o fw0-eth99 -j ACCEPT'
            ],
            "nat": [
                '-A POSTROUTING -o fw0-eth99 -j MASQUERADE',
            ]
        }

        fw0 = self.addFirewall('fw0', rules_v4=rules_v4, defaultRoute='via 172.31.99.254')

        s1 = self.addSwitch('s1', cls=LinuxBridge)
        s2 = self.addSwitch('s2', cls=LinuxBridge)
        nettap1 = self.addSwitch('nettap1', cls=NetworkTAP)
        s99 = self.addSwitch('s99', cls=LinuxBridge)

        self.addLink(s1, h1)
        self.addLink(s1, h2)
        self.addLink(s1, h3)
        self.addLink(h3, lo1)
        self.addLink(s2, srv1)
        self.addLink(s2, srv2)
        self.addLink(s1, fw0, ipv4_node2='192.168.1.1/24')
        self.addLink(s2, fw0, ipv4_node2='10.0.0.254/24')
        self.addLink(s99, fw0, ipv4_node2='172.31.99.1/24', port2=99)
        self.addLink(nettap1, fw0, ipv4_node2='203.0.113.200/24')
        self.addLink(nettap1, outside)

def main():
    "Test Firewall scenario"
    info( 'Starting Mininet-Sec\n' )
    topo = NetworkTopo()
    net = Mininet_sec( topo=topo, controller=NullController, captureDir="/var/tmp" )
    net.start()
    AppManager(net, [net.get("srv1")], "http")
    AppManager(net, [net.get("srv1")], "https")
    AppManager(net, [net.get("srv2")], "smtp")
    AppManager(net, [net.get("srv2")], "imap")
    AppManager(net, [net.get("lo1")], "loopback")
    info( '*** Configure host bridges:\n' )
    run( 'iptables -I FORWARD -i s1-+ -j ACCEPT' )
    run( 'iptables -I FORWARD -i s2-+ -j ACCEPT' )
    run( 'iptables -I FORWARD -i s99-+ -j ACCEPT' )
    run( 'ip addr add 172.31.99.254/24 dev s99' )
    run( 'iptables -t nat -A POSTROUTING -s 172.31.99.0/24 -j MASQUERADE')
    info( '*** Routing Table on firewall:\n' )
    info( net[ 'fw0' ].cmd( 'ip route show' ) )
    info( '*** IPTables rules on filter table (v4):\n' )
    info( net[ 'fw0' ].cmd( 'iptables -L -n -v' ) )
    info( '*** IPTables rules on filter table (v6):\n' )
    info( net[ 'fw0' ].cmd( 'ip6tables -L -n -v' ) )
    CLI( net )
    net.stop()
    info( '*** Cleanup host bridges:\n' )
    run( 'iptables -D FORWARD -i s1-+ -j ACCEPT' )
    run( 'iptables -D FORWARD -i s2-+ -j ACCEPT' )
    run( 'iptables -D FORWARD -i s99-+ -j ACCEPT' )
    run( 'iptables -t nat -D POSTROUTING -s 172.31.99.0/24 -j MASQUERADE')


if __name__ == '__main__':
    setLogLevel( 'info' )
    main()
