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

if [[ $(expr $VERSION_ID '<' 20.04) == 1 ]]; then
  cat <<EOT
Ubuntu 20.04 or newer is required
Installation on older versions may fail
EOT
fi

source "$PKGDEPDIR/debian-like.sh"

if [[ $VERSION_ID == '20.04' ]]; then
  APT_PKGS+=(
    libigraph0-dev
  )
else
  APT_PKGS+=(
    libigraph-dev
  )
fi

if [[ $VERSION_ID == '20.04' ]] || [[ $VERSION_ID == '21.10' ]]; then
  PPA_AVAIL=1
fi
