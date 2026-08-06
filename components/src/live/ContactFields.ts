import {
  css,
  html,
  PropertyValueMap,
  PropertyValues,
  TemplateResult
} from 'lit';
import { property } from 'lit/decorators.js';
import { getClasses, postJSON } from '../utils';
import { ContactFieldEditor } from './ContactFieldEditor';
import { ContactStoreElement } from './ContactStoreElement';
import { Checkbox } from '../form/Checkbox';
import { Contact, ContactField, CustomEventType } from '../interfaces';
import { Events } from '../events/eventRenderers';

const MIN_FOR_FILTER = 10;

export class ContactFields extends ContactStoreElement {
  // we render field values, so field changes are the only events we need -
  // the central watcher hands us a refetched contact when they happen
  protected watchTypes = [Events.CONTACT_FIELD_CHANGED];

  static get styles() {
    return css`
      .field {
        display: flex;
        margin: 1em 0.3em;
        box-shadow: 0 0 0.2em rgba(0, 0, 0, 0.15);
        border-radius: 0px;
        align-items: center;
        overflow: hidden;
      }

      .show-all .unset,
      .featured {
        display: block !important;
      }

      .unset {
        display: none;
      }

      .field:hover {
        box-shadow:
          1px 1px 6px 2px rgba(0, 0, 0, 0.05),
          0px 0px 0px 2px var(--color-link-primary);
        cursor: pointer;
      }

      .label {
        padding: 0.25em 1em;
        border-top-left-radius: 0px;
        border-bottom-left-radius: 0px;
        color: #777;
        font-size: 0.9em;
        font-weight: 400;
        box-shadow: 0px 0px 20px 0px rgba(0, 0, 0, 0.1) inset;
      }

      .value {
        --icon-color: #ddd;
        max-width: 150px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        padding: 0.25em 1em;
        border-top-right-radius: 0px;
        border-bottom-right-radius: 0px;
        font-size: 0.9em;
      }

      .toggle {
        display: flex;
        align-items: center;
        margin-top: 0.5em;
      }

      .disabled .toggle {
        display: none;
      }
    `;
  }

  @property({ type: Boolean })
  system: boolean;

  @property({ type: Boolean })
  dirty: boolean;

  @property({ type: Boolean })
  showAll: boolean;

  @property({ type: String })
  timezone: string;

  @property({ type: String })
  role: string;

  @property({ type: Boolean })
  disabled = false;

  // tracks whether the store's contact field definitions have loaded. these
  // load independently of the contact data this element fetches, so we can't
  // render field rows until they're present (see render). this is reactive so
  // that flipping it re-renders once the definitions arrive.
  @property({ type: Boolean, attribute: false })
  fieldsReady = false;

  connectedCallback(): void {
    super.connectedCallback();
    this.handleFieldChanged = this.handleFieldChanged.bind(this);

    // field definitions are usually already loaded by the time this element
    // connects, but during a cold load they may still be in flight
    this.fieldsReady =
      !!this.store &&
      (this.store.ready ||
        (this.store.getKeyedAssets()['fields'] || []).length > 0);
  }

  protected storeUpdated(event: CustomEvent) {
    super.storeUpdated(event);
    // the store fires a StoreUpdated for the fields endpoint once the field
    // definitions have loaded; that's our signal that it's safe to render
    if (this.store && event.detail.url === this.store.fieldsEndpoint) {
      this.fieldsReady = true;
    }
  }

  private isAgent(): boolean {
    return this.role === 'T' || this.role?.toLowerCase() === 'agent';
  }

  private getAgentAccess(field: ContactField): 'none' | 'view' | 'edit' {
    const access = field.agent_access?.toLowerCase();
    if (access === 'n' || access === 'none') return 'none';
    if (access === 'e' || access === 'edit') return 'edit';
    return 'view';
  }

  private canViewField(field: ContactField): boolean {
    return !this.isAgent() || this.getAgentAccess(field) !== 'none';
  }

  private canEditField(field: ContactField): boolean {
    return (
      !this.disabled &&
      (!this.isAgent() || this.getAgentAccess(field) === 'edit')
    );
  }

  private getVisibleFieldEntries(): [string, string][] {
    if (!this.data || !this.fieldsReady) return [];
    return Object.entries(this.data.fields).filter(
      ([key]: [string, string]) => {
        const field = this.store.getContactField(key);
        return !!field && this.canViewField(field);
      }
    );
  }

  /**
   * A watcher delivery carries server state from before an edit the user is
   * still making, so keep the value we already have for any field whose
   * editor is dirty - rebinding it would drop what they typed.
   */
  protected mergeWatchedContact(contact: Contact, previous: Contact): Contact {
    if (!previous || !previous.fields) {
      return contact;
    }

    const editors = Array.from(
      this.shadowRoot?.querySelectorAll('temba-contact-field') || []
    ) as ContactFieldEditor[];
    const editing = editors.filter(
      (editor) => editor.dirty && editor.key in previous.fields
    );

    if (editing.length === 0) {
      return contact;
    }

    const fields = { ...contact.fields };
    editing.forEach((editor) => {
      fields[editor.key] = previous.fields[editor.key];
    });
    return { ...contact, fields };
  }

  public willUpdate(changed: PropertyValues): void {
    super.willUpdate(changed);
    if (
      (changed.has('data') ||
        changed.has('fieldsReady') ||
        changed.has('role')) &&
      this.data &&
      this.fieldsReady
    ) {
      if (this.getVisibleFieldEntries().length <= MIN_FOR_FILTER) {
        this.showAll = true;
      }
    }
  }

  protected updated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(changes);
    if (
      (changes.has('data') ||
        changes.has('fieldsReady') ||
        changes.has('role')) &&
      this.data &&
      this.fieldsReady
    ) {
      this.fireCustomEvent(CustomEventType.DetailsChanged, {
        count: this.getVisibleFieldEntries().filter(([, value]) => !!value)
          .length
      });
    }
  }

  public handleFieldChanged(evt: InputEvent) {
    const field = evt.currentTarget as ContactFieldEditor;
    const definition = this.store.getContactField(field.key);
    if (!definition || !this.canEditField(definition)) return;

    const value = field.value;

    // TODO: Use contact.postChanges instead of postJSON
    postJSON(this.writeEndpoint + this.data.uuid, {
      fields: { [field.key]: value }
    })
      .then((response: any) => {
        field.handleResponse(response);

        // returns a single contact with latest updates
        this.setContact(response.json);
      })
      .catch((error) => {
        field.handleResponse(error);
      });
  }

  public handleToggle(evt: Event) {
    const checkbox = evt.currentTarget as Checkbox;
    this.showAll = checkbox.checked;
  }

  public render(): TemplateResult {
    // we need both the contact data and the field definitions (loaded during
    // store init) before we can render. these load independently, so the
    // contact data can arrive first; rendering then would crash on missing
    // field definitions and leave the tab empty (see getContactField below).
    if (this.data && this.fieldsReady) {
      // guard against keys with no matching field definition (mid-load races
      // or fields that have since been deleted) so a single missing
      // definition can't throw and blank out the entire tab
      const fieldsToShow = this.getVisibleFieldEntries().sort(
        (a: [string, string], b: [string, string]) => {
          const [ak] = a;
          const [bk] = b;
          const fieldA = this.store.getContactField(ak);
          const fieldB = this.store.getContactField(bk);

          if (fieldA.type === 'ward') {
            return 1;
          }

          if (fieldB.type === 'ward') {
            return -1;
          }

          if (
            fieldA.type === 'district' &&
            fieldB.type !== 'ward' &&
            fieldB.type !== 'district'
          ) {
            return 1;
          }

          if (
            fieldB.type === 'district' &&
            fieldA.type !== 'ward' &&
            fieldA.type !== 'district'
          ) {
            return -1;
          }

          if (
            fieldA.type === 'state' &&
            fieldB.type !== 'ward' &&
            fieldB.type !== 'district' &&
            fieldB.type !== 'state'
          ) {
            return 1;
          }

          if (
            fieldB.type === 'state' &&
            fieldA.type !== 'ward' &&
            fieldA.type !== 'district' &&
            fieldA.type !== 'state'
          ) {
            return -1;
          }

          if (fieldA.featured && !fieldB.featured) {
            return -1;
          }

          if (fieldB.featured && !fieldA.featured) {
            return 1;
          }

          const priority = fieldB.priority - fieldA.priority;
          if (priority !== 0) {
            return priority;
          }

          return ak.localeCompare(bk);
        }
      );

      if (fieldsToShow.length == 0) {
        return html`<slot name="empty"></slot>`;
      }

      const fields = fieldsToShow.map((entry: [string, string]) => {
        const [k, v] = entry;
        const field = this.store.getContactField(k);
        return html`<temba-contact-field
          class=${getClasses({ set: !!v, unset: !v, featured: field.featured })}
          key=${field.key}
          name=${field.label}
          value=${v}
          type=${field.value_type}
          @change=${this.handleFieldChanged}
          timezone=${this.timezone}
          ?disabled=${!this.canEditField(field)}
        ></temba-contact-field>`;
      });

      return html`
        <div class=${getClasses({ disabled: this.disabled })}>
          <div class="fields ${this.showAll ? 'show-all' : ''}">${fields}</div>
          ${fieldsToShow.length >= MIN_FOR_FILTER
            ? html`<div class="toggle">
                <div style="flex-grow: 1"></div>
                <div>
                  <temba-checkbox
                    ?checked=${this.showAll}
                    @change=${this.handleToggle}
                    label="Show All"
                  ></temba-checkbox>
                </div>
              </div>`
            : null}
        </div>
      `;
    }

    return super.render();
  }
}
