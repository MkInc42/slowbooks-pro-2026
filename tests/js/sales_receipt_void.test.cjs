// Void Receipt on the Sales Receipts page voids the payment, then the
// receipt. A receipt brought in from QuickBooks Online is voided with its
// payment (2.18.0), so the page voids the receipt only when it is still open.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

function page({ voidedWithPayment }) {
    const calls = [], toasts = [];
    let receiptStatus = 'paid';
    const receipt = () => ({ id: 9, customer_id: 3, status: receiptStatus });
    const context = {
        confirm: () => true, closeModal() {}, location: { hash: '#/sales-receipts' }, window: {},
        App: { navigate() {}, refresh() {} },
        toast: (message, kind) => toasts.push([message, kind || 'ok']),
        API: {
            get: async url => {
                if (url === '/invoices/9') return receipt();
                if (url.startsWith('/payments?')) return [{ id: 4, is_voided: false, allocations: [{ invoice_id: 9 }] }];
                throw new Error('unexpected ' + url);
            },
            post: async url => {
                calls.push(url);
                if (url === '/payments/4/void' && voidedWithPayment) receiptStatus = 'void';
                if (url === '/invoices/9/void') {
                    if (receiptStatus === 'void') throw new Error('Invoice already voided');
                    receiptStatus = 'void';
                }
                return {};
            },
        },
    };
    // utils.js's fetchAllPages: every page of a list (one page here)
    context.fetchAllPages = url => context.API.get(url);
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/static/js/sales_receipts.js'), 'utf8') + '\nthis.SalesReceiptsPage = SalesReceiptsPage;', context);
    return { page: context.SalesReceiptsPage, calls, toasts };
}

test('a receipt from QuickBooks Online is voided with its payment, with no error', async () => {
    const f = page({ voidedWithPayment: true });
    await f.page.void(9);
    assert.deepEqual(f.calls, ['/payments/4/void']);
    assert.deepEqual(f.toasts, [['Sales receipt voided', 'ok']]);
});

test('any other receipt is voided after its payment', async () => {
    const f = page({ voidedWithPayment: false });
    await f.page.void(9);
    assert.deepEqual(f.calls, ['/payments/4/void', '/invoices/9/void']);
    assert.deepEqual(f.toasts, [['Sales receipt voided', 'ok']]);
});
