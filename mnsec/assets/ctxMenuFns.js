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
  const result = requestAddNode(nodeName, nodeType[1], params);
  if (!result) {
    return;
  }
  if (loadingAddNode) {
    loadingAddNode.style.display = 'flex';
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
          return true;
      });
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
// keyboard handling for the new-node modal: Esc closes, Enter submits
// (Enter only from the text inputs, so it does not fire while picking a type)
document.addEventListener('keydown', function (evt) {
  const modal = document.querySelector('#new-node-modal');
  if (!modal || modal.hidden) {
    return;
  }
  if (evt.key === 'Escape') {
    evt.preventDefault();
    mnsecCloseNewNodeModal();
  } else if (evt.key === 'Enter') {
    const active = document.activeElement;
    const fromTextInput = active
      && active.tagName === 'INPUT'
      && active.closest('#new-node-modal')
      && !active.closest('#new-node-type');
    if (fromTextInput) {
      const submitBtn = document.querySelector('#new-node-submit');
      if (submitBtn) {
        evt.preventDefault();
        submitBtn.click();
      }
    }
  }
});
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
            mnsecAddGroup();
        },
    }
);
