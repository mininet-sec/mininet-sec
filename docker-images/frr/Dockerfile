FROM quay.io/frrouting/frr:master

RUN set -x \
 && sed -i '/^ospfd=/s/no/yes/g; /^ospf6d=/s/no/yes/g; /^bgpd=/s/no/yes/g; s/ldpd=no/ldpd=yes/g; /^bgpd_options=/s/127.0.0.1"/127.0.0.1 -M rpki"/; /^bgpd=yes/i zebra=yes\nstaticd=yes' /etc/frr/daemons \
 && touch /etc/frr/vtysh.conf /etc/frr/frr.conf \
 && chown frr:frr /etc/frr/vtysh.conf /etc/frr/frr.conf

COPY files/ /
