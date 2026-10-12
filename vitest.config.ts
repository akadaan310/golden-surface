import { defineConfig } from 'vitest/config';
export default defineConfig({
  test: {
    include: ['packages/**/*.test.ts', 'services/**/*.test.ts', 'apps/**/*.test.ts'],
    exclude: ['**/node_modules/**', '**/.next/**', 'packages/rf/**'],
    testTimeout: 15000,
    maxWorkers: 4,
    minWorkers: 1,
    fileParallelism: true
  }
});
