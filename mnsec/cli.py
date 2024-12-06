import sys
from select import poll

from mininet.cli import CLI as MN_CLI
from mininet.log import output, error

from mnsec.k8s import K8sPod


class CLI(MN_CLI):
    "Simple command-line interface to talk to nodes."
    MN_CLI.prompt = 'mininet-sec> '

    def __init__(self, mnsec, stdin=sys.stdin, script=None, cmd=None):
        self.cmd = cmd
        if self.cmd:
            MN_CLI.mn = mnsec
            MN_CLI.stdin = stdin
            MN_CLI.inPoller = poll()
            MN_CLI.locals = { 'net': mnsec }
            self.do_cmd(self.cmd)
            return
        mnsec.cli = self
        MN_CLI.__init__(self, mnsec, stdin=stdin, script=script)

    def do_cmd(self, cmd):
        """Read commands from an input file.
           Usage: source <file>"""
        MN_CLI.onecmd(self, line=cmd)
        self.cmd = None
