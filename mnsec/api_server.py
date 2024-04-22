import threading
from werkzeug.serving import make_server
from dash import Dash, html, dcc, Input, Output
import dash_cytoscape as cyto
from mininet.log import info

class APIServer:
    def __init__(self, mnsec, name="mininet-sec", listen="0.0.0.0", port=8050):
        """Starts Flask/Dash API server. Requires Mininet-Sec object."""
        self.name = name
        self.mnsec = mnsec
        self.listen = listen
        self.port = port

        self.app = Dash(name)
        self.server = make_server(listen, port, self.app.server, threaded=True, processes=0)
        self.server_task = None

    def setup(self):
        elements = []
        for host in self.mnsec.hosts:
            elements.append({"data": {"id": host.name, "label": host.name}, "classes": "rectangle"})
        for switch in self.mnsec.switches:
            elements.append({"data": {"id": switch.name, "label": switch.name}})
        for link in self.mnsec.links:
            elements.append({"data": {"source": link.intf1.node.name, "target": link.intf2.node.name}})

        self.app.layout = html.Div(
            [
                dcc.Dropdown(
                    id="dropdown-update-layout",
                    value="cose",
                    clearable=False,
                    options=[
                        {"label": name.capitalize(), "value": name}
                        for name in ["grid", "random", "circle", "cose", "concentric"]
                    ],
                ),
                cyto.Cytoscape(
                    id="cytoscape-update-layout",
                    layout={"name": "cose"},
                    style={"width": "100%", "height": "650px"},
                    elements=elements,
                    stylesheet = [
                        # Group selectors
                        {
                            'selector': 'node',
                            'style': {
                                'content': 'data(label)'
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
                    ],
                ),
            ]
        )

        @self.app.callback(
            Output("cytoscape-update-layout", "layout"),
            Input("dropdown-update-layout", "value"),
        )
        def update_layout(layout):
            return {"name": layout, "animate": True}

        self.app.server.add_url_rule("/topology", None, self.get_topology, methods=["GET"])
        self.app.server.add_url_rule("/mnsecx/<name>", None, self.post_mnsec_exec, methods=["POST"])

    def get_topology(self):
        topo = {'nodes':[], 'links':[]}
        for host in self.mnsec.hosts:
            topo["nodes"].append({"name": host.name, "type": "host"})
        for switch in self.mnsec.switches:
            topo["nodes"].append({"name": switch.name, "type": "switch"})
        for link in self.mnsec.links:
            topo["links"].append({"source": link.intf1.node.name, "target": link.intf2.node.name})
        return topo, 200

    def post_mnsec_exec(self, name):
        data = request.get_json(force=True)
        info(f"exec cmd on {name}: {data}")
        if not data.get("cmd"):
            return "Invalid command on request body", 404
        node = self.mnsec.get(name)
        if not node:
            return f"Invalid node name: {name}", 404
        cmdOut = node.cmd(data["cmd"])
        return {"result": cmdOut}, 200

    def run_server(self):
        info(f"APIServer listening on port {self.listen}:{self.port}\n")
        try:
            self.server.serve_forever()
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
