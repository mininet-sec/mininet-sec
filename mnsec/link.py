"""link.py: link abstractions for mininet-sec (complementary to mininet)"""

import re

from mininet.log import info, error, debug
from mininet.util import makeIntfPair
from mininet.link import Link
from mininet.util import quietRun
from mnsec.k8s import K8sPod


class VxLanLink(Link):
    """VXLan Link"""

    vxlan_next_id = 1

    def __init__(self, node1, node2, **params):
        """Create VXLan Link on nodes."""
        if isinstance(node1, K8sPod):
            node1.wait_running(wait=60)
        if isinstance(node2, K8sPod):
            node2.wait_running(wait=60)
        Link.__init__(self, node1, node2, **params)

    @classmethod
    def makeIntfPair(
        cls,
        intfname1,
        intfname2,
        addr1=None,
        addr2=None,
        node1=None,
        node2=None,
        deleteIntfs=True,
    ):
        """Create pair of interfaces
        intfname1: name for interface 1
        intfname2: name for interface 2
        addr1: MAC address for interface 1 (optional)
        addr2: MAC address for interface 2 (optional)
        node1: home node for interface 1 (optional)
        node2: home node for interface 2 (optional)
        (override this method [and possibly delete()]
        to change link type)"""
        # node1_ip and node2_ip: ip address of the nodes to create the VXLAN
        # if one of them is None it means the VXLAN has to be configured on the Mininet host
        # XXX: test when using ipv6 only
        node1_ip = getattr(node1, "k8s_pod_ip", None)
        node2_ip = getattr(node2, "k8s_pod_ip", None)
        if node1_ip is None:
            node1_ip = quietRun(
                f"LANG=C ip route get {node2_ip} | egrep -o 'src \S+ ' | cut -d' ' -f2",
                shell=True,
            ).strip()
        elif node2_ip is None:
            node2_ip = quietRun(
                f"LANG=C ip route get {node1_ip} | egrep -o 'src \S+ ' | cut -d' ' -f2",
                shell=True,
            ).strip()

        runCmd1 = node1.cmd if isinstance(node1, K8sPod) else quietRun
        runCmd2 = node2.cmd if isinstance(node2, K8sPod) else quietRun
        netns1 = 1 if isinstance(node1, K8sPod) else node1.pid
        netns2 = 1 if isinstance(node2, K8sPod) else node2.pid

        if deleteIntfs:
            # Delete any old interfaces with the same names
            runCmd1("ip link del " + intf1)
            runCmd2("ip link del " + intf2)

        l2addr1 = f"addr {addr1}" if addr1 else ""
        l2addr2 = f"addr {addr2}" if addr2 else ""

        vxlan_id = cls.vxlan_next_id
        cls.vxlan_next_id += 1

        cmdOut1 = runCmd1(
            f"ip link add {intfname1} netns {netns1} {l2addr1} "
            f"type vxlan id {vxlan_id} remote {node2_ip} dstport 8472",
            shell=True,
        )
        cmdOut2 = runCmd2(
            f"ip link add {intfname2} netns {netns2} {l2addr2} "
            f"type vxlan id {vxlan_id} remote {node1_ip} dstport 8472",
            shell=True,
        )

        if cmdOut1 or cmdOut2:
            raise Exception(
                f"Error creating interface pair ({intfname1},{intfname2}): node1={cmdOut1} node2={cmdOut2}"
            )
