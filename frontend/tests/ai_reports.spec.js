import { expect, test } from '@playwright/test'

const sectionNames = ['scientific_summary', 'uncertainty_explanation', 'sampling_decision_explanation', 'one_health_summary']
function draft() {
  return { id: 'mock-report', model_identifier: 'test/mock-model', generated_at: '2026-01-01T00:00:00',
    prompt_version: 'test.v1', validation_status: 'VALIDATED', review_status: 'DRAFT',
    current: true, stale: false, exportable: false,
    narrative: Object.fromEntries(sectionNames.map(name => [name, { statements: [{ text: `Mocked ${name}: the recorded TIE remains unchanged.`, source_references: ['decision:mock'] }] }])),
    sources: { 'decision:mock': { kind: 'decision', status: 'TIE' } } }
}

async function openReport(page) {
  await page.goto('/investigations/demo')
  await page.waitForURL(/\/investigations\/[0-9a-f-]+$/)
  await page.getByRole('button', { name: 'Evaluate sampling decision' }).click()
  await expect(page.getByText('Loading scientific investigation')).toBeHidden()
  await page.goto('/reports')
  await page.getByLabel('Scientific report').selectOption({ label: 'Wigger River Investigation' })
  await expect(page.getByRole('button', { name: 'Export PDF' })).toBeEnabled()
  await page.evaluate(() => { window.print = () => { window.__printCalls = (window.__printCalls || 0) + 1 } })
}

test('draft, explicit approval, regeneration and stale export are isolated from scientific tables', async ({ page }) => {
  let report = null
  await page.route('**/cases/*/ai-report**', async route => {
    if (route.request().method() === 'POST') {
      report = route.request().url().includes('/approve')
        ? { ...report, review_status: 'APPROVED', exportable: true } : draft()
      await route.fulfill({ json: report })
    } else await route.fulfill({ json: { enabled: true, available: true, report } })
  })
  await openReport(page)
  const panel = page.locator('.ai-report-panel')
  await panel.getByRole('button', { name: 'Generate AI Explanation', exact: true }).click()
  await expect(panel).toContainText('DRAFT — researcher review required')
  await expect(panel.locator('.ai-narrative-section')).toHaveCount(4)
  await page.getByRole('button', { name: 'Export PDF' }).click()
  await expect.poll(() => page.evaluate(() => window.__printCalls)).toBe(1)
  await page.emulateMedia({ media: 'print' })
  await expect(panel).toBeHidden()
  await expect(page.locator('#candidates')).toBeVisible()
  await page.emulateMedia({ media: 'screen' })
  await panel.getByRole('button', { name: 'Approve AI Explanation', exact: true }).click()
  await expect(panel).toContainText('APPROVED — scientific input current')
  await page.getByRole('button', { name: 'Export PDF' }).click()
  await expect.poll(() => page.evaluate(() => window.__printCalls)).toBe(2)
  await page.emulateMedia({ media: 'print' })
  await expect(panel).toBeVisible()
  await expect(page.locator('#candidates')).toBeVisible()
  await page.emulateMedia({ media: 'screen' })
  report = { ...report, stale: true, current: false, exportable: false }
  await page.getByRole('button', { name: 'Export PDF' }).click()
  await expect.poll(() => page.evaluate(() => window.__printCalls)).toBe(3)
  await expect(panel).toContainText('STALE — regenerate')
  await expect(panel.getByRole('button', { name: 'Approve AI Explanation', exact: true })).toBeDisabled()
  await page.emulateMedia({ media: 'print' })
  await expect(panel).toBeHidden()
  await page.emulateMedia({ media: 'screen' })
  await panel.getByRole('button', { name: 'Regenerate AI Explanation', exact: true }).click()
  await expect(panel).toContainText('DRAFT — researcher review required')
})

test('disabled and failing AI leave deterministic report and PDF available', async ({ page }) => {
  let enabled = false
  await page.route('**/cases/*/ai-report**', async route => {
    if (route.request().method() === 'POST') await route.fulfill({ status: 504, json: { detail: { message: 'Provider timed out.' } } })
    else await route.fulfill({ json: { enabled, available: enabled, report: null } })
  })
  await openReport(page)
  const panel = page.locator('.ai-report-panel')
  await expect(panel).toContainText('AI explanations are disabled')
  enabled = true
  await panel.getByRole('button', { name: 'Refresh AI status' }).click()
  await panel.getByRole('button', { name: 'Generate AI Explanation', exact: true }).click()
  await expect(panel.getByRole('alert')).toContainText('Provider timed out')
  await page.getByRole('button', { name: 'Export PDF' }).click()
  await expect.poll(() => page.evaluate(() => window.__printCalls)).toBe(1)
  await page.emulateMedia({ media: 'print' })
  await expect(panel).toBeHidden()
  await expect(page.locator('#detection')).toContainText('Fredericella sultana')
})

test('changing detection context discards pending AI output from the old context', async ({ page, request }) => {
  const base = 'http://127.0.0.1:18001'
  const demo = await (await request.get(`${base}/demo/wigger`)).json()
  const species = await (await request.post(`${base}/cases/${demo.case_id}/species`, { data: { taxon: 'Salmo trutta' } })).json()
  const context = await (await request.post(`${base}/cases/${demo.case_id}/detection-contexts`, { data: {
    species_id: species.id, site_id: demo.detection_site_id, sampled_on: '2014-06-27', event_label: 'AI browser isolation',
  } })).json()
  let release
  let started = false
  const pending = new Promise(resolve => { release = resolve })
  await page.route('**/cases/*/ai-report**', async route => {
    if (route.request().method() === 'POST') {
      started = true
      await pending
      await route.fulfill({ json: draft() }).catch(() => {})
    } else {
      const selected = new URL(route.request().url()).searchParams.get('detection_context_id')
      const report = selected === context.id ? draft() : null
      if (report) report.narrative.scientific_summary.statements[0].text = 'Selected Salmo trutta context only.'
      await route.fulfill({ json: { enabled: true, available: true, report } })
    }
  })
  await openReport(page)
  const panel = page.locator('.ai-report-panel')
  await panel.getByRole('button', { name: 'Generate AI Explanation', exact: true }).click()
  await expect.poll(() => started).toBe(true)
  await page.getByLabel('Report detection context').selectOption(context.id)
  await expect(panel).toContainText('Selected Salmo trutta context only.')
  const oldResponse = page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes('/ai-report'))
  release()
  await oldResponse
  await expect(panel).toContainText('Selected Salmo trutta context only.')
  await expect(panel).not.toContainText('Mocked scientific_summary')
  await expect(page.locator('#summary')).toContainText('Salmo trutta')
})
