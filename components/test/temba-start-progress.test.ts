import '../temba-modules';
import { fixture, expect } from '@open-wc/testing';
import { useFakeTimers } from 'sinon';
import { StartProgress } from '../src/live/StartProgress';
import { mockGET, clearMockGets, waitForCondition } from './utils.test';

const STATUS_URL = '/api/v2/flow_starts.json';

// a flow start payload as returned by the status endpoint
const start = (overrides: any = {}) => ({
  status: 'Started',
  modified_on: new Date().toISOString(),
  progress: { current: 10, total: 100 },
  ...overrides
});

const mockStatus = (results: any[]) => {
  clearMockGets();
  mockGET(/flow_starts\.json/, { results, next: null });
};

const createProgress = async (id = 'start-1'): Promise<StartProgress> => {
  const progress = (await fixture(
    `<temba-start-progress statusEndpoint="${STATUS_URL}"></temba-start-progress>`
  )) as StartProgress;
  // assigning id is what kicks off the first refresh
  progress.id = id;
  await progress.updateComplete;
  // let the fetch promise chain settle
  await new Promise((resolve) => setTimeout(resolve, 0));
  return progress;
};

describe('temba-start-progress', () => {
  afterEach(() => {
    clearMockGets();
  });

  describe('refresh', () => {
    it('pulls progress counts from the status endpoint', async () => {
      mockStatus([start({ progress: { current: 25, total: 200 } })]);
      const progress = await createProgress();
      expect(progress.current).to.equal(25);
      expect(progress.total).to.equal(200);
      expect(progress.refreshes).to.equal(1);
    });

    it('does nothing when the endpoint returns no starts', async () => {
      mockStatus([]);
      const progress = await createProgress();
      expect(progress.refreshes).to.equal(0);
      expect(progress.current).to.equal(undefined);
    });

    it('marks a started run as running', async () => {
      mockStatus([start({ status: 'Started' })]);
      const progress = await createProgress();
      expect(progress.running).to.equal(true);
      expect(progress.complete).to.equal(false);
      expect(progress.message).to.equal(null);
    });

    it('shows a preparing message while pending', async () => {
      mockStatus([start({ status: 'Pending' })]);
      const progress = await createProgress();
      expect(progress.message).to.equal('Preparing to start..');
      expect(progress.running).to.equal(false);
    });

    it('shows a waiting message while queued', async () => {
      mockStatus([start({ status: 'Queued' })]);
      const progress = await createProgress();
      expect(progress.message).to.equal('Waiting..');
    });

    for (const status of ['Completed', 'Failed', 'Interrupted']) {
      it(`treats ${status} as complete`, async () => {
        mockStatus([start({ status, progress: { current: 100, total: 100 } })]);
        const progress = await createProgress();
        expect(progress.complete).to.equal(true);
        expect(progress.running).to.equal(false);
      });
    }

    it('estimates an eta once progress is underway', async () => {
      mockStatus([
        start({
          status: 'Started',
          modified_on: new Date(Date.now() - 1000).toISOString(),
          progress: { current: 1000, total: 2000 }
        })
      ]);
      const progress = await createProgress();
      expect(progress.eta).to.be.a('string');
      // the eta is in the near future, not the past
      expect(new Date(progress.eta).getTime()).to.be.greaterThan(
        Date.now() - 1000
      );
    });

    it('skips an eta that is months away', async () => {
      mockStatus([
        start({
          status: 'Started',
          modified_on: new Date(Date.now() - 1000).toISOString(),
          progress: { current: 1000, total: 10000000000 }
        })
      ]);
      const progress = await createProgress();
      expect(progress.eta).to.equal(null);
    });

    it('skips the eta when the rate is too low to be meaningful', async () => {
      mockStatus([
        start({
          status: 'Started',
          modified_on: new Date(Date.now() - 1000000).toISOString(),
          progress: { current: 1, total: 100 }
        })
      ]);
      const progress = await createProgress();
      expect(progress.eta).to.equal(undefined);
    });
  });

  describe('polling', () => {
    it('schedules another refresh while work remains', async () => {
      mockStatus([
        start({ status: 'Started', progress: { current: 10, total: 100 } })
      ]);
      const progress = await createProgress();
      expect(progress.refreshes).to.equal(1);

      // the follow-up completes, so polling stops after one more round
      mockStatus([
        start({ status: 'Completed', progress: { current: 100, total: 100 } })
      ]);

      // the backoff after the first refresh is 1s; poll for the follow-up
      // rather than sleeping a fixed margin, which goes flaky under load
      await waitForCondition(() => progress.refreshes > 1, 60, 50);
      expect(progress.refreshes).to.equal(2);
      expect(progress.complete).to.equal(true);
    });

    it('stops polling once the work is complete', async () => {
      mockStatus([
        start({ status: 'Completed', progress: { current: 100, total: 100 } })
      ]);
      const progress = await createProgress();
      const after = progress.refreshes;

      await new Promise((resolve) => setTimeout(resolve, 20));
      expect(progress.refreshes).to.equal(after);
    });
  });

  describe('scheduleRemoval', () => {
    it('removes itself from the DOM after a delay', async () => {
      mockStatus([]);
      const progress = await createProgress();
      const parent = progress.parentElement;
      expect(parent.contains(progress)).to.equal(true);

      const clock = useFakeTimers();
      try {
        progress.scheduleRemoval();
        expect(parent.contains(progress)).to.equal(true);
        clock.tick(5000);
      } finally {
        clock.restore();
      }
      expect(parent.contains(progress)).to.equal(false);
    });
  });

  describe('interrupting', () => {
    it('opens the interrupt dialog', async () => {
      mockStatus([]);
      const progress = await createProgress();
      progress.interruptTitle = 'Stop this start';
      progress.interruptEndpoint = '/flow_start/interrupt/1/';

      const opened: any[] = [];
      const original = (window as any).showModax;
      (window as any).showModax = (title: string, endpoint: string) =>
        opened.push({ title, endpoint });
      try {
        progress.interruptStart();
      } finally {
        (window as any).showModax = original;
      }

      expect(opened).to.deep.equal([
        { title: 'Stop this start', endpoint: '/flow_start/interrupt/1/' }
      ]);
    });

    it('offers an interrupt control only while running', async () => {
      mockStatus([start({ status: 'Started' })]);
      const progress = await createProgress();
      progress.interruptTitle = 'Stop';
      progress.interruptEndpoint = '/interrupt/';
      await progress.updateComplete;
      expect(
        progress.shadowRoot.querySelector('temba-icon[name="close"]')
      ).to.not.equal(null);
    });

    it('hides the interrupt control when not running', async () => {
      mockStatus([start({ status: 'Completed' })]);
      const progress = await createProgress();
      progress.interruptTitle = 'Stop';
      progress.interruptEndpoint = '/interrupt/';
      await progress.updateComplete;
      expect(
        progress.shadowRoot.querySelector('temba-icon[name="close"]')
      ).to.equal(null);
    });

    it('hides the interrupt control with no endpoint configured', async () => {
      mockStatus([start({ status: 'Started' })]);
      const progress = await createProgress();
      await progress.updateComplete;
      expect(
        progress.shadowRoot.querySelector('temba-icon[name="close"]')
      ).to.equal(null);
    });
  });
});
