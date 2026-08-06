import { expect } from '@open-wc/testing';
import {
  RapidChartData,
  TembaChart,
  formatDurationFromSeconds
} from '../src/live/TembaChart';
import { getComponent } from './utils.test';

const sampleData: RapidChartData = {
  labels: ['January', 'February', 'March', 'April', 'May', 'June', 'July'],
  datasets: [
    {
      label: 'General',
      data: [65, 59, 80, 81, 56, 55, 40]
    },
    {
      label: 'Support',
      data: [28, 48, 40, 19, 86, 27, 90]
    },
    {
      label: 'VIPs',
      data: [58, 28, 10, 1, 0, 19, 20]
    }
  ]
};

const TAG = 'temba-chart';
const getChart = async (attrs: any = {}) => {
  const picker = (await getComponent(TAG, attrs, '', 400)) as TembaChart;
  return picker;
};

describe('temba-chart', () => {
  it('calculates others', async () => {
    const chart: TembaChart = await getChart();

    chart.data = sampleData;
    await chart.updateComplete;

    // if we haven't set any splits, everything should be summed as "All"
    expect(chart.datasets[0].data).to.deep.equal([
      151, 135, 130, 101, 142, 101, 150
    ]);

    // add a split
    chart.splits = ['General'];
    await chart.updateComplete;

    // now we should get an "Others" dataset
    expect(chart.datasets[1].data).to.deep.equal([86, 76, 50, 20, 86, 46, 110]);

    // add another split
    chart.splits = ['General', 'Support'];
    await chart.updateComplete;

    // now others should be everything but general and support
    expect(chart.datasets[2].data).to.deep.equal([58, 28, 10, 1, 0, 19, 20]);
  });

  it('supports duration formatting', async () => {
    const chart: TembaChart = await getChart();

    // Test that formatDuration property exists and defaults to false
    expect(chart.yType).to.equal('count');

    // Test that we can set formatDuration to true
    chart.yType = 'duration';
    expect(chart.yType).to.equal('duration');
  });

  it('formats duration values correctly', async () => {
    const chart: TembaChart = await getChart();

    // Access the formatDurationFromSeconds function through the chart's module
    // We need to test the duration formatting logic
    const durationData: RapidChartData = {
      labels: ['Day 1', 'Day 2', 'Day 3'],
      datasets: [
        {
          label: 'Process Time',
          data: [68787, 958000, 3661] // seconds that should be formatted as durations
        }
      ]
    };

    chart.yType = 'duration';
    chart.data = durationData;
    await chart.updateComplete;

    // Wait for the chart to be created after data is set
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Test that the chart was created and has the duration formatting enabled
    expect(chart.yType).to.equal('duration');
    expect(chart.chart).to.exist;

    // Test that the chart configuration includes the duration formatting
    const chartConfig = chart.chart.options;
    expect(chartConfig.scales.y.ticks).to.exist;
    expect(chartConfig.scales.y.ticks.callback).to.be.a('function');

    // Test the tick callback function formatting
    const tickCallback = chartConfig.scales.y.ticks.callback;
    expect(tickCallback.call({}, 68787, 0, [])).to.equal('19h 6m');
    expect(tickCallback.call({}, 958000, 1, [])).to.equal('11d 2h');
    expect(tickCallback.call({}, 3661, 2, [])).to.equal('1h 1m');
    expect(tickCallback.call({}, 120, 3, [])).to.equal('2m');
    expect(tickCallback.call({}, 0, 4, [])).to.equal('0s');

    // Test tooltip formatting
    expect(chartConfig.plugins.tooltip.callbacks.label).to.be.a('function');
    const tooltipCallback = chartConfig.plugins.tooltip.callbacks.label;

    const mockContext = {
      dataset: { label: 'Process Time' },
      parsed: { y: 68787 }
    };

    expect(tooltipCallback.call({}, mockContext)).to.equal(
      'Process Time: 19h 6m'
    );
  });

  it('formats various duration edge cases correctly', async () => {
    const chart: TembaChart = await getChart();
    chart.yType = 'duration';
    chart.data = sampleData;
    await chart.updateComplete;

    // Wait for the chart to be created after data is set
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(chart.chart).to.exist;
    const tickCallback = chart.chart.options.scales.y.ticks.callback;

    // Test edge cases for duration formatting
    expect(tickCallback.call({}, 0, 0, [])).to.equal('0s');
    expect(tickCallback.call({}, 1, 1, [])).to.equal('1s');
    expect(tickCallback.call({}, 59, 2, [])).to.equal('59s');
    expect(tickCallback.call({}, 60, 3, [])).to.equal('1m');
    expect(tickCallback.call({}, 61, 4, [])).to.equal('1m 1s');
    expect(tickCallback.call({}, 3600, 5, [])).to.equal('1h');
    expect(tickCallback.call({}, 3661, 6, [])).to.equal('1h 1m');
    expect(tickCallback.call({}, 86400, 7, [])).to.equal('1d');
    expect(tickCallback.call({}, 90061, 8, [])).to.equal('1d 1h'); // 1 day, 1 hour, 1 minute, 1 second - should show only first two units
    expect(tickCallback.call({}, 604800, 9, [])).to.equal('7d'); // 1 week in seconds
    expect(tickCallback.call({}, 1209600, 10, [])).to.equal('14d'); // 2 weeks in seconds
  });

  it('applies xFormat when xType is time', async () => {
    const chart: TembaChart = await getChart({
      xType: 'time',
      xFormat: 'DD'
    });

    chart.data = sampleData;
    await chart.updateComplete;

    // Wait for the chart to be created after data is set
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(chart.chart).to.exist;
    expect(chart.chart.options.scales.x.type).to.equal('time');
    expect(
      (chart.chart.options.scales.x as any).time.displayFormats.day
    ).to.equal('DD');
  });

  it('does not include time config when xType is category', async () => {
    const chart: TembaChart = await getChart({
      xType: 'category',
      xFormat: 'DD'
    });

    chart.data = sampleData;
    await chart.updateComplete;

    // Wait for the chart to be created after data is set
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(chart.chart).to.exist;
    expect(chart.chart.options.scales.x.type).to.equal('category');
    expect((chart.chart.options.scales.x as any).time).to.be.undefined;
  });

  it('configures scales correctly for horizontal charts', async () => {
    const chart: TembaChart = await getChart();

    // Test vertical chart (default)
    chart.data = sampleData;
    await chart.updateComplete;
    await new Promise((resolve) => setTimeout(resolve, 100));

    // In vertical charts: x-axis should be for categories, y-axis for values
    expect((chart.chart.options.scales as any).x.type).to.equal('category');
    expect((chart.chart.options.scales as any).y.min).to.equal(0);
    expect((chart.chart.options.scales as any).y.stacked).to.equal(true);

    // Test horizontal chart
    chart.horizontal = true;
    await chart.updateComplete;
    await new Promise((resolve) => setTimeout(resolve, 100));

    // In horizontal charts: x-axis should be for values, y-axis for categories
    expect((chart.chart.options.scales as any).x.min).to.equal(0);
    expect((chart.chart.options.scales as any).x.stacked).to.equal(true);
    expect((chart.chart.options.scales as any).y.type).to.equal('category');
  });
});

describe('formatDurationFromSeconds', () => {
  it('formats zero correctly', () => {
    expect(formatDurationFromSeconds(0)).to.equal('0s');
  });

  it('formats seconds only', () => {
    expect(formatDurationFromSeconds(1)).to.equal('1s');
    expect(formatDurationFromSeconds(30)).to.equal('30s');
    expect(formatDurationFromSeconds(59)).to.equal('59s');
  });

  it('formats minutes and seconds', () => {
    expect(formatDurationFromSeconds(60)).to.equal('1m');
    expect(formatDurationFromSeconds(61)).to.equal('1m 1s');
    expect(formatDurationFromSeconds(90)).to.equal('1m 30s');
    expect(formatDurationFromSeconds(120)).to.equal('2m');
    expect(formatDurationFromSeconds(3599)).to.equal('59m 59s');
  });

  it('formats hours and minutes', () => {
    expect(formatDurationFromSeconds(3600)).to.equal('1h');
    expect(formatDurationFromSeconds(3661)).to.equal('1h 1m');
    expect(formatDurationFromSeconds(7200)).to.equal('2h');
    expect(formatDurationFromSeconds(68787)).to.equal('19h 6m');
  });

  it('formats days and hours', () => {
    expect(formatDurationFromSeconds(86400)).to.equal('1d');
    expect(formatDurationFromSeconds(90000)).to.equal('1d 1h');
    expect(formatDurationFromSeconds(958000)).to.equal('11d 2h');
  });

  it('shows only two most significant units', () => {
    // 1 day, 1 hour, 1 minute, 1 second - should show only "1d 1h"
    expect(formatDurationFromSeconds(90061)).to.equal('1d 1h');

    // 2 hours, 30 minutes, 45 seconds - should show only "2h 30m"
    expect(formatDurationFromSeconds(9045)).to.equal('2h 30m');

    // 5 minutes, 30 seconds - should show "5m 30s"
    expect(formatDurationFromSeconds(330)).to.equal('5m 30s');
  });

  it('handles large durations', () => {
    expect(formatDurationFromSeconds(604800)).to.equal('7d'); // 1 week
    expect(formatDurationFromSeconds(1209600)).to.equal('14d'); // 2 weeks
    expect(formatDurationFromSeconds(2678400)).to.equal('31d'); // ~1 month
  });

  it('supports horizontal bar charts', async () => {
    const chart: TembaChart = await getChart();

    // Test that horizontal property defaults to false
    expect(chart.horizontal).to.equal(false);

    // Set horizontal to true
    chart.horizontal = true;
    chart.data = sampleData;
    await chart.updateComplete;

    // Wait for the chart to be created after data is set
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Test that the chart was created with horizontal configuration
    expect(chart.horizontal).to.equal(true);
    expect(chart.chart).to.exist;

    // Test that the chart configuration includes indexAxis: 'y' for horizontal bars
    const chartConfig = chart.chart.options;
    expect(chartConfig.indexAxis).to.equal('y');
  });
});
