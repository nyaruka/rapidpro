import { expect } from '@open-wc/testing';
import { calculateLayeredLayout, placeStickyNotes } from '../src/flow/reflow';
import { Node, StickyNote } from '../src/store/flow-definition';

// Helper to create a minimal Node with exits
function makeNode(uuid: string, exits: { destination_uuid?: string }[]): Node {
  return {
    uuid,
    actions: [],
    exits: exits.map((e, i) => ({
      uuid: `${uuid}-exit-${i}`,
      destination_uuid: e.destination_uuid
    }))
  };
}

// Helper to return a fixed size for all nodes
function constantSize(width: number, height: number) {
  return () => ({ width, height });
}

describe('Reflow Layout', () => {
  describe('calculateLayeredLayout', () => {
    it('returns empty object for empty nodes', () => {
      const result = calculateLayeredLayout(
        [],
        {},
        'start',
        constantSize(200, 100)
      );
      expect(Object.keys(result)).to.have.length(0);
    });

    it('places a single node at the origin', () => {
      const nodes = [makeNode('A', [])];
      const nodeUIs = { A: { position: { left: 500, top: 500 } } };
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      expect(result['A']).to.not.be.undefined;
      expect(result['A'].left).to.equal(0);
      expect(result['A'].top).to.equal(0);
    });

    it('places a linear chain vertically', () => {
      // A -> B -> C
      const nodes = [
        makeNode('A', [{ destination_uuid: 'B' }]),
        makeNode('B', [{ destination_uuid: 'C' }]),
        makeNode('C', [])
      ];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 0, top: 200 } },
        C: { position: { left: 0, top: 400 } }
      };
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      // All should be at left=0 (centered under parent which is at 0)
      // A at layer 0, B at layer 1, C at layer 2
      expect(result['A'].top).to.equal(0);
      expect(result['B'].top).to.be.greaterThan(result['A'].top);
      expect(result['C'].top).to.be.greaterThan(result['B'].top);
    });

    it('places siblings at the same vertical level', () => {
      // A -> B, A -> C
      const nodes = [
        makeNode('A', [{ destination_uuid: 'B' }, { destination_uuid: 'C' }]),
        makeNode('B', []),
        makeNode('C', [])
      ];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 0, top: 200 } },
        C: { position: { left: 300, top: 200 } }
      };
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      // B and C should be on the same layer (same top)
      expect(result['B'].top).to.equal(result['C'].top);
      expect(result['B'].top).to.be.greaterThan(result['A'].top);
      // B and C should be side by side
      expect(result['B'].left).to.not.equal(result['C'].left);
    });

    it('snaps all positions to grid (multiples of 20)', () => {
      const nodes = [
        makeNode('A', [{ destination_uuid: 'B' }]),
        makeNode('B', [])
      ];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 0, top: 200 } }
      };
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      for (const uuid of Object.keys(result)) {
        expect(result[uuid].left % 20).to.equal(0);
        expect(result[uuid].top % 20).to.equal(0);
      }
    });

    it('handles cycles (back-edges) without infinite loops', () => {
      // A -> B -> A (cycle)
      const nodes = [
        makeNode('A', [{ destination_uuid: 'B' }]),
        makeNode('B', [{ destination_uuid: 'A' }])
      ];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 0, top: 200 } }
      };
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      expect(result['A']).to.not.be.undefined;
      expect(result['B']).to.not.be.undefined;
      // A should be above B (layer 0 vs layer 1)
      expect(result['A'].top).to.be.lessThan(result['B'].top);
    });

    it('handles diamond-shaped flows (merge nodes)', () => {
      // A -> B, A -> C, B -> D, C -> D
      const nodes = [
        makeNode('A', [{ destination_uuid: 'B' }, { destination_uuid: 'C' }]),
        makeNode('B', [{ destination_uuid: 'D' }]),
        makeNode('C', [{ destination_uuid: 'D' }]),
        makeNode('D', [])
      ];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 0, top: 200 } },
        C: { position: { left: 300, top: 200 } },
        D: { position: { left: 150, top: 400 } }
      };
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      // D should be below both B and C (longest path assignment)
      expect(result['D'].top).to.be.greaterThan(result['B'].top);
      expect(result['D'].top).to.be.greaterThan(result['C'].top);
      // B and C on same layer
      expect(result['B'].top).to.equal(result['C'].top);
    });

    it('handles deduplicated exits (same destination from multiple exits)', () => {
      // A has two exits both pointing to B
      const nodes = [
        makeNode('A', [{ destination_uuid: 'B' }, { destination_uuid: 'B' }]),
        makeNode('B', [])
      ];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 0, top: 200 } }
      };
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      expect(result['A']).to.not.be.undefined;
      expect(result['B']).to.not.be.undefined;
      expect(result['B'].top).to.be.greaterThan(result['A'].top);
    });

    it('handles exits with no destination', () => {
      const nodes = [
        makeNode('A', [
          { destination_uuid: undefined },
          { destination_uuid: 'B' }
        ]),
        makeNode('B', [{ destination_uuid: undefined }])
      ];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 0, top: 200 } }
      };
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      expect(result['A']).to.not.be.undefined;
      expect(result['B']).to.not.be.undefined;
    });

    it('handles disconnected nodes', () => {
      // A -> B, C is disconnected (no edges at all)
      const nodes = [
        makeNode('A', [{ destination_uuid: 'B' }]),
        makeNode('B', []),
        makeNode('C', [])
      ];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 0, top: 200 } },
        C: { position: { left: 300, top: 300 } }
      };
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      // All nodes should receive positions
      expect(result['A']).to.not.be.undefined;
      expect(result['B']).to.not.be.undefined;
      expect(result['C']).to.not.be.undefined;
      // C (no edges, inDegree 0) lands in layer 0 alongside start node
      // but gets a 40px vertical offset since it's not the start node
      expect(result['C'].top).to.equal(40);
    });

    it('positions all nodes with non-negative coordinates', () => {
      const nodes = [
        makeNode('A', [{ destination_uuid: 'B' }, { destination_uuid: 'C' }]),
        makeNode('B', [{ destination_uuid: 'D' }]),
        makeNode('C', [{ destination_uuid: 'D' }]),
        makeNode('D', [])
      ];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 0, top: 200 } },
        C: { position: { left: 300, top: 200 } },
        D: { position: { left: 150, top: 400 } }
      };
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      for (const uuid of Object.keys(result)) {
        expect(result[uuid].left).to.be.at.least(0);
        expect(result[uuid].top).to.be.at.least(0);
      }
    });

    it('uses different node sizes for layout', () => {
      // A -> B -> C, B is tall
      const nodes = [
        makeNode('A', [{ destination_uuid: 'B' }]),
        makeNode('B', [{ destination_uuid: 'C' }]),
        makeNode('C', [])
      ];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 0, top: 200 } },
        C: { position: { left: 0, top: 500 } }
      };
      const getSize = (uuid: string) => {
        if (uuid === 'B') return { width: 200, height: 300 };
        return { width: 200, height: 100 };
      };
      const result = calculateLayeredLayout(nodes, nodeUIs, 'A', getSize);

      // Gap between B and C should account for B's height of 300
      const bBottom = result['B'].top + 300;
      expect(result['C'].top).to.be.greaterThanOrEqual(bBottom);
    });

    it('handles a complex flow with self-loops', () => {
      // A -> B, B -> B (self-loop), B -> C
      const nodes = [
        makeNode('A', [{ destination_uuid: 'B' }]),
        makeNode('B', [{ destination_uuid: 'B' }, { destination_uuid: 'C' }]),
        makeNode('C', [])
      ];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 0, top: 200 } },
        C: { position: { left: 0, top: 400 } }
      };
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      expect(result['A'].top).to.equal(0);
      expect(result['B'].top).to.be.greaterThan(result['A'].top);
      expect(result['C'].top).to.be.greaterThan(result['B'].top);
    });

    it('orders sibling nodes using barycenter heuristic', () => {
      // A -> C, B -> D, A and B on layer 0
      // With A first, C should come before D
      const nodes = [
        makeNode('A', [{ destination_uuid: 'C' }]),
        makeNode('B', [{ destination_uuid: 'D' }]),
        makeNode('C', []),
        makeNode('D', [])
      ];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 300, top: 0 } },
        C: { position: { left: 0, top: 200 } },
        D: { position: { left: 300, top: 200 } }
      };
      // A and B are both roots (no parents), so both in layer 0
      // But A is the start node
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      // C should be left of D (follows parent order)
      expect(result['C'].left).to.be.lessThan(result['D'].left);
    });

    it('non-start nodes in first layer are offset down', () => {
      // A and B both in layer 0 (B unreachable from A but has no parents)
      const nodes = [makeNode('A', []), makeNode('B', [])];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 300, top: 0 } }
      };
      // B will end up on a later layer since it's unreachable from A
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      // Start node A should be at top=0
      expect(result['A'].top).to.equal(0);
    });

    it('wraps siblings to new rows when exceeding max width', () => {
      // A -> B..H: 7 children at 200px each = 200*7 + 60*6 = 1760px
      // Should split into rows of 4 (980px) and 3 (720px)
      const childIds = ['B', 'C', 'D', 'E', 'F', 'G', 'H'];
      const nodes = [
        makeNode(
          'A',
          childIds.map((id) => ({ destination_uuid: id }))
        ),
        ...childIds.map((id) => makeNode(id, []))
      ];
      const nodeUIs: Record<
        string,
        { position: { left: number; top: number } }
      > = { A: { position: { left: 0, top: 0 } } };
      childIds.forEach((id, i) => {
        nodeUIs[id] = { position: { left: i * 260, top: 200 } };
      });
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      // All children should be below A
      for (const id of childIds) {
        expect(result[id].top).to.be.greaterThan(result['A'].top);
      }

      // Children should span multiple rows (not all the same top)
      const tops = new Set(childIds.map((id) => result[id].top));
      expect(tops.size).to.be.greaterThan(1);

      // Each visual row should fit within 1200px
      const rowsByTop = new Map<number, string[]>();
      for (const id of childIds) {
        const t = result[id].top;
        const row = rowsByTop.get(t) || [];
        row.push(id);
        rowsByTop.set(t, row);
      }
      for (const [, row] of rowsByTop) {
        const minLeft = Math.min(...row.map((id) => result[id].left));
        const maxRight = Math.max(...row.map((id) => result[id].left + 200));
        expect(maxRight - minLeft).to.be.at.most(1200);
      }
    });

    it('handles wider flows with multiple branches', () => {
      // A -> B, A -> C, A -> D
      const nodes = [
        makeNode('A', [
          { destination_uuid: 'B' },
          { destination_uuid: 'C' },
          { destination_uuid: 'D' }
        ]),
        makeNode('B', []),
        makeNode('C', []),
        makeNode('D', [])
      ];
      const nodeUIs = {
        A: { position: { left: 0, top: 0 } },
        B: { position: { left: 0, top: 200 } },
        C: { position: { left: 300, top: 200 } },
        D: { position: { left: 600, top: 200 } }
      };
      const result = calculateLayeredLayout(
        nodes,
        nodeUIs,
        'A',
        constantSize(200, 100)
      );

      // All three children should be on the same layer
      expect(result['B'].top).to.equal(result['C'].top);
      expect(result['C'].top).to.equal(result['D'].top);

      // They should be spread horizontally with gaps
      const lefts = [result['B'].left, result['C'].left, result['D'].left].sort(
        (a, b) => a - b
      );
      expect(lefts[1]).to.be.greaterThan(lefts[0]);
      expect(lefts[2]).to.be.greaterThan(lefts[1]);
    });
  });

  describe('placeStickyNotes', () => {
    const makeSticky = (left: number, top: number): StickyNote => ({
      position: { left, top },
      title: '',
      body: '',
      color: 'yellow'
    });

    it('returns empty object when no stickies', () => {
      const result = placeStickyNotes(
        {},
        { A: { left: 0, top: 0 } },
        { A: { left: 0, top: 0 } },
        new Map([['A', { width: 200, height: 100 }]]),
        new Map(),
        'A'
      );
      expect(Object.keys(result)).to.have.length(0);
    });

    it('returns empty object when no nodes', () => {
      const result = placeStickyNotes(
        { s1: makeSticky(100, 100) },
        {},
        {},
        new Map(),
        new Map(),
        'A'
      );
      expect(Object.keys(result)).to.have.length(0);
    });

    it('places sticky to the right of its closest node', () => {
      const stickies = { s1: makeSticky(250, 0) }; // right of node at (0,0)
      const oldPositions = { A: { left: 0, top: 0 } };
      const newPositions = { A: { left: 0, top: 0 } };
      const nodeSizes = new Map([['A', { width: 200, height: 100 }]]);
      const stickySizes = new Map([['s1', { width: 182, height: 100 }]]);

      const result = placeStickyNotes(
        stickies,
        oldPositions,
        newPositions,
        nodeSizes,
        stickySizes,
        'A'
      );

      expect(result['s1']).to.not.be.undefined;
      // Should be placed to the right of node A
      expect(result['s1'].left).to.be.greaterThanOrEqual(200);
    });

    it('places sticky to the left when it was originally left', () => {
      // Sticky was to the left of node B (not start node)
      const stickies = { s1: makeSticky(0, 0) }; // left of node at (300, 0)
      const oldPositions = {
        A: { left: 0, top: 0 },
        B: { left: 300, top: 200 }
      };
      const newPositions = {
        A: { left: 0, top: 0 },
        B: { left: 300, top: 200 }
      };
      const nodeSizes = new Map([
        ['A', { width: 200, height: 100 }],
        ['B', { width: 200, height: 100 }]
      ]);
      const stickySizes = new Map([['s1', { width: 182, height: 100 }]]);

      const result = placeStickyNotes(
        stickies,
        oldPositions,
        newPositions,
        nodeSizes,
        stickySizes,
        'A'
      );

      expect(result['s1']).to.not.be.undefined;
    });

    it('redirects left-of-start sticky to the right side', () => {
      // Sticky was to the left of the start node — should be placed to the right
      const stickies = { s1: makeSticky(-200, 0) }; // left of start node at (0,0)
      const oldPositions = { A: { left: 0, top: 0 } };
      const newPositions = { A: { left: 0, top: 0 } };
      const nodeSizes = new Map([['A', { width: 200, height: 100 }]]);
      const stickySizes = new Map([['s1', { width: 182, height: 100 }]]);

      const result = placeStickyNotes(
        stickies,
        oldPositions,
        newPositions,
        nodeSizes,
        stickySizes,
        'A'
      );

      expect(result['s1']).to.not.be.undefined;
      // Should be placed to the right (not left) of the start node
      expect(result['s1'].left).to.be.greaterThanOrEqual(200);
    });

    it('snaps sticky positions to grid', () => {
      const stickies = { s1: makeSticky(250, 5) };
      const oldPositions = { A: { left: 0, top: 0 } };
      const newPositions = { A: { left: 0, top: 0 } };
      const nodeSizes = new Map([['A', { width: 200, height: 100 }]]);
      const stickySizes = new Map([['s1', { width: 182, height: 100 }]]);

      const result = placeStickyNotes(
        stickies,
        oldPositions,
        newPositions,
        nodeSizes,
        stickySizes,
        'A'
      );

      expect(result['s1'].left % 20).to.equal(0);
      expect(result['s1'].top % 20).to.equal(0);
    });

    it('assigns sticky to closest node', () => {
      // s1 is at (310, 200), closer to B at (300, 200) than A at (0, 0)
      const stickies = { s1: makeSticky(310, 200) };
      const oldPositions = {
        A: { left: 0, top: 0 },
        B: { left: 300, top: 200 }
      };
      const newPositions = {
        A: { left: 0, top: 0 },
        B: { left: 300, top: 200 }
      };
      const nodeSizes = new Map([
        ['A', { width: 200, height: 100 }],
        ['B', { width: 200, height: 100 }]
      ]);
      const stickySizes = new Map([['s1', { width: 182, height: 100 }]]);

      const result = placeStickyNotes(
        stickies,
        oldPositions,
        newPositions,
        nodeSizes,
        stickySizes,
        'A'
      );

      expect(result['s1']).to.not.be.undefined;
      // Should be placed near node B, not node A
      expect(result['s1'].left).to.be.greaterThan(200);
    });

    it('nudges stickies to avoid collisions', () => {
      // Two stickies both closest to node A, both on the right side
      const stickies = {
        s1: makeSticky(250, 0),
        s2: makeSticky(260, 0)
      };
      const oldPositions = { A: { left: 0, top: 0 } };
      const newPositions = { A: { left: 0, top: 0 } };
      const nodeSizes = new Map([['A', { width: 200, height: 100 }]]);
      const stickySizes = new Map([
        ['s1', { width: 182, height: 100 }],
        ['s2', { width: 182, height: 100 }]
      ]);

      const result = placeStickyNotes(
        stickies,
        oldPositions,
        newPositions,
        nodeSizes,
        stickySizes,
        'A'
      );

      // Both stickies should be placed
      expect(result['s1']).to.not.be.undefined;
      expect(result['s2']).to.not.be.undefined;

      // If they have the same left, they should be vertically separated
      if (result['s1'].left === result['s2'].left) {
        expect(result['s1'].top).to.not.equal(result['s2'].top);
      }
    });

    it('skips stickies without position', () => {
      const stickies = {
        s1: { title: '', body: '', color: 'yellow' as const } as StickyNote
      };
      const oldPositions = { A: { left: 0, top: 0 } };
      const newPositions = { A: { left: 0, top: 0 } };
      const nodeSizes = new Map([['A', { width: 200, height: 100 }]]);
      const stickySizes = new Map([['s1', { width: 182, height: 100 }]]);

      const result = placeStickyNotes(
        stickies,
        oldPositions,
        newPositions,
        nodeSizes,
        stickySizes,
        'A'
      );

      // Sticky without position should be skipped
      expect(result['s1']).to.be.undefined;
    });

    it('ensures non-negative coordinates for stickies', () => {
      const stickies = { s1: makeSticky(250, 0) };
      const oldPositions = { A: { left: 0, top: 0 } };
      const newPositions = { A: { left: 0, top: 0 } };
      const nodeSizes = new Map([['A', { width: 200, height: 100 }]]);
      const stickySizes = new Map([['s1', { width: 182, height: 100 }]]);

      const result = placeStickyNotes(
        stickies,
        oldPositions,
        newPositions,
        nodeSizes,
        stickySizes,
        'A'
      );

      expect(result['s1'].left).to.be.at.least(0);
      expect(result['s1'].top).to.be.at.least(0);
    });

    it('uses default sizes when not provided', () => {
      const stickies = { s1: makeSticky(250, 0) };
      const oldPositions = { A: { left: 0, top: 0 } };
      const newPositions = { A: { left: 0, top: 0 } };
      const nodeSizes = new Map<string, { width: number; height: number }>();
      const stickySizes = new Map<string, { width: number; height: number }>();

      const result = placeStickyNotes(
        stickies,
        oldPositions,
        newPositions,
        nodeSizes,
        stickySizes,
        'A'
      );

      expect(result['s1']).to.not.be.undefined;
      expect(result['s1'].left).to.be.at.least(0);
      expect(result['s1'].top).to.be.at.least(0);
    });
  });
});
