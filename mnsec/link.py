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
        cmd1Pfx = "ip netns exec mgmt" if isinstance(node1, K8sPod) else ""
        cmd2Pfx = "ip netns exec mgmt" if isinstance(node2, K8sPod) else ""

        if deleteIntfs:
            # Delete any old interfaces with the same names
            runCmd1("ip link del " + intf1)
            runCmd2("ip link del " + intf2)

        l2addr1 = f"addr {addr1}" if addr1 else ""
        l2addr2 = f"addr {addr2}" if addr2 else ""

        vxlan_id = cls.vxlan_next_id
        cls.vxlan_next_id += 1

        cmdOut1 = runCmd1(
            f"{cmd1Pfx} ip link add {intfname1} netns {netns1} {l2addr1} "
            f"type vxlan id {vxlan_id} remote {node2_ip} dstport 8472 nolearning",
            shell=True,
            k8s_mgmt=True,
        )
        cmdOut2 = runCmd2(
            f"{cmd2Pfx} ip link add {intfname2} netns {netns2} {l2addr2} "
            f"type vxlan id {vxlan_id} remote {node1_ip} dstport 8472 nolearning",
            shell=True,
            k8s_mgmt=True,
        )

        if cmdOut1 or cmdOut2:
            raise Exception(
                f"Error creating interface pair ({intfname1},{intfname2}): node1={cmdOut1} node2={cmdOut2}"
            )

class L2tpLink(Link):
    """L2TP Link"""

    l2tp_next_id = 1
    l2tp_intf_tun = {}

    def __init__(self, node1, node2, **params):
        """Create L2TP Link on nodes."""
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
        # node1_ip and node2_ip: ip address of the nodes to create the L2TP
        # if one of them is None it means the L2TP has to be configured on the Mininet host
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
        cmd1Pfx = "ip netns exec mgmt" if isinstance(node1, K8sPod) else ""
        cmd2Pfx = "ip netns exec mgmt" if isinstance(node2, K8sPod) else ""
        l2addr1 = f"addr {addr1}" if addr1 else ""
        l2addr2 = f"addr {addr2}" if addr2 else ""

        if deleteIntfs:
            # Delete any old interfaces with the same names
            if intfname1 in cls.l2tp_intf_tun:
                runCmd1(f"{cmd1Pfx} ip l2tp del tunnel tunnel_id {cls.l2tp_intf_tun[intfname1]}")
            if intfname2 in cls.l2tp_intf_tun:
                runCmd2(f"{cmd2Pfx} ip l2tp del tunnel tunnel_id {cls.l2tp_intf_tun[intfname2]}")

        l2tp_id = cls.l2tp_next_id
        cls.l2tp_next_id += 1
        cls.l2tp_intf_tun[intfname1] = l2tp_id
        cls.l2tp_intf_tun[intfname2] = l2tp_id
        l2tp_port = 10000 + l2tp_id

        cmdOut1 = runCmd1(
            f"{cmd1Pfx} ip l2tp add tunnel local {node1_ip} remote {node2_ip} "
            f"tunnel_id {l2tp_id} peer_tunnel_id {l2tp_id} udp_dport {l2tp_port} udp_sport {l2tp_port}",
            shell=True,
            k8s_mgmt=True,
        )
        cmdOut2 = runCmd2(
            f"{cmd2Pfx} ip l2tp add tunnel local {node2_ip} remote {node1_ip} "
            f"tunnel_id {l2tp_id} peer_tunnel_id {l2tp_id} udp_dport {l2tp_port} udp_sport {l2tp_port}",
            shell=True,
            k8s_mgmt=True,
        )

        if cmdOut1 or cmdOut2:
            raise Exception(
                f"Error create L2TP Link - failed to config tunnel ({intfname1},{intfname2}): node1={cmdOut1} node2={cmdOut2}"
            )

        cmdOut1 = runCmd1(
            f"{cmd1Pfx} ip l2tp add session name {intfname1} tunnel_id {l2tp_id} session_id {l2tp_id} peer_session_id {l2tp_id} ",
            shell=True,
            k8s_mgmt=True,
        )
        cmdOut2 = runCmd2(
            f"{cmd2Pfx} ip l2tp add session name {intfname2} tunnel_id {l2tp_id} session_id {l2tp_id} peer_session_id {l2tp_id} ",
            shell=True,
            k8s_mgmt=True,
        )

        if cmdOut1 or cmdOut2:
            raise Exception(
                f"Error create L2TP Link - failed to config session ({intfname1},{intfname2}): node1={cmdOut1} node2={cmdOut2}"
            )

        cmdOut1 = runCmd1(
            f"{cmd1Pfx} ip link set netns {netns1} {l2addr1} dev {intfname1}",
            shell=True,
            k8s_mgmt=True,
        )
        cmdOut2 = runCmd2(
            f"{cmd2Pfx} ip link set netns {netns2} {l2addr2} dev {intfname2}",
            shell=True,
            k8s_mgmt=True,
        )

        if cmdOut1 or cmdOut2:
            raise Exception(
                f"Error create L2TP Link - failed to config intf ({intfname1},{intfname2}): node1={cmdOut1} node2={cmdOut2}"
            )
