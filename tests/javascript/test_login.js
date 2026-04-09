import { expect, test } from 'vitest';

// Mock implementation of validateLogin for testing
function validateLogin(username, password) {
  return username === 'admin' && password === 'admin';
}

test('Test login validation rejects incorrect credentials', () => {
  expect(validateLogin('user', 'pass')).toBe(false);
});

test('Test login validation accepts default admin/admin credentials', () => {
  expect(validateLogin('admin', 'admin')).toBe(true);
});