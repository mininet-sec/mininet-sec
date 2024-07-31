#
# Copyright (C) 2024-2024, Italo Valcy (italovalcy@ufba.br)
# Copyright (C) 2019-2021, Open Networking Foundation
#
# This file is part of Mininet-Sec and it was strongly based on
# FOP4. All credits for FOP4 team. More information:
# https://github.com/ANTLab-polimi/FOP4/
#
# Mininet-Sec is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This file:
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import multiprocessing
import os
import random
import re
import socket
import threading
from contextlib import closing

import time
from mininet.log import info, warn
from mininet.node import Switch, Host

SIMPLE_SWITCH_GRPC = 'simple_switch_grpc'
SIMPLE_SWITCH_CLI = 'simple_switch_CLI'
PKT_BYTES_TO_DUMP = 80
SWITCH_START_TIMEOUT = 5  # seconds
BMV2_LOG_LINES = 5
BMV2_DEFAULT_DEVICE_ID = 1


def parseBoolean(value):
    if value in ['1', 1, 'true', 'True']:
        return True
    else:
        return False


def pickUnusedPort():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    addr, port = s.getsockname()
    s.close()
    return port


def writeToFile(path, value):
    with open(path, "w") as f:
        f.write(str(value))


def watchDog(sw):
    while True:
        if Bmv2Switch.mininet_exception == 1:
            sw.killBmv2(log=False)
            return
        if sw.stopped:
            return
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            if s.connect_ex(('127.0.0.1', sw.grpcPort)) == 0:
                time.sleep(5)
            else:
                warn("\n*** WARN: BMv2 instance %s died!\n" % sw.name)
                sw.printBmv2Log()
                print(("-" * 80) + "\n")
                return


class P4Host(Host):
    def __init__(self, name, inNamespace=True, **params):
        Host.__init__(self, name, inNamespace=inNamespace, **params)

    def config(self, **params):
        r = super(Host, self).config(**params)
        for off in ["rx", "tx", "sg"]:
            cmd = "/sbin/ethtool --offload %s %s off" \
                  % (self.defaultIntf(), off)
            self.cmd(cmd)
        # disable IPv6
        self.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")
        return r


class Bmv2Switch(Switch):
    """BMv2 software switch with gRPC server"""
    # Shared value used to notify to all instances of this class that a Mininet
    # exception occurred. Mininet exception handling doesn't call the stop()
    # method, so the mn process would hang after clean-up since Bmv2 would still
    # be running.
    mininet_exception = multiprocessing.Value('i', 0)

    def __init__(self, name, json=None, debugger=False, loglevel="warn",
                 elogger=False, grpcport=None, cpuport=255, notifications=False,
                 thriftport=None, netcfg=True, dryrun=False, pipeconf="",
                 pktdump=False, gnmi=False,
                 portcfg=True, switch_config=None, **kwargs):
        Switch.__init__(self, name, **kwargs)
        self.grpcPort = grpcport
        self.thriftPort = thriftport
        self.cpuPort = cpuport
        self.json = json
        self.debugger = parseBoolean(debugger)
        self.notifications = parseBoolean(notifications)
        self.loglevel = loglevel
        # Important: Mininet removes all /tmp/*.log files in case of exceptions.
        # We want to be able to see the bmv2 log if anything goes wrong, hence
        # avoid the .log extension.
        self.logfile = '/tmp/bmv2-%s-log' % self.name
        self.elogger = parseBoolean(elogger)
        self.pktdump = parseBoolean(pktdump)
        self.netcfg = parseBoolean(netcfg)
        self.dryrun = parseBoolean(dryrun)
        self.netcfgfile = '/tmp/bmv2-%s-netcfg.json' % self.name
        self.pipeconfId = pipeconf
        self.injectPorts = parseBoolean(portcfg)
        self.withGnmi = parseBoolean(gnmi)
        self.p4DeviceId = BMV2_DEFAULT_DEVICE_ID
        self.logfd = None
        self.bmv2popen = None
        self.stopped = False
        self.switch_config = switch_config
        # Remove files from previous executions
        self.cleanupTmpFiles()

    def start(self, controllers):
        bmv2Args = [SIMPLE_SWITCH_GRPC] + self.grpcTargetArgs()

        cmdString = " ".join(bmv2Args)

        if self.dryrun:
            info("\n*** DRY RUN (not executing bmv2)")

        info("\nStarting BMv2 target: %s\n" % cmdString)

        writeToFile("/tmp/bmv2-%s-grpc-port" % self.name, self.grpcPort)
        writeToFile("/tmp/bmv2-%s-thrift-port" % self.name, self.thriftPort)

        if self.dryrun:
            return

        try:
            # Start the switch
            self.logfd = open(self.logfile, "w")
            self.bmv2popen = self.popen(cmdString,
                                        stdout=self.logfd,
                                        stderr=self.logfd)
            self.waitBmv2Start()
            # We want to be notified if BMv2 dies...
            threading.Thread(target=watchDog, args=[self]).start()
            if self.json is not None:
                if self.switch_config is not None:
                    # Switch initial configuration using Thrift CLI
                    try:
                        with open(self.switch_config, mode='r') as f:
                            # map(self.bmv2Thrift(), f.readlines())
                            for cmd_row in f:
                                self.bmv2Thrift(cmd_row)
                        info("\nSwitch has been configured with %s configuration file" % self.switch_config)
                    except IOError:
                        info("\nSwitch configuration file %s not found" % self.switch_config)
        except Exception:
            Bmv2Switch.mininet_exception = 1
            self.killBmv2()
            self.printBmv2Log()
            raise

    def bmv2Thrift(self, *args, **kwargs):
        "Run ovs-vsctl command (or queue for later execution)"
        cli_command = SIMPLE_SWITCH_CLI + " --thrift-port " + str(self.thriftPort) + " <<< "
        switch_cmd = ' '.join(map(str, [ar for ar in args if ar is not None]))
        command = cli_command + '"' + switch_cmd + '"'
        self.cmd(command)

    def attach(self, intf):
        """ Connect a new data port """
        # TODO: find a better way to add a port at runtime
        if self.pktdump:
            pcapFiles = ["./" + str(intf) + "_out.pcap", "./" + str(intf) + "_in.pcap"]
            self.bmv2Thrift('port_add', intf, next(key for key, value in list(self.intfs.items()) if value == intf), *pcapFiles)
        else:
            self.bmv2Thrift('port_add', intf, next(key for key, value in list(self.intfs.items()) if value == intf))
        self.cmd('ifconfig', intf, 'up')

    def grpcTargetArgs(self):
        if self.grpcPort is None:
            self.grpcPort = pickUnusedPort()
        if self.thriftPort is None:
            self.thriftPort = pickUnusedPort()
        args = ['--device-id %s' % self.p4DeviceId]
        for port, intf in list(self.intfs.items()):
            if not intf.IP():
                args.append('-i %d@%s' % (port, intf.name))
        args.append('--thrift-port %s' % self.thriftPort)
        if self.notifications:
            ntfaddr = 'ipc:///tmp/bmv2-%s-notifications.ipc' % self.name
            args.append('--notifications-addr %s' % ntfaddr)
        if self.elogger:
            nanologaddr = 'ipc:///tmp/bmv2-%s-nanolog.ipc' % self.name
            args.append('--nanolog %s' % nanologaddr)
        if self.debugger:
            dbgaddr = 'ipc:///tmp/bmv2-%s-debug.ipc' % self.name
            args.append('--debugger-addr %s' % dbgaddr)
        args.append('--log-console')
        if self.pktdump:
            args.append('--pcap --dump-packet-data %s' % PKT_BYTES_TO_DUMP)
        args.append('-L%s' % self.loglevel)
        if not self.json:
            args.append('--no-p4')
        else:
            args.append(self.json)
        # gRPC target-specific options
        args.append('--')
        args.append('--cpu-port %s' % self.cpuPort)
        args.append('--grpc-server-addr 0.0.0.0:%s' % self.grpcPort)
        return args

    def waitBmv2Start(self):
        # Wait for switch to open gRPC port, before sending to the controller.
        # Include time-out just in case something hangs.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        endtime = time.time() + SWITCH_START_TIMEOUT
        while True:
            result = sock.connect_ex(('127.0.0.1', self.grpcPort))
            if result == 0:
                # The port is open. Let's go! (Close socket first)
                sock.close()
                break
            # Port is not open yet. If there is time, we wait a bit.
            if endtime > time.time():
                time.sleep(0.1)
            else:
                # Time's up.
                raise Exception("Switch did not start before timeout")

    def printBmv2Log(self):
        if os.path.isfile(self.logfile):
            print("-" * 80)
            print("%s log (from %s):" % (self.name, self.logfile))
            with open(self.logfile, 'r') as f:
                lines = f.readlines()
                if len(lines) > BMV2_LOG_LINES:
                    print("...")
                for line in lines[-BMV2_LOG_LINES:]:
                    print(line.rstrip())

    def killBmv2(self, log=False):
        if self.bmv2popen is not None:
            self.bmv2popen.kill()
        if self.logfd is not None:
            if log:
                self.logfd.write("*** PROCESS TERMINATED BY MININET ***\n")
            self.logfd.close()

    def cleanupTmpFiles(self):
        self.cmd("rm -f /tmp/bmv2-%s-*" % self.name)

    def stop(self, deleteIntfs=True):
        """Terminate switch."""
        self.stopped = True
        self.killBmv2(log=True)
        Switch.stop(self, deleteIntfs)
