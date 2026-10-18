import { test, expect } from '@playwright/test';
test('catalog browsing, server quote and cart persistence', async ({ page }) => {
  await page.route('**/api/identity/me', route => route.fulfill({status:401,json:{detail:'Sign in required'}}));
  await page.route('**/api/catalog/products?*', route => route.fulfill({ json: {items: [
    {id:'bc-001',name:'Cloud Nine Headphones',category:'Tech',description:'Wireless headphones',priceCents:8990,artwork:'headphones',badge:'Bestseller'},
    {id:'bc-003',name:'Emotional Support Mug',category:'Home',description:'Ceramic mug',priceCents:1890,artwork:'mug',badge:'Under $25'}
  ]} }));
  await page.route('**/api/pricing/quotes', async route => {
    const request = route.request().postDataJSON();
    expect(request.items).toEqual([{productId:'bc-001',quantity:1}]);
    expect(request.items[0]).not.toHaveProperty('priceCents');
    await route.fulfill({json:{quoteId:'test',subtotalCents:8990,discountCents:0,shippingCents:499,totalCents:9489,expiresAt:new Date(Date.now()+300000).toISOString(),lines:[]}});
  });
  await page.goto('/');
  await expect(page.getByRole('heading', {name:'Your next little obsession.'})).toBeVisible();
  await page.getByRole('button', {name:'Add Cloud Nine Headphones to cart'}).click();
  await page.getByRole('button', {name:/Your cart/}).click();
  await expect(page.getByText('$94.89', {exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Sign in to checkout'})).toBeEnabled();
  await page.getByRole('button',{name:'Close cart'}).click();
  await page.reload();
  await expect(page.getByRole('button',{name:/Your cart/})).toContainText('1');
  await page.getByRole('button',{name:'Home',exact:true}).click();
  await expect(page.getByRole('button',{name:'Add Cloud Nine Headphones to cart'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Add Emotional Support Mug to cart'})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
test('shows service errors without fake product fallback', async ({page}) => {
  await page.route('**/api/identity/me', route => route.fulfill({status:401,json:{detail:'Sign in required'}}));
  await page.route('**/api/catalog/products?*', route => route.fulfill({status:503,json:{detail:'Catalog unavailable'}}));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Catalog unavailable');
  await expect(page.getByRole('button',{name:'Try again'})).toBeVisible();
});
