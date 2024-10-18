#!/usr/bin/env python3

"""
p4switch.py: Scenario with P4 switches (Bmv2Switch) and hosts
"""

import os
from subprocess import call
from mnsec.topo import Topo
from mnsec.net import Mininet_sec
from mnsec.cli import CLI
from mnsec.k8s import K8sPod

from mininet.node import NullController
from mininet.log import setLogLevel, info

class NetworkTopo( Topo ):
    """Linear topology with 3 OF switches and 3 hosts: 2 netns + 1 k8s."""
    def build(self):
        K8sPod.setup_node_affinity(["ids-go", "ids-rn"])
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3', cls=K8sPod, publish=["8080:8000"], command=["/usr/bin/python3", "-m", "http.server", "8000"])
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        self.addLink(s1, h1)
        self.addLink(s2, h2)
        self.addLink(s3, h3)
        self.addLink(s1, s2)
        self.addLink(s2, s3)

def run():
    """Test Kubernetes Pod"""
    info( 'Starting Mininet-Sec\n' )
    topo = NetworkTopo()
    net = Mininet_sec( topo=topo, controller=NullController )
    net.start()
    call("sh examples/kubernetes_linear3-flows.sh", shell=True )
    CLI( net )
    net.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    run()
