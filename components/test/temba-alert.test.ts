import { fixture, assert } from '@open-wc/testing';
import { Alert } from '../src/display/Alert';

import { assertScreenshot, getClip } from './utils.test';

export const createAlert = async (level: string, body: string) => {
  const parentNode = document.createElement('div');
  parentNode.setAttribute('style', 'width: 250px;');
  return (await fixture(`<temba-alert level="${level}">${body}</temba-alert>`, {
    parentNode
  })) as Alert;
};

describe('temba-alert', () => {
  it('shows info', async () => {
    const alert = await createAlert('info', 'Here is some info');
    assert.instanceOf(alert, Alert);
    await assertScreenshot('alert/info', getClip(alert));
  });

  it('shows warning', async () => {
    const alert = await createAlert('warning', 'Here is a warning');
    assert.instanceOf(alert, Alert);
    await assertScreenshot('alert/warning', getClip(alert));
  });

  it('shows error', async () => {
    const alert = await createAlert('error', 'Here is an error');
    assert.instanceOf(alert, Alert);
    await assertScreenshot('alert/error', getClip(alert));
  });
});
