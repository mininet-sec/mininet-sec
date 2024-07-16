# -*- Mode:bash; c-file-style:"gnu"; indent-tabs-mode:nil -*- */
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

# needed by Python version detection logic in Mininet install script
export PYTHON=python3

# DEP_INFO key should match *_VERSION variable name.
# DEP_INFO entry should have these comma separated fields:
# [0] local directory name
# [1] dep name
# [2] PPA package name
# [3] GitHub repository (HTTPS)
# [4] Gerrit repository (repo name only)
declare -A DEP_INFO
DEP_INFO=(
  ["slowloris"]="slowloris,slowloris,slowloris,https://github.com/gkbrk/slowloris,"
  #["mausezahn"]="mausezahn,mausezahn,mausezahn,https://github.com/netsniff-ng/netsniff-ng,"
)

install_slowloris() {
  $SUDO $PYTHON setup.py install
  $SUDO install -m0755 -T slowloris.py /usr/local/bin/slowloris
}

# set to 1 if dep needs downloading
declare -A NEED_DL

# download dep source code
dep_checkout() {
  if [[ ${NEED_DL[$1]} -ne 1 ]]; then
    return
  fi
  local INFO=()
  IFS=',' read -a INFO <<< "${DEP_INFO[$1]}"
  local DLDIR="${CODEROOT}/${INFO[0]}"

  echo "Downloading ${INFO[1]} from GitHub (default branch)"
  git clone --recurse-submodules "${INFO[3]}" "$DLDIR"
}

# install dep from source code
dep_install() {
  local INFO=()
  IFS=',' read -a INFO <<< "${DEP_INFO[$1]}"
  local DLDIR="${CODEROOT}/${INFO[0]}"
  if dep_exists $1 || ! [[ -d "$DLDIR" ]]; then
    return
  fi
  pushd "$DLDIR"

  local FN="install_$1"
  if declare -F $FN >/dev/null; then
    echo "Installing ${INFO[1]} with custom command"
    $FN
  else
    echo "Dont know how to install ${INFO[1]}: no custom command defined"
    echo "you need to define a function called $FN with specific install script"
    popd
    exit 1
  fi
  popd
}

if [[ $PPA_AVAIL -ne 1 ]] || [[ $NO_PPA -eq 1 ]]; then
  PREFER_FROM=source
fi

echo "Will download to ${CODEROOT}"
echo 'Will install compiler and build tools'
if [[ $DL_ONLY -ne 1 ]]; then
  echo "Will compile with ${NJOBS} parallel jobs"
fi

if [[ $CONFIRM -ne 1 ]]; then
  read -p 'Press ENTER to continue or CTRL+C to abort '
fi

install_pkgs

$SUDO $PYTHON -m pip install setuptools==69.2.0

if [[ -z $SKIPPYTHONCHECK ]]; then
  PYTHON_VERSION=$($PYTHON --version)
  SUDO_PYTHON_VERSION=$($SUDO $PYTHON --version)
  if [[ "$PYTHON_VERSION" != "$SUDO_PYTHON_VERSION" ]]; then
    cat <<EOT
In your system, '${PYTHON}' is ${PYTHON_VERSION} and '$SUDO ${PYTHON}' is ${SUDO_PYTHON_VERSION}
You must manually resolve the conflict, e.g. delete excess Python installation or change $PATH
To bypass this check, set the environment variable SKIPPYTHONCHECK=1
EOT
    exit 1
  fi
fi

if ! mkdir -p "${CODEROOT}" 2>/dev/null; then
  $SUDO mkdir -p "${CODEROOT}"
  $SUDO chown $(id -u) "${CODEROOT}"
fi

for DEP in "${DEPLIST[@]}"; do
  dep_checkout $DEP
done

if [[ $DL_ONLY -eq 1 ]]; then
  cat <<EOT
Source code has been downloaded to ${CODEROOT}
You may make changes or checkout different versions
Run this script again without --dl-only to install from local checkout
EOT
  exit 0
fi

prepare_ld
for DEP in "${DEPLIST[@]}"; do
  dep_install $DEP
done
$SUDO ldconfig

DESTDIR=/usr/local/etc/mininet-sec
$SUDO install -d -m0755 "$DESTDIR"
find examples/ -type f | xargs $SUDO install -m0644 -t "$DESTDIR/"
$SUDO $PYTHON -m pip install .

echo 'Mininet-Sec installation completed successfully'
