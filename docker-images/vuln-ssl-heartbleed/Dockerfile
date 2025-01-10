FROM debian/eol:wheezy

RUN --mount=source=.,target=/mnt,type=bind \
    export DEBIAN_FRONTEND=noninteractive \
 && apt-get update \
 && apt-get install -y --no-install-recommends apache2 ssl-cert net-tools iputils-ping curl \
 && dpkg -i /mnt/packages/* \
 && a2enmod ssl \
 && a2ensite default-ssl \
 && rm -rf /var/lib/apt/lists/*

EXPOSE 443/tcp

COPY docker-entrypoint.sh /

ENTRYPOINT ["/docker-entrypoint.sh"]
