FROM debian:bullseye-slim

RUN set -x \
 && export DEBIAN_FRONTEND=noninteractive \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
		iproute2 net-tools iputils-ping \
		socat procps curl jq tini uuid-runtime coreutils \
                python3-minimal libpython3-stdlib gnupg2 ca-certificates \
 && curl -fsSL https://packages.nlnetlabs.nl/aptkey.asc | gpg --dearmor -o /usr/share/keyrings/nlnetlabs-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/nlnetlabs-archive-keyring.gpg] https://packages.nlnetlabs.nl/linux/debian bullseye main" > /etc/apt/sources.list.d/nlnetlabs.list \
 && apt update \
 && apt install -y krill \
 && rm -rf /var/lib/apt/lists/*

COPY files/ /

EXPOSE 3000/tcp

ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
CMD ["krill", "-c", "/var/krill/data/krill.conf"]
