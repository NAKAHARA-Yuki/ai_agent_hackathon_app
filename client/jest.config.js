module.exports = {
  testEnvironment: 'jsdom',
  moduleFileExtensions: ['js', 'vue', 'json'],
  transform: {
    '^.+\\.vue$': '@vue/vue3-jest',
    '^.+\\.js$': 'babel-jest'
  },
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1'
  },
  testMatch: [
    '<rootDir>/src/**/__tests__/**/*.test.js',
    '<rootDir>/src/**/*.test.js',
    '<rootDir>/src/**/__tests__/**/*.spec.js',
    '<rootDir>/src/**/*.spec.js'
  ],
  testPathIgnorePatterns: [
    '/node_modules/',
    '/__mocks__/'
  ],
  collectCoverageFrom: [
    'src/**/*.{js,vue}',
    '!src/main.js',
    '!**/node_modules/**',
    '!**/__tests__/**',
    '!**/__mocks__/**'
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  setupFilesAfterEnv: ['<rootDir>/src/__tests__/setup.js'],
  testTimeout: 10000,
  clearMocks: true,
  resetMocks: true,
  globals: {
    'vue-jest': {
      compilerOptions: {
        isCustomElement: (tag) => tag.startsWith('v-')
      }
    }
  },
  transformIgnorePatterns: [
    'node_modules/(?!(vue|@vue|pinia)/)'
  ]
}