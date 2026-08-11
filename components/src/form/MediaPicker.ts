import { TemplateResult, css, html } from 'lit';
import { RapidElement } from '../RapidElement';
import { property } from 'lit/decorators.js';
import { Attachment, CustomEventType } from '../interfaces';
import { Icon } from '../Icons';
import {
  DEFAULT_MEDIA_ENDPOINT,
  WebResponse,
  getClasses,
  postFormData
} from '../utils';

const verifyAccept = (type: string, accept: string): boolean => {
  if (accept) {
    const allowed = accept.split(',').map((x) => x.trim());
    return (
      allowed.includes(type) || allowed.includes(type.split('/')[0] + '/*')
    );
  }
  return true;
};

export class MediaPicker extends RapidElement {
  static get styles() {
    return css`
      .drop-mask {
        border-radius: var(--curvature-widget);
        transition: opacity ease-in-out var(--transition-speed);
      }

      .highlight .drop-mask {
      }

      .drop-mask > div {
        margin: auto;
        border-radius: var(--curvature-widget);
        font-weight: 400;
        color: rgba(0, 0, 0, 0.5);
      }

      .attachments {
      }

      .attachments-list {
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;
        padding: 0.2em;
        align-items: center;
      }

      .attachment-item {
        padding: 0.4em;
        padding-top: 1em;
      }

      .attachment-item.error {
        background: #fff;
        color: rgba(250, 0, 0, 0.75);
        padding: 0.2em;
        margin: 0.3em 0.5em;
        border-radius: var(--curvature);
        display: block;
      }

      .remove-item {
        --icon-color: #ccc;
        background: #fff;
        border-radius: 99%;
        transition: transform 200ms linear;
        transform: scale(0);
        display: block;
        margin-bottom: -24px;
        margin-left: 10px;
        width: 1em;
        height: 1em;
      }

      .attachment-item:hover .remove-item {
        transform: scale(1);
      }

      .remove-item:hover {
        --icon-color: #333;
        cursor: pointer;
      }

      .attachment-name {
        align-self: center;
        font-size: 12px;
        padding: 2px 8px;
      }

      #upload-input {
        display: none;
      }

      .upload-label {
        display: flex;
        align-items: center;
      }

      .upload-icon {
        color: rgb(102, 102, 102);
      }

      .add-attachment {
        padding: 1em;
        background-color: rgba(0, 0, 0, 0.05);
        border-radius: var(--curvature);
        color: #aaa;
        margin: 0.5em;
      }

      .add-attachment:hover {
        background-color: rgba(0, 0, 0, 0.07);
        cursor: pointer;
      }
    `;
  }

  @property({ type: String, attribute: false })
  endpoint = DEFAULT_MEDIA_ENDPOINT;

  @property({ type: Boolean })
  pendingDrop: boolean;

  @property({ type: Boolean })
  ignoreDrops = false;

  @property({ type: String })
  icon = Icon.add;

  @property({ type: String })
  accept = ''; //e.g. ".xls,.xlsx"

  @property({ type: Number })
  max = 3;

  @property({ type: Array })
  attachments: Attachment[] = [];

  @property({ type: Boolean, attribute: false })
  uploading: boolean;

  public updated(changes: Map<string, any>): void {
    super.updated(changes);
    if (changes.has('attachments')) {
      // wait one cycle to fire change for tests
      setTimeout(() => {
        this.dispatchEvent(new Event('change'));
      }, 0);
    }

    if (changes.has('uploading')) {
      this.dispatchEvent(
        new CustomEvent(CustomEventType.Loading, {
          detail: { loading: this.uploading }
        })
      );
    }
  }

  private getAcceptableFiles(evt: DragEvent): File[] {
    const dt = evt.dataTransfer;
    if (dt) {
      const files = [...dt.files];
      return files.filter((file) => verifyAccept(file.type, this.accept));
    }
  }

  private handleDragEnter(evt: DragEvent): void {
    this.highlight(evt);
  }

  private handleDragOver(evt: DragEvent): void {
    this.highlight(evt);
  }

  private handleDragLeave(evt: DragEvent): void {
    this.unhighlight(evt);
  }

  private handleDrop(evt: DragEvent): void {
    if (this.ignoreDrops) {
      return;
    }
    this.unhighlight(evt);
    if (this.canAcceptAttachments()) {
      this.uploadFiles(this.getAcceptableFiles(evt));
    }
  }

  public canAcceptAttachments() {
    return this.attachments.length < this.max;
  }

  private highlight(evt: DragEvent): void {
    if (this.ignoreDrops) {
      return;
    }

    evt.preventDefault();
    evt.stopPropagation();
    if (this.canAcceptAttachments()) {
      this.pendingDrop = true;
    }
  }

  private unhighlight(evt: DragEvent): void {
    if (this.ignoreDrops) {
      return;
    }
    evt.preventDefault();
    evt.stopPropagation();
    this.pendingDrop = false;
  }

  private addCurrentAttachment(attachmentToAdd: any) {
    this.attachments.push(attachmentToAdd);
    this.requestUpdate('attachments');
  }

  private removeCurrentAttachment(attachmentToRemove: any) {
    this.attachments = this.attachments.filter(
      (currentAttachment) => currentAttachment !== attachmentToRemove
    );
    this.requestUpdate('attachments');
  }

  private handleRemoveFileClicked(evt: Event): void {
    const target = evt.target as HTMLDivElement;
    const currentAttachmentToRemove = this.attachments.find(
      ({ url }) => url === target.id
    );
    if (currentAttachmentToRemove) {
      this.removeCurrentAttachment(currentAttachmentToRemove);
    }
  }

  private handleUploadFileInputChanged(evt: Event): void {
    const target = evt.target as HTMLInputElement;
    const files = target.files;
    this.uploadFiles([...files]);
  }

  public uploadFiles(files: File[]): void {
    let filesToUpload = [];

    //remove duplicate files that have already been uploaded
    filesToUpload = files.filter((file) => {
      // check our file type against accepts
      if (this.accept) {
        if (!verifyAccept(file.type, this.accept)) {
          return false;
        }
      }

      const index = this.attachments.findIndex(
        (value) => value.filename === file.name && value.size === file.size
      );
      if (index === -1) {
        return file;
      }
    });

    filesToUpload.map((fileToUpload) => {
      this.uploadFile(fileToUpload);
    });
  }

  private uploadFile(file: File): void {
    this.uploading = true;

    const url = this.endpoint;
    const payload = new FormData();
    payload.append('file', file);
    postFormData(url, payload)
      .then((response: WebResponse) => {
        if (this.attachments.length < this.max) {
          const attachment = response.json as Attachment;
          if (attachment) {
            this.addCurrentAttachment(attachment);
          }
        }
      })
      .catch((error: WebResponse) => {
        let uploadError = '';
        if (error.status === 400) {
          uploadError = error.json.file[0];
        } else {
          uploadError = 'Server failure';
        }
        console.error(uploadError);
      })
      .finally(() => {
        this.uploading = false;
      });
  }

  private renderUploader(): TemplateResult {
    if (this.uploading) {
      return html`<temba-loading units="3" size="12"></temba-loading>`;
    } else {
      return this.attachments.length < this.max
        ? html`<input
              type="file"
              id="upload-input"
              ?multiple=${this.max > 1}
              accept="${this.accept}"
              @change="${this.handleUploadFileInputChanged}"
            />
            <label
              id="upload-label"
              class="actions-left upload-label"
              for="upload-input"
            >
              <div class="add-attachment">
                <temba-icon name="${this.icon}" size="1.5"></temba-icon>
              </div>
            </label>`
        : null;
    }
  }

  public render(): TemplateResult {
    return html` <div
      class=${getClasses({ container: true, highlight: this.pendingDrop })}
      @dragenter="${this.handleDragEnter}"
      @dragover="${this.handleDragOver}"
      @dragleave="${this.handleDragLeave}"
      @drop="${this.handleDrop}"
    >
      <div class="drop-mask">
        <div class="attachments-list">
          ${this.attachments.map((validAttachment) => {
            return html`<div class="attachment-item">
              <temba-icon
                class="remove-item"
                @click="${this.handleRemoveFileClicked}"
                id="${validAttachment.url}"
                name="${Icon.delete_small}"
              ></temba-icon>
              <temba-thumbnail
                attachment="${validAttachment.content_type}:${validAttachment.url}"
              ></temba-thumbnail>
            </div>`;
          })}
          ${this.renderUploader()}
        </div>
      </div>
    </div>`;
  }
}
