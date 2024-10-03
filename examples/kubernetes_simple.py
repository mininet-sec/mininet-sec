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
    """A scenario with Kubernetes and standard host via OpenFlow switch."""
    def build(self):
        h1 = self.addHost('h1')
        h2 = self.addHost('h2', cls=K8sPod)
        s1 = self.addSwitch('s1')
        self.addLink(s1, h1)
        self.addLink(s1, h2)

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
