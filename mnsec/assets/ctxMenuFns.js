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
// canvas position for the node being added: set by the "Add Node" context menu
// entry, consumed when the modal opens (null when opened from the menubar)
let mnsecPendingNodePosition = null;
let mnsecNewNodePosition = null;
function mnsecOpenNewNodeModal() {
  const modal = document.querySelector('#new-node-modal');
  if (!modal) {
    return;
  }
  mnsecNewNodePosition = mnsecPendingNodePosition;
  mnsecPendingNodePosition = null;
  // attach dismiss handlers only once (nodes persist across opens)
  if (!modal.dataset.mnsecBound) {
    modal.dataset.mnsecBound = '1';
    // clicking the backdrop (the overlay itself, not its content) closes
    modal.addEventListener('click', function (evt) {
      if (evt.target === modal) {
        mnsecCloseNewNodeModal();
      }
    });
    const closeBtn = document.querySelector('#new-node-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', mnsecCloseNewNodeModal);
    }
  }
  // reset fields for a fresh entry
  const nameInput = document.querySelector('#new-node-name');
  if (nameInput) {
    nameInput.value = '';
  }
  const attrs = document.querySelector('#new-node-attrs');
  if (attrs) {
    attrs.innerHTML = '';
  }
  modal.hidden = false;
}
function mnsecCloseNewNodeModal() {
  const modal = document.querySelector('#new-node-modal');
  if (modal) {
    modal.hidden = true;
  }
  mnsecNewNodePosition = null;
}
function mnsecAddAttrRow(name, value) {
  const container = document.querySelector('#new-node-attrs');
  if (!container) {
    return;
  }
  const row = document.createElement('div');
  row.className = 'new-node-attr-row';
  const keyInput = document.createElement('input');
  keyInput.type = 'text';
  keyInput.placeholder = 'name';
  keyInput.className = 'attr-key';
  keyInput.value = name || '';
  const valInput = document.createElement('input');
  valInput.type = 'text';
  valInput.placeholder = 'value';
  valInput.className = 'attr-value';
  valInput.value = value || '';
  const removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.className = 'attr-remove';
  removeBtn.textContent = '×';
  removeBtn.addEventListener('click', function () {
    row.remove();
  });
  row.appendChild(keyInput);
  row.appendChild(valInput);
  row.appendChild(removeBtn);
  container.appendChild(row);
}
// replace the attribute rows with the params inherited from an existing node;
// the user is free to edit, remove or add more rows afterwards
function mnsecPopulateAttrRows(params) {
  const container = document.querySelector('#new-node-attrs');
  if (!container) {
    return;
  }
  container.innerHTML = '';
  if (!params) {
    return;
  }
  Object.keys(params).forEach(function (name) {
    const value = params[name];
    mnsecAddAttrRow(name, typeof value === 'string' ? value : JSON.stringify(value));
  });
}
function mnsecSubmitNewNode(nodeTypeStr, nodeNameRaw, connectTo) {
  if (!nodeTypeStr) {
    alert('Please select a node type');
    return;
  }
  if (!nodeNameRaw) {
    alert('Please enter a node name');
    return;
  }
  const nodeName = nodeNameRaw.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
  if (!nodeName) {
    alert('Invalid node name: use only letters and numbers');
    return;
  }
  // value is "<visualType>/<kind>", e.g. "host/proc" or "switch/ovs"
  const nodeType = nodeTypeStr.split('/');
  const params = {};
  document.querySelectorAll('#new-node-attrs .new-node-attr-row').forEach(function (row) {
    const name = row.querySelector('.attr-key').value.trim();
    const rawValue = row.querySelector('.attr-value').value.trim();
    if (name && rawValue) {
      let value;
      try {
        value = JSON.parse(rawValue);
      } catch (error) {
        value = rawValue;
      }
      params[name] = value;
    }
  });
  // optionally connect the new node to one or more existing nodes
  const connectTargets = Array.isArray(connectTo) ? connectTo : (connectTo ? [connectTo] : []);
  if (connectTargets.length) {
    params["connectTo"] = connectTargets;
  }
  const loadingAddNode = document.querySelector('#loading-add-node');
  const btnNewNodeSubmit = document.querySelector('#new-node-submit');
  const spinner = document.createElement('span');
  spinner.className = 'loading-spinner';
  const result = requestAddNode(nodeName, nodeType[1], params);
  if (!result) {
    return;
  }
  if (loadingAddNode) {
    loadingAddNode.style.display = 'flex';
    btnNewNodeSubmit.prepend(spinner);
    btnNewNodeSubmit.style.pointerEvents = 'none';
  }
  result.then(function (displayImg) {
    if (loadingAddNode) {
      loadingAddNode.style.display = 'none';
    }
    if (!displayImg) {
      // request failed (requestAddNode already alerted): keep modal open to retry
      return;
    }
    const newNode = {
      data: {
        id: nodeName,
        label: nodeName,
        type: nodeType[0],
        url: `/assets/${displayImg}`,
      },
      classes: ['rectangle'],
    };
    // when opened from the canvas context menu, place the node where clicked
    if (mnsecNewNodePosition) {
      newNode.position = {
        x: mnsecNewNodePosition.x,
        y: mnsecNewNodePosition.y,
      };
    }
    cy.add(newNode);
    // draw an edge for each requested connection (links already created on
    // the backend during add_node, so fetch the existing interfaces)
    connectTargets.forEach(function (target) {
      mnsecCreateLink(nodeName, target, true);
    });
    mnsecCloseNewNodeModal();
    btnNewNodeSubmit.style.pointerEvents = 'auto';
    spinner.remove();
  });
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
      mnsecCreateLink(source, target);
  }
}
function mnsecCreateLink(source, target, getExisting = false) {
  const params = {node1: source, node2: target};
  if (getExisting) {
    params["getExisting"] = true;
  }
  const requestOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
  };
  return fetch('/add_link', requestOptions)
      .then(response => {
          if (!response.ok) {
              response.text().then(text => {
                  alert(`Error while adding link: ${text}`);
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
          // if it fails to update the topology, force the render to redraw
          cy.forceRender();
          return true;
      });
}
// nodes selected when the group modal was opened: grouped on submit
let mnsecNewGroupNodes = null;
function mnsecOpenNewGroupModal() {
  const modal = document.querySelector('#new-group-modal');
  if (!modal) {
    return;
  }
  // groups cannot contain other groups, so only regular nodes are considered
  const selectedNodes = cy.nodes(':selected').filter('[type != "group"]');
  if (selectedNodes.length === 0) {
    alert('Error: no nodes selected, please select the nodes to group first');
    return;
  }
  mnsecNewGroupNodes = selectedNodes;
  // attach dismiss handlers only once (nodes persist across opens)
  if (!modal.dataset.mnsecBound) {
    modal.dataset.mnsecBound = '1';
    // clicking the backdrop (the overlay itself, not its content) closes
    modal.addEventListener('click', function (evt) {
      if (evt.target === modal) {
        mnsecCloseNewGroupModal();
      }
    });
    const closeBtn = document.querySelector('#new-group-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', mnsecCloseNewGroupModal);
    }
    // dcc.Input does not support type=color, so the native picker is created here
    const colorWrap = document.querySelector('#new-group-color-wrap');
    if (colorWrap) {
      const colorInput = document.createElement('input');
      colorInput.type = 'color';
      colorInput.id = 'new-group-color';
      colorWrap.appendChild(colorInput);
    }
  }
  // reset fields for a fresh entry
  const nameInput = document.querySelector('#new-group-name');
  if (nameInput) {
    nameInput.value = `group-${cy.nodes("[type = 'group']").length + 1}`;
  }
  const colorInput = document.querySelector('#new-group-color');
  if (colorInput) {
    colorInput.value = '#f5f5f5';
  }
  modal.hidden = false;
}
function mnsecCloseNewGroupModal() {
  const modal = document.querySelector('#new-group-modal');
  if (modal) {
    modal.hidden = true;
  }
  mnsecNewGroupNodes = null;
}
function mnsecSubmitNewGroup(groupShape) {
  // the name and color inputs are read straight from the DOM: the default
  // name is set by mnsecOpenNewGroupModal() and the color picker is a native
  // input, so neither is visible through Dash State
  const nameInput = document.querySelector('#new-group-name');
  const groupName = (nameInput ? nameInput.value : '').replace(/[^a-zA-Z0-9-]/g, '');
  if (!groupName) {
    alert('Invalid group name: use only letters, numbers and dashes');
    return;
  }
  if (cy.getElementById(groupName).length > 0) {
    alert(`Error: a node or group named ${groupName} already exists`);
    return;
  }
  const colorInput = document.querySelector('#new-group-color');
  const groupColor = colorInput ? colorInput.value : '#f5f5f5';
  const shape = groupShape || 'rectangle';
  const selectedNodes = mnsecNewGroupNodes;
  const selectedNodeIds = selectedNodes.map((node) =>
      node.data("label")
  );
  const requestOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({nodes: selectedNodeIds, group: groupName, color: groupColor, shape: shape})
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
          cy.add({data: {id: groupName, label: groupName, type: "group", color: groupColor, shape: shape}, classes: ["groupnode"]});
          selectedNodes.move({parent: groupName});
          mnsecCloseNewGroupModal();
      });
}
// keep the group style panel (Settings tab) in sync with the selected group:
// called from the cytoscape select/unselect handler. The color picker is
// created lazily here since dcc.Input does not support type=color
function mnsecSyncGroupStylePanel() {
  const selectedNodes = cy.nodes(':selected');
  if (selectedNodes.length !== 1 || selectedNodes[0].data('type') !== 'group') {
    return;
  }
  const wrap = document.querySelector('#change-group-color-wrap');
  if (!wrap) {
    return;
  }
  let colorInput = document.querySelector('#change-group-color');
  if (!colorInput) {
    colorInput = document.createElement('input');
    colorInput.type = 'color';
    colorInput.id = 'change-group-color';
    colorInput.addEventListener('change', function (evt) {
      mnsecUpdateGroupStyle(evt.target.value, null);
    });
    wrap.appendChild(colorInput);
  }
  colorInput.value = selectedNodes[0].data('color') || '#f5f5f5';
}
// change color and/or shape of the currently selected group, persisting on
// the backend via /add_group (which updates the members' group params)
function mnsecUpdateGroupStyle(color, shape) {
  const selectedNodes = cy.nodes(':selected');
  if (selectedNodes.length !== 1 || selectedNodes[0].data('type') !== 'group') {
    return;
  }
  const group = selectedNodes[0];
  const changes = {};
  if (color && color !== group.data('color')) {
    changes.color = color;
  }
  if (shape && shape !== group.data('shape')) {
    changes.shape = shape;
  }
  if (Object.keys(changes).length === 0) {
    return;
  }
  const memberIds = group.children().map((node) =>
      node.data("label")
  );
  const requestOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign({nodes: memberIds, group: group.data('label')}, changes))
  };
  fetch('/add_group', requestOptions)
      .then(response => {
          if (!response.ok) {
              response.text().then(text => {
                  alert(`Error while updating group: ${text}`);
              });
              return false;
          }
          return response.json();
      })
      .then(result => {
          if (result) {
              group.data(changes);
          }
      });
}
// keyboard handling for the modals: Esc closes, Enter submits
// (Enter only from the text inputs, so it does not fire while picking from a dropdown)
document.addEventListener('keydown', function (evt) {
  [
    {modal: '#new-node-modal', close: mnsecCloseNewNodeModal, submit: '#new-node-submit', dropdown: '#new-node-type'},
    {modal: '#new-group-modal', close: mnsecCloseNewGroupModal, submit: '#new-group-submit', dropdown: '#new-group-shape'},
  ].forEach(function (cfg) {
    const modal = document.querySelector(cfg.modal);
    if (!modal || modal.hidden) {
      return;
    }
    if (evt.key === 'Escape') {
      evt.preventDefault();
      cfg.close();
    } else if (evt.key === 'Enter') {
      const active = document.activeElement;
      const fromTextInput = active
        && active.tagName === 'INPUT'
        && active.closest(cfg.modal)
        && !active.closest(cfg.dropdown);
      if (fromTextInput) {
        const submitBtn = document.querySelector(cfg.submit);
        if (submitBtn) {
          evt.preventDefault();
          submitBtn.click();
        }
      }
    }
  });
});
function mnsecStartCapture(link) {
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
          alert("Packet capture started successfully!");
      });
}
function mnsecStopCapture(link) {
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
          alert("Packet capture stopped!");
      });
}
function mnsecViewCapture(link) {
  const captureFile = link.data("capture");
  const mnsecData = JSON.parse(localStorage.getItem("mnsec_data"));
  if (!captureFile) {
    console.log('Cannot view capture on link - not running:', link.id(), link.data());
    alert(`Cannot view capture on link - not running`);
    return false;
  }
  if (!mnsecData.webSharkUrl) {
    alert(`Cannot view packet capture: webSharkUrl not defined (see --capture_webshark_url)`);
    return false;
  }
  window.open(`${mnsecData.webSharkUrl}#${captureFile}`, "_blank");
}
window.dashCytoscapeFunctions = Object.assign(
    {},
    window.dashCytoscapeFunctions,
    {
        mnsec_add_node: function (event) {
            // remember where the user right-clicked so the new node lands there,
            // then click the menubar button: that opens the modal and also lets
            // Dash refresh the "Connect To" options
            mnsecPendingNodePosition = event.position || event.cyPosition;
            const btn = document.querySelector('#btn-new-node');
            if (btn) {
              btn.click();
            }
        },
        mnsec_add_link: function (event) {
	    mnsecAddLink();
        },
        mnsec_open_xterm: function (event) {
            var node = event.target;
            var nodeid = node.data("label");
            window.open(`/xterm/${nodeid}`, "_blank");
        },
        mnsec_add_group: function (event) {
            mnsecOpenNewGroupModal();
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
