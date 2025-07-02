FROM debian:bullseye-slim

RUN set -x \
 && export DEBIAN_FRONTEND=noninteractive \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
		iproute2 net-tools iputils-ping \
		socat procps curl jq tini uuid-runtime \
                python3-minimal libpython3-stdlib gnupg2 ca-certificates \
 && curl -fsSL https://packages.nlnetlabs.nl/aptkey.asc | gpg --dearmor -o /usr/share/keyrings/nlnetlabs-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/nlnetlabs-archive-keyring.gpg] https://packages.nlnetlabs.nl/linux/debian bullseye main" > /etc/apt/sources.list.d/nlnetlabs.list \
 && apt update \
 && apt install routinator \
 && rm -rf /var/lib/apt/lists/*

COPY files/ /

EXPOSE 3323/tcp
EXPOSE 8323/tcp
EXPOSE 9556/tcp


ENTRYPOINT ["/sbin/tini", "--", "routinator"]
CMD ["server", "--rtr", "0.0.0.0:3323", "--http", "0.0.0.0:8323", "--http", "0.0.0.0:9556"]
