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

    def __init__(self, **kwargs):
        """Create Mininet object.

           xyz: xyz description"""
        self.xyz = None

        # TODO: initialize things here

        Mininet.__init__(self, **kwargs)


class MininetSecWithControlNet(MininetWithControlNet):
    """Control network support."""
    pass
