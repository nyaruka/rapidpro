import { PropertyValueMap, PropertyValues, css, html } from 'lit';
import { RapidElement } from '../RapidElement';
import { property, state } from 'lit/decorators.js';
import { getClasses } from '../utils';
import { Lightbox } from './Lightbox';
import { WebChatIcon } from '../webchat';

enum ThumbnailContentType {
  IMAGE = 'image',
  AUDIO = 'audio',
  VIDEO = 'video',
  DOCUMENT = 'document',
  LOCATION = 'location',
  OTHER = 'other'
}

const ThumbnailIcons = {
  [ThumbnailContentType.IMAGE]: WebChatIcon.attachment_image,
  [ThumbnailContentType.AUDIO]: WebChatIcon.attachment_audio,
  [ThumbnailContentType.VIDEO]: WebChatIcon.attachment_video,
  [ThumbnailContentType.DOCUMENT]: WebChatIcon.attachment_document,
  [ThumbnailContentType.OTHER]: WebChatIcon.attachment
};

export class Thumbnail extends RapidElement {
  static get styles() {
    return css`
      :host {
        display: inline;
      }

      .wrapper {
        padding: var(--thumb-padding, 0.4em);
        background: var(--thumb-background, #fff);
        box-shadow: var(--widget-box-shadow);
        cursor: pointer;
        border-radius: calc(var(--curvature) * 1.5);
        border: 0px solid #f3f3f3;
      }

      .wrapper.zoom {
        border: none;
        padding: 0 !important;
        border-radius: 0 !important;
        overflow: hidden !important;
      }

      .zoom .thumb {
        border-radius: 0px !important;
        width: calc(var(--thumb-size, 4em) + 0.8em);
        max-height: calc(90vh - 10em);
      }

      .thumb {
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        border-radius: var(--curvature);
        max-height: calc(var(--thumb-size, 4em) * 2);
        max-width: calc(var(--thumb-size, 4em) * 2);
        height: var(--thumb-size, 4em);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 400;
        color: var(--thumb-icon, #bbb);
      }

      .thumb.document,
      .thumb.video {
        border: 1px solid #eee;
      }

      .audio-player {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 8px;
        background: rgba(0, 0, 0, 0.05);
        border-radius: var(--curvature);
        cursor: default;
      }

      .audio-play-btn {
        cursor: pointer;
        color: #666;
        display: flex;
        align-items: center;
        flex-shrink: 0;
      }

      .audio-play-btn:hover {
        color: #333;
      }

      .audio-progress-bar {
        flex: 1;
        height: 3px;
        background: #ddd;
        border-radius: 2px;
        overflow: hidden;
        min-width: 60px;
        cursor: pointer;
      }

      .audio-progress-fill {
        height: 100%;
        background: var(--color-primary, #2387ca);
        border-radius: 2px;
        transition: width 0.15s linear;
      }

      .audio-time {
        font-size: 11px;
        color: #999;
        flex-shrink: 0;
        min-width: 28px;
        text-align: right;
      }

      .wrapper:hover .thumb.icon {
      }

      .viewer {
        display: block;
      }

      .zoom .viewer {
        display: block;
      }

      .download {
        display: none;
        position: absolute;
        right: 0em;
        bottom: 0em;
        border-radius: var(--curvature);
        transform: scale(0.2) translate(3em, 3em);
        padding: 0.4em;
      }

      .zoom .download {
        display: block;
        background: rgba(0, 0, 0, 0.5);
      }

      .zoom .download:hover {
        background: rgba(0, 0, 0, 0.6);
        cursor: pointer;
      }
    `;
  }

  @property({ type: String })
  url: string;

  @property({ type: String })
  attachment: string;

  @property({ type: Number })
  ratio: number = 0;

  @property({ type: Boolean })
  preview: boolean = true;

  @property({ type: Boolean, attribute: false })
  zoom: boolean;

  @property({ type: String, attribute: true })
  contentType: string;

  @property({ type: Number, attribute: false })
  latitude: number;

  @property({ type: Number, attribute: false })
  longitude: number;

  // cached tile URL for location thumbnails
  @property({ type: String, attribute: false })
  private tileUrl: string = '';

  // audio player state
  private audio: HTMLAudioElement | null = null;

  // set when an image attachment fails to load, so we fall back to an
  // icon instead of the browser's broken-image glyph
  @state()
  private imageError = false;

  @state()
  private audioPlaying = false;

  @state()
  private audioProgress = 0;

  @state()
  private audioDuration = 0;

  private handleAudioPlayClick(e: Event) {
    e.stopPropagation();

    if (!this.audio) {
      this.audio = new Audio(this.url);
      this.audio.addEventListener('timeupdate', () => {
        if (this.audio.duration) {
          this.audioProgress = this.audio.currentTime / this.audio.duration;
          this.audioDuration = this.audio.duration;
        }
      });
      this.audio.addEventListener('ended', () => {
        this.audioPlaying = false;
        this.audioProgress = 0;
      });
      this.audio.addEventListener('error', () => {
        this.audioPlaying = false;
        this.audioProgress = 0;
      });
    }

    if (this.audioPlaying) {
      this.audio.pause();
      this.audioPlaying = false;
    } else {
      this.audio.play().catch(() => {
        this.audioPlaying = false;
      });
      this.audioPlaying = true;
    }
  }

  private handleProgressClick(e: MouseEvent) {
    e.stopPropagation();
    if (!this.audio || !this.audio.duration) return;
    const bar = e.currentTarget as HTMLElement;
    const rect = bar.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    this.audio.currentTime = pct * this.audio.duration;
  }

  private formatTime(seconds: number): string {
    const s = Math.floor(seconds);
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return `${m}:${rem.toString().padStart(2, '0')}`;
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this.audio) {
      this.audio.pause();
      this.audio = null;
    }
  }

  // convert lat/lng to tile coordinates for OSM
  private latLngToTile(lat: number, lng: number, zoom: number) {
    const n = Math.pow(2, zoom);
    const x = Math.floor(((lng + 180) / 360) * n);
    const latRad = (lat * Math.PI) / 180;
    const y = Math.floor(
      ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) *
        n
    );
    return { x, y, z: zoom };
  }

  protected willUpdate(changes: PropertyValues): void {
    super.willUpdate(changes);

    // convert our attachment to a url and label
    if (changes.has('attachment')) {
      // a new attachment gets a fresh shot at loading its image
      this.imageError = false;
      if (this.attachment) {
        const splitIndex = this.attachment.indexOf(':');
        if (splitIndex === -1) {
          this.url = this.attachment;
        } else {
          const contentType = this.attachment.substring(0, splitIndex);
          this.url = this.attachment.substring(splitIndex + 1);

          if (contentType.startsWith('image')) {
            this.contentType = ThumbnailContentType.IMAGE;
          } else if (contentType.startsWith('audio')) {
            this.contentType = ThumbnailContentType.AUDIO;
          } else if (contentType.startsWith('video')) {
            this.contentType = ThumbnailContentType.VIDEO;
          } else if (contentType.startsWith('application')) {
            this.contentType = ThumbnailContentType.DOCUMENT;
          } else if (contentType.startsWith('geo')) {
            this.contentType = ThumbnailContentType.LOCATION;
            // Parse coordinates from URL which is already stripped of "geo:" prefix
            // Format is now just: lat,lng
            const coords = this.url.match(/^([^,]+),([^,]+)/);
            if (coords) {
              this.latitude = parseFloat(coords[1]);
              this.longitude = parseFloat(coords[2]);
              const tile = this.latLngToTile(this.latitude, this.longitude, 13);
              this.tileUrl = `https://tile.openstreetmap.org/${tile.z}/${tile.x}/${tile.y}.png`;
            }
          } else {
            this.contentType = ThumbnailContentType.OTHER;
          }
        }
      }
    }

    // calculate tile URL when latitude/longitude changes
    if (changes.has('latitude') || changes.has('longitude')) {
      if (
        this.latitude !== undefined &&
        this.longitude !== undefined &&
        !isNaN(this.latitude) &&
        !isNaN(this.longitude)
      ) {
        const tile = this.latLngToTile(this.latitude, this.longitude, 13);
        this.tileUrl = `https://tile.openstreetmap.org/${tile.z}/${tile.x}/${tile.y}.png`;
      } else {
        this.tileUrl = '';
      }
    }
  }

  protected updated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(changes);

    if (
      changes.has('contentType') &&
      this.contentType === ThumbnailContentType.IMAGE
    ) {
      const toObserve = this.shadowRoot.querySelector('.observe');
      if (toObserve) {
        new ResizeObserver((e, observer) => {
          if (toObserve.clientHeight > 0 && toObserve.clientWidth > 0) {
            this.ratio = toObserve.clientHeight / toObserve.clientWidth;
            this.preview =
              this.ratio === 0 || (this.ratio > 0.25 && this.ratio <= 1.5);
            observer.disconnect();
          }
        }).observe(toObserve);
      }
    }
  }

  public handleThumbnailClicked(e?: Event) {
    // a thumbnail click is a self-contained action (lightbox / open / play);
    // don't let it bubble to a clickable ancestor (e.g. a list row that would
    // otherwise navigate away instead of showing the attachment)
    e?.stopPropagation();
    if (
      this.contentType === ThumbnailContentType.IMAGE &&
      this.preview &&
      !this.imageError
    ) {
      const lightbox = document.querySelector('temba-lightbox') as Lightbox;
      if (lightbox) {
        window.setTimeout(() => {
          lightbox.showElement(this);
        }, 100);
      } else {
        // no lightbox mounted on this page — just open the image. This must
        // happen synchronously inside the click's user activation or popup
        // blockers will eat it.
        window.open(this.url, '_blank');
      }
    } else if (this.contentType === ThumbnailContentType.LOCATION) {
      // open location in openstreetmap
      const osmUrl = `https://www.openstreetmap.org/?mlat=${this.latitude}&mlon=${this.longitude}#map=15/${this.latitude}/${this.longitude}`;
      window.open(osmUrl, '_blank');
    } else if (this.contentType === ThumbnailContentType.AUDIO) {
      // audio has inline controls, no click action needed
    } else {
      window.open(this.url, '_blank');
    }
  }

  public handleDownload(e: Event) {
    e.stopPropagation();
    e.preventDefault();

    // open this.url in another tab
    window.open(this.url, '_blank');
  }

  public render() {
    return html`
      <div
        @click=${this.handleThumbnailClicked.bind(this)}
        class="${getClasses({ wrapper: true, zoom: this.zoom })}"
        style="${this.contentType === ThumbnailContentType.AUDIO
          ? 'cursor: default;'
          : ''}"
        url=${this.url}
      >
        ${this.contentType === ThumbnailContentType.IMAGE &&
        this.preview &&
        !this.imageError
          ? html`<div class=""><div class="download" @click=${this.handleDownload.bind(
              this
            )}><temba-icon size="1" style="color:#fff;" name="download"></temba-icon></div><img
          class="observe thumb ${this.contentType}"
          src="${this.url}"
          @error=${() => {
            this.imageError = true;
          }}
        ></img></div>`
          : this.contentType === ThumbnailContentType.AUDIO
            ? html`<div class="audio-player">
                <div class="audio-play-btn" @click=${this.handleAudioPlayClick}>
                  ${this.audioPlaying
                    ? html`<svg
                        viewBox="0 0 24 24"
                        width="14"
                        height="14"
                        fill="currentColor"
                      >
                        <rect x="5" y="3" width="4" height="18" />
                        <rect x="15" y="3" width="4" height="18" />
                      </svg>`
                    : html`<svg
                        viewBox="0 0 24 24"
                        width="14"
                        height="14"
                        fill="currentColor"
                      >
                        <polygon points="6,3 20,12 6,21" />
                      </svg>`}
                </div>
                <div
                  class="audio-progress-bar"
                  @click=${this.handleProgressClick}
                >
                  <div
                    class="audio-progress-fill"
                    style="width: ${this.audioProgress * 100}%"
                  ></div>
                </div>
                <div class="audio-time">
                  ${this.audioDuration
                    ? this.formatTime(
                        this.audioPlaying || this.audioProgress > 0
                          ? this.audio?.currentTime || 0
                          : this.audioDuration
                      )
                    : ''}
                </div>
              </div>`
            : html`
                ${this.contentType === ThumbnailContentType.LOCATION
                  ? html`<img
                      style="height:125px;margin-bottom:-3px;border-radius:var(--curvature);"
                      src="${this.tileUrl}"
                      alt="Location preview"
                    />`
                  : html`<div
                      style="padding:var(--thumb-icon-padding, 1em); background:rgba(0,0,0,.05);border-radius:var(--curvature);"
                    >
                      <temba-icon
                        size="1.5"
                        name="${ThumbnailIcons[this.contentType]}"
                      ></temba-icon>
                    </div>`}
              `}
      </div>
    `;
  }
}
