import {
  Node,
  FlowPosition,
  NodeUI,
  StickyNote
} from '../store/flow-definition';
import { snapToGrid } from './utils';

const VERTICAL_GAP = 80;
const HORIZONTAL_GAP = 60;
const STICKY_GAP = 20;
const MAX_WIDTH = 1200;

interface NodeSize {
  width: number;
  height: number;
}

/**
 * Calculates a layered layout for a flow, placing the start node at the
 * upper-left and arranging the flow downward. Sibling nodes at splits
 * share the same horizontal plane.
 */
export function calculateLayeredLayout(
  nodes: Node[],
  nodeUIs: Record<string, NodeUI>,
  startNodeUuid: string,
  getNodeSize: (uuid: string) => NodeSize
): Record<string, FlowPosition> {
  if (nodes.length === 0) return {};

  const nodeSet = new Set(nodes.map((n) => n.uuid));

  // Build deduplicated adjacency lists
  const children = new Map<string, string[]>();
  const parents = new Map<string, string[]>();

  for (const node of nodes) {
    const seen = new Set<string>();
    const childUuids: string[] = [];
    for (const exit of node.exits) {
      if (
        exit.destination_uuid &&
        nodeSet.has(exit.destination_uuid) &&
        !seen.has(exit.destination_uuid)
      ) {
        seen.add(exit.destination_uuid);
        childUuids.push(exit.destination_uuid);
        const p = parents.get(exit.destination_uuid) || [];
        p.push(node.uuid);
        parents.set(exit.destination_uuid, p);
      }
    }
    children.set(node.uuid, childUuids);
  }

  // Find back-edges via DFS so we can ignore cycles during layering
  const backEdges = findBackEdges(startNodeUuid, children);

  // Assign layers using longest-path on the DAG (ignoring back-edges)
  const layers = assignLayers(
    startNodeUuid,
    nodes,
    children,
    parents,
    backEdges
  );

  // Group nodes by layer
  const layerGroups = new Map<number, string[]>();
  for (const [uuid, layer] of layers) {
    const group = layerGroups.get(layer) || [];
    group.push(uuid);
    layerGroups.set(layer, group);
  }

  // Order nodes within each layer using barycenter heuristic
  const sortedLayers = Array.from(layerGroups.keys()).sort((a, b) => a - b);
  orderNodesInLayers(sortedLayers, layerGroups, parents, layers);

  // Gather sizes
  const sizes = new Map<string, NodeSize>();
  for (const node of nodes) {
    sizes.set(node.uuid, getNodeSize(node.uuid));
  }

  // Compute positions
  return computePositions(
    sortedLayers,
    layerGroups,
    sizes,
    parents,
    layers,
    startNodeUuid
  );
}

/**
 * Finds back-edges (cycle-forming edges) via DFS from the start node.
 * Returns a set of "parentUuid->childUuid" strings representing edges to ignore.
 */
function findBackEdges(
  startNodeUuid: string,
  children: Map<string, string[]>
): Set<string> {
  const backEdges = new Set<string>();
  const visiting = new Set<string>(); // currently on the DFS stack
  const visited = new Set<string>(); // fully processed

  function dfs(node: string): void {
    visiting.add(node);
    visited.add(node);

    for (const child of children.get(node) || []) {
      if (visiting.has(child)) {
        backEdges.add(`${node}->${child}`);
      } else if (!visited.has(child)) {
        dfs(child);
      }
    }

    visiting.delete(node);
  }

  dfs(startNodeUuid);
  return backEdges;
}

/**
 * Assigns layers using topological processing order on the DAG
 * (back-edges removed). Each node's layer = max(parent layers) + 1,
 * giving the longest-path assignment so merge nodes sit below all parents.
 */
function assignLayers(
  startNodeUuid: string,
  nodes: Node[],
  children: Map<string, string[]>,
  parents: Map<string, string[]>,
  backEdges: Set<string>
): Map<string, number> {
  const layers = new Map<string, number>();
  layers.set(startNodeUuid, 0);

  // Build forward in-degree (ignoring back-edges) for topological processing
  const inDegree = new Map<string, number>();
  for (const node of nodes) {
    inDegree.set(node.uuid, 0);
  }
  for (const [parent, childList] of children) {
    for (const child of childList) {
      if (!backEdges.has(`${parent}->${child}`)) {
        inDegree.set(child, (inDegree.get(child) || 0) + 1);
      }
    }
  }

  // Process nodes in topological order (Kahn's algorithm)
  // Start with nodes that have no forward in-edges
  const queue: string[] = [];
  for (const [uuid, deg] of inDegree) {
    if (deg === 0) {
      queue.push(uuid);
      if (!layers.has(uuid)) {
        layers.set(uuid, 0);
      }
    }
  }

  while (queue.length > 0) {
    const current = queue.shift()!;
    const currentLayer = layers.get(current)!;

    for (const child of children.get(current) || []) {
      if (backEdges.has(`${current}->${child}`)) continue;

      // Longest path: child layer = max of all parent layers + 1
      const newLayer = currentLayer + 1;
      if (!layers.has(child) || newLayer > layers.get(child)!) {
        layers.set(child, newLayer);
      }

      // Decrement in-degree; enqueue when all forward parents processed
      const remaining = inDegree.get(child)! - 1;
      inDegree.set(child, remaining);
      if (remaining === 0) {
        queue.push(child);
      }
    }
  }

  // Handle unreachable nodes (not reachable from start)
  const unreachable = nodes.filter((n) => !layers.has(n.uuid));
  if (unreachable.length > 0) {
    const maxLayer = Math.max(...Array.from(layers.values()), -1);
    let unreachableLayer = maxLayer + 2;
    for (const node of unreachable) {
      layers.set(node.uuid, unreachableLayer);
      unreachableLayer++;
    }
  }

  return layers;
}

/**
 * Orders nodes within each layer using a barycenter heuristic:
 * each node is positioned based on the average index of its parents
 * in layers above.
 */
function orderNodesInLayers(
  sortedLayers: number[],
  layerGroups: Map<number, string[]>,
  parents: Map<string, string[]>,
  layers: Map<string, number>
): void {
  const indexInLayer = new Map<string, number>();

  for (const layer of sortedLayers) {
    const group = layerGroups.get(layer)!;

    if (layer === sortedLayers[0]) {
      group.forEach((uuid, idx) => indexInLayer.set(uuid, idx));
      continue;
    }

    const barycenters: { uuid: string; value: number }[] = group.map((uuid) => {
      // Only consider parents that are in layers above this one
      const nodeParents = (parents.get(uuid) || []).filter((p) => {
        const pl = layers.get(p);
        return pl !== undefined && pl < layer;
      });
      if (nodeParents.length === 0) {
        return { uuid, value: Infinity };
      }
      const sum = nodeParents.reduce((acc, p) => {
        return acc + (indexInLayer.get(p) ?? 0);
      }, 0);
      return { uuid, value: sum / nodeParents.length };
    });

    barycenters.sort((a, b) => a.value - b.value);

    const sorted = barycenters.map((b) => b.uuid);
    layerGroups.set(layer, sorted);
    sorted.forEach((uuid, idx) => indexInLayer.set(uuid, idx));
  }
}

/**
 * Splits a layer's nodes into sub-rows that each fit within MAX_WIDTH.
 */
function splitIntoRows(
  group: string[],
  sizes: Map<string, NodeSize>
): string[][] {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentWidth = 0;

  for (const uuid of group) {
    const nodeWidth = sizes.get(uuid)?.width || 200;
    const additionalWidth =
      currentRow.length > 0 ? HORIZONTAL_GAP + nodeWidth : nodeWidth;

    if (currentRow.length > 0 && currentWidth + additionalWidth > MAX_WIDTH) {
      rows.push(currentRow);
      currentRow = [uuid];
      currentWidth = nodeWidth;
    } else {
      currentRow.push(uuid);
      currentWidth += additionalWidth;
    }
  }

  if (currentRow.length > 0) {
    rows.push(currentRow);
  }

  return rows;
}

/**
 * Computes pixel positions for each node. Each node's ideal X is centered
 * under its parent(s), with overlap resolution to prevent collisions.
 * Layers that exceed MAX_WIDTH are split into multiple rows.
 */
function computePositions(
  sortedLayers: number[],
  layerGroups: Map<number, string[]>,
  sizes: Map<string, NodeSize>,
  parents: Map<string, string[]>,
  layers: Map<string, number>,
  startNodeUuid: string
): Record<string, FlowPosition> {
  const positions: Record<string, FlowPosition> = {};
  let currentTop = 0;

  for (const layer of sortedLayers) {
    const group = layerGroups.get(layer)!;
    const subRows = splitIntoRows(group, sizes);

    for (const subRow of subRows) {
      const top = snapToGrid(currentTop);

      if (layer === sortedLayers[0]) {
        // First layer: start node at top, others nudged down two grid squares
        let x = 0;
        for (const uuid of subRow) {
          const nodeTop = uuid === startNodeUuid ? top : top + 40;
          positions[uuid] = { left: snapToGrid(x), top: nodeTop };
          x += (sizes.get(uuid)?.width || 200) + HORIZONTAL_GAP;
        }
      } else {
        // Compute total width of this sub-row
        let totalWidth = 0;
        for (const uuid of subRow) {
          totalWidth += sizes.get(uuid)?.width || 200;
        }
        totalWidth += HORIZONTAL_GAP * (subRow.length - 1);

        // Find the center point to place this sub-row under: midpoint of
        // the span of all parent centers for nodes in this sub-row
        const parentCenters: number[] = [];
        for (const uuid of subRow) {
          const nodeParents = (parents.get(uuid) || []).filter((p) => {
            const pl = layers.get(p);
            return pl !== undefined && pl < layer;
          });
          for (const pUuid of nodeParents) {
            const parentPos = positions[pUuid];
            if (parentPos) {
              const parentWidth = sizes.get(pUuid)?.width || 200;
              parentCenters.push(parentPos.left + parentWidth / 2);
            }
          }
        }

        // Center the sub-row under the parent span, anchored left if not enough room
        let rowLeft: number;
        if (parentCenters.length > 0) {
          const spanCenter =
            (Math.min(...parentCenters) + Math.max(...parentCenters)) / 2;
          rowLeft = Math.max(0, spanCenter - totalWidth / 2);
        } else {
          rowLeft = 0;
        }

        // Place nodes left-to-right starting from rowLeft
        let x = rowLeft;
        for (const uuid of subRow) {
          const nodeWidth = sizes.get(uuid)?.width || 200;
          positions[uuid] = { left: snapToGrid(x), top };
          x = snapToGrid(x) + nodeWidth + HORIZONTAL_GAP;
        }
      }

      // Advance past this sub-row
      const maxHeight = Math.max(
        ...subRow.map((uuid) => sizes.get(uuid)?.height || 100)
      );
      currentTop = top + maxHeight + VERTICAL_GAP;
    }
  }

  // Shift everything so the start node is at (0, 0)
  const startPos = positions[startNodeUuid];
  if (startPos) {
    const offsetX = startPos.left;
    const offsetY = startPos.top;

    for (const uuid of Object.keys(positions)) {
      positions[uuid] = {
        left: snapToGrid(Math.max(0, positions[uuid].left - offsetX)),
        top: snapToGrid(Math.max(0, positions[uuid].top - offsetY))
      };
    }
  }

  return positions;
}

interface StickySize {
  width: number;
  height: number;
}

/**
 * Places sticky notes next to the node they were closest to before reflow.
 * If a sticky was to the left of the start node, it is placed to the right instead.
 */
export function placeStickyNotes(
  stickies: Record<string, StickyNote>,
  oldNodePositions: Record<string, FlowPosition>,
  newNodePositions: Record<string, FlowPosition>,
  nodeSizes: Map<string, NodeSize>,
  stickySizes: Map<string, StickySize>,
  startNodeUuid: string
): Record<string, FlowPosition> {
  const stickyPositions: Record<string, FlowPosition> = {};
  const nodeUuids = Object.keys(newNodePositions);
  if (nodeUuids.length === 0) return stickyPositions;

  // For each sticky, find the closest node based on pre-reflow positions
  const stickyToNode = new Map<string, string>();
  const nodeStickies = new Map<string, { uuid: string; wasLeft: boolean }[]>();

  for (const [stickyUuid, sticky] of Object.entries(stickies)) {
    if (!sticky.position) continue;

    const sx = sticky.position.left;
    const sy = sticky.position.top;

    let closestNode = nodeUuids[0];
    let closestDist = Infinity;

    for (const nodeUuid of nodeUuids) {
      const np = oldNodePositions[nodeUuid];
      if (!np) continue;
      const dx = sx - np.left;
      const dy = sy - np.top;
      const dist = dx * dx + dy * dy;
      if (dist < closestDist) {
        closestDist = dist;
        closestNode = nodeUuid;
      }
    }

    stickyToNode.set(stickyUuid, closestNode);

    // Was the sticky to the left of the node?
    const nodePos = oldNodePositions[closestNode];
    const wasLeft = nodePos ? sx < nodePos.left : false;

    const list = nodeStickies.get(closestNode) || [];
    list.push({ uuid: stickyUuid, wasLeft });
    nodeStickies.set(closestNode, list);
  }

  // Place stickies next to their associated nodes
  // Collect all placed rectangles (nodes + stickies) for collision avoidance
  const placed: { left: number; top: number; width: number; height: number }[] =
    [];

  // Add all nodes to placed rectangles
  for (const nodeUuid of nodeUuids) {
    const pos = newNodePositions[nodeUuid];
    const size = nodeSizes.get(nodeUuid) || { width: 200, height: 100 };
    placed.push({
      left: pos.left,
      top: pos.top,
      width: size.width,
      height: size.height
    });
  }

  for (const [nodeUuid, stickyList] of nodeStickies) {
    const nodePos = newNodePositions[nodeUuid];
    if (!nodePos) continue;
    const nodeSize = nodeSizes.get(nodeUuid) || { width: 200, height: 100 };

    for (const { uuid: stickyUuid, wasLeft } of stickyList) {
      const stickySize = stickySizes.get(stickyUuid) || {
        width: 182,
        height: 100
      };

      // Determine placement side: right of node if it's the start node and sticky
      // was to the left, otherwise prefer the side it was on originally
      const placeRight = (nodeUuid === startNodeUuid && wasLeft) || !wasLeft;

      let candidateLeft: number;
      if (placeRight) {
        candidateLeft = nodePos.left + nodeSize.width + STICKY_GAP;
      } else {
        candidateLeft = nodePos.left - stickySize.width - STICKY_GAP;
      }
      let candidateTop = nodePos.top;

      // Snap and clamp
      candidateLeft = snapToGrid(Math.max(0, candidateLeft));
      candidateTop = snapToGrid(Math.max(0, candidateTop));

      // Nudge down if colliding with any placed rectangle
      let maxAttempts = 50;
      while (
        maxAttempts-- > 0 &&
        collidesWithAny(
          candidateLeft,
          candidateTop,
          stickySize.width,
          stickySize.height,
          placed
        )
      ) {
        candidateTop = snapToGrid(candidateTop + STICKY_GAP);
      }

      stickyPositions[stickyUuid] = {
        left: candidateLeft,
        top: candidateTop
      };

      // Add this sticky to placed rectangles
      placed.push({
        left: candidateLeft,
        top: candidateTop,
        width: stickySize.width,
        height: stickySize.height
      });
    }
  }

  return stickyPositions;
}

function collidesWithAny(
  left: number,
  top: number,
  width: number,
  height: number,
  placed: { left: number; top: number; width: number; height: number }[]
): boolean {
  for (const r of placed) {
    if (
      left < r.left + r.width + STICKY_GAP &&
      left + width + STICKY_GAP > r.left &&
      top < r.top + r.height + STICKY_GAP &&
      top + height + STICKY_GAP > r.top
    ) {
      return true;
    }
  }
  return false;
}
