# temba-components

[![Coverage](https://nyaruka.github.io/temba-components/coverage-badge.svg)](https://nyaruka.github.io/temba-components/)

Coverage reports are automatically generated and deployed to [GitHub Pages](https://nyaruka.github.io/temba-components/) from the `coverage` branch after each merge to main.

temba-components is a suite of ui widgets used by various RapidPro projects.

Some of the components:

- `<temba-select/>` Advanced select widget with support for remote fetching and filtering. Also supports multi selection with the ability to enter expressions.

- `<temba-completion/>` Completion widget for completing RP-style expressions
- `<temba-textinput/>` - Standard text field with baked in support for date picking
- `<temba-charcount/>` - SMS segment counter attachable to elements for monitoring
- `<temba-store/>` - In page cache for RP core data types
- `<temba-options/>` - Generic option list with configurable rendering, remote list paging, and keyboard support. Used by temba-select, temba-completion, and temba-list
- `<temba-list/>` - Block rendered option list
- `<temba-dialog/>` - Basic modal
- `<temba-modax/>` - Fancier modal that fetches and submits html rendered forms and is triggered by a slot element
- .. and many more

## Install

We use [bun](https://bun.com), so you'll want to install with that if you care about our lock file.

```bash
% bun install
```

## Demo

To view the interactive demo, use start.

```bash
% bun run start
```

## Testing

All tests live under [/test](test). When running tests, some tests capture screenshots for pixel
comparision under [/screenshots](screenshots/truth). Running tests requires that you have Chromium
installed.

```bash
% bun run test
```

## Usage

Simply include the built file as a module and you should be off to the races!

```html
<html>
  <head>
    <script type="module">
      import '../out-tsc/temba-components.js';
    </script>
  </head>
  <body>
    <temba-select name="color">
      <temba-option name="Red" value="r"></temba-option>
      <temba-option name="Green" value="g"></temba-option>
      <temba-option name="Blue" value="b"></temba-option>
    </temba-select>
  </body>
</html>
```

To interactively work with components whilst embedded in another project, it can easily be done with a couple nginx rules.

```
  location ~ /out-tsc/(.*) {
      proxy_pass http://localhost:3010/out-tsc/$1;
  }

  location ~ /node_modules/(.*) {
      proxy_pass http://localhost:3010/node_modules/$1;
  }
```
