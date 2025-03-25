"""
Node objects for Mininet-Sec

LinuxServer: provides minimal functionatility to work as a server
"""
import os
import re
import traceback

from mininet.nodelib import LinuxBridge as MN_Lxbr
from mininet.node import Node
from mininet.node import OVSSwitch as MN_OVS
from mininet.link import Intf
from mininet.log import info, error, warn, debug
from mininet.moduledeps import pathCheck
from mininet.clean import addCleanupCallback, sh

from mnsec.portforward import portforward
from mnsec.util import makeIntfSingle, parse_publish


def cleanup():
    info("*** Cleaning up Linux bridges\n")
    bridges = sh("brctl show | tail +2 | cut -f1").splitlines()
    for br in bridges:
        sh(f"ip link set down {br} && brctl delbr {br}")


addCleanupCallback(cleanup)

class OVSSwitch(MN_OVS):
    """Mininet-Sec openvswitch."""
    display_image = "switch-of.png"


class Host( Node ):
    """Mininet-Sec host."""
    display_image = "computer.png"

    def post_startup(self):
        """Run steps after host has been created"""
        self.setup_published_ports()

    def setup_published_ports(self):
        """Setup published ports using socat."""
        for kw in parse_publish(self.params.get("publish", [])):
            h1, p1, proto, p2 = kw["host1"], kw["port1"], kw["proto"], kw["port2"]
            socat_filename = f"/tmp/mnsec/local-{h1}-{p1}-{proto}.sock"
            try:
                pf = portforward(
                    host1=h1,
                    port1=p1,
                    proto=proto,
                    proto2="unix-connect",
                    dst_pair=socat_filename,
                )
            except Exception as exc:
                error(f"\n[ERROR] Failed to create port forward: kw={kw} -- {exc}")
                continue
            kw["portforward"] = pf
            self.cmd(f"socat -lpmnsec-socat-unix-{h1}-{p1}-{proto} unix-listen:{socat_filename},fork {proto}:127.0.0.1:{p2} >/dev/null 2>&1 &", shell=True)


class LinuxBridge(MN_Lxbr):
    """Mininet-Sec linux bridge."""
    display_image = "switch.png"


class IPTablesFirewall( Node ):
    "A Node with IPTables Linux Firewall."
    display_image = "firewall.png"

    def __init__( self, name, rules_v4="", rules_v6="", **params):
        """Start IPTables firewall
            rules_v4: IPv4 firewall rules to be loaded into iptables via
                iptables-restore command. Three formats are accepted:
                    - filename containing the IPv4 rules (from iptables-save)
                    - multiline string representing IPv4 rules (iptables-save)
                    - dict(list) where keys are tables and values are list of
                      chains or rules (same format as iptables-save)
            rules_v6: IPv6 firewall rules to be loaded into ip6tables via
                ip6tables-restore command. Same format as rules_v4
            flush: flush iptables before installing NAT rules"""
        Node.__init__( self, name, **params )

        self.rules_v4 = rules_v4
        self.rules_v6 = rules_v6


    def create_rules_files(self):
        """Create rules files to be used by iptables-restore."""
        self.fw_rules_v4 = f"{self.params['homeDir']}/iptables_v4.conf"
        if isinstance(self.rules_v4, dict):
            f = open(self.fw_rules_v4, "w")
            for table in self.rules_v4:
                f.write(f"*{table}\n")
                for rule in self.rules_v4[table]:
                    f.write(f"{rule}\n")
                f.write("COMMIT\n\n")
            f.close()
        elif isinstance(self.rules_v4, str) and os.path.isfile(self.rules_v4):
            self.fw_rules_v4 = self.rules_v4
        else:
            with open(self.fw_rules_v4, "w") as f:
                f.write(self.rules_v4)

        self.fw_rules_v6 = f"{self.params['homeDir']}/iptables_v6.conf"
        if isinstance(self.rules_v6, dict):
            f = open(self.fw_rules_v6, "w")
            for table in self.rules_v6:
                f.write(f"*{table}\n")
                for rule in self.rules_v6[table]:
                    f.write(f"{rule}\n")
                f.write("COMMIT\n\n")
            f.close()
        elif isinstance(self.rules_v6, str) and os.path.isfile(self.rules_v6):
            self.fw_rules_v6 = self.rules_v6
        else:
            with open(self.fw_rules_v6, "w") as f:
                f.write(self.rules_v6)

    def start( self, **moreParams ):
        self.params.update(moreParams)

        self.create_rules_files()

        # Default policy DROP
        for command in ["iptables", "ip6tables"]:
            self.cmd("f{command} -t filter -P INPUT DROP")
            self.cmd("f{command} -t filter -P FORWARD DROP")
            self.cmd("f{command} -t filter -P OUTPUT DROP")

        # Load firewall rules
        self.cmd(f"iptables-restore < {self.fw_rules_v4}")
        self.cmd(f"ip6tables-restore < {self.fw_rules_v6}")

        # Enable forwarding
        self.cmd("sysctl net.ipv4.ip_forward=1")
        self.cmd("sysctl net.ipv6.conf.all.forwarding=1")

    def terminate( self ):
        self.cmd("sysctl net.ipv4.ip_forward=0")
        self.cmd("sysctl net.ipv6.conf.all.forwarding=0")
        for command in ["iptables", "ip6tables"]:
            self.cmd("f{command} -t filter -P INPUT ACCEPT")
            self.cmd("f{command} -t filter -P FORWARD ACCEPT")
            self.cmd("f{command} -t filter -P OUTPUT ACCEPT")
            self.cmd("f{command} -t filter -F")
            self.cmd("f{command} -t filter -X")
            self.cmd("f{command} -t filter -Z ")
            self.cmd("f{command} -t nat -F")
            self.cmd("f{command} -t nat -X")
            self.cmd("f{command} -t mangle -F")
            self.cmd("f{command} -t mangle -X")
            self.cmd("f{command} -t raw -F")
            self.cmd("f{command} -t raw -X")
        Node.terminate(self)

    @classmethod
    def setup( cls ):
        """Check dependencies for iptables."""
        pathCheck("iptables-restore", moduleName="iptables-persistent")
        pathCheck("ip6tables-restore", moduleName="iptables-persistent")
        pathCheck("iptables", moduleName="iptables")
        pathCheck("ip6tables", moduleName="iptables")


class NetworkTAP( OVSSwitch ):
    """Network TAP for analysis, security or general network management.
       Overwall functionality consists of:
        - Port A will be the first attached link (mandatory)
        - Port B will be the second attached link (mandatory)
        - Mon A will be the attached link (optional). If no Mon A port
          is provided, then a dummy interface will be created on the
          format XXX-eth1001 (XXX is the node name)
        - Mon B will be the 4th attached link (optional). If no Mon B port
          is provided, then a dummy interface will be created on the
          format XXX-eth1002 (XXX is the node name)
    """
    display_image = "switch-tap.png"

    def __init__(self, name, port_a=1, port_b=2, mon_a=None, mon_b=None, mon_together=False, **kwargs):
        """Wrapper to capture the port A and B, and monitor"""
        self.port_a = port_a
        self.port_b = port_b
        self.mon_a = mon_a
        self.mon_b = mon_b
        self.mon_together = mon_together
        # force batch False
        kwargs["batch"] = False
        OVSSwitch.__init__(self, name, **kwargs)

    def start(self, controllers):
        """Starts standard OVSSwitch and then add monitor ports."""
        if not self.mon_a:
            name_mon_a = f"{self.name}-eth1001"
            makeIntfSingle(name_mon_a)
            intf = Intf(name_mon_a, node=self)
            self.mon_a = self.ports[intf]
        if self.mon_together:
            self.mon_b = self.mon_a
        elif not self.mon_b:
            name_mon_b = f"{self.name}-eth1002"
            makeIntfSingle(name_mon_b)
            intf = Intf(name_mon_b, node=self)
            self.mon_b = self.ports[intf]

        OVSSwitch.start(self, [])

        cmdOutA = self.dpctl("add-flow", f"in_port={self.port_a},actions=output:{self.port_b},output:{self.mon_a}")
        cmdOutB = self.dpctl("add-flow", f"in_port={self.port_b},actions=output:{self.port_a},output:{self.mon_b}")
        if cmdOutA:
            error(f"Failed to setup monitor port A: {cmdOutA}")
        if cmdOutB:
            error(f"Failed to setup monitor port B: {cmdOutB}")
