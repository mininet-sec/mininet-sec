import sys
import warnings
from cryptography.utils import CryptographyDeprecationWarning
warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

#from scapy.sendrecv import sniff,sendp
from scapy.all import sniff,sendp

if len(sys.argv) != 2:
    print("USAGE %s INTERFACE" % sys.argv[0])
    sys.exit(1)

sniff(iface=sys.argv[1], filter="inbound", prn = lambda p: sendp(p, iface=sys.argv[1], verbose=0))
