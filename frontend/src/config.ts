const CANVAS_WIDTH = 700 as const;
const CANVAS_HEIGHT = 700 as const;
const LINK_DISTANCE = 150 as const;
const NODE_ATTACHMENT_POINT = 10 as const;
const GRAPHML_DIR = "graphml"

const BITCOIN_CORE_BINARY_VERSIONS = [
  "20.0",
  "21.0",
  "22.0",
  "22.1",
  "23.0",
  "24.0",
  "24.0.1",
  "25.0",
  "0.21.0",
  "0.21.1",
  "0.20.1"
] as const;

const NODE_LATENCY = [
  "0ms",
  "5ms",
  "10ms",
  "15ms",
  "20ms",
  "30ms",
  "40ms",
] as const;

const RAM_OPTIONS = [
  2,
  4,
  6,
  8,
  12
] as const;

const CPU_CORES = [
  1,
  2,
  4,
  6,
  8,
] as const;

export {
  GRAPHML_DIR,
  CANVAS_WIDTH,
  CANVAS_HEIGHT,
  LINK_DISTANCE,
  NODE_LATENCY,
  RAM_OPTIONS,
  CPU_CORES,
  NODE_ATTACHMENT_POINT,
  BITCOIN_CORE_BINARY_VERSIONS,
};
