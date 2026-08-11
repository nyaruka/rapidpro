import { property } from 'lit/decorators.js';
import { TemplateResult, html, css, LitElement, PropertyValues } from 'lit';
import { CustomEventType } from '../interfaces';
import { MediaPicker } from './MediaPicker';
import { getClasses } from '../utils';
import { FieldElement } from './FieldElement';

interface Component {
  name: string;
  type: string;
  content: string;
  variables: { [key: string]: number };
}

interface Translation {
  locale: string;
  status: string;
  channel: { uuid: string; name: string };
  components: Component[];
  variables: { type: string }[];
}

interface Template {
  created_on: string;
  modified_on: string;
  name: string;
  uuid: string;
  base_translation: Translation;
}

export class TemplateEditor extends FieldElement {
  static shadowRootOptions = {
    ...LitElement.shadowRootOptions,
    delegatesFocus: true
  };

  static get styles() {
    return css`
      .component {
        background: #fff;
        border: 1px solid var(--color-widget-border);
        border-radius: var(--curvature);
        padding: 1em;
        margin-top: 1em;
      }

      .content {
      }

      .picker {
        margin-bottom: 0.5em;
        display: block;
      }
      .param {
        display: flex;
        margin-bottom: 0.5em;
        align-items: center;
      }
      label {
        margin-right: 0.5em;
      }

      .content span {
        margin-right: 0.25em;
      }

      .error-message {
        padding-left: 0.5em;
        padding-bottom: 1em;
      }

      .variable {
        display: inline-block;
        margin: 0.25em 0em;
        margin-right: 0.25em;
      }

      .button-wrapper {
        background: #f9f9f9;
        border-radius: var(--curvature);
        padding: 0.5em;
        display: flex;
        flex-direction: column;
      }

      .button-header {
        font-weight: normal;
        margin-left: 0.25em;
        margin-bottom: -0.5em;
        font-size: 0.9em;
        color: #777;
      }

      .buttons {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        margin-bottom: 1em;
      }

      .button {
        background: var(--surface);
        padding: 0.3em 1em;
        border: 1px solid var(--color-widget-border);
        border-radius: var(--curvature);
        min-height: 23px;
        display: flex;
        flex-direction: row;
        align-items: center;
        margin-right: 0.5em;
        margin-top: 0.5em;
        align-items: center;
      }

      .button .content {
        margin-bottom: 0;
      }

      .button .display {
        margin-right: 0.5em;
        background: var(--sunken);
        padding: 0.25em 1em;
        border-radius: var(--curvature);
      }

      .variable {
        --temba-textinput-padding: 5px 5px;
        --temba-textinput-font-size: 0.9em;
        line-height: initial;
      }

      .template {
        background: var(--surface);
        border-radius: var(--curvature);
        border: 1px solid var(--color-widget-border);
        padding: 1em;
        line-height: 2.2em;
        max-height: 50vh;
        overflow-y: auto;
        overflow-x: hidden;
        padding-bottom: 0;
      }

      .label {
        font-size: 0.9em;
        color: #777;
        margin-left: 0.25em;
      }
    `;
  }

  @property({ type: String })
  url: string;

  // initial template uuid
  @property({ type: String })
  template: string;

  @property({ type: Object })
  selectedTemplate: Template;

  // initial variables, not reflected back
  @property({ type: Array })
  variables: string[];

  @property({ type: Array })
  currentVariables: string[];

  @property({ type: Object, attribute: false })
  translation: Translation;

  @property({ type: Boolean })
  translating: boolean;

  @property({ type: Boolean })
  session = false;

  @property({ type: String, attribute: 'template-warning' })
  templateWarning: string;

  pickersLoading: { [key: number]: boolean } = {};

  textInputAttachments: { [index: number]: boolean } = {};

  public willUpdate(changes: PropertyValues): void {
    super.willUpdate(changes);
    if (changes.has('template')) {
      this.textInputAttachments = {};
      this.currentVariables = this.variables || [];

      // check if our variables should be a textinput
      if (this.currentVariables.length > 0) {
        this.currentVariables.forEach((variable, index) => {
          const split = variable.split(':');
          if (split.length > 1) {
            // we have a generary content type
            if (split[0].indexOf('/') === -1) {
              this.textInputAttachments[index] = true;
            }
          }
        });
      }
    }
  }

  private handleTemplateChanged(event: CustomEvent) {
    const prev = this.selectedTemplate;
    this.selectedTemplate = (event.target as any).values[0] as Template;
    if (prev) {
      this.currentVariables = [];
      this.textInputAttachments = {};
    }

    if (this.selectedTemplate) {
      this.translation = this.selectedTemplate.base_translation;
      if (this.translation) {
        this.variables = new Array(
          (this.translation.variables || []).length
        ).fill('');
      } else {
        this.variables = [];
      }
    } else {
      this.translation = null;
      this.variables = [];
    }

    this.fireCustomEvent(CustomEventType.ContextChanged, {
      template: this.selectedTemplate,
      translation: this.translation,
      variables: this.currentVariables
    });
  }

  private handleAttachmentLoading(event: CustomEvent) {
    const media = event.target as MediaPicker;
    const index = parseInt(media.getAttribute('index'));
    this.pickersLoading[index] = event.detail.loading;
    this.requestUpdate();
  }

  private handleAttachmentsChanged(event: CustomEvent) {
    const media = event.target as MediaPicker;
    const index = parseInt(media.getAttribute('index'));

    if (media.attachments.length === 0) {
      this.currentVariables[index] = '';
    } else {
      const attachment = media.attachments[0];
      if (attachment.url && attachment.content_type) {
        this.currentVariables[index] =
          `${attachment.content_type}:${attachment.url}`;
      } else {
        this.currentVariables[index] = ``;
      }
    }
    this.fireContentChange();
    this.requestUpdate('currentVariables');
  }

  private handleVariableChanged(event: InputEvent) {
    const target = event.target as HTMLInputElement;
    const variableIndex = parseInt(target.getAttribute('index'));
    const prefix = target.getAttribute('prefix') || '';

    // add our prefix if we have a value
    let value = target.value;
    if (value) {
      value = prefix + value;
    }

    this.currentVariables[variableIndex] = value;
    this.fireContentChange();
  }

  private fireContentChange() {
    this.fireCustomEvent(CustomEventType.ContentChanged, {
      template: this.selectedTemplate,
      translation: this.translation,
      variables: this.currentVariables
    });
  }

  private renderVariables(component: Component) {
    // create a regex match based on the variable names
    const variableRegex = new RegExp(
      `{{(${Object.keys(component.variables || []).join('|')})}}`,
      'g'
    );

    let variables = null;

    let parts = [];
    if (component.content && component.content.trim().length > 0) {
      parts = component.content?.split(variableRegex) || [];
    }
    const currVariables = this.currentVariables || [];
    if (parts.length > 0) {
      variables = parts.map((part, index) => {
        if (index % 2 === 0) {
          return html`<span class="text">${part}</span>`;
        }
        const variableIndex = component.variables[part];

        return html`<temba-completion
          class="variable"
          type="text"
          ?session=${this.session}
          value=${variableIndex < currVariables.length
            ? currVariables[variableIndex]
            : null}
          @keyup=${this.handleVariableChanged}
          name="${component.name}"
          index="${variableIndex}"
          placeholder="{{${part}}}"
        ></temba-completion>`;
      });
    } else {
      variables = Object.values(component.variables).map((variableIndex) => {
        const variableSpec = this.translation.variables[variableIndex];
        if (
          variableSpec.type === 'image' ||
          variableSpec.type === 'document' ||
          variableSpec.type === 'audio' ||
          variableSpec.type === 'video'
        ) {
          let attachments = [];
          if (this.currentVariables[variableIndex]) {
            const parts = this.currentVariables[variableIndex].split(':');
            const content_type = parts[0];
            const url = parts.slice(1).join(':');
            attachments = [{ url, content_type }];
          }

          const loading = this.pickersLoading[variableIndex];

          const prefix = variableSpec.type + ':';
          let value =
            variableIndex < currVariables.length
              ? currVariables[variableIndex]
              : null;

          if (value && value.startsWith(prefix)) {
            value = value.slice(prefix.length);
          }

          return html`
            ${this.textInputAttachments[variableIndex]
              ? html` <div class="label">
                    ${variableSpec.type.charAt(0).toUpperCase() +
                    variableSpec.type.slice(1)}
                    URL
                  </div>
                  <div
                    style="display:flex;align-items:center;margin-bottom:1em;"
                  >
                    <temba-completion
                      style="flex-grow:1; margin-right:1em;"
                      ?session=${this.session}
                      prefix="${prefix}"
                      index=${variableIndex}
                      value=${value}
                      @keyup=${this.handleVariableChanged}
                    ></temba-completion>
                    <temba-icon
                      name="close"
                      clickable
                      @click=${() => {
                        this.textInputAttachments[variableIndex] = false;
                        this.currentVariables[variableIndex] = '';
                        this.requestUpdate();
                      }}
                    >
                    </temba-icon>
                    <div></div>
                  </div>`
              : html`
                  <div
                    class=${getClasses({ loading })}
                    style="
              display: flex; 
              align-items: center; 
              border-radius: var(--curvature);
              margin-bottom: 0.5em;
              ${attachments.length === 0 && !loading
                      ? `background-color:rgba(0,0,0,.04);`
                      : ``}"
                  >
                    <temba-media-picker
                      accept="${variableSpec.type === 'document'
                        ? 'application/pdf'
                        : variableSpec.type + '/*'}"
                      max="1"
                      index=${variableIndex}
                      icon="attachment_${variableSpec.type}"
                      attachments=${JSON.stringify(attachments)}
                      @temba-loading=${this.handleAttachmentLoading.bind(this)}
                      @change=${this.handleAttachmentsChanged.bind(this)}
                    ></temba-media-picker>
                    <div style="flex-grow:1">
                      ${attachments.length == 0 && !loading
                        ? html`Attach ${variableSpec.type} to continue`
                        : ''}
                    </div>
                    <temba-icon
                      clickable
                      name="edit"
                      @click=${() => {
                        this.currentVariables[variableIndex] = '';
                        this.textInputAttachments[variableIndex] = true;
                        this.requestUpdate();
                      }}
                      style="margin-right:1em"
                    ></temba-icon>
                  </div>
                `}
          `;
        }
      });
    }

    return html`<div class="content">${variables}</div> `;
  }

  public renderComponents(components: Component[]): TemplateResult {
    const nonButtons = components
      .filter((comp) => !comp.type.startsWith('button/'))
      .map(
        (component) =>
          html`<div class="${component['name']}">
            ${this.renderVariables(component)}
          </div>`
      );
    const buttonComponents = components.filter((comp) =>
      comp.type.startsWith('button/')
    );
    const buttons =
      buttonComponents.length > 0 ? this.renderButtons(buttonComponents) : null;
    return html`<div class="main">${nonButtons}</div>
      <div class="buttons">
        ${buttons}
        <div></div>
      </div>`;
  }

  public renderButtons(components): TemplateResult {
    const buttons = components.map((component) => {
      if (component.display) {
        return html`
          <div class="button">
            <div class="display">${component.display}</div>
            ${this.renderVariables(component)}
          </div>
        `;
      } else {
        return html`
          <div class="button">${this.renderVariables(component)}</div>
        `;
      }
    });
    return html`<div class="button-wrapper">
      <div class="button-header">Template Buttons</div>
      <div class="buttons">${buttons}</div>
    </div>`;
  }

  public renderWidget(): TemplateResult {
    let content = null;
    if (this.translation) {
      content = this.renderComponents(this.translation.components);
    } else if (this.selectedTemplate) {
      content = html`<div class="error-message">
        This template currently has no approved translations.
      </div>`;
    }

    return html`
      <div>
        <temba-select
          searchable
          ?clearable=${!this.translating}
          ?disabled=${this.translating}
          valuekey="uuid"
          class="picker"
          value="${this.template}"
          endpoint="${this.url}"
          shouldExclude=${(template) => template.status !== 'approved'}
          placeholder="Select a template"
          @temba-content-changed=${this.swallowEvent}
          @change=${this.handleTemplateChanged}
        >
        </temba-select>
        ${this.templateWarning && this.selectedTemplate
          ? html`<temba-alert
              level="warning"
              style="margin-bottom: 0.5em; display: block;"
              >${this.templateWarning}</temba-alert
            >`
          : null}
        ${content ? html` <div class="template">${content}</div>` : null}
      </div>
    `;
  }
}
