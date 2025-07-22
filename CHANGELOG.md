# Changelog

## [UNRELEASED] - Under development

- Added support for touch devices
- Added feature to open host terminal based on double check in the Mininet-Sec Web UI
- Added script to setup DNS service based on bind9 (`service-mnsec-bind9.sh`), with options: enable the DNS server, enable recursion, add a zone, add entires to a zone
- Fixed issue with Kubernetes terminals that could freeze/stop-working after a while
- Added feature to display images for hosts, switches, Pods, etc
- Added option to allow user to provide an URL with image to be displayed (`img_url`)
- Added option to allow Mininet-Sec hosts to configure DNS resolvers (`dns_nameservers`)
- Added option to allow run post startup commands (`postStart`)
- Added option to run the Kubernetes Pods without isolating the control network (i.e., network provided by Kubernets, usually `eth0`) keeping the control net in the root netns (`isolateControlNet`)
- Fixed issue with bind9 mnsec service for the regex to validade zone being added
- Added support for sysctls definition on Kubernetes Pods

## [1.1.0] - 2025-01-10

- Enhancements on the topology component for loading topology from YAML files
- Kubernetes backend was refactored to leverage a Kubernetes Proxy being developed on the context of HackInSDN project, which will allow fine-grained control about Pods being created via Mininet-Sec as well as it will eliminate the requirement of Kube config on the Mininet-Sec pod
- Isolating management IP address from Pods created via Mininet-Sec for a `mgmt` Linux network namespace in order to provide more isolation from th Kubernetes Pod network (not having the kubernetes pod network is not an option, otherwise we cannot create the VXLAN tunnels)
- Added support for L2TP tunnels to provide connectivity with Pods and changing this protocol to be the default option to allow interconnecting with Pod containers with old software (VXLAN was introduced around 2014)
- Enhance `examples/` with many usage examples and use cases
- Refactor Docker image to include new tools
- Routing Helper component now adds a default route with next hop being a null interface. This was necessary to allow running spoofed network tests in scenarios where the host server applies loose RPF check on Linux Kernel.
- Adding Scripts to allow running real servers in addition to Simulated services. Currently we are supporting Apache2 (HTTP and HTTPS), OpenSSH (SSH) and Dovecot (IMAP, POP3, IMAPS, POP3S).
- Allow multiple xterm sessions simultaneously for the same host
- Fix server disconnected events for Xterm to allow closing the Browser tab and also finishing the xterm socketio session, as well as allowing the user to hit CTRL+D and closing the tab
- Change the API Server startup order to allow a Loading message prior to the topology being actually available
- Change the Topology visualization to allow creating the groups from python topology setup (`group` attribute for Hosts and Switches)

## [1.0.0] - 2024-09-16

This is the first release of Mininet-Sec. The first release include a set of features:

- Extended Mininet implementation to add support for a Web Interface for topology visualization and management
- Added Cybersecurity components, like Firewall, IDS, offensive security tools
- Added support for Simulated Applications with more than 30 network services available (HTTP, HTTPS, LDAP, SSH, IMAP, SMTP, POP3, etc)
- Added integration with traffic generators like Cisco Trex (see Secflood project at https://github.com/hackinsdn/secflood)
- Added integration with Kubernetes and interconnection of hosts via VXLAN
