import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['js_simulator/tests/unit/**/*.{test,spec}.{js,ts}'],
    environment: 'node',
    reporters: ['default'],
  },
});
