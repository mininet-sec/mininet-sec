#!/usr/bin/env python3

"""
p4switch.py: Scenario with P4 switches (Bmv2Switch) and hosts
"""

import os
from mnsec.topo import Topo
from mnsec.net import Mininet_sec
from mnsec.cli import CLI
from mnsec.k8s import K8sPod

from mininet.node import NullController
from mininet.log import setLogLevel, info

class NetworkTopo( Topo ):
    """Linear topology with 3 OF switches and 3 hosts: 2 netns + 1 k8s."""
    def build(self):
        # Victim
        h1 = self.addHost('h1', apps=[{"name": "ssh", "port": 22}, {"name": "http", "port": 80}, {"name": "mysql"}])
        # IDS
        h2 = self.addHost('h2', cls=K8sPod, image="hackinsdn/suricata:latest", command=["/docker-entrypoint.sh"], env=[{"name": "SURICATA_IFACE", "value": "h2-eth0"}, {"name": "SURICATA_HOME_NET", "value": "192.168.20.0/24,172.16.20.0/24"}, {"name": "KYTOS_URL", "value": "http://kytos:8181"}, {"name": "BLOCKING_DURATION", "value": "300"}])
        # Attacker
        h3 = self.addHost('h3', cls=K8sPod)
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        self.addLink(s1, h1)
        self.addLink(s2, h2)  # by default h2 interface will be h2-eth0
        self.addLink(s3, h3)
        self.addLink(s1, s2)
        self.addLink(s2, s3)

def run():
    """Test Kubernetes Pod"""
    info( 'Starting Mininet-Sec\n' )
    topo = NetworkTopo()
    net = Mininet_sec( topo=topo, controller=NullController )
    net.start()
    CLI( net )
    net.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    run()
