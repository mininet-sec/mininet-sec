# Mininet-Sec
Emulation platform for studying and experimenting cybersecurity tools in programmable networks

Install and run:
```
git clone https://github.com/mininet-sec/mininet-sec
cd mininet-sec
python3 -m pip install .

mnsec --topo=linear,3 --controller=remote,ip=127.0.0.1
```

## Credits

Many parts of the code here were inspired or directly derivated from great projects like
Mini-NDN (https://github.com/named-data/mini-ndn/), Mininet-WiFi 
(https://github.com/intrig-unicamp/mininet-wifi/) and, of course, Mininet
(https://github.com/mininet/mininet).
