# Test Suite Optimization Guide

This document outlines strategies for running tests efficiently and optimizing developer feedback cycles.

## Quick Test Commands

### Fast Test Execution
```bash
# Run tests in fast mode (skips network idle waits)
bun run test:fast

# Watch mode for iterative development
bun run test:watch
```

### Coverage and Validation
```bash
# Full test suite with coverage
bun run test --coverage

# Complete validation (formatting, build, tests)
bun run validate
```

## Test Categories

### Unit Tests
- Fast execution (< 1s per test)
- No visual screenshots
- Focus on component logic and behavior

### Visual Regression Tests
- Screenshot comparisons
- Slower execution due to image processing
- Use `assertScreenshot()` helper

## Performance Optimizations

### 1. Timeout Configurations
- Default test timeout: 5s (reduced from 10s)
- Concurrency: 4 parallel browsers
- Network idle wait: 100ms + 1s timeout (when enabled)

### 2. Fast Mode Features
- Pass `--fast` flag to skip network idle waits
- Reduced screenshot comparison timeouts
- Optimized clock tick intervals in fake timer tests

### 3. Helper Function Optimizations
- `openSelect()`: 25ms wait (reduced from 100ms)
- `openAndClick()`: 25ms clock tick (reduced from 50ms)
- Toast test timeouts: 75ms (reduced from 150ms)

### 4. Development Best Practices

#### Use Minimal Waits
```typescript
// Good: Use updateComplete when possible
await component.updateComplete;

// Acceptable: Short timeouts when necessary
await new Promise(resolve => setTimeout(resolve, 25));

// Avoid: Long arbitrary waits
await new Promise(resolve => setTimeout(resolve, 500));
```

#### Optimize Clock Usage
```typescript
// Good: Run all pending timers
clock.runAll();

// Good: Minimal specific ticks
clock.tick(25);

// Avoid: Large clock advances
clock.tick(1000);
```

#### Efficient Screenshot Testing
```typescript
// Good: Test behavior first, then screenshot
expect(component.property).to.equal(expectedValue);
await assertScreenshot('component/state', getClip(component));

// Good: Group related visual states
await assertScreenshot('select/open', getClipWithOptions(select));
```

## Running Subsets of Tests

### Individual Test Files
```bash
# Run specific test file
bun run test test/temba-select.test.ts

# Run multiple specific files
bun run test test/temba-select.test.ts test/temba-list.test.ts
```

### Isolating Tests During Development
Use `it.only()` to focus on specific tests:

```typescript
// Run only this test
it.only('should handle specific case', async () => {
  // test implementation
});

// Skip this test
it.skip('should handle edge case', async () => {
  // test implementation
});
```

## Environment-Specific Behavior

### Copilot Environment
- Higher screenshot comparison thresholds (1.0 vs 0.1)
- Automatic detection via environment variables
- Adaptive timeout handling

### CI Environment
- Standard screenshot comparison
- Full network idle waits
- Complete test suite execution

## Performance Monitoring

### Timing Analysis
Monitor test execution times to identify slow tests:

```bash
# Time full test suite
time bun run test

# Profile individual test files
time bun run test test/specific-file.test.ts
```

### Common Performance Issues
1. **Excessive timeouts**: Replace with `updateComplete` where possible
2. **Redundant screenshots**: Group similar visual states
3. **Network waits**: Use fast mode for unit-focused testing
4. **Large clock advances**: Use minimal tick values

## Best Practices Summary

1. **Start with fast mode** during development
2. **Use unit tests** for rapid iteration
3. **Reserve full suite** for final validation
4. **Group visual tests** by component/feature
5. **Minimize wait times** in test helpers
6. **Leverage concurrency** with parallel execution
7. **Monitor and profile** slow tests regularly