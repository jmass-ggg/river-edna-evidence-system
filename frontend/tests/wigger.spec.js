import { expect, test } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

const artifacts=path.resolve('../browser_artifacts/screenshots')

async function monitor(page) {
  const errors=[]
  page.on('pageerror',error=>errors.push(`page: ${error.message}`))
  page.on('console',message=>{if(message.type()==='error')errors.push(`console: ${message.text()}`)})
  page.on('response',response=>{if(response.status()>=500)errors.push(`HTTP ${response.status()}: ${response.url()}`)})
  return errors
}

async function loadDemo(page) {
  await page.goto('/investigations/demo')
  await page.waitForURL(/\/investigations\/[0-9a-f-]+$/)
  await expect(page.getByText('Fredericella sultana').first()).toBeVisible()
}

test.beforeAll(async()=>mkdir(artifacts,{recursive:true}))

test('homepage navigation and verified map render without errors', async ({page},testInfo) => {
  const errors=await monitor(page)
  await page.goto('/')
  await expect(page.getByRole('heading',{name:'From uncertain DNA detections to clearer freshwater decisions.'})).toBeVisible()
  await expect(page.locator('.home-map .river-reach').first()).toBeVisible()
  await expect(page.locator('.home-map').first().getByText('Verified preflight geometry · EPSG:4326')).toBeVisible()
  await expect(page.getByRole('link',{name:'Dashboard'})).toHaveAttribute('href','/dashboard')
  await page.screenshot({path:path.join(artifacts,`home-${testInfo.project.name}.png`),fullPage:true})
  expect(errors).toEqual([])
})

test('Wigger workspace exposes the historical observation, map controls, decision, and trace', async ({page},testInfo) => {
  const errors=await monitor(page)
  await loadDemo(page)
  await expect(page.getByText('2014-06-25')).toBeVisible()
  await expect(page.getByText('Observation index').locator('..')).toContainText('4')
  await expect(page.getByText('1.2983219767633366e-17 mol/L')).toBeVisible()
  await expect(page.getByText('DETECTED')).toBeVisible()
  await expect(page.getByText('TIE').first()).toBeVisible()
  await expect(page.locator('.workspace-map .river-reach')).toHaveCount(49)
  await expect(page.locator('.workspace-map .map-marker')).toHaveCount(4)

  const map=page.locator('.workspace-map .scientific-map')
  const geometry=map.locator('.geo-svg')
  const initialViewBox=await geometry.getAttribute('viewBox')
  await map.getByRole('button',{name:'Zoom in'}).click()
  await expect(geometry).not.toHaveAttribute('viewBox',initialViewBox)
  await map.getByRole('button',{name:'Reset map view'}).click()
  await expect(geometry).toHaveAttribute('viewBox',initialViewBox)
  await map.getByLabel('Select Site B').press('Enter')
  await expect(map.getByRole('status')).toContainText('Reach 20450127')
  await map.getByRole('checkbox',{name:'River network'}).uncheck()
  await expect(map.locator('.river-reach')).toHaveCount(0)
  await map.getByRole('checkbox',{name:'River network'}).check()
  await map.getByRole('button',{name:'Toggle fullscreen'}).click()
  await expect(map).toHaveClass(/map-fullscreen/)
  await map.getByRole('button',{name:'Toggle fullscreen'}).click()

  await page.getByRole('button',{name:/Next Steps/}).click()
  await expect(page.getByText('Register a real follow-up sample')).toBeVisible()
  await page.getByRole('button',{name:'Evaluate sampling decision'}).click()
  await expect(page.getByText('Loading scientific investigation')).toBeHidden()
  await expect(page.getByRole('heading',{name:'Decision trace'})).toBeVisible()
  await expect(page.getByText(/sampling\.topology_pair_separation\.v1/)).toBeVisible()
  await page.screenshot({path:path.join(artifacts,`workspace-${testInfo.project.name}.png`),fullPage:true})
  expect(errors).toEqual([])
})

test('site filtering keeps list, markers, and details synchronized', async ({page},testInfo) => {
  await page.goto('/sites')
  await expect(page.locator('.site-cards button')).toHaveCount(4)
  await page.locator('.site-cards button').filter({hasText:'Site C'}).click()
  await expect(page.locator('.site-details')).toContainText('20451169')
  await page.getByLabel('Site type').selectOption({label:'Candidate sample'})
  await expect(page.locator('.site-cards button')).toHaveCount(3)
  await expect(page.locator('.scientific-map .map-marker')).toHaveCount(3)
  await expect(page.locator('.site-details h3')).toHaveText('Site C')
  await page.getByPlaceholder('Search sites').fill('Site D')
  await expect(page.locator('.site-cards button')).toHaveCount(1)
  await expect(page.locator('.site-details h3')).toHaveText('Site D')
  await expect(page.locator('.site-details')).toContainText('20448315')
  await page.screenshot({path:path.join(artifacts,`sites-${testInfo.project.name}.png`),fullPage:true})
})

test('responsive pages have no document-level horizontal overflow', async ({page},testInfo) => {
  await loadDemo(page)
  const casePath=new URL(page.url()).pathname
  for (const [name,url] of [['dashboard','/dashboard'],['investigations','/investigations'],['sites','/sites'],['workspace',casePath],['reports','/reports']]) {
    await page.goto(url)
    await page.waitForLoadState('networkidle')
    if(name==='reports'){
      await page.getByLabel('Scientific report').selectOption({label:'Wigger River Investigation'})
      await expect(page.getByText('1.2983219767633366e-17 mol/L')).toBeVisible()
    }
    const dimensions=await page.evaluate(()=>[document.documentElement.scrollWidth,document.documentElement.clientWidth])
    expect(dimensions[0],`${name} overflow at ${testInfo.project.name}`).toBeLessThanOrEqual(dimensions[1])
  }
  await page.screenshot({path:path.join(artifacts,`report-${testInfo.project.name}.png`),fullPage:true})
})

test('desktop workflow validates creation, filters records, and prints the report', async ({page},testInfo) => {
  test.skip(testInfo.project.name!=='desktop-1440','Full interaction runs once at desktop size')
  await loadDemo(page)
  await page.getByRole('button',{name:'Evaluate sampling decision'}).click()
  await expect(page.getByRole('heading',{name:'Decision trace'})).toBeVisible()

  await page.goto('/investigations/new')
  await page.getByRole('button',{name:'Create investigation'}).click()
  await expect(page.getByText('Required')).toHaveCount(6)
  await page.getByLabel('Investigation name').fill('Browser verification case')
  await page.getByLabel('Target species').fill('Browser verification test taxon')
  await page.getByLabel('Latitude').fill('47.314')
  await page.getByLabel('Longitude').fill('7.8954')
  await page.getByLabel('Verified HydroRIVERS reach ID').fill('999999999')
  await page.locator('.investigation-form').getByLabel('Date').fill('2026-10-02')
  await page.getByRole('button',{name:'Create investigation'}).click()
  await expect(page.locator('.form-notice')).toContainText('not found in loaded network data')
  await page.getByLabel('Verified HydroRIVERS reach ID').fill('20446064')
  await page.getByLabel('Replicate 1').selectOption('Negative')
  await page.getByRole('button',{name:'Create investigation'}).click()
  await page.waitForURL(/\/investigations\/[0-9a-f-]+$/)

  await page.goto('/investigations')
  await page.getByLabel('Search investigations').fill('Browser verification case')
  await expect(page.locator('tbody tr')).toHaveCount(1)
  await expect(page.getByText('NOT EVALUATED')).toBeVisible()
  await page.getByText('Clear filters').click()
  await page.getByLabel('Scientific decision').selectOption('TIE')
  await expect(page.locator('tbody tr')).toHaveCount(1)
  await expect(page.locator('tbody tr')).toContainText('Fredericella sultana')

  await page.goto('/dashboard')
  await expect(page.getByText('Persisted ACTIVE cases').locator('..').locator('b')).toHaveText('2')
  await expect(page.getByText('Cases without a persisted decision').locator('..').locator('b')).toHaveText('1')

  await page.goto('/reports')
  await page.getByLabel('Scientific report').selectOption({label:'Wigger River Investigation'})
  await expect(page.getByText('1.2983219767633366e-17 mol/L')).toBeVisible()
  await expect(page.getByText('hydrorivers.directed_contribution.v1').first()).toBeVisible()
  await expect(page.locator('.report-document .river-reach')).toHaveCount(49)
  await expect(page.locator('#assumptions')).toContainText('remaining hypotheses')
  await expect(page.locator('#followup')).toContainText('Site B, Site C, Site D')
  await page.locator('.report-toc').getByRole('button',{name:'Limitations',exact:true}).click()
  await expect(page.locator('#limitations')).toBeInViewport()
  await page.emulateMedia({media:'print'})
  await expect(page.locator('.app-nav')).toBeHidden()
  await page.pdf({path:path.resolve('../browser_artifacts/WIGGER_BROWSER_REPORT.pdf'),format:'A4',printBackground:true})
})

test('frontend presents API failures as errors rather than empty records', async ({page},testInfo) => {
  test.skip(testInfo.project.name!=='desktop-1440','Failure-path checks run once')
  await page.route('**/cases',route=>route.abort('failed'))
  await page.goto('/dashboard')
  await expect(page.getByText('Could not load investigations')).toBeVisible()
  await page.unroute('**/cases')
  await page.goto('/investigations/not-a-uuid')
  await expect(page.getByText('Investigation unavailable')).toBeVisible()
  await page.route('**/demo/wigger/map',route=>route.fulfill({status:500,contentType:'application/json',body:'{"error":{"message":"map unavailable"}}'}))
  await page.goto('/sites')
  await expect(page.getByText('Map service unavailable')).toBeVisible()
})
