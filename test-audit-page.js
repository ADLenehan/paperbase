const puppeteer = require('puppeteer');

async function testAuditPage() {
    console.log('🧪 Testing Audit Page after bbox fix...\n');

    const browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();

    // Collect errors
    const errors = [];
    page.on('pageerror', error => {
        errors.push(error.toString());
        console.log(`❌ [PAGE ERROR] ${error.toString()}`);
    });

    // Collect console errors
    const consoleErrors = [];
    page.on('console', msg => {
        if (msg.type() === 'error') {
            consoleErrors.push(msg.text());
            console.log(`❌ [CONSOLE ERROR] ${msg.text()}`);
        }
    });

    try {
        console.log('📍 Navigating to http://localhost:3000/audit/document/75\n');

        await page.goto('http://localhost:3000/audit/document/75', {
            waitUntil: 'networkidle0',
            timeout: 15000
        });

        // Wait for React to render
        await new Promise(resolve => setTimeout(resolve, 3000));

        // Check if page has content
        const pageContent = await page.evaluate(() => {
            const root = document.getElementById('root');
            return {
                hasContent: root?.children?.length > 0,
                bodyText: document.body.innerText.substring(0, 200),
                hasAuditContent: document.body.innerText.includes('Audit') || document.body.innerText.includes('Queue'),
            };
        });

        console.log('\n📊 Test Results:');
        console.log(`  - Page Errors: ${errors.length}`);
        console.log(`  - Console Errors: ${consoleErrors.length}`);
        console.log(`  - Has Content: ${pageContent.hasContent}`);
        console.log(`  - Has Audit Content: ${pageContent.hasAuditContent}`);
        console.log(`  - Preview: "${pageContent.bodyText}..."\n`);

        if (errors.length === 0 && consoleErrors.filter(e => e.includes('iterable')).length === 0) {
            console.log('✅ SUCCESS! Page loads without bbox errors!\n');
            await browser.close();
            process.exit(0);
        } else {
            console.log('❌ FAILED - Still seeing errors\n');
            await browser.close();
            process.exit(1);
        }

    } catch (error) {
        console.error('💥 Test failed:', error.message);
        await browser.close();
        process.exit(1);
    }
}

testAuditPage();
