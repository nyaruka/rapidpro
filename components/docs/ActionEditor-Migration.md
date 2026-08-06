# ActionEditor Form Data Abstraction Migration Guide

## Overview

The ActionEditor now supports form-level data transformations that provide a higher level of abstraction than the previous per-property approach. This allows for flexible mapping between action properties and form fields.

## Key Changes

### 1. Action-Level Transformations
Instead of per-property `toFormValue`/`fromFormValue`, you can now define these at the action level:

```typescript
export const myAction: UIConfig = {
  // Transform entire action to form data
  toFormValue: (action: MyAction) => ({
    // Form data can combine multiple action properties
    contact_info: `${action.name} <${action.email}>`,
    selected_options: action.options.map(opt => ({ name: opt, value: opt }))
  }),
  
  // Transform form data back to action
  fromFormValue: (formData: any): MyAction => {
    // Parse the combined contact_info back to separate fields
    const [name, email] = parseContactInfo(formData.contact_info);
    return {
      ...action,
      name,
      email,
      options: formData.selected_options.map(opt => opt.value)
    };
  }
}
```

### 2. Form Configuration (replaces properties)
Use `form` instead of `properties`, with keys matching your form data structure:

```typescript
export const myAction: UIConfig = {
  // OLD: properties keys matched action properties
  properties: {
    name: { /* config */ },
    email: { /* config */ }
  },

  // NEW: form keys match form data structure
  form: {
    contact_info: { /* combines name + email */ },
    selected_options: { /* transforms options array */ }
  }
}
```

## Migration Examples

### Before (per-property transformations)
```typescript
export const send_msg: UIConfig = {
  properties: {
    quick_replies: {
      toFormValue: (actionValue: string[]) => 
        actionValue.map(text => ({ name: text, value: text })),
      fromFormValue: (formValue: Array<{name: string, value: string}>) =>
        formValue.map(item => item.value)
    }
  }
}
```

### After (form-level transformations)
```typescript
export const send_msg_new: UIConfig = {
  toFormValue: (action: SendMsg) => ({
    text: action.text,
    quick_replies: action.quick_replies.map(text => ({ name: text, value: text }))
  }),
  
  fromFormValue: (formData: any): SendMsg => ({
    ...formData,
    type: 'send_msg',
    quick_replies: formData.quick_replies.map(item => item.value || item.name)
  }),
  
  form: {
    text: { /* config */ },
    quick_replies: { /* config */ }
  }
}
```

## Benefits

1. **Flexible field mapping**: Form fields don't need to match action properties 1:1
2. **Data consolidation**: Combine multiple action properties into single form fields
3. **Cleaner separation**: Form structure is independent of action structure
4. **Backward compatibility**: Existing configs continue to work unchanged

## Backward Compatibility

The ActionEditor automatically falls back to the old per-property approach when form-level transformations aren't provided:

- Uses `properties` if `form` is not defined
- Applies per-property `toFormValue`/`fromFormValue` if action-level ones aren't provided
- Maintains 1:1 mapping when no transformations are specified

## Testing

Test both transformation directions:

```typescript
it('should transform action to form data', async () => {
  // Set action and verify formData structure
});

it('should transform form data back to action on save', async () => {
  // Modify formData and verify saved action structure
});
```