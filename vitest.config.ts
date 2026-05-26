import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/javascript/**/*.{test,spec}.{js,ts}'],
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/javascript/setup.ts'],
  },
});