#!/usr/bin/env python3

"""
Mininet runner
author: Italo Valcy (italovalcy@ufba.br)

This file is strongly based on Mininet/mn file available at
    https://github.com/mininet/mininet/blob/master/bin/mn

To see options:
  sudo mnsec -h

Example to pull custom params (topo, switch, etc.) from a file:
  sudo mnsec --custom ~/mininet/custom/custom_example.py
"""

import os
import sys
import time
import traceback

from functools import partial
from optparse import OptionParser  # pylint: disable=deprecated-module
from sys import exit  # pylint: disable=redefined-builtin

# Fix setuptools' evil madness, and open up (more?) security holes
if 'PYTHONPATH' in os.environ:
    sys.path = os.environ[ 'PYTHONPATH' ].split( ':' ) + sys.path

# pylint: disable=wrong-import-position

import mnsec.cli
from mnsec.net import ( Mininet_sec, MininetWithControlNet, VERSION,
                        TOPODEF, TOPOS, SWITCHDEF, SWITCHES, HOSTDEF, HOSTS,
                        CONTROLLERDEF, CONTROLLERS, LINKDEF, LINKS )
from mnsec.k8s import K8sPod

from mininet.clean import cleanup
from mininet.log import lg, LEVELS, info, debug, warn, error, output
from mininet.net import Mininet, MininetWithControlNet, VERSION
from mininet.node import findController
from mininet.util import customClass, splitArgs, buildTopo

# Experimental! cluster edition prototype
from mininet.examples.cluster import ( MininetCluster, RemoteHost,
                                       RemoteOVSSwitch, RemoteLink,
                                       SwitchBinPlacer, RandomPlacer,
                                       ClusterCleanup )
from mininet.examples.clustercli import ClusterCLI


PLACEMENT = { 'block': SwitchBinPlacer, 'random': RandomPlacer }


# TESTS dict can contain functions and/or Mininet() method names
# XXX: it would be nice if we could specify a default test, but
# this may be tricky
TESTS = { name: True
          for name in ( 'pingall', 'pingpair', 'iperf', 'iperfudp' ) }

CLI = None  # Set below if needed

# Locally defined tests
def allTest( net ):
    "Run ping and iperf tests"
    net.start()
    net.ping()
    net.iperf()

def nullTest( _net ):
    "Null 'test' (does nothing)"
    pass


TESTS.update( all=allTest, none=nullTest, build=nullTest )

# Map to alternate spellings of Mininet() methods
ALTSPELLING = { 'pingall': 'pingAll', 'pingpair': 'pingPair',
                'iperfudp': 'iperfUdp' }

def runTests( mn, options ):
    """Run tests
       mn: Mininet object
       option: list of test optinos """
    # Split option into test name and parameters
    for option in options:
        # Multiple tests may be separated by '+' for now
        for test in option.split( '+' ):
            test, args, kwargs = splitArgs( test )
            test = ALTSPELLING.get( test.lower(), test )
            testfn = TESTS.get( test, test )
            if callable( testfn ):
                testfn( mn, *args, **kwargs )
            elif hasattr( mn, test ):
                getattr( mn, test )( *args, **kwargs )
            else:
                raise Exception( 'Test %s is unknown - please specify one of '
                                 '%s ' % ( test, TESTS.keys() ) )


def addDictOption( opts, choicesDict, default, name, **kwargs ):
    """Convenience function to add choices dicts to OptionParser.
       opts: OptionParser instance
       choicesDict: dictionary of valid choices, must include default
       default: default choice key
       name: long option name
       kwargs: additional arguments to add_option"""
    helpStr = ( '|'.join( sorted( choicesDict.keys() ) ) +
                '[,param=value...]' )
    helpList = [ '%s=%s' % ( k, v.__name__ )
                 for k, v in choicesDict.items() ]
    helpStr += ' ' + ( ' '.join( helpList ) )
    params = dict( type='string', default=default, help=helpStr )
    params.update( **kwargs )
    opts.add_option( '--' + name, **params )

def version( *_args ):
    "Print Mininet version and exit"
    output( "%s\n" % VERSION )
    exit()


class MininetRunner( object ):
    "Build, setup, and run Mininet."

    def __init__( self ):
        "Init."
        self.options = None
        self.args = None  # May be used someday for more CLI scripts
        self.validate = None

        self.parseArgs()
        self.setup()
        self.begin()

    def custom( self, _option, _opt_str, value, _parser ):
        """Parse custom file and add params.
           option: option e.g. --custom
           opt_str: option string e.g. --custom
           value: the value the follows the option
           parser: option parser instance"""
        files = []
        if os.path.isfile( value ):
            # Accept any single file (including those with commas)
            files.append( value )
        else:
            # Accept a comma-separated list of filenames
            files += value.split(',')

        for fileName in files:
            customs = {}
            if os.path.isfile( fileName ):
                # pylint: disable=exec-used
                with open( fileName ) as f:
                    exec( compile( f.read(), fileName, 'exec' ),
                          customs, customs )
                for name, val in customs.items():
                    self.setCustom( name, val )
            else:
                raise Exception( 'could not find custom file: %s' % fileName )

    def setCustom( self, name, value ):
        "Set custom parameters for MininetRunner."
        if name in ( 'topos', 'switches', 'hosts', 'controllers', 'links'
                     'testnames', 'tests' ):
            # Update dictionaries
            param = name.upper()
            globals()[ param ].update( value )
        elif name == 'validate':
            # Add custom validate function
            self.validate = value
        else:
            # Add or modify global variable or class
            globals()[ name ] = value

    def setNat( self, _option, opt_str, value, parser ):
        "Set NAT option(s)"
        assert self  # satisfy pylint
        parser.values.nat = True
        # first arg, first char != '-'
        if parser.rargs and parser.rargs[ 0 ][ 0 ] != '-':
            value = parser.rargs.pop( 0 )
            _, args, kwargs = splitArgs( opt_str + ',' + value )
            parser.values.nat_args = args
            parser.values.nat_kwargs = kwargs
        else:
            parser.values.nat_args = []
            parser.values.nat_kwargs = {}

    def parseArgs( self ):
        """Parse command-line args and return options object.
           returns: opts parse options dict"""

        desc = ( "The %prog utility creates Mininet network from the\n"
                 "command line. It can create parametrized topologies,\n"
                 "invoke the Mininet CLI, and run tests." )

        usage = ( '%prog [options]\n'
                  '(type %prog -h for details)' )

        opts = OptionParser( description=desc, usage=usage )
        addDictOption( opts, SWITCHES, SWITCHDEF, 'switch' )
        addDictOption( opts, HOSTS, HOSTDEF, 'host' )
        addDictOption( opts, CONTROLLERS, [], 'controller', action='append' )
        addDictOption( opts, LINKS, LINKDEF, 'link' )
        addDictOption( opts, TOPOS, TOPODEF, 'topo' )

        opts.add_option( '--clean', '-c', action='store_true',
                         default=False, help='clean and exit' )
        opts.add_option( '--custom', action='callback',
                         callback=self.custom,
                         type='string',
                         help='read custom classes or params from .py file(s)'
                         )
        opts.add_option( '--test', default=[], action='append',
                         dest='test', help='|'.join( TESTS.keys() ) )
        opts.add_option( '--xterms', '-x', action='store_true',
                         default=False, help='spawn xterms for each node' )
        opts.add_option( '--ipbase', '-i', type='string', default='10.255.0.0/16',
                         help='base IP address for hosts' )
        opts.add_option( '--mac', action='store_true',
                         default=False, help='automatically set host MACs' )
        opts.add_option( '--arp', action='store_true',
                         default=False, help='set all-pairs ARP entries' )
        opts.add_option( '--verbosity', '-v', type='choice',
                         choices=list( LEVELS.keys() ), default = 'info',
                         help = '|'.join( LEVELS.keys() )  )
        opts.add_option( '--innamespace', action='store_true',
                         default=False, help='sw and ctrl in namespace?' )
        opts.add_option( '--listenport', type='int', default=6654,
                         help='base port for passive switch listening' )
        opts.add_option( '--nolistenport', action='store_true',
                         default=False, help="don't use passive listening " +
                         "port")
        opts.add_option( '--pre', type='string', default=None,
                         help='CLI script to run before tests' )
        opts.add_option( '--post', type='string', default=None,
                         help='CLI script to run after tests' )
        opts.add_option( '--pin', action='store_true',
                         default=False, help="pin hosts to CPU cores "
                         "(requires --host cfs or --host rt)" )
        opts.add_option( '--nat', action='callback', callback=self.setNat,
                         help="[option=val...] adds a NAT to the topology that"
                         " connects Mininet hosts to the physical network."
                         " Warning: This may route any traffic on the machine"
                         " that uses Mininet's"
                         " IP subnet into the Mininet network."
                         " If you need to change"
                         " Mininet's IP subnet, see the --ipbase option." )
        opts.add_option( '--version', action='callback', callback=version,
                         help='prints the version and exits' )
        opts.add_option( '--wait', '-w', action='store_true',
                         default=False, help='wait for switches to connect' )
        opts.add_option( '--twait', '-t', action='store', type='int',
                         dest='wait',
                         help='timed wait (s) for switches to connect' )
        opts.add_option( '--cluster', type='string', default=None,
                         metavar='server1,server2...',
                         help=( 'run on multiple servers (experimental!)' ) )
        opts.add_option( '--placement', type='choice',
                         choices=list( PLACEMENT.keys() ), default='block',
                         metavar='block|random',
                         help=( 'node placement for --cluster '
                                '(experimental!) ' ) )
        opts.add_option( '--workdir', '-W', type='string', default='/tmp/mnsec',
                         help='Specify the working directory' )
        opts.add_option( '--apps', type='string', default='',
                         metavar='h1=http,h1:ssh:port=22:ip=0.0.0.0,h2:snmp...',
                         help=('Specify apps to be run on nodes') )
        opts.add_option( '--enable_sflow', '-s', action='store_true',
                         default=False, help='enable sflow on switches' )
        opts.add_option( '--sflow_collector', type='string', default='127.0.0.1:6343',
                         help='Specify the sflow collector' )
        opts.add_option( '--sflow_sampling', type=int, default=64,
                         help='Specify the sflow sampling rate' )
        opts.add_option( '--sflow_polling', type=int, default=10,
                         help='Specify the sflow polling interval' )
        opts.add_option( '--disable_api', action='store_false', default=True,
                         help='disable API server and topology view' )
        opts.add_option( '--k8s_node_affinity', type='string', default='',
                         metavar='node1,k8s-node2,server3',
                         help=('Comma-separated list of nodes where pods should be created (K8s nodeAffinity)') )
        opts.add_option( '--topofile', type='string', default='',
                         help='Topology file location (yaml)' )
        opts.add_option( '--capture_dir', type='string', default='',
                         help='Directory to save capture files' )
        opts.add_option( '--capture_file_size', type='string', default='10',
                         help='Maximum size for capture files (only one file is saved)' )
        opts.add_option( '--capture_webshark_url', type='string', default='',
                         help='URL for webshark service' )
        opts.add_option( '--secrets_file', type='string', default='',
                         help='Filename containing secrets that will overwrite mnsec params' )

        self.options, self.args = opts.parse_args()

        # We don't accept extra arguments after the options
        if self.args:
            opts.print_help()
            exit()

    def setup( self ):
        "Setup and validate environment."

        # set logging verbosity
        if LEVELS[self.options.verbosity] > LEVELS['output']:
            warn( '*** WARNING: selected verbosity level (%s) will hide CLI '
                    'output!\n'
                    'Please restart Mininet with -v [debug, info, output].\n'
                    % self.options.verbosity )
        lg.setLogLevel( self.options.verbosity )

    # Maybe we'll reorganize this someday...
    # pylint: disable=too-many-branches,too-many-statements,global-statement

    def begin( self ):
        "Create and run mininet."

        global CLI

        opts = self.options

        if opts.cluster:
            servers = opts.cluster.split( ',' )
            for server in servers:
                ClusterCleanup.add( server )

        if opts.clean:
            cleanup()
            exit()

        start = time.time()

        if not opts.controller:
            # Update default based on available controllers
            CONTROLLERS[ 'default' ] = findController()
            opts.controller = [ 'default' ]
            if not CONTROLLERS[ 'default' ]:
                opts.controller = [ 'none' ]
                if opts.switch == 'default':
                    info( '*** No default OpenFlow controller found '
                          'for default switch!\n' )
                    info( '*** Falling back to OVS Bridge\n' )
                    opts.switch = 'ovsbr'
                elif opts.switch not in ( 'ovsbr', 'lxbr' ):
                    raise Exception( "Could not find a default controller "
                                     "for switch %s" %
                                     opts.switch )

        topo = buildTopo( TOPOS, opts.topo ) if not opts.topofile else None
        switch = customClass( SWITCHES, opts.switch )
        host = customClass( HOSTS, opts.host )
        controller = [ customClass( CONTROLLERS, c )
                       for c in opts.controller ]

        if opts.switch == 'user' and opts.link == 'default':
            debug( '*** Using TCULink with UserSwitch\n' )
            # Use link configured correctly for UserSwitch
            opts.link = 'tcu'

        link = customClass( LINKS, opts.link )

        if self.validate:
            self.validate( opts )

        if opts.nolistenport:
            opts.listenport = None

        # Handle innamespace, cluster options
        if opts.innamespace and opts.cluster:
            error( "Please specify --innamespace OR --cluster\n" )
            exit()
        Net = MininetSecWithControlNet if opts.innamespace else Mininet_sec
        if opts.cluster:
            warn( '*** WARNING: Experimental cluster mode!\n'
                  '*** Using RemoteHost, RemoteOVSSwitch, RemoteLink\n' )
            host, switch, link = RemoteHost, RemoteOVSSwitch, RemoteLink
            Net = partial( MininetCluster, servers=servers,
                           placement=PLACEMENT[ opts.placement ] )
            mininet.cli.CLI = ClusterCLI

        # Wait for controllers to connect unless we're running null test
        if ( opts.test and opts.test != [ 'none' ] and
             isinstance( opts.wait, bool ) ):
            opts.wait = True

        if opts.k8s_node_affinity:
            K8sPod.setup_node_affinity(opts.k8s_node_affinity)

        mn = Net( topo=topo,
                  topoFile=opts.topofile,
                  switch=switch, host=host, controller=controller, link=link,
                  ipBase=opts.ipbase, inNamespace=opts.innamespace,
                  xterms=opts.xterms, autoSetMacs=opts.mac,
                  autoStaticArp=opts.arp, autoPinCpus=opts.pin,
                  waitConnected=opts.wait,
                  workDir=opts.workdir, apps=opts.apps, enable_api=opts.disable_api,
                  enable_sflow=opts.enable_sflow, sflow_collector=opts.sflow_collector,
                  sflow_sampling=opts.sflow_sampling, sflow_polling=opts.sflow_polling,
                  captureDir=opts.capture_dir, captureFileSize=opts.capture_file_size,
                  captureWebSharkUrl=opts.capture_webshark_url,
                  secretsFile=opts.secrets_file,
                  listenPort=opts.listenport )

        if opts.ensure_value( 'nat', False ):
            with open( '/etc/resolv.conf' ) as f:
                if 'nameserver 127.' in f.read():
                    warn( '*** Warning: loopback address in /etc/resolv.conf '
                          'may break host DNS over NAT\n')
            mn.addNAT( *opts.nat_args, **opts.nat_kwargs ).configDefault()

        # --custom files can set CLI or change mininet.cli.CLI
        CLI = mnsec.cli.CLI if CLI is None else CLI

        if opts.pre:
            CLI( mn, script=opts.pre )

        mn.start()

        if opts.test:
            runTests( mn, opts.test )
        else:
            CLI( mn )

        if opts.post:
            CLI( mn, script=opts.post )

        mn.stop()

        elapsed = float( time.time() - start )
        info( 'completed in %0.3f seconds\n' % elapsed )


if __name__ == "__main__":
    try:
        MininetRunner()
    except KeyboardInterrupt:
        info( "\n\nKeyboard Interrupt. Shutting down and cleaning up...\n\n")
        cleanup()
    except Exception:  # pylint: disable=broad-except
        # Print exception
        type_, val_, trace_ = sys.exc_info()
        trace_str = traceback.format_exc().replace("\n", ", ")
        errorMsg = ( "-"*80 + "\n" +
                     "Caught exception. Cleaning up...\n\n" +
                     "%s: %s\n" % ( type_.__name__, val_ ) +
                     "Traceback: %s\n" % (trace_str) +
                     "-"*80 + "\n" )
        error( errorMsg )
        # Print stack trace to debug log
        import traceback
        stackTrace = traceback.format_exc()
        debug( stackTrace + "\n" )
        cleanup()
