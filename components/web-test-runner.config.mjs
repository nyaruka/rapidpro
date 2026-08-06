/* eslint-disable no-async-promise-executor */
/* eslint-disable @typescript-eslint/no-unused-vars */
process.env.PUPPETEER_DISABLE_HEADLESS_WARNING = '1';
import { puppeteerLauncher } from '@web/test-runner-puppeteer';
import { defaultReporter, summaryReporter } from '@web/test-runner';

// Workaround for a wtr OOM under coverage on this branch. With our
// volume of instrumented code, the merged istanbul-coverage payload
// across all 121 test sessions overflows V8's max string length
// (~512MB) when `getTestCoverage` deep-clones it via
// `JSON.parse(JSON.stringify(coverages))`. That clone exists only to
// insulate watch mode from istanbul's in-place mutation of the
// originals — in non-watch coverage mode the clone is dead weight.
// The throw is caught inside `onSessionFinished`'s try/catch, which
// calls `runner.stop(error)` and silently exits 1 (the `console.error`
// it logs is swallowed by wtr's BufferedLogger before the final
// reportEnd flush ever runs).
//
// We can't import `getTestCoverage` directly (it's a transitive dep
// not re-exported by `@web/test-runner`), so we shim JSON.parse: when
// it's handed the sentinel produced by our JSON.stringify shim, it
// returns the original `coverages` array instead of the stringified
// copy. The shim is intentionally narrow:
//
//   - Gated on `WTR_COVERAGE_SHIM` (defaults on when --coverage is in
//     argv; can be force-disabled by setting it to "0") so it never
//     runs in plain `bun run test`, only in the coverage path.
//   - Sentinel is a runtime-random string, so a fixture/cached body
//     containing the literal can't collide.
//   - `__pendingCoverages` is cleared on every parse — matched OR not —
//     so the ~512MB reference never lingers past one call pair, and
//     mismatched call sequences never silently corrupt other parses.
//   - The shape check `__looksLikeCoverageArray` only matches arrays
//     whose first element is an object keyed by absolute file paths
//     pointing at istanbul-shaped entries; it can't be triggered by
//     ordinary JSON the orchestrator stringifies (HTTP responses, etc.)
//
// A wtr update that changes how getTestCoverage clones would make the
// shim a no-op (`__looksLikeCoverageArray` returns false) — we'd then
// regress to the original OOM rather than silently corrupt data, and
// the next coverage run would surface it immediately. Long-term, the
// right fix is patch-package on `@web/test-runner-core`'s
// `getTestCoverage` to skip the clone in non-watch mode; this shim is
// scoped to keep that scope-creep out of this PR.
const __WTR_COVERAGE_SHIM_ON =
  process.env.WTR_COVERAGE_SHIM !== '0' &&
  (process.env.WTR_COVERAGE_SHIM === '1' ||
    process.argv.some((a) => a === '--coverage' || a === '--watch-coverage'));

if (__WTR_COVERAGE_SHIM_ON) {
  const __origStringify = JSON.stringify;
  const __origParse = JSON.parse;
  // Random sentinel so the literal string in user content can't
  // accidentally trigger the parse shim.
  const __CLONE_SENTINEL =
    '__WTR_COVERAGE_CLONE__' + Math.random().toString(36).slice(2);
  let __pendingCoverages = null;

  const __looksLikeCoverageArray = (value) => {
    if (!Array.isArray(value) || value.length === 0) return false;
    const first = value[0];
    if (!first || typeof first !== 'object' || Array.isArray(first)) {
      return false;
    }
    const keys = Object.keys(first);
    if (keys.length === 0) return false;
    if (!keys.every((k) => k.startsWith('/') || /^[a-zA-Z]:[\\/]/.test(k))) {
      return false;
    }
    const entry = first[keys[0]];
    return (
      entry &&
      typeof entry === 'object' &&
      (entry.statementMap || entry.fnMap || entry.b || entry.s)
    );
  };

  JSON.stringify = function (value, ...rest) {
    if (__looksLikeCoverageArray(value)) {
      // A second matched stringify before a matched parse would
      // otherwise silently drop the first payload — clear first.
      __pendingCoverages = value;
      return __CLONE_SENTINEL;
    }
    return __origStringify(value, ...rest);
  };
  JSON.parse = function (text, ...rest) {
    // Always clear pending on parse (matched or not). Keeps the ~512MB
    // reference from outliving a single call pair even if the matched
    // parse never arrives (e.g. wtr throws between the two calls).
    const pending = __pendingCoverages;
    __pendingCoverages = null;
    if (text === __CLONE_SENTINEL && pending) {
      return pending;
    }
    return __origParse(text, ...rest);
  };
}
import { esbuildPlugin } from '@web/dev-server-esbuild';
import fs from 'fs';
import * as path from 'path';
import * as pngs from 'pngjs';
import dynamicpixelmatch from 'dynamicpixelmatch';
import pixelmatch from 'pixelmatch';
import sizeOf from 'image-size';

import rimraf from 'rimraf';

import replace from '@rollup/plugin-replace';
import { fromRollup } from '@web/dev-server-rollup';

const replacePlugin = fromRollup(replace);
const TEMBA_COMPONENTS_VERSION = JSON.parse(
  fs.readFileSync(path.resolve('./package.json'), 'utf-8')
).version;

const SCREENSHOTS = 'screenshots';
const DIFF = 'diff';
const TEST = 'test';
const TRUTH = 'truth';

const PNG = pngs.PNG;

const fileExists = (filename) => {
  return new Promise((resolve, reject) => {
    fs.access(filename, fs.F_OK, (err) => {
      if (err) {
        resolve(false);
      }
      resolve(true);
    });
  });
};

const ensureExists = function (mydir) {
  return new Promise((resolve, reject) => {
    fs.mkdir(mydir, { recursive: true }, function (err) {
      if (err) {
        if (err.code == 'EEXIST')
          resolve('ignore the error if the folder already exists');
        else reject(err); // something else went wrong
      }
      resolve('path created');
    });
  });
};

const getPath = async (type, filename) => {
  const file = path.resolve(SCREENSHOTS, type, filename);

  // make sure our directory exists
  const parts = filename.split(path.sep);
  let pngdir = parts.slice(0, parts.length - 1);
  await ensureExists(path.resolve(SCREENSHOTS, type, ...pngdir));

  return file;
};

const checkScreenshot = async (filename, excluded, threshold) => {
  return new Promise(async (resolve, reject) => {
    const doneReading = async () => {
      // Wait until both files are read.
      if (++filesRead < 2) return;

      // The files should be the same size.
      if (img1.width != img2.width || img1.height !== img2.height) {
        // resolve(`Screenshot was ${img2.width}x${img2.height} but should be ${img1.width}x${img1.height}:\n${testImg}`);

        reject({
          message: 'Screenshot was not the right size',
          expected: `${img1.width}x${img1.height}`,
          actual: `${img2.width}x${img2.height}`,
          files: [testImg, truthImg, path.resolve(SCREENSHOTS)]
        });
        return;
      }

      // Do the visual diff.
      const diff = new PNG({ width: img1.width, height: img2.height });
      const matchOptions = {
        threshold: threshold || 0.3,
        includeAA: false,
        diffColor: [255, 0, 0],
        aaColor: [0, 0, 255]
      };
      const numDiffPixels =
        excluded != null && excluded.length != 0
          ? dynamicpixelmatch(
              img1.data,
              img2.data,
              diff.data,
              img1.width,
              img1.height,
              matchOptions,
              excluded
            )
          : pixelmatch(
              img1.data,
              img2.data,
              diff.data,
              img1.width,
              img1.height,
              matchOptions
            );

      // The files should look the same (allow a tiny tolerance for subpixel rendering differences)
      const totalPixels = img1.width * img1.height;
      const diffRatio = numDiffPixels / totalPixels;
      if (diffRatio > 0.001) {
        const diffImg = await getPath(DIFF, filename);
        diff.pack().pipe(fs.createWriteStream(diffImg));
        reject({
          message: `Pixel match failed (${numDiffPixels} pixels differ, ${(diffRatio * 100).toFixed(3)}%)`,
          files: [diffImg, testImg, truthImg, path.resolve(SCREENSHOTS)]
        });
      }
      resolve('success');
    };

    let filesRead = 0;

    const truthImg = await getPath(TRUTH, filename);
    const testImg = await getPath(TEST, filename);

    const img1 = fs
      .createReadStream(truthImg)
      .pipe(new PNG())
      .on('parsed', doneReading);

    const img2 = fs
      .createReadStream(testImg)
      .pipe(new PNG())
      .on('parsed', doneReading);
  });
};

// clear out any past tests once per process — clearing per-page would race
// with other concurrent pages that have already written test screenshots and
// are about to read them back, causing intermittent ENOENT failures.
rimraf.sync(path.resolve(SCREENSHOTS, DIFF));
rimraf.sync(path.resolve(SCREENSHOTS, TEST));

const wireScreenshots = async (page, context, wait, replaceScreenshots) => {

  await page.exposeFunction(
    'matchPageSnapshot',
    (filename, clip, excluded, threshold, waitForNetwork = false) => {
      return new Promise(async (resolve, reject) => {
        try {
          if (page.isClosed()) {
            resolve(null);
            return;
          }

          const testFile = await getPath(TEST, filename);
          const truthFile = await getPath(TRUTH, filename);

          // Wait for network idle before taking screenshot
          try {
            if (waitForNetwork) {
              await page.waitForNetworkIdle({ idleTime: 500, timeout: 2000 });
            } else if (wait) {
              await page.waitForNetworkIdle({ idleTime: 100, timeout: 1000 });
            } else {
              await page.waitForNetworkIdle({ idleTime: 10, timeout: 100 });
            }
          } catch (error) {
            // timeout is expected, proceed with screenshot
          }

          if (page.isClosed()) {
            resolve(null);
            return;
          }

          if (!(await fileExists(truthFile))) {
            // no truth yet, record it
            await page.screenshot({ path: truthFile, clip });
          } else {
            // if its close, force our file to be the same size as our truth for pixelmatch
            const dimensions = sizeOf(truthFile);
            let { width, height } = dimensions;

            // we should have a device ratio of 2
            width /= 2;
            height /= 2;

            const wDiff = Math.abs((clip.width - width) / width);
            const hDiff = Math.abs((clip.height - height) / height);

            if (wDiff < 0.15) {
              clip.width = width;
            }

            if (hDiff < 0.15) {
              clip.height = height;
            }

            if (!clip.width || !clip.height) {
              reject({ message: "Couldn't take screenshot clip is empty" });
              return;
            }

            // create a test screenshot to compare with our truth
            await page.screenshot({ path: testFile, clip });

            try {
              const result = await checkScreenshot(
                filename,
                excluded,
                threshold
              );
              resolve(result);
            } catch (error) {
              if (replaceScreenshots) {
                await page.screenshot({ path: truthFile, clip });
                resolve();
              } else {
                reject(error);
              }
              return;
            }
          }

          resolve(true);
        } catch (error) {
          // guard against page closure during screenshot operations
          if (
            error.constructor.name === 'TargetCloseError' ||
            page.isClosed()
          ) {
            resolve(null);
          } else {
            reject(error);
          }
        }
      });
    }
  );

  await page.exposeFunction('waitForNetworkIdle', async () => {
    if (!page.isClosed()) await page.waitForNetworkIdle();
  });

  await page.exposeFunction('setViewport', async (options) => {
    if (!page.isClosed()) await page.setViewport(options);
  });

  await page.exposeFunction('waitFor', (millis) => {
    return new Promise((resolve) => setTimeout(resolve, millis));
  });

  await page.exposeFunction('moveMouse', async (x, y) => {
    if (!page.isClosed()) await page.mouse.move(x, y, { steps: 5 });
  });

  await page.exposeFunction('mouseClick', async (x, y) => {
    if (page.isClosed()) return;
    await page.mouse.move(x, y);
    // reset mouse state to avoid "already pressed" errors in Puppeteer 24+
    await page.mouse.up().catch(() => {});
    await page.mouse.down();
    await page.mouse.up();
  });

  await page.exposeFunction('mouseDown', async () => {
    if (page.isClosed()) return;
    // reset mouse state to avoid "already pressed" errors in Puppeteer 24+
    await page.mouse.up().catch(() => {});
    await page.mouse.down();
  });

  await page.exposeFunction('mouseUp', async () => {
    if (!page.isClosed()) await page.mouse.up().catch(() => {});
  });

  await page.exposeFunction('click', async (element) => {
    if (page.isClosed()) return;
    // reset mouse state to avoid "already pressed" errors
    await page.mouse.up().catch(() => {});
    const frame = await page.frames().find((f) => {
      return true;
    });
    const ele = await frame.$(element);
    await ele.click({});
  });

  await page.exposeFunction(
    'typeInto',
    async (selector, text, replace = false, enter = false) => {
      if (page.isClosed()) return;
      const selectors = selector.split(':');
      const frame = await page.frames().find((f) => {
        return true;
      });
      await frame.$(selectors[0]);

      let codeSelector = `document.querySelector("${selectors[0]}")`;
      selectors.shift();
      if (selectors.length > 0) {
        codeSelector +=
          '.' +
          selectors
            .map((entry) => `shadowRoot.querySelector("${entry}")`)
            .join('.');
      }

      const element = await page.evaluateHandle(codeSelector);
      await element.click({ clickCount: replace ? 3 : 1 });
      await page.keyboard.type(text);

      if (enter) {
        await page.keyboard.press('Enter');
      }
    }
  );

  await page.exposeFunction('pressKey', async (key, times, options) => {
    if (page.isClosed()) return;
    for (let i = 0; i < times; i++) {
      await page.keyboard.press(key, options);
    }
  });

  await page.exposeFunction('type', async (text) => {
    if (!page.isClosed()) await page.keyboard.type(text);
  });
};

export default {
  rootDir: './',
  files: ['**/test/**/*.test.ts', '!**/test/utils.test.ts'],
  nodeResolve: true,
  concurrency: 4,
  // screenshot-heavy test files can exceed the default 120s on slower CI runners
  testsFinishTimeout: 240000,
  filterBrowserLogs(log) {
    return !log.args.some(
      (arg) => typeof arg === 'string' && arg.includes('Lit is in dev mode')
    );
  },
  coverageConfig: {
    include: ['src/**']
  },
  reporters: [
    defaultReporter({ reportTestResults: true, reportTestProgress: true }),
    summaryReporter({ flatten: true })
  ],
  testFramework: {
    config: {
      timeout: '10000'
    }
  },

  plugins: [
    replacePlugin({
      preventAssignment: true,
      'process.env.NODE_ENV': JSON.stringify('test'),
      __TEMBA_DEV_SERVER__: JSON.stringify(false),
      __TEMBA_COMPONENTS_VERSION__: JSON.stringify(TEMBA_COMPONENTS_VERSION)
    }),
    {
      name: 'api-mock-server',
      serve(context) {
        // Handle API endpoints by serving static files
        if (
          context.request.method === 'GET' &&
          context.path.startsWith('/api/')
        ) {
          // Map API endpoints to static files
          const apiMappings = {
            '/api/v2/groups.json': './static/api/groups.json',
            '/api/v2/labels.json': './static/api/labels.json',
            '/api/v2/fields.json': './static/api/fields.json',
            '/api/v2/globals.json': './static/api/globals.json',
            '/api/v2/completion.json': './static/mr/docs/en-us/editor.json',
            '/api/v2/functions.json': './static/api/functions.json',
            '/api/internal/templates.json': './static/api/templates.json',
            '/api/v2/media.json': './static/api/media.json',
            '/api/v2/users.json': './static/api/users.json',
            '/api/v2/contacts.json': './static/api/contacts.json',
            '/api/v2/optins.json': './static/api/optins.json',
            '/api/v2/topics.json': './static/api/topics.json',
            '/api/v2/workspace.json': './static/api/workspace.json',
            '/api/internal/locations.json': './static/api/locations.json',
            '/api/internal/orgs.json': './static/api/orgs.json'
          };

          // Handle base path without query parameters
          const basePath = context.path.split('?')[0];
          const staticFile = apiMappings[basePath];

          if (staticFile && fs.existsSync(path.resolve(staticFile))) {
            context.contentType = 'application/json';
            context.body = fs.readFileSync(path.resolve(staticFile), 'utf-8');
            return;
          }
        }
      }
    },
    {
      name: 'add-style',
      transform(context) {
        if (context.response.is('html')) {
          return {
            body: context.body.replace(
              /<head>/,
              `<head><link rel="stylesheet" href="/test-assets/temba-components.css"/><link rel="stylesheet" href="/test-assets/style.css"/>`
            )
          };
        }
      }
    },
    esbuildPlugin({ ts: true, tsconfig: './tsconfig.json' })

    /* importMapsPlugin({
      inject: {
        importMap: {
          imports: {
            // mock a module in your own code
            // './out-tsc/src/utils/index.js': 'out-tsc/test/server.js',
            // './src/utils': './test/server'
          },
        },
      },
    }),*/
  ],
  browsers: [
    puppeteerLauncher({
      launchOptions: {
        args: [
          '--font-render-hinting=medium',
          '--force-color-profile=srgb',
          '--hide-scrollbars',
          '--disable-web-security',
          '--force-device-scale-factor=1',
          '--no-sandbox',
          '--disable-gpu',
          '--disable-font-subpixel-positioning',
          '--disable-lcd-text',
          '--force-prefers-reduced-motion',
          '--disable-background-timer-throttling',
          '--disable-backgrounding-occluded-windows',
          '--disable-renderer-backgrounding',
          // additional flags for consistent rendering across environments
          '--disable-gpu-sandbox',
          '--disable-software-rasterizer',
          '--disable-background-networking',
          '--disable-default-apps',
          '--disable-extensions',
          '--disable-sync',
          '--disable-translate',
          '--hide-crash-restore-bubble',
          '--metrics-recording-only',
          '--no-first-run',
          '--safebrowsing-disable-auto-update',
          '--use-mock-keychain',
          '--disable-ipc-flooding-protection',
          '--disable-component-update',
          '--disable-domain-reliability',
          '--disable-dev-shm-usage'
        ],
        headless: true
      },
      createPage: async ({ context, config }) => {
        const params = config['unknown'] || [];
        const wait = !params.includes('--fast');
        const replaceScreenshots = params.includes('--replace-screenshots');

        const page = await context.newPage();
        await page.setUserAgent(
          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36'
        );

        // detect if we're running in copilot's environment
        const isCopilotEnvironment =
          process.env.COPILOT_API_URL || process.env.COPILOT_AGENT_CALLBACK_URL;

        // inject script into every document that loads
        await page.evaluateOnNewDocument(
          (watched, copilotEnv) => {
            window.watched = watched;
            window.isCopilotEnvironment = copilotEnv;
          },
          config.watch,
          !!isCopilotEnvironment
        );

        // serialize wireScreenshots setup to avoid CDP deadlock with concurrent pages
        if (!globalThis.__wireScreenshotsLock) {
          globalThis.__wireScreenshotsLock = Promise.resolve();
        }
        globalThis.__wireScreenshotsLock =
          globalThis.__wireScreenshotsLock.then(() =>
            wireScreenshots(page, context, wait, replaceScreenshots)
          );
        await globalThis.__wireScreenshotsLock;

        await page.emulateTimezone('GMT');

        return page;
      }
    })
  ]
};
