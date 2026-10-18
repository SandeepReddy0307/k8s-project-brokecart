import { test, expect } from '@playwright/test';
test('real catalog and pricing drive the storefront', async ({page}, info) => {
  test.skip(process.env.LIVE_API !== '1', 'Start the two Java applications and set LIVE_API=1 for this integration check.');
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('button',{name:/Add .* to cart/})).toHaveCount(8);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({path:`/tmp/brokecart-${info.project.name}.png`,fullPage:true});
  await page.getByRole('button',{name:'Add Cloud Nine Headphones to cart'}).click();
  await page.getByRole('button',{name:/Your cart/}).click();
  await expect(page.getByText('$94.89',{exact:true})).toBeVisible();
  await page.getByRole('textbox',{name:'Promotion code'}).fill('BROKE10');
  await page.getByRole('button',{name:'Apply',exact:true}).click();
  await expect(page.getByText('$85.90',{exact:true})).toBeVisible();
  await expect(page.getByText('BROKE10 · 10% off')).toBeVisible();
  expect(errors).toEqual([]);
});
