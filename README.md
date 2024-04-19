# Mininet-Sec
Emulation platform for studying and experimenting cybersecurity tools in programmable networks

Install and run:
```
git clone https://github.com/mininet-sec/mininet-sec
cd mininet-sec
python3 -m pip install .
sudo apt-get install iptables-persistent bridge-utils nmap hping3 mininet iperf3 hydra

mnsec --topo linear,3 --apps h1:ssh:port=22,h1:http:port=80,h2:ldap,h3:smtp,h3:imap,h3:pop3 --controller=remote,ip=127.0.0.1

python3 examples/firewall.py

curl -LO https://raw.githubusercontent.com/danielmiessler/SecLists/master/Usernames/top-usernames-shortlist.txt
curl -LO https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Common-Credentials/top-passwords-shortlist.txt
mnsecx o1 hydra -L top-usernames-shortlist.txt -P top-usernames-shortlist.txt imap://10.0.0.2/LOGIN
```

## Credits

Many parts of the code here were inspired or directly derivated from great projects like
Mini-NDN (https://github.com/named-data/mini-ndn/), Mininet-WiFi 
(https://github.com/intrig-unicamp/mininet-wifi/) and, of course, Mininet
(https://github.com/mininet/mininet).
