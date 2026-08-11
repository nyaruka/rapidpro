import { css, html, LitElement, TemplateResult } from 'lit';
import { FeatureProperties } from '../interfaces';
import { getUrl, postJSON, WebResponse } from '../utils';
import { TextInput } from '../form/TextInput';
import { styleMap } from 'lit-html/directives/style-map.js';
import { Icon } from '../Icons';

import { property } from 'lit/decorators.js';
import { Select } from '../form/select/Select';

export class AliasEditor extends LitElement {
  static get styles() {
    return css`
      :host {
        line-height: normal;
      }

      temba-textinput {
        height: 150px;
      }

      #left-column {
        display: inline-block;
        margin-left: 10px;
        width: 300px;
        z-index: 100;
      }

      .search {
        margin-bottom: 10px;
      }

      .feature {
        padding: 4px 14px;
        font-size: 16px;
      }

      .level-0 {
        margin-left: 0px;
      }

      .level-1 {
        margin-left: 5px;
        font-size: 95%;
      }

      .level-2 {
        margin-left: 10px;
        font-size: 90%;
      }

      .level-3 {
        margin-left: 15px;
        font-size: 85%;
      }

      .feature-name {
        display: inline-block;
      }

      .clickable {
        text-decoration: none;
        cursor: pointer;
        color: var(--color-link-primary);
      }

      .clickable.secondary {
        color: var(--color-link-secondary);
      }

      .clickable:hover {
        text-decoration: underline;
        color: var(--color-link-primary-hover);
      }

      .feature:hover .showonhover {
        visibility: visible;
      }

      .showonhover {
        visibility: hidden;
      }

      .aliases {
        color: #bbb;
        font-size: 80%;
        display: inline;
        margin-left: 5px;
      }

      temba-label {
        margin-right: 3px;
        margin-bottom: 3px;
        vertical-align: top;
      }

      .selected {
        display: flex;
        flex-direction: column;
        padding: 15px;
        padding-bottom: 40px;
      }

      .selected .name {
        font-size: 18px;
        padding: 5px;
      }

      .selected .help {
        padding: 5px 2px;
        font-size: 11px;
        color: var(--color-secondary-light);
      }

      #right-column {
        vertical-align: top;
        margin-left: 20px;
        display: inline-block;
      }

      leaflet-map {
        height: 600px;
        width: 800px;
        border: 0px solid #999;
        border-radius: var(--curvature);
      }

      .edit {
        display: inline-block;
        margin-right: 0px;
      }
    `;
  }

  @property({ type: Array, attribute: false })
  path: FeatureProperties[] = [];

  @property()
  endpoint: string;

  @property()
  osmId: string;

  @property({ type: Object })
  hovered: FeatureProperties;

  @property({ type: Object })
  editFeature: FeatureProperties;

  @property({ type: String, attribute: false })
  editFeatureAliases: string;

  public constructor() {
    super();
  }

  public updated(changedProperties: Map<string, any>) {
    if (changedProperties.has('osmId')) {
      // going up the tree doesn't require a fetch
      const newPath = [];
      for (const feature of this.path) {
        newPath.push(feature);
        if (feature.osm_id === this.osmId) {
          this.path = [...newPath];
          this.hideAliasDialog();
          return;
        }
      }

      this.fetchFeature();
    }
  }

  private fetchFeature() {
    getUrl(this.getEndpoint() + 'boundaries/' + this.osmId + '/').then(
      (response: WebResponse) => {
        this.path = response.json as FeatureProperties[];
        this.hideAliasDialog();
      }
    );
  }

  private handleMapClicked(feature: FeatureProperties): void {
    this.hovered = null;
    if (!feature || feature.osm_id !== this.osmId) {
      this.osmId = feature.osm_id;
    }
  }

  private handlePlaceClicked(feature: FeatureProperties) {
    this.osmId = feature.osm_id;
  }

  private handleSearchSelection(evt: CustomEvent) {
    const selection = evt.detail.selected as FeatureProperties;
    this.showAliasDialog(selection);
    const select = this.shadowRoot.querySelector('temba-select') as Select<any>;
    select.clear();
  }

  private isMatch(option: any, query: string) {
    return `${option.name} ${option.aliases}`.toLowerCase().indexOf(query) > -1;
  }

  private renderFeature(
    feature: FeatureProperties,
    remainingPath: FeatureProperties[]
  ): TemplateResult {
    const selectedFeature = this.path[this.path.length - 1];
    const clickable =
      (feature.has_children || feature.level === 0) &&
      feature !== selectedFeature;
    const renderedFeature = html`
      <div class="feature">
        <div
          @mouseover=${() => {
            if (feature.level > 0) {
              this.hovered = feature;
            }
          }}
          @mouseout=${() => {
            this.hovered = null;
          }}
          class="level-${feature.level}"
        >
          <div
            class="feature-name ${clickable ? 'clickable' : ''}"
            @click=${() => {
              if (clickable) {
                this.handlePlaceClicked(feature);
              }
            }}
          >
            ${feature.name}
          </div>

          <div class="aliases">
            ${feature.aliases.split('\n').map((alias: string) =>
              alias.trim().length > 0
                ? html`
                    <temba-label
                      class="alias"
                      @click=${() => {
                        this.showAliasDialog(feature);
                      }}
                      light
                      clickable
                      >${alias}</temba-label
                    >
                  `
                : null
            )}
            ${feature.level > 0
              ? html`
                  <div
                    class="edit clickable showonhover"
                    @click=${(evt: MouseEvent) => {
                      this.showAliasDialog(feature);
                      evt.preventDefault();
                      evt.stopPropagation();
                    }}
                  >
                    <temba-icon name="${Icon.updated}" />
                  </div>
                `
              : ''}
          </div>
        </div>
      </div>
    `;

    const renderedChildren = (feature.children || []).map(
      (child: FeatureProperties) => {
        if (
          remainingPath.length > 0 &&
          remainingPath[0].osm_id === child.osm_id
        ) {
          return this.renderFeature(remainingPath[0], remainingPath.slice(1));
        }

        if (
          remainingPath.length === 0 ||
          remainingPath[0].children.length === 0
        ) {
          return this.renderFeature(child, remainingPath);
        }

        return null;
      }
    );

    return html` ${renderedFeature} ${renderedChildren} `;
  }

  public showAliasDialog(feature: FeatureProperties) {
    this.editFeatureAliases = feature.aliases;
    this.editFeature = feature;
    const aliasDialog = this.shadowRoot.getElementById('alias-dialog');
    if (aliasDialog) {
      aliasDialog.setAttribute('open', '');
    }
  }

  public hideAliasDialog() {
    const aliasDialog = this.shadowRoot.getElementById('alias-dialog');
    this.editFeature = null;
    this.editFeatureAliases = null;
    if (aliasDialog) {
      aliasDialog.removeAttribute('open');
    }

    this.requestUpdate();
  }

  private getEndpoint(): string {
    return this.endpoint + (!this.endpoint.endsWith('/') ? '/' : '');
  }

  private handleDialogClick(evt: CustomEvent) {
    const button = evt.detail.button;
    if (button.name === 'Save') {
      const textarea = this.shadowRoot.getElementById(
        this.editFeature.osm_id
      ) as TextInput;
      const aliases = textarea.inputElement.value;
      const payload = { osm_id: this.editFeature.osm_id, aliases };
      postJSON(
        this.getEndpoint() + 'boundaries/' + this.editFeature.osm_id + '/',
        payload
      ).then(() => {
        this.fetchFeature();
      });
    }

    if (button.name === 'Cancel') {
      this.hideAliasDialog();
    }
  }

  private getOptions(response: WebResponse) {
    return response.json.filter((option: any) => option.level > 0);
  }

  private getOptionsComplete(newestOptions: FeatureProperties[]) {
    return newestOptions.length === 0;
  }

  private renderOptionDetail(option: FeatureProperties): TemplateResult {
    const labelStyles = {
      marginTop: '3px',
      marginRight: '3px'
    };

    const aliasList = option.aliases.split('\n');
    const aliases = aliasList.map((alias: string) =>
      alias.trim().length > 0
        ? html`
            <temba-label style=${styleMap(labelStyles)} class="alias" dark
              >${alias}</temba-label
            >
          `
        : null
    );
    return html`
      <div class="path">${option.path.replace(/>/gi, '‣')}</div>
      <div class="aliases">${aliases}</div>
    `;
  }

  public render(): TemplateResult {
    if (this.path.length === 0) {
      return html``;
    }

    // if we are a leaf, have our map show the level above
    const selectedFeature = this.path[this.path.length - 1];
    const mapFeature =
      selectedFeature.children.length === 0
        ? this.path[this.path.length - 2]
        : selectedFeature;

    const editFeatureId = this.editFeature ? this.editFeature.osm_id : null;
    const editFeatureName = this.editFeature ? this.editFeature.name : null;

    return html`
      <div id="left-column">
        <div class="search">
          <temba-select
            placeholder="Search"
            endpoint="${this.getEndpoint()}boundaries/${this.path[0].osm_id}/?"
            .renderOptionDetail=${this.renderOptionDetail}
            .getOptions=${this.getOptions}
            .isComplete=${this.getOptionsComplete}
            .isMatch=${this.isMatch}
            @temba-selection=${this.handleSearchSelection.bind(this)}
            queryParam="q"
            searchable
          ></temba-select>
        </div>
        <div class="feature-tree">
          ${this.renderFeature(this.path[0], this.path.slice(1))}
        </div>
      </div>

      <div id="right-column">
        <leaflet-map
          endpoint=${this.getEndpoint()}
          .feature=${mapFeature}
          .osmId=${mapFeature.osm_id}
          .hovered=${this.hovered}
          .onFeatureClicked=${this.handleMapClicked.bind(this)}
        >
        </leaflet-map>
      </div>

      <temba-dialog
        id="alias-dialog"
        header="Aliases for ${editFeatureName}"
        primaryButtonName="Save"
        @temba-button-clicked=${this.handleDialogClick.bind(this)}
      >
        <div class="selected">
          <temba-textinput
            .helpText="Enter other aliases for ${editFeatureName}, one per line"
            name="aliases"
            id=${editFeatureId}
            .value=${this.editFeatureAliases}
            textarea
          ></temba-textinput>
        </div>
      </temba-dialog>
    `;
  }
}
