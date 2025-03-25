FROM debian:bookworm-slim
MAINTAINER Italo Valcy <italovalcy@gmail.com>

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends --no-install-suggests tini iputils-ping net-tools tcpdump x11-xserver-utils \
		xterm iperf socat telnet tmux git iptables-persistent traceroute \
		bridge-utils nmap hping3 mininet iperf3 hydra iproute2 \
		python3-pip libpq-dev openvswitch-switch openvswitch-testcontroller curl jq d-itg \
		gcc python3-dev vim hashcat dstat \
		apache2 ntp ssh bind9 dovecot-imapd dovecot-pop3d \
 && rm -f /usr/lib/python3.11/EXTERNALLY-MANAGED \
 && cd /tmp \
 && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
 && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
 && curl -LO https://github.com/italovalcy/ali/releases/download/v0.7.6/ali_0.7.6_linux_amd64.deb \
 && dpkg -i ali_0.7.6_linux_amd64.deb \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /tmp/*

COPY . /src/mnsec
RUN python3 -m pip install --no-cache-dir -e /src/mnsec

WORKDIR /src/mnsec
COPY docker-entrypoint.sh /docker-entrypoint.sh

EXPOSE 8050 6640

ENTRYPOINT ["/usr/bin/tini", "--", "/docker-entrypoint.sh"]
