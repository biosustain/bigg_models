from typing import Any, Dict
from tornado.web import HTTPError
from biggr_models.handlers import utils
from escher import plots
import json
from cobradb.api.escher import ESCHER_MODULE_DEFINITIONS

from biggr_models.queries.escher_queries import get_model_reactions_for_escher_map

ESCHER_CSS = """svg.escher-svg #mouse-node {
  fill: none;
}
svg.escher-svg #canvas {
  stroke: #ccc;
  stroke-width: 7px;
  fill: white;
}
svg.escher-svg .resize-rect {
  fill: black;
  opacity: 0;
  stroke: none;
}
svg.escher-svg .label {
  font-family: sans-serif;
  font-style: italic;
  font-weight: bold;
  font-size: 8px;
  fill: black;
  stroke: none;
  text-rendering: optimizelegibility;
  cursor: default;
}
svg.escher-svg .reaction-label {
  font-size: 30px;
  fill: rgb(13, 110, 253);
  text-rendering: optimizelegibility;
}
svg.escher-svg .node-label {
  font-size: 20px;
}
svg.escher-svg .gene-label {
  font-size: 18px;
  fill: rgb(32, 32, 120);
  text-rendering: optimizelegibility;
  cursor: default;
}
svg.escher-svg .text-label .label {
  font-size: 50px;
}
svg.escher-svg .text-label-input {
  font-size: 50px;
}
svg.escher-svg .node-circle {
  stroke-width: 4px;
}
svg.escher-svg .midmarker-circle, svg.escher-svg .multimarker-circle {
  fill: white;
  fill-opacity: 0.2;
  stroke: rgb(50, 50, 50);
  display: none !important;
}
svg.escher-svg g.selected .node-circle{
  stroke-width: 6px;
  stroke: rgb(20, 113, 199);
}
svg.escher-svg g.selected .label {
  fill: rgb(20, 113, 199);
}
svg.escher-svg .metabolite-circle {
  stroke: #d36b2a;
  fill: #ff883f;
}
svg.escher-svg g.selected .metabolite-circle {
  stroke: rgb(5, 2, 0);
}
svg.escher-svg .segment {
  stroke: #334E75;
  stroke-width: 10px;
  fill: none;
}
svg.escher-svg .arrowhead {
  fill: #334E75;
}
svg.escher-svg .stoichiometry-label-rect {
  fill: white;
  opacity: 0.5;
}
svg.escher-svg .stoichiometry-label {
  fill: #334E75;
  font-size: 17px;
}
svg.escher-svg .membrane {
  fill: none;
  stroke: rgb(255, 187, 0);
}
svg.escher-svg .brush .extent {
  fill-opacity: 0.1;
  fill: black;
  stroke: #fff;
  shape-rendering: crispEdges;
}
svg.escher-svg #brush-container .background {
  fill: none;
}
svg.escher-svg .bezier-circle {
  fill: rgb(255,255,255);
}
svg.escher-svg .bezier-circle.b1 {
  stroke: red;
}
svg.escher-svg .bezier-circle.b2 {
  stroke: blue;
}
svg.escher-svg .connect-line{
  stroke: rgb(200,200,200);
}
svg.escher-svg .direction-arrow {
  cursor: default;
  stroke: black;
  stroke-width: 1px;
  fill: white;
  opacity: 0.3;
}
svg.escher-svg .start-reaction-target {
  stroke: rgb(100,100,100);
  fill: none;
  opacity: 0.5;
}
svg.escher-svg .rotation-center-line {
  stroke: red;
  stroke-width: 5px;
}
svg.escher-svg .highlight {
  fill: #D97000;
  text-decoration: underline;
}
svg.escher-svg .node-to-combine {
  stroke-width: 12px !important;
}
.escher-container .button.btn, .escher-container .buttonGroup.btn {
  border-radius: none !important;
  background: rgb(51, 122, 183) !important;
  border: 1px solid rgb(43.35, 103.7, 155.55) !important;
  color: white !important;
  font-weight: normal !important;
}
.legend-container{
  display: none !important;
}
"""


def builder_to_html_string(builder: plots.Builder, **kwargs):
    # This is the same as the Builder.save_html method,
    # except it does not write the html to a file.
    options = {}
    for key in builder.traits(option=True):
        val = getattr(builder, key)
        if val is not None:
            options[key] = val
    options_json = json.dumps(options)

    template = utils.env.get_template("escher_standalone.html")
    embedded_css_b64 = (
        plots.b64dump(builder.embedded_css)
        if builder.embedded_css is not None
        else None
    )
    html = template.render(
        escher_url=plots.get_url("escher_min"),
        embedded_css_b64=embedded_css_b64,
        map_data_json_b64=plots.b64dump(builder._loaded_map_json),
        model_data_json_b64=plots.b64dump(builder._loaded_model_json),
        options_json_b64=plots.b64dump(options_json),
        **kwargs
    )

    return html.encode("utf-8")


class EscherHandler(utils.BaseHandler):
    name = None

    def initialize(self, **kwargs):
        self.name = kwargs.get("name")

    def prepare(self):
        self.api = self.path_kwargs.get("api") is not None

    def get(self, model_bigg_id: str, map_bigg_id: str, **kwargs):
        escher_module = ESCHER_MODULE_DEFINITIONS.get(map_bigg_id)
        if escher_module is None:
            raise HTTPError(status_code=404, reason="Map BiGG ID not found.")
        model_reactions = utils.do_safe_query(
            get_model_reactions_for_escher_map, model_bigg_id, map_bigg_id
        )
        escher_map = utils.do_safe_query(escher_module.build_map, model_reactions)
        escher_map.fit_canvas(expand_only=False)
        escher_map_json = escher_map.to_escher()
        if self.api:
            if (
                str(self.get_query_argument("download", default="false")).lower()
                == "true"
            ):
                self.set_header("Content-Type", "application/x-json")
                self.set_header(
                    "Content-Disposition", 'attachment; filename="bigg_reactions.json"'
                )
            self.write(escher_map_json)
            self.finish()
        else:
            sel_reactions = set(self.get_query_arguments("reaction"))
            reaction_data = None
            zoom_to_element = None
            if sel_reactions:
                reaction_data = {rx: 1 for rx in sel_reactions}
                if len(sel_reactions) == 1:
                    zoom_reaction_bigg_id = sel_reactions.pop()
                    zoom_to_element_id = next(
                        (
                            k
                            for k, x in escher_map.reactions.items()
                            if x.bigg_id == zoom_reaction_bigg_id
                        ),
                        None,
                    )
                    if zoom_to_element_id is not None:
                        zoom_to_element = {"type": "reaction", "id": zoom_to_element_id}

            if str(self.get_query_argument("edit", default="false")).lower() == "true":
                self.write_map(
                    json.dumps(escher_map_json),
                    menu="all",
                    scroll_behavior="pan",
                    never_ask_before_quit=False,
                    enable_keys=True,
                    enable_editing=True,
                    reaction_data=reaction_data,
                    reaction_styles=["color"],
                    metabolite_styles=["color"],
                    zoom_to_element=zoom_to_element,
                    embedded_css=ESCHER_CSS,
                    builder_opts=dict(model_bigg_id=model_bigg_id),
                )
            else:
                self.write_map(
                    json.dumps(escher_map_json),
                    menu="zoom",
                    scroll_behavior=None,
                    never_ask_before_quit=True,
                    enable_keys=False,
                    enable_editing=False,
                    reaction_data=reaction_data,
                    reaction_styles=["color"],
                    metabolite_styles=["color"],
                    zoom_to_element=zoom_to_element,
                    embedded_css=ESCHER_CSS,
                    builder_opts=dict(model_bigg_id=model_bigg_id),
                )

    def write_map(self, map_json: str, builder_opts: Dict[str, Any] = {}, **kwargs):
        builder = plots.Builder(map_json=map_json, **kwargs)
        html = builder_to_html_string(builder, **builder_opts)
        self.write(html)
