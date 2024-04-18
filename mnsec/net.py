"""
    Mininet-Sec: Emulation platform for studying and experimenting
                 cybersecurity tools in programmable networks
    author: Italo Valcy (italovalcy@ufba.br)

    This software is strongly based on Mininet project, as well
    as their forks/sub-projects Mininet-Wifi and Mini-NDN.
"""

import re
import socket

from itertools import chain, groupby
from threading import Thread as thread
from time import sleep
from sys import exit

from mininet.net import Mininet, MininetWithControlNet

import mnsec.apps.all
from mnsec.apps.app_manager import AppManager
from mnsec.nodelib import IPTablesFirewall, Host


VERSION = "0.1.0"


class Mininet_sec(Mininet):
    """Emulation platform for cybersecurity tools in programmable networks"""

    def __init__(self, workDir="/tmp/mnsec", apps="", **kwargs):
        """Create Mininet object.

           apps: string with list of host, app_name and optional params
           workDir: working directory where data will be saved"""
        self.apps = apps
        self.workDir = workDir

        self.cleanups = []
        kwargs.setdefault("host", Host)

        Mininet.__init__(self, **kwargs)

    def start(self):
        """Start nodes, apps and call Mininet to finish the startup."""
        for host in self.hosts:
            homeDir = f"{self.workDir}/{host.name}"
            host.params["homeDir"] = homeDir
            host.cmd(f"mkdir -p {homeDir}")
            host.cmd(f"export HOME={homeDir} && cd ~")
            if hasattr(host, "start"):
                host.start()

        # start apps
        for app_str in self.apps.split(","):
            if not app_str:
                continue
            app_spec = app_str.split(":")
            if len(app_spec) < 2:
                raise ValueError(f"Invalid apps param: {app_str}.")
            params = dict([i.split('=') for i in app_spec[2:]])
            host = self.get(app_spec[0])
            AppManager(self, [host], app_spec[1], **params)

        Mininet.start(self)

    def stop(self):
        for cleanup in self.cleanups:
            cleanup()
        Mininet.stop(self)

    def addFirewall( self, name='fw0', **params):
        """Add a Firewall to the Mininet-Sec network
           name: name of Firewall node
           params: other Firewall node params, notably:
               rules_v4: string, filename or dict(list) with IPv4 rules
               rules_v6: string, filename or dict(list) with IPv6 rules"""
        params.setdefault('ip', None)
        fw = self.addHost( name, cls=IPTablesFirewall, **params )
        return fw

    def addLink(
        self, node1, node2, ipv4_node1=None, ipv4_node2=None,
        ipv6_node1=None, ipv6_node2=None, **params
    ):
        """"Add a link from node1 to node2 and configure IP addr
            node1: source node (or name)
            node2: dest node (or name)
            ipv4_node1: IPv4 address to configure on node1
            ipv4_node2: IPv4 address to configure on node2
            ipv6_node1: IPv6 address to configure on node1
            ipv6_node2: IPv6 address to configure on node2
            params: additional link params (optional)
            returns: link object"""
        link = Mininet.addLink(self, node1, node2, **params)

        if ipv4_node1:
            link.intf1.setIP(ipv4_node1)
        if ipv4_node2:
            link.intf2.setIP(ipv4_node2)
        if ipv6_node1:
            link.intf1.setIP(ipv6_node1)
        if ipv6_node2:
            link.intf2.setIP(ipv6_node2)

        return link

class MininetSecWithControlNet(MininetWithControlNet):
    """Control network support."""
    pass
