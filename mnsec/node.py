"""
Node objects for Mininet-Sec

LinuxServer: provides minimal functionatility to work as a server
"""
import os
import re
import traceback

from mininet.node import Node
from mininet.log import info, error, warn, debug

HONEYPOTS_PREFIX = "python3 -m honeypots --termination-strategy signal --setup"

SERVICES = {
    "dns": HONEYPOTS_PREFIX + " dns",
    "ftp": HONEYPOTS_PREFIX + " ftp",
    "httpproxy": HONEYPOTS_PREFIX + " httpproxy",
    "http": HONEYPOTS_PREFIX + " http",
    "https": HONEYPOTS_PREFIX + " https",
    "imap": HONEYPOTS_PREFIX + " imap",
    "mysql": HONEYPOTS_PREFIX + " mysql",
    "pop3": HONEYPOTS_PREFIX + " pop3",
    "postgres": HONEYPOTS_PREFIX + " postgres",
    "redis": HONEYPOTS_PREFIX + " redis",
    "smb": HONEYPOTS_PREFIX + " smb",
    "smtp": HONEYPOTS_PREFIX + " smtp",
    "socks5": HONEYPOTS_PREFIX + " socks5",
    "ssh": HONEYPOTS_PREFIX + " ssh",
    "telnet": HONEYPOTS_PREFIX + " telnet",
    "vnc": HONEYPOTS_PREFIX + " vnc",
    "elastic": HONEYPOTS_PREFIX + " elastic",
    "mssql": HONEYPOTS_PREFIX + " mssql",
    "ldap": HONEYPOTS_PREFIX + " ldap",
    "ntp": HONEYPOTS_PREFIX + " ntp",
    "memcache": HONEYPOTS_PREFIX + " memcache",
    "oracle": HONEYPOTS_PREFIX + " oracle",
    "snmp": HONEYPOTS_PREFIX + " snmp",
}

class HostServices( Node ):
    "A Node with some services enabled."

    def start( self, **moreParams ):
        self.params.update(moreParams)
        homedir = self.params.get("homeDir", f"/tmp/mnsec/{self.name}")
        os.makedirs(homedir, exist_ok=True)

        services = self.params.get("services", [])
        self.services = []
        for service in services:
            srv_name = service["name"]
            cmd = SERVICES.get(srv_name, "")
            if not cmd:
                warn(f"Unknown service {service} for host {self.name}\n")
                continue
            args = [f"--{k} {v}" for k, v in service.items() if k != "name"]
            logfile = f"{homedir}/{srv_name}.log"
            cmd = "%s %s 2>&1 >%s &" % (cmd, " ".join(args), logfile)
            result = self.cmd(cmd)
            match = re.search("\[[0-9]+\] ([0-9]+)", result)
            if not match:
                warn(f"Failed to start service {service}: {result}\n")
                continue
            self.services.append([service, match.group(1)])

        # Enable forwarding on the router
        #self.cmd( 'sysctl net.ipv4.ip_forward=1' )

    def terminate( self ):
        #self.cmd( 'sysctl net.ipv4.ip_forward=0' )
        for srv_name, srv_pid in self.services:
            info("terminate ", srv_pid, srv_name)
            self.cmd(f"kill {srv_pid}")
        Node.terminate(self)
