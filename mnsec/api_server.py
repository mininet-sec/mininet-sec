import json
import yaml
import flask
import threading
import textwrap
from flask_socketio import SocketIO, disconnect
#from werkzeug.serving import make_server
from dash import Dash, html, dcc, Input, Output, State, callback, clientside_callback, get_asset_url, no_update
import dash_cytoscape as cyto
from mininet.log import info, warning

import pty
import os
import signal
import subprocess
import select
import struct
import fcntl
import termios


def set_winsize(fd, row, col, xpix=0, ypix=0):
    winsize = struct.pack("HHHH", row, col, xpix, ypix)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)



class APIServer:
    def __init__(self, mnsec, listen="0.0.0.0", port=8050):
        """Starts Flask/Dash API server. Requires Mininet-Sec object."""
        self.mnsec = mnsec
        self.listen = listen
        self.port = port

        # Analytics measurements
        self.gtag = os.getenv("GTAG")
        external_scripts = []
        if self.gtag:
            external_scripts.append(
                f"https://www.googletagmanager.com/gtag/js?id={self.gtag}"
            )

        self.server = flask.Flask(__name__)
        self.app = Dash(
            __name__,
            server=self.server,
            update_title="Mininet-Sec Updating...",
            suppress_callback_exceptions=True,
            external_scripts = external_scripts or None
        )
        self.app.title = "Mininet-Sec"
        #self.server = make_server(listen, port, self.app.server, threaded=True, processes=0)
        self.socketio = SocketIO(self.server)
        self.server_task = None

        # xterm connections
        self.xterm_conns = {}

        self.topology_loaded = False

        self.default_stylesheet = []

        self.positions = {}

        # loading layout
        self.app.layout = html.Div([
            dcc.Location(id='url'),
            dcc.Interval(id='interval-loading', interval=2000),
            html.Img(src=get_asset_url('mininet-sec.png')),
            html.H3("Wait while loading the topology..."),
            dcc.Loading(id="loading-1", display='show'),
        ])

        @callback(
            Output("url", 'href'),
            Output("interval-loading", "disabled"),
            Input("interval-loading", "n_intervals"),
            prevent_initial_call=True,
        )
        def interval_update(n):
            if self.topology_loaded:
                return "/", True
            else:
                return no_update

        @callback(
            Output("cytoscape", "layout"),
            Input("dropdown-update-layout", "value"),
        )
        def update_layout(layout):
            new_layout = {"name": layout, "animate": True}
            if layout == "preset":
                new_layout["positions"] = self.positions
            return new_layout

        @callback(
            Output("tap-node-data-json-output", "children"),
            Input("cytoscape", "selectedNodeData"),
        )
        def displayTapNodeData(data):
            return json.dumps(data, indent=2)

        @callback(
            Output("tap-edge-data-json-output", "children"),
            Input("cytoscape", "selectedEdgeData"),
        )
        def displayTapEdgeData(data):
            return json.dumps(data, indent=2)

        @callback(
            Output("console-cmd-result", "children"),
            Input("cmd_str", "value"),
        )
        def update_output(cmd_str):
            if not cmd_str:
                return ""
            cmdOut = self.mnsec.run_cli(cmd_str)
            return cmdOut

        @callback(
            Output('cytoscape', 'elements'),
            Input('cytoscape', 'selectedNodeData'),
            Input('input-node-label', 'value'),
            State('cytoscape', 'elements'),
        )
        def updateNodeLabel(data, new_label, elements):
            if not data or data[-1]["label"] == new_label:
                return elements
            for ele in elements:
                if ele["data"]["id"] == data[-1]["id"]:
                    ele["data"]["label"] = str(new_label)
                    if ele["data"]["type"] == "group":
                        self.mnsec.updateGroupName(data[-1]["label"], new_label)
                    break
            return elements

        @callback(
            Output('change-node-id', 'children'),
            Input('cytoscape', 'selectedNodeData')
        )
        def displayNodeLabelSettings(data):
            if not data:
                return ""
            return data[-1].get("id", "")

        @callback(
            Output('input-node-label', 'value'),
            Input('cytoscape', 'selectedNodeData')
        )
        def displayNodeLabelSettings(data):
            if not data:
                return ""
            return data[-1].get("label", "")

        @callback(
            Output('change-node-data', 'hidden'),
            Input('cytoscape', 'selectedNodeData')
        )
        def displayChangeNodeData(data):
            if data and len(data) == 1 and data[0].get("type") == "group":
                return False
            return True

        @callback(
            Output('cytoscape', 'stylesheet'),
            Input('show-interface-name', 'value'),
            prevent_initial_call=True,
        )
        def show_interface_name(show):
            for item in self.default_stylesheet:
                if item["selector"] == "edge":
                    item["style"]["source-label"] = "" if show == "disabled" else "data(slabel)"
                    item["style"]["target-label"] = "" if show == "disabled" else "data(tlabel)"
            return self.default_stylesheet

        @callback(
            Output("download-topology", "data"),
            Input("btn-download-topology", "n_clicks"),
            State('cytoscape', 'elements'),
            prevent_initial_call=True,
        )
        def download_topology(n_clicks, elements):
            topo_dict = {
                "settings": self.mnsec.topo_dict.get("settings", {}),
                "hosts": {},
                "switches": {},
                "links": [],
            }
            for ele in elements:
                data = ele["data"]
                if "source" in data or data.get("type") == "group":
                    continue
                ele_type = "hosts" if data["type"] == "host" else "switches"
                node = self.mnsec.nameToNode.get(data["id"])
                if not node:
                    warning(f"Ignoring element id not found on mnsec {data=}\n")
                    continue
                topo_dict[ele_type][node.name] = node.params
                kind = self.mnsec.getObjKind(node)
                if topo_dict["settings"].get(f"{ele_type}_kind", "default") != kind:
                    topo_dict[ele_type][node.name]["kind"] = kind

                # add x, y positions if they actually exist (float comparison with almost-equality)
                if abs(ele["position"]["x"] - 0.01) > 0.1:
                    topo_dict[ele_type][node.name]["posX"] = float("%.2f" % ele["position"]["x"])
                if abs(ele["position"]["y"] - 0.01) > 0.1:
                    topo_dict[ele_type][node.name]["posY"] = float("%.2f" % ele["position"]["y"])

                # remove attributes that are empty, internal, etc
                topo_dict[ele_type][node.name].pop("homeDir", None)
                topo_dict[ele_type][node.name].pop("isSwitch", None)
                if "ip" in topo_dict[ele_type][node.name] and not topo_dict[ele_type][node.name]["ip"]:
                    topo_dict[ele_type][node.name].pop("ip")

            for link in self.mnsec.links:
                link_dict = {
                    "node1": link.intf1.node.name,
                    "node2": link.intf2.node.name,
                }
                kind = self.mnsec.getObjKind(link)
                if topo_dict["settings"].get("links_kind", "default") != kind:
                    link_dict["kind"] = kind
                if link.intf1.params:
                    link_dict["params1"] = link.intf1.params
                if link.intf2.params:
                    link_dict["params2"] = link.intf2.params
                topo_dict["links"].append(link_dict)

            return {"content": yaml.dump(topo_dict, sort_keys=False), "filename": "mytopology.yaml"}


        gtag_str = (
            "window.dataLayer = window.dataLayer || [];"
            "function gtag () {"
            "  dataLayer.push(arguments);"
            "};"
            "gtag('js',new Date());"
            f"gtag('config', '{self.gtag}');"
        ) if self.gtag else ""
        clientside_callback(
            """
            function(input1) {
              let timer;
              let selectedNodes;
              let hasTapHold = false;
              const duration = 500;
              let tapCount = 0;
              let dblTapTimer;
              const dblTapDelay = 300;
              document.querySelectorAll('.cy-context-menus-cxt-menuitem').forEach(el=>el.addEventListener("touchend", function(){el.click()}));
              cy.on('touchstart', 'node', function(evt) {
                timer = setTimeout(function() {
                  hasTapHold = true;
                  evt.target.select();
	              selectedNodes = cy.nodes(":selected");
                }, duration);
              });
              cy.on('touchend', 'node', function(evt) {
                if (hasTapHold) {
                  // make nodes immutable so that they cannot be unselect
                  selectedNodes.forEach((node) => {
                    node.unselectify();
                  });
                  // resume nodes mutability
                  setTimeout(function() {
                    selectedNodes.forEach((node) => {
                      node.selectify();
                    });
                    selectedNodes = [];
                  }, 300);
                } else {
                  tapCount++;
                  if (tapCount === 1) {
                    dblTapTimer = setTimeout(() => {
                      tapCount = 0;
                    }, dblTapDelay);
                  } else if (tapCount > 1) {
                    clearTimeout(dblTapTimer);
                    // Double tap action
                    window.open('/xterm/' + evt.target.id(), '_blank');
                    tapCount = 0;
                  }
                }
                clearTimeout(timer);
                hasTapHold = false;
              });
              cy.on('touchmove', 'node', function(evt) {
                clearTimeout(timer);
                hasTapHold = false;
                selectedNodes = [];
              });

              cy.on('select unselect', 'node', function(evt) {
                const link = document.querySelector('#link-open-term');
                link.style.display = "none";
                link.href = '#';
	            const selectedNodes = cy.nodes(":selected");
                if (selectedNodes.length === 1 && selectedNodes[0].data("type") !== "group") {
                  link.style.display = "block";
                  link.href = '/xterm/' + selectedNodes[0].data("label");
                }
              });
              cy.on('dblclick', function(evt) {
                window.open('/xterm/' + evt.target.id(), '_blank');
              });
              %s
              return dash_clientside.no_update;
            }
            """ % (gtag_str),
            Output('cytoscape', 'id'),
            Input('cytoscape', 'id')
        )

        clientside_callback(
            """
            function(typeStr) {
              const inputEle = document.querySelector('#btn-add-node input');
              inputEle.disabled = true;
              const nodeType = typeStr.split("/");
              var nodeId = cy.nodes().length + 1;
              let nodeName = prompt("Node name (only letters and numbers)", `n${nodeId}`);
              if (!nodeName) {
                return "";
              }
              nodeName = nodeName.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
              let nodeParams = prompt("Node parameters (comma-separated name=value pairs. Example: image='hackinsdn/debian:latest', group='group1'):");
              const params = {};
              if (nodeParams) {
                nodeParams.split(',').forEach(function (pair) {
                  const [name, value] = pair.split('=');
                  if (name && value) {
                    let newValue;
                    try {
                      newValue = JSON.parse(value.trim());
                    } catch (error) {
                      newValue = value.trim();
                    }
                    params[name.trim()] = newValue;
                  }
                });
              }
              var result = requestAddNode(nodeName, nodeType[1], params);
              if (result) {
                const loadingAddNode = document.querySelector('#loading-add-node');
                loadingAddNode.style.display = "flex";
                result.then(function(displayImg){
                  inputEle.disabled = false;
                  if (!displayImg) {
                    return "";
                  }
                  cy.add({
                    data: {
                      id: nodeName,
                      label: nodeName,
                      type: nodeType[0],
                      url: `/assets/${displayImg}`,
                    },
                    classes: ['rectangle'],
                  });
                  loadingAddNode.style.display = "none";
                });
                return "";
              }
              return "";
            }
            """,
            Output('btn-add-node', 'value'),
            Input("btn-add-node", "value"),
            prevent_initial_call=True,
        )

        clientside_callback(
            """
            function(input1) {
              return 'show';
            }
            """,
            Output('loading-add-node', 'display'),
            Input("btn-add-node", "value"),
            prevent_initial_call=True,
        )

        clientside_callback(
            """
            function(input1) {
              mnsecAddLink();
              return dash_clientside.no_update;
            }
            """,
            Output('btn-add-link', 'id'),
            Input("btn-add-link", "n_clicks"),
            prevent_initial_call=True,
        )

        clientside_callback(
            """
            function(input1) {
              mnsecAddGroup();
              return dash_clientside.no_update;
            }
            """,
            Output('btn-add-group', 'id'),
            Input("btn-add-group", "n_clicks"),
            prevent_initial_call=True,
        )

        clientside_callback(
            """
            function(data) {
              localStorage.setItem("mnsec_data", JSON.stringify(data));
              return dash_clientside.no_update;
            }
            """,
            Output('store-mnsec-data', 'id'),
            Input("store-mnsec-data", "data"),
        )

        self.server.add_url_rule("/topology", None, self.get_topology, methods=["GET"])
        self.server.add_url_rule("/ifindexes", None, self.get_ifindexes, methods=["GET"])
        self.server.add_url_rule("/add_node", None, self.add_node, methods=["POST"])
        self.server.add_url_rule("/add_link", None, self.add_link, methods=["POST"])
        self.server.add_url_rule("/add_group", None, self.add_group, methods=["POST"])
        self.server.add_url_rule("/xterm/<host>", None, self.xterm, methods=["GET"])
        self.server.add_url_rule("/start_capture", None, self.start_capture, methods=["POST"])
        self.server.add_url_rule("/stop_capture", None, self.stop_capture, methods=["POST"])


    def setup(self):
        self.app.layout = self.serve_layout
        self.topology_loaded = True

    def serve_layout(self):
        layout = "cose"
        elements = []
        groups = {}
        for host in self.mnsec.hosts:
            img_url = host.params.get("img_url")
            if not img_url:
                img_url = get_asset_url(getattr(host, "display_image", "computer.png"))
            position = {}
            if host.params.get("posX"):
                layout = "preset"
                position["x"] = host.params["posX"]
            if host.params.get("posY"):
                layout = "preset"
                position["y"] = host.params["posY"]
            elements.append({"data": {"id": host.name, "label": host.name, "type": "host", "url": img_url}, "classes": "rectangle", "position": position})
            if position:
                self.positions[host.name] = position
            # setup groups
            group = host.params.get("group")
            if not group:
                continue
            group_id = groups.get(group)
            if not group_id:
                group_id = len(groups.keys()) + 1
                groups[group] = group_id
            elements[-1]["data"]["parent"] = f"group-{group_id}"
        for switch in self.mnsec.switches:
            img_url = switch.params.get("img_url")
            if not img_url:
                img_url = get_asset_url(getattr(switch, "display_image", "switch.png"))
            dpid = ":".join(textwrap.wrap(getattr(switch, "dpid", "0000000000000000"), 2))
            position = {}
            if switch.params.get("posX"):
                layout = "preset"
                position["x"] = switch.params["posX"]
            if switch.params.get("posY"):
                layout = "preset"
                position["y"] = switch.params["posY"]
            elements.append({"data": {"id": switch.name, "label": switch.name, "type": "switch", "dpid": dpid, "url": img_url}, "classes": "rectangle", "position": position})
            if position:
                self.positions[switch.name] = position
            # setup groups
            group = switch.params.get("group")
            if not group:
                continue
            group_id = groups.get(group)
            if not group_id:
                group_id = len(groups.keys()) + 1
                groups[group] = group_id
            elements[-1]["data"]["parent"] = f"group-{group_id}"
        for link in self.mnsec.links:
            elements.append({"data": {"source": link.intf1.node.name, "target": link.intf2.node.name, "slabel": link.intf1.name.split("-")[-1], "tlabel": link.intf2.name.split("-")[-1], "source_interface": link.intf1.name, "target_interface": link.intf2.name}})
        for group, group_id in groups.items():
            elements.insert(0, {"data": {"group": "nodes", "id": f"group-{group_id}", "label": group, "type": "group"}, "classes": "groupnode"})

        context_menu = [
            {
                "id": "add-host",
                "label": "Add Host",
                "tooltipText": "Add Host",
                "availableOn": ["canvas"],
                "onClickCustom": "mnsec_add_host",
            },
            {
                "id": "add-switch",
                "label": "Add Switch",
                "tooltipText": "Add Switch",
                "availableOn": ["canvas"],
                "onClickCustom": "mnsec_add_switch",
            },
            {
                "id": "add-link",
                "label": "Add Link",
                "tooltipText": "Add Link",
                "availableOn": ["node"],
                "onClickCustom": "mnsec_add_link",
            },
            {
                "id": "open-xterm",
                "label": "Terminal",
                "tooltipText": "Open xterm",
                "availableOn": ["node"],
                "onClickCustom": "mnsec_open_xterm",
            },
            {
                "id": "add-group",
                "label": "Add group",
                "tooltipText": "Add group",
                "availableOn": ["node"],
                "onClickCustom": "mnsec_add_group",
            },
            {
                "id": "remove-node",
                "label": "Remove node",
                "tooltipText": "Remove node from canvas",
                "availableOn": ["node"],
                "onClick": "remove",
            },
            {
                "id": "start-link-capture",
                "label": "Start capture",
                "tooltipText": "Start Packet Capture",
                "availableOn": ["edge"],
                "onClickCustom": "mnsec_start_capture",
            },
            {
                "id": "view-link-capture",
                "label": "View capture",
                "tooltipText": "View Packet Capture",
                "availableOn": ["edge"],
                "onClickCustom": "mnsec_view_capture",
            },
            {
                "id": "stop-link-capture",
                "label": "Stop capture",
                "tooltipText": "Stop Packet Capture",
                "availableOn": ["edge"],
                "onClickCustom": "mnsec_stop_capture",
            },
        ]
        styles = {
            "json-output": {
                "overflowY": "scroll",
                "border": "thin lightgray solid",
                "height": "100%",
            },
            "tab": {"height": "calc(98vh - 115px)"},
            "full-height": {
                "height": "calc(100% - 115px)",
            },
            "half-height": {
                "height": "calc(50vh - 10px)",
            },
        }
        self.default_stylesheet = [
            # Group selectors
            {
                'selector': 'node',
                'style': {
                    'content': 'data(label)',
                    'text-valign': 'bottom',
                }
            },
            {
                'selector': 'edge',
                'style': {
                    #'label': 'data(label)',
                    #'source-label': 'data(slabel)',
                    'source-label': '',
                    #'target-label': 'data(tlabel)',
                    'target-label': '',
                    'text-wrap': 'wrap',
                    'color': '#000',
                    'font-size': '10px',
                    'width': '3px',
                    'curve-style': 'bezier',
                    'source-text-offset': '15px',
                    'target-text-offset': '15px',
                }
            },
            # Class selectors
            {
                'selector': '.red',
                'style': {
                    'background-color': 'red',
                    'line-color': 'red'
                }
            },
            {
                'selector': '.rectangle',
                'style': {
                    'shape': 'rectangle',
                    'background-color': 'white',
                    'background-width': '90%',
                    'background-height': '90%',
                    'background-image': 'data(url)',
                }
            },
            {
                'selector': '.circle',
                'style': {
                    'background-color': 'white',
                    'background-width': '90%',
                    'background-height': '90%',
                    'background-image': 'data(url)',
                }
            },
            {
                'selector': '.groupnode',
                'style': {
                    'text-halign': 'center',
                    'text-valign': 'top',
                    'background-color': '#F5F5F5',
                }
            },
            {
                'selector': ':selected',
                'style': {
                  'background-color': '#F5F5F5',
                  'line-color': '#505050',
                  'target-arrow-color': 'black',
                  'source-arrow-color': 'black',
                  'border-width': 3,
                  'border-color': '#505050',
                  #'border-color': 'SteelBlue',
                }
            },
        ]

        return_layout = html.Div([
            dcc.Store(id='store-mnsec-data', data={"webSharkUrl": self.mnsec.captureWebSharkUrl}),
            dcc.Location(id='url'),
            dcc.Interval(id='interval-loading', interval=2000, disabled=True),
            html.Div(
                className="eight columns",
                id="topology",
                children = [
                    html.Div(
                        className="navibar",
                        id="topNaviBar",
                        children = [
                            html.Img(src=get_asset_url('mininet-sec.png')),
                            html.Div(
                                className="menubar",
                                id="menuNaviBar",
                                children = [
                                    dcc.Loading(id="loading-add-node", display='hide'),
                                    html.A(
                                        html.Button("Term", id="btn-open-term"),
                                        href="#", target="_blank", id="link-open-term", style={"display": "none"},
                                    ),
                                    dcc.Dropdown(
                                        id="btn-add-node",
                                        placeholder="+ Node",
                                        className="menudropdown",
                                        clearable=False,
                                        options=[
                                            {"label": "Host", "value": "host/proc"},
                                            {"label": "OVS Switch", "value": "switch/ovs"},
                                            {"label": "Bridge Switch", "value": "switch/lxbr"},
                                            {"label": "Pod K8s", "value": "host/k8spod"},
                                        ],
                                    ),
                                    html.Button("+ Link", id="btn-add-link"),
                                    html.Button("+ Group", id="btn-add-group"),
                                ],
                            ),
                        ],
                    ),
                    cyto.Cytoscape(
                        id="cytoscape",
                        layout={"name": layout, "fit": True},
                        style={"width": "100%", "height": "95vh"},
                        elements=elements,
                        contextMenu=context_menu,
                        autoRefreshLayout=False,
                        stylesheet = self.default_stylesheet,
                    ),  # end Cytoscape
                ]
            ), # end div eight columns
            html.Div(
                className="four columns",
                children=[
                    dcc.Tabs(
                        id="tabs",
                        children=[
                            dcc.Tab(
                                label="Settings & Node/Link Data",
                                children=[
                                    html.Div(
                                        style=styles["tab"],
                                        children=[
                                            html.Div(
                                                children=[
                                                    html.Div(
                                                        style=styles["half-height"],
                                                        children=[
                                                            html.I("Change topology layout:"),
                                                            html.Br(),
                                                            dcc.Dropdown(
                                                                id="dropdown-update-layout",
                                                                value=layout,
                                                                clearable=False,
                                                                options=[
                                                                    {"label": name.capitalize(), "value": name}
                                                                    for name in set(["grid", "random", "circle", "cose", "concentric", layout])
                                                                ],
                                                            ),
                                                            html.Br(),
                                                            html.Div(
                                                                className="row",
                                                                children=[
                                                                    html.Div(
                                                                        className="one-half column",
                                                                        children=[
                                                                            html.I("Show interface names on links:"),
                                                                            dcc.RadioItems(['enabled', 'disabled'], 'disabled', id="show-interface-name"),
                                                                        ],
                                                                    ),
                                                                    html.Div(
                                                                        className="one-half column",
                                                                        children=[
                                                                            html.Button("Download topology", id="btn-download-topology"),
                                                                            dcc.Download(id="download-topology"),
                                                                        ],
                                                                    ),
                                                                ],
                                                            ),
                                                            html.Br(),
                                                            html.I("Change node data:"),
                                                            html.Br(),
                                                            html.Pre(id='change-node-id'),
                                                            html.Div(id="change-node-data", hidden=True, children=[
                                                                'Node Label:',
                                                                dcc.Input(id='input-node-label', type='text', debounce=True, value="")
                                                            ])
                                                        ],
                                                    ),
                                                    html.Div(
                                                        style=styles["half-height"],
                                                        children=[
                                                            html.Div(
                                                                className="six columns",
                                                                style=styles["full-height"],
                                                                children=[
                                                                        html.P("Node Data JSON:"),
                                                                        html.Pre(
                                                                            id="tap-node-data-json-output",
                                                                            style=styles["json-output"],
                                                                        ),
                                                                ],
                                                            ),
                                                            html.Div(
                                                                className="six columns",
                                                                style=styles["full-height"],
                                                                children=[
                                                                        html.P("Edge Data JSON:"),
                                                                        html.Pre(
                                                                            id="tap-edge-data-json-output",
                                                                            style=styles["json-output"],
                                                                        ),
                                                                ],
                                                            ),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    )
                                ],
                            ),
                            dcc.Tab(
                                label="Mininet-Sec Console",
                                children=[
                                    html.Div(
                                        style=styles["tab"],
                                        children=[
                                            html.I("Enter the node and command below:"),
                                            html.Br(),
                                            dcc.Input(value="", id="cmd_str", type="text", placeholder="Command", debounce=True, style={'width':'100%'}),
                                            html.Pre(
                                                id="console-cmd-result",
                                                style=styles["json-output"],
                                            ),
                                        ],
                                    )
                                ],
                            ),
                        ],
                    ),  # end dcc.Tabs
                ],
            ),  # end div four columns
        ])

        @self.socketio.on("pty-input", namespace="/pty")
        def pty_input(data):
            """write to the child pty. The pty sees this as if you are typing in a real
            terminal.
            """
            host = data.get("host")
            session = self.xterm_conns.get(flask.request.sid)
            if not session:
                warning(f"Host not connected host={host} session_id={flask.request.sid}\n")
                return False
            os.write(session[0], data["input"].encode())

        @self.socketio.on("connect", namespace="/pty")
        def pty_connect(auth):
            """new client connected."""
            host = flask.request.args.get("host") 
            if not host or host not in self.mnsec:
                warning(
                    "socketio connnect request for unknown host=%s args=%s\n"
                    % (host, flask.request.event["args"])
                )
                return False
            session_id = flask.request.sid
            if session_id in self.xterm_conns:
                warning(f"Host already connected host={host} session_id={session_id}\n")
                return False

            # create child process attached to a pty we can read from and write to
            (child_pid, fd) = pty.fork()
            if child_pid == 0:
                # this is the child process fork.
                # anything printed here will show up in the pty, including the output
                # of this subprocess
                host_pid = self.mnsec[host].pid
                homeDir = self.mnsec.setupHostHomeDir(host)
                myenv = dict(os.environ)
                myenv.update({"PS1": f"\\u@{host}:\\W\\$ ", "HOME": homeDir, "TERM": "xterm"})
                # workaround to avoid bash overridding PS1
                myenv["SUDO_USER"] = "root"
                myenv["SUDO_PS1"] = "# "
                mncmd = ['mnexec', '-a', str(host_pid)]
                with self.mnsec[host].popen(
                    "bash", env=myenv, cwd=homeDir, mncmd=mncmd, stdout=None, stderr=None,
                ) as process:
                    try:
                        stdout, stderr = process.communicate()
                    except:
                        process.kill()
            else:
                # this is the parent process fork.
                # store child fd and pid
                self.xterm_conns[session_id] = (fd, child_pid, host)
                set_winsize(fd, 50, 50)
                self.socketio.start_background_task(read_and_forward_pty_output, session_id)

        @self.socketio.on("resize", namespace="/pty")
        def resize(data):
            """resize window lenght"""
            session_id = flask.request.sid
            if session_id not in self.xterm_conns:
                warning(f"Host not connected session_id={session_id}\n")
                return False
            (fd, _, _) = self.xterm_conns[session_id]
            if fd:
                set_winsize(fd, data["dims"]["rows"], data["dims"]["cols"])

        @self.socketio.on("disconnect", namespace="/pty")
        def pty_disconnect():
            """client disconnected."""
            host = flask.request.args.get("host") 
            session_id = flask.request.sid
            if session_id not in self.xterm_conns:
                #warning(f"Host not connected host={host}\n")
                return False
            (_, pid, _) = self.xterm_conns[session_id]
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception as exc:
                warning(f"Error terminating xterm child process for {host}: {exc}\n")
                pass
            self.xterm_conns.pop(session_id, None)

        def read_and_forward_pty_output(session_id):
            fd, pid, host = self.xterm_conns[session_id]
            max_read_bytes = 1024 * 20
            while True:
                self.socketio.sleep(0.01)
                if not fd:
                    continue
                timeout_sec = 0
                (data_ready, _, _) = select.select([fd], [], [], timeout_sec)
                if not data_ready:
                    continue
                try:
                    output = os.read(fd, max_read_bytes).decode(
                        errors="ignore"
                    )
                except Exception as exc:
                    #info(f"error reading fd={fd} exc={exc}\n")
                    break
                self.socketio.emit(f"pty-output-{host}", {"output": output}, namespace="/pty", to=session_id)
            self.socketio.emit("server-disconnected", namespace="/pty", to=session_id)
            try:
                os.close(fd)
                os.kill(pid, signal.SIGTERM)
                self.xterm_conns.pop(session_id, None)
            except:
                pass

        return return_layout

    def get_topology(self):
        topo = {'nodes':[], 'links':[]}
        for host in self.mnsec.hosts:
            topo["nodes"].append({"name": host.name, "type": "host"})
        for switch in self.mnsec.switches:
            topo["nodes"].append({"name": switch.name, "type": "switch"})
        for link in self.mnsec.links:
            topo["links"].append({"source": link.intf1.node.name, "target": link.intf2.node.name})
        return topo, 200

    def get_ifindexes(self):
        ifindexes = {}
        sw2dpid = {}
        for switch in self.mnsec.switches:
            sw2dpid[switch.name] = switch.dpid
        for link in self.mnsec.links:
            for intf in [link.intf1, link.intf2]:
                if intf.node.name not in sw2dpid:
                    continue
                result = intf.cmd(f"ip link show dev {intf.name}")
                result = result.split(":", 1)[0]
                ifindex = 0
                if result.isdigit():
                    ifindex = int(result)
                    ifindexes[ifindex] = {
                        "dpid": sw2dpid[intf.node.name],
                        "port_no": intf.node.ports[intf]
                    }
        return ifindexes, 200

    def add_node(self):
        data = flask.request.get_json(force=True)
        for req_field in ["name", "type"]:
            if not data.get(req_field):
                return f"Missing field {req_field} on request", 400
        if data["name"] in self.mnsec:
            return f"Node already exists: {data['name']}", 400
        params = data.get("params")
        if not isinstance(params, dict):
            params = {}
        try:
            node = self.mnsec.addNodeKind(data["name"], data["type"], **params)
            assert node
        except Exception as exc:
            return f"failed to add node: {exc}", 424
        display_image = getattr(node, "display_image", "computer.png")
        return display_image, 200

    def add_link(self):
        data = flask.request.get_json(force=True)
        for node in ["node1", "node2"]:
            if not data.get(node):
                return f"Missing field {node} on request", 400
            if data[node] not in self.mnsec:
                return f"Node does not exist: {data[node]}", 400

        try:
            link = self.mnsec.addLink(data["node1"], data["node2"])
            assert link
        except Exception as exc:
            return {"result": f"failed to create link: {exc}"}, 424 

        # switches will require the port to be attached to data-plane
        if hasattr(link.intf1.node, "attach"):
            link.intf1.node.attach(link.intf1.name)
        if hasattr(link.intf2.node, "attach"):
            link.intf2.node.attach(link.intf2.name)

        return {"intf1": link.intf1.name, "intf2": link.intf2.name}, 200

    def add_group(self):
        data = flask.request.get_json(force=True)
        nodes = data.get("nodes")
        group = data.get("group")
        if not nodes or not isinstance(nodes, list):
            return "Invalid/missing nodes to add_group. Please select the nodes first!", 400
        if not group:
            return "Invalid/missing group name to add_group", 400
        for node in nodes:
            node_obj = self.mnsec.get(node)
            if not node_obj:
                return f"Invalid {node} to add_group", 400
            node_obj.params["group"] = group
        return {"result": "all nodes added to group"}, 200

    def xterm(self, host):
        """Open xterm for a node"""
        if not host or host not in self.mnsec:
            return flask.render_template("xterm_error.html", error=f"Invalid host={host}")
        return flask.render_template("xterm.html", host=host, gtag=self.gtag)

    def start_capture(self):
        data = flask.request.get_json(force=True)
        status, msg = self.mnsec.startPacketCapture(
            nodeName1 = data.get("source"),
            nodeName2 = data.get("target"),
            intfName1 = data.get("source_interface"),
            intfName2 = data.get("target_interface"),
        )
        if not status:
            return f"Failed to start packet capture: {msg}", 400
        return {"capture": msg}, 200

    def stop_capture(self):
        data = flask.request.get_json(force=True)
        status, msg = self.mnsec.stopPacketCapture(
            intfName1 = data.get("source_interface"),
            intfName2 = data.get("target_interface"),
        )
        if not status:
            return f"Failed to stop packet capture: {msg}", 400
        return {"result": msg}, 200

    def run_server(self):
        info(f"APIServer listening on port {self.listen}:{self.port}\n")
        try:
            #self.server.serve_forever()
            self.app.run(host=self.listen, port=self.port, debug=True, use_reloader=False)
        except SystemExit:
            pass
        except Exception as error:
            info(f"Error while running APIServer: {error}")

    def start(self):
        info("*** Starting API/Dash server\n")
        self.server_task = threading.Thread(target=self.run_server, args=())
        self.server_task.daemon = True
        self.server_task.start()

    def stop(self):
        pass
