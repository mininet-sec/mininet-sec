"""
    Mininet-Sec: Emulation platform for studying and experimenting
                 cybersecurity tools in programmable networks
    author: Italo Valcy (italovalcy@ufba.br)

    This software is strongly based on Mininet project, as well
    as their forks/sub-projects Mininet-Wifi and Mini-NDN.
"""

import re
import socket
import sys

from itertools import chain, groupby
from threading import Thread as thread
from time import sleep
from contextlib import redirect_stdout
from io import StringIO
from subprocess import call

from mininet.net import Mininet, MininetWithControlNet
from mininet.node import OVSSwitch
from mininet.log import info, error, warn, debug
from mininet.util import quietRun
from mininet import cli, util

import mnsec.apps.all
from mnsec.apps.app_manager import AppManager
from mnsec.nodelib import IPTablesFirewall, Host
from mnsec.api_server import APIServer


VERSION = "0.1.0"

UUID_PATTERN = re.compile(r'^[\da-f]{8}-([\da-f]{4}-){3}[\da-f]{12}$')

class Mininet_sec(Mininet):
    """Emulation platform for cybersecurity tools in programmable networks"""

    def __init__(
        self, workDir="/tmp/mnsec", apps="", enable_api=True,
        enable_sflow=False, sflow_collector="127.0.0.1:6343", sflow_sampling=64, sflow_polling=10,
        **kwargs,
    ):
        """Create Mininet object.

           apps: string with list of host, app_name and optional params
           workDir: working directory where data will be saved
           enable_sflow: enable sFlow agent on all OVSSwitch nodes
           sflow_collector: IP address and port of the sFlow collector
           sflow_sampling: sFlow sampling rate (collects 1 every N packets)
           sflow_polling: polling interval (send collected flows every N seconds)
        """
        self.apps = apps
        self.workDir = workDir
        self.sflow_enabled = enable_sflow
        self.sflow_collector = sflow_collector
        self.sflow_sampling = sflow_sampling
        self.sflow_polling = sflow_polling
        self.run_api_server = enable_api

        self.cleanups = []
        self.cli = None

        if self.run_api_server:
            self.api_server = APIServer(self)
        else:
            self.api_server = None

        kwargs.setdefault("host", Host)
        Mininet.__init__(self, **kwargs)

    def start(self):
        """Start nodes, apps and call Mininet to finish the startup."""
        for host in self.hosts:
            self.startHost(host)

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

        if self.sflow_enabled:
            self.enable_sflow()

        if self.run_api_server:
            self.api_server.setup()
            self.api_server.start()

    def setupHostHomeDir(self, host):
        """Setup host home dir."""
        host = host if not isinstance( host, str ) else self[ host ]
        homeDir = f"{self.workDir}/{host.name}"
        host.params["homeDir"] = homeDir
        host.cmd(f"mkdir -p {homeDir}")
        return homeDir

    def startHost(self, host):
        """Start hosts."""
        if not host:
            return
        homeDir = self.setupHostHomeDir(host)
        host.cmd(f"export HOME={homeDir} && cd ~")
        if hasattr(host, "start"):
            host.start()

    def enable_sflow(self):
        """Enable sflow on switches."""
        info("*** Enabling sFlow:\n")
        cmd, names = ("", "")
        for switch in self.switches:
            if not isinstance(switch, OVSSwitch):
                continue
            cmd += f" -- set bridge {switch.name} sflow=@sflow"
            names += f"{switch.name} "
        if not cmd:
            return
        sflow = (
            f"ovs-vsctl -- --id=@sflow create sflow target=\"{self.sflow_collector}\""
            f" sampling={self.sflow_sampling} polling={self.sflow_sampling} --"
        )
        info(f"{names}\n")
        cmdOut = quietRun(sflow + cmd)
        if UUID_PATTERN.match(cmdOut.lower()):
            self.sflow_uuid = cmdOut
        else:
            error(f"Failed to enable sflow: {cmdOut}")

    def stop(self):
        for cleanup in self.cleanups:
            cleanup()

        if self.run_api_server:
            self.api_server.stop()

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
        node1 = node1 if not isinstance( node1, str ) else self[ node1 ]
        node2 = node2 if not isinstance( node2, str ) else self[ node2 ]
        # fix for cases where node1 == node2
        if node1.name == node2.name:
            newPort = node1.newPort()
            if "port1" not in params:
                params["port1"] = newPort
                newPort += 1
            if "port2" not in params or params["port2"] == params["port1"]:
                params["port2"] = newPort

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

    def run_cli(self, cmd):
        """Run on CLI if available."""
        if not self.cli:
            return

        def wrapper_output(msg, *args, **kwargs):
            print(msg, *args, end="")

        def wrapper_do_sh(self, line):
            print(quietRun(line), end="")

        orig_cli_output = cli.output
        orig_util_output = util.output
        orig_cli_do_sh = cli.CLI.do_sh
        orig_stdout = sys.stdout
        cli.CLI.do_sh = wrapper_do_sh
        cli.output = wrapper_output
        util.output = wrapper_output
        io_str = StringIO()
        sys.stdout = io_str

        try:
            self.cli.onecmd(cmd)
            cmdOut = io_str.getvalue()
        except Exception as exc:
            cmdOut = f"Error running cmd: {exc}"
        finally:
            sys.stdout = orig_stdout
            cli.output = orig_cli_output
            util.output = orig_util_output
            cli.CLI.do_sh = orig_cli_do_sh

        return cmdOut

class MininetSecWithControlNet(MininetWithControlNet):
    """Control network support."""
    pass
