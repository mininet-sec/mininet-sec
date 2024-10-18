"""Kubernetes Node."""

import time
import os
import sys
import json
from uuid import uuid4
from pathlib import Path

from mininet.log import info, error, warn, debug
from mininet.node import Node
from mininet.moduledeps import pathCheck
from mininet.util import quietRun, errRun
from mininet.clean import addCleanupCallback

from mnsec.portforward import portforward


KUBECTL=None


class K8sPod(Node):
    "A Node running on Kubernetes as a Pod."
    initialized = False
    tag = None
    node_affinity = []

    def __init__(
        self,
        name,
        image="hackinsdn/debian:latest",
        command=[],
        args=[],
        env=[],
        publish=[],
        waitRunning=False,
        **params,
    ):
        """Instantiate the Pod
        waitRunning: wait for Pod to be Running? False: dont wait; True:
            wait indefinitely; Int: time to  wait (sec)
        env: environment variables for the container. Example:
            env=[{"name": "XPTO", "value": "foobar"}]
        command: command to be executed as the container entrypoint. Example:
            command=["/bin/bash"]
        args: To define arguments for the command. Note: The command field
            corresponds to ENTRYPOINT, and the args field corresponds to CMD
            in some container runtimes. Example:
            args=["-c", "tail -f /dev/null"]
        publish: Publish or expose a port (tcp, udp, tcp6, udp6, etc). Syntax:
            [bind_addr]:local_port:remote_prot[/protocol]. Multiple ports can
            be published/exposed. This option requires waitRunning. Example:
            publish=['8080:80', '127.0.0.1:5353:53/udp', ...]

        """
        if self.tag is None:
            self.tag = uuid4().hex[:14]
        self.k8s_name = f"mnsec-{name}-{self.tag}"
        self.k8s_image = image
        self.k8s_command = command
        self.k8s_args = args
        self.k8s_pod_ip = None
        self.k8s_env = env
        self.k8s_publish = self.parse_publish(publish)
        self.port_forward = []
        self.waitRunning = waitRunning
        if self.k8s_publish and not self.waitRunning:
            self.waitRunning = True
        Node.__init__(self, name, **params)

    def parse_publish(self, publish_orig):
        """Parse publish: from list of string to list of dict."""
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

    def startShell(self, **moreParams):
        """Create the Pod (run)."""
        self.params.update(moreParams)

        pod_manifest = {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {
                    "name": self.k8s_name,
                    "labels": {"app": f"mnsec-{self.tag}"},
                    "annotations": {
                        "container.apparmor.security.beta.kubernetes.io/"
                        + self.k8s_name: "unconfined",
                    },
                },
                "spec": {
                    "containers": [
                        {
                            "image": self.k8s_image,
                            "imagePullPolicy": "Always",
                            "name": self.k8s_name,
                            "env": self.k8s_env,
                            "securityContext": {
                                "capabilities": {
                                    "add": ["NET_ADMIN"],
                                },
                            },
                        }
                    ],
                },
        }
        if self.k8s_command:
            pod_manifest["spec"]["containers"][0]["command"] = self.k8s_command
        if self.k8s_args:
            pod_manifest["spec"]["containers"][0]["args"] = self.k8s_command
        if self.node_affinity:
            pod_manifest["spec"]["affinity"] = {
                "nodeAffinity": {
                    "requiredDuringSchedulingIgnoredDuringExecution": {
                        "nodeSelectorTerms": [
                            {
                                "matchExpressions": [
                                    {
                                        "key": "kubernetes.io/hostname",
                                        "operator": "In",
                                        "values": self.node_affinity,
                                    },
                                ],
                            },
                        ],
                    },
                },
            }
        pod_manifest_str = json.dumps(pod_manifest)
        out, err, exitcode = errRun(
            f"echo '{pod_manifest_str}' | {KUBECTL} create -f -", shell=True
        )
        if exitcode:
            raise Exception(
                f"Failed to create Kubernetes Pod: exit={exitcode} out={out} err={err}"
            )
        if self.waitRunning:
            if isinstance(self.waitRunning, bool):
                self.waitRunning = float("inf")
            self.wait_running(wait=self.waitRunning)

        # setup port forward
        self.setup_port_forward()

    def wait_running(self, wait=float("inf"), step=3):
        """Wait for Pod to be Running and get its IP address."""
        while wait > 0:
            try:
                output = quietRun(
                    f"{KUBECTL} get pod {self.k8s_name} -o custom-columns=IP:.status.podIP,PHASE:.status.phase --no-headers=true"
                )
                pod_ip, phase = output.split()
                if phase == "Running" and pod_ip:
                    self.k8s_pod_ip = pod_ip
                    break
            except:
                pass
            time.sleep(step)
            wait -= step

    def setup_port_forward(self):
        """Create port forward for the pod."""
        for kwargs in self.k8s_publish:
            try:
                p = portforward(host2=self.k8s_pod_ip, **kwargs)
            except Exception as exc:
                error(f"\n[ERROR] Failed to create port forward: host2={self.k8s_pod_ip} kwargs={kwargs} -- {exc}")
                continue
            kwargs["portforward"] = p

    def delete_port_forward(self):
        """Delete port forward."""
        for kwargs in self.k8s_publish:
            p = kwargs.get("portforward")
            if not p:
                continue
            p.kill()

    def delete_pod(self):
        info("(waiting on Kubernetes...) ")
        out, err, exitcode = errRun(f"{KUBECTL} delete pod {self.k8s_name} --wait=true")
        if exitcode:
            error(f"Failed to delete Pod: out={out} err={err}")

    def terminate(self):
        """Stop the Pod."""
        self.delete_pod()
        self.delete_port_forward()

    def stop(self):
        """Stop the Pod."""
        self.terminate()

    def cmd(self, *args, **kwargs):
        """Send a command, wait for output, and return it."""
        verbose = kwargs.get("verbose", False)
        log = info if verbose else debug
        log("*** %s : %s\n" % (self.name, args))
        # Allow sendCmd( [ list ] )
        if len(args) == 1 and isinstance(args[0], list):
            cmd = args[0]
        # Allow sendCmd( cmd, arg1, arg2... )
        elif len(args) > 0:
            cmd = args
        # Convert to string
        if not isinstance(cmd, str):
            cmd = " ".join([str(c) for c in cmd])
        return self.sendCmd(cmd)

    def sendCmd(self, cmd):
        """Run command on node"""
        return quietRun(f"{KUBECTL} exec -i {self.k8s_name} -- {cmd}")

    def popen(self, *args, **kwargs):
        """Return a Popen() object from kubectl exec."""
        kwargs["mncmd"] = [KUBECTL, "exec", "-it", self.k8s_name, "--"]
        kwargs["cwd"] = "/"
        # once we overwrite the HOME, we have to explicitly set KUBECONFIG
        if isinstance(kwargs.get("env"), dict):
            kwargs["env"]["KUBECONFIG"] = f"{os.path.expanduser('~')}/.kube/config"
        return Node.popen(self, *args, **kwargs)

    def setRoutes(self, routes=[]):
        """Additional routes to be added."""
        for net, gw in routes:
            self.cmd(f"ip route add {net} via {gw}")

    def config( self, routes=[], **params ):
        """routes: list of tuples with addional routes to be added
           params: parameters for Node.config()"""
        r = Node.config( self, **params )
        self.setParam( r, 'setRoutes', routes=routes )
        return r

    @classmethod
    def setup(cls):
        "Make sure kubectl is installed and working"
        if not cls.initialized:
            error(
                "Cannot find 'kubectl' executable. Please make sure it is"
                " installed and available in your PATH\n"
            )
            sys.exit(1)
        out, err, exitcode = errRun(f"{KUBECTL} get pods")
        if exitcode:
            error(f"kubectl exited with code {exitcode} out={out} err={err}\n")
            sys.exit(1)

    @classmethod
    def initialize(cls):
        """Initialize the class and add cleanup callback."""
        if cls.initialized:
            return

        addCleanupCallback(cls.cleanup)
        
        mnsec_tag = Path("/var/run/secrets/mnsec/tag")
        try:
            cls.tag = mnsec_tag.read_text()
        except FileNotFoundError:
            cls.tag = uuid4().hex[:14]
            mnsec_tag.parent.mkdir(parents=True, exist_ok=True)
            mnsec_tag.write_text(cls.tag)
        
        cls.node_affinity = os.environ.get("K8S_NODE_AFFINITY", "").split(",")

        cls.initialized = True

    @classmethod
    def cleanup(cls):
        """Clean up"""
        info("*** Cleaning up Kubernetes Pods\n")
        pods = quietRun(
            f"{KUBECTL} get pods --selector app=mnsec-{cls.tag} -o custom-columns=NAME:.metadata.name --no-headers=true"
        )
        if not pods:
            return
        pods = " ".join(pods.split())
        info(f"{pods} (Please wait a few seconds)...\n")
        quietRun(f"{KUBECTL} delete pods --wait=true {pods}")

    @classmethod
    def setup_node_affinity(cls, nodes):
        if isinstance(nodes, list):
            cls.node_affinity = nodes
        elif isinstance(nodes, str):
            cls.node_affinity = nodes.split(",")
        else:
            raise ValueError("Invalid data type for node affinity, must be string or list of strings")


KUBECTL = quietRun("which kubectl").strip()
if KUBECTL:
    K8sPod.initialize()
