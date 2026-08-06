import '../temba-modules';
import { fixture, expect } from '@open-wc/testing';
import { ShortcutList } from '../src/list/ShortcutList';
import { Store } from '../src/store/Store';
import { CustomEventType, Shortcut } from '../src/interfaces';
import { loadStore } from './utils.test';

const shortcut = (name: string, text: string): Shortcut => ({
  uuid: `uuid-${name.toLowerCase().replace(/\s/g, '-')}`,
  name,
  text,
  modified_on: '2024-01-01T00:00:00Z'
});

const SHORTCUTS = [
  shortcut('Greeting', 'Hello and welcome!'),
  shortcut('Goodbye', 'Thanks for chatting'),
  shortcut('Hours', 'We are open 9 to 5')
];

describe('temba-shortcuts', () => {
  let store: Store;

  beforeEach(async () => {
    store = await loadStore();
    (store as any).shortcuts = SHORTCUTS;
  });

  const createList = async (attrs = ''): Promise<ShortcutList> => {
    const list = (await fixture(
      `<temba-shortcuts ${attrs}></temba-shortcuts>`
    )) as ShortcutList;
    list.storeUpdated();
    await list.updateComplete;
    return list;
  };

  describe('loading', () => {
    it('takes its shortcuts from the store', async () => {
      const list = await createList();
      expect(list.filteredShortcuts).to.have.length(3);
      expect(list.filteredShortcuts[0].name).to.equal('Greeting');
    });

    it('shows an empty state when there are no shortcuts', async () => {
      (store as any).shortcuts = [];
      const list = await createList();
      const message = list.shadowRoot.querySelector('.no-match');
      expect(message).to.not.equal(null);
      expect(message.textContent).to.contain('No shortcuts yet');
    });
  });

  describe('filtering', () => {
    it('narrows the list to matching names', async () => {
      const list = await createList();
      list.filter = 'good';
      await list.updateComplete;
      expect(list.filteredShortcuts).to.have.length(1);
      expect(list.filteredShortcuts[0].name).to.equal('Goodbye');
    });

    it('matches case insensitively', async () => {
      const list = await createList();
      list.filter = 'HOURS';
      await list.updateComplete;
      expect(list.filteredShortcuts).to.have.length(1);
      expect(list.filteredShortcuts[0].name).to.equal('Hours');
    });

    it('matches on the name rather than the body text', async () => {
      const list = await createList();
      list.filter = 'welcome';
      await list.updateComplete;
      expect(list.filteredShortcuts).to.have.length(0);
    });

    it('restores the full list when the filter is cleared', async () => {
      const list = await createList();
      list.filter = 'good';
      await list.updateComplete;
      list.filter = '';
      await list.updateComplete;
      expect(list.filteredShortcuts).to.have.length(3);
    });

    it('reports no matches for an unmatched filter', async () => {
      const list = await createList();
      list.filter = 'nonsense';
      // filteredShortcuts is recomputed in updated(), so the empty state
      // only reaches the DOM on the following render
      await list.updateComplete;
      await list.updateComplete;
      const message = list.shadowRoot.querySelector('.no-match');
      expect(message.textContent).to.contain('No matches for');
      expect(list.shadowRoot.querySelector('.filter').textContent).to.contain(
        'nonsense'
      );
    });

    it('resets the cursor when the filter changes', async () => {
      const list = await createList();
      list.cursorIndex = 2;
      list.filter = 'o';
      await list.updateComplete;
      expect(list.cursorIndex).to.equal(0);
    });
  });

  describe('search box', () => {
    it('is hidden by default', async () => {
      const list = await createList();
      expect(list.shadowRoot.querySelector('.search-box')).to.equal(null);
    });

    it('is shown when requested', async () => {
      const list = await createList('showSearch');
      expect(list.shadowRoot.querySelector('.search-box')).to.not.equal(null);
    });

    it('filters as the user types', async () => {
      const list = await createList('showSearch');
      const input = list.shadowRoot.querySelector(
        '.search-box input'
      ) as HTMLInputElement;
      input.value = 'hours';
      input.dispatchEvent(new Event('input'));
      await list.updateComplete;
      expect(list.filteredShortcuts).to.have.length(1);
      expect(list.filteredShortcuts[0].name).to.equal('Hours');
    });

    it('focuses the input on request', async () => {
      const list = await createList('showSearch');
      const input = list.shadowRoot.querySelector(
        '.search-box input'
      ) as HTMLInputElement;
      list.focusSearch();
      expect(list.shadowRoot.activeElement).to.equal(input);
    });

    it('does nothing when focusing with no search box', async () => {
      const list = await createList();
      // no throw is the assertion here
      list.focusSearch();
    });
  });

  describe('keyboard navigation', () => {
    const press = async (list: ShortcutList, key: string) => {
      const input = list.shadowRoot.querySelector(
        '.search-box input'
      ) as HTMLInputElement;
      input.dispatchEvent(
        new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true })
      );
      await list.updateComplete;
    };

    it('moves the cursor down and stops at the end', async () => {
      const list = await createList('showSearch');
      await press(list, 'ArrowDown');
      expect(list.cursorIndex).to.equal(1);
      await press(list, 'ArrowDown');
      expect(list.cursorIndex).to.equal(2);
      await press(list, 'ArrowDown');
      expect(list.cursorIndex).to.equal(2);
    });

    it('moves the cursor up and stops at the start', async () => {
      const list = await createList('showSearch');
      list.cursorIndex = 1;
      await press(list, 'ArrowUp');
      expect(list.cursorIndex).to.equal(0);
      await press(list, 'ArrowUp');
      expect(list.cursorIndex).to.equal(0);
    });

    it('fires a selection on enter', async () => {
      const list = await createList('showSearch');
      list.cursorIndex = 1;
      const selections: any[] = [];
      list.addEventListener(CustomEventType.Selection, (e: any) =>
        selections.push(e.detail.selected)
      );
      await press(list, 'Enter');
      expect(selections).to.have.length(1);
      expect(selections[0].name).to.equal('Goodbye');
    });

    it('fires nothing on enter with an empty list', async () => {
      (store as any).shortcuts = [];
      const list = await createList('showSearch');
      const selections: any[] = [];
      list.addEventListener(CustomEventType.Selection, (e: any) =>
        selections.push(e.detail.selected)
      );
      await press(list, 'Enter');
      expect(selections).to.have.length(0);
    });

    it('ignores other keys', async () => {
      const list = await createList('showSearch');
      await press(list, 'Escape');
      expect(list.cursorIndex).to.equal(0);
    });
  });

  describe('rendering', () => {
    it('renders the name and body of a shortcut', async () => {
      const list = await createList();
      const rendered = list.renderShortcut(SHORTCUTS[0]);
      const host = (await fixture('<div></div>')) as HTMLElement;
      const { render } = await import('lit-html');
      render(rendered, host);
      expect(host.textContent).to.contain('Greeting');
      expect(host.textContent).to.contain('Hello and welcome!');
    });

    it('returns the shortcut under the cursor', async () => {
      const list = await createList();
      list.cursorIndex = 2;
      await list.updateComplete;
      expect(list.getShortcut().name).to.equal('Hours');
    });
  });
});
