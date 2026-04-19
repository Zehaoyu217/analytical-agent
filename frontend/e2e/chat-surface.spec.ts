import { test, expect, type Page } from '@playwright/test'

async function loadApp(page: Page): Promise<void> {
  page.on('requestfailed', () => {
    /* swallow backend failures */
  })
  await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 15_000 })
}

test.describe('chat surface', () => {
  test('header renders sidebar toggle, title, and action buttons', async ({ page }) => {
    await loadApp(page)
    await expect(page.getByRole('button', { name: /show threads|hide threads/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /search/i }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: /fork/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /export/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /more/i })).toBeVisible()
  })

  test('composer shows model picker, extended toggle, plan toggle, send', async ({ page }) => {
    await loadApp(page)
    await expect(page.getByRole('button', { name: /model/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /extended/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /plan/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /^send$/i })).toBeVisible()
  })

  test('mod+Shift+E toggles extended thinking', async ({ page }) => {
    await loadApp(page)
    const btn = page.getByRole('button', { name: /extended/i })
    const before = await btn.getAttribute('data-active')
    await page.keyboard.press('ControlOrMeta+Shift+E')
    await expect
      .poll(async () => btn.getAttribute('data-active'), { timeout: 2_000 })
      .not.toBe(before)
  })

  test('mod+Shift+M cycles model', async ({ page }) => {
    await loadApp(page)
    const picker = page.getByRole('button', { name: /model/i })
    const before = await picker.textContent()
    await page.keyboard.press('ControlOrMeta+Shift+M')
    await expect
      .poll(async () => picker.textContent(), { timeout: 2_000 })
      .not.toBe(before)
  })
})
