#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const COVERAGE_THRESHOLD = 80;
const LCOV_FILE = path.join(__dirname, 'coverage', 'lcov.info');

function parseLcovInfo(lcovPath) {
  if (!fs.existsSync(lcovPath)) {
    console.error('❌ Coverage file not found:', lcovPath);
    process.exit(1);
  }

  const lcovData = fs.readFileSync(lcovPath, 'utf8');
  const lines = lcovData.split('\n');

  let totalLines = 0;
  let hitLines = 0;
  let totalFunctions = 0;
  let hitFunctions = 0;
  let totalBranches = 0;
  let hitBranches = 0;

  lines.forEach((line) => {
    if (line.startsWith('LF:')) {
      totalLines += parseInt(line.substring(3));
    } else if (line.startsWith('LH:')) {
      hitLines += parseInt(line.substring(3));
    } else if (line.startsWith('FNF:')) {
      totalFunctions += parseInt(line.substring(4));
    } else if (line.startsWith('FNH:')) {
      hitFunctions += parseInt(line.substring(4));
    } else if (line.startsWith('BRF:')) {
      totalBranches += parseInt(line.substring(4));
    } else if (line.startsWith('BRH:')) {
      hitBranches += parseInt(line.substring(4));
    }
  });

  return {
    lines: {
      total: totalLines,
      hit: hitLines,
      percentage: totalLines > 0 ? (hitLines / totalLines) * 100 : 0
    },
    functions: {
      total: totalFunctions,
      hit: hitFunctions,
      percentage: totalFunctions > 0 ? (hitFunctions / totalFunctions) * 100 : 0
    },
    branches: {
      total: totalBranches,
      hit: hitBranches,
      percentage: totalBranches > 0 ? (hitBranches / totalBranches) * 100 : 0
    }
  };
}

function displayCoverageReport(coverage) {
  console.log('\n📊 Coverage Report');
  console.log('==================');
  console.log(
    `Lines:      ${coverage.lines.hit}/${
      coverage.lines.total
    } (${coverage.lines.percentage.toFixed(2)}%)`
  );
  console.log(
    `Functions:  ${coverage.functions.hit}/${
      coverage.functions.total
    } (${coverage.functions.percentage.toFixed(2)}%)`
  );
  console.log(
    `Branches:   ${coverage.branches.hit}/${
      coverage.branches.total
    } (${coverage.branches.percentage.toFixed(2)}%)`
  );
  console.log('==================');

  // Use statement coverage (lines) as the metric for build success/failure
  const statementCoverage = coverage.lines.percentage;

  if (statementCoverage >= COVERAGE_THRESHOLD) {
    console.log(
      `✅ Statement Coverage: ${statementCoverage.toFixed(
        2
      )}% (above ${COVERAGE_THRESHOLD}% threshold)`
    );
  } else {
    console.log(
      `❌ Statement Coverage: ${statementCoverage.toFixed(
        2
      )}% (below ${COVERAGE_THRESHOLD}% threshold)`
    );
  }

  return statementCoverage;
}

function main() {
  try {
    const coverage = parseLcovInfo(LCOV_FILE);
    const statementCoverage = displayCoverageReport(coverage);

    if (statementCoverage < COVERAGE_THRESHOLD) {
      console.log(
        `\n💥 Build failed: Statement coverage ${statementCoverage.toFixed(
          2
        )}% is below the required ${COVERAGE_THRESHOLD}% threshold.`
      );
      console.log(
        `📈 Increase coverage by ${(
          COVERAGE_THRESHOLD - statementCoverage
        ).toFixed(2)}% to pass the build.`
      );
      process.exit(1);
    } else {
      console.log(
        `\n🎉 Build passed: Statement coverage meets the ${COVERAGE_THRESHOLD}% threshold!`
      );
      process.exit(0);
    }
  } catch (error) {
    console.error('❌ Error checking coverage:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { parseLcovInfo, displayCoverageReport, COVERAGE_THRESHOLD };
