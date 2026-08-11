import { expect, assert } from '@open-wc/testing';
import { useFakeTimers } from 'sinon';
import { StickyNote } from '../src/flow/StickyNote';
import { CustomEventType } from '../src/interfaces';
import { StickyNote as StickyNoteData } from '../src/store/flow-definition';
import { assertScreenshot, getClip, getComponent } from './utils.test';

describe('temba-sticky-note', () => {
  const mockStickyData: StickyNoteData = {
    position: { left: 0, top: 0 },
    title: 'Test Title',
    body: 'Test body content',
    color: 'yellow'
  };

  const createStickyNote = async (
    data: StickyNoteData,
    uuid: string = 'test-uuid'
  ) => {
    const component = (await getComponent(
      'temba-sticky-note',
      {},
      '',
      220,
      120
    )) as StickyNote;
    component.uuid = uuid;
    component.data = data;
    await component.updateComplete;
    return component;
  };

  it('can be created', async () => {
    const component = await createStickyNote(mockStickyData);

    assert.instanceOf(component, StickyNote);
    expect(component.data).to.exist;
    expect(component.data.color).to.equal('yellow');

    const stickyNote = component.shadowRoot?.querySelector('.sticky-note');
    expect(stickyNote).to.exist;
    expect(stickyNote?.classList.contains('yellow')).to.be.true;

    await assertScreenshot('sticky-note/default', getClip(component));
  });

  it('renders yellow sticky note', async () => {
    const data = { ...mockStickyData, color: 'yellow' as const };
    const component = await createStickyNote(data);

    const stickyNote = component.shadowRoot?.querySelector('.sticky-note');
    expect(stickyNote?.classList.contains('yellow')).to.be.true;

    await assertScreenshot('sticky-note/yellow', getClip(component));
  });

  it('renders blue sticky note', async () => {
    const data = { ...mockStickyData, color: 'blue' as const };
    const component = await createStickyNote(data);

    const stickyNote = component.shadowRoot?.querySelector('.sticky-note');
    expect(stickyNote?.classList.contains('blue')).to.be.true;

    await assertScreenshot('sticky-note/blue', getClip(component));
  });

  it('renders pink sticky note', async () => {
    const data = { ...mockStickyData, color: 'pink' as const };
    const component = await createStickyNote(data);

    const stickyNote = component.shadowRoot?.querySelector('.sticky-note');
    expect(stickyNote?.classList.contains('pink')).to.be.true;

    await assertScreenshot('sticky-note/pink', getClip(component));
  });

  it('renders green sticky note', async () => {
    const data = { ...mockStickyData, color: 'green' as const };
    const component = await createStickyNote(data);

    const stickyNote = component.shadowRoot?.querySelector('.sticky-note');
    expect(stickyNote?.classList.contains('green')).to.be.true;

    await assertScreenshot('sticky-note/green', getClip(component));
  });

  it('renders gray sticky note', async () => {
    const data = { ...mockStickyData, color: 'gray' as const };
    const component = await createStickyNote(data);

    const stickyNote = component.shadowRoot?.querySelector('.sticky-note');
    expect(stickyNote?.classList.contains('gray')).to.be.true;

    await assertScreenshot('sticky-note/gray', getClip(component));
  });

  it('renders color picker in bottom right corner', async () => {
    const component = await createStickyNote(mockStickyData);

    const colorPicker = component.shadowRoot?.querySelector('.color-picker');
    expect(colorPicker).to.exist;

    // Check for color options container
    const colorOptions = component.shadowRoot?.querySelector('.color-options');
    expect(colorOptions).to.exist;

    // Check for all 5 color option elements
    const colorOptionElements =
      component.shadowRoot?.querySelectorAll('.color-option');
    expect(colorOptionElements).to.have.lengthOf(5);

    // Verify each color option is present
    expect(component.shadowRoot?.querySelector('.color-option.yellow')).to
      .exist;
    expect(component.shadowRoot?.querySelector('.color-option.blue')).to.exist;
    expect(component.shadowRoot?.querySelector('.color-option.pink')).to.exist;
    expect(component.shadowRoot?.querySelector('.color-option.green')).to.exist;
    expect(component.shadowRoot?.querySelector('.color-option.gray')).to.exist;
  });

  it('shows expanded color picker on hover', async () => {
    const component = await createStickyNote(mockStickyData);

    const colorPicker = component.shadowRoot?.querySelector(
      '.color-picker'
    ) as HTMLElement;
    expect(colorPicker).to.exist;

    // Simulate mouseenter event to expand the color picker
    const mouseEnterEvent = new MouseEvent('mouseenter', { bubbles: true });
    colorPicker.dispatchEvent(mouseEnterEvent);

    await component.updateComplete;

    // Check that the color options have the expanded class
    const colorOptions = component.shadowRoot?.querySelector('.color-options');
    expect(colorOptions?.classList.contains('expanded')).to.be.true;

    await assertScreenshot(
      'sticky-note/color-picker-expanded',
      getClip(component)
    );
  });

  it('hides color picker on mouse leave', async () => {
    const component = await createStickyNote(mockStickyData);

    const colorPicker = component.shadowRoot?.querySelector(
      '.color-picker'
    ) as HTMLElement;

    // First expand it
    colorPicker.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
    await component.updateComplete;

    // Check that it's expanded
    const expandedColorOptions =
      component.shadowRoot?.querySelector('.color-options');
    expect(expandedColorOptions?.classList.contains('expanded')).to.be.true;

    // Then simulate mouse leave
    const mouseLeaveEvent = new MouseEvent('mouseleave', { bubbles: true });
    colorPicker.dispatchEvent(mouseLeaveEvent);

    await component.updateComplete;

    // Check that it's no longer expanded
    const collapsedColorOptions =
      component.shadowRoot?.querySelector('.color-options');
    expect(collapsedColorOptions?.classList.contains('expanded')).to.be.false;
  });

  it('displays title and body content', async () => {
    const data = {
      ...mockStickyData,
      title: 'Custom Title',
      body: 'This is custom body content for testing purposes.'
    };
    const component = await createStickyNote(data);

    const titleElement = component.shadowRoot?.querySelector('.sticky-title');
    const bodyElement = component.shadowRoot?.querySelector('.sticky-body');

    expect(titleElement?.textContent).to.equal('Custom Title');
    expect(bodyElement?.textContent).to.equal(
      'This is custom body content for testing purposes.'
    );
  });

  it('renders drag handle', async () => {
    const component = await createStickyNote(mockStickyData);

    const dragHandle = component.shadowRoot?.querySelector('.drag-handle');
    expect(dragHandle).to.exist;

    // The drag handle should have the drag icon
    expect(dragHandle?.getAttribute('name')).to.equal('drag');
  });

  // Screenshot tests for color options (without clicking to avoid store errors)
  it('renders yellow color option correctly', async () => {
    const component = await createStickyNote(mockStickyData);

    // Expand color picker
    const colorPicker = component.shadowRoot?.querySelector(
      '.color-picker'
    ) as HTMLElement;
    colorPicker.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
    await component.updateComplete;

    const yellowOption = component.shadowRoot?.querySelector(
      '.color-option.yellow'
    );
    expect(yellowOption).to.exist;

    await assertScreenshot('sticky-note/yellow-color', getClip(component));
  });

  it('renders blue color option correctly', async () => {
    const component = await createStickyNote(mockStickyData);

    const colorPicker = component.shadowRoot?.querySelector(
      '.color-picker'
    ) as HTMLElement;
    colorPicker.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
    await component.updateComplete;

    const blueOption =
      component.shadowRoot?.querySelector('.color-option.blue');
    expect(blueOption).to.exist;

    await assertScreenshot('sticky-note/blue-color', getClip(component));
  });

  it('renders pink color option correctly', async () => {
    const component = await createStickyNote(mockStickyData);

    const colorPicker = component.shadowRoot?.querySelector(
      '.color-picker'
    ) as HTMLElement;
    colorPicker.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
    await component.updateComplete;

    const pinkOption =
      component.shadowRoot?.querySelector('.color-option.pink');
    expect(pinkOption).to.exist;

    await assertScreenshot('sticky-note/pink-color', getClip(component));
  });

  it('renders green color option correctly', async () => {
    const component = await createStickyNote(mockStickyData);

    const colorPicker = component.shadowRoot?.querySelector(
      '.color-picker'
    ) as HTMLElement;
    colorPicker.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
    await component.updateComplete;

    const greenOption = component.shadowRoot?.querySelector(
      '.color-option.green'
    );
    expect(greenOption).to.exist;

    await assertScreenshot('sticky-note/green-color', getClip(component));
  });

  it('renders gray color option correctly', async () => {
    const component = await createStickyNote(mockStickyData);

    const colorPicker = component.shadowRoot?.querySelector(
      '.color-picker'
    ) as HTMLElement;
    colorPicker.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
    await component.updateComplete;

    const grayOption =
      component.shadowRoot?.querySelector('.color-option.gray');
    expect(grayOption).to.exist;

    await assertScreenshot('sticky-note/gray-color', getClip(component));
  });

  it('renders remove button', async () => {
    const component = await createStickyNote(mockStickyData);

    const removeButton = component.shadowRoot?.querySelector('.remove-button');
    expect(removeButton).to.exist;
    expect(removeButton?.textContent?.trim()).to.equal('✕');
  });

  it('shows removing state on first click', async () => {
    const component = await createStickyNote(mockStickyData);

    const removeButton = component.shadowRoot?.querySelector(
      '.remove-button'
    ) as HTMLElement;
    removeButton.click();
    await component.updateComplete;

    // Title container should have removing class
    const titleContainer = component.shadowRoot?.querySelector(
      '.sticky-title-container'
    );
    expect(titleContainer?.classList.contains('removing')).to.be.true;

    // Title should show "Remove?"
    const title = component.shadowRoot?.querySelector('.sticky-title');
    expect(title?.textContent).to.equal('Remove?');

    await assertScreenshot('sticky-note/removing', getClip(component));
  });

  it('resets removing state after timeout', async () => {
    const clock = useFakeTimers();

    try {
      const component = await createStickyNote(mockStickyData);

      const removeButton = component.shadowRoot?.querySelector(
        '.remove-button'
      ) as HTMLElement;
      removeButton.click();
      await component.updateComplete;

      // Verify it's in removing state
      const titleContainer = component.shadowRoot?.querySelector(
        '.sticky-title-container'
      );
      expect(titleContainer?.classList.contains('removing')).to.be.true;

      // Advance clock past the timeout
      clock.tick(1001);
      await component.updateComplete;

      // Should no longer be in removing state
      expect(titleContainer?.classList.contains('removing')).to.be.false;

      // Title should be back to original
      const title = component.shadowRoot?.querySelector('.sticky-title');
      expect(title?.textContent).to.equal('Test Title');
    } finally {
      clock.restore();
    }
  });

  it('fires StickyNoteDeleted event on second click', async () => {
    const component = await createStickyNote(mockStickyData);

    let deletedUuid: string | null = null;
    component.addEventListener(CustomEventType.StickyNoteDeleted, ((
      event: CustomEvent
    ) => {
      deletedUuid = event.detail.uuid;
    }) as EventListener);

    const removeButton = component.shadowRoot?.querySelector(
      '.remove-button'
    ) as HTMLElement;

    // First click — enter removing state
    removeButton.click();
    await component.updateComplete;

    // Second click — confirm removal
    removeButton.click();
    await component.updateComplete;

    expect(deletedUuid).to.equal('test-uuid');
  });
});
