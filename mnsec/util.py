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

from mininet.util import quietRun

def popenGetEnv(node, envDict={}):
    env = {}
    homeDir = node.params['homeDir']
    printenv = node.popen(
        'printenv'.split(), cwd=homeDir, text=True
    ).communicate()[0]
    for var in printenv.strip().split('\n'):
        p = var.split('=')
        env[p[0]] = p[1]
    env['HOME'] = homeDir

    for key, value in envDict.items():
        env[key] = str(value)

    return env

def getPopen(host, cmd, envDict={}, **params):
    return host.popen(cmd, cwd=host.params['homeDir'],
                      env=popenGetEnv(host, envDict), **params)

def makeIntfSingle(intf, deleteIntf=True, node=None):
    """Make a single/dummy new interface. Parameters:
       intf: name for the new interface
       deleteIntf: delete interface before creating (optional)
       node: node where interface will be attached (optional)
       raises Exception on failure"""
    runCmd = quietRun if not node else node.cmd
    if deleteIntf:
        runCmd(f"ip link del {intf}")
    cmdOutput = runCmd(f"ip link add {intf} type dummy")
    if cmdOutput:
        raise Exception(f"Error creating interface {intf}: {cmdOutput}")
    runCmd(f"ip link set up {intf}")

def parse_publish(publish_orig):
    """Parse published ports: from list of string to list of dict."""
    publish = []
    for publish_str in publish_orig:
        params = publish_str.split(":")
        if len(params) < 2:
            raise ValueError(f"Invalid publish params {publish_str}")
        port2 = params.pop(-1)
        proto = "tcp"
        if "/" in port2:
            port2, proto = port2.split("/")
        port1 = params.pop(-1)
        host1 = "0.0.0.0"
        if params:
            host1 = ":".join(params)
        publish.append({"host1": host1, "port1": port1, "port2": port2, "proto": proto})
    return publish
