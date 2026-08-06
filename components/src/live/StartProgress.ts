import { css, html, PropertyValueMap, TemplateResult } from 'lit';
import { RapidElement } from '../RapidElement';
import { property } from 'lit/decorators.js';
import { fetchResults, showModax } from '../utils';

export class StartProgress extends RapidElement {
  static styles = css`
    temba-icon[name='close'] {
      cursor: pointer;
      margin: 0 4px;
    }

    temba-icon[name='close']:hover {
      color: var(--color-primary-dark);
    }
  `;
  @property({ type: String })
  id: string;

  @property({ type: Number })
  current: number;

  @property({ type: Number })
  total: number;

  @property({ type: Number })
  refreshes: number = 0;

  @property({ type: String })
  eta: string;

  @property({ type: Boolean })
  complete = false;

  @property({ type: Boolean })
  running = false;

  @property({ type: String })
  message: string;

  @property({ type: String })
  statusEndpoint: string;

  @property({ type: String })
  interruptTitle: string;

  @property({ type: String })
  interruptEndpoint: string;

  public updated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(changes);
    if (changes.has('id')) {
      this.refresh();
    }

    // Useful for simulating progress
    /*
    if (changes.has('current')) {
      this.requestUpdate();
      setTimeout(() => {
        this.current = this.current + 100000;
        this.complete = this.current >= this.total;
        this.message = null;

        if (this.complete) {
          this.scheduleRemoval();
        }
      }, 5000);
    }*/
  }

  public interruptStart(): void {
    showModax(this.interruptTitle, this.interruptEndpoint);
  }

  public refresh(): void {
    fetchResults(this.statusEndpoint, this.getHeaders()).then((data: any) => {
      if (data.length > 0) {
        this.refreshes++;
        const start = data[0];

        this.current = start.progress.current;
        this.total = start.progress.total;

        this.complete =
          start.status == 'Completed' ||
          start.status == 'Failed' ||
          start.status == 'Interrupted';

        this.running = start.status === 'Started';

        if (start.status === 'Pending') {
          this.message = 'Preparing to start..';
        } else if (start.status === 'Queued') {
          this.message = 'Waiting..';
        } else {
          this.message = null;
        }

        if (start.status === 'Started') {
          const elapsed =
            new Date().getTime() - new Date(start.modified_on).getTime();
          const rate = this.current / elapsed;

          // only calculate eta if the rate is actually reasonable
          if (rate > 0.1) {
            const eta = new Date(
              new Date().getTime() + (this.total - this.current) / rate
            );
            // Don't bother with estimates months out
            const nextMonth = new Date();
            nextMonth.setMonth(nextMonth.getMonth() + 2);
            if (eta > nextMonth) {
              this.eta = null;
            } else {
              this.eta = eta.toISOString();
            }
          }
        }

        if (!this.complete && this.current < this.total) {
          // refresh with a backoff up to 1 minute
          setTimeout(
            () => {
              this.refresh();
            },
            Math.min(1000 * this.refreshes, 60000)
          );
        }

        if (this.complete) {
          this.scheduleRemoval();
        }
      }
    });
  }

  public scheduleRemoval(): void {
    setTimeout(() => {
      this.remove();
    }, 5000);
  }

  public render(): TemplateResult {
    return html`<temba-progress
      total=${this.total}
      current=${this.current}
      eta=${this.eta}
      message=${this.message}
    >
      ${this.running && this.interruptTitle && this.interruptEndpoint
        ? html`<temba-icon
            name="close"
            @click=${this.interruptStart}
          ></temba-icon>`
        : null}
    </temba-progress>`;
  }
}
