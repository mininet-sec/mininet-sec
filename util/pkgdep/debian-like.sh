# -*- Mode:python; c-file-style:"gnu"; indent-tabs-mode:nil -*- */
#
# Copyright (C) 2024-2024, Italo Valcy (italovalcy@ufba.br)
# Copyright (C) 2015-2019, The University of Memphis,
#                          Arizona Board of Regents,
#                          Regents of the University of California.
#
# This file is part of Mininet-Sec and it was strongly based on
# Mini-NDN. All credits for Mini-NDN team. More information:
# http://github.com/named-data/mini-ndn/
#
# Mininet-Sec is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mininet-Sec is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mininet-Sec, e.g., in COPYING.md file.
# If not, see <http://www.gnu.org/licenses/>.

# APT packages, written in alphabetical order.
APT_PKGS=(
  build-essential
  ca-certificates
  git
  iptables-persistent
  bridge-utils
  nmap
  hping3
  mininet
  iperf3
  hydra
  netsniff-ng
  iproute2
  python3-pip
  tshark
)

install_pkgs() {
  $SUDO apt-get update
  $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${APT_PKGS[@]}"
  if [[ $PPA_AVAIL -eq 1 ]] && [[ ${#PPA_PKGS[@]} -gt 0 ]]; then
    $SUDO add-apt-repository -y -u ppa:italovalcy/ppa
    $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${PPA_PKGS[@]}"
  fi
}

prepare_ld() {
  return
}
