import merge from 'deepmerge';
import config from './rollup.components.mjs';

const webchatConfig = merge(config, {
    input: 'temba-webchat.ts',
    output: {
        file: 'dist/temba-webchat.js',
    },
});

export default webchatConfig;