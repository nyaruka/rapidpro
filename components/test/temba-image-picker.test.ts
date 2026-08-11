import '../temba-modules';
import { fixture, expect } from '@open-wc/testing';
import { ImagePicker } from '../src/form/ImagePicker';

// a stand-in for the croppie widget, which needs a real canvas otherwise
class FakeCroppie {
  public static instances: FakeCroppie[] = [];

  public element: HTMLElement;
  public options: any;
  public bound: any = null;
  public resultOptions: any = null;
  public resultBlob = new Blob(['image'], { type: 'image/webp' });

  constructor(element: HTMLElement, options: any) {
    this.element = element;
    this.options = options;
    FakeCroppie.instances.push(this);
  }

  public bind(options: any) {
    this.bound = options;
  }

  public result(options: any): Promise<Blob> {
    this.resultOptions = options;
    return Promise.resolve(this.resultBlob);
  }
}

const createPicker = async (attrs = ''): Promise<ImagePicker> => {
  const picker = (await fixture(
    `<temba-image-picker name="avatar" ${attrs}></temba-image-picker>`
  )) as ImagePicker;
  await picker.updateComplete;
  return picker;
};

const toggle = (picker: ImagePicker) =>
  picker.shadowRoot.querySelector('.toggle') as HTMLElement;

const fileInput = (picker: ImagePicker) =>
  picker.shadowRoot.querySelector('#file') as HTMLInputElement;

describe('temba-image-picker', () => {
  let originalCroppie: any;

  beforeEach(() => {
    originalCroppie = (window as any).Croppie;
    (window as any).Croppie = FakeCroppie;
    FakeCroppie.instances = [];
  });

  afterEach(() => {
    (window as any).Croppie = originalCroppie;
  });

  describe('rendering', () => {
    it('renders a toggle and a hidden file input', async () => {
      const picker = await createPicker();
      expect(toggle(picker)).to.not.equal(null);
      expect(fileInput(picker)).to.not.equal(null);
      expect(fileInput(picker).getAttribute('accept')).to.equal('image/*');
    });

    it('shows a placeholder background with no image set', async () => {
      const picker = await createPicker();
      expect(toggle(picker).style.background).to.contain('rgba(0, 0, 0, 0.1)');
      expect(toggle(picker).classList.contains('set')).to.equal(false);
    });

    it('shows the image once a url is set', async () => {
      const picker = await createPicker();
      picker.url = 'http://example.com/avatar.png';
      await picker.updateComplete;
      expect(toggle(picker).classList.contains('set')).to.equal(true);
      expect(toggle(picker).style.background).to.contain(
        'http://example.com/avatar.png'
      );
    });

    it('mirrors the url onto the host attribute', async () => {
      const picker = await createPicker();
      picker.url = 'http://example.com/avatar.png';
      await picker.updateComplete;
      expect(picker.getAttribute('url')).to.equal(
        'http://example.com/avatar.png'
      );
    });

    it('defaults to a square viewport shape', async () => {
      const picker = await createPicker();
      expect(picker.shape).to.equal('square');
      expect(
        picker.shadowRoot.querySelector('.wrapper').classList.contains('square')
      ).to.equal(true);
    });

    it('honours a circle shape', async () => {
      const picker = await createPicker('shape="circle"');
      expect(
        picker.shadowRoot.querySelector('.wrapper').classList.contains('circle')
      ).to.equal(true);
    });
  });

  describe('choosing a file', () => {
    it('opens the file dialog when the toggle is clicked', async () => {
      const picker = await createPicker();
      let clicked = false;
      fileInput(picker).click = () => {
        clicked = true;
      };
      toggle(picker).click();
      expect(clicked).to.equal(true);
    });

    it('reads the chosen file and opens the cropper', async () => {
      const picker = await createPicker();
      const input = fileInput(picker);
      const transfer = new DataTransfer();
      transfer.items.add(
        new File([new Blob(['img'])], 'avatar.png', { type: 'image/png' })
      );
      input.files = transfer.files;

      const opened = new Promise<void>((resolve) => {
        const original = picker.uploadReader.onload;
        picker.uploadReader.onload = function (this: any, ev: any) {
          (original as any).call(this, ev);
          resolve();
        };
      });

      input.dispatchEvent(new Event('change'));
      await opened;
      await picker.updateComplete;

      expect(FakeCroppie.instances).to.have.length(1);
      expect(picker.showCroppie).to.equal(true);
      // the reader hands croppie a data url for the chosen file
      expect(FakeCroppie.instances[0].bound.url).to.contain('data:');
      // the input is cleared so the same file can be picked again
      expect(input.value).to.equal('');
    });

    it('ignores a change event with no file', async () => {
      const picker = await createPicker();
      fileInput(picker).dispatchEvent(new Event('change'));
      await picker.updateComplete;
      expect(FakeCroppie.instances).to.have.length(0);
      expect(picker.showCroppie).to.equal(false);
    });
  });

  describe('cropping', () => {
    // opens the cropper directly rather than going through the file reader
    const openCropper = async (picker: ImagePicker) => {
      (picker as any).launchCroppie('data:image/png;base64,abc');
      await picker.updateComplete;
    };

    it('builds the cropper with the configured shape', async () => {
      const picker = await createPicker('shape="circle"');
      await openCropper(picker);
      const croppie = FakeCroppie.instances[0];
      expect(croppie.options.viewport.type).to.equal('circle');
      expect(croppie.options.viewport.width).to.equal(300);
      expect(croppie.options.enableExif).to.equal(true);
    });

    it('replaces any previous cropper', async () => {
      const picker = await createPicker();
      await openCropper(picker);
      await openCropper(picker);
      expect(FakeCroppie.instances).to.have.length(2);
      // only one embedded widget remains
      expect(
        picker.shadowRoot.querySelectorAll('.croppie .embed > div')
      ).to.have.length(1);
    });

    it('closes without saving', async () => {
      const picker = await createPicker();
      await openCropper(picker);
      expect(picker.showCroppie).to.equal(true);

      (
        picker.shadowRoot.querySelector('.controls .close') as HTMLElement
      ).click();
      await picker.updateComplete;

      expect(picker.showCroppie).to.equal(false);
      expect(
        picker.shadowRoot.querySelectorAll('.croppie .embed > div')
      ).to.have.length(0);
      // nothing was captured, so the field value is left untouched
      expect(picker.value).to.not.be.instanceOf(FormData);
    });

    it('saves the cropped result as form data', async () => {
      const picker = await createPicker();
      await openCropper(picker);

      (
        picker.shadowRoot.querySelector('.controls .submit') as HTMLElement
      ).click();

      // let the croppie result promise settle
      await new Promise((resolve) => setTimeout(resolve, 0));
      await picker.updateComplete;

      const croppie = FakeCroppie.instances[0];
      expect(croppie.resultOptions.format).to.equal('webp');
      expect(croppie.resultOptions.type).to.equal('blob');

      expect(picker.value).to.be.instanceOf(FormData);
      const saved = (picker.value as any).get('avatar');
      expect(saved).to.not.equal(null);
      expect(saved.name).to.equal('filename.webp');

      // the preview switches to the newly cropped image and the editor closes
      expect(picker.url).to.contain('blob:');
      expect(picker.showCroppie).to.equal(false);
    });
  });
});
