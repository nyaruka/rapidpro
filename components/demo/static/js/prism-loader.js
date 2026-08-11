// PrismJS loader for demo HTML
import 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js';
import 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-markup.min.js';
import 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-javascript.min.js';
import 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-css.min.js';

window.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('pre.example-html').forEach((block) => {
    block.classList.add('language-markup');
    if (window.Prism) window.Prism.highlightElement(block);
  });
});
