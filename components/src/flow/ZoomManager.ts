import { FloatingTab } from '../display/FloatingTab';
import type { Editor } from './Editor';

export class ZoomManager {
  // Zoom state
  private zoomInitialized = false;
  private zoomFitted = false;

  // Loupe magnifier state
  private loupeEl: HTMLElement | null = null;
  private loupeContentEl: HTMLElement | null = null;
  private loupeRAF: number | null = null;
  private hiddenTitles: { el: Element; title: string }[] = [];
  private loupeKeyHeld = false;
  private loupeMouseIsDown = false;
  private loupeLastMouse: { clientX: number; clientY: number } | null = null;
  private loupeCloneTime = 0;
  private loupeClone: HTMLElement | null = null;
  private loupeCursorCanvas: { x: number; y: number } = { x: 0, y: 0 };

  private static readonly LOUPE_DIAMETER = 280;
  private static readonly LOUPE_CLONE_INTERVAL = 200;

  // Bound loupe event handlers
  private readonly boundLoupeMouseMove = this.handleLoupeMouseMove.bind(this);
  private readonly boundLoupeMouseDown = this.handleLoupeMouseDown.bind(this);
  private readonly boundLoupeMouseUp = this.handleLoupeMouseUp.bind(this);
  private readonly boundLoupeKeyDown = this.handleLoupeKeyDown.bind(this);
  private readonly boundLoupeKeyUp = this.handleLoupeKeyUp.bind(this);

  constructor(private editor: Editor) {}

  // --- Zoom ---

  public setZoom(
    newZoom: number,
    center?: { clientX: number; clientY: number }
  ): void {
    const clamped = Math.max(
      0.3,
      Math.min(1.0, Math.round(newZoom * 100) / 100)
    );
    if (clamped === this.editor.zoom) return;

    const editor = this.editor.querySelector('#editor') as HTMLElement;
    const oldZoom = this.editor.zoom;
    this.editor.zoom = clamped;
    this.editor.plumber.zoom = clamped;
    this.zoomFitted = false;
    this.editor.requestUpdate();
    this.editor.saveFlowSetting('zoom', clamped);

    if (editor && center) {
      const editorRect = editor.getBoundingClientRect();
      const ox = center.clientX - editorRect.left;
      const oy = center.clientY - editorRect.top;
      // Canvas point under cursor at old zoom
      const cx = (editor.scrollLeft + ox) / oldZoom;
      const cy = (editor.scrollTop + oy) / oldZoom;

      requestAnimationFrame(() => {
        editor.scrollLeft = cx * clamped - ox;
        editor.scrollTop = cy * clamped - oy;
        this.editor.plumber.repaintEverything();
      });
    } else {
      requestAnimationFrame(() => this.editor.plumber.repaintEverything());
    }
  }

  public zoomIn(): void {
    this.setZoom(this.editor.zoom + 0.05);
  }

  public zoomOut(): void {
    this.setZoom(this.editor.zoom - 0.05);
  }

  public zoomToFit(): void {
    if (!this.editor.definition || this.editor.definition.nodes.length === 0)
      return;

    const editor = this.editor.querySelector('#editor') as HTMLElement;
    if (!editor) return;

    // Calculate bounding box of all content in canvas coordinates
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;

    this.editor.definition.nodes.forEach((node) => {
      const ui = this.editor.definition._ui?.nodes[node.uuid];
      if (!ui?.position) return;
      const el = this.editor.querySelector(
        `[id="${node.uuid}"]`
      ) as HTMLElement;
      if (!el) return;
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      minX = Math.min(minX, ui.position.left);
      minY = Math.min(minY, ui.position.top);
      maxX = Math.max(maxX, ui.position.left + w);
      maxY = Math.max(maxY, ui.position.top + h);
    });

    const stickies = this.editor.definition._ui?.stickies || {};
    Object.entries(stickies).forEach(([uuid, sticky]) => {
      if (!sticky.position) return;
      const el = this.editor.querySelector(
        `temba-sticky-note[uuid="${uuid}"]`
      ) as HTMLElement;
      if (!el) return;
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      minX = Math.min(minX, sticky.position.left);
      minY = Math.min(minY, sticky.position.top);
      maxX = Math.max(maxX, sticky.position.left + w);
      maxY = Math.max(maxY, sticky.position.top + h);
    });

    if (minX === Infinity) return;

    const contentWidth = maxX - minX;
    const contentHeight = maxY - minY;
    const padding = 40;

    const availWidth = editor.clientWidth - padding * 2;
    const availHeight = editor.clientHeight - padding * 2;

    const scaleX = availWidth / contentWidth;
    const scaleY = availHeight / contentHeight;
    let fitZoom = Math.min(scaleX, scaleY, 1.0);
    fitZoom = Math.max(fitZoom, 0.3);
    fitZoom = Math.round(fitZoom * 20) / 20; // round to nearest 0.05

    this.editor.zoom = fitZoom;
    this.editor.plumber.zoom = fitZoom;
    this.zoomFitted = true;
    this.editor.requestUpdate();
    this.editor.saveFlowSetting('zoom', fitZoom);

    // Center of content in canvas coordinates, plus grid/canvas margin offset
    const centerX = (minX + maxX) / 2 + 40;
    const centerY = (minY + maxY) / 2 + 40;

    requestAnimationFrame(() => {
      editor.scrollLeft = centerX * fitZoom - editor.clientWidth / 2;
      editor.scrollTop = centerY * fitZoom - editor.clientHeight / 2;
      this.editor.plumber.repaintEverything();
    });
  }

  public zoomToFull(): void {
    this.setZoom(1.0);
  }

  public handleWheel(event: WheelEvent): void {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();

    const delta = event.deltaY > 0 ? -0.05 : 0.05;
    this.setZoom(this.editor.zoom + delta, {
      clientX: event.clientX,
      clientY: event.clientY
    });
  }

  public restoreInitialZoomFromSettings(): void {
    if (this.zoomInitialized || !this.editor.definition) {
      return;
    }

    const savedZoom = this.editor.getFlowSetting<number>('zoom');
    if (typeof savedZoom === 'number' && Number.isFinite(savedZoom)) {
      const clamped = Math.max(
        0.3,
        Math.min(1.0, Math.round(savedZoom * 100) / 100)
      );
      this.editor.zoom = clamped;
      if (this.editor.plumber) {
        this.editor.plumber.zoom = clamped;
      }
    }
    this.zoomInitialized = true;
    this.editor.requestUpdate();
  }

  /** Adjust floating tab positioning relative to toolbar and editor scrollbar */
  public updateZoomControlPositioning(): void {
    requestAnimationFrame(() => {
      const editor = this.editor.querySelector('#editor') as HTMLElement;
      if (editor) {
        const scrollbarWidth = Math.max(
          editor.offsetWidth - editor.clientWidth,
          0
        );
        // Keep floating tabs just left of the vertical scrollbar.
        document.documentElement.style.setProperty(
          '--floating-tab-clip',
          `${scrollbarWidth}px`
        );
      }

      const toolbar = this.editor.querySelector(
        '.editor-toolbar'
      ) as HTMLElement;
      if (toolbar) {
        const rect = toolbar.getBoundingClientRect();
        FloatingTab.START_TOP = rect.bottom + 20;
        FloatingTab.updateAllPositions();
      }
    });
  }

  // --- Loupe magnifier ---

  public initLoupe(): void {
    document.addEventListener('mousemove', this.boundLoupeMouseMove);
    document.addEventListener('keydown', this.boundLoupeKeyDown);
    document.addEventListener('keyup', this.boundLoupeKeyUp);
    document.addEventListener('mouseup', this.boundLoupeMouseUp);
    // Capture-phase listener catches all mousedowns (including those where
    // Plumber calls stopPropagation, e.g. exits and connection re-routing)
    const editor = this.editor.querySelector('#editor') as HTMLElement;
    if (editor) {
      editor.addEventListener('mousedown', this.boundLoupeMouseDown, true);
    }
  }

  public teardownLoupe(): void {
    document.removeEventListener('mousemove', this.boundLoupeMouseMove);
    document.removeEventListener('keydown', this.boundLoupeKeyDown);
    document.removeEventListener('keyup', this.boundLoupeKeyUp);
    document.removeEventListener('mouseup', this.boundLoupeMouseUp);
    const editor = this.editor.querySelector('#editor') as HTMLElement;
    if (editor) {
      editor.removeEventListener('mousedown', this.boundLoupeMouseDown, true);
    }
    this.hideLoupe();
  }

  public setLoupeElements(
    loupeEl: HTMLElement | null,
    loupeContentEl: HTMLElement | null
  ): void {
    this.loupeEl = loupeEl;
    this.loupeContentEl = loupeContentEl;
  }

  public isDialogOrMenuOpen(): boolean {
    if (this.editor.editingNode || this.editor.editingAction) return true;
    if (this.editor.deleteDialog?.open) return true;
    const canvasMenu = this.editor.querySelector('temba-canvas-menu') as any;
    if (canvasMenu?.open) return true;
    return false;
  }

  public get isZoomFitted(): boolean {
    return this.zoomFitted;
  }

  public get isZoomInitialized(): boolean {
    return this.zoomInitialized;
  }

  // --- Private loupe helpers ---

  private handleLoupeKeyDown(event: KeyboardEvent): void {
    // Cmd+Ctrl+A (Mac) / Ctrl+Meta+A (Windows)
    if (event.key.toLowerCase() !== 'a') return;
    if (event.metaKey && event.ctrlKey) {
      event.preventDefault();
      this.loupeKeyHeld = true;
      // Show loupe immediately at last known mouse position
      if (this.loupeLastMouse) {
        this.handleLoupeMouseMove(this.loupeLastMouse as MouseEvent);
      }
    }
  }

  private handleLoupeKeyUp(event: KeyboardEvent): void {
    if (!this.loupeKeyHeld) return;
    // Hide when any modifier is released
    if (event.key === 'a' || event.key === 'Meta' || event.key === 'Control') {
      this.loupeKeyHeld = false;
      this.hideLoupe();
    }
  }

  private handleLoupeMouseDown(): void {
    this.loupeMouseIsDown = true;
    this.hideLoupe();
  }

  private handleLoupeMouseUp(): void {
    this.loupeMouseIsDown = false;
  }

  private handleLoupeMouseMove(event: MouseEvent): void {
    this.loupeLastMouse = { clientX: event.clientX, clientY: event.clientY };

    // Require Cmd+Ctrl+A held, hide while mouse is down, during interactions, or with dialogs open
    if (
      !this.loupeKeyHeld ||
      this.loupeMouseIsDown ||
      this.editor.isDragging ||
      this.editor.isSelecting ||
      this.editor.plumber?.connectionDragging ||
      this.isDialogOrMenuOpen()
    ) {
      this.hideLoupe();
      return;
    }

    // Check if cursor is within the editor bounds
    const editor = this.editor.querySelector('#editor') as HTMLElement;
    if (!editor) return;
    const rect = editor.getBoundingClientRect();
    if (
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom
    ) {
      this.hideLoupe();
      return;
    }

    if (this.loupeRAF) cancelAnimationFrame(this.loupeRAF);
    this.loupeRAF = requestAnimationFrame(() => {
      this.updateLoupe(event.clientX, event.clientY);
    });
  }

  private hideLoupe(): void {
    if (this.loupeEl) {
      this.loupeEl.classList.remove('visible');
    }
    this.restoreTitles();
    if (this.loupeClone) {
      this.loupeClone.remove();
      this.loupeClone = null;
    }
    if (this.loupeRAF) {
      cancelAnimationFrame(this.loupeRAF);
      this.loupeRAF = null;
    }
  }

  private suppressTitles(): void {
    this.hiddenTitles = [];
    const canvas = this.editor.querySelector('#canvas');
    if (!canvas) return;
    for (const el of canvas.querySelectorAll('[title]')) {
      this.hiddenTitles.push({ el, title: el.getAttribute('title')! });
      el.removeAttribute('title');
    }
    // Also check shadow DOMs of canvas nodes and sticky notes
    for (const node of canvas.querySelectorAll(
      'temba-canvas-node, temba-sticky-note'
    )) {
      if (node.shadowRoot) {
        for (const el of node.shadowRoot.querySelectorAll('[title]')) {
          this.hiddenTitles.push({ el, title: el.getAttribute('title')! });
          el.removeAttribute('title');
        }
      }
    }
  }

  private restoreTitles(): void {
    for (const { el, title } of this.hiddenTitles) {
      el.setAttribute('title', title);
    }
    this.hiddenTitles = [];
  }

  private rebuildLoupeClone(
    canvas: HTMLElement,
    canvasX: number,
    canvasY: number,
    visibleRadius: number
  ): void {
    const contentEl = this.loupeContentEl;
    if (!contentEl) return;

    if (this.loupeClone) {
      this.loupeClone.remove();
    }

    const clone = document.createElement('div');
    clone.className = 'loupe-clone';
    clone.style.width = `${canvas.scrollWidth}px`;
    clone.style.height = `${canvas.scrollHeight}px`;

    const pad = 50; // extra padding for partially visible elements

    // Clone only nearby nodes (light DOM -- innerHTML captures rendered content)
    const nodeEls = canvas.querySelectorAll('[data-node-uuid]');
    for (const el of nodeEls) {
      const htmlEl = el as HTMLElement;
      const left = parseFloat(htmlEl.style.left) || 0;
      const top = parseFloat(htmlEl.style.top) || 0;
      const w = htmlEl.offsetWidth;
      const h = htmlEl.offsetHeight;

      // Bounding-box vs visible circle check
      if (
        left + w < canvasX - visibleRadius - pad ||
        left > canvasX + visibleRadius + pad ||
        top + h < canvasY - visibleRadius - pad ||
        top > canvasY + visibleRadius + pad
      )
        continue;

      // Wrap innerHTML in a plain div to avoid custom element upgrade
      const div = document.createElement('div');
      div.className = htmlEl.className;
      div.style.cssText = htmlEl.style.cssText;
      div.innerHTML = htmlEl.innerHTML;
      clone.appendChild(div);
    }

    // Clone SVG connections (standard elements, no upgrade issue)
    const svgs = canvas.querySelectorAll('svg.plumb-connector');
    for (const svg of svgs) {
      clone.appendChild(svg.cloneNode(true));
    }

    // Clone activity overlays
    const overlays = canvas.querySelectorAll('.activity-overlay');
    for (const overlay of overlays) {
      clone.appendChild(overlay.cloneNode(true));
    }

    // Clone sticky notes from their shadow DOM
    const stickyEls = canvas.querySelectorAll('temba-sticky-note');
    for (const el of stickyEls) {
      const stickyEl = el as HTMLElement;
      const sw = stickyEl.offsetWidth;
      const sh = stickyEl.offsetHeight;
      const left = parseFloat(stickyEl.style.left) || 0;
      const top = parseFloat(stickyEl.style.top) || 0;

      if (
        left + sw < canvasX - visibleRadius - pad ||
        left > canvasX + visibleRadius + pad ||
        top + sh < canvasY - visibleRadius - pad ||
        top > canvasY + visibleRadius + pad
      )
        continue;

      if (!stickyEl.shadowRoot) continue;

      const div = document.createElement('div');
      div.className = stickyEl.className;
      div.style.cssText = stickyEl.style.cssText;
      // Extract adopted stylesheets from the shadow root (Lit uses these
      // instead of inline <style> tags), scoping all rules under .loupe-sticky
      // to prevent them from leaking into the light DOM
      div.classList.add('loupe-sticky');
      const sheets = stickyEl.shadowRoot.adoptedStyleSheets;
      let cssText = '';
      for (const sheet of sheets) {
        for (const rule of sheet.cssRules) {
          const ruleText = rule.cssText;
          if (ruleText.startsWith(':host')) {
            cssText += ruleText.replace(/:host/g, '.loupe-sticky') + '\n';
          } else {
            // Scope non-:host rules under .loupe-sticky
            const braceIdx = ruleText.indexOf('{');
            if (braceIdx !== -1) {
              const selector = ruleText.substring(0, braceIdx).trim();
              const body = ruleText.substring(braceIdx);
              cssText += `.loupe-sticky ${selector} ${body}\n`;
            }
          }
        }
      }
      div.innerHTML =
        `<style>${cssText}</style>` + stickyEl.shadowRoot.innerHTML;
      clone.appendChild(div);
    }

    contentEl.appendChild(clone);
    this.loupeClone = clone;
  }

  private updateLoupe(clientX: number, clientY: number): void {
    const loupeEl = this.loupeEl;
    const contentEl = this.loupeContentEl;
    if (!loupeEl || !contentEl || !this.editor.definition) return;

    const canvas = this.editor.querySelector('#canvas') as HTMLElement;
    if (!canvas) return;
    const canvasRect = canvas.getBoundingClientRect();

    // Canvas coordinates under cursor
    const canvasX = (clientX - canvasRect.left) / this.editor.zoom;
    const canvasY = (clientY - canvasRect.top) / this.editor.zoom;

    const D = ZoomManager.LOUPE_DIAMETER;
    const R = D / 2;
    // Show content at a fixed comfortable scale inside the loupe
    const loupeScale = Math.min(1.5, this.editor.zoom * 2.5);
    const visibleRadius = R / loupeScale;

    // Position loupe at cursor
    loupeEl.style.left = `${clientX}px`;
    loupeEl.style.top = `${clientY}px`;
    loupeEl.classList.add('visible');
    if (this.hiddenTitles.length === 0) {
      this.suppressTitles();
    }

    // Grid background
    const bgSize = 20 * loupeScale;
    contentEl.style.backgroundSize = `${bgSize}px ${bgSize}px`;
    contentEl.style.backgroundPosition = `${R - canvasX * loupeScale}px ${R - canvasY * loupeScale}px`;

    // Rebuild clone periodically or when cursor has moved significantly
    const now = performance.now();
    const dx = canvasX - this.loupeCursorCanvas.x;
    const dy = canvasY - this.loupeCursorCanvas.y;
    const moved =
      Math.abs(dx) > visibleRadius * 0.5 || Math.abs(dy) > visibleRadius * 0.5;

    if (
      !this.loupeClone ||
      (now - this.loupeCloneTime > ZoomManager.LOUPE_CLONE_INTERVAL && moved)
    ) {
      this.rebuildLoupeClone(canvas, canvasX, canvasY, visibleRadius);
      this.loupeCloneTime = now;
      this.loupeCursorCanvas = { x: canvasX, y: canvasY };
    }

    // Position the clone so the canvas point under the cursor is at the loupe center
    if (this.loupeClone) {
      this.loupeClone.style.transform = `translate(${R - canvasX * loupeScale}px, ${R - canvasY * loupeScale}px) scale(${loupeScale})`;
    }
  }
}
