import { css, html, TemplateResult } from 'lit';
import { Select, SelectOption } from './Select';
import { property } from 'lit/decorators.js';
import { getFullName } from '../../display/TembaUser';

export interface UserOption extends SelectOption {
  email: string;
  name: string;
  avatar: string;
}

export class UserSelect extends Select<UserOption> {
  static get styles() {
    return css`
      ${super.styles}

      :host {
        width: 150px;
        display: block;
      }
    `;
  }

  @property({ type: String })
  endpoint = '/api/v2/users.json';

  @property({ type: String })
  nameKey = 'name';

  @property({ type: String })
  valueKey = 'email';

  @property({ type: String })
  placeholder: string = 'Select a user';

  @property({ type: Boolean })
  sorted: boolean = true;

  @property({ type: Object })
  user: UserOption;

  constructor() {
    super();
    this.shouldExclude = (option: UserOption) => {
      const selected = this.values[0];
      return option.email === selected?.email;
    };
  }

  public prepareOptionsDefault(options: UserOption[]): UserOption[] {
    options.forEach((option) => {
      option.name = getFullName(option);
    });
    return options;
  }

  public renderOptionDefault(option: UserOption): TemplateResult {
    if (!option) {
      return html``;
    }

    return html`<temba-user
      email=${option.email}
      name=${option.name}
      avatar=${option.avatar}
      showname
    ></temba-user>`;
  }
}
