export type Cart = Record<string, number>;
export const CART_KEY = 'brokecart.cart.v1';
export function readCart(raw: string | null): Cart {
  try {
    const input: unknown = JSON.parse(raw || '{}');
    if (!input || typeof input !== 'object' || Array.isArray(input)) return {};
    return Object.fromEntries(Object.entries(input).filter(([id, q]) =>
      /^bc-[0-9]{3}$/.test(id) && Number.isInteger(q) && Number(q) > 0 && Number(q) <= 10
    ).slice(0, 30));
  } catch { return {}; }
}
export function updateQuantity(cart: Cart, id: string, quantity: number): Cart {
  if (!/^bc-[0-9]{3}$/.test(id) || !Number.isInteger(quantity)) return cart;
  const next = { ...cart };
  if (quantity <= 0) delete next[id];
  else next[id] = Math.min(quantity, 10);
  return next;
}
export const money = (cents: number) => new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD'
}).format(cents / 100);
