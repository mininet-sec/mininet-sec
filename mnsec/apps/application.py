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

from mnsec.util import getPopen

class Application(object):
    def __init__(self, node):
        self.node = node
        self.process = None
        self.logfile = None
        self.homeDir = self.node.params['homeDir']

        # Make directory for log file
        self.logDir = f"{self.homeDir}/log"
        self.node.cmd(f"mkdir -p {self.logDir}")

    def start(self, cmd, logfile, envDict={}):
        if self.process:
            return
        self.logfile = open(f"{self.logDir}/{logfile}", "w")
        if isinstance(cmd, str):
            cmd = cmd.split()
        self.process = getPopen(
            self.node, cmd, envDict, stdout=self.logfile, stderr=self.logfile
        )

    def stop(self):
        if self.process is not None:
            self.process.kill()
            self.process = None
        if self.logfile is not None:
            self.logfile.close()
