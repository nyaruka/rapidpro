import '../temba-modules';
import { fixture, expect } from '@open-wc/testing';
import { Plumber } from '../src/flow/Plumber';
import { mockPOST, clearMockPosts } from './utils.test';

// fetchRecentContacts calls fetch with only an AbortSignal, so the shared
// fetch mock (which keys off options.method) looks the request up in its
// non-GET list - hence mockPOST here for what is really a GET
const mockRecentContacts = (body: any, status = '200') =>
  mockPOST(/recent_contacts/, body, {}, status);

const FLOW_UUID = 'flow-uuid-1';

const createPlumber = async (editor: any = {}) => {
  const canvas = (await fixture('<div class="canvas"></div>')) as HTMLElement;
  return new Plumber(canvas, editor);
};

const withDefinition = () => ({ definition: { uuid: FLOW_UUID } });

const settle = () => new Promise((resolve) => setTimeout(resolve, 10));

describe('flow/Plumber overlays', () => {
  afterEach(() => {
    clearMockPosts();
    document
      .querySelectorAll('.recent-contacts-popup')
      .forEach((el) => el.remove());
  });

  describe('getFlowUuid', () => {
    it('reads the uuid from the editor definition', async () => {
      const plumber = await createPlumber(withDefinition());
      expect((plumber as any).getFlowUuid()).to.equal(FLOW_UUID);
    });

    it('returns null without a definition', async () => {
      const plumber = await createPlumber({});
      expect((plumber as any).getFlowUuid()).to.equal(null);
    });

    it('returns null without an editor', async () => {
      const plumber = await createPlumber(null);
      expect((plumber as any).getFlowUuid()).to.equal(null);
    });
  });

  describe('createOverlayElement', () => {
    it('renders the activity count', async () => {
      const plumber = await createPlumber(withDefinition());
      const overlay = (plumber as any).createOverlayElement(5, 'exit-1:node-2');
      expect(overlay.className).to.equal('activity-overlay');
      expect(overlay.textContent).to.equal('5');
      expect(overlay.getAttribute('data-activity-key')).to.equal(
        'exit-1:node-2'
      );
    });

    it('formats large counts with separators', async () => {
      const plumber = await createPlumber(withDefinition());
      const overlay = (plumber as any).createOverlayElement(
        12345,
        'exit-1:node-2'
      );
      expect(overlay.textContent).to.equal((12345).toLocaleString());
    });
  });

  describe('findOverlayForActivityKey', () => {
    it('finds the overlay carrying the key', async () => {
      const plumber = await createPlumber(withDefinition());
      const first = (plumber as any).createOverlayElement(1, 'exit-1:node-2');
      const second = (plumber as any).createOverlayElement(2, 'exit-3:node-4');
      (plumber as any).overlays.set('exit-1', first);
      (plumber as any).overlays.set('exit-3', second);

      expect(
        (plumber as any).findOverlayForActivityKey('exit-3:node-4')
      ).to.equal(second);
    });

    it('returns null when no overlay matches', async () => {
      const plumber = await createPlumber(withDefinition());
      expect((plumber as any).findOverlayForActivityKey('nonsense')).to.equal(
        null
      );
    });
  });

  describe('fetchRecentContacts', () => {
    const ACTIVITY_KEY = 'exit-1:node-2';

    it('caches the contacts it fetches', async () => {
      mockRecentContacts([
        { contact: { uuid: 'c1', name: 'Ann' }, operand: 'red', time: null }
      ]);
      const plumber = await createPlumber(withDefinition());

      await (plumber as any).fetchRecentContacts(ACTIVITY_KEY, FLOW_UUID);

      expect((plumber as any).recentContactsCache[ACTIVITY_KEY]).to.have.length(
        1
      );
      expect(
        (plumber as any).recentContactsCache[ACTIVITY_KEY][0].contact.name
      ).to.equal('Ann');
    });

    it('does not refetch what it already has', async () => {
      const plumber = await createPlumber(withDefinition());
      (plumber as any).recentContactsCache[ACTIVITY_KEY] = ['cached'];

      // no mock is registered, so a real fetch would fail the test
      await (plumber as any).fetchRecentContacts(ACTIVITY_KEY, FLOW_UUID);
      expect((plumber as any).recentContactsCache[ACTIVITY_KEY]).to.deep.equal([
        'cached'
      ]);
    });

    it('clears the pending marker once done', async () => {
      mockRecentContacts([]);
      const plumber = await createPlumber(withDefinition());
      await (plumber as any).fetchRecentContacts(ACTIVITY_KEY, FLOW_UUID);
      expect((plumber as any).pendingFetches[ACTIVITY_KEY]).to.equal(undefined);
    });

    it('survives a failed request', async () => {
      mockRecentContacts({ detail: 'boom' }, '500');
      const plumber = await createPlumber(withDefinition());

      await (plumber as any).fetchRecentContacts(ACTIVITY_KEY, FLOW_UUID);

      expect((plumber as any).recentContactsCache[ACTIVITY_KEY]).to.equal(
        undefined
      );
      expect((plumber as any).pendingFetches[ACTIVITY_KEY]).to.equal(undefined);
    });
  });

  describe('renderRecentContactsPopup', () => {
    const popupFor = async (contacts: any[]) => {
      const plumber = await createPlumber(withDefinition());
      const popup = document.createElement('div');
      (plumber as any).recentContactsPopup = popup;
      (plumber as any).renderRecentContactsPopup(contacts);
      return popup;
    };

    it('reports when there is nothing to show', async () => {
      const popup = await popupFor([]);
      expect(popup.innerHTML).to.contain('No Recent Contacts');
    });

    it('lists each contact', async () => {
      const popup = await popupFor([
        { contact: { uuid: 'c1', name: 'Ann' } },
        { contact: { uuid: 'c2', name: 'Bo' } }
      ]);
      expect(popup.querySelectorAll('.contact-row')).to.have.length(2);
      expect(popup.textContent).to.contain('Ann');
      expect(popup.textContent).to.contain('Bo');
      expect(
        popup.querySelector('.contact-name').getAttribute('data-uuid')
      ).to.equal('c1');
    });

    it('shows the matching operand when there is one', async () => {
      const popup = await popupFor([
        { contact: { uuid: 'c1', name: 'Ann' }, operand: 'red' }
      ]);
      expect(popup.querySelector('.contact-operand').textContent).to.equal(
        'red'
      );
    });

    it('omits the operand when there is none', async () => {
      const popup = await popupFor([{ contact: { uuid: 'c1', name: 'Ann' } }]);
      expect(popup.querySelector('.contact-operand')).to.equal(null);
    });

    it('describes recent times in minutes', async () => {
      const popup = await popupFor([
        {
          contact: { uuid: 'c1', name: 'Ann' },
          time: new Date(Date.now() - 5 * 60000).toISOString()
        }
      ]);
      expect(popup.querySelector('.contact-time').textContent).to.equal(
        '5m ago'
      );
    });

    it('describes very recent times as just now', async () => {
      const popup = await popupFor([
        {
          contact: { uuid: 'c1', name: 'Ann' },
          time: new Date().toISOString()
        }
      ]);
      expect(popup.querySelector('.contact-time').textContent).to.equal(
        'just now'
      );
    });

    it('describes older times in hours and days', async () => {
      const hours = await popupFor([
        {
          contact: { uuid: 'c1', name: 'Ann' },
          time: new Date(Date.now() - 3 * 3600000).toISOString()
        }
      ]);
      expect(hours.querySelector('.contact-time').textContent).to.equal(
        '3h ago'
      );

      const days = await popupFor([
        {
          contact: { uuid: 'c1', name: 'Ann' },
          time: new Date(Date.now() - 2 * 86400000).toISOString()
        }
      ]);
      expect(days.querySelector('.contact-time').textContent).to.equal(
        '2d ago'
      );
    });

    it('does nothing without a popup element', async () => {
      const plumber = await createPlumber(withDefinition());
      // no throw is the assertion here
      (plumber as any).renderRecentContactsPopup([]);
    });
  });

  describe('showRecentContacts', () => {
    const ACTIVITY_KEY = 'exit-1:node-2';

    it('does nothing when there is no matching overlay', async () => {
      const plumber = await createPlumber(withDefinition());
      await (plumber as any).showRecentContacts(ACTIVITY_KEY, FLOW_UUID);
      expect((plumber as any).recentContactsPopup).to.equal(null);
    });

    it('creates and positions a popup beneath the overlay', async () => {
      mockRecentContacts([{ contact: { uuid: 'c1', name: 'Ann' } }]);
      const plumber = await createPlumber(withDefinition());

      const overlay = (plumber as any).createOverlayElement(3, ACTIVITY_KEY);
      document.body.appendChild(overlay);
      (plumber as any).overlays.set('exit-1', overlay);

      try {
        await (plumber as any).fetchRecentContacts(ACTIVITY_KEY, FLOW_UUID);
        await (plumber as any).showRecentContacts(ACTIVITY_KEY, FLOW_UUID);
        await settle();

        const popup = (plumber as any).recentContactsPopup as HTMLElement;
        expect(popup).to.not.equal(null);
        expect(popup.className).to.contain('recent-contacts-popup');
        expect(popup.style.position).to.equal('absolute');
        expect(popup.textContent).to.contain('Ann');
        expect((plumber as any).hoveredActivityKey).to.equal(ACTIVITY_KEY);
      } finally {
        overlay.remove();
      }
    });
  });

  describe('positionPopup', () => {
    it('places the popup just below the overlay', async () => {
      const plumber = await createPlumber(withDefinition());
      const popup = document.createElement('div');
      (plumber as any).recentContactsPopup = popup;
      document.body.appendChild(popup);

      const overlay = document.createElement('div');
      overlay.style.position = 'absolute';
      overlay.style.left = '40px';
      overlay.style.top = '60px';
      overlay.style.width = '20px';
      overlay.style.height = '10px';
      document.body.appendChild(overlay);

      try {
        (plumber as any).positionPopup(overlay);
        const rect = overlay.getBoundingClientRect();
        expect(popup.style.left).to.equal(`${rect.left + window.scrollX}px`);
        expect(popup.style.top).to.equal(
          `${rect.bottom + window.scrollY + 5}px`
        );
        expect(popup.classList.contains('show')).to.equal(true);
      } finally {
        overlay.remove();
        popup.remove();
      }
    });

    it('does nothing without a popup', async () => {
      const plumber = await createPlumber(withDefinition());
      // no throw is the assertion here
      (plumber as any).positionPopup(document.createElement('div'));
    });
  });

  describe('removeAllEndpoints', () => {
    it('unregisters the source for each exit of a node', async () => {
      const plumber = await createPlumber(withDefinition());

      const nodeEl = document.createElement('div');
      nodeEl.id = 'node-1';
      const exitOne = document.createElement('div');
      exitOne.className = 'exit';
      exitOne.id = 'exit-1';
      const exitTwo = document.createElement('div');
      exitTwo.className = 'exit';
      exitTwo.id = 'exit-2';
      nodeEl.appendChild(exitOne);
      nodeEl.appendChild(exitTwo);
      document.body.appendChild(nodeEl);

      const cleaned: string[] = [];
      (plumber as any).sources.set('exit-1', () => cleaned.push('exit-1'));
      (plumber as any).sources.set('exit-2', () => cleaned.push('exit-2'));
      (plumber as any).sources.set('other', () => cleaned.push('other'));

      try {
        plumber.removeAllEndpoints('node-1');

        expect(cleaned.sort()).to.deep.equal(['exit-1', 'exit-2']);
        expect((plumber as any).sources.has('exit-1')).to.equal(false);
        expect((plumber as any).sources.has('other')).to.equal(true);
      } finally {
        nodeEl.remove();
      }
    });

    it('does nothing for a node that is not on the page', async () => {
      const plumber = await createPlumber(withDefinition());
      // no throw is the assertion here
      plumber.removeAllEndpoints('missing-node');
    });
  });
});
