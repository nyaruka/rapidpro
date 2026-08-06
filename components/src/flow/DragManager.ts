import { html, TemplateResult } from 'lit-html';
import { FlowPosition } from '../store/flow-definition';
import { getStore } from '../store/Store';
import { isRightClick, snapToGrid } from './utils';
import { ARROW_LENGTH, CURSOR_GAP } from './Plumber';
import type { Editor, DraggableItem } from './Editor';

const DRAG_THRESHOLD = 5;
const AUTO_SCROLL_EDGE_ZONE = 150;
const AUTO_SCROLL_EDGE_ZONE_TOUCH = 40;
const AUTO_SCROLL_MAX_SPEED = 15;
const AUTO_SCROLL_BEYOND_MULTIPLIER = 5;

export class DragManager {
  // Drag state
  private isMouseDown = false;
  private shiftDragCopy = false;
  private currentDragIsCopy = false;
  private dragStartPos = { x: 0, y: 0 };

  // Mid-drag shift toggle: remember originals so we can switch between move/copy
  private originalDragItem: DraggableItem | null = null;
  private originalSelectedItems: Set<string> | null = null;

  // Drag hint tooltip
  private dragHintTimer: ReturnType<typeof setTimeout> | null = null;

  // Auto-scroll state
  private autoScrollAnimationId: number | null = null;
  private autoScrollDeltaX = 0;
  private autoScrollDeltaY = 0;
  private lastPointerPos: { clientX: number; clientY: number } | null = null;
  private activeDragIsTouch = false;

  // Touch device state
  private isTouchDevice = false;
  private isTwoFingerPanning = false;
  private twoFingerDidPan = false;
  private twoFingerStartMidX = 0;
  private twoFingerStartMidY = 0;
  private twoFingerOnCanvas = false;
  private lastPanX = 0;
  private lastPanY = 0;

  private canvasMouseDown = false;

  // Bound event handlers
  private boundMouseMove: (e: MouseEvent) => void;
  private boundMouseUp: (e: MouseEvent) => void;
  private boundGlobalMouseDown: (e: MouseEvent) => void;
  private boundKeyDown: (e: KeyboardEvent) => void;
  private boundKeyUp: (e: KeyboardEvent) => void;
  private boundWindowBlur: () => void;
  private boundTouchMove: (e: TouchEvent) => void;
  private boundTouchEnd: (e: TouchEvent) => void;
  private boundTouchCancel: () => void;
  private boundCanvasTouchStart: (e: TouchEvent) => void;

  constructor(private editor: Editor) {
    this.boundMouseMove = this.handleMouseMove.bind(this);
    this.boundMouseUp = this.handleMouseUp.bind(this);
    this.boundGlobalMouseDown = this.handleGlobalMouseDown.bind(this);
    this.boundKeyDown = this.handleKeyDown.bind(this);
    this.boundKeyUp = this.handleKeyUp.bind(this);
    this.boundWindowBlur = this.handleWindowBlur.bind(this);
    this.boundTouchMove = this.handleTouchMove.bind(this);
    this.boundTouchEnd = this.handleTouchEnd.bind(this);
    this.boundTouchCancel = this.handleTouchCancel.bind(this);
    this.boundCanvasTouchStart = this.handleCanvasTouchStart.bind(this);
  }

  public setupListeners(): void {
    document.addEventListener('mousemove', this.boundMouseMove);
    document.addEventListener('mouseup', this.boundMouseUp);
    document.addEventListener('mousedown', this.boundGlobalMouseDown);
    document.addEventListener('keydown', this.boundKeyDown);
    document.addEventListener('keyup', this.boundKeyUp);
    window.addEventListener('blur', this.boundWindowBlur);
    document.addEventListener('touchmove', this.boundTouchMove, {
      passive: false
    });
    document.addEventListener('touchend', this.boundTouchEnd);
    document.addEventListener('touchcancel', this.boundTouchCancel);
    const canvas = this.editor.querySelector('#canvas');
    canvas?.addEventListener(
      'touchstart',
      this.boundCanvasTouchStart as EventListener,
      { passive: false }
    );
  }

  public teardownListeners(): void {
    document.removeEventListener('mousemove', this.boundMouseMove);
    document.removeEventListener('mouseup', this.boundMouseUp);
    document.removeEventListener('mousedown', this.boundGlobalMouseDown);
    document.removeEventListener('keydown', this.boundKeyDown);
    document.removeEventListener('keyup', this.boundKeyUp);
    window.removeEventListener('blur', this.boundWindowBlur);
    document.removeEventListener('touchmove', this.boundTouchMove);
    document.removeEventListener('touchend', this.boundTouchEnd);
    document.removeEventListener('touchcancel', this.boundTouchCancel);
    const canvas = this.editor.querySelector('#canvas');
    canvas?.removeEventListener(
      'touchstart',
      this.boundCanvasTouchStart as EventListener
    );
    this.stopAutoScroll();
    this.hideDragHint();
  }

  private getPosition(uuid: string, type: 'node' | 'sticky'): FlowPosition {
    if (type === 'node') {
      return this.editor.definition._ui.nodes[uuid]?.position;
    } else {
      return this.editor.definition._ui.stickies?.[uuid]?.position;
    }
  }

  public handleMouseDown(event: MouseEvent): void {
    if (isRightClick(event)) return;

    if (this.editor.isReadOnly()) return;
    this.blurActiveContentEditable();

    const element = event.currentTarget as HTMLElement;
    const target = event.target as HTMLElement;
    if (
      target.classList.contains('exit') ||
      target.closest('.exit') ||
      target.closest('.linked-name') ||
      target.closest('.linked-pill')
    ) {
      return;
    }

    const uuid = element.getAttribute('uuid');
    const type = element.tagName === 'TEMBA-FLOW-NODE' ? 'node' : 'sticky';

    const position = this.getPosition(uuid, type);
    if (!position) return;

    if (
      !this.editor.selectedItems.has(uuid) &&
      !event.ctrlKey &&
      !event.metaKey
    ) {
      this.editor.selectedItems.clear();
    } else if (!this.editor.selectedItems.has(uuid)) {
      this.editor.selectedItems.add(uuid);
    }

    this.isMouseDown = true;
    this.activeDragIsTouch = false;
    this.shiftDragCopy = event.shiftKey;
    this.dragStartPos = { x: event.clientX, y: event.clientY };
    this.editor.currentDragItem = {
      uuid,
      position,
      element,
      type
    };

    event.preventDefault();
    event.stopPropagation();
  }

  /* c8 ignore start -- touch-only handlers untestable in headless Chromium */

  private markTouchDevice(): void {
    if (this.isTouchDevice) return;
    this.isTouchDevice = true;
    this.editor.querySelector('#canvas')?.classList.add('touch-device');
    this.editor.querySelector('#editor')?.classList.add('touch-device');
  }

  public handleItemTouchStart(event: TouchEvent): void {
    this.markTouchDevice();

    if (this.editor.isReadOnly()) return;
    this.blurActiveContentEditable();

    const touch = event.touches[0];
    if (!touch) return;

    const element = event.currentTarget as HTMLElement;
    const target = event.target as HTMLElement;
    if (
      target.classList.contains('exit') ||
      target.closest('.exit') ||
      target.closest('.linked-name') ||
      target.closest('.linked-pill')
    ) {
      return;
    }

    const uuid = element.getAttribute('uuid');
    const type = element.tagName === 'TEMBA-FLOW-NODE' ? 'node' : 'sticky';

    const position = this.getPosition(uuid, type);
    if (!position) return;

    if (!this.editor.selectedItems.has(uuid)) {
      this.editor.selectedItems.clear();
    }

    this.isMouseDown = true;
    this.activeDragIsTouch = true;
    this.dragStartPos = { x: touch.clientX, y: touch.clientY };
    this.editor.currentDragItem = {
      uuid,
      position,
      element,
      type
    };

    // Don't preventDefault here — allow the threshold check in touchmove
    // to decide whether this is a drag or a tap
    event.stopPropagation();
  }

  private handleGlobalMouseDown(event: MouseEvent): void {
    if (isRightClick(event)) return;

    const canvasRect = this.editor
      .querySelector('#grid')
      ?.getBoundingClientRect();
    if (!canvasRect) return;

    const isWithinCanvas =
      event.clientX >= canvasRect.left &&
      event.clientX <= canvasRect.right &&
      event.clientY >= canvasRect.top &&
      event.clientY <= canvasRect.bottom;

    if (!isWithinCanvas) return;

    const target = event.target as HTMLElement;
    const clickedOnDraggable = target.closest('.draggable');

    if (clickedOnDraggable) {
      return;
    }

    this.handleCanvasMouseDown(event);
  }

  public blurActiveContentEditable(): void {
    let active: Element | null = document.activeElement;
    while (active?.shadowRoot?.activeElement) {
      active = active.shadowRoot.activeElement;
    }
    if (
      active instanceof HTMLElement &&
      active.getAttribute('contenteditable') === 'true'
    ) {
      active.blur();
    }
  }

  private handleCanvasMouseDown(event: MouseEvent): void {
    if (this.editor.isReadOnly()) return;
    this.blurActiveContentEditable();

    const target = event.target as HTMLElement;
    if (target.id === 'canvas' || target.id === 'grid') {
      this.canvasMouseDown = true;
      this.dragStartPos = { x: event.clientX, y: event.clientY };

      const canvasRect = this.editor
        .querySelector('#canvas')
        ?.getBoundingClientRect();
      if (canvasRect) {
        this.editor.selectedItems.clear();

        const relativeX = (event.clientX - canvasRect.left) / this.editor.zoom;
        const relativeY = (event.clientY - canvasRect.top) / this.editor.zoom;

        this.editor.selectionBox = {
          startX: relativeX,
          startY: relativeY,
          endX: relativeX,
          endY: relativeY
        };
      }

      event.preventDefault();
    }
  }

  private showDragHint(): void {
    if (this.editor.isReadOnly()) return;
    const hint = this.editor.querySelector('#drag-hint') as HTMLElement;
    if (!hint) return;
    this.dragHintTimer = setTimeout(() => {
      hint.classList.add('visible');
      this.dragHintTimer = null;
    }, 600);
  }

  private hideDragHint(): void {
    if (this.dragHintTimer) {
      clearTimeout(this.dragHintTimer);
      this.dragHintTimer = null;
    }
    const hint = this.editor.querySelector('#drag-hint') as HTMLElement;
    if (hint) {
      hint.classList.remove('visible');
    }
  }

  private handleKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Shift') {
      this.editor.querySelector('#canvas')?.classList.add('shift-held');

      // Toggle to copy mode mid-drag (nodes)
      if (this.editor.isDragging && !this.currentDragIsCopy) {
        this.hideDragHint();
        this.performShiftDragCopy();
        requestAnimationFrame(() => {
          this.markCopyElements();
          this.updateDragPositions();
        });
      }
    }

    // Forward to editor for non-drag keyboard handling
    this.editor.handleKeyDown(event);
  }

  private handleKeyUp(event: KeyboardEvent): void {
    if (event.key === 'Shift') {
      this.editor.querySelector('#canvas')?.classList.remove('shift-held');

      // Toggle back to move mode mid-drag (nodes)
      if (this.editor.isDragging && this.currentDragIsCopy) {
        this.revertShiftDragCopy();
        requestAnimationFrame(() => this.updateDragPositions());
      }
    }

    // Forward to editor for action drag shift-copy
    this.editor.handleKeyUp(event);
  }

  private handleWindowBlur(): void {
    this.editor.querySelector('#canvas')?.classList.remove('shift-held');

    // Revert copy mode if blur happens mid-drag (keyup may never fire)
    if (this.editor.isDragging && this.currentDragIsCopy) {
      this.revertShiftDragCopy();
      requestAnimationFrame(() => this.updateDragPositions());
    }

    // Forward to editor for action drag blur handling
    this.editor.handleWindowBlur();
  }

  private updateSelectionBox(event: MouseEvent): void {
    if (!this.editor.selectionBox || !this.canvasMouseDown) return;

    const canvasRect = this.editor
      .querySelector('#canvas')
      ?.getBoundingClientRect();
    if (!canvasRect) return;

    const relativeX = (event.clientX - canvasRect.left) / this.editor.zoom;
    const relativeY = (event.clientY - canvasRect.top) / this.editor.zoom;

    this.editor.selectionBox = {
      ...this.editor.selectionBox,
      endX: relativeX,
      endY: relativeY
    };

    this.updateSelectedItemsFromBox();
  }

  private updateSelectedItemsFromBox(): void {
    if (!this.editor.selectionBox) return;

    const newSelection = new Set<string>();

    const boxLeft = Math.min(
      this.editor.selectionBox.startX,
      this.editor.selectionBox.endX
    );
    const boxTop = Math.min(
      this.editor.selectionBox.startY,
      this.editor.selectionBox.endY
    );
    const boxRight = Math.max(
      this.editor.selectionBox.startX,
      this.editor.selectionBox.endX
    );
    const boxBottom = Math.max(
      this.editor.selectionBox.startY,
      this.editor.selectionBox.endY
    );

    // Check nodes
    this.editor.definition?.nodes.forEach((node) => {
      const nodeElement = this.editor.querySelector(
        `[id="${node.uuid}"]`
      ) as HTMLElement;
      if (nodeElement) {
        const position = this.editor.definition._ui?.nodes[node.uuid]?.position;
        if (position) {
          const canvasRect = this.editor
            .querySelector('#canvas')
            ?.getBoundingClientRect();

          if (canvasRect) {
            const nodeLeft = position.left;
            const nodeTop = position.top;
            const nodeRight = nodeLeft + nodeElement.offsetWidth;
            const nodeBottom = nodeTop + nodeElement.offsetHeight;

            if (
              boxLeft < nodeRight &&
              boxRight > nodeLeft &&
              boxTop < nodeBottom &&
              boxBottom > nodeTop
            ) {
              newSelection.add(node.uuid);
            }
          }
        }
      }
    });

    // Check sticky notes
    const stickies = this.editor.definition?._ui?.stickies || {};
    Object.entries(stickies).forEach(([uuid, sticky]) => {
      if (sticky.position) {
        const stickyElement = this.editor.querySelector(
          `temba-sticky-note[uuid="${uuid}"]`
        ) as HTMLElement;

        if (stickyElement) {
          const width = stickyElement.clientWidth;
          const height = stickyElement.clientHeight;

          const stickyLeft = sticky.position.left;
          const stickyTop = sticky.position.top;
          const stickyRight = stickyLeft + width;
          const stickyBottom = stickyTop + height;

          if (
            boxLeft < stickyRight &&
            boxRight > stickyLeft &&
            boxTop < stickyBottom &&
            boxBottom > stickyTop
          ) {
            newSelection.add(uuid);
          }
        }
      }
    });

    this.editor.selectedItems = newSelection;
  }

  public renderSelectionBox(): TemplateResult | string {
    if (!this.editor.selectionBox || !this.editor.isSelecting) return '';

    const left = Math.min(
      this.editor.selectionBox.startX,
      this.editor.selectionBox.endX
    );
    const top = Math.min(
      this.editor.selectionBox.startY,
      this.editor.selectionBox.endY
    );
    const width = Math.abs(
      this.editor.selectionBox.endX - this.editor.selectionBox.startX
    );
    const height = Math.abs(
      this.editor.selectionBox.endY - this.editor.selectionBox.startY
    );

    return html`<div
      class="selection-box"
      style="left: ${left}px; top: ${top}px; width: ${width}px; height: ${height}px;"
    ></div>`;
  }

  private handleCanvasTouchStart(event: TouchEvent): void {
    this.markTouchDevice();

    const touch = event.touches[0];
    if (!touch) return;

    const target = event.target as HTMLElement;
    if (target.closest('.draggable')) return;
    if (target.id !== 'canvas' && target.id !== 'grid') return;

    if (event.touches.length >= 2) {
      this.canvasMouseDown = false;
      this.editor.isSelecting = false;
      this.editor.selectionBox = null;

      this.isTwoFingerPanning = true;
      this.twoFingerOnCanvas = true;
      this.twoFingerDidPan = false;
      this.twoFingerStartMidX =
        (event.touches[0].clientX + event.touches[1].clientX) / 2;
      this.twoFingerStartMidY =
        (event.touches[0].clientY + event.touches[1].clientY) / 2;
      this.lastPanX = this.twoFingerStartMidX;
      this.lastPanY = this.twoFingerStartMidY;
      return;
    }

    if (this.editor.isReadOnly()) return;

    this.canvasMouseDown = true;
    this.dragStartPos = { x: touch.clientX, y: touch.clientY };

    const canvasRect = this.editor
      .querySelector('#canvas')
      ?.getBoundingClientRect();
    if (canvasRect) {
      this.editor.selectedItems.clear();

      const relativeX = (touch.clientX - canvasRect.left) / this.editor.zoom;
      const relativeY = (touch.clientY - canvasRect.top) / this.editor.zoom;

      this.editor.selectionBox = {
        startX: relativeX,
        startY: relativeY,
        endX: relativeX,
        endY: relativeY
      };
    }

    event.preventDefault();
  }

  /* c8 ignore stop */

  private handleMouseMove(event: MouseEvent): void {
    // Handle selection box drawing
    if (this.canvasMouseDown && !this.isMouseDown) {
      this.editor.isSelecting = true;
      this.updateSelectionBox(event);
      this.editor.requestUpdate();
      return;
    }

    if (this.editor.plumber.connectionDragging) {
      this.activeDragIsTouch = false;
      this.lastPointerPos = { clientX: event.clientX, clientY: event.clientY };
      this.startAutoScroll();

      const targetNode = document.querySelector('temba-flow-node:hover');

      document.querySelectorAll('temba-flow-node').forEach((node) => {
        node.classList.remove(
          'connection-target-valid',
          'connection-target-invalid'
        );
      });

      if (targetNode) {
        this.editor.targetId = targetNode.getAttribute('uuid');
        this.editor.isValidTarget =
          this.editor.targetId !== this.editor.dragFromNodeId;

        if (this.editor.isValidTarget) {
          targetNode.classList.add('connection-target-valid');
        } else {
          targetNode.classList.add('connection-target-invalid');
        }

        this.editor.connectionPlaceholder = null;
      } else {
        this.editor.targetId = null;
        this.editor.isValidTarget = true;

        const canvas = this.editor.querySelector('#canvas');
        if (canvas) {
          const canvasRect = canvas.getBoundingClientRect();
          const relativeX =
            (event.clientX - canvasRect.left) / this.editor.zoom;
          const relativeY = (event.clientY - canvasRect.top) / this.editor.zoom;

          const placeholderWidth = 200;
          const placeholderHeight = 64;
          const arrowLength = ARROW_LENGTH;
          const cursorGap = CURSOR_GAP;

          const dragUp =
            this.editor.connectionSourceY != null
              ? relativeY < this.editor.connectionSourceY
              : false;

          let top: number;
          if (dragUp) {
            top = relativeY + cursorGap - placeholderHeight;
          } else {
            top = relativeY - cursorGap + arrowLength;
          }

          this.editor.connectionPlaceholder = {
            position: {
              left: relativeX - placeholderWidth / 2,
              top
            },
            visible: true,
            dragUp
          };
        }
      }

      this.editor.requestUpdate();
    }

    // Handle item dragging
    if (!this.isMouseDown || !this.editor.currentDragItem) return;

    this.lastPointerPos = { clientX: event.clientX, clientY: event.clientY };

    const deltaX = event.clientX - this.dragStartPos.x + this.autoScrollDeltaX;
    const deltaY = event.clientY - this.dragStartPos.y + this.autoScrollDeltaY;
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

    if (!this.editor.isDragging && distance > DRAG_THRESHOLD) {
      this.editor.isDragging = true;
      this.startAutoScroll();

      this.originalDragItem = { ...this.editor.currentDragItem };
      this.originalSelectedItems = new Set(this.editor.selectedItems);

      if (this.shiftDragCopy || event.shiftKey) {
        this.performShiftDragCopy();
        this.shiftDragCopy = false;
      } else {
        this.showDragHint();
      }
    }

    if (this.editor.isDragging) {
      this.updateDragPositions();
    }
  }

  private performShiftDragCopy(): void {
    if (!this.originalDragItem) return;

    const itemsToCopy =
      this.originalSelectedItems?.has(this.originalDragItem.uuid) &&
      (this.originalSelectedItems?.size ?? 0) > 1
        ? Array.from(this.originalSelectedItems!)
        : [this.originalDragItem.uuid];

    if (itemsToCopy.length === 0) return;

    const uuidMapping = getStore().getState().duplicateNodes(itemsToCopy);

    for (const uuid of itemsToCopy) {
      const newUuid = uuidMapping[uuid];
      if (newUuid && !this.editor.copiedItemUuids.includes(newUuid)) {
        this.editor.copiedItemUuids.push(newUuid);
      }
    }
    this.currentDragIsCopy = true;

    for (const uuid of itemsToCopy) {
      const element = this.editor.querySelector(
        `[uuid="${uuid}"]`
      ) as HTMLElement;
      const type = element?.tagName === 'TEMBA-FLOW-NODE' ? 'node' : 'sticky';
      const position = this.getPosition(uuid, type);
      if (element && position) {
        element.style.left = `${position.left}px`;
        element.style.top = `${position.top}px`;
      }
    }
    this.editor.plumber.revalidate(itemsToCopy);
    for (const uuid of itemsToCopy) {
      const element = this.editor.querySelector(
        `[uuid="${uuid}"]`
      ) as HTMLElement;
      if (element) {
        void element.offsetHeight;
        element.classList.remove('dragging');
      }
    }

    const newDragUuid = uuidMapping[this.originalDragItem.uuid];
    if (newDragUuid) {
      this.editor.currentDragItem = {
        ...this.originalDragItem,
        uuid: newDragUuid
      };
    }

    if ((this.originalSelectedItems?.size ?? 0) > 1) {
      const newSelectedItems = new Set<string>();
      for (const uuid of this.originalSelectedItems!) {
        const newUuid = uuidMapping[uuid];
        newSelectedItems.add(newUuid || uuid);
      }
      this.editor.selectedItems = newSelectedItems;
    }
  }

  private markCopyElements(): void {
    for (const uuid of this.editor.copiedItemUuids) {
      const el = this.editor.querySelector(`[uuid="${uuid}"]`) as HTMLElement;
      el?.classList.add('drag-copy');
    }
  }

  private revertShiftDragCopy(): void {
    if (!this.originalDragItem) return;

    if (this.editor.copiedItemUuids.length > 0) {
      const nodeUuids = this.editor.copiedItemUuids.filter((uuid) =>
        this.editor.definition.nodes.some((n) => n.uuid === uuid)
      );
      const stickyUuids = this.editor.copiedItemUuids.filter(
        (uuid) => this.editor.definition._ui?.stickies?.[uuid]
      );

      if (nodeUuids.length > 0) {
        getStore().getState().removeNodes(nodeUuids);
      }
      if (stickyUuids.length > 0) {
        getStore().getState().removeStickyNotes(stickyUuids);
      }
      this.editor.copiedItemUuids = [];
    }

    this.currentDragIsCopy = false;

    getStore().getState().setDirtyDate(null);

    this.editor.currentDragItem = { ...this.originalDragItem };
    if (this.originalSelectedItems) {
      this.editor.selectedItems = new Set(this.originalSelectedItems);
    }
  }

  private updateDragPositions(): void {
    if (!this.editor.currentDragItem || !this.lastPointerPos) return;

    const deltaX =
      (this.lastPointerPos.clientX -
        this.dragStartPos.x +
        this.autoScrollDeltaX) /
      this.editor.zoom;
    const deltaY =
      (this.lastPointerPos.clientY -
        this.dragStartPos.y +
        this.autoScrollDeltaY) /
      this.editor.zoom;

    const itemsToMove =
      this.editor.selectedItems.has(this.editor.currentDragItem.uuid) &&
      this.editor.selectedItems.size > 1
        ? Array.from(this.editor.selectedItems)
        : [this.editor.currentDragItem.uuid];

    itemsToMove.forEach((uuid) => {
      const element = this.editor.querySelector(
        `[uuid="${uuid}"]`
      ) as HTMLElement;
      if (element) {
        const type = element.tagName === 'TEMBA-FLOW-NODE' ? 'node' : 'sticky';
        const position = this.getPosition(uuid, type);

        if (position) {
          element.style.left = `${position.left + deltaX}px`;
          element.style.top = `${position.top + deltaY}px`;
          element.classList.add('dragging');
          if (this.currentDragIsCopy) {
            element.classList.add('drag-copy');
          }
        }
      }
    });

    this.editor.plumber.revalidate(itemsToMove);
  }

  private startAutoScroll(): void {
    if (this.autoScrollAnimationId !== null) return;

    const editorEl = this.editor.querySelector('#editor') as HTMLElement;
    if (!editorEl) return;

    const tick = () => {
      if (
        (!this.editor.isDragging && !this.editor.plumber?.connectionDragging) ||
        !this.lastPointerPos
      ) {
        this.autoScrollAnimationId = null;
        return;
      }

      const editorRect = editorEl.getBoundingClientRect();
      const mouseX = this.lastPointerPos.clientX;
      const mouseY = this.lastPointerPos.clientY;
      const edgeZone = this.activeDragIsTouch
        ? AUTO_SCROLL_EDGE_ZONE_TOUCH
        : AUTO_SCROLL_EDGE_ZONE;

      let scrollDx = 0;
      let scrollDy = 0;

      // Left edge (including beyond)
      const distFromLeft = mouseX - editorRect.left;
      if (distFromLeft < edgeZone) {
        const beyond = distFromLeft < 0;
        const ratio = Math.min(1, 1 - distFromLeft / edgeZone);
        const speed =
          AUTO_SCROLL_MAX_SPEED * (beyond ? AUTO_SCROLL_BEYOND_MULTIPLIER : 1);
        scrollDx = -(ratio * speed);
      }

      // Right edge (including beyond)
      const distFromRight = editorRect.right - mouseX;
      if (distFromRight < edgeZone) {
        const beyond = distFromRight < 0;
        const ratio = Math.min(1, 1 - distFromRight / edgeZone);
        const speed =
          AUTO_SCROLL_MAX_SPEED * (beyond ? AUTO_SCROLL_BEYOND_MULTIPLIER : 1);
        scrollDx = ratio * speed;
      }

      const distFromTop = mouseY - editorRect.top;
      // Top edge (including beyond)
      if (distFromTop < edgeZone) {
        const beyond = distFromTop < 0;
        const ratio = Math.min(1, 1 - distFromTop / edgeZone);
        const speed =
          AUTO_SCROLL_MAX_SPEED * (beyond ? AUTO_SCROLL_BEYOND_MULTIPLIER : 1);
        scrollDy = -(ratio * speed);
      }

      // Bottom edge (including beyond)
      const distFromBottom = editorRect.bottom - mouseY;
      if (distFromBottom < edgeZone) {
        const beyond = distFromBottom < 0;
        const ratio = Math.min(1, 1 - distFromBottom / edgeZone);
        const speed =
          AUTO_SCROLL_MAX_SPEED * (beyond ? AUTO_SCROLL_BEYOND_MULTIPLIER : 1);
        scrollDy = ratio * speed;
      }

      if (scrollDx !== 0 || scrollDy !== 0) {
        const beforeScrollLeft = editorEl.scrollLeft;
        const beforeScrollTop = editorEl.scrollTop;

        if (scrollDx > 0 || scrollDy > 0) {
          const neededWidth =
            (editorEl.scrollLeft + editorEl.clientWidth + scrollDx) /
            this.editor.zoom;
          const neededHeight =
            (editorEl.scrollTop + editorEl.clientHeight + scrollDy) /
            this.editor.zoom;
          getStore()?.getState()?.expandCanvas(neededWidth, neededHeight);
        }

        editorEl.scrollLeft += scrollDx;
        editorEl.scrollTop += scrollDy;

        const actualDx = editorEl.scrollLeft - beforeScrollLeft;
        const actualDy = editorEl.scrollTop - beforeScrollTop;
        this.autoScrollDeltaX += actualDx;
        this.autoScrollDeltaY += actualDy;

        if (actualDx !== 0 || actualDy !== 0) {
          this.updateDragPositions();
        }
      }

      this.autoScrollAnimationId = requestAnimationFrame(tick);
    };

    this.autoScrollAnimationId = requestAnimationFrame(tick);
  }

  private stopAutoScroll(): void {
    if (this.autoScrollAnimationId !== null) {
      cancelAnimationFrame(this.autoScrollAnimationId);
      this.autoScrollAnimationId = null;
    }
  }

  private handleMouseUp(event: MouseEvent): void {
    // Handle selection box completion
    if (this.canvasMouseDown && this.editor.isSelecting) {
      this.editor.isSelecting = false;
      this.editor.selectionBox = null;
      this.canvasMouseDown = false;
      this.editor.requestUpdate();
      return;
    }

    // Handle canvas click (clear selection)
    if (this.canvasMouseDown && !this.editor.isSelecting) {
      this.canvasMouseDown = false;
      return;
    }

    // Handle item drag completion
    if (!this.isMouseDown || !this.editor.currentDragItem) return;

    this.stopAutoScroll();

    if (this.editor.isDragging) {
      const deltaX =
        (event.clientX - this.dragStartPos.x + this.autoScrollDeltaX) /
        this.editor.zoom;
      const deltaY =
        (event.clientY - this.dragStartPos.y + this.autoScrollDeltaY) /
        this.editor.zoom;

      const itemsToMove =
        this.editor.selectedItems.has(this.editor.currentDragItem.uuid) &&
        this.editor.selectedItems.size > 1
          ? Array.from(this.editor.selectedItems)
          : [this.editor.currentDragItem.uuid];

      const newPositions: { [uuid: string]: FlowPosition } = {};

      itemsToMove.forEach((uuid) => {
        const type = this.editor.definition.nodes.find(
          (node) => node.uuid === uuid
        )
          ? 'node'
          : 'sticky';
        const position = this.getPosition(uuid, type);

        if (position) {
          const newLeft = position.left + deltaX;
          const newTop = position.top + deltaY;

          const snappedLeft = snapToGrid(newLeft);
          const snappedTop = snapToGrid(newTop);

          const newPosition = { left: snappedLeft, top: snappedTop };
          newPositions[uuid] = newPosition;

          const element = this.editor.querySelector(
            `[uuid="${uuid}"]`
          ) as HTMLElement;
          if (element) {
            element.classList.remove('dragging', 'drag-copy');
            element.style.left = `${snappedLeft}px`;
            element.style.top = `${snappedTop}px`;
          }
        }
      });

      if (Object.keys(newPositions).length > 0) {
        if (this.currentDragIsCopy) {
          this.editor.pendingTimer.pending = true;
          this.editor.capturePositionsOnce();
        }

        getStore().getState().updateCanvasPositions(newPositions);

        setTimeout(() => {
          this.editor.checkCollisionsAndReflow(itemsToMove);
          this.editor.plumber.repaintEverything();
        }, 0);
      }

      if (this.currentDragIsCopy) {
        this.editor.pendingTimer.start();
      }

      this.editor.selectedItems.clear();
    }

    // Reset all drag state
    this.hideDragHint();
    this.editor.isDragging = false;
    this.isMouseDown = false;
    this.shiftDragCopy = false;
    this.currentDragIsCopy = false;
    this.editor.currentDragItem = null;
    this.originalDragItem = null;
    this.originalSelectedItems = null;
    this.canvasMouseDown = false;
    this.autoScrollDeltaX = 0;
    this.autoScrollDeltaY = 0;
    this.lastPointerPos = null;
  }

  /* c8 ignore start -- touch-only handlers */

  private handleTouchMove(event: TouchEvent): void {
    // --- Two-finger panning ---
    if (event.touches.length >= 2) {
      event.preventDefault();
      const midX = (event.touches[0].clientX + event.touches[1].clientX) / 2;
      const midY = (event.touches[0].clientY + event.touches[1].clientY) / 2;

      if (this.isTwoFingerPanning) {
        const dx = this.lastPanX - midX;
        const dy = this.lastPanY - midY;
        if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
          this.twoFingerDidPan = true;
        }
        const editorEl = this.editor.querySelector('#editor') as HTMLElement;
        if (editorEl) {
          editorEl.scrollBy(dx, dy);
        }
      }

      this.canvasMouseDown = false;
      this.editor.isSelecting = false;
      this.editor.selectionBox = null;

      this.isTwoFingerPanning = true;
      this.lastPanX = midX;
      this.lastPanY = midY;
      return;
    }

    const touch = event.touches[0];
    if (!touch) return;

    // --- Selection box drawing ---
    if (this.canvasMouseDown && !this.isMouseDown) {
      event.preventDefault();
      this.editor.isSelecting = true;

      const canvasRect = this.editor
        .querySelector('#canvas')
        ?.getBoundingClientRect();
      if (canvasRect && this.editor.selectionBox) {
        this.editor.selectionBox = {
          ...this.editor.selectionBox,
          endX: (touch.clientX - canvasRect.left) / this.editor.zoom,
          endY: (touch.clientY - canvasRect.top) / this.editor.zoom
        };
        this.updateSelectedItemsFromBox();
      }

      this.editor.requestUpdate();
      return;
    }

    // --- Connection dragging ---
    if (this.editor.plumber.connectionDragging) {
      event.preventDefault();

      const targetNode = this.editor.findTargetNodeAt(
        touch.clientX,
        touch.clientY
      );

      document.querySelectorAll('temba-flow-node').forEach((node) => {
        node.classList.remove(
          'connection-target-valid',
          'connection-target-invalid'
        );
      });

      if (targetNode) {
        this.editor.targetId = targetNode.getAttribute('uuid');
        this.editor.isValidTarget =
          this.editor.targetId !== this.editor.dragFromNodeId;

        if (this.editor.isValidTarget) {
          targetNode.classList.add('connection-target-valid');
        } else {
          targetNode.classList.add('connection-target-invalid');
        }

        this.editor.connectionPlaceholder = null;
      } else {
        this.editor.targetId = null;
        this.editor.isValidTarget = true;

        const canvas = this.editor.querySelector('#canvas');
        if (canvas) {
          const canvasRect = canvas.getBoundingClientRect();
          const relativeX =
            (touch.clientX - canvasRect.left) / this.editor.zoom;
          const relativeY = (touch.clientY - canvasRect.top) / this.editor.zoom;

          const placeholderWidth = 200;
          const placeholderHeight = 64;
          const arrowLength = ARROW_LENGTH;
          const cursorGap = CURSOR_GAP;

          const dragUp =
            this.editor.connectionSourceY != null
              ? relativeY < this.editor.connectionSourceY
              : false;

          let top: number;
          if (dragUp) {
            top = relativeY + cursorGap - placeholderHeight;
          } else {
            top = relativeY - cursorGap + arrowLength;
          }

          this.editor.connectionPlaceholder = {
            position: {
              left: relativeX - placeholderWidth / 2,
              top
            },
            visible: true,
            dragUp
          };
        }
      }

      this.editor.requestUpdate();
      return;
    }

    // --- Node/sticky dragging ---
    if (!this.isMouseDown || !this.editor.currentDragItem) return;

    this.lastPointerPos = { clientX: touch.clientX, clientY: touch.clientY };

    const deltaX = touch.clientX - this.dragStartPos.x + this.autoScrollDeltaX;
    const deltaY = touch.clientY - this.dragStartPos.y + this.autoScrollDeltaY;
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

    if (!this.editor.isDragging && distance > DRAG_THRESHOLD) {
      this.editor.isDragging = true;
      this.startAutoScroll();
    }

    if (this.editor.isDragging) {
      event.preventDefault();
      this.updateDragPositions();
    }
  }

  private handleTouchEnd(event: TouchEvent): void {
    // --- Two-finger gesture end ---
    if (this.isTwoFingerPanning) {
      if (event.touches.length === 0) {
        const didPan = this.twoFingerDidPan;
        const onCanvas = this.twoFingerOnCanvas;
        const midX = this.twoFingerStartMidX;
        const midY = this.twoFingerStartMidY;

        this.isTwoFingerPanning = false;
        this.twoFingerOnCanvas = false;
        this.twoFingerDidPan = false;

        if (!didPan && onCanvas) {
          this.editor.showContextMenuAt(midX, midY);
        }
      }
      return;
    }

    const touch = event.changedTouches[0];

    // --- Selection box completion ---
    if (this.canvasMouseDown && this.editor.isSelecting) {
      this.editor.isSelecting = false;
      this.editor.selectionBox = null;
      this.canvasMouseDown = false;
      this.editor.requestUpdate();
      return;
    }

    // --- Canvas tap (no drag) — clear selection ---
    if (this.canvasMouseDown && !this.editor.isSelecting) {
      this.canvasMouseDown = false;
      return;
    }

    // --- Connection dragging ---
    if (this.editor.plumber.connectionDragging) {
      if (touch) {
        const targetNode = this.editor.findTargetNodeAt(
          touch.clientX,
          touch.clientY
        );
        if (targetNode) {
          this.editor.targetId = targetNode.getAttribute('uuid');
          this.editor.isValidTarget =
            this.editor.targetId !== this.editor.dragFromNodeId;
        }
      }
      return;
    }

    // --- Node/sticky dragging ---
    if (!this.isMouseDown || !this.editor.currentDragItem) return;

    this.stopAutoScroll();

    if (this.editor.isDragging && touch) {
      const deltaX =
        (touch.clientX - this.dragStartPos.x + this.autoScrollDeltaX) /
        this.editor.zoom;
      const deltaY =
        (touch.clientY - this.dragStartPos.y + this.autoScrollDeltaY) /
        this.editor.zoom;

      const itemsToMove =
        this.editor.selectedItems.has(this.editor.currentDragItem.uuid) &&
        this.editor.selectedItems.size > 1
          ? Array.from(this.editor.selectedItems)
          : [this.editor.currentDragItem.uuid];

      const newPositions: { [uuid: string]: FlowPosition } = {};

      itemsToMove.forEach((uuid) => {
        const type = this.editor.definition.nodes.find(
          (node) => node.uuid === uuid
        )
          ? 'node'
          : 'sticky';
        const position = this.getPosition(uuid, type);

        if (position) {
          const newLeft = position.left + deltaX;
          const newTop = position.top + deltaY;
          const snappedLeft = snapToGrid(newLeft);
          const snappedTop = snapToGrid(newTop);

          newPositions[uuid] = { left: snappedLeft, top: snappedTop };

          const element = this.editor.querySelector(
            `[uuid="${uuid}"]`
          ) as HTMLElement;
          if (element) {
            element.classList.remove('dragging');
            element.style.left = `${snappedLeft}px`;
            element.style.top = `${snappedTop}px`;
          }
        }
      });

      if (Object.keys(newPositions).length > 0) {
        getStore().getState().updateCanvasPositions(newPositions);

        setTimeout(() => {
          this.editor.checkCollisionsAndReflow(itemsToMove);
          this.editor.plumber.repaintEverything();
        }, 0);
      }

      this.editor.selectedItems.clear();
    }

    // Reset all drag state
    this.editor.isDragging = false;
    this.isMouseDown = false;
    this.editor.currentDragItem = null;
    this.canvasMouseDown = false;
    this.autoScrollDeltaX = 0;
    this.autoScrollDeltaY = 0;
    this.lastPointerPos = null;
  }

  private handleTouchCancel(): void {
    this.isTwoFingerPanning = false;
    this.editor.isSelecting = false;
    this.editor.selectionBox = null;
    this.canvasMouseDown = false;

    if (this.editor.isDragging && this.editor.currentDragItem) {
      const itemsToReset =
        this.editor.selectedItems.has(this.editor.currentDragItem.uuid) &&
        this.editor.selectedItems.size > 1
          ? Array.from(this.editor.selectedItems)
          : [this.editor.currentDragItem.uuid];
      itemsToReset.forEach((uuid) => {
        const el = this.editor.querySelector(`[uuid="${uuid}"]`) as HTMLElement;
        if (el) el.classList.remove('dragging');
      });
    }

    this.stopAutoScroll();
    this.editor.isDragging = false;
    this.isMouseDown = false;
    this.editor.currentDragItem = null;
    this.autoScrollDeltaX = 0;
    this.autoScrollDeltaY = 0;
    this.lastPointerPos = null;

    document.querySelectorAll('temba-flow-node').forEach((node) => {
      node.classList.remove(
        'connection-target-valid',
        'connection-target-invalid'
      );
    });
    this.editor.connectionPlaceholder = null;

    this.editor.requestUpdate();
  }

  /* c8 ignore stop */
}
