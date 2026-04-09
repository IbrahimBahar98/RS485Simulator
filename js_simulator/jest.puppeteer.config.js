module.exports = {
  // Jest configuration for Puppeteer E2E tests
  preset: 'jest-puppeteer',
  testMatch: [
    '**/tests/e2e/**/*.test.js',
    '**/tests/e2e/**/*.test.jsx',
    '**/tests/e2e/**/*.spec.js',
    '**/tests/e2e/**/*.spec.jsx'
  ],
  testEnvironment: 'node',
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.js'],
  collectCoverage: true,
  coverageDirectory: 'coverage/e2e',
  coverageReporters: ['json', 'text', 'lcov', 'clover'],
  coverageThreshold: {
    global: {
      statements: 80,
      branches: 80,
      functions: 80,
      lines: 80
    }
  },
  // Puppeteer-specific configuration
  puppeteer: {
    dumpio: false,
    headless: true,
    slowMo: 0,
    timeout: 30000
  }
};