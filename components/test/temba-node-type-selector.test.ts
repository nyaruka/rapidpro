import { expect, assert } from '@open-wc/testing';
import { NodeTypeSelector } from '../src/flow/NodeTypeSelector';
import { assertScreenshot, getClip, getComponent } from './utils.test';

describe('temba-node-type-selector', () => {
  const createSelector = async () => {
    const component = (await getComponent(
      'temba-node-type-selector',
      {},
      '',
      700,
      600
    )) as NodeTypeSelector;
    await component.updateComplete;
    return component;
  };

  it('can be created', async () => {
    const selector = await createSelector();
    assert.instanceOf(selector, NodeTypeSelector);
    expect(selector.open).to.be.false;
  });

  it('is not visible when closed', async () => {
    const selector = await createSelector();
    expect(selector.open).to.be.false;

    // component should not be in DOM when closed
    expect(selector.hasAttribute('open')).to.be.false;
  });

  it('shows unified dialog when opened in all mode', async () => {
    const selector = await createSelector();

    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    expect(selector.open).to.be.true;
    expect(selector.mode).to.equal('all');
    expect(selector.hasAttribute('open')).to.be.true;

    // No title heading, just a search input in the header
    const title = selector.shadowRoot?.querySelector('.header h2');
    expect(title).to.be.null;

    const searchInput = selector.shadowRoot?.querySelector('.search-input');
    expect(searchInput).to.not.be.null;

    const dialog = selector.shadowRoot?.querySelector('.dialog') as HTMLElement;
    await assertScreenshot(
      'node-type-selector/all-mode',
      getClip(dialog),
      true
    );
  });

  it('shows promoted items at the top', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    const promotedSection =
      selector.shadowRoot?.querySelector('.promoted-section');
    expect(promotedSection).to.not.be.null;

    const promotedTitles = Array.from(
      promotedSection?.querySelectorAll('.node-item-title') || []
    ).map((item) => item.textContent?.trim());

    expect(promotedTitles).to.include('Send Message');
    expect(promotedTitles).to.include('Wait for Response');

    // Promoted section should NOT have a border-bottom
    // (no extra visual separator beyond normal spacing)
  });

  it('uses different colors for promoted items', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    const promotedItems = selector.shadowRoot?.querySelectorAll(
      '.promoted-section .node-item'
    );
    expect(promotedItems?.length).to.equal(2);

    // Each promoted item should have its own color via --item-color
    const sendMsgStyle = (promotedItems?.[0] as HTMLElement)?.style;
    const waitStyle = (promotedItems?.[1] as HTMLElement)?.style;
    const sendMsgColor = sendMsgStyle?.getPropertyValue('--item-color');
    const waitColor = waitStyle?.getPropertyValue('--item-color');

    // Colors should be different
    expect(sendMsgColor).to.not.equal(waitColor);
  });

  it('shows both actions and splits in unified view', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    const nodeItems = selector.shadowRoot?.querySelectorAll('.node-item-title');
    const titles = Array.from(nodeItems || []).map((item) =>
      item.textContent?.trim()
    );

    // Should have actions
    expect(titles).to.include('Update Field');

    // Should have splits
    expect(titles).to.include('Split by Expression');
    expect(titles).to.include('Split by Contact Field');
  });

  it('does not offer Add Input Labels in background flows', async () => {
    const selector = await createSelector();

    const titlesFor = async (flowType: string) => {
      selector.flowType = flowType as any;
      await selector.updateComplete;
      selector.show('all', { x: 100, y: 100 });
      await selector.updateComplete;
      return Array.from(
        selector.shadowRoot?.querySelectorAll('.node-item-title') || []
      ).map((item) => item.textContent?.trim());
    };

    // available in messaging flows
    expect(await titlesFor('message')).to.include('Add Input Labels');

    // not available in background flows: goflow treats add_input_labels as an
    // interactive action that a messaging_background flow rejects
    expect(await titlesFor('background')).to.not.include('Add Input Labels');
  });

  it('shows Call AI in action categories (not a separate branching section)', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    selector.features = [];
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    const nodeItems = selector.shadowRoot?.querySelectorAll('.node-item-title');
    const titles = Array.from(nodeItems || []).map((item) =>
      item.textContent?.trim()
    );
    expect(titles).to.include('Call AI');

    // Should NOT have a separate "Actions that Branch" section
    const branchingSection =
      selector.shadowRoot?.querySelector('.section-branching');
    expect(branchingSection).to.be.null;
  });

  it('marks branching items with the branching class', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    // Call AI should have branching class
    const nodeItems = selector.shadowRoot?.querySelectorAll('.node-item');
    let callAiBranching = false;
    let setFieldBranching = false;

    nodeItems?.forEach((item) => {
      const title = item.querySelector('.node-item-title')?.textContent?.trim();
      if (title === 'Call AI') {
        callAiBranching = item.classList.contains('branching');
      }
      if (title === 'Update Field') {
        setFieldBranching = item.classList.contains('branching');
      }
    });

    expect(callAiBranching).to.be.true;
    expect(setFieldBranching).to.be.false;
  });

  it('highlights first item by default', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    // First node-item should have the highlighted class
    const firstItem = selector.shadowRoot?.querySelector('.node-item');
    expect(firstItem?.classList.contains('highlighted')).to.be.true;

    // Only one item should be highlighted
    const highlightedItems = selector.shadowRoot?.querySelectorAll(
      '.node-item.highlighted'
    );
    expect(highlightedItems?.length).to.equal(1);
  });

  it('selects first item on Enter key', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    let selectionDetail: any = null;
    selector.addEventListener('temba-selection', (event: any) => {
      selectionDetail = event.detail;
    });

    const searchInput = selector.shadowRoot?.querySelector(
      '.search-input'
    ) as HTMLInputElement;
    searchInput.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
    );
    await selector.updateComplete;

    expect(selectionDetail).to.not.be.null;
    expect(selectionDetail.nodeType).to.equal('send_msg');
    expect(selector.open).to.be.false;
  });

  it('selects filtered item on Enter key', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    // Search for webhook
    const searchInput = selector.shadowRoot?.querySelector(
      '.search-input'
    ) as HTMLInputElement;
    searchInput.value = 'webhook';
    searchInput.dispatchEvent(new InputEvent('input'));
    await selector.updateComplete;

    let selectionDetail: any = null;
    selector.addEventListener('temba-selection', (event: any) => {
      selectionDetail = event.detail;
    });

    searchInput.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
    );
    await selector.updateComplete;

    expect(selectionDetail).to.not.be.null;
    expect(selectionDetail.nodeType).to.equal('split_by_webhook');
  });

  it('navigates highlight with arrow keys', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    const searchInput = selector.shadowRoot?.querySelector(
      '.search-input'
    ) as HTMLInputElement;

    // Initially first item is highlighted
    let highlighted = selector.shadowRoot?.querySelectorAll(
      '.node-item.highlighted'
    );
    expect(highlighted?.length).to.equal(1);

    // Arrow down moves to second item
    searchInput.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })
    );
    await selector.updateComplete;

    highlighted = selector.shadowRoot?.querySelectorAll(
      '.node-item.highlighted'
    );
    expect(highlighted?.length).to.equal(1);
    // The highlighted item should be the second one
    const allItems = selector.shadowRoot?.querySelectorAll('.node-item');
    expect(allItems?.[1]?.classList.contains('highlighted')).to.be.true;

    // Arrow up moves back to first
    searchInput.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true })
    );
    await selector.updateComplete;

    expect(allItems?.[0]?.classList.contains('highlighted')).to.be.true;
  });

  it('navigates highlight with Ctrl+n and Ctrl+p', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    const searchInput = selector.shadowRoot?.querySelector(
      '.search-input'
    ) as HTMLInputElement;

    // Ctrl+n moves down
    searchInput.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'n',
        ctrlKey: true,
        bubbles: true
      })
    );
    await selector.updateComplete;

    const allItems = selector.shadowRoot?.querySelectorAll('.node-item');
    expect(allItems?.[1]?.classList.contains('highlighted')).to.be.true;

    // Ctrl+p moves up
    searchInput.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'p',
        ctrlKey: true,
        bubbles: true
      })
    );
    await selector.updateComplete;

    expect(allItems?.[0]?.classList.contains('highlighted')).to.be.true;
  });

  it('closes on Escape key', async () => {
    const selector = await createSelector();
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    expect(selector.open).to.be.true;

    const searchInput = selector.shadowRoot?.querySelector(
      '.search-input'
    ) as HTMLInputElement;
    searchInput.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })
    );
    await selector.updateComplete;

    expect(selector.open).to.be.false;
  });

  it('hides branching items in action-no-branching mode', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    await selector.updateComplete;
    selector.show('action-no-branching', { x: 100, y: 100 });
    await selector.updateComplete;

    const nodeItems = selector.shadowRoot?.querySelectorAll('.node-item-title');
    const titles = Array.from(nodeItems || []).map((item) =>
      item.textContent?.trim()
    );

    // Should have regular actions
    expect(titles).to.include('Update Field');

    // Should NOT have branching items
    expect(titles).to.not.include('Call AI');
    expect(titles).to.not.include('Call Webhook');
    expect(titles).to.not.include('Wait for Response');
    expect(titles).to.not.include('Split by Expression');
  });

  it('has a search input that filters items', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    // Search input should exist
    const searchInput = selector.shadowRoot?.querySelector(
      '.search-input'
    ) as HTMLInputElement;
    expect(searchInput).to.not.be.null;

    // Type a search query
    searchInput.value = 'webhook';
    searchInput.dispatchEvent(new InputEvent('input'));
    await selector.updateComplete;

    // Should only show matching items
    const nodeItems = selector.shadowRoot?.querySelectorAll('.node-item-title');
    const titles = Array.from(nodeItems || []).map((item) =>
      item.textContent?.trim()
    );

    expect(titles).to.include('Call Webhook');
    expect(titles).to.not.include('Update Field');
    expect(titles).to.not.include('Send Message');
  });

  it('shows no results message when search has no matches', async () => {
    const selector = await createSelector();
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    const searchInput = selector.shadowRoot?.querySelector(
      '.search-input'
    ) as HTMLInputElement;
    searchInput.value = 'xyznonexistent';
    searchInput.dispatchEvent(new InputEvent('input'));
    await selector.updateComplete;

    const noResults = selector.shadowRoot?.querySelector('.no-results');
    expect(noResults).to.not.be.null;
    expect(noResults?.textContent?.trim()).to.equal('No matching items found');
  });

  it('closes when close() is called', async () => {
    const selector = await createSelector();
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    expect(selector.open).to.be.true;

    selector.close();
    await selector.updateComplete;

    expect(selector.open).to.be.false;
  });

  it('closes when overlay is clicked', async () => {
    const selector = await createSelector();
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    const overlay = selector.shadowRoot?.querySelector(
      '.overlay'
    ) as HTMLElement;
    overlay.click();
    await selector.updateComplete;

    expect(selector.open).to.be.false;
  });

  it('closes when cancel button is clicked', async () => {
    const selector = await createSelector();
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    const cancelButton = selector.shadowRoot?.querySelector(
      'temba-button'
    ) as HTMLElement;
    cancelButton.click();
    await selector.updateComplete;

    expect(selector.open).to.be.false;
  });

  it('fires selection event when node type is clicked', async () => {
    const selector = await createSelector();
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    let selectionFired = false;
    let selectionDetail = null;

    selector.addEventListener('temba-selection', (event: any) => {
      selectionFired = true;
      selectionDetail = event.detail;
    });

    // click on first node item
    const firstNodeItem = selector.shadowRoot?.querySelector(
      '.node-item'
    ) as HTMLElement;
    firstNodeItem.click();
    await selector.updateComplete;

    expect(selectionFired).to.be.true;
    expect(selectionDetail).to.have.property('nodeType');
    expect(selectionDetail).to.have.property('position');
    expect(selectionDetail.position).to.deep.equal({ x: 100, y: 100 });
    expect(selector.open).to.be.false;
  });

  it('filters actions by flow type - voice flow should show voice-only actions', async () => {
    const selector = await createSelector();
    selector.flowType = 'voice';
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    // get all node item titles
    const nodeItems = selector.shadowRoot?.querySelectorAll('.node-item-title');
    const titles = Array.from(nodeItems || []).map((item) =>
      item.textContent?.trim()
    );

    // voice flow should have Say Message and Play Recording
    expect(titles).to.include('Say Message');
    expect(titles).to.include('Play Recording');
  });

  it('filters actions by flow type - message flow should not show voice-only actions', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    // get all node item titles
    const nodeItems = selector.shadowRoot?.querySelectorAll('.node-item-title');
    const titles = Array.from(nodeItems || []).map((item) =>
      item.textContent?.trim()
    );

    // message flow should not have Say Message or Play Recording
    expect(titles).to.not.include('Say Message');
    expect(titles).to.not.include('Play Recording');
  });

  it('filters by features - airtime feature enables airtime actions', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    selector.features = ['airtime'];
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    // get all node item titles
    const nodeItems = selector.shadowRoot?.querySelectorAll('.node-item-title');
    const titles = Array.from(nodeItems || []).map((item) =>
      item.textContent?.trim()
    );

    // with airtime feature, should have Send Airtime
    expect(titles).to.include('Send Airtime');
  });

  it('filters by features - without airtime feature, airtime actions are hidden', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    selector.features = [];
    await selector.updateComplete;
    selector.show('all', { x: 100, y: 100 });
    await selector.updateComplete;

    // get all node item titles
    const nodeItems = selector.shadowRoot?.querySelectorAll('.node-item-title');
    const titles = Array.from(nodeItems || []).map((item) =>
      item.textContent?.trim()
    );

    // without airtime feature, should not have Send Airtime
    expect(titles).to.not.include('Send Airtime');
  });

  it('hides actions/nodes with empty flowTypes array from selector', async () => {
    const selector = await createSelector();

    // test that isConfigAvailable returns false for empty flowTypes array
    const configWithEmptyFlowTypes = {
      name: 'Test Action',
      type: 'test_action',
      flowTypes: [] // empty array should hide from all flow types
    };

    selector.flowType = 'message';
    await selector.updateComplete;

    // call private method via any to test behavior
    const isAvailable = (selector as any).isConfigAvailable(
      configWithEmptyFlowTypes
    );
    expect(isAvailable).to.be.false;

    // test with different flow types - should still be false
    selector.flowType = 'voice';
    await selector.updateComplete;

    const isAvailableVoice = (selector as any).isConfigAvailable(
      configWithEmptyFlowTypes
    );
    expect(isAvailableVoice).to.be.false;
  });

  it('shows actions/nodes with undefined flowTypes for all flow types', async () => {
    const selector = await createSelector();

    // test that isConfigAvailable returns true for undefined flowTypes
    const configWithUndefinedFlowTypes = {
      name: 'Test Action',
      type: 'test_action'
      // flowTypes is undefined - should be available for all
    };

    selector.flowType = 'message';
    await selector.updateComplete;

    const isAvailable = (selector as any).isConfigAvailable(
      configWithUndefinedFlowTypes
    );
    expect(isAvailable).to.be.true;

    // test with different flow types - should still be true
    selector.flowType = 'voice';
    await selector.updateComplete;

    const isAvailableVoice = (selector as any).isConfigAvailable(
      configWithUndefinedFlowTypes
    );
    expect(isAvailableVoice).to.be.true;
  });

  describe('alias filtering', () => {
    it('should not show split_by_run_result twice when aliases exist', async () => {
      const selector = await createSelector();

      selector.show('all', { x: 100, y: 100 });
      await selector.updateComplete;

      // Get all the node items rendered in the selector
      const nodeItems = selector.shadowRoot!.querySelectorAll('.node-item');

      // Count how many times "Split by Result" appears
      let splitByResultCount = 0;
      nodeItems.forEach((item) => {
        const title = item.querySelector('.node-item-title');
        if (title?.textContent?.includes('Split by Result')) {
          splitByResultCount++;
        }
      });

      // Should only appear once, not twice
      expect(splitByResultCount).to.equal(1);
    });

    it('should not show split_by_run_result_delimited type in the selector', async () => {
      const selector = await createSelector();

      selector.show('all', { x: 100, y: 100 });
      await selector.updateComplete;

      // Get all the node items and check their data-type attributes
      const nodeItems = selector.shadowRoot!.querySelectorAll('.node-item');

      let foundDelimitedType = false;
      nodeItems.forEach((item) => {
        const typeAttr = item.getAttribute('data-type');
        if (typeAttr === 'split_by_run_result_delimited') {
          foundDelimitedType = true;
        }
      });

      expect(foundDelimitedType).to.be.false;
    });

    it('should show split_by_llm_categorize in the selector', async () => {
      const selector = await createSelector();

      selector.show('all', { x: 100, y: 100 });
      await selector.updateComplete;

      const titles = Array.from(
        selector.shadowRoot!.querySelectorAll('.node-item-title')
      ).map((el) => el.textContent?.trim());

      expect(titles).to.include('Split by AI');
    });
  });

  it('send_msg appears in promoted section for message flows', async () => {
    const selector = await createSelector();
    selector.flowType = 'message';
    await selector.updateComplete;
    selector.show('action-no-branching', { x: 100, y: 100 });
    await selector.updateComplete;

    const promotedSection =
      selector.shadowRoot?.querySelector('.promoted-section');
    const promotedTitles = Array.from(
      promotedSection?.querySelectorAll('.node-item-title') || []
    ).map((item) => item.textContent?.trim());

    expect(promotedTitles).to.include('Send Message');
    // Wait for Response is branching, so it should NOT appear in no-branching mode
    expect(promotedTitles).to.not.include('Wait for Response');
  });
});
