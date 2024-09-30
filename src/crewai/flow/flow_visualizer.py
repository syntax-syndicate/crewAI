import base64
import os
import re
from abc import ABC, abstractmethod

from pyvis.network import Network


class FlowVisualizer(ABC):
    def __init__(self, flow):
        self.flow = flow
        self.colors = {
            "bg": "#FFFFFF",
            "start": "#FF5A50",
            "method": "#333333",
            "router": "#333333",  # Dark gray for router background
            "router_border": "#FF8C00",  # Orange for router border
            "edge": "#666666",
            "router_edge": "#FF8C00",  # Orange for router edges
            "text": "#FFFFFF",
        }
        self.node_styles = {
            "start": {
                "color": self.colors["start"],
                "shape": "box",
                "font": {"color": self.colors["text"]},
            },
            "method": {
                "color": self.colors["method"],
                "shape": "box",
                "font": {"color": self.colors["text"]},
            },
            "router": {
                "color": self.colors["router"],
                "shape": "box",
                "font": {"color": self.colors["text"]},
                "borderWidth": 2,
                "borderWidthSelected": 4,
                "borderDashes": [5, 5],  # Dashed border
                "borderColor": self.colors["router_border"],
            },
        }

    @abstractmethod
    def visualize(self, filename):
        pass


class PyvisFlowVisualizer(FlowVisualizer):
    def visualize(self, filename):
        net = Network(
            directed=True,
            height="750px",
            width="100%",
            bgcolor=self.colors["bg"],
            layout=None,
        )

        # Calculate levels for nodes
        node_levels = self._calculate_node_levels()
        print("node_levels", node_levels)

        # Assign positions to nodes based on levels
        y_spacing = 150  # Adjust spacing between levels (positive for top-down)
        x_spacing = 150  # Adjust spacing between nodes
        level_nodes = {}

        for method_name, level in node_levels.items():
            level_nodes.setdefault(level, []).append(method_name)

        print("level_nodes", level_nodes)

        # Compute positions
        for level, nodes in level_nodes.items():
            print("level", level, "nodes", nodes)
            x_offset = -(len(nodes) - 1) * x_spacing / 2  # Center nodes horizontally
            for i, method_name in enumerate(nodes):
                x = x_offset + i * x_spacing
                y = level * y_spacing  # Use level directly for y position
                method = self.flow._methods.get(method_name)
                if hasattr(method, "__is_start_method__"):
                    node_style = self.node_styles["start"]
                elif method_name in self.flow._routers.values():
                    node_style = self.node_styles["router"]
                else:
                    node_style = self.node_styles["method"]

                net.add_node(
                    method_name,
                    label=method_name,
                    x=x,
                    y=y,
                    fixed=True,
                    physics=False,  # Disable physics for fixed positioning
                    **node_style,
                )

        # Add edges
        print("self.flow._routers.values()", self.flow._routers)
        for method_name in self.flow._listeners:
            print("Listeners for", method_name)
            condition_type, trigger_methods = self.flow._listeners[method_name]
            is_and_condition = condition_type == "AND"

            for trigger in trigger_methods:
                print("Trigger", trigger)
                if trigger in self.flow._methods:
                    is_router_edge = any(
                        trigger in paths for paths in self.flow._router_paths.values()
                    )
                    print("is_router_edge", is_router_edge)
                    edge_color = (
                        self.colors["router_edge"]
                        if is_router_edge
                        else self.colors["edge"]
                    )
                    edge_style = {
                        "color": edge_color,
                        "width": 2,
                        "arrows": "to",
                        "dashes": True if is_router_edge or is_and_condition else False,
                        "smooth": {"type": "cubicBezier"},
                    }
                    net.add_edge(trigger, method_name, **edge_style)

        # Add edges from router methods to their possible paths
        for router_method_name, paths in self.flow._router_paths.items():
            for path in paths:
                for listener_name, (
                    condition_type,
                    trigger_methods,
                ) in self.flow._listeners.items():
                    if path in trigger_methods:
                        edge_style = {
                            "color": self.colors["router_edge"],
                            "width": 2,
                            "arrows": "to",
                            "dashes": True,
                            "smooth": {"type": "cubicBezier"},
                        }
                        net.add_edge(router_method_name, listener_name, **edge_style)

        # Set options for curved edges and disable physics
        net.set_options(
            """
            var options = {
            "physics": {
                "enabled": false
            },
            "edges": {
                "smooth": {
                "enabled": true,
                "type": "cubicBezier",
                "roundness": 0.5
                }
            }
            }
            """
        )

        network_html = net.generate_html()

        # Extract just the body content from the generated HTML
        match = re.search("<body.*?>(.*?)</body>", network_html, re.DOTALL)
        if match:
            network_body = match.group(1)
        else:
            network_body = ""

        # Read the custom template
        current_dir = os.path.dirname(__file__)
        template_path = os.path.join(
            current_dir, "assets", "crewai_flow_visual_template.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            html_template = f.read()

        # Generate the legend items HTML
        legend_items = [
            {"label": "Start Method", "color": self.colors["start"]},
            {"label": "Method", "color": self.colors["method"]},
            {
                "label": "Router",
                "color": self.colors["router"],
                "border": self.colors["router_border"],
                "dashed": True,
            },
            {"label": "Trigger", "color": self.colors["edge"], "dashed": False},
            {"label": "AND Trigger", "color": self.colors["edge"], "dashed": True},
            {
                "label": "Router Trigger",
                "color": self.colors["router_edge"],
                "dashed": True,
            },
        ]

        legend_items_html = ""
        for item in legend_items:
            if "border" in item:
                legend_items_html += f"""
                <div class="legend-item">
                <div class="legend-color-box" style="background-color: {item['color']}; border: 2px dashed {item['border']};"></div>
                <div>{item['label']}</div>
                </div>
                """
            elif item.get("dashed") is not None:
                style = "dashed" if item["dashed"] else "solid"
                legend_items_html += f"""
                <div class="legend-item">
                <div class="legend-{style}" style="border-bottom: 2px {style} {item['color']};"></div>
                <div>{item['label']}</div>
                </div>
                """
            else:
                legend_items_html += f"""
                <div class="legend-item">
                <div class="legend-color-box" style="background-color: {item['color']};"></div>
                <div>{item['label']}</div>
                </div>
                """

        # Read the logo file and encode it
        logo_path = os.path.join(current_dir, "assets", "crewai_logo.svg")
        with open(logo_path, "rb") as logo_file:
            logo_svg_data = logo_file.read()
            logo_svg_base64 = base64.b64encode(logo_svg_data).decode("utf-8")

        # Replace placeholders in the template
        final_html_content = html_template.replace("{{ title }}", "Flow Graph")
        final_html_content = final_html_content.replace(
            "{{ network_content }}", network_body
        )
        final_html_content = final_html_content.replace(
            "{{ logo_svg_base64 }}", logo_svg_base64
        )
        final_html_content = final_html_content.replace(
            "<!-- LEGEND_ITEMS_PLACEHOLDER -->", legend_items_html
        )

        # Save the final HTML content to the file
        with open(f"{filename}.html", "w", encoding="utf-8") as f:
            f.write(final_html_content)
        print(f"Graph saved as {filename}.html")

    def _calculate_node_levels(self):
        levels = {}
        queue = []
        visited = set()
        pending_and_listeners = {}

        # Initialize start methods at level 0
        for method_name, method in self.flow._methods.items():
            if hasattr(method, "__is_start_method__"):
                levels[method_name] = 0
                queue.append(method_name)

        # Breadth-first traversal to assign levels
        while queue:
            current = queue.pop(0)
            current_level = levels[current]
            visited.add(current)

            # Get methods that listen to the current method
            for listener_name, (
                condition_type,
                trigger_methods,
            ) in self.flow._listeners.items():
                if condition_type == "OR":
                    if current in trigger_methods:
                        if (
                            listener_name not in levels
                            or levels[listener_name] > current_level + 1
                        ):
                            levels[listener_name] = current_level + 1
                            if listener_name not in visited:
                                queue.append(listener_name)
                elif condition_type == "AND":
                    if listener_name not in pending_and_listeners:
                        pending_and_listeners[listener_name] = set()
                    if current in trigger_methods:
                        pending_and_listeners[listener_name].add(current)
                    if set(trigger_methods) == pending_and_listeners[listener_name]:
                        if (
                            listener_name not in levels
                            or levels[listener_name] > current_level + 1
                        ):
                            levels[listener_name] = current_level + 1
                            if listener_name not in visited:
                                queue.append(listener_name)

            # Handle router connections (same as before)
            if current in self.flow._routers.values():
                router_method_name = current
                paths = self.flow._router_paths.get(router_method_name, [])
                for path in paths:
                    for listener_name, (
                        condition_type,
                        trigger_methods,
                    ) in self.flow._listeners.items():
                        if path in trigger_methods:
                            if (
                                listener_name not in levels
                                or levels[listener_name] > current_level + 1
                            ):
                                levels[listener_name] = current_level + 1
                                if listener_name not in visited:
                                    queue.append(listener_name)
        return levels


def visualize_flow(flow, filename="flow_graph"):
    visualizer = PyvisFlowVisualizer(flow)
    visualizer.visualize(filename)