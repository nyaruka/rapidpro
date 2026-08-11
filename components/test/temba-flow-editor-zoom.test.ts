import { expect } from '@open-wc/testing';
import { Editor } from '../src/flow/Editor';
import { IssuesWindow } from '../src/flow/IssuesWindow';
import { RevisionsWindow } from '../src/flow/RevisionsWindow';
import { stub, restore, spy } from 'sinon';
import { getCookie, setCookie } from '../src/utils';

customElements.define('temba-flow-editor-zoom', Editor);
if (!customElements.get('temba-issues-window')) {
  customElements.define('temba-issues-window', IssuesWindow);
}
if (!customElements.get('temba-revisions-window')) {
  customElements.define('temba-revisions-window', RevisionsWindow);
}

/** Create an Editor instance with a mock plumber, suitable for unit-testing
 *  zoom methods without needing a full flow definition. */
const createEditorWithMockPlumber = (): Editor => {
  const editor = new Editor();
  (editor as any).plumber = {
    zoom: 1,
    repaintEverything: stub()
  };
  return editor;
};

describe('Editor Zoom', () => {
  beforeEach(() => {
    restore();
  });

  afterEach(() => {
    restore();
  });

  // --- A. setZoom state management ---

  describe('setZoom', () => {
    it('clamps to minimum of 0.3', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;
      (editor as any).zoomManager.setZoom(0.02);
      expect((editor as any).zoom).to.equal(0.3);
    });

    it('clamps to maximum of 1.0', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;
      (editor as any).zoomManager.setZoom(1.5);
      expect((editor as any).zoom).to.equal(1.0);
    });

    it('rounds to 2 decimal places', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;
      (editor as any).zoomManager.setZoom(0.333);
      expect((editor as any).zoom).to.equal(0.33);
    });

    it('rounds 0.555 to 0.56', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;
      (editor as any).zoomManager.setZoom(0.555);
      expect((editor as any).zoom).to.equal(0.56);
    });

    it('is a no-op when clamped value equals current zoom', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;
      const rafSpy = spy(window, 'requestAnimationFrame');
      (editor as any).zoomManager.setZoom(0.5);
      expect((editor as any).zoom).to.equal(0.5);
      expect(rafSpy).to.not.have.been.called;
      rafSpy.restore();
    });

    it('syncs plumber.zoom', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;
      (editor as any).zoomManager.setZoom(0.75);
      expect((editor as any).plumber.zoom).to.equal(0.75);
    });

    it('clears zoomFitted flag', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;
      (editor as any).zoomManager.zoomFitted = true;
      (editor as any).zoomManager.setZoom(0.8);
      expect((editor as any).zoomManager.isZoomFitted).to.be.false;
    });

    it('preserves viewport center point when center is provided', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 1.0;

      // Create mock #editor element with known geometry
      const mockEditor = {
        scrollLeft: 100,
        scrollTop: 200,
        getBoundingClientRect: () => ({
          left: 50,
          top: 50,
          width: 800,
          height: 600
        })
      };
      stub(editor, 'querySelector').returns(mockEditor as any);

      // Stub rAF to invoke callback synchronously
      const rafStub = stub(window, 'requestAnimationFrame').callsFake(
        (cb: FrameRequestCallback) => {
          cb(0);
          return 0;
        }
      );

      const center = { clientX: 450, clientY: 350 };
      (editor as any).zoomManager.setZoom(0.5, center);

      // Verify scroll math:
      // ox = 450 - 50 = 400, oy = 350 - 50 = 300
      // cx = (100 + 400) / 1.0 = 500, cy = (200 + 300) / 1.0 = 500
      // newScrollLeft = 500 * 0.5 - 400 = -150
      // newScrollTop  = 500 * 0.5 - 300 = -50
      expect(mockEditor.scrollLeft).to.equal(-150);
      expect(mockEditor.scrollTop).to.equal(-50);

      rafStub.restore();
    });
  });

  // --- B. Convenience methods ---

  describe('zoomIn', () => {
    it('increments zoom by 0.05', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;
      (editor as any).zoomManager.zoomIn();
      expect((editor as any).zoom).to.equal(0.55);
    });

    it('stays at 1.0 when already at maximum', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 1.0;
      (editor as any).zoomManager.zoomIn();
      expect((editor as any).zoom).to.equal(1.0);
    });
  });

  describe('zoomOut', () => {
    it('decrements zoom by 0.05', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;
      (editor as any).zoomManager.zoomOut();
      expect((editor as any).zoom).to.equal(0.45);
    });

    it('stays at 0.3 when already at minimum', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.3;
      (editor as any).zoomManager.zoomOut();
      expect((editor as any).zoom).to.equal(0.3);
    });
  });

  describe('zoomToFull', () => {
    it('resets zoom to 1.0', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.4;
      (editor as any).zoomManager.zoomToFull();
      expect((editor as any).zoom).to.equal(1.0);
    });
  });

  // --- C. zoomToFit ---

  describe('zoomToFit', () => {
    it('returns early when no definition', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).definition = null;
      (editor as any).zoomManager.zoomToFit();
      expect((editor as any).zoom).to.equal(1.0);
    });

    it('returns early when definition has zero nodes', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).definition = { nodes: [], _ui: { nodes: {} } };
      (editor as any).zoomManager.zoomToFit();
      expect((editor as any).zoom).to.equal(1.0);
    });

    it('sets zoomFitted to true', () => {
      const editor = createEditorWithMockPlumber();

      // Create mock definition with nodes spread wide enough for zoom < 1.0
      const node1uuid = 'node-1-uuid';
      const node2uuid = 'node-2-uuid';
      (editor as any).definition = {
        nodes: [{ uuid: node1uuid }, { uuid: node2uuid }],
        _ui: {
          nodes: {
            [node1uuid]: { position: { left: 0, top: 0 } },
            [node2uuid]: { position: { left: 2000, top: 1500 } }
          },
          stickies: {}
        }
      };

      // Create mock node elements
      const el1 = document.createElement('div');
      el1.id = node1uuid;
      el1.style.width = '200px';
      el1.style.height = '100px';
      document.body.appendChild(el1);

      const el2 = document.createElement('div');
      el2.id = node2uuid;
      el2.style.width = '200px';
      el2.style.height = '100px';
      document.body.appendChild(el2);

      // Create mock #editor element
      const mockEditor = document.createElement('div');
      mockEditor.id = 'mock-editor-for-zoom';
      Object.defineProperty(mockEditor, 'clientWidth', { value: 800 });
      Object.defineProperty(mockEditor, 'clientHeight', { value: 600 });
      mockEditor.scrollLeft = 0;
      mockEditor.scrollTop = 0;

      stub(editor, 'querySelector').callsFake((selector: string) => {
        if (selector === '#editor') return mockEditor;
        if (selector.includes(node1uuid)) return el1;
        if (selector.includes(node2uuid)) return el2;
        return null;
      });

      stub(window, 'requestAnimationFrame').callsFake(
        (cb: FrameRequestCallback) => {
          cb(0);
          return 0;
        }
      );

      (editor as any).zoomManager.zoomToFit();
      expect((editor as any).zoomManager.isZoomFitted).to.be.true;

      el1.remove();
      el2.remove();
    });

    it('caps zoom at 1.0 when nodes fit easily', () => {
      const editor = createEditorWithMockPlumber();

      // Tiny content that fits easily
      const nodeUuid = 'small-node';
      (editor as any).definition = {
        nodes: [{ uuid: nodeUuid }],
        _ui: {
          nodes: {
            [nodeUuid]: { position: { left: 100, top: 100 } }
          },
          stickies: {}
        }
      };

      const el = document.createElement('div');
      el.id = nodeUuid;
      el.style.width = '50px';
      el.style.height = '30px';
      document.body.appendChild(el);

      const mockEditor = document.createElement('div');
      Object.defineProperty(mockEditor, 'clientWidth', { value: 800 });
      Object.defineProperty(mockEditor, 'clientHeight', { value: 600 });
      mockEditor.scrollLeft = 0;
      mockEditor.scrollTop = 0;

      stub(editor, 'querySelector').callsFake((selector: string) => {
        if (selector === '#editor') return mockEditor;
        if (selector.includes(nodeUuid)) return el;
        return null;
      });

      stub(window, 'requestAnimationFrame').callsFake(
        (cb: FrameRequestCallback) => {
          cb(0);
          return 0;
        }
      );

      (editor as any).zoomManager.zoomToFit();
      expect((editor as any).zoom).to.equal(1.0);

      el.remove();
    });

    it('rounds zoom to nearest 0.05', () => {
      const editor = createEditorWithMockPlumber();

      // Create nodes that produce a zoom that's not a multiple of 0.05
      const node1uuid = 'fit-node-1';
      const node2uuid = 'fit-node-2';
      (editor as any).definition = {
        nodes: [{ uuid: node1uuid }, { uuid: node2uuid }],
        _ui: {
          nodes: {
            [node1uuid]: { position: { left: 0, top: 0 } },
            [node2uuid]: { position: { left: 3000, top: 2000 } }
          },
          stickies: {}
        }
      };

      const el1 = document.createElement('div');
      el1.id = node1uuid;
      el1.style.width = '200px';
      el1.style.height = '100px';
      document.body.appendChild(el1);

      const el2 = document.createElement('div');
      el2.id = node2uuid;
      el2.style.width = '200px';
      el2.style.height = '100px';
      document.body.appendChild(el2);

      const mockEditor = document.createElement('div');
      Object.defineProperty(mockEditor, 'clientWidth', { value: 800 });
      Object.defineProperty(mockEditor, 'clientHeight', { value: 600 });
      mockEditor.scrollLeft = 0;
      mockEditor.scrollTop = 0;

      stub(editor, 'querySelector').callsFake((selector: string) => {
        if (selector === '#editor') return mockEditor;
        if (selector.includes(node1uuid)) return el1;
        if (selector.includes(node2uuid)) return el2;
        return null;
      });

      stub(window, 'requestAnimationFrame').callsFake(
        (cb: FrameRequestCallback) => {
          cb(0);
          return 0;
        }
      );

      (editor as any).zoomManager.zoomToFit();

      const zoom = (editor as any).zoom;
      // Zoom should be a multiple of 0.05 (within float tolerance)
      const remainder = Math.round((zoom % 0.05) * 1000) / 1000;
      expect(remainder === 0 || remainder === 0.05).to.be.true;

      el1.remove();
      el2.remove();
    });
  });

  // --- D. handleWheel ---

  describe('handleWheel', () => {
    it('ignores non-ctrl/meta scroll', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;

      const event = new WheelEvent('wheel', {
        deltaY: 100,
        clientX: 400,
        clientY: 300
      });

      (editor as any).zoomManager.handleWheel(event);
      expect((editor as any).zoom).to.equal(0.5);
    });

    it('zooms out by 0.05 on Ctrl+scroll-down', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;

      // Stub querySelector for setZoom's editor lookup
      stub(editor, 'querySelector').returns(null);

      const event = new WheelEvent('wheel', {
        ctrlKey: true,
        deltaY: 100,
        clientX: 400,
        clientY: 300
      });

      (editor as any).zoomManager.handleWheel(event);
      expect((editor as any).zoom).to.equal(0.45);
    });

    it('zooms in by 0.05 on Meta+scroll-up', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;

      stub(editor, 'querySelector').returns(null);

      const event = new WheelEvent('wheel', {
        metaKey: true,
        deltaY: -100,
        clientX: 400,
        clientY: 300
      });

      (editor as any).zoomManager.handleWheel(event);
      expect((editor as any).zoom).to.equal(0.55);
    });

    it('calls preventDefault on ctrl/meta wheel events', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;

      stub(editor, 'querySelector').returns(null);

      const event = new WheelEvent('wheel', {
        ctrlKey: true,
        deltaY: 100,
        clientX: 400,
        clientY: 300,
        cancelable: true
      });

      const preventDefaultSpy = spy(event, 'preventDefault');
      (editor as any).zoomManager.handleWheel(event);
      expect(preventDefaultSpy).to.have.been.calledOnce;
    });
  });

  // --- E. Coordinate conversions ---

  describe('coordinate conversions', () => {
    it('handleCanvasContextMenu divides by zoom', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;
      (editor as any).viewingRevision = null;
      (editor as any).isTranslating = false;
      (editor as any).definition = { nodes: [{ uuid: 'n' }] };

      // Track the canvas-space position passed to canvasMenu.show
      // show() is called with: (clientX, clientY, {x: snappedLeft, y: snappedTop}, true, hasNodes)
      let capturedPosition: any = null;
      const mockCanvasMenu = {
        show: (
          _clientX: number,
          _clientY: number,
          position: any,
          ..._rest: any[]
        ) => {
          capturedPosition = position;
        }
      };

      const mockCanvas = {
        getBoundingClientRect: () => ({
          left: 0,
          top: 0,
          width: 1000,
          height: 800
        })
      };

      stub(editor, 'querySelector').callsFake(((selector: string) => {
        if (selector === '#canvas') return mockCanvas;
        if (selector === 'temba-canvas-menu') return mockCanvasMenu;
        return null;
      }) as any);

      const event = {
        clientX: 200,
        clientY: 300,
        target: { id: 'canvas' },
        preventDefault: stub(),
        stopPropagation: stub()
      };

      (editor as any).handleCanvasContextMenu(event);

      // relativeX = (200 - 0) / 0.5 - 10 = 390, snapped to grid(20): 400
      // relativeY = (300 - 0) / 0.5 - 10 = 590, snapped to grid(20): 600
      expect(capturedPosition).to.not.be.null;
      expect(capturedPosition.x).to.equal(400);
      expect(capturedPosition.y).to.equal(600);
    });

    it('calculateCanvasDropPosition divides by zoom', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;

      const mockCanvas = {
        getBoundingClientRect: () => ({
          left: 0,
          top: 0,
          width: 1000,
          height: 800
        })
      };

      stub(editor, 'querySelector').callsFake(((selector: string) => {
        if (selector === '#canvas') return mockCanvas;
        return null;
      }) as any);

      // DROP_PREVIEW_OFFSET_X = 20, DROP_PREVIEW_OFFSET_Y = 20
      const pos = (editor as any).calculateCanvasDropPosition(200, 300, true);

      // left = (200 - 0) / 0.5 - 20 = 380, snapped: 380
      // top  = (300 - 0) / 0.5 - 20 = 580, snapped: 580
      expect(pos.left).to.equal(380);
      expect(pos.top).to.equal(580);
    });

    it('focusNode multiplies by zoom for scroll position', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;

      const mockNode = {
        offsetLeft: 200,
        offsetTop: 300,
        offsetWidth: 100,
        offsetHeight: 60
      };

      let scrollToArgs: any = null;
      const mockEditor = {
        getBoundingClientRect: () => ({
          width: 800,
          height: 600,
          left: 0,
          top: 0
        }),
        scrollTo: (args: any) => {
          scrollToArgs = args;
        }
      };

      stub(editor, 'querySelector').callsFake(((selector: string) => {
        if (selector.includes('temba-flow-node')) return mockNode;
        if (selector === '#editor') return mockEditor;
        return null;
      }) as any);

      editor.focusNode('test-uuid');

      // nodeCenterX = 200 + 50 = 250, nodeCenterY = 300 + 30 = 330
      // targetScrollX = 250 * 0.5 - 400 = -275 -> max(0, -275) = 0
      // targetScrollY = 330 * 0.5 - 300 = -135 -> max(0, -135) = 0
      expect(scrollToArgs).to.not.be.null;
      expect(scrollToArgs.left).to.equal(0);
      expect(scrollToArgs.top).to.equal(0);
    });

    it('focusNode scroll positions scale with zoom for distant nodes', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).zoom = 0.5;

      const mockNode = {
        offsetLeft: 2000,
        offsetTop: 1500,
        offsetWidth: 200,
        offsetHeight: 100
      };

      let scrollToArgs: any = null;
      const mockEditor = {
        getBoundingClientRect: () => ({
          width: 800,
          height: 600,
          left: 0,
          top: 0
        }),
        scrollTo: (args: any) => {
          scrollToArgs = args;
        }
      };

      stub(editor, 'querySelector').callsFake(((selector: string) => {
        if (selector.includes('temba-flow-node')) return mockNode;
        if (selector === '#editor') return mockEditor;
        return null;
      }) as any);

      editor.focusNode('distant-node');

      // nodeCenterX = 2000 + 100 = 2100, nodeCenterY = 1500 + 50 = 1550
      // targetScrollX = 2100 * 0.5 - 400 = 650
      // targetScrollY = 1550 * 0.5 - 300 = 475
      expect(scrollToArgs.left).to.equal(650);
      expect(scrollToArgs.top).to.equal(475);
    });
  });

  // --- F. Zoom persistence via flow-settings cookie ---

  describe('zoom persistence', () => {
    beforeEach(() => {
      setCookie('flow-settings', '{}');
    });

    afterEach(() => {
      setCookie('flow-settings', '{}');
    });

    it('saves zoom to flow-settings cookie on setZoom', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).flow = 'flow-abc';
      (editor as any).zoom = 0.5;
      stub(editor, 'querySelector').returns(null);

      (editor as any).zoomManager.setZoom(0.75);

      const settings = JSON.parse(getCookie('flow-settings') || '{}');
      expect(settings['flow-abc']).to.exist;
      expect(settings['flow-abc'].zoom).to.equal(0.75);
    });

    it('saves zoom to flow-settings cookie on zoomToFit', () => {
      const editor = createEditorWithMockPlumber();
      (editor as any).flow = 'flow-def';

      const nodeUuid = 'fit-persist-node';
      (editor as any).definition = {
        nodes: [{ uuid: nodeUuid }],
        _ui: {
          nodes: {
            [nodeUuid]: { position: { left: 0, top: 0 } }
          },
          stickies: {}
        }
      };

      const el = document.createElement('div');
      el.id = nodeUuid;
      el.style.width = '50px';
      el.style.height = '30px';
      document.body.appendChild(el);

      const mockEditor = document.createElement('div');
      Object.defineProperty(mockEditor, 'clientWidth', { value: 800 });
      Object.defineProperty(mockEditor, 'clientHeight', { value: 600 });
      mockEditor.scrollLeft = 0;
      mockEditor.scrollTop = 0;

      stub(editor, 'querySelector').callsFake((selector: string) => {
        if (selector === '#editor') return mockEditor;
        if (selector.includes(nodeUuid)) return el;
        return null;
      });

      stub(window, 'requestAnimationFrame').callsFake(
        (cb: FrameRequestCallback) => {
          cb(0);
          return 0;
        }
      );

      (editor as any).zoomManager.zoomToFit();

      const settings = JSON.parse(getCookie('flow-settings') || '{}');
      expect(settings['flow-def']).to.exist;
      expect(settings['flow-def'].zoom).to.be.a('number');

      el.remove();
    });

    it('restores zoom from cookie on initial definition load', () => {
      setCookie(
        'flow-settings',
        JSON.stringify({ 'flow-ghi': { zoom: 0.65 } })
      );

      const editor = createEditorWithMockPlumber();
      (editor as any).flow = 'flow-ghi';

      // Simulate initial definition load: previous value is undefined
      const changes = new Map();
      changes.set('definition', undefined);
      (editor as any).definition = { uuid: 'flow-ghi', nodes: [] };
      (editor as any).willUpdate(changes);

      expect((editor as any).zoom).to.equal(0.65);
      expect((editor as any).plumber.zoom).to.equal(0.65);
    });

    it('clamps invalid zoom values from cookie', () => {
      setCookie('flow-settings', JSON.stringify({ 'flow-jkl': { zoom: 5.0 } }));

      const editor = createEditorWithMockPlumber();
      (editor as any).flow = 'flow-jkl';

      const changes = new Map();
      changes.set('definition', undefined);
      (editor as any).definition = { uuid: 'flow-jkl', nodes: [] };
      (editor as any).willUpdate(changes);

      expect((editor as any).zoom).to.equal(1.0);
    });

    it('ignores non-numeric zoom values from cookie', () => {
      setCookie(
        'flow-settings',
        JSON.stringify({ 'flow-mno': { zoom: 'bad' } })
      );

      const editor = createEditorWithMockPlumber();
      (editor as any).flow = 'flow-mno';
      (editor as any).zoom = 1.0;

      const changes = new Map();
      changes.set('definition', undefined);
      (editor as any).definition = { uuid: 'flow-mno', nodes: [] };
      (editor as any).willUpdate(changes);

      // zoom should remain at default since 'bad' is not a number
      expect((editor as any).zoom).to.equal(1.0);
    });

    it('evicts oldest entries when exceeding max flow settings', () => {
      // Fill up the settings to the max
      const settings: Record<string, any> = {};
      for (let i = 0; i < Editor.MAX_FLOW_SETTINGS; i++) {
        settings[`old-flow-${i}`] = { zoom: 0.5 };
      }
      setCookie('flow-settings', JSON.stringify(settings));

      const editor = createEditorWithMockPlumber();
      (editor as any).flow = 'new-flow';
      (editor as any).zoom = 0.5;
      stub(editor, 'querySelector').returns(null);

      (editor as any).zoomManager.setZoom(0.8);

      const result = JSON.parse(getCookie('flow-settings') || '{}');
      const keys = Object.keys(result);

      expect(keys.length).to.equal(Editor.MAX_FLOW_SETTINGS);
      expect(result['new-flow']).to.exist;
      expect(result['new-flow'].zoom).to.equal(0.8);
      // oldest entry should have been evicted
      expect(result['old-flow-0']).to.not.exist;
    });
  });
});
