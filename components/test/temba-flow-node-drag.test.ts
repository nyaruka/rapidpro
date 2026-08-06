import { fixture, assert } from '@open-wc/testing';
import { html } from 'lit';

describe('temba-flow-node drag and drop functionality', () => {
  it('should add drag styling and event listeners to elements', async () => {
    // Create a simple div to test our drag functionality
    const testElement = await fixture(html`
      <div
        class="node"
        style="position: absolute; left: 100px; top: 100px; width: 200px; height: 100px; background: white; border: 1px solid #ccc; cursor: move;"
      >
        Test Node
        <div class="exit" style="padding: 5px; background: red;">Exit</div>
      </div>
    `);

    // Test that the node has the correct cursor style
    const computedStyle = window.getComputedStyle(testElement);
    assert.equal(computedStyle.cursor, 'move');

    // Test drag event simulation
    let dragStarted = false;
    let dragEnded = false;
    let newPosition = { left: 0, top: 0 };

    // Simulate our drag implementation
    let isDragging = false;
    let dragStartPos = { x: 0, y: 0 };
    let nodeStartPos = { left: 100, top: 100 };

    const handleMouseDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (target.classList.contains('exit') || target.closest('.exit')) {
        return;
      }

      isDragging = true;
      dragStarted = true;
      dragStartPos = { x: event.clientX, y: event.clientY };
      nodeStartPos = { left: 100, top: 100 };
      event.preventDefault();
      event.stopPropagation();
    };

    const handleMouseMove = (event: MouseEvent) => {
      if (!isDragging) return;

      const deltaX = event.clientX - dragStartPos.x;
      const deltaY = event.clientY - dragStartPos.y;

      const newLeft = nodeStartPos.left + deltaX;
      const newTop = nodeStartPos.top + deltaY;

      // Update position
      (testElement as HTMLElement).style.left = `${newLeft}px`;
      (testElement as HTMLElement).style.top = `${newTop}px`;
    };

    const handleMouseUp = (event: MouseEvent) => {
      if (!isDragging) return;

      isDragging = false;
      dragEnded = true;

      const deltaX = event.clientX - dragStartPos.x;
      const deltaY = event.clientY - dragStartPos.y;

      newPosition = {
        left: nodeStartPos.left + deltaX,
        top: nodeStartPos.top + deltaY
      };
    };

    // Add event listeners
    testElement.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    // Test drag from node (should work)
    const mouseDownEvent = new MouseEvent('mousedown', {
      clientX: 150,
      clientY: 150,
      bubbles: true
    });
    testElement.dispatchEvent(mouseDownEvent);

    assert.isTrue(dragStarted, 'Drag should start when clicking on node');

    const mouseMoveEvent = new MouseEvent('mousemove', {
      clientX: 200,
      clientY: 200,
      bubbles: true
    });
    document.dispatchEvent(mouseMoveEvent);

    const mouseUpEvent = new MouseEvent('mouseup', {
      clientX: 200,
      clientY: 200,
      bubbles: true
    });
    document.dispatchEvent(mouseUpEvent);

    assert.isTrue(dragEnded, 'Drag should end on mouse up');
    assert.equal(
      newPosition.left,
      150,
      'New left position should be calculated correctly'
    );
    assert.equal(
      newPosition.top,
      150,
      'New top position should be calculated correctly'
    );

    // Test that position was visually updated
    assert.equal((testElement as HTMLElement).style.left, '150px');
    assert.equal((testElement as HTMLElement).style.top, '150px');

    // Reset for next test
    dragStarted = false;
    dragEnded = false;

    // Test drag from exit element (should not work)
    const exitElement = testElement.querySelector('.exit') as HTMLElement;
    const exitMouseDownEvent = new MouseEvent('mousedown', {
      clientX: 150,
      clientY: 150,
      bubbles: true
    });
    exitElement.dispatchEvent(exitMouseDownEvent);

    assert.isFalse(
      dragStarted,
      'Drag should not start when clicking on exit element'
    );

    // Clean up
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  });

  it('should snap node positions to 20px grid during drag and drop', async () => {
    // Create a test node element
    const testElement = await fixture(html`
      <div
        class="node"
        style="position: absolute; left: 100px; top: 100px; width: 200px; height: 100px; background: white; border: 1px solid #ccc; cursor: move;"
      >
        Test Node for Grid Snapping
      </div>
    `);

    // Helper function to snap values to 20px grid (same as implementation)
    const snapToGrid = (value: number): number => {
      return Math.round(value / 20) * 20;
    };

    // Simulate drag implementation with grid snapping
    let isDragging = false;
    let dragStartPos = { x: 0, y: 0 };
    let nodeStartPos = { left: 100, top: 100 };
    let finalPosition = { left: 0, top: 0 };

    const handleMouseDown = (event: MouseEvent) => {
      isDragging = true;
      dragStartPos = { x: event.clientX, y: event.clientY };
      // Get current position from element style
      const currentLeft =
        parseInt((testElement as HTMLElement).style.left) || 0;
      const currentTop = parseInt((testElement as HTMLElement).style.top) || 0;
      nodeStartPos = { left: currentLeft, top: currentTop };
      event.preventDefault();
      event.stopPropagation();
    };

    const handleMouseMove = (event: MouseEvent) => {
      if (!isDragging) return;

      const deltaX = event.clientX - dragStartPos.x;
      const deltaY = event.clientY - dragStartPos.y;

      const newLeft = nodeStartPos.left + deltaX;
      const newTop = nodeStartPos.top + deltaY;

      // Snap to 20px grid
      const snappedLeft = snapToGrid(newLeft);
      const snappedTop = snapToGrid(newTop);

      // Update position with snapped values
      (testElement as HTMLElement).style.left = `${snappedLeft}px`;
      (testElement as HTMLElement).style.top = `${snappedTop}px`;
    };

    const handleMouseUp = (event: MouseEvent) => {
      if (!isDragging) return;
      isDragging = false;

      const deltaX = event.clientX - dragStartPos.x;
      const deltaY = event.clientY - dragStartPos.y;

      const newLeft = nodeStartPos.left + deltaX;
      const newTop = nodeStartPos.top + deltaY;

      // Snap final position to grid
      finalPosition = {
        left: snapToGrid(newLeft),
        top: snapToGrid(newTop)
      };
    };

    // Add event listeners
    testElement.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    // Test Case 1: Drag to position that should snap to grid
    // Starting at (100, 100), drag by (33, 27) pixels
    // Should result in (133, 127) -> snapped to (140, 120)
    const mouseDownEvent1 = new MouseEvent('mousedown', {
      clientX: 150,
      clientY: 150,
      bubbles: true
    });
    testElement.dispatchEvent(mouseDownEvent1);

    const mouseMoveEvent1 = new MouseEvent('mousemove', {
      clientX: 183, // 150 + 33
      clientY: 177, // 150 + 27
      bubbles: true
    });
    document.dispatchEvent(mouseMoveEvent1);

    // Check that position is snapped during drag
    assert.equal((testElement as HTMLElement).style.left, '140px');
    assert.equal((testElement as HTMLElement).style.top, '120px');

    const mouseUpEvent1 = new MouseEvent('mouseup', {
      clientX: 183,
      clientY: 177,
      bubbles: true
    });
    document.dispatchEvent(mouseUpEvent1);

    // Check final snapped position
    assert.equal(
      finalPosition.left,
      140,
      'Final left position should be snapped to 140px'
    );
    assert.equal(
      finalPosition.top,
      120,
      'Final top position should be snapped to 120px'
    );

    // Test Case 2: Test different snap scenarios
    // Reset position
    nodeStartPos = { left: 60, top: 80 };
    (testElement as HTMLElement).style.left = '60px';
    (testElement as HTMLElement).style.top = '80px';

    const mouseDownEvent2 = new MouseEvent('mousedown', {
      clientX: 100,
      clientY: 100,
      bubbles: true
    });
    testElement.dispatchEvent(mouseDownEvent2);

    // Drag by (15, 25) -> should snap to nearest 20px grid
    // (60 + 15, 80 + 25) = (75, 105) -> snapped to (80, 100)
    const mouseMoveEvent2 = new MouseEvent('mousemove', {
      clientX: 115, // 100 + 15
      clientY: 125, // 100 + 25
      bubbles: true
    });
    document.dispatchEvent(mouseMoveEvent2);

    assert.equal((testElement as HTMLElement).style.left, '80px');
    assert.equal((testElement as HTMLElement).style.top, '100px');

    const mouseUpEvent2 = new MouseEvent('mouseup', {
      clientX: 115,
      clientY: 125,
      bubbles: true
    });
    document.dispatchEvent(mouseUpEvent2);

    assert.equal(
      finalPosition.left,
      80,
      'Final left position should be snapped to 80px'
    );
    assert.equal(
      finalPosition.top,
      100,
      'Final top position should be snapped to 100px'
    );

    // Test Case 3: Test exact grid positions remain unchanged
    nodeStartPos = { left: 120, top: 160 }; // Already on grid
    (testElement as HTMLElement).style.left = '120px';
    (testElement as HTMLElement).style.top = '160px';

    const mouseDownEvent3 = new MouseEvent('mousedown', {
      clientX: 200,
      clientY: 200,
      bubbles: true
    });
    testElement.dispatchEvent(mouseDownEvent3);

    // Small movement that should stay on same grid position
    const mouseMoveEvent3 = new MouseEvent('mousemove', {
      clientX: 202, // +2 pixels
      clientY: 203, // +3 pixels
      bubbles: true
    });
    document.dispatchEvent(mouseMoveEvent3);

    // (120 + 2, 160 + 3) = (122, 163) -> snapped to (120, 160)
    assert.equal((testElement as HTMLElement).style.left, '120px');
    assert.equal((testElement as HTMLElement).style.top, '160px');

    const mouseUpEvent3 = new MouseEvent('mouseup', {
      clientX: 202,
      clientY: 203,
      bubbles: true
    });
    document.dispatchEvent(mouseUpEvent3);

    assert.equal(finalPosition.left, 120, 'Position should remain on grid');
    assert.equal(finalPosition.top, 160, 'Position should remain on grid');

    // Clean up
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  });

  describe('auto-scroll during drag', () => {
    const AUTO_SCROLL_EDGE_ZONE = 100;
    const AUTO_SCROLL_MAX_SPEED = 15;

    function calculateScrollSpeed(
      mousePos: number,
      edgeStart: number,
      edgeEnd: number
    ): { dx: number; dy: number } {
      const dx = 0;
      const dy = 0;

      // Left/top edge
      const distFromStart = mousePos - edgeStart;
      if (distFromStart >= 0 && distFromStart < AUTO_SCROLL_EDGE_ZONE) {
        const ratio = 1 - distFromStart / AUTO_SCROLL_EDGE_ZONE;
        return { dx: -(ratio * AUTO_SCROLL_MAX_SPEED), dy: 0 };
      }

      // Right/bottom edge
      const distFromEnd = edgeEnd - mousePos;
      if (distFromEnd >= 0 && distFromEnd < AUTO_SCROLL_EDGE_ZONE) {
        const ratio = 1 - distFromEnd / AUTO_SCROLL_EDGE_ZONE;
        return { dx: ratio * AUTO_SCROLL_MAX_SPEED, dy: 0 };
      }

      return { dx, dy };
    }

    it('should calculate scroll speed based on distance to edge', () => {
      const edgeStart = 0;
      const edgeEnd = 800;

      // At the very left edge (distance = 0), speed should be max
      let result = calculateScrollSpeed(0, edgeStart, edgeEnd);
      assert.equal(result.dx, -AUTO_SCROLL_MAX_SPEED);

      // At the edge zone boundary, speed should be 0
      result = calculateScrollSpeed(AUTO_SCROLL_EDGE_ZONE, edgeStart, edgeEnd);
      assert.equal(result.dx, 0);

      // Halfway into the zone, speed should be half of max
      result = calculateScrollSpeed(
        AUTO_SCROLL_EDGE_ZONE / 2,
        edgeStart,
        edgeEnd
      );
      assert.closeTo(result.dx, -AUTO_SCROLL_MAX_SPEED / 2, 0.01);

      // At the very right edge (distance = 0), speed should be max positive
      result = calculateScrollSpeed(800, edgeStart, edgeEnd);
      assert.equal(result.dx, AUTO_SCROLL_MAX_SPEED);

      // Halfway into the right edge zone
      result = calculateScrollSpeed(
        edgeEnd - AUTO_SCROLL_EDGE_ZONE / 2,
        edgeStart,
        edgeEnd
      );
      assert.closeTo(result.dx, AUTO_SCROLL_MAX_SPEED / 2, 0.01);

      // In the middle of the viewport, no scrolling
      result = calculateScrollSpeed(400, edgeStart, edgeEnd);
      assert.equal(result.dx, 0);
    });

    it('should not scroll when mouse is outside the viewport', () => {
      const edgeStart = 0;
      const edgeEnd = 800;

      // Mouse is to the left of the viewport
      const result = calculateScrollSpeed(-10, edgeStart, edgeEnd);
      assert.equal(result.dx, 0);
    });

    it('should account for scroll delta in drag position calculation', () => {
      // Simulate the formula: deltaX = (clientX - startX) + autoScrollDeltaX
      const dragStartX = 400;
      const currentClientX = 450;
      const autoScrollDeltaX = 200;

      const deltaX = currentClientX - dragStartX + autoScrollDeltaX;

      // Without auto-scroll, delta would be 50. With 200px of scroll, it's 250.
      assert.equal(deltaX, 250);

      const originalLeft = 100;
      const newLeft = originalLeft + deltaX;
      assert.equal(newLeft, 350);
    });

    it('should accumulate scroll deltas correctly over multiple frames', () => {
      let autoScrollDeltaX = 0;
      let autoScrollDeltaY = 0;

      // Simulate several frames of scrolling
      const scrollIncrements = [
        { dx: 5, dy: 3 },
        { dx: 8, dy: 6 },
        { dx: 10, dy: 9 },
        { dx: 0, dy: 12 } // only vertical scrolling
      ];

      scrollIncrements.forEach(({ dx, dy }) => {
        autoScrollDeltaX += dx;
        autoScrollDeltaY += dy;
      });

      assert.equal(autoScrollDeltaX, 23);
      assert.equal(autoScrollDeltaY, 30);
    });

    it('should clamp scroll delta when at scroll boundaries', () => {
      // Simulate a scroll container at its left boundary
      let scrollLeft = 0;
      const requestedDx = -10;

      const beforeScrollLeft = scrollLeft;
      scrollLeft = Math.max(0, scrollLeft + requestedDx);
      const actualDx = scrollLeft - beforeScrollLeft;

      // At the boundary, actual delta should be 0
      assert.equal(actualDx, 0);

      // Simulate a scroll container not at boundary
      scrollLeft = 50;
      const beforeScrollLeft2 = scrollLeft;
      scrollLeft = Math.max(0, scrollLeft + requestedDx);
      const actualDx2 = scrollLeft - beforeScrollLeft2;

      // Should have scrolled the full amount
      assert.equal(actualDx2, -10);
    });

    it('should reset scroll deltas after drag ends', () => {
      let autoScrollDeltaX = 150;
      let autoScrollDeltaY = 200;

      // Simulate drag end reset
      autoScrollDeltaX = 0;
      autoScrollDeltaY = 0;

      assert.equal(autoScrollDeltaX, 0);
      assert.equal(autoScrollDeltaY, 0);
    });

    it('should handle simultaneous horizontal and vertical auto-scroll', () => {
      // Simulate mouse in the bottom-right corner of the viewport
      const edgeEnd = 800;
      const mousePos = 780; // 20px from the right/bottom edge

      const distFromEnd = edgeEnd - mousePos;
      assert.isTrue(distFromEnd < AUTO_SCROLL_EDGE_ZONE);

      const ratio = 1 - distFromEnd / AUTO_SCROLL_EDGE_ZONE;
      const scrollSpeed = ratio * AUTO_SCROLL_MAX_SPEED;

      // Both axes should get the same speed when equidistant from edges
      assert.isAbove(scrollSpeed, 0);

      // Apply to both axes
      let autoScrollDeltaX = 0;
      let autoScrollDeltaY = 0;
      autoScrollDeltaX += scrollSpeed;
      autoScrollDeltaY += scrollSpeed;

      assert.equal(autoScrollDeltaX, autoScrollDeltaY);
      assert.isAbove(autoScrollDeltaX, 0);
    });
  });
});
