from mnsec.node import HostServices
from mininet.topo import Topo

class HostServicesLinearTopo( Topo ):
    "Linear topology of k switches, with n hosts per switch."

    def build( self, k=2, n=1, **_opts):
        """k: number of switches
           n: number of hosts per switch"""
        self.k = k
        self.n = n

        if n == 1:
            def genHostName( i, _j ):
                return 'h%s' % i
        else:
            def genHostName( i, j ):
                return 'h%ss%d' % ( j, i )

        hostservices = {}
        for pair in _opts.get("services", "").split("+"):
            pair_l = pair.split(":")
            host, service = pair_l[:2]
            params = {}
            if len(pair_l) > 2:
                for param in pair_l[2:]:
                    attr, value = param.split("/")
                    params[attr] = value
            hostservices.setdefault(host, [])
            hostservices[host].append({"name": service}|params)

        lastSwitch = None
        for i in range( 1, k+1 ):
            # Add switch
            switch = self.addSwitch( 's%s' % i )
            # Add hosts to switch
            for j in range( 1, n+1 ):
                host_name = genHostName( i, j )
                host = self.addHost(host_name, cls=HostServices, services=hostservices.get(host_name))
                self.addLink( host, switch )
            # Connect switch to previous
            if lastSwitch:
                self.addLink( switch, lastSwitch )
            lastSwitch = switch

topos = {
    "hostserviceslinear": HostServicesLinearTopo,
}
