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

from collections import OrderedDict
from mininet.node import Node

class AppManager(object):
    """Manage the start/stop of apps on nodes."""

    apps = OrderedDict()

    def __init__(self, mnsec, hosts, app_cls, **params):
        if isinstance(app_cls, str):
            params = self.apps[app_cls][1] | params
            app_cls = self.apps[app_cls][0]
        self.app_cls = app_cls
        self.apps = []
        for host in hosts:
            # Don't run apps on switches
            if isinstance(host, Node):
                self.start_on_node(host, **params)

        mnsec.cleanups.append(self.cleanup)

    @classmethod
    def register_app(cls, app_name, app_cls, **params):
        cls.apps[app_name] = [app_cls, params]

    def start_on_node(self, host, **params):
        app = self.app_cls(host, **params)
        app.start()
        self.apps.append(app)

    def cleanup(self):
        for app in self.apps:
            app.stop()

    def __getitem__(self, nodeName):
        for app in self.apps:
            if app.node.name == nodeName:
                return app
        return None

    def __iter__(self):
        return self.apps.__iter__()

    def __next__(self):
        return self.apps.__next__()
