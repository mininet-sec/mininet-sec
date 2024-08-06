FROM debian:bookworm-slim
MAINTAINER Italo Valcy <italovalcy@gmail.com>

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends --no-install-suggests iputils-ping net-tools tcpdump x11-xserver-utils \
		xterm iperf socat telnet tmux git iptables-persistent \
		bridge-utils nmap hping3 mininet iperf3 hydra iproute2 \
		python3-pip libpq-dev openvswitch-testcontroller curl d-itg \
 && rm -f /usr/lib/python3.11/EXTERNALLY-MANAGED \
 && python3 -m pip install -e git+https://github.com/mininet-sec/mininet-sec@main#egg=mnsec \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src/mininet-sec
COPY docker-entrypoint.sh /docker-entrypoint.sh

EXPOSE 8050 6640

ENTRYPOINT ["/docker-entrypoint.sh"]
