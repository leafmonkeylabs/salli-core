import { describe, expect, it } from 'vitest';
import { balancesOf, goalsOf, incomesOf } from '../src/lib/firstrun';

describe('first run', () => {
  it('sends only named lines with an amount, as exact strings, with codes beside the starter chart', () => {
    const own = [{ name: 'Checking', amount: '10,000.50' }, { name: 'Savings', amount: '' }, { name: '', amount: '5' }, { name: 'Brokerage', amount: '1200' }];
    const owe = [{ name: 'Card', amount: '230.10' }];
    expect(balancesOf(own, owe)).toEqual([
      { code: '1500', name: 'Checking', type: 'asset', amount: '10000.50' },
      { code: '1510', name: 'Brokerage', type: 'asset', amount: '1200' },
      { code: '2500', name: 'Card', type: 'liability', amount: '230.10' },
    ]);
  });

  it('pays income into the first account owned, or leaves it to the server', () => {
    const incomes = [{ name: 'Salary', amount: '4000' }];
    expect(incomesOf(incomes, [{ name: 'Checking', amount: '10' }])).toEqual([
      { code: '4700', name: 'Salary', amount: '4000', deposit_account_code: '1500', deposit_account_name: 'Checking' },
    ]);
    expect(incomesOf(incomes, [])).toEqual([{ code: '4700', name: 'Salary', amount: '4000' }]);
  });

  it('keeps goals by name, with an amount and a year when given', () => {
    expect(goalsOf([{ name: 'House', amount: '40000', date: '2029' }, { name: 'Trip', amount: 'soon', date: '' }, { name: '', amount: '1', date: '' }])).toEqual([
      { name: 'House', target_amount: '40000', target_date: '2029-12-31' },
      { name: 'Trip' },
    ]);
  });
});
