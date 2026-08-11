import { expect } from '@open-wc/testing';
import { WebChat } from '../src/webchat/WebChat';
import { getComponent } from './utils.test';

const getWebChat = async (attrs: any = {}) => {
  const webChat = (await getComponent(
    'temba-webchat',
    attrs,
    '',
    400,
    600
  )) as WebChat;
  return webChat;
};

describe('WebChat Lightbox Fix', () => {
  afterEach(() => {
    // Clean up any lightbox elements after each test
    const lightboxes = document.querySelectorAll('temba-lightbox');
    lightboxes.forEach((lightbox) => lightbox.remove());
  });

  it('should only create one lightbox element even with multiple WebChat instances', async () => {
    // Create first WebChat instance
    await getWebChat({
      channel: 'test-channel-1'
    });

    // Verify lightbox was created
    let lightboxes = document.querySelectorAll('temba-lightbox');
    expect(lightboxes.length).to.equal(1);

    // Create second WebChat instance
    await getWebChat({
      channel: 'test-channel-2'
    });

    // Verify still only one lightbox exists
    lightboxes = document.querySelectorAll('temba-lightbox');
    expect(lightboxes.length).to.equal(1);
  });

  it('should not create lightbox if one already exists', async () => {
    // Manually create a lightbox first
    const existingLightbox = document.createElement('temba-lightbox');
    document.body.appendChild(existingLightbox);

    // Create WebChat instance
    await getWebChat({
      channel: 'test-channel'
    });

    // Verify still only one lightbox exists
    const lightboxes = document.querySelectorAll('temba-lightbox');
    expect(lightboxes.length).to.equal(1);
  });
});
