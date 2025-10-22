// Test script to debug the upload issue
const fs = require('fs');
const path = require('path');

async function testUpload() {
    console.log('Testing upload endpoint...');

    // Create a simple test file
    const testFilePath = '/tmp/test-upload.txt';
    fs.writeFileSync(testFilePath, 'Test document content\nInvoice #123\nAmount: $500');

    const FormData = require('form-data');
    const form = new FormData();
    form.append('files', fs.createReadStream(testFilePath), {
        filename: 'test-document.txt',
        contentType: 'text/plain'
    });

    try {
        const response = await fetch('http://localhost:8000/api/bulk/upload-and-analyze', {
            method: 'POST',
            body: form,
            headers: form.getHeaders()
        });

        console.log('Status:', response.status);
        console.log('Status Text:', response.statusText);

        const text = await response.text();
        console.log('Response:', text);

        if (!response.ok) {
            console.error('ERROR: Request failed');
        } else {
            console.log('SUCCESS: Upload completed');
        }
    } catch (error) {
        console.error('FETCH ERROR:', error.message);
        console.error('Stack:', error.stack);
    }
}

testUpload();
