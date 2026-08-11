#!/usr/bin/env node

import { execSync } from 'child_process';
import { performance } from 'perf_hooks';

// Parse command line arguments
const args = process.argv.slice(2);
let testFile = '';
let maxRuns = 10;

// Parse arguments
for (let i = 0; i < args.length; i++) {
  const arg = args[i];

  if (arg.startsWith('--runs=')) {
    maxRuns = parseInt(arg.split('=')[1]);
    if (isNaN(maxRuns) || maxRuns <= 0) {
      console.error('❌ Invalid runs value. Must be a positive integer.');
      process.exit(1);
    }
  } else if (arg.startsWith('test/') && arg.endsWith('.test.ts')) {
    testFile = arg;
  } else if (!arg.startsWith('--')) {
    testFile = arg;
  }
}

// Validate test file
if (!testFile) {
  console.error('❌ Usage: bun run stress-test <test-file> [--runs=N]');
  console.error(
    '   Example: bun run stress-test test/temba-webchat.test.ts --runs=100'
  );
  process.exit(1);
}

if (!testFile.startsWith('test/') || !testFile.endsWith('.test.ts')) {
  console.error(
    '❌ Test file must be in the test/ directory and end with .test.ts'
  );
  process.exit(1);
}

console.log(`🧪 Stress testing: ${testFile}`);
console.log(`🔄 Running up to ${maxRuns} times (or until failure)`);
console.log('');

let run = 1;
let totalTime = 0;
const runTimes = [];
let failures = 0;

const startTime = performance.now();

try {
  while (run <= maxRuns) {
    const runStartTime = performance.now();

    process.stdout.write(`Run ${run.toString().padStart(3)}/${maxRuns}: `);

    try {
      // Run the test with minimal output
      const result = execSync(`bun run test ${testFile}`, {
        encoding: 'utf-8',
        stdio: ['pipe', 'pipe', 'pipe']
      });

      const runEndTime = performance.now();
      const runTime = runEndTime - runStartTime;
      runTimes.push(runTime);
      totalTime += runTime;

      // Check if the test actually passed by looking for success indicators
      if (result.includes('all tests passed') || result.includes('0 failed')) {
        console.log(`✅ PASS (${(runTime / 1000).toFixed(2)}s)`);
      } else {
        console.log(`❌ FAIL (unexpected output)`);
        console.log('Output:', result);
        failures++;
        break;
      }
    } catch (error) {
      const runEndTime = performance.now();
      const runTime = runEndTime - runStartTime;

      console.log(`❌ FAIL (${(runTime / 1000).toFixed(2)}s)`);
      console.log('');
      console.log('💥 Test failed on run', run);
      console.log('');
      console.log('Error output:');
      console.log(error.stdout || error.message);
      if (error.stderr) {
        console.log('');
        console.log('Error details:');
        console.log(error.stderr);
      }
      failures++;
      break;
    }

    run++;
  }
} catch (error) {
  console.log('');
  console.log('💥 Unexpected error:', error.message);
  process.exit(1);
}

const endTime = performance.now();
const totalTestTime = endTime - startTime;

console.log('');
console.log('📊 Results Summary');
console.log('==================');
console.log(`Test file: ${testFile}`);
console.log(`Completed runs: ${run - 1}/${maxRuns}`);
console.log(`Failures: ${failures}`);
console.log(
  `Success rate: ${(((run - 1 - failures) / (run - 1)) * 100).toFixed(1)}%`
);
console.log('');

if (runTimes.length > 0) {
  const avgTime = runTimes.reduce((a, b) => a + b, 0) / runTimes.length;
  const minTime = Math.min(...runTimes);
  const maxTime = Math.max(...runTimes);

  console.log('⏱️  Timing Statistics');
  console.log('=====================');
  console.log(`Total time: ${(totalTestTime / 1000).toFixed(2)}s`);
  console.log(`Average run time: ${(avgTime / 1000).toFixed(2)}s`);
  console.log(`Fastest run: ${(minTime / 1000).toFixed(2)}s`);
  console.log(`Slowest run: ${(maxTime / 1000).toFixed(2)}s`);
  console.log('');
}

if (failures === 0) {
  console.log(`🎉 All ${run - 1} runs passed successfully!`);
  process.exit(0);
} else {
  console.log(`💥 Test failed after ${run - 1} runs`);
  process.exit(1);
}
