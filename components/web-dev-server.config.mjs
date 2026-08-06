import replace from '@rollup/plugin-replace';
import { fromRollup } from '@web/dev-server-rollup';
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';

// Import the shared flow info generator and Minio functionality
import { generateFlowInfo, handleMinioUpload, handleEntityCreation } from './web-dev-mock.mjs';

// Development data directory outside project structure
const DEV_DATA_DIR = '/tmp/temba-dev-data';
const DEV_FLOWS_DIR = path.join(DEV_DATA_DIR, 'flows');
const DEV_API_DIR = path.join(DEV_DATA_DIR, 'api');
const TEMBA_COMPONENTS_VERSION = JSON.parse(
  fs.readFileSync(path.resolve('./package.json'), 'utf-8')
).version;

// Setup development data directories and copy defaults if needed
function setupDevData() {
  // Ensure directories exist
  if (!fs.existsSync(DEV_DATA_DIR)) {
    fs.mkdirSync(DEV_DATA_DIR, { recursive: true });
  }
  if (!fs.existsSync(DEV_FLOWS_DIR)) {
    fs.mkdirSync(DEV_FLOWS_DIR, { recursive: true });
  }
  if (!fs.existsSync(DEV_API_DIR)) {
    fs.mkdirSync(DEV_API_DIR, { recursive: true });
  }

  // Copy default flows if dev flows directory is empty
  const defaultFlowsDir = path.resolve('./demo/data/flows');
  if (fs.existsSync(defaultFlowsDir)) {
    const devFlowFiles = fs.readdirSync(DEV_FLOWS_DIR).filter(f => f.endsWith('.json'));
    if (devFlowFiles.length === 0) {
      const defaultFlowFiles = fs.readdirSync(defaultFlowsDir).filter(f => f.endsWith('.json'));
      console.log(`Copying ${defaultFlowFiles.length} default flow files to development directory...`);
      defaultFlowFiles.forEach(file => {
        fs.copyFileSync(
          path.join(defaultFlowsDir, file),
          path.join(DEV_FLOWS_DIR, file)
        );
      });
    }
  }

  // Copy default API files if dev API directory is empty
  const defaultApiDir = path.resolve('./static/api');
  if (fs.existsSync(defaultApiDir)) {
    const devApiFiles = fs.readdirSync(DEV_API_DIR).filter(f => f.endsWith('.json'));
    if (devApiFiles.length === 0) {
      const defaultApiFiles = fs.readdirSync(defaultApiDir).filter(f => f.endsWith('.json'));
      console.log(`Copying ${defaultApiFiles.length} default API files to development directory...`);
      defaultApiFiles.forEach(file => {
        fs.copyFileSync(
          path.join(defaultApiDir, file),
          path.join(DEV_API_DIR, file)
        );
      });
    }
  }
}

// Get the appropriate file path, preferring dev directory over defaults
function getDataFilePath(type, filename) {
  const devPath = type === 'flows' 
    ? path.join(DEV_FLOWS_DIR, filename)
    : path.join(DEV_API_DIR, filename);
  
  const defaultPath = type === 'flows'
    ? path.resolve(`./demo/data/flows/${filename}`)
    : path.resolve(`./static/api/${filename}`);

  // Use dev file if it exists, otherwise fall back to default
  return fs.existsSync(devPath) ? devPath : defaultPath;
}

// Handle entity creation using development directory
function handleDevEntityCreation(entityType, context) {
  const entityConfigs = {
    labels: {
      filename: 'labels.json',
      createEntity: (name) => ({
        uuid: crypto.randomUUID(),
        name: name.trim(),
        count: 0
      }),
      nameField: 'name',
      entityType: 'Label'
    },
    fields: {
      filename: 'fields.json',
      createEntity: (name) => ({
        key: name.trim().toLowerCase().replace(/\s+/g, '_'),
        name: name.trim(),
        type: 'text',
        featured: false,
        priority: 0,
        usages: {
          flows: 0,
          groups: 0,
          campaign_events: 0
        },
        agent_access: 'view',
        label: name.trim(),
        value_type: 'text'
      }),
      nameField: 'name',
      uniqueField: 'key',
      entityType: 'Field'
    },
    groups: {
      filename: 'groups.json',
      createEntity: (name) => ({
        uuid: crypto.randomUUID(),
        name: name.trim(),
        query: null,
        status: 'ready',
        count: 0
      }),
      nameField: 'name',
      entityType: 'Group'
    }
  };

  const config = entityConfigs[entityType];
  
  if (!config) {
    context.status = 400;
    context.body = JSON.stringify({ error: `Unsupported entity type: ${entityType}` });
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    let body = '';
    
    context.req.on('data', chunk => {
      body += chunk.toString();
    });
    
    context.req.on('end', () => {
      try {
        const requestData = JSON.parse(body);
        const entityName = requestData[config.nameField] || '';
        
        if (!entityName.trim()) {
          context.status = 400;
          context.body = JSON.stringify({ error: `${config.entityType} name is required` });
          resolve();
          return;
        }
        
        // Get the correct file path (dev directory preferred)
        const filePath = getDataFilePath('api', config.filename);
        
        // Read existing data file
        let entityData;
        
        try {
          entityData = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
        } catch (error) {
          // If file doesn't exist, create basic structure
          entityData = {
            next: null,
            previous: null,
            results: []
          };
        }
        
        // Check if entity already exists
        const uniqueField = config.uniqueField || config.nameField;
        const checkValue = uniqueField === 'key' 
          ? entityName.trim().toLowerCase().replace(/\s+/g, '_')
          : entityName.trim().toLowerCase();
          
        const existingEntity = entityData.results.find(
          entity => entity[uniqueField].toLowerCase() === checkValue
        );
        
        if (existingEntity) {
          // Return existing entity
          context.contentType = 'application/json';
          context.body = JSON.stringify(existingEntity);
          resolve();
          return;
        }
        
        // Create new entity
        const newEntity = config.createEntity(entityName);
        
        // Add to entity data
        entityData.results.push(newEntity);
        
        // Write back to the dev directory file
        const devFilePath = path.join(DEV_API_DIR, config.filename);
        fs.writeFileSync(devFilePath, JSON.stringify(entityData, null, 2));
        
        // Return the new entity
        context.contentType = 'application/json';
        context.body = JSON.stringify(newEntity);
        context.status = 201;
        
        console.log(`📝 ${config.entityType} created:`, newEntity);
        resolve();
        
      } catch (error) {
        console.error(`Error creating ${entityType}:`, error);
        context.status = 500;
        context.body = JSON.stringify({ error: 'Internal server error' });
        resolve();
      }
    });
  });
}

const replacePlugin = fromRollup(replace);

// Initialize development data on server startup
setupDevData();

// Simple wrapper function to use the shared flow info generator
function generateFlowMetadata(flowDefinition) {
  return generateFlowInfo(flowDefinition);
}

// In-memory state for the content-list demo so the labeling flow
// (label, refresh, recheck) is exercisable end-to-end. The first
// GET / POST loads from the on-disk fixture; subsequent ops mutate
// the in-memory copy. The on-disk fixture is never written — state
// resets on dev-server restart, which is the right default for a
// throwaway demo.
const demoState = {
  messages: null,
  flows: null,
  labels: null,
  flowLabels: null
};

function loadDemoJson(stateKey, filePath) {
  if (demoState[stateKey] === null) {
    demoState[stateKey] = JSON.parse(
      fs.readFileSync(path.resolve(filePath), 'utf-8')
    );
  }
  return demoState[stateKey];
}

/** Filter the in-memory demo items for a content-list endpoint.
 *
 * Supports `?label=<uuid>` (only items carrying that label) so the
 * demo can exercise the filtered-view → label-removed → row-drops-
 * out → recheck-selection lifecycle. */
function getFilteredDemoItems(data, url) {
  const labelFilter = url.searchParams.get('label');
  let results = data.results;
  if (labelFilter) {
    results = results.filter((item) =>
      (item.labels || []).some((l) => l.uuid === labelFilter)
    );
  }
  return { ...data, count: results.length, results };
}

/** Apply a label-toggle to a list of in-memory items, mirroring
 * smartmin's BulkActionMixin behavior. Body is x-www-form-urlencoded
 * (params: action, objects[], label, add). The `idKey` is what each
 * item is matched against (messages use numeric `id`, flows use
 * string `uuid`). */
function applyDemoListAction(body, items, labels, idKey) {
  const params = new URLSearchParams(body);
  const action = params.get('action');
  if (action !== 'label') return;
  const labelUuid = params.get('label');
  const add = params.get('add') !== 'false';
  const objectIds = params.getAll('objects');
  const label = (labels.results || []).find((l) => l.uuid === labelUuid);
  if (!label) return;
  objectIds.forEach((idStr) => {
    const lookup = idKey === 'id' ? parseInt(idStr, 10) : idStr;
    const item = items.results.find((i) => i[idKey] === lookup);
    if (!item) return;
    item.labels = item.labels || [];
    const idx = item.labels.findIndex((l) => l.uuid === labelUuid);
    if (add && idx < 0) {
      item.labels.push({ uuid: label.uuid, name: label.name });
    } else if (!add && idx >= 0) {
      item.labels.splice(idx, 1);
    }
  });
}

export default {
  nodeResolve: true,
  middleware: [
    // Permissive CORS so this dev server can be loaded as a cross-origin
    // module source by a rapidpro instance running on a different localhost
    // port (e.g. Nautilus/run-pair.sh launching rapidpro:8001 + components:3011).
    // The Store fetches completion.json with custom headers (X-CSRFToken,
    // X-Temba-Workspace, X-Requested-With), which makes it a non-simple
    // cross-origin request, so we must also answer the preflight (OPTIONS)
    // with the allowed methods/headers or the browser blocks it.
    (ctx, next) => {
      ctx.set('Access-Control-Allow-Origin', '*');
      ctx.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
      ctx.set('Access-Control-Allow-Headers', '*');
      if (ctx.method === 'OPTIONS') {
        ctx.status = 204;
        return;
      }
      return next();
    },
  ],
  plugins: [
    replacePlugin({
      preventAssignment: true,
      'process.env.NODE_ENV': JSON.stringify('development'),
      '__TEMBA_DEV_SERVER__': JSON.stringify(true),
      '__TEMBA_COMPONENTS_VERSION__': JSON.stringify(TEMBA_COMPONENTS_VERSION),
      'process.env.MINIO_ENDPOINT': JSON.stringify('http://minio:9000'),
      'process.env.MINIO_PUBLIC_ENDPOINT': JSON.stringify('http://localhost:9000'),
      'process.env.MINIO_ACCESS_KEY': JSON.stringify('root'),
      'process.env.MINIO_SECRET_KEY': JSON.stringify('tembatemba'),
    }),
    {
      name: 'api-mock-server',
      serve(context) {
        // Handle API endpoints by serving static files
        if (context.request.method === 'GET' && context.path.startsWith('/api/')) {
          // Map API endpoints to static files
          const apiMappings = {
            '/api/v2/groups.json': 'groups.json',
            '/api/v2/labels.json': 'labels.json',
            '/api/v2/flow-labels.json': 'flow-labels.json',
            '/api/v2/fields.json': 'fields.json', 
            '/api/v2/globals.json': 'globals.json',
            '/api/v2/resthooks.json': 'resthooks.json',
            '/api/v2/completion.json': '../mr/docs/en-us/editor.json', // Special case
            '/api/v2/functions.json': 'functions.json',
            '/api/internal/templates.json': 'templates.json',
            '/api/v2/media.json': 'media.json',
            '/api/v2/users.json': 'users.json',
            '/api/v2/contacts.json': 'contacts.json',
            '/api/v2/optins.json': 'optins.json',
            '/api/v2/topics.json': 'topics.json',
            '/api/v2/workspace.json': 'workspace.json',
            '/api/internal/locations.json': 'locations.json',
            '/api/internal/orgs.json': 'orgs.json',
            '/api/v2/channels.json': 'channels.json',
            '/api/internal/llms.json': 'llms.json'
          };

          // Handle base path without query parameters
          const basePath = context.path.split('?')[0];
          const filename = apiMappings[basePath];
          
          if (filename) {
            let filePath;
            if (filename === '../mr/docs/en-us/editor.json') {
              // Special case for completion endpoint
              filePath = path.resolve('./static/mr/docs/en-us/editor.json');
            } else {
              filePath = getDataFilePath('api', filename);
            }
            
            if (fs.existsSync(filePath)) {
              context.contentType = 'application/json';
              context.body = fs.readFileSync(filePath, 'utf-8');
              return;
            }
          }

          // Handle dynamic flows endpoint
          if (basePath === '/api/v2/flows.json') {
            // Check dev flows directory first, then fall back to default
            let flowsDir = DEV_FLOWS_DIR;
            if (!fs.existsSync(flowsDir) || fs.readdirSync(flowsDir).filter(f => f.endsWith('.json')).length === 0) {
              flowsDir = path.resolve('./demo/data/flows');
            }
            
            if (fs.existsSync(flowsDir)) {
              const files = fs.readdirSync(flowsDir).filter(file => file.endsWith('.json'));
              const flows = files.map(file => {
                try {
                  const filePath = path.join(flowsDir, file);
                  const flowData = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
                  return {
                    uuid: flowData.definition.uuid,
                    name: flowData.definition.name
                  };
                } catch (e) {
                  console.warn(`Error reading flow file ${file}:`, e.message);
                  return null;
                }
              }).filter(Boolean);

              context.contentType = 'application/json';
              context.body = JSON.stringify({ results: flows });
              return;
            }
          }
        }

        // Handle contact chat history
        if (context.request.method === 'GET' && context.path.match(/^\/contact\/chat\/[^/]+\/$/)) {
          const historyPath = path.resolve('./demo/data/contact-chat-history.json');
          if (fs.existsSync(historyPath)) {
            const history = JSON.parse(fs.readFileSync(historyPath, 'utf-8'));
            const url = new URL(context.request.url, 'http://localhost');
            const before = url.searchParams.get('before');
            const after = url.searchParams.get('after');

            if (before) {
              // return events older than this UUID
              const events = history.events.filter(e => e.uuid < before);
              context.contentType = 'application/json';
              context.body = JSON.stringify({ events: events, next: null });
              return;
            } else if (after) {
              // return events newer than this UUID
              const events = history.events.filter(e => e.uuid > after);
              context.contentType = 'application/json';
              context.body = JSON.stringify({ events: events.reverse(), next: null });
              return;
            }
          }
          context.contentType = 'application/json';
          context.body = JSON.stringify({ error: 'must specify before or after parameter' });
          context.status = 400;
          return;
        }

        // Handle contact chat search
        if (context.request.method === 'GET' && context.path.match(/^\/contact\/chat_search\/[^/]+\/$/)) {
          const historyPath = path.resolve('./demo/data/contact-chat-history.json');
          if (fs.existsSync(historyPath)) {
            const history = JSON.parse(fs.readFileSync(historyPath, 'utf-8'));
            const url = new URL(context.request.url, 'http://localhost');
            const text = (url.searchParams.get('text') || '').toLowerCase();
            if (text) {
              const results = history.events.filter(
                e => e.msg && e.msg.text && e.msg.text.toLowerCase().includes(text)
              );
              context.contentType = 'application/json';
              context.body = JSON.stringify({ results });
              return;
            }
          }
          context.contentType = 'application/json';
          context.body = JSON.stringify({ results: [] });
          return;
        }

        // Handle contact timeline (upcoming / past scheduled events).
        // Dates are generated relative to now so the demo never goes stale.
        if (context.request.method === 'GET' && context.path.match(/^\/contact\/timeline\/[^/]+\/$/)) {
          const now = new Date();
          const days = n => new Date(now.getTime() + n * 86400000).toISOString();
          const campaign = { uuid: 'campaign-1', name: 'Customer Onboarding' };
          context.contentType = 'application/json';
          context.body = JSON.stringify({
            now: now.toISOString(),
            campaigns: [campaign],
            future_count: 3,
            future: [
              {
                type: 'campaign_event',
                scheduled: days(2),
                repeat_period: 'O',
                campaign,
                flow: { uuid: 'flow-1', name: 'Welcome Check-in' }
              },
              {
                type: 'scheduled_broadcast',
                scheduled: days(5),
                repeat_period: 'W',
                message: 'Weekly tips: how to get the most out of your account'
              },
              {
                type: 'campaign_event',
                scheduled: days(9),
                repeat_period: 'O',
                campaign,
                flow: { uuid: 'flow-2', name: 'Satisfaction Survey' }
              }
            ],
            past: [
              {
                type: 'campaign_event',
                scheduled: days(-3),
                repeat_period: 'O',
                campaign,
                flow: { uuid: 'flow-3', name: 'Getting Started' }
              },
              {
                type: 'sent_broadcast',
                scheduled: days(-7),
                repeat_period: 'O',
                message: 'Welcome aboard!'
              }
            ],
            next_before: null,
            next_after: null
          });
          return;
        }

        // Serve the content-list demo messages from in-memory state
        // so a labeling POST is reflected on the next refresh. Honors
        // an optional `?label=<uuid>` filter for testing the filtered-
        // view drop-out lifecycle.
        if (
          context.request.method === 'GET' &&
          context.path === '/demo/components/content-list/data/messages.json'
        ) {
          const reqUrl = new URL(context.request.url, 'http://localhost');
          const data = loadDemoJson(
            'messages',
            './demo/components/content-list/data/messages.json'
          );
          context.contentType = 'application/json';
          context.body = JSON.stringify(getFilteredDemoItems(data, reqUrl));
          return;
        }

        // Same lifecycle for the flows list — labels carried on
        // each flow live in flows.json; the labels themselves come
        // from /api/v2/flow-labels.json.
        if (
          context.request.method === 'GET' &&
          context.path === '/demo/components/content-list/data/flows.json'
        ) {
          const reqUrl = new URL(context.request.url, 'http://localhost');
          const data = loadDemoJson(
            'flows',
            './demo/components/content-list/data/flows.json'
          );
          context.contentType = 'application/json';
          context.body = JSON.stringify(getFilteredDemoItems(data, reqUrl));
          return;
        }

        // Bulk-action POSTs for the content-list demo: mutate the
        // in-memory items so the subsequent refresh actually shows
        // the labeling change. Body is form-urlencoded as sent by
        // ContentList.toggleLabel().
        if (
          context.request.method === 'POST' &&
          context.path === '/demo/components/content-list/list-action'
        ) {
          return new Promise((resolve) => {
            let body = '';
            context.req.on('data', (chunk) => { body += chunk.toString(); });
            context.req.on('end', () => {
              const messages = loadDemoJson(
                'messages',
                './demo/components/content-list/data/messages.json'
              );
              const labels = loadDemoJson(
                'labels',
                './static/api/labels.json'
              );
              applyDemoListAction(body, messages, labels, 'id');
              context.contentType = 'application/json';
              context.status = 200;
              context.body = JSON.stringify({ status: 'success' });
              resolve();
            });
          });
        }

        if (
          context.request.method === 'POST' &&
          context.path === '/demo/components/content-list/flow-list-action'
        ) {
          return new Promise((resolve) => {
            let body = '';
            context.req.on('data', (chunk) => { body += chunk.toString(); });
            context.req.on('end', () => {
              const flows = loadDemoJson(
                'flows',
                './demo/components/content-list/data/flows.json'
              );
              const labels = loadDemoJson(
                'flowLabels',
                './static/api/flow-labels.json'
              );
              applyDemoListAction(body, flows, labels, 'uuid');
              context.contentType = 'application/json';
              context.status = 200;
              context.body = JSON.stringify({ status: 'success' });
              resolve();
            });
          });
        }

        // Handle contact chat POST (send message) - return a mock event
        if (context.request.method === 'POST' && context.path.match(/^\/contact\/chat\/[^/]+\/$/)) {
          return new Promise((resolve) => {
            let body = '';
            context.req.on('data', chunk => { body += chunk.toString(); });
            context.req.on('end', () => {
              const data = JSON.parse(body);
              const event = {
                uuid: crypto.randomUUID(),
                type: 'msg_created',
                created_on: new Date().toISOString(),
                msg: {
                  urn: 'tel:+1234567890',
                  text: data.text || '',
                  channel: { uuid: 'ch-001', name: 'SMS Channel' },
                  attachments: data.attachments || []
                }
              };
              context.contentType = 'application/json';
              context.body = JSON.stringify({ event });
              resolve();
            });
          });
        }

        // Handle omnibox endpoint - combines groups and contacts
        if (context.request.method === 'GET' && context.path === '/contact/omnibox/') {
          const url = new URL(context.request.url, 'http://localhost');
          const search = (url.searchParams.get('search') || '').toLowerCase();
          const types = url.searchParams.get('types') || 'gc';
          const results = [];

          if (types.includes('g')) {
            const groupsPath = getDataFilePath('api', 'groups.json');
            if (fs.existsSync(groupsPath)) {
              const groups = JSON.parse(fs.readFileSync(groupsPath, 'utf-8')).results || [];
              for (const g of groups) {
                if (!search || g.name.toLowerCase().includes(search)) {
                  results.push({ id: g.uuid, name: g.name, type: 'group', count: g.count || 0 });
                }
              }
            }
          }

          if (types.includes('c')) {
            const contactsPath = getDataFilePath('api', 'contacts.json');
            if (fs.existsSync(contactsPath)) {
              const contacts = JSON.parse(fs.readFileSync(contactsPath, 'utf-8')).results || [];
              for (const c of contacts) {
                if (!search || c.name.toLowerCase().includes(search)) {
                  results.push({ id: c.uuid, name: c.name, type: 'contact' });
                }
              }
            }
          }

          context.contentType = 'application/json';
          context.body = JSON.stringify({ results, more: false, total: results.length, err: 'nil' });
          return;
        }

        // Handle minio file uploads for media
        if (context.request.method === 'POST' && context.path === '/api/v2/media.json') {
          return handleMinioUpload(context);
        }

        // Handle label creation
        if (context.request.method === 'POST' && context.path === '/api/v2/labels.json') {
          return handleDevEntityCreation('labels', context);
        }

        // Handle field creation
        if (context.request.method === 'POST' && context.path === '/api/v2/fields.json') {
          return handleDevEntityCreation('fields', context);
        }

        // Handle group creation
        if (context.request.method === 'POST' && context.path === '/api/v2/groups.json') {
          return handleDevEntityCreation('groups', context);
        }

        // Handle mock LLM translations
        if (
          context.request.method === 'POST' &&
          context.path.startsWith('/llm/translate/')
        ) {
          return new Promise((resolve) => {
            let body = '';
            context.req.on('data', (chunk) => {
              body += chunk.toString();
            });
            context.req.on('end', () => {
              let payload = {};
              try {
                payload = body ? JSON.parse(body) : {};
              } catch (error) {
                console.warn('Invalid LLM translate payload', error);
              }

              const sourceText =
                typeof payload.text === 'string' ? payload.text : '';
              const targetLang = payload.lang?.to || 'eng';
              const modelUuid = context.path.split('/')[3] || 'mock-model';

              const translated = sourceText
                ? `${sourceText} (${targetLang.toUpperCase()})`
                : `Translation for ${targetLang.toUpperCase()}`;

              context.contentType = 'application/json';
              context.status = 200;
              context.body = JSON.stringify({
                status: 'success',
                model: modelUuid,
                text: translated,
                result: translated,
                lang: {
                  from: payload.lang?.from || 'eng',
                  to: targetLang
                }
              });
              resolve();
            });
          });
        }
      }
    },
    {
      name: 'flows-directory-listing',
      serve(context) {
        // Handle directory listing for flows using a special API endpoint

        if (context.request.method === 'GET' && context.path === '/api/flows-list') {

          // Check dev flows directory first, then fall back to default
          let flowsDir = DEV_FLOWS_DIR;
          if (!fs.existsSync(flowsDir) || fs.readdirSync(flowsDir).filter(f => f.endsWith('.json')).length === 0) {
            flowsDir = path.resolve('./demo/data/flows');
          }
          
          if (fs.existsSync(flowsDir)) {
            const files = fs.readdirSync(flowsDir).filter(file => file.endsWith('.json'));
            console.log(`Listing ${files.length} flow files from ${flowsDir}...`);

            // Return JSON array of filenames
            context.contentType = 'application/json';
            context.body = JSON.stringify(files);
            return;
          }
        }
      }
    },
    {
      name: 'flow-files',
      serve(context) {
        if (context.request.method === 'POST' && context.path.startsWith('/flow/revisions/')) {
          return new Promise((resolve) => {
            let body = '';
            const parts = context.path.split('/');
            const uuid = parts[3];
            context.req.on('data', chunk => {
              body += chunk.toString();
            });
            context.req.on('end', () => {
              context.contentType = 'application/json';
              if (body) {
                const flowDefinition = JSON.parse(body);
                const flowPath = path.join(DEV_FLOWS_DIR, `${uuid}.json`);
                fs.writeFileSync(
                  flowPath,
                  JSON.stringify({ definition: flowDefinition }, null, 2)
                );
                
                // Generate metadata similar to production
                const metadata = generateFlowMetadata(flowDefinition);
                
                const response = {
                  status: 'success',
                  saved_on: new Date().toISOString(),
                  revision: {
                    id: Math.floor(Math.random() * 1000) + 1,
                    user: {
                      email: 'admin1@textit.com',
                      name: 'Adam McAdmin'
                    },
                    created_on: new Date().toISOString(),
                    version: flowDefinition.spec_version || '14.3.0',
                    revision: (flowDefinition.revision || 0) + 1
                  },
                  info: {
                    counts: metadata.counts,
                    dependencies: metadata.dependencies,
                    locals: metadata.locals,
                    results: metadata.results,
                    parent_refs: [],
                    issues: []
                  },
                  issues: [],
                  metadata: {
                    counts: metadata.counts,
                    dependencies: metadata.dependencies,
                    locals: metadata.locals,
                    results: metadata.results,
                    parent_refs: [],
                    issues: []
                  }
                };
                
                context.body = JSON.stringify(response);
                context.status = 200;
              } else {
                console.log(`No body received for flow ${uuid}.`);
                context.body = {
                  status: 'error',
                  message: `No body received for flow ${uuid}.`,
                };
                context.status = 400;
              }
              resolve();
            });
          });
        }

        if (context.request.method === 'GET' && context.path.startsWith('/flow/revisions/')) {
          const parts = context.path.split('/');
          const uuid = parts[3];
          context.contentType = 'application/json';
          
          // Read the flow definition from file (try dev directory first)
          const flowPath = getDataFilePath('flows', `${uuid}.json`);
          
          if (!fs.existsSync(flowPath)) {
            context.status = 404;
            context.body = JSON.stringify({ error: 'Flow not found' });
            return;
          }
          
          const flowFileContent = fs.readFileSync(flowPath, 'utf-8');
          
          const flowData = JSON.parse(flowFileContent);
          
          if (flowData.definition) {
            const info = generateFlowMetadata(flowData.definition);
            context.body = JSON.stringify({
              definition: flowData.definition,
              info: info
            });
          }
        }
      }
    }
  ],
};
