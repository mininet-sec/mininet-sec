#!/usr/bin/env python3

"""
p4switch.py: Scenario with P4 switches (Bmv2Switch) and hosts
"""

import os
from mnsec.topo import Topo
from mnsec.net import Mininet_sec
from mnsec.cli import CLI
from mnsec.bmv2 import Bmv2Switch

from mininet.node import NullController
from mininet.log import setLogLevel, info

CUR_DIR = os.path.dirname(os.path.realpath(__file__))

class NetworkTopo( Topo ):
    """A scenario with P4 switches and hosts."""
    def build(self):
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        s1 = self.addSwitch('s1', cls=Bmv2Switch, json=f"{CUR_DIR}/simple_router.json")
        s2 = self.addSwitch('s2', cls=Bmv2Switch, json=f"{CUR_DIR}/simple_router.json")
        s3 = self.addSwitch('s3', cls=Bmv2Switch, json=f"{CUR_DIR}/simple_router.json")
        self.addLink(s1, h1)
        self.addLink(s2, h2)
        self.addLink(s3, h3)
        self.addLink(s1, s2)
        self.addLink(s2, s3)
        self.addLink(s3, s1)

def run():
    "Test P4 switch scenario"
    info( 'Starting Mininet-Sec\n' )
    topo = NetworkTopo()
    net = Mininet_sec( topo=topo, controller=NullController )
    net.start()
    CLI( net )
    net.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    run()
