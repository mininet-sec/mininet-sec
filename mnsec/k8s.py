"""Kubernetes Node."""

import time
import os
import sys
import json
import pty
import select
import signal
from uuid import uuid4
from pathlib import Path
from subprocess import Popen
import jwt

from mininet.log import info, error, warn, debug
from mininet.node import Node
from mininet.moduledeps import pathCheck
from mininet.util import quietRun, errRun
from mininet.clean import addCleanupCallback

from mnsec.portforward import portforward


KUBECTL = None
K8S_TOKEN_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/token"
K8S_NAMESPACE_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
K8S_CERT_FILE = "/var/run/secrets/mnsec/proxy.crt"

DISPLAY_IMG = {
    "hackinsdn/kytos": "server_kytos.png",
    "hackinsdn/suricata": "server_suricata.png",
    "hackinsdn/misp": "server_misp.png",
    "hackinsdn/secflood": "server_secflood.png",
    "hackinsdn/zeek": "server_zeek.png",
}


def parse_token(token):
    try:
        data = jwt.decode(token, options={"verify_signature": False})
        return data['kubernetes.io']['pod']['name'], data['kubernetes.io']['pod']['uid']
    except:
        return None, None


class K8sPod(Node):
    "A Node running on Kubernetes as a Pod."
    initialized = False
    tag = None
    pod_name = None
    pod_uid = None
    node_affinity = []
    display_image = "computer-k8s.png"

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
        if os.getenv("GTAG"):
            self.k8s_env.append({"name": "GTAG", "value": os.getenv("GTAG")})
        self.k8s_publish = self.parse_publish(publish)
        self.port_forward = []
        self.waitRunning = waitRunning
        if self.k8s_publish and not self.waitRunning:
            self.waitRunning = True
        img = DISPLAY_IMG.get(image.rsplit(":", 1)[0])
        if img:
            self.display_image = img
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
                                    "add": ["NET_ADMIN", "SYS_ADMIN"],
                                },
                            },
                        }
                    ],
                },
        }
        if self.k8s_command:
            pod_manifest["spec"]["containers"][0]["command"] = self.k8s_command
        if self.k8s_args:
            pod_manifest["spec"]["containers"][0]["args"] = self.k8s_args
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
        if self.pod_name and self.pod_uid:
            pod_manifest["metadata"]["ownerReferences"] = [{
                "name": self.pod_name,
                "uid": self.pod_uid,
                "apiVersion": "v1",
                "kind": "Pod",
            }]
        pod_manifest_str = json.dumps(pod_manifest)
        out, err, exitcode = errRun(
            f"echo '{pod_manifest_str}' | {KUBECTL} create -f -", shell=True
        )
        if exitcode:
            raise Exception(
                f"Failed to create Kubernetes Pod: exit={exitcode} out={out} err={err}"
            )

    def post_startup(self):
        """Run steps after Kubernetes has created the Pod (and all other pods)"""
        # wait until make sure pod is Running
        self.wait_running()
        # setup shell
        self.setup_shell()
        # change control network to mgmt namespace
        self.setup_mgmt_namespace()
        # setup port forward
        self.setup_port_forward()

    def wait_running(self, wait=float("inf"), step=2):
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

    @classmethod
    def wait_deleted(cls):
        if not cls.initialized:
            return
        info(f" (waiting pods deletion)")
        for _ in range(60):
            output = quietRun(
                f"{KUBECTL} get pod --selector app=mnsec-{cls.tag} "
                "-o custom-columns=IP:.status.podIP,PHASE:.status.phase "
                "--no-headers=true"
            )
            if not output:
                info(" done\n")
                break
            info(".")
            time.sleep(2)
        else:
            info(f" Timeout waiting for pods to be deleted\n")

    def setup_shell(self):
        cmd = [
            "mnexec", "-cd", KUBECTL, "exec", "-it", self.k8s_name, "--",
            "env", 'PS1=' + chr( 127 ), "bash", "--norc", "--noediting", "-is", "mininet:" + self.name
        ]
        self.master, self.slave = pty.openpty()
        self.shell = Popen( cmd, stdin=self.slave, stdout=self.slave, stderr=self.slave, close_fds=False )
        self.stdin = os.fdopen( self.master, 'r' )
        self.stdout = self.stdin
        self.pid = self.shell.pid
        self.pollOut = select.poll()
        self.pollOut.register( self.stdout )
        # Maintain mapping between file descriptors and nodes
        # This is useful for monitoring multiple nodes
        # using select.poll()
        self.outToNode[ self.stdout.fileno() ] = self
        self.inToNode[ self.stdin.fileno() ] = self
        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''
        # Wait for prompt
        while True:
            data = self.read( 1024 )
            if data[ -1 ] == chr( 127 ):
                break
            self.pollOut.poll()
        self.waiting = False
        self.cmd( 'unset HISTFILE; stty -echo; set +m' )

    def setup_mgmt_namespace(self):
        """Change the default network to mgmt namespace."""
        addr = self.cmd("ip -4 addr show dev eth0 | grep inet").split()[1]
        routes_link = self.cmd("ip route show dev eth0 scope link").splitlines()
        routes_global = self.cmd("ip route show dev eth0 scope global").splitlines()
        self.cmd("ip netns add mgmt")
        self.cmd("ip link set netns mgmt eth0")
        self.cmd("ip netns exec mgmt ip link set up lo")
        self.cmd("ip netns exec mgmt ip link set up eth0")
        self.cmd(f"ip netns exec mgmt ip addr add {addr} dev eth0")
        for route in routes_link:
            self.cmd(f"ip netns exec mgmt ip route add {route.strip()} dev eth0 scope link")
        for route in routes_global:
            self.cmd(f"ip netns exec mgmt ip route add {route.strip()} dev eth0 scope global")
        # setup DNS for the mgmt namespace according to original Kubernetes config
        self.cmd(f"mkdir -p /etc/netns/mgmt")
        self.cmd(f"cat /etc/resolv.conf > /etc/netns/mgmt/resolv.conf")

    def setup_port_forward(self):
        """Create port forward for the pod."""
        for kwargs in self.k8s_publish:
            try:
                p = portforward(host2=self.k8s_pod_ip, **kwargs)
            except Exception as exc:
                error(f"\n[ERROR] Failed to create port forward: host2={self.k8s_pod_ip} kwargs={kwargs} -- {exc}")
                continue
            kwargs["portforward"] = p
            # Since the services will not run on mgmt interface anymore
            # we need to create a proxy on the Pod to expose the service there
            # using socat (if available)
            port2 = kwargs.get("port2")
            proto = kwargs.get("proto", "tcp")
            if not port2:
                continue
            self.cmd(f"socat -lpmnsec-socat-unix-local-{port2}-{proto} unix-listen:/tmp/local-{port2}-{proto}.sock,fork {proto}:127.0.0.1:{port2} >/dev/null 2>&1 &", shell=True)
            self.cmd(f"ip netns exec mgmt socat -lpmnsec-socat-local-{port2}-{proto}-unix {proto}-listen:{port2},bind=0.0.0.0,reuseaddr,fork unix-connect:/tmp/local-{port2}-{proto}.sock >/dev/null 2>&1 &", shell=True)

    def delete_port_forward(self):
        """Delete port forward."""
        for kwargs in self.k8s_publish:
            p = kwargs.get("portforward")
            if not p:
                continue
            p.kill()

    def delete_pod(self):
        out, err, exitcode = errRun(f"{KUBECTL} delete pod {self.k8s_name} --wait=false")
        if exitcode:
            error(f"Failed to delete Pod: out={out} err={err}")

    def terminate(self):
        """Stop the Pod."""
        self.delete_pod()
        self.delete_port_forward()

    def stop(self):
        """Stop the Pod."""
        self.terminate()

    #def cmd(self, *args, **kwargs):
    #    """Send a command, wait for output, and return it."""
    #    verbose = kwargs.get("verbose", False)
    #    log = info if verbose else debug
    #    log("*** %s : %s\n" % (self.name, args))
    #    # Allow sendCmd( [ list ] )
    #    if len(args) == 1 and isinstance(args[0], list):
    #        cmd = args[0]
    #    # Allow sendCmd( cmd, arg1, arg2... )
    #    elif len(args) > 0:
    #        cmd = args
    #    # Convert to string
    #    if not isinstance(cmd, str):
    #        cmd = " ".join([str(c) for c in cmd])
    #    return self.sendCmd(cmd)

    #def sendCmd(self, cmd):
    #    """Run command on node"""
    #    return quietRun(f"{KUBECTL} exec -i {self.k8s_name} -- {cmd}")

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
        self.setRoutes(routes)
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

        pod_token = None
        if os.path.exists(K8S_TOKEN_FILE):
            pod_token = open(K8S_TOKEN_FILE).read()
        pod_namespace = None
        if os.path.exists(K8S_NAMESPACE_FILE):
            pod_namespace = open(K8S_NAMESPACE_FILE).read()
        
        # setup kube config
        if not os.path.exists(os.path.expanduser("~/.kube/config")):
            proxy_cert_f = os.environ.get("K8S_PROXY_CERT_FILE", K8S_CERT_FILE)
            proxy_token = os.environ.get("K8S_PROXY_TOKEN", pod_token)
            proxy_ns = os.environ.get("K8S_PROXY_NAMESPACE", pod_namespace)
            proxy_host = os.environ.get("K8S_PROXY_HOST")
            proxy_port = os.environ.get("K8S_PROXY_PORT", 443)
            if any([
                not os.path.exists(proxy_cert_f),
                not proxy_ns,
                not proxy_token,
                not proxy_host,
                not proxy_host,
            ]):
                return
            quietRun(f"{KUBECTL} config set-cluster mnsecproxy --server=https://{proxy_host}:{proxy_port} --certificate-authority={proxy_cert_f}")
            quietRun(f"{KUBECTL} config set-credentials default --token={proxy_token}")
            quietRun(f"{KUBECTL} config set-context {proxy_ns}_default@mnsecproxy --cluster mnsecproxy --user default --namespace {proxy_ns}")
            quietRun(f"{KUBECTL} config use-context {proxy_ns}_default@mnsecproxy")

        # test kubernetes access
        result = quietRun(f"{KUBECTL} auth can-i create pods")
        if "yes" not in result:
            raise ValueError("Failed to initialize kubernetes")

        cls.pod_name, cls.pod_uid = parse_token(pod_token)

        # setup Pod tag to avoid conflicts
        mnsec_tag = Path("/var/run/secrets/mnsec/tag")
        try:
            cls.tag = mnsec_tag.read_text()
        except FileNotFoundError:
            cls.tag = os.environ.get("K8S_POD_HASH") or uuid4().hex[:14]
            mnsec_tag.parent.mkdir(parents=True, exist_ok=True)
            mnsec_tag.write_text(cls.tag)
        
        cls.setup_node_affinity(os.environ.get("K8S_NODE_AFFINITY"))

        addCleanupCallback(cls.cleanup)
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
        info(pods)
        quietRun(f"{KUBECTL} delete pods --wait=false {pods}")
        cls.wait_deleted()

    @classmethod
    def setup_node_affinity(cls, nodes):
        if not nodes:
            return
        if isinstance(nodes, list):
            cls.node_affinity = nodes
        elif isinstance(nodes, str):
            cls.node_affinity = nodes.split(",")
        else:
            raise ValueError("Invalid data type for node affinity, must be string or list of strings")


KUBECTL = quietRun("which kubectl").strip()
if KUBECTL:
    K8sPod.initialize()
