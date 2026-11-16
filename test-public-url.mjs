import test from 'node:test';
import assert from 'node:assert/strict';
import { publicOrigin } from './src/public-url.js';

test('configured public origin overrides Railway request host', () => {
  const previous = process.env.PUBLIC_BASE_URL;
  process.env.PUBLIC_BASE_URL = 'https://movieapi.ideapaid911.workers.dev';
  try {
    assert.equal(publicOrigin({ get: () => 'movieapi-production-59c04909.up.railway.app' }), 'https://movieapi.ideapaid911.workers.dev');
  } finally {
    if (previous === undefined) delete process.env.PUBLIC_BASE_URL;
    else process.env.PUBLIC_BASE_URL = previous;
  }
});

test('forwarded Worker host is used when no canonical origin is configured', () => {
  const previous = process.env.PUBLIC_BASE_URL;
  delete process.env.PUBLIC_BASE_URL;
  try {
    assert.equal(publicOrigin({
      headers: { 'x-forwarded-host': 'movieapi.ideapaid911.workers.dev', 'x-forwarded-proto': 'https' },
      get: () => 'movieapi-production-59c04909.up.railway.app', secure: false,
    }), 'https://movieapi.ideapaid911.workers.dev');
  } finally {
    if (previous !== undefined) process.env.PUBLIC_BASE_URL = previous;
  }
});

test('invalid configured public origin is rejected', () => {
  const previous = process.env.PUBLIC_BASE_URL;
  process.env.PUBLIC_BASE_URL = 'http://movieapi-production-59c04909.up.railway.app';
  try {
    assert.throws(() => publicOrigin({ get: () => 'origin.invalid' }), /PUBLIC_BASE_URL/);
  } finally {
    if (previous === undefined) delete process.env.PUBLIC_BASE_URL;
    else process.env.PUBLIC_BASE_URL = previous;
  }
});
