const puppeteer = require('puppeteer');

async function diagnoseFrontend() {
    console.log('🔍 Starting frontend diagnostics...\n');

    const browser = await puppeteer.launch({
        headless: false, // Show browser for debugging
        devtools: true,  // Open devtools
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();

    // Collect console messages
    const consoleMessages = [];
    page.on('console', msg => {
        const type = msg.type();
        const text = msg.text();
        consoleMessages.push({ type, text });
        console.log(`[CONSOLE ${type.toUpperCase()}] ${text}`);
    });

    // Collect errors
    const errors = [];
    page.on('pageerror', error => {
        errors.push(error.toString());
        console.log(`[PAGE ERROR] ${error.toString()}`);
    });

    // Collect failed requests
    const failedRequests = [];
    page.on('requestfailed', request => {
        failedRequests.push({
            url: request.url(),
            failure: request.failure()
        });
        console.log(`[REQUEST FAILED] ${request.url()}`);
    });

    // Collect network requests
    const requests = [];
    page.on('response', async response => {
        const url = response.url();
        const status = response.status();

        if (url.includes('/api/')) {
            requests.push({ url, status });
            console.log(`[API CALL] ${status} ${url}`);

            // Log response body for audit API
            if (url.includes('/api/audit/')) {
                try {
                    const body = await response.text();
                    console.log(`[API RESPONSE] ${body.substring(0, 200)}...`);
                } catch (e) {
                    console.log(`[API RESPONSE] Could not read body: ${e.message}`);
                }
            }
        }
    });

    try {
        console.log('\n📍 Navigating to http://localhost:3000/audit/document/75\n');

        await page.goto('http://localhost:3000/audit/document/75', {
            waitUntil: 'networkidle0',
            timeout: 30000
        });

        // Wait a bit for React to render
        await page.waitForTimeout(2000);

        console.log('\n📊 Checking page state...\n');

        // Check if React root has content
        const rootContent = await page.evaluate(() => {
            const root = document.getElementById('root');
            return {
                exists: !!root,
                innerHTML: root?.innerHTML?.substring(0, 500),
                children: root?.children?.length,
                hasText: root?.innerText?.length
            };
        });

        console.log('Root element:', JSON.stringify(rootContent, null, 2));

        // Check React errors
        const reactErrors = await page.evaluate(() => {
            return window.__REACT_ERROR__ || null;
        });

        if (reactErrors) {
            console.log('\n❌ React Errors:', reactErrors);
        }

        // Check loading state
        const pageState = await page.evaluate(() => {
            return {
                url: window.location.href,
                title: document.title,
                bodyClasses: document.body.className,
                hasLoadingSpinner: !!document.querySelector('.animate-spin'),
                hasErrorMessage: !!document.querySelector('[class*="error"]'),
                visibleText: document.body.innerText.substring(0, 500)
            };
        });

        console.log('\n📄 Page State:', JSON.stringify(pageState, null, 2));

        // Try to find specific Audit component elements
        const auditElements = await page.evaluate(() => {
            return {
                hasQueue: document.body.innerText.includes('Queue'),
                hasAudit: document.body.innerText.includes('Audit'),
                hasCaughtUp: document.body.innerText.includes('All Caught Up'),
                hasLoading: document.body.innerText.includes('Loading'),
                bodyText: document.body.innerText
            };
        });

        console.log('\n🎯 Audit Component Check:', JSON.stringify(auditElements, null, 2));

        // Take screenshot
        await page.screenshot({ path: '/tmp/audit-page.png', fullPage: true });
        console.log('\n📸 Screenshot saved to /tmp/audit-page.png');

        console.log('\n📊 Summary:');
        console.log(`  - Console messages: ${consoleMessages.length}`);
        console.log(`  - Page errors: ${errors.length}`);
        console.log(`  - Failed requests: ${failedRequests.length}`);
        console.log(`  - API calls: ${requests.length}`);

        if (errors.length > 0) {
            console.log('\n❌ Errors found:');
            errors.forEach((err, i) => console.log(`  ${i + 1}. ${err}`));
        }

        if (failedRequests.length > 0) {
            console.log('\n❌ Failed requests:');
            failedRequests.forEach((req, i) => {
                console.log(`  ${i + 1}. ${req.url}`);
                console.log(`     Failure: ${req.failure?.errorText}`);
            });
        }

        // Keep browser open for manual inspection
        console.log('\n⏸️  Browser will stay open for 30 seconds for manual inspection...');
        await page.waitForTimeout(30000);

    } catch (error) {
        console.error('\n💥 Fatal error:', error);
    } finally {
        await browser.close();
        console.log('\n✅ Diagnostics complete');
    }
}

diagnoseFrontend().catch(console.error);
