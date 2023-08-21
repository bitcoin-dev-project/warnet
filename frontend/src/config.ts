const CANVAS_WIDTH = 700 as const;
const CANVAS_HEIGHT = 700 as const;
const LINK_DISTANCE = 150 as const;
const NODE_ATTACHMENT_POINT = 10 as const;

const BITCOIN_CORE_BINARY_VERSIONS = [
  "22.0",
  "23.0",
  "24.0",
  "24.1",
  "25.0",
] as const;

const NODE_LATENCY = [
  "0ms",
  "10ms",
  "20ms",
  "30ms",
  "40ms",
]

export {
  CANVAS_WIDTH,
  CANVAS_HEIGHT,
  LINK_DISTANCE,
  NODE_LATENCY,
  NODE_ATTACHMENT_POINT,
  BITCOIN_CORE_BINARY_VERSIONS,
};
