import '../temba-modules';
import { fixture, expect } from '@open-wc/testing';
import { MediaPicker } from '../src/form/MediaPicker';
import { Attachment, CustomEventType } from '../src/interfaces';
import { mockPOST, clearMockPosts } from './utils.test';

const MEDIA_ENDPOINT = /\/api\/v2\/media\.json/;

const file = (name: string, type: string, size = 100): File => {
  const blob = new Blob(['x'.repeat(size)], { type });
  return new File([blob], name, { type });
};

const attachment = (url: string, filename = 'a.jpg'): Attachment =>
  ({
    uuid: `uuid-${url}`,
    url,
    filename,
    content_type: 'image/jpeg',
    size: 100
  }) as Attachment;

// a DragEvent carrying the given files
const dragEvent = (type: string, files: File[] = []): DragEvent => {
  const event = new Event(type, {
    bubbles: true,
    cancelable: true
  }) as DragEvent;
  Object.defineProperty(event, 'dataTransfer', {
    value: { files }
  });
  return event;
};

const createPicker = async (attrs = ''): Promise<MediaPicker> => {
  return (await fixture(
    `<temba-media-picker ${attrs}></temba-media-picker>`
  )) as MediaPicker;
};

// the drag handlers live on the container inside the shadow root, so events
// have to be dispatched there rather than on the host
const drag = async (picker: MediaPicker, type: string, files: File[] = []) => {
  await picker.updateComplete;
  const container = picker.shadowRoot.querySelector('.container');
  container.dispatchEvent(dragEvent(type, files));
};

// waits for the post promise chain plus the deferred change event
const settle = () => new Promise((resolve) => setTimeout(resolve, 10));

describe('temba-media-picker', () => {
  afterEach(() => {
    clearMockPosts();
  });

  describe('canAcceptAttachments', () => {
    it('accepts while below the maximum', async () => {
      const picker = await createPicker('max="2"');
      expect(picker.canAcceptAttachments()).to.equal(true);
      picker.attachments = [attachment('one')];
      expect(picker.canAcceptAttachments()).to.equal(true);
    });

    it('refuses once the maximum is reached', async () => {
      const picker = await createPicker('max="2"');
      picker.attachments = [attachment('one'), attachment('two')];
      expect(picker.canAcceptAttachments()).to.equal(false);
    });
  });

  describe('drag and drop', () => {
    it('highlights on drag enter and over', async () => {
      const picker = await createPicker();
      await drag(picker, 'dragenter');
      expect(picker.pendingDrop).to.equal(true);

      picker.pendingDrop = false;
      await drag(picker, 'dragover');
      expect(picker.pendingDrop).to.equal(true);
    });

    it('clears the highlight on drag leave', async () => {
      const picker = await createPicker();
      await drag(picker, 'dragenter');
      await drag(picker, 'dragleave');
      expect(picker.pendingDrop).to.equal(false);
    });

    it('does not highlight once full', async () => {
      const picker = await createPicker('max="1"');
      picker.attachments = [attachment('one')];
      await drag(picker, 'dragenter');
      expect(picker.pendingDrop).to.not.equal(true);
    });

    it('ignores drag events entirely when told to', async () => {
      const picker = await createPicker('ignoreDrops');
      await drag(picker, 'dragenter');
      expect(picker.pendingDrop).to.not.equal(true);
    });

    it('uploads acceptable files on drop', async () => {
      mockPOST(MEDIA_ENDPOINT, attachment('dropped', 'photo.jpg'));
      const picker = await createPicker();
      await drag(picker, 'drop', [file('photo.jpg', 'image/jpeg')]);
      await settle();
      expect(picker.attachments).to.have.length(1);
      expect(picker.attachments[0].url).to.equal('dropped');
    });

    it('filters dropped files against the accept list', async () => {
      mockPOST(MEDIA_ENDPOINT, attachment('dropped'));
      const picker = await createPicker('accept="image/png"');
      await drag(picker, 'drop', [
        file('photo.jpg', 'image/jpeg'),
        file('shot.png', 'image/png')
      ]);
      await settle();
      expect(picker.attachments).to.have.length(1);
    });

    it('ignores a drop when told to ignore drops', async () => {
      mockPOST(MEDIA_ENDPOINT, attachment('dropped'));
      const picker = await createPicker('ignoreDrops');
      await drag(picker, 'drop', [file('photo.jpg', 'image/jpeg')]);
      await settle();
      expect(picker.attachments).to.have.length(0);
    });

    it('ignores a drop once full', async () => {
      mockPOST(MEDIA_ENDPOINT, attachment('dropped'));
      const picker = await createPicker('max="1"');
      picker.attachments = [attachment('one')];
      await drag(picker, 'drop', [file('photo.jpg', 'image/jpeg')]);
      await settle();
      expect(picker.attachments).to.have.length(1);
    });
  });

  describe('accept matching', () => {
    const uploadOne = async (accept: string, type: string) => {
      mockPOST(MEDIA_ENDPOINT, attachment('uploaded'));
      const picker = await createPicker(`accept="${accept}"`);
      picker.uploadFiles([file('f', type)]);
      await settle();
      return picker.attachments.length;
    };

    it('accepts an exact content type match', async () => {
      expect(await uploadOne('image/png', 'image/png')).to.equal(1);
    });

    it('accepts a wildcard subtype match', async () => {
      expect(await uploadOne('image/*', 'image/jpeg')).to.equal(1);
    });

    it('accepts any of a comma separated list', async () => {
      expect(
        await uploadOne('image/png, application/pdf', 'application/pdf')
      ).to.equal(1);
    });

    it('rejects a type outside the list', async () => {
      expect(await uploadOne('image/png', 'application/pdf')).to.equal(0);
    });

    it('accepts anything when no accept is configured', async () => {
      expect(await uploadOne('', 'application/octet-stream')).to.equal(1);
    });
  });

  describe('uploadFiles', () => {
    it('skips files already attached with the same name and size', async () => {
      mockPOST(MEDIA_ENDPOINT, attachment('uploaded'));
      const picker = await createPicker();
      picker.attachments = [
        { ...attachment('one'), filename: 'photo.jpg', size: 100 } as Attachment
      ];
      picker.uploadFiles([file('photo.jpg', 'image/jpeg', 100)]);
      await settle();
      expect(picker.attachments).to.have.length(1);
    });

    it('uploads a file whose name matches but size differs', async () => {
      mockPOST(MEDIA_ENDPOINT, attachment('uploaded'));
      const picker = await createPicker();
      picker.attachments = [
        { ...attachment('one'), filename: 'photo.jpg', size: 100 } as Attachment
      ];
      picker.uploadFiles([file('photo.jpg', 'image/jpeg', 200)]);
      await settle();
      expect(picker.attachments).to.have.length(2);
    });

    it('does not add beyond the maximum', async () => {
      mockPOST(MEDIA_ENDPOINT, attachment('uploaded'));
      const picker = await createPicker('max="1"');
      picker.attachments = [attachment('one')];
      picker.uploadFiles([file('photo.jpg', 'image/jpeg')]);
      await settle();
      expect(picker.attachments).to.have.length(1);
    });

    it('reports loading state while uploading', async () => {
      mockPOST(MEDIA_ENDPOINT, attachment('uploaded'));
      const picker = await createPicker();
      const loadingStates: boolean[] = [];
      picker.addEventListener(CustomEventType.Loading, (e: any) =>
        loadingStates.push(e.detail.loading)
      );
      picker.uploadFiles([file('photo.jpg', 'image/jpeg')]);
      await settle();
      expect(loadingStates).to.deep.equal([true, false]);
      expect(picker.uploading).to.equal(false);
    });
  });

  describe('upload failures', () => {
    it('reports a validation error without attaching', async () => {
      mockPOST(MEDIA_ENDPOINT, { file: ['Unsupported file type'] }, {}, '400');
      const picker = await createPicker();
      picker.uploadFiles([file('bad.exe', 'application/octet-stream')]);
      await settle();
      expect(picker.attachments).to.have.length(0);
      expect(picker.uploading).to.equal(false);
    });

    it('recovers from a server failure', async () => {
      mockPOST(MEDIA_ENDPOINT, { detail: 'boom' }, {}, '500');
      const picker = await createPicker();
      picker.uploadFiles([file('photo.jpg', 'image/jpeg')]);
      await settle();
      expect(picker.attachments).to.have.length(0);
      expect(picker.uploading).to.equal(false);
    });
  });

  describe('removing attachments', () => {
    it('removes the attachment matching the clicked icon', async () => {
      const picker = await createPicker();
      picker.attachments = [attachment('one'), attachment('two')];
      await picker.updateComplete;

      const remove = picker.shadowRoot.querySelector(
        'temba-icon[id="one"]'
      ) as HTMLElement;
      expect(remove).to.not.equal(null);
      remove.click();
      await picker.updateComplete;

      expect(picker.attachments).to.have.length(1);
      expect(picker.attachments[0].url).to.equal('two');
    });
  });

  describe('rendering', () => {
    it('offers the upload input while there is room', async () => {
      const picker = await createPicker('max="2"');
      await picker.updateComplete;
      expect(picker.shadowRoot.querySelector('#upload-input')).to.not.equal(
        null
      );
    });

    it('hides the upload input once full', async () => {
      const picker = await createPicker('max="1"');
      picker.attachments = [attachment('one')];
      await picker.updateComplete;
      expect(picker.shadowRoot.querySelector('#upload-input')).to.equal(null);
    });

    it('shows a loading indicator while uploading', async () => {
      const picker = await createPicker();
      picker.uploading = true;
      await picker.updateComplete;
      expect(picker.shadowRoot.querySelector('temba-loading')).to.not.equal(
        null
      );
    });

    it('allows multiple selection only when more than one is allowed', async () => {
      const single = await createPicker('max="1"');
      await single.updateComplete;
      expect(
        single.shadowRoot
          .querySelector('#upload-input')
          .hasAttribute('multiple')
      ).to.equal(false);

      const multi = await createPicker('max="3"');
      await multi.updateComplete;
      expect(
        multi.shadowRoot.querySelector('#upload-input').hasAttribute('multiple')
      ).to.equal(true);
    });

    it('renders a thumbnail per attachment', async () => {
      const picker = await createPicker();
      picker.attachments = [attachment('one'), attachment('two')];
      await picker.updateComplete;
      expect(
        picker.shadowRoot.querySelectorAll('temba-thumbnail')
      ).to.have.length(2);
    });
  });

  describe('file input', () => {
    it('uploads files chosen through the input', async () => {
      mockPOST(MEDIA_ENDPOINT, attachment('chosen'));
      const picker = await createPicker();
      await picker.updateComplete;

      const input = picker.shadowRoot.querySelector(
        '#upload-input'
      ) as HTMLInputElement;
      const transfer = new DataTransfer();
      transfer.items.add(file('photo.jpg', 'image/jpeg'));
      input.files = transfer.files;
      input.dispatchEvent(new Event('change'));

      await settle();
      expect(picker.attachments).to.have.length(1);
      expect(picker.attachments[0].url).to.equal('chosen');
    });
  });
});
