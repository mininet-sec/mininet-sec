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
from collections import defaultdict
import networkx as nx

from itertools import chain, groupby
from threading import Thread as thread
from time import sleep
from contextlib import redirect_stdout
from io import StringIO
from subprocess import call
import yaml

from mininet.net import Mininet, MininetWithControlNet
from mininet.node import OVSSwitch
from mininet.log import info, error, output, warn, debug
from mininet.topo import Topo
from mininet.util import quietRun
from mininet import cli, util

import mnsec.apps.all
from mnsec.apps.app_manager import AppManager
from mnsec.nodelib import ( IPTablesFirewall, Host, NetworkTAP, OVSSwitch,
                            LinuxBridge, RTSchedHost, CFSSchedHost )
from mnsec.api_server import APIServer
from mnsec.k8s import K8sPod
from mnsec.link import VxLanLink, L2tpLink

from mininet.node import ( CPULimitedHost, Controller, OVSController,
                           Ryu, NOX, RemoteController,
                           DefaultController, NullController,
                           UserSwitch, OVSBridge,
                           IVSSwitch )
from mininet.link import Link, TCLink, TCULink, OVSLink
from mininet.topo import ( SingleSwitchTopo, LinearTopo,
                           SingleSwitchReversedTopo, MinimalTopo )
from mininet.topolib import TreeTopo, TorusTopo

# built in topologies, created only when run
TOPODEF = 'minimal'
TOPOS = { 'minimal': MinimalTopo,
          'linear': LinearTopo,
          'reversed': SingleSwitchReversedTopo,
          'single': SingleSwitchTopo,
          'tree': TreeTopo,
          'torus': TorusTopo,
}

SWITCHDEF = 'default'
SWITCHES = { 'user': UserSwitch,
             'ovs': OVSSwitch,
             'ovsbr' : OVSBridge,
             # Keep ovsk for compatibility with 2.0
             'ovsk': OVSSwitch,
             'ivs': IVSSwitch,
             'lxbr': LinuxBridge,
             'nettap': NetworkTAP,
             'default': OVSSwitch,
}
SWITCHES_REV = {
    "UserSwitch": "user",
    "OVSSwitch": "default",
    "OVSBridge": "ovsbr",
    "LinuxBridge": "lxbr",
    "NetworkTAP": "nettap",
}

HOSTDEF = 'proc'
HOSTS = { 'proc': Host,
          'rt': RTSchedHost,
          'cfs': CFSSchedHost,
          'default': Host,
          'k8spod': K8sPod,
          'iptables': IPTablesFirewall,
}
HOSTS_REV = {
    "Host": "default",
    "RTSchedHost": "rt",
    "CFSSchedHost": "cfs",
    "K8sPod": "k8spod",
    "IPTablesFirewall": "iptables",
}

CONTROLLERDEF = 'default'
CONTROLLERS = { 'ref': Controller,
                'ovsc': OVSController,
                'nox': NOX,
                'remote': RemoteController,
                'ryu': Ryu,
                'default': DefaultController,  # Note: overridden below
                'none': NullController,
}
CONTROLLERS_REV = {
    "Controller": "ref",
    "OVSController": "ovsc",
    "NOX": "nox",
    "RemoteController": "remote",
    "Ryu": "ryu",
    "DefaultController": "default",
    "NullController": "none",
}

LINKDEF = 'default'
LINKS = { 'default': Link,  # Note: overridden below
          'tc': TCLink,
          'tcu': TCULink,
          'ovs': OVSLink,
          'vxlan': VxLanLink,
          'l2tp': L2tpLink,
}
LINKS_REV = {
    "Link": "default",
    "TCLink": "tc",
    "TCULink": "tcu",
    "OVSLink": "ovs",
    "VxLanLink": "vxlan",
    "L2tpLink": "l2tp",
}

VERSION = "1.1.0"

UUID_PATTERN = re.compile(r'^[\da-f]{8}-([\da-f]{4}-){3}[\da-f]{12}$')

class Mininet_sec(Mininet):
    """Emulation platform for cybersecurity tools in programmable networks"""

    def __init__(
        self, topoFile="", workDir="/tmp/mnsec", apps="", enable_api=True,
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
        self.topo_dict = {}
        self.cli = None

        if topoFile:
            kwargs["topo"] = self.buildTopoFromFile(topoFile)
            kwargs.update(self.processTopoSettings())

        if self.run_api_server:
            self.api_server = APIServer(self)
            self.api_server.start()
        else:
            self.api_server = None

        kwargs.setdefault("host", Host)
        kwargs.setdefault("switch", OVSSwitch)
        # changing ipBase to reduce chances of conflict
        kwargs.setdefault("ipBase", "10.255.0.0/16")
        Mininet.__init__(self, **kwargs)

    def buildTopoFromFile(self, topoFile):
        """Build topology from YAML file"""
        try:
            self.topo_dict = yaml.load(open(topoFile), Loader=yaml.Loader)
        except Exception as exc:
            raise ValueError(f"Invalid topology file. Error reading topology: {exc}")
        settings = self.topo_dict.get("settings", {})
        topo = Topo()
        for host in self.topo_dict.get("hosts", {}):
            host_opts = self.topo_dict["hosts"][host] or {}
            # TODO: process settings["env"]
            cls = HOSTS[host_opts.get("kind", settings.get("hosts_kind", HOSTDEF))]
            topo.addHost(host, cls=cls, **host_opts)
        for switch in self.topo_dict.get("switches", {}):
            sw_opts = self.topo_dict["switches"][switch] or {}
            cls = SWITCHES[sw_opts.get("kind", settings.get("switches_kind", SWITCHDEF))]
            topo.addSwitch(switch, cls=cls, **sw_opts)
        for link in self.topo_dict.get("links", []):
            cls = LINKS[link.get("kind", settings.get("links_kind", LINKDEF))]
            node1 = link.pop("node1")
            node2 = link.pop("node2")
            topo.addLink(node1, node2, cls=cls, **link)
        return topo

    def processTopoSettings(self):
        """When using the yaml topology, process settings attribute"""
        if not self.topo_dict.get("settings") or not isinstance(self.topo_dict["settings"], dict):
            return
        mnsec_attrs = [
            "apps",
            "workDir",
            "sflow_enabled",
            "sflow_collector",
            "sflow_sampling",
            "sflow_polling",
            "run_api_server",
        ]
        for attr in mnsec_attrs:
            if self.topo_dict["settings"].get(attr):
                setattr(self, attr, self.topo_dict["settings"][attr])
        return self.topo_dict["settings"].get("mininet", {})

    def buildFromTopo( self, topo=None ):
        """Build mininet from a topology object
           At the end of this function, everything should be connected
           and up."""

        # Possibly we should clean up here and/or validate
        # the topo
        if self.cleanup:
            pass

        info( '*** Creating network\n' )

        if not self.controllers and self.controller:
            # Add a default controller
            info( '*** Adding controller\n' )
            classes = self.controller
            if not isinstance( classes, list ):
                classes = [ classes ]
            for i, cls in enumerate( classes ):
                # Allow Controller objects because nobody understands partial()
                if isinstance( cls, Controller ):
                    self.addController( cls )
                else:
                    self.addController( 'c%d' % i, cls )

        info( '*** Adding hosts:\n' )
        for hostName in topo.hosts():
            self.addHost( hostName, **topo.nodeInfo( hostName ) )
            info( hostName + ' ' )

        info( '\n*** Running hosts post-startup:\n ')
        for host in self.hosts:
            if hasattr( host, 'post_startup' ):
                info( host.name + ' ' )
                host.post_startup()

        info( '\n*** Adding switches:\n' )
        for switchName in topo.switches():
            # A bit ugly: add batch parameter if appropriate
            params = topo.nodeInfo( switchName)
            cls = params.get( 'cls', self.switch )
            if hasattr( cls, 'batchStartup' ):
                params.setdefault( 'batch', True )
            self.addSwitch( switchName, **params )
            info( switchName + ' ' )

        info( '\n*** Adding links:\n' )
        for srcName, dstName, params in topo.links(
                sort=True, withInfo=True ):
            self.addLink( **params )
            info( '(%s, %s) ' % ( srcName, dstName ) )

        info( '\n' )

    def start(self):
        """Start nodes, apps and call Mininet to finish the startup."""
        for host in self.hosts:
            self.startHost(host)
            for app in host.params.get("apps", []):
                AppManager(self, [host], app["name"], **app)

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

    def setupHostHomeDir(self, host):
        """Setup host home dir."""
        host = host if not isinstance( host, str ) else self[ host ]
        homeDir = f"{self.workDir}/{host.name}"
        host.params["homeDir"] = homeDir
        host.cmd(f"mkdir -p {homeDir}")
        return homeDir

    def setupHostDNS(self, host):
        """Configure node's resolv.conf DNS resolver from parameters:
           dns_nameservers (str): space-separated list of DNS servers addresses
           dns_extra_opts (str): extra options to be added to resolv.conf
        """
        host = host if not isinstance( host, str ) else self[ host ]
        extra_opts = host.params.get("dns_extra_opts", "")
        config = [
            f"nameserver {server}"
            for server in host.params.get("dns_nameservers", "").split()
        ]
        if extra_opts:
            config.append(extra_opts)
        conf_str = "\n".join(config)
        conf_file = f"{host.params['homeDir']}/resolv.conf"
        host.cmd(f"echo -e '{conf_str}' > {conf_file}", shell=True)
        host.cmd(f"mount --bind {conf_file} /etc/resolv.conf")


    def startHost(self, host):
        """Start hosts."""
        if not host:
            return
        host.cmd(f"export HOSTNAME={host.name}")
        homeDir = self.setupHostHomeDir(host)
        host.cmd(f"export HOME={homeDir} && cd ~")
        self.setupHostDNS(host)
        if hasattr(host, "start"):
            host.start()
        for cmd in host.params.get("postStart", []):
            host.cmd(cmd)

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

        info("*** Cleanup K8s Pods\n")
        K8sPod.wait_deleted()

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

        if isinstance(node1, K8sPod) or isinstance(node2, K8sPod):
            params["cls"] = L2tpLink

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

    def routingHelper(self):
        networks = {}
        g = nx.Graph()

        for host in self.hosts:
            mynetworks = getattr(host, "params", {}).get("mynetworks")
            if mynetworks is None:
                continue
            networks[host.name] = mynetworks 
            g.add_node(host.name)

        for link in self.links:
            if (
                link.intf1.node == link.intf2.node or
                link.intf1.node.name not in g.nodes() or
                link.intf2.node.name not in g.nodes()
            ):
                continue
            n1 = link.intf1.node.name
            n2 = link.intf2.node.name
            g.add_edge(n1, n2, net={n1: link.intf1.ip, n2: link.intf2.ip})

        known_routes = defaultdict(list)
        for node1 in g.nodes():
            for node2 in g.nodes():
                if node1 == node2:
                    continue
                try:
                    paths = list(nx.all_shortest_paths(g, source=node1, target=node2))
                except:
                    warn(f"\nFailed to find a path from {node1} to {node2}")
                    continue
                for path in paths:
                    prev_hop = path[0]
                    for hop in path[1:]:
                        hop_net = g.get_edge_data(prev_hop, hop)["net"]
                        for net in networks[node1]:
                            route = f"{net} via {hop_net[prev_hop]}"
                            if route in known_routes[hop]:
                                 continue
                            self[hop].cmd(f"ip route add {route}")
                            known_routes[hop].append(route)
                        prev_hop = hop
            # add a generic default route with loopback next-hop and low
            # priority (high metric). This will help packets go through in case
            # RPF is configured in loose mode (net.ipv4.conf.all.rp_filter=1)
            self[node1].cmd(f"ip route add default dev lo metric 4294967295")

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

    def nmap(self, node, *args):
        """Run Nnmap from a given host."""
        node = node if not isinstance( node, str ) else self[ node ]
        output(node.cmd("nmap " + " ".join(args)))

    def getObjKind(self, obj):
        name = obj.__class__.__name__
        if name in HOSTS_REV:
            return HOSTS_REV[name]
        if name in SWITCHES_REV:
            return SWITCHES_REV[name]
        if name in LINKS_REV:
            return LINKS_REV[name]
        if name in CONTROLLERS_REV:
            return CONTROLLERS_REV[name]
        return None


class MininetSecWithControlNet(MininetWithControlNet):
    """Control network support."""
    pass
