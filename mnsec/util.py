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
