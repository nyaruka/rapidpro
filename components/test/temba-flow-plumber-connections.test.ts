import { expect } from '@open-wc/testing';
import { stub, useFakeTimers, SinonFakeTimers } from 'sinon';
import { Plumber } from '../src/flow/Plumber';

describe('Plumber - Connection Management', () => {
  let plumber: Plumber;
  let mockCanvas: HTMLElement;
  let clock: SinonFakeTimers;

  beforeEach(() => {
    clock = useFakeTimers();

    mockCanvas = document.createElement('div');
    mockCanvas.id = 'canvas';
    document.body.appendChild(mockCanvas);

    const mockEditor = { fireCustomEvent: stub() };
    plumber = new Plumber(mockCanvas, mockEditor);
  });

  afterEach(() => {
    mockCanvas.remove();
    clock.restore();
  });

  describe('setConnectionRemovingState', () => {
    it('returns false when no connection exists for the exit', () => {
      const result = plumber.setConnectionRemovingState('nonexistent', true);
      expect(result).to.be.false;
    });

    it('adds removing class when isRemoving is true', () => {
      // Create mock elements for a connection
      const exitEl = document.createElement('div');
      exitEl.id = 'exit-1';
      const targetEl = document.createElement('div');
      targetEl.id = 'target-1';
      mockCanvas.appendChild(exitEl);
      mockCanvas.appendChild(targetEl);

      // Create a connection
      plumber.connectIds('node-1', 'exit-1', 'target-1');
      clock.tick(16);

      const result = plumber.setConnectionRemovingState('exit-1', true);
      expect(result).to.be.true;

      const conn = (plumber as any).connections.get('exit-1');
      expect(conn.svgEl.classList.contains('removing')).to.be.true;

      exitEl.remove();
      targetEl.remove();
    });

    it('removes removing class when isRemoving is false', () => {
      const exitEl = document.createElement('div');
      exitEl.id = 'exit-2';
      const targetEl = document.createElement('div');
      targetEl.id = 'target-2';
      mockCanvas.appendChild(exitEl);
      mockCanvas.appendChild(targetEl);

      plumber.connectIds('node-1', 'exit-2', 'target-2');
      clock.tick(16);

      plumber.setConnectionRemovingState('exit-2', true);
      plumber.setConnectionRemovingState('exit-2', false);

      const conn = (plumber as any).connections.get('exit-2');
      expect(conn.svgEl.classList.contains('removing')).to.be.false;

      exitEl.remove();
      targetEl.remove();
    });
  });

  describe('removeExitConnection', () => {
    it('removes a connection for an exit', () => {
      const exitEl = document.createElement('div');
      exitEl.id = 'exit-3';
      const targetEl = document.createElement('div');
      targetEl.id = 'target-3';
      mockCanvas.appendChild(exitEl);
      mockCanvas.appendChild(targetEl);

      plumber.connectIds('node-1', 'exit-3', 'target-3');
      clock.tick(16);

      expect((plumber as any).connections.has('exit-3')).to.be.true;

      const result = plumber.removeExitConnection('exit-3');
      expect(result).to.be.true;
      expect((plumber as any).connections.has('exit-3')).to.be.false;

      exitEl.remove();
      targetEl.remove();
    });

    it('returns false when no connection exists', () => {
      const result = plumber.removeExitConnection('nonexistent');
      expect(result).to.be.false;
    });
  });

  describe('connectIds and processPendingConnections', () => {
    it('adds connection to pending connections', () => {
      plumber.connectIds('test-node', 'test-from', 'test-to');
      expect((plumber as any).pendingConnections.length).to.equal(1);
    });

    it('clears previous rAF when called multiple times', () => {
      const cancelSpy = stub(window, 'cancelAnimationFrame');
      const rafSpy = stub(window, 'requestAnimationFrame').returns(123 as any);

      plumber.processPendingConnections();
      plumber.processPendingConnections();

      expect(cancelSpy).to.have.been.calledOnce;
      expect(rafSpy).to.have.been.calledTwice;

      cancelSpy.restore();
      rafSpy.restore();
    });
  });

  describe('removeNodeConnections', () => {
    it('removes inbound and outbound connections for a node', () => {
      const exitEl = document.createElement('div');
      exitEl.id = 'exit-4';
      exitEl.classList.add('exit');
      const nodeEl = document.createElement('div');
      nodeEl.id = 'node-1';
      nodeEl.appendChild(exitEl);
      const targetEl = document.createElement('div');
      targetEl.id = 'target-4';
      mockCanvas.appendChild(nodeEl);
      mockCanvas.appendChild(targetEl);

      plumber.connectIds('node-1', 'exit-4', 'target-4');
      clock.tick(16);

      expect((plumber as any).connections.size).to.equal(1);

      plumber.removeNodeConnections('node-1', ['exit-4']);
      expect((plumber as any).connections.size).to.equal(0);

      nodeEl.remove();
      targetEl.remove();
    });
  });
});
