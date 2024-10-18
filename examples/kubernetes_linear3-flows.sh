ovs-ofctl add-flow -O OpenFlow13 s1 in_port=1,actions=push_vlan:0x88a8,mod_vlan_vid:4000,output:2
ovs-ofctl add-flow -O OpenFlow13 s1 in_port=2,dl_vlan=4000,actions=pop_vlan,output:1
ovs-ofctl add-flow -O OpenFlow13 s2 in_port=2,dl_vlan=4000,actions=output:3,pop_vlan,output:1
ovs-ofctl add-flow -O OpenFlow13 s2 in_port=3,dl_vlan=4000,actions=output:2,pop_vlan,output:1
ovs-ofctl add-flow -O OpenFlow13 s3 in_port=1,actions=push_vlan:0x88a8,mod_vlan_vid:4000,output:2
ovs-ofctl add-flow -O OpenFlow13 s3 in_port=2,dl_vlan=4000,actions=pop_vlan,output:1
