function requestAddNode(nodeName, nodeType, params) {
    var result = false;
    const requestOptions = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({name: nodeName, type: nodeType, params: params})
    };
    const request = async () => {
        const response = await fetch('/add_node', requestOptions);
        const resText = await response.text();
        if (!response.ok) {
          alert(`Error while adding node: ${resText}`);
          return "";
        }
        return resText;
    }
    var resText = request();
    return resText;
}
function mnsecAddLink() {
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
	      const intf1 = result["intf1"].split("-");
	      const intf2 = result["intf2"].split("-");
              cy.add({
                  data: {
                      id: Date.now(),
                      source: source,
                      target: target,
                      slabel: intf1.at(-1),
                      tlabel: intf2.at(-1),
                      source_interface: result["intf1"],
                      target_interface: result["intf2"],
                  },
              });
          });
  }
}
function mnsecAddGroup() {
  var groupId = cy.nodes("[type = 'group']").length + 1;
  let groupName = prompt("Group name (only letters and numbers)", `group-${groupId}`);
  if (!groupName) {
    return false;
  }
  const selectedNodes = cy.nodes(":selected");
  const selectedNodeIds = selectedNodes.map((node) =>
      node.data("label")
  );
  const requestOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({nodes: selectedNodeIds, group: groupName})
  };
  fetch('/add_group', requestOptions)
      .then(response => {
          if (!response.ok) {
              response.text().then(text => {
                  alert(`Error while adding group: ${text}`);
              });
              return false;
          }
          return response.json();
      })
      .then(result => {
          if (!result) {
             return false;
          }
          cy.add({data: {id: groupName, label: groupName, type:"group"}, classes: ["groupnode"]});
          selectedNodes.move({parent: groupName});
      });
}
function mnsecStartCapture(link) {
  console.log('Start capture on Edge:', link.id(), link.data());
  if (!link) {
    return false;
  }
  const requestOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(link.data())
  };
  fetch('/start_capture', requestOptions)
      .then(response => {
          if (!response.ok) {
              response.text().then(text => {
                  alert(`Error while starting capture: ${text}`);
              });
              return false;
          }
          return response.json();
      })
      .then(result => {
          if (!result) {
            return false;
          }
	  link.data("capture", result["capture"]);
      });
}
function mnsecStopCapture(link) {
  console.log('Stop capture on link:', link.id(), link.data());
  if (!link) {
    return false;
  }
  const requestOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(link.data())
  };
  fetch('/stop_capture', requestOptions)
      .then(response => {
          if (!response.ok) {
              response.text().then(text => {
                  alert(`Error while starting capture: ${text}`);
              });
              return false;
          }
          return response.json();
      })
      .then(result => {
          if (!result) {
            return false;
          }
	  link.removeData("capture");
      });
}
function mnsecViewCapture(link) {
  const captureFile = link.data("capture");
  if (!captureFile) {
    console.log('Cannot view capture on link - not running:', link.id(), link.data());
    alert(`Cannot view capture on link - not running`);
  }
  window.open(`/webshark/#${captureFile}`, "_blank");
}
window.dashCytoscapeFunctions = Object.assign(
    {},
    window.dashCytoscapeFunctions,
    {
        mnsec_add_host: function (event) {
            var pos = event.position || event.cyPosition;
	    var hostId = cy.nodes("[type = 'host']").length + 1;
            var result = requestAddNode(`h${hostId}`, "proc", {});
            if (result) {
              result.then(function(displayImg){
                if (!displayImg) {
                  return "";
                }
                cy.add({
                  data: {
		    id: `h${hostId}`,
		    label: `h${hostId}`,
		    type: "host",
                    url: `/assets/${displayImg}`,
                  },
                  position: {
                      x: pos.x,
                      y: pos.y,
                  },
                  classes: ['rectangle'],
                });
              });
            }
        },
        mnsec_add_switch: function (event) {
            var pos = event.position || event.cyPosition;
	    var switchId = cy.nodes("[type = 'switch']").length + 1;
            var result = requestAddNode(`s${switchId}`, "ovs", {});
            if (result) {
              result.then(function(displayImg){
                if (!displayImg) {
                  return "";
                }
                cy.add({
                  data: {
		    id: `s${switchId}`,
		    label: `s${switchId}`,
		    type: "switch",
                    url: `/assets/${displayImg}`,
                  },
                  position: {
                      x: pos.x,
                      y: pos.y,
                  },
                  classes: ['rectangle'],
                });
              });
            }
        },
        mnsec_add_link: function (event) {
	    mnsecAddLink();
        },
        mnsec_open_xterm: function (event) {
	    const selectedNodes = cy.nodes(":selected");
            const selectedNodeIds = selectedNodes.map((node) =>
                node.data("label")
            );
            selectedNodeIds.forEach((nodeid) => {window.open(`/xterm/${nodeid}`, "_blank");});
        },
        mnsec_add_group: function (event) {
            mnsecAddGroup();
        },
        mnsec_start_capture: function (event) {
            mnsecStartCapture(event.target);
        },
        mnsec_stop_capture: function (event) {
            mnsecStopCapture(event.target);
        },
        mnsec_view_capture: function (event) {
            mnsecViewCapture(event.target);
        },
    }
);
