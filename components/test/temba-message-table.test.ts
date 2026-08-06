import '../temba-modules';
import { fixture, expect } from '@open-wc/testing';
import { MessageTable } from '../src/flow/MessageTable';
import { zustand } from '../src/store/AppState';
import { CustomEventType } from '../src/interfaces';

const SPANISH = 'spa';

// a send_msg action with optional localizable extras
const sendMsg = (overrides: any = {}) => ({
  uuid: 'action-1',
  type: 'send_msg',
  text: 'Hello there',
  ...overrides
});

const node = (overrides: any = {}) => ({
  uuid: 'node-1',
  actions: [],
  exits: [{ uuid: 'exit-1' }],
  ...overrides
});

// builds a flow definition around the given nodes
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

const createTable = async (
  def: any,
  { languageCode = '', isTranslating = false } = {}
): Promise<MessageTable> => {
  zustand.setState({
    flowDefinition: def,
    languageCode,
    isTranslating
  } as any);
  return (await fixture(
    '<temba-message-table></temba-message-table>'
  )) as MessageTable;
};

describe('temba-message-table', () => {
  const initial = zustand.getState();

  afterEach(() => {
    zustand.setState({
      flowDefinition: initial.flowDefinition,
      languageCode: initial.languageCode,
      isTranslating: initial.isTranslating
    } as any);
  });

  describe('getEntries', () => {
    it('returns nothing for a flow with no nodes', async () => {
      const table = await createTable(definition([]));
      expect((table as any).getEntries()).to.have.length(0);
    });

    it('includes send_msg actions', async () => {
      const table = await createTable(
        definition([node({ actions: [sendMsg()] })])
      );
      const entries = (table as any).getEntries();
      expect(entries).to.have.length(1);
      expect(entries[0].kind).to.equal('message');
      expect(entries[0].action.uuid).to.equal('action-1');
      expect(entries[0].nodeIndex).to.equal(1);
    });

    it('includes other localizable actions', async () => {
      const table = await createTable(
        definition([
          node({
            actions: [
              {
                uuid: 'action-email',
                type: 'send_email',
                subject: 'Hi',
                body: 'Body'
              }
            ]
          })
        ])
      );
      const entries = (table as any).getEntries();
      expect(entries).to.have.length(1);
      expect(entries[0].action.type).to.equal('send_email');
    });

    it('excludes actions with nothing localizable', async () => {
      const table = await createTable(
        definition([
          node({
            actions: [
              { uuid: 'action-name', type: 'set_contact_name', name: 'Bob' }
            ]
          })
        ])
      );
      expect((table as any).getEntries()).to.have.length(0);
    });

    it('numbers nodes in definition order', async () => {
      const table = await createTable(
        definition([
          node({ uuid: 'node-1', actions: [sendMsg({ uuid: 'a1' })] }),
          node({ uuid: 'node-2', actions: [sendMsg({ uuid: 'a2' })] })
        ])
      );
      const entries = (table as any).getEntries();
      expect(entries.map((e: any) => e.nodeIndex)).to.deep.equal([1, 2]);
    });

    it('skips localization groups when not translating', async () => {
      const def = definition(
        [
          node({
            router: {
              cases: [
                { uuid: 'case-1', type: 'has_any_word', arguments: ['red'] }
              ],
              categories: [{ uuid: 'cat-1', name: 'Red' }]
            }
          })
        ],
        {
          _ui: {
            nodes: { 'node-1': { type: 'wait_for_response', config: {} } },
            languages: []
          }
        }
      );
      const table = await createTable(def, { isTranslating: false });
      expect((table as any).getEntries()).to.have.length(0);
    });

    it('includes rules flagged for localization when translating', async () => {
      const def = definition(
        [
          node({
            router: {
              cases: [
                { uuid: 'case-1', type: 'has_any_word', arguments: ['red'] }
              ],
              categories: [{ uuid: 'cat-1', name: 'Red' }]
            }
          })
        ],
        {
          _ui: {
            nodes: {
              'node-1': {
                type: 'wait_for_response',
                config: { localizeRules: true }
              }
            },
            languages: []
          }
        }
      );
      const table = await createTable(def, {
        languageCode: SPANISH,
        isTranslating: true
      });
      const entries = (table as any).getEntries();
      expect(entries).to.have.length(1);
      expect(entries[0].kind).to.equal('localization-group');
      expect(entries[0].rules).to.have.length(1);
      expect(entries[0].rules[0].uuid).to.equal('case-1');
    });

    it('includes rules that already carry a translation', async () => {
      const def = definition(
        [
          node({
            router: {
              cases: [
                { uuid: 'case-1', type: 'has_any_word', arguments: ['red'] }
              ],
              categories: [{ uuid: 'cat-1', name: 'Red' }]
            }
          })
        ],
        {
          _ui: {
            nodes: { 'node-1': { type: 'wait_for_response', config: {} } },
            languages: []
          },
          localization: { [SPANISH]: { 'case-1': { arguments: ['rojo'] } } }
        }
      );
      const table = await createTable(def, {
        languageCode: SPANISH,
        isTranslating: true
      });
      const entries = (table as any).getEntries();
      expect(entries).to.have.length(1);
      expect(entries[0].rules[0].arguments).to.deep.equal(['red']);
    });

    it('ignores rules with no arguments', async () => {
      const def = definition(
        [
          node({
            router: {
              cases: [{ uuid: 'case-1', type: 'has_text', arguments: [] }],
              categories: [{ uuid: 'cat-1', name: 'Has Text' }]
            }
          })
        ],
        {
          _ui: {
            nodes: {
              'node-1': {
                type: 'wait_for_response',
                config: { localizeRules: true }
              }
            },
            languages: []
          }
        }
      );
      const table = await createTable(def, {
        languageCode: SPANISH,
        isTranslating: true
      });
      expect((table as any).getEntries()).to.have.length(0);
    });
  });

  describe('getTranslatedText', () => {
    it('returns null when not translating', async () => {
      const table = await createTable(
        definition([node({ actions: [sendMsg()] })], {
          localization: { [SPANISH]: { 'action-1': { text: ['Hola'] } } }
        })
      );
      expect((table as any).getTranslatedText('action-1')).to.equal(null);
    });

    it('returns the first localized string when translating', async () => {
      const table = await createTable(
        definition([node({ actions: [sendMsg()] })], {
          localization: { [SPANISH]: { 'action-1': { text: ['Hola'] } } }
        }),
        { languageCode: SPANISH, isTranslating: true }
      );
      expect((table as any).getTranslatedText('action-1')).to.equal('Hola');
    });

    it('returns null when the action has no translation', async () => {
      const table = await createTable(
        definition([node({ actions: [sendMsg()] })]),
        { languageCode: SPANISH, isTranslating: true }
      );
      expect((table as any).getTranslatedText('action-1')).to.equal(null);
    });

    it('treats an empty translation as absent', async () => {
      const table = await createTable(
        definition([node({ actions: [sendMsg()] })], {
          localization: { [SPANISH]: { 'action-1': { text: [''] } } }
        }),
        { languageCode: SPANISH, isTranslating: true }
      );
      expect((table as any).getTranslatedText('action-1')).to.equal(null);
    });
  });

  describe('getTranslatedQuickReplies', () => {
    const withReplies = (replies: any) =>
      definition([node({ actions: [sendMsg()] })], {
        localization: { [SPANISH]: { 'action-1': { quick_replies: replies } } }
      });

    it('returns an empty list when not translating', async () => {
      const table = await createTable(withReplies(['Si']));
      expect(
        (table as any).getTranslatedQuickReplies('action-1')
      ).to.deep.equal([]);
    });

    it('returns the localized replies', async () => {
      const table = await createTable(withReplies(['Si', 'No']), {
        languageCode: SPANISH,
        isTranslating: true
      });
      expect(
        (table as any).getTranslatedQuickReplies('action-1')
      ).to.deep.equal(['Si', 'No']);
    });

    it('trims and drops blank replies', async () => {
      const table = await createTable(withReplies(['  Si  ', '', '   ']), {
        languageCode: SPANISH,
        isTranslating: true
      });
      expect(
        (table as any).getTranslatedQuickReplies('action-1')
      ).to.deep.equal(['Si']);
    });

    it('ignores non string entries', async () => {
      const table = await createTable(withReplies(['Si', 3, null]), {
        languageCode: SPANISH,
        isTranslating: true
      });
      expect(
        (table as any).getTranslatedQuickReplies('action-1')
      ).to.deep.equal(['Si']);
    });

    it('returns an empty list when the field is not an array', async () => {
      const table = await createTable(withReplies('Si'), {
        languageCode: SPANISH,
        isTranslating: true
      });
      expect(
        (table as any).getTranslatedQuickReplies('action-1')
      ).to.deep.equal([]);
    });
  });

  describe('getTranslatedCategoryName', () => {
    const withCategory = (name: any) =>
      definition([node()], {
        localization: { [SPANISH]: { 'cat-1': { name } } }
      });

    it('returns null when not translating', async () => {
      const table = await createTable(withCategory(['Rojo']));
      expect((table as any).getTranslatedCategoryName('cat-1')).to.equal(null);
    });

    it('reads the first entry of an array name', async () => {
      const table = await createTable(withCategory(['Rojo']), {
        languageCode: SPANISH,
        isTranslating: true
      });
      expect((table as any).getTranslatedCategoryName('cat-1')).to.equal(
        'Rojo'
      );
    });

    it('reads a plain string name', async () => {
      const table = await createTable(withCategory('Rojo'), {
        languageCode: SPANISH,
        isTranslating: true
      });
      expect((table as any).getTranslatedCategoryName('cat-1')).to.equal(
        'Rojo'
      );
    });

    it('returns null for a missing or empty name', async () => {
      const table = await createTable(withCategory(['']), {
        languageCode: SPANISH,
        isTranslating: true
      });
      expect((table as any).getTranslatedCategoryName('cat-1')).to.equal(null);

      const missing = await createTable(definition([node()]), {
        languageCode: SPANISH,
        isTranslating: true
      });
      expect((missing as any).getTranslatedCategoryName('cat-1')).to.equal(
        null
      );
    });
  });

  describe('getTranslatedField and getTranslatedArrayField', () => {
    const withEmail = (localization: any = {}) =>
      definition(
        [
          node({
            actions: [
              {
                uuid: 'action-email',
                type: 'send_email',
                subject: 'Hi',
                body: 'Body'
              }
            ]
          })
        ],
        { localization }
      );

    it('returns the first entry of a localized field', async () => {
      const table = await createTable(
        withEmail({ [SPANISH]: { 'action-email': { subject: ['Hola'] } } }),
        { languageCode: SPANISH, isTranslating: true }
      );
      expect(
        (table as any).getTranslatedField('action-email', 'subject')
      ).to.equal('Hola');
    });

    it('returns null when not translating', async () => {
      const table = await createTable(
        withEmail({ [SPANISH]: { 'action-email': { subject: ['Hola'] } } })
      );
      expect(
        (table as any).getTranslatedField('action-email', 'subject')
      ).to.equal(null);
    });

    it('returns the whole array for an array field', async () => {
      const table = await createTable(
        withEmail({
          [SPANISH]: { 'action-email': { attachments: ['image/jpeg:a.jpg'] } }
        }),
        { languageCode: SPANISH, isTranslating: true }
      );
      expect(
        (table as any).getTranslatedArrayField('action-email', 'attachments')
      ).to.deep.equal(['image/jpeg:a.jpg']);
    });

    it('returns an empty array when the field is missing', async () => {
      const table = await createTable(withEmail(), {
        languageCode: SPANISH,
        isTranslating: true
      });
      expect(
        (table as any).getTranslatedArrayField('action-email', 'attachments')
      ).to.deep.equal([]);
    });
  });

  describe('hasAnyTranslation', () => {
    const entryFor = (action: any) => ({
      kind: 'message',
      node: node(),
      action,
      nodeIndex: 1
    });

    it('is false when there is no localization for the action', async () => {
      const table = await createTable(
        definition([node({ actions: [sendMsg()] })]),
        { languageCode: SPANISH, isTranslating: true }
      );
      expect((table as any).hasAnyTranslation(entryFor(sendMsg()))).to.equal(
        false
      );
    });

    it('is true when a localizable field holds text', async () => {
      const table = await createTable(
        definition([node({ actions: [sendMsg()] })], {
          localization: { [SPANISH]: { 'action-1': { text: ['Hola'] } } }
        }),
        { languageCode: SPANISH, isTranslating: true }
      );
      expect((table as any).hasAnyTranslation(entryFor(sendMsg()))).to.equal(
        true
      );
    });

    it('is false when the localized values are all blank', async () => {
      const table = await createTable(
        definition([node({ actions: [sendMsg()] })], {
          localization: { [SPANISH]: { 'action-1': { text: ['  '] } } }
        }),
        { languageCode: SPANISH, isTranslating: true }
      );
      expect((table as any).hasAnyTranslation(entryFor(sendMsg()))).to.equal(
        false
      );
    });

    it('is false for an action type with nothing localizable', async () => {
      const table = await createTable(definition([node()]), {
        languageCode: SPANISH,
        isTranslating: true
      });
      expect(
        (table as any).hasAnyTranslation(
          entryFor({ uuid: 'a', type: 'set_contact_name' })
        )
      ).to.equal(false);
    });
  });

  describe('usesPairedRows and getPairedFields', () => {
    it('pairs rows for actions with more than one text field', async () => {
      const table = await createTable(definition([node()]));
      expect((table as any).usesPairedRows({ type: 'send_email' })).to.equal(
        true
      );
    });

    it('does not pair rows for a single text field action', async () => {
      const table = await createTable(definition([node()]));
      expect((table as any).usesPairedRows({ type: 'send_msg' })).to.equal(
        false
      );
    });

    it('does not pair rows for actions with nothing localizable', async () => {
      const table = await createTable(definition([node()]));
      expect(
        (table as any).usesPairedRows({ type: 'set_contact_name' })
      ).to.equal(false);
    });

    it('returns each paired field with its label and original text', async () => {
      const table = await createTable(definition([node()]), {
        languageCode: SPANISH,
        isTranslating: true
      });
      const fields = (table as any).getPairedFields({
        uuid: 'action-email',
        type: 'send_email',
        subject: 'Hi',
        body: 'Body text'
      });
      expect(fields.map((f: any) => f.key)).to.deep.equal(['subject', 'body']);
      expect(fields[0].original).to.equal('Hi');
      expect(fields[1].original).to.equal('Body text');
      expect(fields[0].translated).to.equal(null);
    });

    it('carries the translation through for paired fields', async () => {
      const table = await createTable(
        definition([node()], {
          localization: { [SPANISH]: { 'action-email': { subject: ['Hola'] } } }
        }),
        { languageCode: SPANISH, isTranslating: true }
      );
      const fields = (table as any).getPairedFields({
        uuid: 'action-email',
        type: 'send_email',
        subject: 'Hi',
        body: 'Body text'
      });
      expect(fields[0].translated).to.equal('Hola');
      expect(fields[1].translated).to.equal(null);
    });

    it('returns nothing for an action with no form config', async () => {
      const table = await createTable(definition([node()]));
      expect(
        (table as any).getPairedFields({ uuid: 'a', type: 'set_contact_name' })
      ).to.deep.equal([]);
    });
  });

  describe('stripLeadingLineBreaks', () => {
    it('removes leading newlines only', async () => {
      const table = await createTable(definition([node()]));
      const strip = (text: string) =>
        (table as any).stripLeadingLineBreaks(text);
      expect(strip('\n\nhello')).to.equal('hello');
      expect(strip('\r\nhello')).to.equal('hello');
      expect(strip('hello\n\n')).to.equal('hello\n\n');
      expect(strip('hello')).to.equal('hello');
      expect(strip('')).to.equal('');
    });
  });

  describe('getGroupTranslations', () => {
    it('pairs each rule with its localized arguments', async () => {
      const table = await createTable(
        definition([node()], {
          localization: { [SPANISH]: { 'case-1': { arguments: ['rojo'] } } }
        }),
        { languageCode: SPANISH, isTranslating: true }
      );
      const items = (table as any).getGroupTranslations({
        kind: 'localization-group',
        node: node(),
        rules: [{ uuid: 'case-1', type: 'has_any_word', arguments: ['red'] }],
        categories: [],
        nodeIndex: 1
      });
      expect(items).to.have.length(1);
      expect(items[0].original).to.equal('red');
      expect(items[0].translated).to.equal('rojo');
      expect(items[0].isRule).to.equal(true);
      expect(items[0].operatorName).to.equal('has any of the words');
    });

    it('joins multiple arguments with commas', async () => {
      const table = await createTable(
        definition([node()], {
          localization: {
            [SPANISH]: { 'case-1': { arguments: ['rojo', 'carmesi'] } }
          }
        }),
        { languageCode: SPANISH, isTranslating: true }
      );
      const items = (table as any).getGroupTranslations({
        kind: 'localization-group',
        node: node(),
        rules: [
          {
            uuid: 'case-1',
            type: 'has_any_word',
            arguments: ['red', 'crimson']
          }
        ],
        categories: [],
        nodeIndex: 1
      });
      expect(items[0].original).to.equal('red, crimson');
      expect(items[0].translated).to.equal('rojo, carmesi');
    });

    it('falls back to the raw type for an unknown operator', async () => {
      const table = await createTable(definition([node()]), {
        languageCode: SPANISH,
        isTranslating: true
      });
      const items = (table as any).getGroupTranslations({
        kind: 'localization-group',
        node: node(),
        rules: [{ uuid: 'case-1', type: 'has_nonsense', arguments: ['x'] }],
        categories: [],
        nodeIndex: 1
      });
      expect(items[0].operatorName).to.equal('has_nonsense');
      expect(items[0].translated).to.equal(null);
    });

    it('appends categories after the rules', async () => {
      const table = await createTable(
        definition([node()], {
          localization: { [SPANISH]: { 'cat-1': { name: ['Rojo'] } } }
        }),
        { languageCode: SPANISH, isTranslating: true }
      );
      const items = (table as any).getGroupTranslations({
        kind: 'localization-group',
        node: node(),
        rules: [{ uuid: 'case-1', type: 'has_any_word', arguments: ['red'] }],
        categories: [{ uuid: 'cat-1', name: 'Red' }],
        nodeIndex: 1
      });
      expect(items).to.have.length(2);
      expect(items[1].isRule).to.equal(false);
      expect(items[1].original).to.equal('Red');
      expect(items[1].translated).to.equal('Rojo');
    });
  });

  describe('getEntryRailColor', () => {
    it('uses the action group colour for a message entry', async () => {
      const table = await createTable(definition([node()]));
      const color = (table as any).getEntryRailColor({
        kind: 'message',
        node: node(),
        action: sendMsg(),
        nodeIndex: 1
      });
      expect(color).to.equal('#3498db');
    });

    it('falls back to a neutral colour for an unknown action type', async () => {
      const table = await createTable(definition([node()]));
      const color = (table as any).getEntryRailColor({
        kind: 'message',
        node: node(),
        action: { uuid: 'a', type: 'has_nonsense' },
        nodeIndex: 1
      });
      expect(color).to.equal('#cbd5e1');
    });

    it('falls back to a neutral colour when the node has no ui type', async () => {
      const table = await createTable(definition([node()]));
      const color = (table as any).getEntryRailColor({
        kind: 'localization-group',
        node: node(),
        rules: [],
        categories: [],
        nodeIndex: 1
      });
      expect(color).to.equal('#cbd5e1');
    });

    it('uses the node group colour for a localization group', async () => {
      const table = await createTable(
        definition([node()], {
          _ui: {
            nodes: { 'node-1': { type: 'wait_for_response' } },
            languages: []
          }
        })
      );
      const color = (table as any).getEntryRailColor({
        kind: 'localization-group',
        node: node(),
        rules: [],
        categories: [],
        nodeIndex: 1
      });
      expect(color).to.be.a('string');
      expect(color.startsWith('#')).to.equal(true);
    });
  });

  describe('edit requests', () => {
    it('fires an action edit request forcing the base language', async () => {
      const table = await createTable(
        definition([node({ actions: [sendMsg()] })])
      );
      const events: any[] = [];
      table.addEventListener(CustomEventType.ActionEditRequested, (e: any) =>
        events.push(e.detail)
      );
      (table as any).handleBaseTextClick({
        kind: 'message',
        node: node(),
        action: sendMsg(),
        nodeIndex: 1
      });
      expect(events).to.have.length(1);
      expect(events[0].forceBase).to.equal(true);
      expect(events[0].nodeUuid).to.equal('node-1');
      expect(events[0].action.uuid).to.equal('action-1');
    });

    it('fires an action edit request for the translation', async () => {
      const table = await createTable(
        definition([node({ actions: [sendMsg()] })])
      );
      const events: any[] = [];
      table.addEventListener(CustomEventType.ActionEditRequested, (e: any) =>
        events.push(e.detail)
      );
      (table as any).handleTranslationClick({
        kind: 'message',
        node: node(),
        action: sendMsg(),
        nodeIndex: 1
      });
      expect(events).to.have.length(1);
      expect(events[0].forceBase).to.equal(undefined);
    });

    it('fires a node edit request for a localization group', async () => {
      const table = await createTable(
        definition([node()], {
          _ui: {
            nodes: { 'node-1': { type: 'wait_for_response' } },
            languages: []
          }
        })
      );
      const events: any[] = [];
      table.addEventListener(CustomEventType.NodeEditRequested, (e: any) =>
        events.push(e.detail)
      );
      const entry = {
        kind: 'localization-group',
        node: node(),
        rules: [],
        categories: [],
        nodeIndex: 1
      };
      (table as any).handleBaseGroupClick(entry);
      (table as any).handleGroupTranslationClick(entry);
      expect(events).to.have.length(2);
      expect(events[0].forceBase).to.equal(true);
      expect(events[1].forceBase).to.equal(undefined);
    });

    it('does not fire a node edit request when the node has no ui', async () => {
      const table = await createTable(definition([node()]));
      const events: any[] = [];
      table.addEventListener(CustomEventType.NodeEditRequested, (e: any) =>
        events.push(e.detail)
      );
      (table as any).handleBaseGroupClick({
        kind: 'localization-group',
        node: node(),
        rules: [],
        categories: [],
        nodeIndex: 1
      });
      expect(events).to.have.length(0);
    });
  });

  describe('focusSearchResult', () => {
    it('does nothing when there are no rows', async () => {
      const table = await createTable(definition([]));
      await table.updateComplete;
      // no throw is the assertion here
      table.focusSearchResult('node-1', 'action-1');
    });

    it('scrolls the matching action row into view', async () => {
      const table = await createTable(
        definition([node({ actions: [sendMsg()] })])
      );
      await table.updateComplete;
      const row = table.renderRoot.querySelector(
        'tr[data-node-uuid="node-1"]'
      ) as HTMLElement;
      expect(row).to.not.equal(null);

      let scrolled = false;
      row.scrollIntoView = () => {
        scrolled = true;
      };
      table.focusSearchResult('node-1', 'action-1');
      expect(scrolled).to.equal(true);
    });
  });
});
