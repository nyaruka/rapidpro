import '../temba-modules';
import { fixture, expect } from '@open-wc/testing';
import { FlowSearch } from '../src/flow/FlowSearch';

const SPANISH = 'spa';

const sendMsg = (uuid: string, text: string, extra: any = {}) => ({
  uuid,
  type: 'send_msg',
  text,
  ...extra
});

const definition = (nodes: any[], overrides: any = {}) => ({
  uuid: 'flow-1',
  name: 'Test Flow',
  language: 'eng',
  type: 'messaging' as const,
  revision: 1,
  spec_version: '14.3',
  localization: {},
  nodes,
  _ui: { nodes: {}, languages: [] },
  ...overrides
});

const createSearch = async (
  def: any,
  { scope = 'table', languageCode = '' } = {}
): Promise<FlowSearch> => {
  const search = (await fixture(
    '<temba-flow-search></temba-flow-search>'
  )) as FlowSearch;
  search.definition = def;
  search.scope = scope as any;
  search.languageCode = languageCode;
  await search.updateComplete;
  return search;
};

// runs a query through the component's own search path
const search = async (element: FlowSearch, query: string) => {
  (element as any).searchQuery = query;
  (element as any).runSearch();
  await element.updateComplete;
  return (element as any).results;
};

describe('temba-flow-search table scope', () => {
  describe('matching message text', () => {
    it('finds an action by its text', async () => {
      const element = await createSearch(
        definition([
          { uuid: 'node-1', actions: [sendMsg('a1', 'Hello there')], exits: [] }
        ])
      );
      const results = await search(element, 'hello');
      expect(results).to.have.length(1);
      expect(results[0].nodeUuid).to.equal('node-1');
      expect(results[0].action.uuid).to.equal('a1');
      expect(results[0].fullText).to.equal('Hello there');
      expect(results[0].matchStart).to.equal(0);
      expect(results[0].matchLength).to.equal(5);
    });

    it('reports where in the text the match falls', async () => {
      const element = await createSearch(
        definition([
          {
            uuid: 'node-1',
            actions: [sendMsg('a1', 'Well hello there')],
            exits: []
          }
        ])
      );
      const results = await search(element, 'hello');
      expect(results[0].matchStart).to.equal(5);
    });

    it('matches case insensitively', async () => {
      const element = await createSearch(
        definition([
          { uuid: 'node-1', actions: [sendMsg('a1', 'HELLO')], exits: [] }
        ])
      );
      expect(await search(element, 'hello')).to.have.length(1);
    });

    it('returns nothing for an unmatched query', async () => {
      const element = await createSearch(
        definition([
          { uuid: 'node-1', actions: [sendMsg('a1', 'Hello')], exits: [] }
        ])
      );
      expect(await search(element, 'nonsense')).to.have.length(0);
    });

    it('returns nothing for an empty query', async () => {
      const element = await createSearch(
        definition([
          { uuid: 'node-1', actions: [sendMsg('a1', 'Hello')], exits: [] }
        ])
      );
      expect(await search(element, '   ')).to.have.length(0);
    });

    it('returns nothing without a definition', async () => {
      const element = await createSearch(null);
      expect(await search(element, 'hello')).to.have.length(0);
    });

    it('finds matches across several nodes', async () => {
      const element = await createSearch(
        definition([
          { uuid: 'node-1', actions: [sendMsg('a1', 'Hello one')], exits: [] },
          { uuid: 'node-2', actions: [sendMsg('a2', 'Hello two')], exits: [] }
        ])
      );
      const results = await search(element, 'hello');
      expect(results.map((r: any) => r.nodeUuid)).to.deep.equal([
        'node-1',
        'node-2'
      ]);
    });

    it('reports one result per action', async () => {
      const element = await createSearch(
        definition([
          {
            uuid: 'node-1',
            actions: [sendMsg('a1', 'hello hello hello')],
            exits: []
          }
        ])
      );
      expect(await search(element, 'hello')).to.have.length(1);
    });
  });

  describe('localizable fields', () => {
    it('searches quick replies', async () => {
      const element = await createSearch(
        definition([
          {
            uuid: 'node-1',
            actions: [
              sendMsg('a1', 'Pick one', { quick_replies: ['Yes', 'Maybe'] })
            ],
            exits: []
          }
        ])
      );
      const results = await search(element, 'maybe');
      expect(results).to.have.length(1);
      expect(results[0].fullText).to.equal('Maybe');
    });

    it('searches every localizable text field of an action', async () => {
      const element = await createSearch(
        definition([
          {
            uuid: 'node-1',
            actions: [
              {
                uuid: 'a1',
                type: 'send_email',
                subject: 'Invoice attached',
                body: 'Please see the attachment'
              }
            ],
            exits: []
          }
        ])
      );
      expect(await search(element, 'invoice')).to.have.length(1);
      expect(await search(element, 'attachment')).to.have.length(1);
    });

    it('skips actions with nothing localizable', async () => {
      const element = await createSearch(
        definition([
          {
            uuid: 'node-1',
            actions: [
              { uuid: 'a1', type: 'set_contact_name', name: 'Hello Bob' }
            ],
            exits: []
          }
        ])
      );
      expect(await search(element, 'hello')).to.have.length(0);
    });

    it('ignores blank field values', async () => {
      const element = await createSearch(
        definition([
          {
            uuid: 'node-1',
            actions: [sendMsg('a1', '   ', { quick_replies: ['', '  '] })],
            exits: []
          }
        ])
      );
      expect(await search(element, ' ')).to.have.length(0);
    });
  });

  describe('translations', () => {
    const translated = definition(
      [{ uuid: 'node-1', actions: [sendMsg('a1', 'Hello')], exits: [] }],
      { localization: { [SPANISH]: { a1: { text: ['Hola amigo'] } } } }
    );

    it('searches the translation while translating', async () => {
      const element = await createSearch(translated, {
        languageCode: SPANISH
      });
      const results = await search(element, 'amigo');
      expect(results).to.have.length(1);
      expect(results[0].fullText).to.equal('Hola amigo');
    });

    it('still matches the base text while translating', async () => {
      const element = await createSearch(translated, {
        languageCode: SPANISH
      });
      expect(await search(element, 'hello')).to.have.length(1);
    });

    it('does not search translations in the base language', async () => {
      const element = await createSearch(translated, { languageCode: 'eng' });
      expect(await search(element, 'amigo')).to.have.length(0);
    });
  });

  describe('sticky notes', () => {
    const withSticky = (sticky: any) =>
      definition([], {
        _ui: {
          nodes: {},
          languages: [],
          stickies: { 'sticky-1': sticky }
        }
      });

    // stickies live on the canvas rather than the message table, so they are
    // only searched in flow scope
    const createFlowSearch = (def: any) => createSearch(def, { scope: 'flow' });

    it('are not searched in table scope', async () => {
      const element = await createSearch(
        withSticky({
          title: 'Remember this',
          body: '',
          position: { left: 0, top: 0 },
          color: 'yellow'
        })
      );
      expect(await search(element, 'remember')).to.have.length(0);
    });

    it('matches a sticky title', async () => {
      const element = await createFlowSearch(
        withSticky({
          title: 'Remember this',
          body: '',
          position: { left: 0, top: 0 },
          color: 'yellow'
        })
      );
      const results = await search(element, 'remember');
      expect(results).to.have.length(1);
      expect(results[0].typeName).to.equal('Sticky Note');
      expect(results[0].stickyField).to.equal('title');
      expect(results[0].nodeUuid).to.equal('sticky-1');
    });

    it('matches a sticky body', async () => {
      const element = await createFlowSearch(
        withSticky({
          title: 'Note',
          body: 'Check the numbers',
          position: { left: 0, top: 0 },
          color: 'blue'
        })
      );
      const results = await search(element, 'numbers');
      expect(results[0].stickyField).to.equal('body');
    });

    it('prefers the title when both match', async () => {
      const element = await createFlowSearch(
        withSticky({
          title: 'Check this',
          body: 'Check that',
          position: { left: 0, top: 0 },
          color: 'yellow'
        })
      );
      const results = await search(element, 'check');
      expect(results).to.have.length(1);
      expect(results[0].stickyField).to.equal('title');
    });

    it('falls back to yellow for an unknown colour', async () => {
      const element = await createFlowSearch(
        withSticky({
          title: 'Remember',
          body: '',
          position: { left: 0, top: 0 },
          color: 'chartreuse'
        })
      );
      const results = await search(element, 'remember');
      expect(results[0].color).to.be.a('string');
    });
  });

  describe('rendering results', () => {
    it('lists the matches', async () => {
      const element = await createSearch(
        definition([
          { uuid: 'node-1', actions: [sendMsg('a1', 'Hello one')], exits: [] },
          { uuid: 'node-2', actions: [sendMsg('a2', 'Hello two')], exits: [] }
        ])
      );
      element.open = true;
      await search(element, 'hello');
      await element.updateComplete;
      const rendered = element.shadowRoot.textContent;
      expect(rendered).to.contain('Hello one');
      expect(rendered).to.contain('Hello two');
    });

    it('fires an event when a result is selected', async () => {
      const element = await createSearch(
        definition([
          { uuid: 'node-1', actions: [sendMsg('a1', 'Hello')], exits: [] }
        ])
      );
      const selected: any[] = [];
      element.addEventListener('temba-search-result-selected', (e: any) =>
        selected.push(e.detail)
      );
      const results = await search(element, 'hello');
      (element as any).selectResult(results[0]);
      expect(selected).to.have.length(1);
      expect(selected[0].nodeUuid).to.equal('node-1');
    });
  });
});
