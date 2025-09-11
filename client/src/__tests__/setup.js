// Test setup and global mocks

// Mock import.meta
global.importMeta = {
  env: {
    VITE_USE_MOCK: process.env.VITE_USE_MOCK || 'false',
    DEV: process.env.NODE_ENV !== 'production'
  }
};

// Transform import.meta.env calls to global.importMeta.env for Jest
Object.defineProperty(global, 'import', {
  value: {
    meta: global.importMeta
  }
});

// Create proper mock for localStorage
const createLocalStorageMock = () => {
  let store = {}
  return {
    getItem: jest.fn((key) => store[key] || null),
    setItem: jest.fn((key, value) => { store[key] = value.toString() }),
    removeItem: jest.fn((key) => { delete store[key] }),
    clear: jest.fn(() => { store = {} }),
    get length() { return Object.keys(store).length },
    key: jest.fn((index) => Object.keys(store)[index] || null)
  }
}

// Mock localStorage
global.localStorage = createLocalStorageMock()

// Mock fetch
global.fetch = jest.fn();

// Mock crypto.randomUUID
Object.defineProperty(global, 'crypto', {
  value: {
    randomUUID: jest.fn(() => 'mock-uuid-1234'),
  },
  writable: true
});

// Mock window location
Object.defineProperty(window, 'location', {
  value: {
    pathname: '/',
    search: '',
    hash: '',
  },
  writable: true,
});

// Mock console methods to avoid noise in tests
global.console = {
  ...console,
  log: jest.fn(),
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
};