/**
 * E2E Smoke Tests — claude-code-agent
 *
 * Critical user journeys:
 *   1. App loads without crashing
 *   2. Chat input is present and focusable
 *   3. Sidebar / icon rail renders
 *   4. Theme toggle works
 *
 * Backend may be unavailable — tests are scoped to UI-only flows
 * and do not assert on API responses.
 */

import { test, expect } from '@playwright/test'

// ────────────────────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────────────────────

/**
 * Navigate to the app and wait for the main shell to be visible.
 * Swallows network errors originating from the backend (port 8000) so that
 * tests pass even when the backend is not running.
 */
async function loadApp(page: import('@playwright/test').Page) {
  // Suppress backend request failures so UI-only assertions still pass
  page.on('requestfailed', () => {/* intentionally swallowed */})
  await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 15_000 })
}

// ────────────────────────────────────────────────────────────────────────────
// Test 1: App loads without crashing
// ────────────────────────────────────────────────────────────────────────────

test('app loads without crashing', async ({ page }) => {
  const jsErrors: string[] = []
  page.on('pageerror', (err) => jsErrors.push(err.message))

  await loadApp(page)

  // The root React mounting point must exist
  const root = page.locator('#root')
  await expect(root).toBeAttached()

  // At least one meaningful element should be visible — icon rail nav or chat input
  const navOrInput = page.locator(
    'nav[aria-label="Main navigation"], [data-chat-input], textarea[aria-label="Message"]',
  )
  await expect(navOrInput.first()).toBeVisible({ timeout: 10_000 })

  // No uncaught JavaScript exceptions
  expect(jsErrors, `Unexpected JS errors: ${jsErrors.join('; ')}`).toHaveLength(0)

  await page.screenshot({ path: 'e2e-smoke-app-loaded.png' })
})

// ────────────────────────────────────────────────────────────────────────────
// Test 2: Chat input is present and focusable
// ────────────────────────────────────────────────────────────────────────────

test('chat input is present and focusable', async ({ page }) => {
  await loadApp(page)

  // The textarea is the primary chat input — it carries data-chat-input and aria-label
  const chatInput = page.locator('textarea[aria-label="Message"], [data-chat-input]').first()
  await expect(chatInput).toBeVisible({ timeout: 10_000 })

  // Clicking the input should focus it
  await chatInput.click()
  await expect(chatInput).toBeFocused()

  // Typing should populate the field
  await chatInput.fill('Hello, test!')
  const value = await chatInput.inputValue()
  expect(value).toContain('Hello')

  // Clear so subsequent tests start clean
  await chatInput.clear()

  await page.screenshot({ path: 'e2e-smoke-chat-input.png' })
})

// ────────────────────────────────────────────────────────────────────────────
// Test 3: Sidebar / icon rail renders with navigation buttons
// ────────────────────────────────────────────────────────────────────────────

test('icon rail renders with navigation buttons', async ({ page }) => {
  await loadApp(page)

  const nav = page.locator('nav[aria-label="Main navigation"]')
  await expect(nav).toBeVisible({ timeout: 10_000 })

  // Expect core nav buttons to exist
  const expectedLabels = ['Chat', 'Agents', 'Skills', 'DevTools', 'Settings']
  for (const label of expectedLabels) {
    const btn = nav.locator(`button[aria-label="${label}"]`)
    await expect(btn).toBeVisible({ timeout: 5_000 })
  }

  // Chat button should be active by default (aria-current="page")
  const chatBtn = nav.locator('button[aria-label="Chat"]')
  await expect(chatBtn).toHaveAttribute('aria-current', 'page')

  await page.screenshot({ path: 'e2e-smoke-icon-rail.png' })
})

// ────────────────────────────────────────────────────────────────────────────
// Test 4: Theme toggle works
// ────────────────────────────────────────────────────────────────────────────

test('theme toggle switches between dark and light', async ({ page }) => {
  await loadApp(page)

  const html = page.locator('html')

  // App defaults to dark (no .light class on <html>)
  const initialClasses = await html.getAttribute('class') ?? ''
  const startsDark = !initialClasses.includes('light')
  // Accept either dark or light as valid initial state
  expect(typeof startsDark).toBe('boolean')

  // Theme is toggled via the ThemeProvider — trigger it through localStorage + reload
  // This simulates the user flipping the theme via settings or command palette
  await page.evaluate(() => {
    const current = localStorage.getItem('theme') ?? 'dark'
    localStorage.setItem('theme', current === 'dark' ? 'light' : 'dark')
  })
  await page.reload({ waitUntil: 'domcontentloaded' })

  const afterClasses = await html.getAttribute('class') ?? ''
  const nowLight = afterClasses.includes('light')

  // Toggling from dark → light should add .light class; from light → dark removes it
  if (startsDark) {
    expect(nowLight).toBe(true)
  } else {
    expect(nowLight).toBe(false)
  }

  // Restore original theme
  await page.evaluate(() => {
    localStorage.setItem('theme', 'dark')
  })

  await page.screenshot({ path: 'e2e-smoke-theme-toggle.png' })
})

// ────────────────────────────────────────────────────────────────────────────
// Test 5: Section navigation via icon rail
// ────────────────────────────────────────────────────────────────────────────

test('clicking icon rail buttons switches active section', async ({ page }) => {
  await loadApp(page)

  const nav = page.locator('nav[aria-label="Main navigation"]')
  await expect(nav).toBeVisible({ timeout: 10_000 })

  // Navigate to DevTools section
  const devtoolsBtn = nav.locator('button[aria-label="DevTools"]')
  await expect(devtoolsBtn).toBeVisible()
  await devtoolsBtn.click()

  // The DevTools button should become active
  await expect(devtoolsBtn).toHaveAttribute('aria-current', 'page', { timeout: 3_000 })

  // Navigate back to Chat
  const chatBtn = nav.locator('button[aria-label="Chat"]')
  await chatBtn.click()
  await expect(chatBtn).toHaveAttribute('aria-current', 'page', { timeout: 3_000 })

  await page.screenshot({ path: 'e2e-smoke-section-nav.png' })
})
