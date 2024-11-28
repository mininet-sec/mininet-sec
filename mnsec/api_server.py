import json
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

        self.server = flask.Flask(__name__)
        self.app = Dash(__name__, server=self.server)
        self.app.title = "Mininet-Sec"
        #self.server = make_server(listen, port, self.app.server, threaded=True, processes=0)
        self.socketio = SocketIO(self.server)
        self.server_task = None

        # xterm connections
        self.xterm_conns = {}

        self.topology_loaded = False

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

        self.server.add_url_rule("/topology", None, self.get_topology, methods=["GET"])
        self.server.add_url_rule("/add_node", None, self.add_node, methods=["POST"])
        self.server.add_url_rule("/add_link", None, self.add_link, methods=["POST"])
        self.server.add_url_rule("/xterm/<host>", None, self.xterm, methods=["GET"])

    def setup(self):
        elements = []
        for host in self.mnsec.hosts:
            elements.append({"data": {"id": host.name, "label": host.name, "type": "host"}, "classes": "rectangle"})
        for switch in self.mnsec.switches:
            dpid = ":".join(textwrap.wrap(getattr(switch, "dpid", "0000000000000000"), 2))
            elements.append({"data": {"id": switch.name, "label": switch.name, "type": "switch", "dpid": dpid}})
        for link in self.mnsec.links:
            elements.append({"data": {"source": link.intf1.node.name, "target": link.intf2.node.name, "slabel": link.intf1.name, "tlabel": link.intf2.name}})

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
        ]
        styles = {
            "json-output": {
                "overflowY": "scroll",
                "height": "calc(50% - 25px)",
                "border": "thin lightgrey solid",
            },
            "tab": {"height": "calc(98vh - 115px)"},
        }
        default_stylesheet = [
            # Group selectors
            {
                'selector': 'node',
                'style': {
                    'content': 'data(label)',
                    'text-valign': 'center',
                }
            },
            {
                'selector': 'edge',
                'style': {
                    #'label': 'data(label)',
                    'source-label': 'data(slabel)',
                    'target-label': 'data(tlabel)',
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
                    'shape': 'rectangle'
                }
            },
            {
                'selector': '.groupnode',
                'style': {
                    'text-halign': 'center',
                    'text-valign': 'top',
                }
            },
        ]

        self.app.layout = html.Div([
            dcc.Location(id='url'),
            dcc.Interval(id='interval-loading', interval=2000, disabled=True),
            html.Div(
                className="eight columns",
                id="topology",
                children = [
                    html.Img(src=get_asset_url('mininet-sec.png')),
                    cyto.Cytoscape(
                        id="cytoscape",
                        layout={"name": "cose"},
                        style={"width": "100%", "height": "95vh"},
                        elements=elements,
                        contextMenu=context_menu,
                        autoRefreshLayout=False,
                        stylesheet = default_stylesheet,
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
                                label="Node/Link Data",
                                children=[
                                    html.Div(
                                        style=styles["tab"],
                                        children=[
                                            html.P("Node Data JSON:"),
                                            html.Pre(
                                                id="tap-node-data-json-output",
                                                style=styles["json-output"],
                                            ),
                                            html.P("Edge Data JSON:"),
                                            html.Pre(
                                                id="tap-edge-data-json-output",
                                                style=styles["json-output"],
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
                            dcc.Tab(
                                label="Settings",
                                children=[
                                    html.Div(
                                        style=styles["tab"],
                                        children=[
                                            html.I("Change topology layout:"),
                                            html.Br(),
                                            dcc.Dropdown(
                                                id="dropdown-update-layout",
                                                value="cose",
                                                clearable=False,
                                                options=[
                                                    {"label": name.capitalize(), "value": name}
                                                    for name in ["grid", "random", "circle", "cose", "concentric"]
                                                ],
                                            ),
                                            html.Br(),
                                            html.I("Show interface names on links:"),
                                            dcc.RadioItems(['enabled', 'disabled'], 'enabled', id="show-interface-name"),
                                            html.Br(),
                                            html.I("Change node data:"),
                                            html.Br(),
                                            html.Div(id="change-node-data", hidden=True, children=[
                                                html.Pre(id='change-node-id'),
                                                'Node Label:',
                                                dcc.Input(id='input-node-label', type='text', debounce=True, value="")
                                            ])
                                        ],
                                    )
                                ],
                            ),
                        ],
                    ),  # end dcc.Tabs
                ],
            ),  # end div four columns
        ])

        @callback(
            Output("cytoscape", "layout"),
            Input("dropdown-update-layout", "value"),
        )
        def update_layout(layout):
            return {"name": layout, "animate": True}

        @callback(
            Output("tap-node-data-json-output", "children"),
            Input("cytoscape", "selectedNodeData")
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
            if data:
                for ele in elements:
                    if ele["data"]["id"] == data[-1]["id"]:
                        ele["data"]["label"] = str(new_label)
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
            return False if data and len(data) == 1 else True

        @callback(
            Output('cytoscape', 'stylesheet'),
            Input('show-interface-name', 'value'),
        )
        def show_interface_name(show):
            for item in default_stylesheet:
                if item["selector"] == "edge":
                    item["style"]["source-label"] = "" if show == "disabled" else "data(slabel)"
                    item["style"]["target-label"] = "" if show == "disabled" else "data(tlabel)"
            return default_stylesheet

        @self.socketio.on("pty-input", namespace="/pty")
        def pty_input(data):
            """write to the child pty. The pty sees this as if you are typing in a real
            terminal.
            """
            host = data.get("host")
            if not host or host not in self.xterm_conns:
                warning(f"Host not connected host={host}\n")
                return False
            (fd, _) = self.xterm_conns[host]
            if fd:
                os.write(fd, data["input"].encode())

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
            if host in self.xterm_conns:
                warning(f"Host already connected host={host}\n")
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
                # after finish make sure we cleanup
                self.xterm_conns.pop(host, None)
                # TODO: trigger a disconnect socketio event! (even if it is possible to close the tab, we shouldnt do that to avoid loosing data on the section)
            else:
                # this is the parent process fork.
                # store child fd and pid
                self.xterm_conns[host] = (fd, child_pid)
                set_winsize(fd, 50, 50)
                self.socketio.start_background_task(read_and_forward_pty_output, host, fd)

        @self.socketio.on("resize", namespace="/pty")
        def resize(data):
            """resize window lenght"""
            host = data.get("host")
            if not host or host not in self.xterm_conns:
                warning(f"Host not connected host={host}\n")
                return False
            (fd, _) = self.xterm_conns[host]
            if fd:
                set_winsize(fd, data["dims"]["rows"], data["dims"]["cols"])

        @self.socketio.on("disconnect", namespace="/pty")
        def pty_disconnect():
            """client disconnected."""
            host = flask.request.args.get("host") 
            if not host or host not in self.xterm_conns:
                #warning(f"Host not connected host={host}\n")
                return False
            (_, pid) = self.xterm_conns[host]
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception as exc:
                warning(f"Error terminating xterm child process for {host}: {exc}\n")
                pass
            self.xterm_conns.pop(host, None)

        def read_and_forward_pty_output(host, fd):
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
                    self.xterm_conns.pop(host, None)
                    break
                self.socketio.emit(f"pty-output-{host}", {"output": output}, namespace="/pty")

        self.topology_loaded = True


    def get_topology(self):
        topo = {'nodes':[], 'links':[]}
        for host in self.mnsec.hosts:
            topo["nodes"].append({"name": host.name, "type": "host"})
        for switch in self.mnsec.switches:
            topo["nodes"].append({"name": switch.name, "type": "switch"})
        for link in self.mnsec.links:
            topo["links"].append({"source": link.intf1.node.name, "target": link.intf2.node.name})
        return topo, 200

    def add_node(self):
        data = flask.request.get_json(force=True)
        for req_field in ["name", "type"]:
            if not data.get(req_field):
                return f"Missing field {req_field} on request", 400
        if data["name"] in self.mnsec:
            return f"Node already exists: {data['name']}", 400
        if data["type"] == "host":
            try:
                host = self.mnsec.addHost(data["name"])
                assert host
                self.mnsec.startHost(host)
            except Exception as exc:
                return {"result": f"failed to add host: {exc}"}, 424
        elif data["type"] == "switch":
            try:
                switch = self.mnsec.addSwitch(data["name"])
                assert switch
            except Exception as exc:
                return {"result": f"failed to add switch: {exc}"}, 424
        return {"result": "ok"}, 200

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

    def xterm(self, host):
        """Open xterm for a node"""
        if not host or host not in self.mnsec:
            return flask.render_template("xterm_error.html", error=f"Invalid host={host}")
        return flask.render_template("xterm.html", host=host)

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
