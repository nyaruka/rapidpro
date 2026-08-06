# Node Configuration Tests

This directory contains tests for node configurations using the `NodeHelper` testing framework.

## Overview

Similar to how the `ActionHelper` provides a uniform testing strategy for action configurations, the `NodeHelper` class provides a structured approach to testing node configurations. It handles:

1. **Rendering Tests**: Verifies nodes render correctly in the flow editor
2. **Editor Tests**: Verifies the node editor opens and displays correctly
3. **Round-trip Conversion**: Tests form data conversion for nodes with `toFormData`/`fromFormData`
4. **Screenshot Testing**: Captures visual screenshots for regression testing

## Test Structure

Each node test file follows this pattern:

```typescript
import { expect } from '@open-wc/testing';
import { node_config } from '../../src/flow/nodes/node_config';
import { Node } from '../../src/store/flow-definition';
import { NodeTest } from '../NodeHelper';

describe('node_config node config', () => {
  const helper = new NodeTest(node_config, 'node_config');

  describe('basic properties', () => {
    helper.testBasicProperties();

    // Additional property tests...
  });

  describe('node scenarios', () => {
    helper.testNode(nodeData, nodeUI, 'test-name');

    // More scenarios...
  });

  // Optional: data transformation tests for nodes with form configuration
  describe('data transformation', () => {
    // Round-trip conversion tests...
  });
});
```

## Node Types Covered

### Simple Nodes

- `wait_for_digits`: Basic node with no form configuration
- `wait_for_audio`, `wait_for_image`, etc.: Similar wait nodes

### Form-Configured Nodes

- `wait_for_response`: Node with form fields and data transformation
- `split_by_llm_categorize`: Complex node with form configuration

### Router-Based Nodes

- `split_by_random`: Random distribution node
- Other split nodes with router configurations

## Screenshots

Screenshots are automatically generated and stored in:

- `screenshots/nodes/{node_name}/render/{test_name}.png` - Flow editor rendering
- `screenshots/nodes/{node_name}/editor/{test_name}.png` - Node editor dialog

## Running Tests

```bash
# Run all node tests
bun run test test/nodes/*.test.ts --no-watch

# Run specific node test
bun run test test/nodes/wait_for_response.test.ts --no-watch
```
