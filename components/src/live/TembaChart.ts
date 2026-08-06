import { RapidElement } from '../RapidElement';
import { property, state } from 'lit/decorators.js';
import {
  css,
  html,
  PropertyValueMap,
  PropertyValues,
  TemplateResult
} from 'lit';

import { Select, SelectOption } from '../form/select/Select';
import { darkenColor, getClasses } from '../utils';
import { getStore } from '../store/Store';

// eslint-disable-next-line import/no-named-as-default
import Chart, { ChartType } from 'chart.js/auto';
import 'chartjs-adapter-luxon';
import ChartDataLabels from 'chartjs-plugin-datalabels';

Chart.register(ChartDataLabels);

const DEFAULT_PALETTE: keyof typeof COLOR_PALETTES = 'qualitative-set1';
const COLOR_PALETTES = {
  // Qualitative (categorical, no order)
  'qualitative-set1': [
    '#5ea3db',
    '#c186e3',
    '#66c2a5',
    '#fc8d62',
    '#a6d854',
    '#ffd92f',
    '#e5c494',
    '#b3b3b3'
  ],
  'qualitative-set2': [
    '#377eb8',
    '#984ea3',
    '#4daf4a',
    '#ff7f00',
    '#e41a1c',
    '#a65628',
    '#f781bf',
    '#ffff33'
  ],
  'qualitative-set3': [
    '#1b9e77',
    '#d95f02',
    '#7570b3',
    '#e7298a',
    '#66a61e',
    '#e6ab02',
    '#a6761d'
  ],
  'qualitative-paired': [
    '#1f78b4',
    '#a6cee3',
    '#6a3d9a',
    '#cab2d6',
    '#33a02c',
    '#b2df8a',
    '#e31a1c',
    '#fb9a99',
    '#ff7f00',
    '#fdbf6f'
  ],
  'qualitative-accent': [
    '#7fc97f',
    '#beaed4',
    '#fdc086',
    '#ffff99',
    '#386cb0',
    '#f0027f',
    '#bf5b17',
    '#666666'
  ],
  'qualitative-pastel1': [
    '#fbb4ae',
    '#b3cde3',
    '#ccebc5',
    '#decbe4',
    '#fed9a6',
    '#ffffcc',
    '#e5d8bd',
    '#fddaec'
  ],
  'qualitative-pastel2': [
    '#b3e2cd',
    '#fdcdac',
    '#cbd5e8',
    '#f4cae4',
    '#e6f5c9',
    '#fff2ae',
    '#f1e2cc'
  ],
  // Diverging (for data with midpoint like 0)
  'diverging-prgn': [
    '#40004b',
    '#762a83',
    '#9970ab',
    '#c2a5cf',
    '#e7d4e8',
    '#f7f7f7',
    '#d9f0d3',
    '#a6dba0',
    '#5aae61',
    '#1b7837',
    '#00441b'
  ],
  'diverging-spectral': [
    '#9e0142',
    '#d53e4f',
    '#f46d43',
    '#fdae61',
    '#fee08b',
    '#ffffbf',
    '#e6f598',
    '#abdda4',
    '#66c2a5',
    '#3288bd',
    '#5e4fa2'
  ],
  'diverging-piyg': [
    '#8e0152',
    '#c51b7d',
    '#de77ae',
    '#f1b6da',
    '#fde0ef',
    '#f7f7f7',
    '#e6f5d0',
    '#b8e186',
    '#7fbc41',
    '#4d9221',
    '#276419'
  ],
  'diverging-rdylgn': [
    '#a50026',
    '#d73027',
    '#f46d43',
    '#fdae61',
    '#fee08b',
    '#ffffbf',
    '#d9ef8b',
    '#a6d96a',
    '#66bd63',
    '#1a9850',
    '#006837'
  ],
  'diverging-brbg': [
    '#543005',
    '#8c510a',
    '#bf812d',
    '#dfc27d',
    '#f6e8c3',
    '#f5f5f5',
    '#c7eae5',
    '#80cdc1',
    '#35978f',
    '#01665e',
    '#003c30'
  ],

  // Sequential (for continuous or ordered data)
  'sequential-blues': [
    '#f7fbff',
    '#deebf7',
    '#c6dbef',
    '#9ecae1',
    '#6baed6',
    '#4292c6',
    '#2171b5',
    '#08519c',
    '#08306b'
  ],
  'sequential-greens': [
    '#f7fcf5',
    '#e5f5e0',
    '#c7e9c0',
    '#a1d99b',
    '#74c476',
    '#41ab5d',
    '#238b45',
    '#006d2c',
    '#00441b'
  ],
  'sequential-oranges': [
    '#fff5eb',
    '#fee6ce',
    '#fdd0a2',
    '#fdae6b',
    '#fd8d3c',
    '#f16913',
    '#d94801',
    '#a63603',
    '#7f2704'
  ],
  'sequential-purples': [
    '#fcfbfd',
    '#efedf5',
    '#dadaeb',
    '#bcbddc',
    '#9e9ac8',
    '#807dba',
    '#6a51a3',
    '#54278f',
    '#3f007d'
  ],
  'sequential-reds': [
    '#fff5f0',
    '#fee0d2',
    '#fcbba1',
    '#fc9272',
    '#fb6a4a',
    '#ef3b2c',
    '#cb181d',
    '#a50f15',
    '#67000d'
  ],
  'sequential-ylgnbu': [
    '#ffffd9',
    '#edf8b1',
    '#c7e9b4',
    '#7fcdbb',
    '#41b6c4',
    '#1d91c0',
    '#225ea8',
    '#253494',
    '#081d58'
  ]
};

const otherBackgroundColor = 'rgba(212, 212, 212, 0.5)';

/**
 * Formats a duration in seconds to a human-readable string showing the two largest units.
 * Examples: 68787 -> "19h 6m", 958000 -> "11d 2h", 3661 -> "1h 1m"
 */
export function formatDurationFromSeconds(seconds: number): string {
  if (seconds === 0) {
    return '0s';
  }

  const totalDays = Math.floor(seconds / 86400);
  const remainingAfterDays = seconds % 86400;
  const remainingHours = Math.floor(remainingAfterDays / 3600);
  const remainingAfterHours = remainingAfterDays % 3600;
  const remainingMinutes = Math.floor(remainingAfterHours / 60);
  const remainingSeconds = remainingAfterHours % 60;

  const units = [];

  if (totalDays > 0) {
    units.push(`${totalDays}d`);
  }
  if (remainingHours > 0) {
    units.push(`${remainingHours}h`);
  }
  if (remainingMinutes > 0 && units.length < 2) {
    units.push(`${remainingMinutes}m`);
  }
  if (remainingSeconds > 0 && units.length < 2) {
    units.push(`${remainingSeconds}s`);
  }

  // Return the first two most significant units
  return units.slice(0, 2).join(' ');
}

export interface RapidChartData {
  labels: string[];
  datasets: { label: string; data: number[] }[];
}

export class TembaChart extends RapidElement {
  @property({ type: String })
  chartType: ChartType = 'bar';

  @property({ type: Boolean })
  horizontal: boolean = false;

  @property({ type: String })
  url: string;

  @property({ type: String })
  start: string;

  @property({ type: String })
  end: string;

  @property({ type: String })
  header: string = '';

  @property({ type: Boolean })
  other: boolean = false;

  @property({ type: Object })
  data: RapidChartData;

  @state()
  datasets: { label: string; data: number[] }[] = [];

  @property({ type: Number })
  maxSplits: number = 2;

  @property({ type: String, attribute: 'splits' })
  splitNames: string;

  @property({ type: String })
  xType: 'category' | 'time' = 'category';

  @property({ type: Number })
  xMaxTicks: number = 10;

  @property({ type: String })
  yType: 'count' | 'duration' = 'count';

  @property({ type: String })
  xFormat: 'MMM yy' | 'MMM yyyy' | 'MMM dd' | 'DD' | 'EEE' | 'auto' = 'auto';

  @property({ type: Number })
  maxChartHeight: number = 250;

  @property({ type: Boolean })
  hideOther: boolean = false;

  @state()
  splits: string[] = [];

  @property({ type: String })
  dataname = 'Counts';

  @property({ type: Boolean })
  single: boolean = false;

  @property({ type: Boolean })
  legend: boolean = false;

  @property({ type: Boolean })
  config: boolean = false;

  @property({ type: Boolean })
  showAll: boolean = false;

  @property({ type: Boolean })
  requireWindow: boolean = false;

  @property({ type: Number })
  colorIndex: number = 0;

  @state()
  showConfig: boolean = false;

  @property({ type: String })
  palette: keyof typeof COLOR_PALETTES;

  @property({ type: Number })
  opacity: number = 1;

  @property({ type: Number })
  seriesBorderRadius: number = 2;

  @property({ type: Number })
  seriesBorderWidth: number = 1;

  @property({ type: Boolean, attribute: 'percent' })
  showPercent: boolean = false;

  // head-room for labels when percentages are visible
  private getInflatedMax(): number | undefined {
    if (!this.showPercent || !this.data) return undefined;

    // total stacked value for each x-index
    const totals: number[] = Array(this.data.labels.length).fill(0);
    for (const ds of this.datasets) {
      ds.data.forEach((v, i) => (totals[i] += v));
    }
    const maxStack = Math.max(...totals);
    return maxStack > 0 ? maxStack * 1.15 : undefined;
  }

  chart: Chart;
  shadowRootDiv: HTMLDivElement;
  canvas: HTMLCanvasElement;
  ctx: CanvasRenderingContext2D;

  static get styles() {
    return css`
      .chart-title {
        font-size: 1.2em;
        font-weight: 600;
        text-align: center;
      }

      temba-select {
        display: block;
      }

      .config-toggle {
        margin-top: -2.5em;
        margin-right: -0.5em;
        color: #bbb;
        display: none;
      }

      .config-toggle:hover {
        color: #666;
      }

      .config-toggle.show {
        color: #666;
        display: block;
      }

      .config {
        max-height: 0px;
        padding: 0em 1em;
        border-radius: var(--curvature);
        border: 1px solid transparent;
        background: transparent;
        overflow: hidden;
        transition: all 0.2s ease-in-out;
      }

      .config.show {
        padding: 2em 1em 1.5em 1em;
        max-height: 50px;
      }
    `;
  }

  constructor() {
    super();
  }

  protected firstUpdated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.firstUpdated(changes);
    const wrapper = this.shadowRoot.querySelector('#canvas-wrapper');
    this.canvas = document.createElement('canvas');
    this.canvas.setAttribute('height', '300px');
    wrapper.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');
  }

  public willUpdate(changed: PropertyValues): void {
    super.willUpdate(changed);

    if (changed.has('splitNames')) {
      this.splits = this.splitNames.split(',').map((s) => s.trim());
    }

    if (changed.has('data') || changed.has('splits')) {
      this.calculateSplits();
    }
  }

  protected updated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(changes);

    if (changes.has('datasets')) {
      this.updateChart();
    }

    if (changes.has('horizontal')) {
      this.updateChart();
    }

    if (changes.has('url') || changes.has('start') || changes.has('end')) {
      if (this.url && (!this.requireWindow || (this.start && this.end))) {
        const store = getStore();
        let fullUrl = this.url;

        // Add query parameters for date range if provided
        const params = new URLSearchParams();
        if (this.start) {
          params.append('since', this.start);
        }
        if (this.end) {
          params.append('until', this.end);
        }

        if (params.toString()) {
          const separator = this.url.includes('?') ? '&' : '?';
          fullUrl = `${this.url}${separator}${params.toString()}`;
        }

        store.getUrl(fullUrl, { skipCache: true }).then((response) => {
          this.data = response.json.data;
        });
      }
    }

    if (changes.has('chartType')) {
      if (this.chartType === 'line') {
        this.seriesBorderWidth = Math.max(1, this.seriesBorderWidth);
      }
    }

    if (changes.has('showPercent') && this.chart) {
      // in horizontal charts, the value axis is X, in vertical charts it's Y
      const valueScale = this.horizontal
        ? (this.chart.options.scales as any).x
        : (this.chart.options.scales as any).y;
      valueScale.ticks.display = !this.showPercent;
      valueScale.grid.display = !this.showPercent;
      valueScale.border.display = !this.showPercent;
      valueScale.max = this.showPercent ? this.getInflatedMax() : undefined;
      this.chart.update();
    }
  }

  /**
   * Returns a tuple: [backgroundColors[], borderColors[]].
   * Border colors are darkened versions of the base palette (before transparency).
   * Background colors have transparency applied.
   */
  get colors(): [string[], string[]] {
    const baseColors =
      COLOR_PALETTES[this.palette] || COLOR_PALETTES[DEFAULT_PALETTE];
    // clamp transparency between 0 and 1
    const alpha = Math.max(0, Math.min(1, this.opacity));
    // borders darken base color, no transparency
    const borderColors = baseColors.map((color) => darkenColor(color, 0.25));
    // backgrounds apply transparency to base color
    const backgroundColors = baseColors.map((color) => {
      // if already rgba, just replace the alpha
      if (color.startsWith('rgba')) {
        return color.replace(
          /rgba\(([^,]+),([^,]+),([^,]+),([^)]+)\)/,
          (_m, r, g, b) => {
            return `rgba(${r},${g},${b},${alpha})`;
          }
        );
      }
      // if already rgb, convert to rgba
      if (color.startsWith('rgb(')) {
        return color.replace(
          /rgb\(([^,]+),([^,]+),([^,]+)\)/,
          (_m, r, g, b) => {
            return `rgba(${r},${g},${b},${alpha})`;
          }
        );
      }
      // if hex, convert to rgba
      if (color.startsWith('#')) {
        let hex = color.replace('#', '');
        if (hex.length === 3) {
          hex = hex
            .split('')
            .map((c) => c + c)
            .join('');
        }
        const num = parseInt(hex, 16);
        const r = (num >> 16) & 255;
        const g = (num >> 8) & 255;
        const b = num & 255;
        return `rgba(${r},${g},${b},${alpha})`;
      }
      // fallback
      return color;
    });
    return [backgroundColors, borderColors];
  }

  private handleResize() {
    if (this.chart) {
      // recalculate canvas size based on parent container
      const wrapper = this.shadowRoot.querySelector('#canvas-wrapper');
      if (wrapper) {
        if (wrapper.clientHeight > this.maxChartHeight) {
          this.canvas.style.height = `${this.maxChartHeight}px`;
          this.chart.resize();
        }
      }
    }
  }

  private calculateSplits() {
    if (this.data) {
      const datasets = [];
      const sums = [];
      const [backgroundColors, borderColors] = this.colors;
      for (const dataset of this.data.datasets) {
        if (
          !this.showAll &&
          this.splits.find((s) => s === dataset.label) === undefined
        ) {
          for (let i = 0; i < dataset.data.length; i++) {
            if (sums[i] === undefined) {
              sums[i] = dataset.data[i];
            } else {
              sums[i] += dataset.data[i];
            }
          }
        } else {
          const colorIdx =
            (datasets.length + this.colorIndex) % backgroundColors.length;
          const bgColor = backgroundColors[colorIdx];
          const borderColor = borderColors[colorIdx];
          datasets.push({
            ...dataset,
            backgroundColor: bgColor,
            borderColor,
            borderWidth: this.seriesBorderWidth,
            borderRadius: this.seriesBorderRadius
          });
        }
      }

      if (datasets.length === 0) {
        const idx = this.colorIndex % backgroundColors.length;
        datasets.push({
          label: this.single ? this.dataname : `All ${this.dataname}`,
          data: sums,
          backgroundColor: backgroundColors[idx],
          borderColor: borderColors[idx],
          borderWidth: this.seriesBorderWidth,
          borderRadius: this.seriesBorderRadius
        });
      } else {
        if (!this.hideOther && !this.showAll) {
          datasets.push({
            label: 'Other',
            data: sums,
            backgroundColor: otherBackgroundColor,
            borderColor: darkenColor(otherBackgroundColor, 0.05),
            borderWidth: 1,
            borderRadius: this.seriesBorderRadius
          });
        }
      }
      this.datasets = datasets;
    }
  }

  public updateChart(): void {
    if (this.datasets?.length > 0) {
      const grandTotal =
        this.datasets.reduce(
          (sum: number, ds: any) =>
            sum +
            (ds.data as number[]).reduce(
              (dsSum: number, v: number) => dsSum + (v ?? 0),
              0
            ),
          0
        ) || undefined;

      const percentFormatter = (value: number): string => {
        const pct = grandTotal ? (value / grandTotal) * 100 : 0;
        if (pct === 0) {
          return '';
        }
        return `${Math.round(pct)}%`;
      };

      if (this.chart) {
        this.chart.data.labels = this.data.labels;
        this.chart.data.datasets = this.datasets;

        // update y-axis max dynamically
        if (this.showPercent) {
          (this.chart.options.scales as any).y.max = this.getInflatedMax();
        }

        const datalabels = this.chart.options.plugins.datalabels || {};
        datalabels.display = this.showPercent;
        if (this.showPercent) {
          datalabels.formatter = percentFormatter;
        } else {
          delete datalabels.formatter;
        }
        this.chart.options.plugins.datalabels = datalabels;

        // the scale config could have changed, so we need to update it
        if (this.horizontal) {
          this.chart.options.scales.x = this.getValueAxisConfig();
          this.chart.options.scales.y = this.getCategoryAxisConfig() as any;
        } else {
          this.chart.options.scales.x = this.getCategoryAxisConfig() as any;
          this.chart.options.scales.y = this.getValueAxisConfig();
        }

        this.chart.update();
      } else {
        const chartData = {
          type: this.chartType,
          data: {
            labels: this.data.labels,
            datasets: this.datasets
          },
          options: {
            ...(this.horizontal && { indexAxis: 'y' }),
            maxBarThickness: 80,
            plugins: {
              legend: { display: this.legend },
              tooltip: {
                callbacks: {
                  label: (context: any) => {
                    const label = context.dataset.label || '';
                    // in horizontal charts, the value is on parsed.x, in vertical charts on parsed.y
                    const value = this.horizontal
                      ? context.parsed.x
                      : context.parsed.y;
                    if (this.yType === 'duration') {
                      return `${label}: ${formatDurationFromSeconds(value)}`;
                    }
                    return `${label}: ${value}`;
                  }
                }
              },
              datalabels: {
                display: this.showPercent,
                anchor: 'end',
                align: 'end',
                offset: -3,
                clamp: true,
                ...(this.showPercent && { formatter: percentFormatter }),
                color: '#666',
                font: { weight: '600' }
              }
            },
            responsive: true,
            aspectRatio: 2,
            onResize: this.handleResize.bind(this),
            maintainAspectRatio: false,
            animation: false,
            animations: {
              x: {
                duration: 0
              },
              y: {
                duration: 0
              }
            },
            scales: this.horizontal
              ? {
                  x: this.getValueAxisConfig(),
                  y: this.getCategoryAxisConfig()
                }
              : {
                  y: this.getValueAxisConfig(),
                  x: this.getCategoryAxisConfig()
                }
          }
        };

        this.chart = new Chart(this.ctx, chartData as any);
      }
    }
  }

  private handleSplitsChanged(e: Event) {
    const select = e.target as Select<SelectOption>;
    this.splits = select.values.map((option) => {
      return option.value;
    });
  }

  private handleToggleConfig() {
    this.showConfig = !this.showConfig;
    if (!this.showConfig) {
      this.splits = [];
    }
  }

  private getValueAxisConfig() {
    return {
      min: 0,
      ...(this.showPercent && { max: this.getInflatedMax() }),
      stacked: true,
      grid: {
        color: 'rgba(0,0,0,0.04)',
        display: !this.showPercent,
        drawBorder: !this.showPercent
      },
      border: {
        display: !this.showPercent
      },
      ticks: {
        display: !this.showPercent,
        ...(this.yType === 'duration' &&
          !this.showPercent && {
            callback: (value: any) => formatDurationFromSeconds(value)
          })
      }
    };
  }

  private getCategoryAxisConfig() {
    let format = this.xFormat;
    if (this.xType === 'time' && this.xFormat === 'auto') {
      const firstDate = this.data.labels[0];
      const lastDate = this.data.labels[this.data.labels.length - 1];

      const first = Date.parse(firstDate);
      const last = Date.parse(lastDate);

      const dayDiff = Math.ceil((last - first) / (1000 * 60 * 60 * 24));
      format = 'MMM dd';
      if (dayDiff > 365) {
        format = 'MMM yyyy';
      }
    }

    return {
      max: this.xType === 'time' ? this.end : this.xMaxTicks,
      min: this.xType === 'time' ? this.start : 0,
      type: this.xType,
      grid: { display: false },
      stacked: true,
      ticks: {
        maxTicksLimit: this.xMaxTicks
      },
      ...(this.xType === 'time' && {
        time: {
          unit: 'day',
          tooltipFormat: 'DDD',
          displayFormats: { day: format }
        }
      })
    };
  }

  protected render(): TemplateResult {
    return html`<div>
      ${this.header
        ? html`<div class="chart-title">${this.header}</div>`
        : null}
      <div id="canvas-wrapper"></div>
      ${this.config && this.data
        ? html`
            <div
              class="${getClasses({
                'config-toggle': true,
                show: this.showConfig && this.data?.datasets?.length > 1
              })}"
              style="display: flex; flex-direction: row; align-items: center; justify-content: space-between;"
            >
              <div></div>
              <div>
                <temba-icon
                  animateChange="spin"
                  name="${this.showConfig ? 'close' : 'settings'}"
                  clickable
                  size="1.5"
                  @click=${this.handleToggleConfig}
                ></temba-icon>
              </div>
            </div>
          `
        : null}

      <div class=${getClasses({ config: true, show: this.showConfig })}>
        <temba-select
          multi
          placeholder="Select ${this.dataname}"
          options=${JSON.stringify(
            this.data?.datasets.map((dataset) => ({
              name: dataset.label,
              value: dataset.label
            }))
          )}
          .values=${this.splits.map((s) => ({ name: s, value: s }))}
          @change=${this.handleSplitsChanged}
        >
        </temba-select>
        <div></div>
      </div>
    </div>`;
  }
}
