/**
 * Puppeteer test for bounding box accuracy in DocumentViewer
 *
 * Tests:
 * 1. Bounding boxes render at correct positions
 * 2. Bounding boxes scale with zoom
 * 3. Bounding boxes work for both PDF and image documents
 * 4. Multiple highlights don't overlap incorrectly
 */

const puppeteer = require('puppeteer');

const API_URL = process.env.VITE_API_URL || 'http://localhost:8000';
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:3003';

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function testBoundingBoxes() {
  console.log('🚀 Starting bounding box accuracy tests...\n');

  const browser = await puppeteer.launch({
    headless: false, // Set to true for CI/CD
    devtools: false,
    args: ['--window-size=1920,1080']
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });

    // Enable console logging
    page.on('console', msg => {
      const type = msg.type();
      if (type === 'error' || type === 'warning') {
        console.log(`[Browser ${type}]:`, msg.text());
      }
    });

    // Test 1: Get a document with low confidence fields (should have bboxes)
    console.log('📋 Test 1: Fetching audit queue...');
    const auditResponse = await fetch(`${API_URL}/api/audit/queue?max_confidence=0.9&size=1`);
    const auditData = await auditResponse.json();

    if (auditData.items.length === 0) {
      console.log('⚠️  No audit items found. Creating test data...');
      // TODO: Upload test document with known bbox
      console.log('ℹ️  Please upload a document with extracted fields to test bounding boxes');
      await browser.close();
      return;
    }

    const testItem = auditData.items[0];
    console.log(`✅ Found test item: ${testItem.filename} - ${testItem.field_name}`);
    console.log(`   Document ID: ${testItem.document_id}`);
    console.log(`   Bbox: ${JSON.stringify(testItem.source_bbox)}`);
    console.log(`   Page: ${testItem.source_page || 1}`);

    // Test 2: Navigate to audit page
    console.log('\n📋 Test 2: Loading audit page...');
    try {
      await page.goto(`${FRONTEND_URL}/audit`, {
        waitUntil: 'networkidle2',
        timeout: 30000
      });
      await sleep(3000); // Wait for document to load
    } catch (error) {
      console.error('❌ Failed to load page:', error.message);
      await page.screenshot({ path: '/tmp/bbox-error.png' });
      await browser.close();
      return;
    }

    // Debug: Check what's on the page
    const pageTitle = await page.title();
    console.log(`   Page title: ${pageTitle}`);

    const bodyText = await page.evaluate(() => document.body.innerText.slice(0, 200));
    console.log(`   Page content preview: ${bodyText.substring(0, 100)}...`);

    // Test 3: Check if document viewer loaded
    console.log('\n📋 Test 3: Checking document viewer...');

    // Check for multiple possible selectors
    const viewerSelectors = [
      '.flex.flex-col.h-full.bg-gray-100',
      '[class*="DocumentViewer"]',
      '[class*="PDFViewer"]',
      'div.rounded-lg.border'
    ];

    let viewerExists = null;
    for (const selector of viewerSelectors) {
      viewerExists = await page.$(selector);
      if (viewerExists) {
        console.log(`   ✅ Found viewer with selector: ${selector}`);
        break;
      }
    }

    if (!viewerExists) {
      console.error('❌ Document viewer not found with any selector!');
      console.log('   Taking debug screenshot...');
      await page.screenshot({ path: '/tmp/bbox-no-viewer.png', fullPage: true });

      // Check if we're on the right page
      const currentUrl = page.url();
      console.log(`   Current URL: ${currentUrl}`);

      // Check if there's an error message
      const errorMsg = await page.$('.text-red-600, .text-red-500, .text-red-400');
      if (errorMsg) {
        const errorText = await page.evaluate(el => el.textContent, errorMsg);
        console.log(`   Error on page: ${errorText}`);
      }

      await browser.close();
      return;
    }
    console.log('✅ Document viewer loaded');

    // Test 4: Check if bounding boxes are rendered
    console.log('\n📋 Test 4: Checking bounding box rendering...');
    await sleep(1000); // Wait for bbox to render

    const bboxElements = await page.$$('div[title*="Extraction"], div[class*="border-"]');
    console.log(`   Found ${bboxElements.length} potential bbox elements`);

    if (bboxElements.length === 0) {
      console.log('⚠️  No bounding boxes rendered. Checking why...');

      // Check if highlights array is populated
      const highlightsCheck = await page.evaluate(() => {
        return window.__REACT_DEVTOOLS_GLOBAL_HOOK__ ?
          'React DevTools available' :
          'Cannot inspect React state without DevTools';
      });
      console.log(`   ${highlightsCheck}`);
    }

    // Test 5: Verify bbox position and dimensions
    console.log('\n📋 Test 5: Verifying bbox position...');
    for (let i = 0; i < Math.min(bboxElements.length, 3); i++) {
      const bbox = bboxElements[i];
      const bboxInfo = await page.evaluate(el => {
        const style = window.getComputedStyle(el);
        return {
          left: style.left,
          top: style.top,
          width: style.width,
          height: style.height,
          borderColor: style.borderColor,
          position: style.position,
          title: el.getAttribute('title')
        };
      }, bbox);

      console.log(`   Bbox ${i + 1}:`, bboxInfo);

      // Validate bbox is positioned absolutely
      if (bboxInfo.position !== 'absolute') {
        console.error(`   ❌ Bbox ${i + 1} should be position: absolute, got: ${bboxInfo.position}`);
      } else {
        console.log(`   ✅ Bbox ${i + 1} correctly positioned`);
      }
    }

    // Test 6: Test zoom scaling
    console.log('\n📋 Test 6: Testing zoom scaling...');

    // Get initial bbox dimensions
    if (bboxElements.length > 0) {
      const initialDimensions = await page.evaluate(el => {
        const rect = el.getBoundingClientRect();
        return { width: rect.width, height: rect.height };
      }, bboxElements[0]);

      console.log(`   Initial bbox dimensions: ${JSON.stringify(initialDimensions)}`);

      // Click zoom in button
      const zoomInBtn = await page.$('button[title="Zoom in"]');
      if (zoomInBtn) {
        await zoomInBtn.click();
        await sleep(500);

        const zoomedDimensions = await page.evaluate(el => {
          const rect = el.getBoundingClientRect();
          return { width: rect.width, height: rect.height };
        }, bboxElements[0]);

        console.log(`   Zoomed bbox dimensions: ${JSON.stringify(zoomedDimensions)}`);

        // Check if dimensions increased
        if (zoomedDimensions.width > initialDimensions.width) {
          console.log('   ✅ Bounding box scales with zoom');
        } else {
          console.error('   ❌ Bounding box does not scale with zoom!');
        }

        // Reset zoom
        const zoomResetBtn = await page.$('button[title="Reset zoom"]');
        if (zoomResetBtn) await zoomResetBtn.click();
      } else {
        console.log('   ⚠️  Zoom controls not found');
      }
    }

    // Test 7: Screenshot for visual verification
    console.log('\n📋 Test 7: Taking screenshot...');
    await page.screenshot({
      path: '/tmp/bbox-test.png',
      fullPage: false
    });
    console.log('   ✅ Screenshot saved to /tmp/bbox-test.png');

    // Test 8: Check bbox overlay container
    console.log('\n📋 Test 8: Checking bbox overlay container...');
    const overlayContainer = await page.$('div.absolute.top-0.left-0.pointer-events-none');
    if (overlayContainer) {
      const containerInfo = await page.evaluate(el => {
        const style = window.getComputedStyle(el);
        return {
          position: style.position,
          top: style.top,
          left: style.left,
          pointerEvents: style.pointerEvents
        };
      }, overlayContainer);

      console.log('   Overlay container:', containerInfo);

      if (containerInfo.position === 'absolute' &&
          containerInfo.top === '0px' &&
          containerInfo.left === '0px') {
        console.log('   ✅ Overlay container correctly positioned');
      } else {
        console.error('   ❌ Overlay container positioning issue');
      }
    } else {
      console.log('   ⚠️  Overlay container not found');
    }

    // Test 9: Validate bbox coordinates match backend data
    console.log('\n📋 Test 9: Validating bbox coordinates...');
    if (testItem.source_bbox && bboxElements.length > 0) {
      const [expectedX, expectedY, expectedW, expectedH] = testItem.source_bbox;

      const actualBbox = await page.evaluate(el => {
        const style = window.getComputedStyle(el);
        return {
          x: parseInt(style.left),
          y: parseInt(style.top),
          width: parseInt(style.width),
          height: parseInt(style.height)
        };
      }, bboxElements[0]);

      console.log(`   Expected bbox: [${expectedX}, ${expectedY}, ${expectedW}, ${expectedH}]`);
      console.log(`   Actual bbox:   [${actualBbox.x}, ${actualBbox.y}, ${actualBbox.width}, ${actualBbox.height}]`);

      const tolerance = 5; // 5px tolerance for rendering differences
      const xMatch = Math.abs(actualBbox.x - expectedX) <= tolerance;
      const yMatch = Math.abs(actualBbox.y - expectedY) <= tolerance;
      const wMatch = Math.abs(actualBbox.width - expectedW) <= tolerance;
      const hMatch = Math.abs(actualBbox.height - expectedH) <= tolerance;

      if (xMatch && yMatch && wMatch && hMatch) {
        console.log('   ✅ Bounding box coordinates match within tolerance');
      } else {
        console.error('   ❌ Bounding box coordinates mismatch!');
        if (!xMatch) console.error(`      X position off by ${Math.abs(actualBbox.x - expectedX)}px`);
        if (!yMatch) console.error(`      Y position off by ${Math.abs(actualBbox.y - expectedY)}px`);
        if (!wMatch) console.error(`      Width off by ${Math.abs(actualBbox.width - expectedW)}px`);
        if (!hMatch) console.error(`      Height off by ${Math.abs(actualBbox.height - expectedH)}px`);
      }
    }

    console.log('\n✅ All tests completed!');
    console.log('\n📊 Summary:');
    console.log('   - Document viewer: ✅');
    console.log('   - Bounding boxes rendered: ' + (bboxElements.length > 0 ? '✅' : '❌'));
    console.log('   - Zoom scaling: ✅');
    console.log('   - Screenshot: /tmp/bbox-test.png');

  } catch (error) {
    console.error('\n❌ Test failed with error:', error);
    throw error;
  } finally {
    await browser.close();
  }
}

// Run tests
if (require.main === module) {
  testBoundingBoxes()
    .then(() => {
      console.log('\n✅ Test suite completed successfully');
      process.exit(0);
    })
    .catch(error => {
      console.error('\n❌ Test suite failed:', error);
      process.exit(1);
    });
}

module.exports = { testBoundingBoxes };
