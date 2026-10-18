import { describe, expect, it } from 'vitest';
import { readCart, updateQuantity, money } from './cart';
describe('browser cart boundary', () => {
  it('rejects corrupt and unsafe persisted data', () => {
    expect(readCart('broken')).toEqual({});
    expect(readCart('[1,2]')).toEqual({});
    expect(readCart('{"bc-001":2,"bc-002":-1,"bc-003":11,"oops":4,"bc-004":"2"}')).toEqual({'bc-001':2});
  });
  it('caps quantities and removes empty lines without mutation', () => {
    const cart = {'bc-001':2};
    expect(updateQuantity(cart, 'bc-001', 12)).toEqual({'bc-001':10});
    expect(updateQuantity(cart, 'bc-001', 0)).toEqual({});
    expect(cart).toEqual({'bc-001':2});
  });
  it('formats integer cents', () => expect(money(8990)).toBe('$89.90'));
});
