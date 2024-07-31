function requestAddNode(nodeName, nodeType) {
    var result = false;
    const requestOptions = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({name: nodeName, type: nodeType})
    };
    fetch('/add_node', requestOptions)
	.then((response) => {
	    if (!response.ok) {
		response.text().then(text => { 
                    alert(`Error while adding node: ${text}`);
		});
		return false;
            }
	    return response.json();
        })
	.then((data) => {
	    result = data;
	});
    return result;
}
window.dashCytoscapeFunctions = Object.assign(
    {},
    window.dashCytoscapeFunctions,
    {
        mnsec_add_host: function (event) {
            var pos = event.position || event.cyPosition;
	    var hostId = cy.nodes("[type = 'host']").length + 1;
            cy.add({
                data: {
                    group: 'nodes',
		    id: `h${hostId}`,
		    label: `h${hostId}`,
		    type: "host",
                },
                position: {
                    x: pos.x,
                    y: pos.y,
                },
		classes: ['rectangle'],
            });
	    requestAddNode(`h${hostId}`, "host");
        },
        mnsec_add_switch: function (event) {
            var pos = event.position || event.cyPosition;
	    var switchId = cy.nodes("[type = 'switch']").length + 1;
            cy.add({
                data: {
                    group: 'nodes',
		    id: `s${switchId}`,
		    label: `s${switchId}`,
		    type: "switch",
                },
                position: {
                    x: pos.x,
                    y: pos.y,
                },
		classes: [],
            });
	    requestAddNode(`s${switchId}`, "switch");
        },
        mnsec_add_link: function (event) {
	    const selectedNodes = cy.nodes(":selected");
            const selectedNodeIds = selectedNodes.map((node) =>
                node.data("label")
            );
	    var source;
	    var target;
            if (selectedNodes.length === 0) {
                alert('Error: No nodes selected, cannot add edge');
            } else if (selectedNodes.length === 1) {
		source = selectedNodeIds[0];
		target = selectedNodeIds[0];
            } else if (selectedNodes.length === 2) {
		source = selectedNodeIds[0];
		target = selectedNodeIds[1];
            } else {
                alert('Error: more than 2 nodes selected, cannot add edge');
            }
	    if (source && target) {
                const requestOptions = {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({node1: source, node2: target})
                };
                fetch('/add_link', requestOptions)
	            .then(response => {
	                if (!response.ok) {
		            response.text().then(text => { 
                                alert(`Error while adding node: ${text}`);
		            });
			    return false;
                        }
	                return response.json();
                    })
	            .then(result => {
			if (!result) {
			    return false;
	                }
                        cy.add({
                            data: {
                                id: Date.now(),
                                group: 'edges',
                                source: source,
                                target: target,
	                	    slabel: result["intf1"],
	                	    tlabel: result["intf2"],
                            },
                        });
		    });
	    }
        },
        mnsec_open_xterm: function (event) {
	    const selectedNodes = cy.nodes(":selected");
            const selectedNodeIds = selectedNodes.map((node) =>
                node.data("label")
            );
            selectedNodeIds.forEach((nodeid) => {window.open(`/xterm/${nodeid}`, "_blank");});
        },
        mnsec_add_group: function (event) {
	    var groupId = cy.nodes("[type = 'group']").length + 1;
	    cy.add({data: {group: "nodes", id: `group-${groupId}`, label:`group-${groupId}`, type:"group"}, classes: ["groupnode"]});
	    cy.nodes(":selected").move({parent:  `group-${groupId}`});
        },
    }
);
