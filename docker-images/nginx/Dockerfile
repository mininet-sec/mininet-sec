FROM nginx:latest

RUN set -x \
 && export DEBIAN_FRONTEND=noninteractive \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
		iproute2 net-tools iputils-ping \
		socat procps curl jq \
 && rm -rf /var/lib/apt/lists/*

COPY files/ /
