# -*- Mode:python; c-file-style:"gnu"; indent-tabs-mode:nil -*- */
#
# Copyright (C) 2024-2024, Italo Valcy (italovalcy@ufba.br)
# Copyright (C) 2015-2019, The University of Memphis,
#                          Arizona Board of Regents,
#                          Regents of the University of California.
#
# This file is part of Mininet-Sec and it was strongly based on
# Mini-NDN. All credits for Mini-NDN team. More information:
# http://github.com/named-data/mini-ndn/
#
# Mininet-Sec is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mininet-Sec is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mini-NDN, e.g., in COPYING.md file.
# If not, see <http://www.gnu.org/licenses/>.

import re
import sys
from mininet.log import warn, error
from mininet.util import quietRun
from mnsec.apps.application import Application
from mnsec.apps.app_manager import AppManager

HONEYPOTS_PREFIX = "python3 -m honeypots --termination-strategy input --setup"

SERVICES = {
    "dns": [HONEYPOTS_PREFIX + " dns", 53],
    "ftp": [HONEYPOTS_PREFIX + " ftp", 21],
    "httpproxy": [HONEYPOTS_PREFIX + " httpproxy", 8080],
    "http": [HONEYPOTS_PREFIX + " http", 80],
    "https": [HONEYPOTS_PREFIX + " https", 443],
    "imap": [HONEYPOTS_PREFIX + " imap", 143],
    "mysql": [HONEYPOTS_PREFIX + " mysql", 3306],
    "pop3": [HONEYPOTS_PREFIX + " pop3", 110],
    "postgres": [HONEYPOTS_PREFIX + " postgres", 5432],
    "redis": [HONEYPOTS_PREFIX + " redis", 6379],
    "smb": [HONEYPOTS_PREFIX + " smb", 139],
    "smtp": [HONEYPOTS_PREFIX + " smtp", 25],
    "socks5": [HONEYPOTS_PREFIX + " socks5", 1080],
    "ssh": [HONEYPOTS_PREFIX + " ssh", 22],
    "telnet": [HONEYPOTS_PREFIX + " telnet", 23],
    "vnc": [HONEYPOTS_PREFIX + " vnc", 5900],
    "elastic": [HONEYPOTS_PREFIX + " elastic", 9200],
    "mssql": [HONEYPOTS_PREFIX + " mssql", 1433],
    "ldap": [HONEYPOTS_PREFIX + " ldap", 389],
    "ntp": [HONEYPOTS_PREFIX + " ntp", 123],
    "memcache": [HONEYPOTS_PREFIX + " memcache", 11211],
    "oracle": [HONEYPOTS_PREFIX + " oracle", 1521],
    "snmp": [HONEYPOTS_PREFIX + " snmp", 161],
# voip? imaps? pops?
}

class HoneypotFactory(Application):
    """Honeypot Factory."""

    def __init__(self, node, name=None, **params):
        Application.__init__(self, node)
        if name not in SERVICES:
            raise ValueError(f"Unknown service name {name}")
        self.logfile = f"{self.logDir}/{name}.log"
        self.cmd = SERVICES[name][0]
        params.setdefault("port", SERVICES[name][1])
        self.name = name
        self.params = params

    def start(self):
        cmd = self.cmd 
        for k, v in self.params.items():
            cmd += f" --{k} {v}"
        result = self.node.cmd(f"nohup {cmd} >{self.logfile} 2>&1 </dev/null &")
        match = re.search("\[[0-9]+\] ([0-9]+)", result)
        if not match:
            warn(f"Failed to start service {self.name} on {self.node.name}: {result}\n")
            return
        self.pid = match.group(1)

    def stop(self):
        #self.node.cmd(f"kill {self.pid}")
        self.node.cmd(f"pkill -f 'python3 .*/honeypots/{self.name}_server.py --custom'")


for name in SERVICES:
    AppManager.register_app(name, HoneypotFactory, name=name)

# Check dependency on honeypots module
if quietRun('python3 -c "import honeypots"', shell=True):
    error("Cannot find required module honeypots.\n")
    sys.exit(1)
