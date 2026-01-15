const esbuild = require('esbuild');
const fs = require('fs');

const isWatch = process.argv.includes('--watch');

// Plugin to replace React imports with window globals
const reactGlobalPlugin = {
  name: 'react-global',
  setup(build) {
    build.onResolve({ filter: /^react$/ }, args => {
      return { path: args.path, namespace: 'react-global' };
    });
    build.onResolve({ filter: /^react-dom$/ }, args => {
      return { path: args.path, namespace: 'react-global' };
    });
    build.onResolve({ filter: /^react-dom\/client$/ }, args => {
      return { path: args.path, namespace: 'react-global' };
    });
    
    build.onLoad({ filter: /.*/, namespace: 'react-global' }, args => {
      if (args.path === 'react') {
        return {
          contents: 'module.exports = window.React;',
          loader: 'js',
        };
      }
      if (args.path === 'react-dom') {
        return {
          contents: 'module.exports = window.ReactDOM;',
          loader: 'js',
        };
      }
      if (args.path === 'react-dom/client') {
        return {
          contents: 'module.exports = window.ReactDOM;',
          loader: 'js',
        };
      }
    });
  },
};

const config = {
  entryPoints: ['src/app.tsx'],
  bundle: true,
  outfile: 'static/app.js',
  format: 'iife',
  globalName: 'TodoApp',
  plugins: [reactGlobalPlugin],
  define: {
    'process.env.NODE_ENV': '"production"'
  },
  jsx: 'transform',
  jsxFactory: 'React.createElement',
  jsxFragment: 'React.Fragment',
};

if (isWatch) {
  esbuild.context(config).then(ctx => {
    ctx.watch();
    console.log('Watching...');
  });
} else {
  esbuild.build(config).then(() => {
    console.log('Build complete');
  }).catch(() => process.exit(1));
}
