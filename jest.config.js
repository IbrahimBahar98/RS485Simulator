module.exports = {
  testMatch: ['**/__tests__/**/*.test.(js|jsx|ts|tsx)', '**/?(*.)+(spec|test).(js|jsx|ts|tsx)'],
  collectCoverageFrom: [
    'js_simulator/**/*.{js,jsx}',
    '!js_simulator/**/node_modules/**',
  ],
  coverageReporters: ['text', 'lcov'],
};