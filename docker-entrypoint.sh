#!/bin/bash
set -e

usage() {
  echo "docker run hackinsdn/mininet-sec [options]"
  echo "    -h, --help                    display help information"
  echo "    /path/program ARG1 .. ARGn    execute the specified local program"
  echo "    URL ARG1 .. ARGn              download script from URL and execute it"
  echo "    --ARG1 .. --ARGn              execute mininet with these arguments"
}

launch() {
  # If first argument is a URL then download the script and execute it passing
  # it the rest of the arguments
  if [[ $1 =~ ^(file|http|https|ftp|ftps):// ]]; then
    curl -s -o ./script $1
    chmod 755 ./script
    shift
    exec ./script $@

  # If first argument is an absolute file path then execute that file passing
  # it the rest of the arguments
  elif [[ $1 =~ ^/ ]]; then
    exec $@

  # If first argument looks like an argument then execute mininet with all the
  # arguments
  elif [[ $1 =~ ^- ]]; then
    exec mnsec $@

  # Unknown argument
  else
    usage
  fi
}

if [ $# -eq 0 ] || [ $1 = "-h" -o $1 = "--help" ]; then
  usage
  exit 0
fi

# Start the Open Virtual Switch Service
service openvswitch-switch start
ovs-vsctl set-manager ptcp:6640

launch $@
