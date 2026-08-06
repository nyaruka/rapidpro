module.exports = {
  '*.ts': (files) => {
    const filtered = files.filter((f) => !f.includes('/locales/'));
    if (filtered.length === 0) return [];
    return [
      `prettier --config .prettierrc --write ${filtered.join(' ')}`,
      `eslint ${filtered.join(' ')}`
    ];
  }
};
