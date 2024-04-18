"""
Node objects for Mininet-Sec

LinuxServer: provides minimal functionatility to work as a server
"""
import os
import re
import traceback

from mininet.node import Node
from mininet.log import info, error, warn, debug
from mininet.moduledeps import pathCheck

class Host( Node ):
    """Mininet-Sec host."""
    pass

class IPTablesFirewall( Node ):
    "A Node with IPTables Linux Firewall."

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
                    f.write(f"*{rule}\n")
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
                    f.write(f"*{rule}\n")
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
