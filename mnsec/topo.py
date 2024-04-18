from mnsec.nodelib import IPTablesFirewall, Host

from mininet.topo import Topo as MN_Topo

class Topo(MN_Topo):
    def addFirewall( self, name, **opts ):
        """Convenience method: Add Firewall to graph.
           name: firewall name
           opts: firewall options
           returns: firewall name"""
        if not opts and self.hopts:
            opts = self.hopts
        opts.setdefault('ip', None)
        return self.addNode( name, cls=IPTablesFirewall, **opts )
