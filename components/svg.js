#!/usr/bin/env node

const argv = require('yargs').usage('Usage: $0 [options]').argv;

const svgstore = require('svgstore');
const htmlclean = require('htmlclean');
const sh = require('shelljs');
const fs = require('fs');
const path = require('path');
const SVGFixer = require('oslllo-svg-fixer');
const { digestSync } = require('fprint');

const cwd = process.cwd();

const PACK_DIR = cwd + '/static/svg/packs';
const USED_DIR = cwd + '/static/svg/work/used';
const TRACED_DIR = cwd + '/static/svg/work/traced';
const USAGE_REGEX = /'(.*)'/;

const sprites = svgstore();

function processFileWithRegex(filePath, regexPattern) {
  try {
    const data = fs.readFileSync(filePath, 'utf-8');
    const lines = data.split(/\r?\n/);
    const regex = new RegExp(regexPattern, 'g');
    let matches = [];

    lines.forEach((line) => {
      let match;
      while ((match = regex.exec(line)) !== null) {
        matches.push(match[1]);
      }
    });

    return matches;
  } catch (err) {
    console.error('Error reading the file:', err);
  }
}

// Convert matches array to an object with keys being the matches and values being true
function matchesToObject(matches) {
  const result = {};
  matches.forEach((match) => {
    result[match] = true;
  });
  return result;
}

function copyFilesInDict(sourceDir, targetDir, matchDict) {
  try {
    const files = fs.readdirSync(sourceDir);
    files.forEach((file) => {
      const fileNameWithoutExtension = path.parse(file).name;
      if (matchDict[fileNameWithoutExtension]) {
        const sourcePath = path.join(sourceDir, file);
        const targetPath = path.join(targetDir, file);

        try {
          fs.copyFileSync(sourcePath, targetPath);
          // console.log(`Copied file '${file}' to the target directory.`);
        } catch (err) {
          console.error(`Error copying file '${file}':`, err);
        }
      }
    });
  } catch (err) {
    console.error('Error reading the source directory:', err);
  }
}

function modifyFileContent(filePath, regexPattern, groupNumber, replacement) {
  try {
    const data = fs.readFileSync(filePath, 'utf-8');
    const regex = new RegExp(regexPattern, 'g');

    const modifiedData = data.replace(regex, (match, ...groups) => {
      if (groups[groupNumber - 1] !== undefined) {
        return match.replace(groups[groupNumber - 1], replacement);
      }
      return match;
    });

    fs.writeFileSync(filePath, modifiedData, 'utf-8');
    console.log('File content modified successfully');
  } catch (err) {
    console.error('Error modifying the file content:', err);
  }
}

async function main() {
  const OUTPUT_FILE_NAME = argv.output || cwd + '/static/svg/index.svg';
  const USAGE_FILE = argv.usage || './src/Icons.ts';

  let packs = sh.ls(PACK_DIR);
  packs.sort();

  // create our work directory
  [USED_DIR, TRACED_DIR].forEach((dir) => {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  });

  const matches = processFileWithRegex(USAGE_FILE, USAGE_REGEX);
  const ids = matchesToObject(matches);

  // copy any icons from our packs that are used
  packs.forEach((pack) => {
    copyFilesInDict(`${PACK_DIR}/${pack}`, USED_DIR, ids);
  });

  // trace our strokes so we can rely on consistent fills
  var options = {
    showProgressBar: true,
    throwIfDestinationDoesNotExist: false,
    traceResolution: argv.resolution || 600
  };

  await SVGFixer(USED_DIR, TRACED_DIR, options).fix();

  const files = sh.find(TRACED_DIR).filter((file) => file.match(/\.svg$/));

  files.forEach((file) => {
    const id = path.basename(file, '.svg');
    const contents = fs.readFileSync(file, 'utf8');
    sprites.add(id, contents);
  });

  let output = htmlclean(
    sprites.toString({ cleanDefs: true, cleanSymbols: true, renameDefs: true })
  );
  output = output.replaceAll(/fill="black"/g, `fill="currentColor"`);

  fs.writeFileSync(OUTPUT_FILE_NAME, output);
  console.info('Merged %s files into %s', files.length, OUTPUT_FILE_NAME);

  const stream = fs.createReadStream(OUTPUT_FILE_NAME);
  const file = fs.readFileSync(OUTPUT_FILE_NAME);
  const md5 = digestSync(file, 'md5');
  modifyFileContent(
    USAGE_FILE,
    "export const SVG_FINGERPRINT = '(.*)';",
    1,
    md5
  );
}

main();
