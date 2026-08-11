import { fixture, expect, assert } from '@open-wc/testing';
import { DatePicker } from '../src/form/DatePicker';
import { assertScreenshot, getAttributes, getClip } from './utils.test';

export const getPickerHTML = (attrs: any = {}) => {
  return `<temba-datepicker ${getAttributes(attrs)}></temba-datepicker>`;
};

export const createPicker = async (def: string) => {
  const parentNode = document.createElement('div');
  parentNode.setAttribute('style', 'width: 400px;');
  parentNode.id = 'parent';
  const picker: DatePicker = await fixture(def, { parentNode });
  return picker;
};

describe('temba-datepicker', () => {
  it('can create a date picker', async () => {
    const picker: DatePicker = await createPicker(getPickerHTML());
    assert.instanceOf(picker, DatePicker);
    await assertScreenshot('datepicker/date', getClip(picker));
  });

  it('can create a datetime picker', async () => {
    const picker: DatePicker = await createPicker(
      getPickerHTML({ time: true })
    );
    assert.instanceOf(picker, DatePicker);
    // await assertScreenshot('datepicker/datetime', getClip(picker));
  });

  it('can be initialized with an iso date', async () => {
    const picker: DatePicker = await createPicker(
      getPickerHTML({ value: '2020-01-20T14:00Z', time: true })
    );

    // default should be browser locale, which for our tests is UTC
    // expect(picker.timezone).to.equal('UTC');

    // we should display in the current locale
    // await assertScreenshot('datepicker/initial-value', getClip(picker));

    // but our value should be our original value as a full iso date
    expect(picker.value).is.equal('2020-01-20T14:00:00.000Z');
  });

  it('can be initialized with a timezone', async () => {
    const picker: DatePicker = await createPicker(
      getPickerHTML({
        value: '2020-01-20T14:00Z',
        timezone: 'America/New_York',
        time: true
      })
    );

    expect(picker.timezone).to.equal('America/New_York');

    // we should display in the eastern timezone
    await assertScreenshot('datepicker/initial-timezone', getClip(picker));
    expect(picker.value).to.equal('2020-01-20T14:00:00.000Z');
  });

  it('can be updated via keyboard', async () => {
    const picker: DatePicker = await createPicker(
      getPickerHTML({ value: '2020-01-20T14:00Z', id: 'picker', time: true })
    );

    // click into the picker and update the date
    await click('#picker');
    await typeInto('#picker', '01202024', false);

    // click away to update
    picker.blur();

    expect(picker.value).to.equal('2024-01-20T14:00:00.000Z');
    // await assertScreenshot('datepicker/updated-keyboard', getClip(picker));
  });

  it('can update date via keyboard', async () => {
    const picker: DatePicker = await createPicker(
      getPickerHTML({ value: '2020-01-20', id: 'picker' })
    );

    // click into the picker and update the date
    await click('#picker');
    await typeInto('#picker', '12252024', false);

    // click away to update
    picker.blur();

    expect(picker.value).to.equal('2024-12-25');
    await assertScreenshot('datepicker/updated-keyboard-date', getClip(picker));
  });

  it('truncates time on dates', async () => {
    const picker: DatePicker = await createPicker(
      getPickerHTML({ value: '2020-01-20 00:00:00' })
    );

    expect(picker.value).to.equal('2020-01-20');
    await assertScreenshot('datepicker/date-truncated-time', getClip(picker));
  });
});
