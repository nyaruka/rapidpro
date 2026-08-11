import { fixture, expect } from '@open-wc/testing';
import { FlowSearch, SearchResult } from '../src/flow/FlowSearch';
import { FlowDefinition } from '../src/store/flow-definition';

if (!customElements.get('temba-flow-search')) {
  customElements.define('temba-flow-search', FlowSearch);
}

const DEFINITION = {
  language: 'eng',
  nodes: [
    {
      uuid: 'node-email',
      actions: [
        {
          type: 'send_email',
          uuid: 'action-email',
          subject: 'Weekly report',
          body: 'The report is attached.',
          addresses: ['ops@example.com']
        }
      ],
      exits: []
    },
    {
      uuid: 'node-msg',
      actions: [
        {
          type: 'send_msg',
          uuid: 'action-msg',
          text: 'Check your email inbox'
        }
      ],
      exits: []
    },
    {
      uuid: 'node-wait',
      router: {
        type: 'switch',
        operand: '@input.text',
        categories: [],
        cases: []
      },
      exits: []
    }
  ],
  _ui: {
    nodes: {
      'node-email': { type: 'execute_actions', position: { left: 0, top: 0 } },
      'node-msg': { type: 'execute_actions', position: { left: 0, top: 100 } },
      'node-wait': {
        type: 'wait_for_response',
        position: { left: 0, top: 200 }
      }
    },
    stickies: {}
  }
} as unknown as FlowDefinition;

const search = async (query: string): Promise<SearchResult[]> => {
  const el = (await fixture(
    '<temba-flow-search></temba-flow-search>'
  )) as FlowSearch;
  el.definition = DEFINITION;
  el.show();
  await el.updateComplete;

  const input = el.shadowRoot.querySelector('input') as HTMLInputElement;
  input.value = query;
  input.dispatchEvent(new InputEvent('input', { bubbles: true }));
  await el.updateComplete;

  return (el as any).results as SearchResult[];
};

describe('temba-flow-search', () => {
  it('matches action content text', async () => {
    const results = await search('attached');
    expect(results.length).to.equal(1);
    expect(results[0].nodeUuid).to.equal('node-email');
    expect(results[0].typeName).to.equal('Send Email');
    expect(results[0].fullText).to.equal('The report is attached.');
    expect(results[0].matchLength).to.equal('attached'.length);
  });

  it('matches action type names', async () => {
    const results = await search('email');

    // The send_msg action matches on content, the send_email action
    // matches on its type name
    expect(results.length).to.equal(2);

    const typeMatch = results.find((r) => r.nodeUuid === 'node-email');
    expect(typeMatch.typeName).to.equal('Send Email');
    expect(typeMatch.action.uuid).to.equal('action-email');
    // type-name matches preview the first content text without a highlight
    expect(typeMatch.fullText).to.equal('Weekly report');
    expect(typeMatch.matchLength).to.equal(0);

    const contentMatch = results.find((r) => r.nodeUuid === 'node-msg');
    expect(contentMatch.fullText).to.equal('Check your email inbox');
    expect(contentMatch.matchLength).to.equal('email'.length);
  });

  it('does not duplicate results when both content and type match', async () => {
    const results = await search('send');
    // Both actions match on type name only ("Send Email", "Send Message")
    expect(results.length).to.equal(2);
    expect(results.every((r) => r.matchLength === 0)).to.equal(true);
  });

  it('matches node type names', async () => {
    const results = await search('wait for');
    expect(results.length).to.equal(1);
    expect(results[0].nodeUuid).to.equal('node-wait');
    expect(results[0].typeName).to.equal('Wait for Response');
    expect(results[0].action).to.equal(null);
    // type-name match previews the node's first content text (its operand)
    expect(results[0].fullText).to.equal('@input.text');
    expect(results[0].matchLength).to.equal(0);
  });

  it('highlights within the type name when there is no content preview', async () => {
    const definition = {
      language: 'eng',
      nodes: [
        {
          uuid: 'node-random',
          router: { type: 'random', categories: [], cases: [] },
          exits: []
        }
      ],
      _ui: {
        nodes: {
          'node-random': {
            type: 'split_by_random',
            position: { left: 0, top: 0 }
          }
        },
        stickies: {}
      }
    } as unknown as FlowDefinition;

    const el = (await fixture(
      '<temba-flow-search></temba-flow-search>'
    )) as FlowSearch;
    el.definition = definition;
    el.show();
    await el.updateComplete;

    const input = el.shadowRoot.querySelector('input') as HTMLInputElement;
    input.value = 'random';
    input.dispatchEvent(new InputEvent('input', { bubbles: true }));
    await el.updateComplete;

    const results = (el as any).results as SearchResult[];
    expect(results.length).to.equal(1);
    const typeName = results[0].typeName;
    expect(results[0].fullText).to.equal(typeName);
    expect(results[0].matchStart).to.equal(
      typeName.toLowerCase().indexOf('random')
    );
    expect(results[0].matchLength).to.equal('random'.length);
  });
});
