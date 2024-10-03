"""Kubernetes Node."""

import time
import os
import sys
import json

from mininet.log import info, error, warn, debug
from mininet.node import Node
from mininet.moduledeps import pathCheck
from mininet.util import quietRun, errRun
from mininet.clean import addCleanupCallback


KUBECTL=None
try:
    NAMESPACE = os.getenv("NAMESPACE")
    if not NAMESPACE:
        NAMESPACE = open(
            "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        ).read()
except:
    NAMESPACE = "default"


class K8sPod(Node):
    "A Node running on Kubernetes as a Pod."
    namespace = NAMESPACE
    initialized = False

    def __init__(
        self,
        name,
        image="hackinsdn/debian:stable",
        command=["/bin/bash", "-c", "tail -f /dev/null"],
        env=[],
        waitRunning=False,
        **params,
    ):
        """Instantiate the Pod
        waitRunning: wait for Pod to be Running? False: dont wait; True:
            wait indefinitely; Int: time to  wait (sec)
        env: environment variables for the container. Example:
            env=[{"name": "XPTO", "value": "foobar"}]
        """
        self.k8s_name = f"mnsec-{name}"
        self.k8s_image = image
        self.k8s_command = command
        self.k8s_pod_ip = None
        self.k8s_env = env
        self.waitRunning = waitRunning
        Node.__init__(self, name, **params)

    def startShell(self, **moreParams):
        """Create the Pod (run)."""
        self.params.update(moreParams)

        pod_manifest = json.dumps(
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {
                    "name": self.k8s_name,
                    "labels": {"app": "mnsec"},
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
                            "command": self.k8s_command,
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
        )
        out, err, exitcode = errRun(
            f"echo '{pod_manifest}' | {KUBECTL} create -f -", shell=True
        )
        if exitcode:
            raise Exception(
                f"Failed to create Kubernetes Pod: exit={exitcode} out={out} err={err}"
            )
        if self.waitRunning:
            if isinstance(self.waitRunning, bool):
                self.waitRunning = float("inf")
            self.wait_running(max_wait=self.waitRunning)

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

    def delete_pod(self):
        info("(waiting on Kubernetes...) ")
        out, err, exitcode = errRun(f"{KUBECTL} delete pod {self.k8s_name} --wait=true")
        if exitcode:
            error(f"Failed to delete Pod: out={out} err={err}")

    def terminate(self):
        """Stop the Pod."""
        self.delete_pod()

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
        defaults = {"mncmd": [KUBECTL, "exec", "-it", self.k8s_name, "--"]}
        defaults.update(kwargs)
        if isinstance(defaults.get("env"), dict):
            defaults["env"]["KUBECONFIG"] = f"{os.path.expanduser('~')}/.kube/config"
        return Node.popen(self, *args, **defaults)

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
        cls.initialized = True

    @classmethod
    def cleanup(cls):
        """Clean up"""
        info("*** Cleaning up Kubernetes Pods\n")
        pods = quietRun(
            f"{KUBECTL} get pods --selector app=mnsec -o custom-columns=NAME:.metadata.name --no-headers=true"
        )
        if not pods:
            return
        pods = " ".join(pods.split())
        info(f"{pods} (Please wait a few seconds)...\n")
        quietRun(f"{KUBECTL} delete pods --wait=true {pods}")


KUBECTL = quietRun("which kubectl").strip()
if KUBECTL:
    K8sPod.initialize()
