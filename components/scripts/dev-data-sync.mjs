#!/usr/bin/env node

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');

// Development data directory outside project structure
const DEV_DATA_DIR = '/tmp/temba-dev-data';
const DEV_FLOWS_DIR = path.join(DEV_DATA_DIR, 'flows');
const DEV_API_DIR = path.join(DEV_DATA_DIR, 'api');

// Project directories
const PROJECT_FLOWS_DIR = path.join(projectRoot, 'demo/data/flows');
const PROJECT_API_DIR = path.join(projectRoot, 'static/api');

function copyChangesToProject() {
  console.log('📁 Copying development changes back to project...');
  
  let flowsCopied = 0;
  let apiFilesCopied = 0;

  // Copy flows
  if (fs.existsSync(DEV_FLOWS_DIR)) {
    const devFlowFiles = fs.readdirSync(DEV_FLOWS_DIR).filter(f => f.endsWith('.json'));
    
    // Ensure project flows directory exists
    if (!fs.existsSync(PROJECT_FLOWS_DIR)) {
      fs.mkdirSync(PROJECT_FLOWS_DIR, { recursive: true });
    }

    devFlowFiles.forEach(file => {
      const devFile = path.join(DEV_FLOWS_DIR, file);
      const projectFile = path.join(PROJECT_FLOWS_DIR, file);
      
      fs.copyFileSync(devFile, projectFile);
      flowsCopied++;
      console.log(`  ✅ Copied flow: ${file}`);
    });
  }

  // Copy API files
  if (fs.existsSync(DEV_API_DIR)) {
    const devApiFiles = fs.readdirSync(DEV_API_DIR).filter(f => f.endsWith('.json'));
    
    // Ensure project API directory exists
    if (!fs.existsSync(PROJECT_API_DIR)) {
      fs.mkdirSync(PROJECT_API_DIR, { recursive: true });
    }

    devApiFiles.forEach(file => {
      const devFile = path.join(DEV_API_DIR, file);
      const projectFile = path.join(PROJECT_API_DIR, file);
      
      fs.copyFileSync(devFile, projectFile);
      apiFilesCopied++;
      console.log(`  ✅ Copied API file: ${file}`);
    });
  }

  console.log(`\n🎉 Copy complete! ${flowsCopied} flows and ${apiFilesCopied} API files copied to project.`);
  console.log('💡 Don\'t forget to commit these changes if you want to keep them!');
}

function resetDevData() {
  console.log('🗑️  Wiping development data and recreating from defaults...');
  
  // Remove existing dev data
  if (fs.existsSync(DEV_DATA_DIR)) {
    fs.rmSync(DEV_DATA_DIR, { recursive: true, force: true });
    console.log('  🗑️  Removed existing development data');
  }

  // Recreate directories
  fs.mkdirSync(DEV_DATA_DIR, { recursive: true });
  fs.mkdirSync(DEV_FLOWS_DIR, { recursive: true });
  fs.mkdirSync(DEV_API_DIR, { recursive: true });

  let flowsCopied = 0;
  let apiFilesCopied = 0;

  // Copy default flows
  if (fs.existsSync(PROJECT_FLOWS_DIR)) {
    const defaultFlowFiles = fs.readdirSync(PROJECT_FLOWS_DIR).filter(f => f.endsWith('.json'));
    defaultFlowFiles.forEach(file => {
      fs.copyFileSync(
        path.join(PROJECT_FLOWS_DIR, file),
        path.join(DEV_FLOWS_DIR, file)
      );
      flowsCopied++;
      console.log(`  ✅ Restored default flow: ${file}`);
    });
  }

  // Copy default API files
  if (fs.existsSync(PROJECT_API_DIR)) {
    const defaultApiFiles = fs.readdirSync(PROJECT_API_DIR).filter(f => f.endsWith('.json'));
    defaultApiFiles.forEach(file => {
      fs.copyFileSync(
        path.join(PROJECT_API_DIR, file),
        path.join(DEV_API_DIR, file)
      );
      apiFilesCopied++;
      console.log(`  ✅ Restored default API file: ${file}`);
    });
  }

  console.log(`\n🎉 Reset complete! ${flowsCopied} flows and ${apiFilesCopied} API files restored from defaults.`);
}

function showStatus() {
  console.log('📊 Development Data Status');
  console.log('=' .repeat(50));
  
  if (!fs.existsSync(DEV_DATA_DIR)) {
    console.log('❌ No development data directory found');
    console.log('💡 Run the dev server to initialize, or use "bun run dev-data:reset"');
    return;
  }

  // Check flows
  const devFlowFiles = fs.existsSync(DEV_FLOWS_DIR) 
    ? fs.readdirSync(DEV_FLOWS_DIR).filter(f => f.endsWith('.json'))
    : [];
  const projectFlowFiles = fs.existsSync(PROJECT_FLOWS_DIR)
    ? fs.readdirSync(PROJECT_FLOWS_DIR).filter(f => f.endsWith('.json'))
    : [];

  console.log(`\n📁 Flows:`);
  console.log(`  Dev directory: ${devFlowFiles.length} files`);
  console.log(`  Project directory: ${projectFlowFiles.length} files`);

  // Check API files
  const devApiFiles = fs.existsSync(DEV_API_DIR)
    ? fs.readdirSync(DEV_API_DIR).filter(f => f.endsWith('.json'))
    : [];
  const projectApiFiles = fs.existsSync(PROJECT_API_DIR)
    ? fs.readdirSync(PROJECT_API_DIR).filter(f => f.endsWith('.json'))
    : [];

  console.log(`\n📄 API Files:`);
  console.log(`  Dev directory: ${devApiFiles.length} files`);
  console.log(`  Project directory: ${projectApiFiles.length} files`);

  console.log(`\n📍 Locations:`);
  console.log(`  Dev data: ${DEV_DATA_DIR}`);
  console.log(`  Project flows: ${PROJECT_FLOWS_DIR}`);
  console.log(`  Project API: ${PROJECT_API_DIR}`);
}

// Parse command line arguments
const command = process.argv[2];

switch (command) {
  case 'copy':
  case 'sync':
    copyChangesToProject();
    break;
  case 'reset':
  case 'wipe':
    resetDevData();
    break;
  case 'status':
    showStatus();
    break;
  default:
    console.log('📋 Development Data Management');
    console.log('=' .repeat(40));
    console.log('');
    console.log('Available commands:');
    console.log('  copy/sync   - Copy dev changes back to project');
    console.log('  reset/wipe  - Wipe dev data and restore defaults');
    console.log('  status      - Show current status');
    console.log('');
    console.log('Usage: bun run dev-data:copy');
    console.log('       bun run dev-data:reset');
    console.log('       bun run dev-data:status');
    process.exit(1);
}
