import { Client as MinioClient } from 'minio';
import busboy from 'busboy';
import { v4 as uuidv4 } from 'uuid';
import fs from 'fs';

/**
 * Generates FlowInfo dynamically from a FlowDefinition
 * This is a plain JavaScript version that can be imported by the web-dev-server
 */
export function generateFlowInfo(definition) {
  const dependencies = [];
  const results = [];
  const locals = [];

  // Track unique dependencies by key/uuid to avoid duplicates
  const dependencyMap = new Map();
  // Track results by name to collect node_uuids
  const resultMap = new Map();

  // Process all nodes
  definition.nodes.forEach((node) => {
    // Process actions
    node.actions.forEach((action) => {
      extractDependenciesFromAction(action, dependencyMap, resultMap, node.uuid);
    });

    // Process router
    if (node.router) {
      extractDependenciesFromRouter(
        node.router,
        dependencyMap,
        resultMap,
        node.uuid
      );
    }
  });

  // Extract unique dependencies from map
  dependencies.push(...Array.from(dependencyMap.values()));

  // Extract results from map
  results.push(...Array.from(resultMap.values()));

  // Count languages from localization
  const languageCount = Object.keys(definition.localization || {}).length;

  return {
    results,
    dependencies,
    counts: {
      nodes: definition.nodes.length,
      languages: languageCount
    },
    locals
  };
}

function extractDependenciesFromAction(action, dependencyMap, resultMap, nodeUuid) {
  switch (action.type) {
    case 'set_contact_field':
      if (action.field?.name) {
        const key = `field:${action.field.name}`;
        dependencyMap.set(key, {
          uuid: action.field.uuid || '',
          name: action.field.name,
          type: 'field'
        });
      }
      break;

    case 'call_webhook':
      if (action.url) {
        const key = `webhook:${action.url}`;
        dependencyMap.set(key, {
          uuid: action.uuid,
          name: action.url,
          type: 'webhook'
        });
      }
      break;

    case 'add_contact_groups':
      action.groups?.forEach((group) => {
        if (group.name) {
          const key = `group:${group.uuid || group.name}`;
          dependencyMap.set(key, {
            uuid: group.uuid || '',
            name: group.name,
            type: 'group'
          });
        }
      });
      break;

    case 'remove_contact_groups':
      action.groups?.forEach((group) => {
        if (group.name) {
          const key = `group:${group.uuid || group.name}`;
          dependencyMap.set(key, {
            uuid: group.uuid || '',
            name: group.name,
            type: 'group'
          });
        }
      });
      break;

    case 'set_contact_channel':
      if (action.channel?.name) {
        const key = `channel:${action.channel.uuid}`;
        dependencyMap.set(key, {
          uuid: action.channel.uuid,
          name: action.channel.name,
          type: 'channel'
        });
      }
      break;

    case 'send_broadcast':
      action.groups?.forEach((group) => {
        if (group.name) {
          const key = `group:${group.uuid || group.name}`;
          dependencyMap.set(key, {
            uuid: group.uuid || '',
            name: group.name,
            type: 'group'
          });
        }
      });
      action.contacts?.forEach((contact) => {
        if (contact.name) {
          const key = `contact:${contact.uuid}`;
          dependencyMap.set(key, {
            uuid: contact.uuid,
            name: contact.name,
            type: 'contact'
          });
        }
      });
      break;

    case 'enter_flow':
      if (action.flow?.name) {
        const key = `flow:${action.flow.uuid}`;
        dependencyMap.set(key, {
          uuid: action.flow.uuid,
          name: action.flow.name,
          type: 'flow'
        });
      }
      break;

    case 'start_session':
      if (action.flow?.name) {
        const key = `flow:${action.flow.uuid}`;
        dependencyMap.set(key, {
          uuid: action.flow.uuid,
          name: action.flow.name,
          type: 'flow'
        });
      }
      action.groups?.forEach((group) => {
        if (group.name) {
          const key = `group:${group.uuid || group.name}`;
          dependencyMap.set(key, {
            uuid: group.uuid || '',
            name: group.name,
            type: 'group'
          });
        }
      });
      break;

    case 'call_classifier':
      if (action.classifier?.name) {
        const key = `classifier:${action.classifier.uuid}`;
        dependencyMap.set(key, {
          uuid: action.classifier.uuid,
          name: action.classifier.name,
          type: 'classifier'
        });
      }
      break;

    case 'call_resthook':
      if (action.resthook) {
        const key = `resthook:${action.resthook}`;
        dependencyMap.set(key, {
          uuid: action.uuid,
          name: action.resthook,
          type: 'resthook'
        });
      }
      break;

    case 'call_llm':
      if (action.llm?.name) {
        const key = `llm:${action.llm.uuid}`;
        dependencyMap.set(key, {
          uuid: action.llm.uuid,
          name: action.llm.name,
          type: 'llm'
        });
      }
      break;

    case 'open_ticket':
      if (action.assignee?.name) {
        const key = `user:${action.assignee.uuid}`;
        dependencyMap.set(key, {
          uuid: action.assignee.uuid,
          name: action.assignee.name,
          type: 'user'
        });
      }
      if (action.topic?.name) {
        const key = `topic:${action.topic.uuid}`;
        dependencyMap.set(key, {
          uuid: action.topic.uuid,
          name: action.topic.name,
          type: 'topic'
        });
      }
      break;

    case 'request_optin':
      if (action.optin?.name) {
        const key = `optin:${action.optin.uuid}`;
        dependencyMap.set(key, {
          uuid: action.optin.uuid,
          name: action.optin.name,
          type: 'optin'
        });
      }
      break;

    case 'add_input_labels':
      action.labels?.forEach((label) => {
        if (label.name) {
          const key = `label:${label.uuid}`;
          dependencyMap.set(key, {
            uuid: label.uuid,
            name: label.name,
            type: 'label'
          });
        }
      });
      break;

    case 'send_msg':
      if (action.template?.name) {
        const key = `template:${action.template.uuid}`;
        dependencyMap.set(key, {
          uuid: action.template.uuid,
          name: action.template.name,
          type: 'template'
        });
      }
      break;

    case 'set_run_result':
      if (action.name) {
        const existingResult = resultMap.get(action.name);
        if (existingResult) {
          // Add this node to existing result if not already present
          if (!existingResult.node_uuids.includes(nodeUuid)) {
            existingResult.node_uuids.push(nodeUuid);
          }
          // Add category if specified and not already present
          if (action.category && !existingResult.categories.includes(action.category)) {
            existingResult.categories.push(action.category);
          }
        } else {
          // Create new result
          const categories = action.category ? [action.category] : ['All Responses'];
          resultMap.set(action.name, {
            key: action.name.toLowerCase().replace(/[^a-z0-9_]/g, '_'),
            name: action.name,
            categories: categories,
            node_uuids: [nodeUuid]
          });
        }
      }
      break;
  }
}

function extractDependenciesFromRouter(router, dependencyMap, resultMap, nodeUuid) {
  // Extract result information
  if (router.result_name && router.categories) {
    const existingResult = resultMap.get(router.result_name);
    if (existingResult) {
      // Add this node to existing result if not already present
      if (!existingResult.node_uuids.includes(nodeUuid)) {
        existingResult.node_uuids.push(nodeUuid);
      }
    } else {
      // Create new result
      const categories = router.categories.length > 0 
        ? router.categories.map((cat) => cat.name)
        : ['All Responses'];
      
      const result = {
        key: router.result_name.toLowerCase().replace(/[^a-z0-9_]/g, '_'),
        name: router.result_name,
        categories: categories,
        node_uuids: [nodeUuid]
      };
      resultMap.set(router.result_name, result);
    }
  }

  // Process cases for potential dependencies
  router.cases?.forEach((case_) => {
    if (case_.type === 'has_group' && case_.arguments?.length >= 2) {
      // Group dependency from split_by_groups
      const groupUuid = case_.arguments[0];
      const groupName = case_.arguments[1];
      if (groupName) {
        const key = `group:${groupUuid}`;
        dependencyMap.set(key, {
          uuid: groupUuid,
          name: groupName,
          type: 'group'
        });
      }
    }
  });
}

// Initialize Minio client for file uploads
export const minioClient = new MinioClient({
  endPoint: 'minio',
  port: 9000,
  useSSL: false,
  accessKey: 'root',
  secretKey: 'tembatemba'
});

// Helper function to generate the correct public URL for uploaded files
export function getPublicUrl(bucketName, fileName, request) {
  // Check if request is coming from localhost/127.0.0.1 (host machine)
  // or from within docker network
  const host = request.headers.host;
  const userAgent = request.headers['user-agent'] || '';
  
  // If accessing from host machine (localhost:3010), use localhost for minio too
  if (host && host.startsWith('localhost:')) {
    return `http://localhost:9000/${bucketName}/${fileName}`;
  }
  
  // If accessing from docker network, use internal hostname
  return `http://minio:9000/${bucketName}/${fileName}`;
}

// Handle minio file uploads for media
export function handleMinioUpload(context) {
  return new Promise((resolve) => {
    try {
      const bb = busboy({ headers: context.request.headers });
      let fileInfo = null;
      let fileBuffer = null;
      
      bb.on('file', (name, file, info) => {
        fileInfo = info;
        const chunks = [];
        
        file.on('data', (chunk) => {
          chunks.push(chunk);
        });
        
        file.on('end', () => {
          fileBuffer = Buffer.concat(chunks);
        });
      });
      
      bb.on('finish', async () => {
        if (!fileBuffer || !fileInfo) {
          context.status = 400;
          context.body = JSON.stringify({ error: 'No file uploaded' });
          resolve();
          return;
        }
        
        try {
          const fileUuid = uuidv4();
          const fileName = `${fileUuid}-${fileInfo.filename}`;
          const bucketName = 'temba-attachments';
          
          // Upload to minio
          await minioClient.putObject(bucketName, fileName, fileBuffer, {
            'Content-Type': fileInfo.mimeType
          });
          
          // Return success response with appropriate URL based on request source
          const publicUrl = getPublicUrl(bucketName, fileName, context.request);
          
          // Debug logging
          console.log('🔧 Upload Debug:', {
            fileUuid,
            fileName,
            bucketName,
            publicUrl,
            contentType: fileInfo.mimeType,
            host: context.request.headers.host
          });
          
          context.contentType = 'application/json';
          context.body = JSON.stringify({
            uuid: fileUuid,
            content_type: fileInfo.mimeType,
            url: publicUrl,
            filename: fileInfo.filename,
            size: fileBuffer.length
          });
          
        } catch (uploadError) {
          console.error('Minio upload error:', uploadError);
          context.status = 500;
          context.body = JSON.stringify({ 
            error: 'Upload failed',
            details: uploadError.message 
          });
        }
        
        resolve();
      });
      
      context.req.pipe(bb);
      
    } catch (error) {
      console.error('File upload processing error:', error);
      context.status = 500;
      context.body = JSON.stringify({ 
        error: 'Upload processing failed',
        details: error.message 
      });
      resolve();
    }
  });
}

// Entity creation configurations
const ENTITY_CONFIGS = {
  labels: {
    filePath: './static/api/labels.json',
    createEntity: (name) => ({
      uuid: uuidv4(),
      name: name.trim(),
      count: 0
    }),
    nameField: 'name',
    entityType: 'Label'
  },
  fields: {
    filePath: './static/api/fields.json',
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
    uniqueField: 'key', // check uniqueness by key for fields
    entityType: 'Field'
  },
  groups: {
    filePath: './static/api/groups.json',
    createEntity: (name) => ({
      uuid: uuidv4(),
      name: name.trim(),
      query: null,
      status: 'ready',
      count: 0
    }),
    nameField: 'name',
    entityType: 'Group'
  }
};

// Generic entity creation handler for labels, fields, and groups
export function handleEntityCreation(entityType, context) {
  const config = ENTITY_CONFIGS[entityType];
  
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
        
        // Read existing data file
        let entityData;
        
        try {
          entityData = JSON.parse(fs.readFileSync(config.filePath, 'utf-8'));
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
        
        // Write back to file
        fs.writeFileSync(config.filePath, JSON.stringify(entityData, null, 2));
        
        // Return the new entity
        context.contentType = 'application/json';
        context.body = JSON.stringify(newEntity);
        
        console.log(`📝 ${config.entityType} created:`, newEntity);
        
      } catch (error) {
        console.error(`${config.entityType} creation error:`, error);
        context.status = 500;
        context.body = JSON.stringify({ 
          error: `${config.entityType} creation failed`,
          details: error.message 
        });
      }
      
      resolve();
    });
  });
}

