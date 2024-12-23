FROM debian/eol:wheezy

RUN --mount=source=.,target=/mnt,type=bind \
    export DEBIAN_FRONTEND=noninteractive \
 && apt-get update \
 && apt-get install -y --no-install-recommends apache2 net-tools iputils-ping curl \
 && dpkg -i /mnt/packages/* \
 && a2enmod ssl \
 && rm -rf /var/lib/apt/lists/*

EXPOSE 443/tcp

ENTRYPOINT ["/usr/sbin/apache2ctl", "-DFOREGROUND"]
