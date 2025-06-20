# -*- Mode:python; c-file-style:"gnu"; indent-tabs-mode:nil -*- */
#
# Copyright (C) 2024-2024, Italo Valcy (italovalcy@ufba.br)
# Copyright (C) 2015-2019, The University of Memphis,
#                          Arizona Board of Regents,
#                          Regents of the University of California.
#
# This file is part of Mininet-Sec
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

EXEC_PREFIX = "python3 -m mnsec.server.loopback"

class LoopbackServer(Application):
    """Loopback server: echo server application."""

    def __init__(self, node, **params):
        Application.__init__(self, node)
        self.logfile = f"{self.logDir}/loopback.log"
        self.cmd = EXEC_PREFIX
        self.params = params

    def start(self):
        cmd = self.cmd + " " + self.node.intf().name
        result = self.node.cmd(f"nohup {cmd} >{self.logfile} 2>&1 </dev/null &")
        match = re.search("\[[0-9]+\] ([0-9]+)", result)
        if not match:
            warn(f"Failed to start service loopback on {self.node.name}: {result}\n")
            return
        self.pid = match.group(1)

    def stop(self):
        #self.node.cmd(f"kill {self.pid}")
        self.node.cmd(f"pkill -f '%s'" % EXEC_PREFIX)


AppManager.register_app("loopback", LoopbackServer)

## Check dependency on honeypots module
#if quietRun('python3 -c "import scapy"', shell=True):
#    error("Cannot find required module 'scapy'.\n")
#    sys.exit(1)
