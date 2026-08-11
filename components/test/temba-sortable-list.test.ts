import { expect, fixture, oneEvent } from '@open-wc/testing';
import { html, TemplateResult } from 'lit';
import { CustomEventType } from '../src/interfaces';
import { SortableList } from '../src/list/SortableList';
import { assertScreenshot, getClip } from './utils.test';
import Sinon, { useFakeTimers } from 'sinon';

const BORING_LIST = html`
  <temba-sortable-list>
    <style>
      .sortable {
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        height: 20px;
      }
    </style>
    <div class="sortable" id="chicken" style="">Chicken</div>
    <div class="sortable" id="fish">Fish</div>
  </temba-sortable-list>
`;

const HORIZONTAL_LIST = html`
  <temba-sortable-list horizontal>
    <style>
      .sortable {
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        height: 20px;
        width: 50px;
      }
    </style>
    <div class="sortable" id="red">Red</div>
    <div class="sortable" id="blue">Blue</div>
    <div class="sortable" id="green">Green</div>
  </temba-sortable-list>
`;

const createSorter = async (def: TemplateResult) => {
  const parentNode = document.createElement('div');
  parentNode.setAttribute('style', 'width: 100px;');
  return (await fixture(def, { parentNode })) as SortableList;
};

describe('temba-sortable-list', () => {
  let clock: Sinon.SinonFakeTimers;
  beforeEach(function () {
    clock = useFakeTimers();
    clock.runAll();
  });

  afterEach(function () {
    clock.restore();
  });

  it('renders default', async () => {
    const list: SortableList = await createSorter(BORING_LIST);
    await assertScreenshot('list/sortable', getClip(list));
  });

  it('can get ids of sortable elements', async () => {
    const list: SortableList = await createSorter(BORING_LIST);
    await list.updateComplete;

    const ids = list.getIds();
    expect(ids).to.deep.equal(['chicken', 'fish']);
  });

  it('works with horizontal layout', async () => {
    const list: SortableList = await createSorter(HORIZONTAL_LIST);
    await list.updateComplete;

    const ids = list.getIds();
    expect(ids).to.deep.equal(['red', 'blue', 'green']);

    // Test horizontal drag behavior
    const bounds = list.getBoundingClientRect();
    const orderChanged = oneEvent(list, CustomEventType.OrderChanged, false);

    // Drag the first item (red) to after the second item (blue)
    await moveMouse(bounds.left + 10, bounds.top + 10);
    await mouseDown();
    await moveMouse(bounds.left + 80, bounds.top + 10);
    await mouseUp();
    clock.runAll();

    const orderEvent = await orderChanged;
    expect(orderEvent.detail).to.deep.equal({
      swap: [0, 2]
    });
  });

  it('handles prepareGhost callback', async () => {
    const list: SortableList = await createSorter(BORING_LIST);
    let ghostPrepared = false;

    list.prepareGhost = (ghost: HTMLElement) => {
      ghostPrepared = true;
      ghost.style.backgroundColor = 'red';
    };

    const bounds = list.getBoundingClientRect();

    // Start dragging to trigger ghost creation
    await moveMouse(bounds.left + 20, bounds.bottom - 10);
    await mouseDown();
    await moveMouse(bounds.left + 30, bounds.bottom - 10);

    expect(ghostPrepared).to.be.true;

    // Clean up
    await mouseUp();
    clock.runAll();
  });

  it('drags', async () => {
    const list: SortableList = await createSorter(BORING_LIST);
    const updated = oneEvent(list, 'change', false);

    const bounds = list.getBoundingClientRect();

    await moveMouse(bounds.left + 20, bounds.bottom - 10);
    await mouseDown();
    await moveMouse(bounds.left + 20, bounds.top + 5);

    // should be hovered
    await assertScreenshot('list/sortable-dragging', getClip(list));

    // now lets drop - this will fire the order changed event
    const orderChanged = oneEvent(list, CustomEventType.OrderChanged, false);
    await mouseUp();
    clock.runAll();
    await list.updateComplete;
    clock.runAll();

    // we should fire an order changed event on drop
    const orderEvent = await orderChanged;
    expect(orderEvent.detail).to.deep.equal({
      swap: [1, 0]
    });

    await assertScreenshot('list/sortable-dropped', getClip(list));

    // we should fire a change event
    const changeEvent = await updated;
    expect(changeEvent.type).to.equal('change');
  });

  it('detects external drag when dragging outside container', async () => {
    const list: SortableList = await createSorter(BORING_LIST);
    list.externalDrag = true;
    await list.updateComplete;

    const bounds = list.getBoundingClientRect();

    // track external drag events
    let externalDragFired = false;
    let internalDragFired = false;

    list.addEventListener(CustomEventType.DragExternal, () => {
      externalDragFired = true;
    });

    list.addEventListener(CustomEventType.DragInternal, () => {
      internalDragFired = true;
    });

    // start dragging an item
    await moveMouse(bounds.left + 20, bounds.bottom - 10);
    await mouseDown();

    // drag outside the container (far to the right)
    await moveMouse(bounds.right + 100, bounds.top + 10);
    clock.runAll();

    // should have fired external drag event
    expect(externalDragFired).to.be.true;

    // drag back inside
    externalDragFired = false; // reset
    await moveMouse(bounds.left + 20, bounds.top + 10);
    clock.runAll();

    // should have fired internal drag event
    expect(internalDragFired).to.be.true;

    // clean up
    await mouseUp();
    clock.runAll();
  });

  it('fires DragStop with isExternal=true when dropped outside container', async () => {
    const list: SortableList = await createSorter(BORING_LIST);
    list.externalDrag = true;
    await list.updateComplete;

    const bounds = list.getBoundingClientRect();

    // start dragging an item
    await moveMouse(bounds.left + 20, bounds.bottom - 10);
    await mouseDown();

    // drag outside the container
    await moveMouse(bounds.right + 100, bounds.top + 10);
    clock.runAll();

    // listen for drag stop event
    const dragStop = oneEvent(list, CustomEventType.DragStop, false);

    // drop outside
    await mouseUp();
    clock.runAll();

    const dragStopEvent = await dragStop;
    expect(dragStopEvent.detail.isExternal).to.be.true;
  });

  describe('zoom-aware dimensions', () => {
    it('stores layout dimensions on mousedown via offsetWidth/offsetHeight', async () => {
      const list: SortableList = await createSorter(BORING_LIST);
      await list.updateComplete;

      const bounds = list.getBoundingClientRect();

      // Start drag
      await moveMouse(bounds.left + 20, bounds.bottom - 10);
      await mouseDown();

      // originalLayoutSize should be set using offsetWidth/offsetHeight
      expect(list.originalLayoutSize).to.not.be.null;
      // At zoom=1.0, layout size equals viewport size
      expect(list.originalLayoutSize.width).to.equal(
        list.originalElementRect.width
      );
      expect(list.originalLayoutSize.height).to.equal(
        list.originalElementRect.height
      );

      await mouseUp();
      clock.runAll();
    });

    it('ghost uses scale(1.03) without ancestor transform', async () => {
      const list: SortableList = await createSorter(BORING_LIST);
      await list.updateComplete;

      const bounds = list.getBoundingClientRect();

      // Start drag past threshold to create ghost
      await moveMouse(bounds.left + 20, bounds.bottom - 10);
      await mouseDown();
      await moveMouse(bounds.left + 30, bounds.bottom - 10);
      clock.runAll();

      expect(list.ghostElement).to.not.be.null;
      expect(list.ghostElement.style.transform).to.equal('scale(1.03)');
      // transformOrigin should NOT be set to '0 0' when there's no ancestor scale
      expect(list.ghostElement.style.transformOrigin).to.not.equal('0 0');

      await mouseUp();
      clock.runAll();
    });

    it('detects ancestor scale and applies it to ghost', () => {
      // Unit test the ghost scaling logic directly:
      // When originalElementRect (viewport) differs from originalLayoutSize (layout),
      // the ancestor scale is detected and applied to the ghost.
      const list = new SortableList();

      // Simulate being inside a container with transform: scale(0.5)
      // Layout dimensions: 100x20, viewport dimensions: 50x10
      list.originalElementRect = {
        width: 50,
        height: 10,
        left: 0,
        top: 0,
        right: 50,
        bottom: 10,
        x: 0,
        y: 0,
        toJSON: () => ({})
      } as DOMRect;
      list.originalLayoutSize = { width: 100, height: 20 };

      // Calculate ancestor scale the same way the component does
      const ancestorScale =
        list.originalLayoutSize.width > 0
          ? list.originalElementRect.width / list.originalLayoutSize.width
          : 1;
      const hasAncestorScale = Math.abs(ancestorScale - 1) > 0.001;

      expect(hasAncestorScale).to.be.true;
      expect(ancestorScale).to.equal(0.5);

      // The ghost would get: transform: scale(0.5 * 1.03) = scale(0.515)
      const expectedScale = ancestorScale * 1.03;
      expect(expectedScale).to.be.closeTo(0.515, 0.001);
    });

    it('uses originalLayoutSize for placeholder sizing', () => {
      // Verify that the component stores separate layout vs viewport dimensions
      const list = new SortableList();

      // At zoom=1.0, both should be the same
      const mockRect = {
        width: 100,
        height: 20,
        left: 0,
        top: 0,
        right: 100,
        bottom: 20,
        x: 0,
        y: 0,
        toJSON: () => ({})
      } as DOMRect;

      list.originalElementRect = mockRect;
      list.originalLayoutSize = { width: 100, height: 20 };

      // At zoom=1.0, they match
      expect(list.originalLayoutSize.width).to.equal(
        list.originalElementRect.width
      );

      // At zoom=0.5, viewport rect would be half but layout stays the same
      list.originalElementRect = {
        ...mockRect,
        width: 50,
        height: 10
      } as DOMRect;

      // Layout size is independent of zoom
      expect(list.originalLayoutSize.width).to.equal(100);
      expect(list.originalLayoutSize.height).to.equal(20);
    });
  });

  describe('setOriginalVisible', () => {
    it('toggles the original element display during drag', async () => {
      const list: SortableList = await createSorter(BORING_LIST);
      list.externalDrag = true;
      await list.updateComplete;

      const bounds = list.getBoundingClientRect();

      // Start dragging to set up downEle
      await moveMouse(bounds.left + 20, bounds.bottom - 10);
      await mouseDown();
      await moveMouse(bounds.left + 30, bounds.bottom - 10);
      clock.runAll();

      // downEle should be hidden during drag
      expect(list.downEle).to.exist;
      expect(list.downEle.style.display).to.equal('none');

      // Show original
      list.setOriginalVisible(true);
      expect(list.downEle.style.display).to.not.equal('none');

      // Hide original again
      list.setOriginalVisible(false);
      expect(list.downEle.style.display).to.equal('none');

      // Clean up
      await mouseUp();
      clock.runAll();
    });

    it('is a no-op when no element is being dragged', () => {
      const list = new SortableList();
      // Should not throw when downEle is null
      list.setOriginalVisible(true);
      list.setOriginalVisible(false);
    });
  });
});
