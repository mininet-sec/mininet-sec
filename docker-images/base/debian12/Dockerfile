FROM debian:bookworm-slim

RUN set -x \
 && export DEBIAN_FRONTEND=noninteractive \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
		iproute2 net-tools iputils-ping \
		socat procps curl jq \
                python3-minimal libpython3-stdlib \
 && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["tail", "-f", "/dev/null"]
