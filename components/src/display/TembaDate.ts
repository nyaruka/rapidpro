import { css, html, nothing, PropertyValues, TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { RapidElement } from '../RapidElement';
import { Store } from '../store/Store';
import { DateTime } from 'luxon';

export const Display = {
  date: DateTime.DATE_SHORT,
  datetime: DateTime.DATETIME_SHORT,
  time: DateTime.TIME_SIMPLE,
  timedate: 'timedate',
  duration: 'duration',
  relative: 'relative',
  countdown: 'countdown',
  day: 'LLL d'
};

export class TembaDate extends RapidElement {
  static get styles() {
    return css`
      .date {
        display: inline;
      }
    `;
  }

  @property({ type: String })
  value: string;

  @property({ type: String })
  display = 'date';

  @property({ type: Object, attribute: false })
  datetime: DateTime;

  store: Store;

  public connectedCallback(): void {
    super.connectedCallback();
    this.store = document.querySelector('temba-store');
  }

  public willUpdate(changed: PropertyValues): void {
    super.willUpdate(changed);
    if (changed.has('value')) {
      this.datetime = DateTime.fromISO(this.value);
    }
  }

  public render(): TemplateResult | typeof nothing {
    // unparseable values and zero-value times (e.g. go's zero time,
    // 0001-01-01T00:00:00Z, for a contact that has never been seen) aren't
    // real dates - render nothing rather than something like "2025 years ago"
    if (this.datetime && !(this.datetime.isValid && this.datetime.year > 1)) {
      return nothing;
    }

    if (this.datetime && this.store) {
      this.datetime.setLocale(this.store.getLocale());

      let formatted = '';
      if (this.display === Display.timedate) {
        const hours = Math.abs(
          this.datetime.diffNow().milliseconds / 1000 / 60 / 60
        );

        const day = this.datetime.get('day');
        if (hours < 24 && day == DateTime.now().get('day')) {
          formatted = this.datetime.toLocaleString(Display.time);
        } else if (hours < 24 * 365) {
          formatted = this.datetime.toFormat(Display.day);
        } else {
          formatted = this.datetime.toLocaleString(Display.date);
        }
      } else if (this.display === Display.relative) {
        const minutes = Math.abs(
          this.datetime.diffNow().milliseconds / 1000 / 60
        );
        if (minutes < 1) {
          return html`<span
            class="date"
            title="${this.datetime.toLocaleString(Display.datetime)}"
            >just now</span
          >`;
        }

        formatted = this.store.getShortDuration(this.datetime);
      } else if (this.display === Display.duration) {
        const minutes = Math.abs(
          this.datetime.diffNow().milliseconds / 1000 / 60
        );
        if (minutes < 1) {
          return html`<span
            class="date"
            title="${this.datetime.toLocaleString(Display.datetime)}"
            >just now</span
          >`;
        }
        formatted = this.store.getShortDuration(this.datetime);
      } else if (this.display === Display.countdown) {
        formatted = this.store.getCountdown(this.datetime);
      } else if (this.display === 'day') {
        // the display attribute carries the key ('day'), and Display.day
        // is a luxon format string ('LLL d') rather than an Intl options
        // object, so it must go through toFormat — matching how the
        // timedate branch renders the same format above. The short
        // month-day form is only unambiguous for dates in the current
        // year; anything else falls back to the locale date with year.
        formatted =
          this.datetime.year === DateTime.now().year
            ? this.datetime.toFormat(Display.day)
            : this.datetime.toLocaleString(Display.date);
      } else {
        formatted = this.datetime.toLocaleString(Display[this.display]);
      }

      return html`<span
        class="date"
        title="${this.datetime.toLocaleString(Display.datetime)}"
        >${formatted}</span
      >`;
    }
  }
}
