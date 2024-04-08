"""
Node objects for Mininet-Sec

LinuxServer: provides minimal functionatility to work as a server
"""
import os
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

        services = self.params.get("services", [])
        self.services = []
        for service in services:
            srv_name = service["name"]
            cmd = SERVICES.get(srv_name, "").split(" ")
            if not cmd:
                warn(f"Unknown service {service} for host {self.name}\n")
                continue
            for attr, value in service.items():
                if attr == "name":
                    continue
                cmd.append("--"+attr)
                cmd.append(value)
            homedir = self.params.get("workDir", "/tmp/mnsec") + f"/{self.name}"
            os.makedirs(homedir, exist_ok=True)
            logfile = open(f"{homedir}/{srv_name}.log", "w")
            try:
                popen = self._popen(cmd, stdout=logfile, stderr=logfile)
            except:
                trace_str = traceback.format_exc().replace("\n", ", ")
                warn(f"Error starting service {service} on {self.name}: {trace_str}\n")
                continue
            #result = self.cmd(cmd +  + f" 2>&1 >/tmp/{srv_name}.log &")
            #if result:
            #    warn(f"Output for service {service}: {result}\n")
            self.services.append([service, popen.pid])

        # Enable forwarding on the router
        #self.cmd( 'sysctl net.ipv4.ip_forward=1' )

    def terminate( self ):
        #self.cmd( 'sysctl net.ipv4.ip_forward=0' )
        for srv_name, srv_pid in self.services:
            info("terminate ", srv_pid, srv_name)
            self.cmd(f"kill {srv_pid}")
        Node.terminate(self)
