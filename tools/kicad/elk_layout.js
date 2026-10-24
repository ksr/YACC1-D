// Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
//
// elk_layout.js - lay out one schematic sheet with ELK (the Eclipse Layout Kernel, elkjs). Reads an ELK JSON graph
// on stdin (built by tools/kicad/sch_wire.py: one node per symbol unit or label, fixed port positions on the 1.27 mm
// grid), runs the layered algorithm with orthogonal edge routing, writes the laid-out graph (node positions, edge
// sections and bend points) on stdout. The model is the P8X project's generators/sch/elk_layout.js.
//     node tools/kicad/elk_layout.js < graph.json > layout.json
const ELK = require("elkjs");
let input = "";
process.stdin.on("data", (d) => (input += d));
process.stdin.on("end", async () => {
  const graph = JSON.parse(input);
  graph.layoutOptions = Object.assign({
    "elk.algorithm": "layered",
    "elk.direction": "RIGHT",
    "elk.edgeRouting": "ORTHOGONAL",
    "elk.layered.mergeEdges": "true",                 // one wire trunk per net
    "elk.portConstraints": "FIXED_POS",
    "elk.spacing.nodeNode": "6",
    "elk.layered.spacing.nodeNodeBetweenLayers": "8",
    "elk.spacing.edgeEdge": "2",
    "elk.layered.spacing.edgeEdgeBetweenLayers": "2",
    "elk.spacing.edgeNode": "2",
    "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
    "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
    "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",  // keep the given part order where it costs nothing
  }, graph.layoutOptions || {});
  try {
    const out = await new ELK().layout(graph);
    process.stdout.write(JSON.stringify(out));
  } catch (e) {
    process.stderr.write("elk_layout: " + e + "\n");
    process.exit(1);
  }
});
