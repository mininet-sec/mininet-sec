"""
    Mininet-Sec: Emulation platform for studying and experimenting
                 cybersecurity tools in programmable networks
    author: Italo Valcy (italovalcy@ufba.br)

    This software is strongly based on Mininet project, as well
    as their forks/sub-projects Mininet-Wifi and Mini-NDN.
"""

import re
import socket

from itertools import chain, groupby
from threading import Thread as thread
from time import sleep
from sys import exit

from mininet.net import Mininet, MininetWithControlNet

import mnsec.apps.all
from mnsec.apps.app_manager import AppManager


VERSION = "0.1.0"


class Mininet_sec(Mininet):
    """Emulation platform for cybersecurity tools in programmable networks"""

    def __init__(self, workDir="/tmp/mnsec", apps="", **kwargs):
        """Create Mininet object.

           apps: string with list of host, app_name and optional params
           workDir: working directory where data will be saved"""
        self.apps = apps
        self.workDir = workDir

        # TODO: initialize things here
        self.cleanups = []

        Mininet.__init__(self, **kwargs)

    def start(self):
        """Start nodes, apps and call Mininet to finish the startup."""
        for host in self.hosts:
            homeDir = f"{self.workDir}/{host.name}"
            host.params["homeDir"] = homeDir
            host.cmd(f"mkdir -p {homeDir}")
            host.cmd(f"export HOME={homeDir} && cd ~")
            if hasattr(host, "start"):
                host.start()

        # start apps
        for app_str in self.apps.split(","):
            app_spec = app_str.split(":")
            if len(app_spec) < 2:
                raise ValueError(f"Invalid apps param: {app_str}.")
            params = dict([i.split('=') for i in app_spec[2:]])
            host = self.get(app_spec[0])
            AppManager(self, [host], app_spec[1], **params)

        Mininet.start(self)

    def stop(self):
        for cleanup in self.cleanups:
            cleanup()
        Mininet.stop(self)

class MininetSecWithControlNet(MininetWithControlNet):
    """Control network support."""
    pass
