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


VERSION = "0.1.0"


class Mininet_sec(Mininet):
    """Emulation platform for cybersecurity tools in programmable networks"""

    def __init__(self, workDir="/tmp/mnsec", **kwargs):
        """Create Mininet object.

           workDir: working directory where data will be saved"""
        self.workDir = workDir

        # TODO: initialize things here

        Mininet.__init__(self, **kwargs)

    def start(self):
        """Start nodes and call Mininet to finish the startup."""
        for host in self.hosts:
            if hasattr(host, "start"):
                host.start(workDir=self.workDir)
        Mininet.start(self)


class MininetSecWithControlNet(MininetWithControlNet):
    """Control network support."""
    pass
