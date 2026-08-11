import resolve from '@rollup/plugin-node-resolve';
import commonjs from '@rollup/plugin-commonjs';
import replace from '@rollup/plugin-replace'
import typescript from '@rollup/plugin-typescript';
import terser from '@rollup/plugin-terser';
import svg from 'rollup-plugin-svg-import';
import copy from 'rollup-plugin-copy';
import fs from 'fs';

const packageJson = JSON.parse(
    fs.readFileSync(new URL('./package.json', import.meta.url), 'utf-8')
);
const TEMBA_COMPONENTS_VERSION = packageJson.version;


export default {
    input: 'temba-components.ts',
    output: {
        file: 'dist/temba-components.js',

        // Immediately Invoked Function Expression
        format: 'iife',

        name: 'TembaComponents',
        sourcemap: true
    },
    onwarn: function(warning, handler) {
        // Skip certain warnings
        if ( warning.code === 'THIS_IS_UNDEFINED' ) { return; }


        if (warning.code === 'CIRCULAR_DEPENDENCY') {
            
            // luxon has a ton of circular dependencies they don't care about
            if(warning.message.includes('luxon')) {
                return;
            }

            // same with lit-localize
            if(warning.message.includes('lit-localize')) {
                return;
            }
        }
        handler( warning );
    },
    plugins: [
        replace({
            preventAssignment: true,
            'process.env.NODE_ENV': JSON.stringify('development'),
            '__TEMBA_COMPONENTS_VERSION__': JSON.stringify(TEMBA_COMPONENTS_VERSION)
          }),

        // inline our icons
        svg({ stringify: true }),

        // resolve external modules
        resolve(),

        // convert commonjs modules to es6
        commonjs({ include: 'node_modules/**' }),

        // compile our typescript
        typescript({ sourceMap: true, inlineSources: true, outDir: 'dist' }),

        copy({
            targets: [
                { src: 'static/svg/index.svg', dest: 'dist/static/svg/' },
                { src: 'static/img', dest: 'dist/static/' },
                { src: 'out-tsc/src/locales', dest: 'dist/' },
            ],
            hook: 'writeBundle',
        }),

        // minify
        terser()
    ]
};
