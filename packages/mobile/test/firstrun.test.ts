import { describe, expect, it } from 'vitest';
import { balancesOf, goalsOf, incomesOf, rolesGiven, type Line } from '../src/lib/firstrun';

describe('first run', () => {
  it('sends only named lines with an amount, as exact strings, with codes beside the starter chart', () => {
    const own: Line[] = [
      { name: 'Checking', amount: '10,000.50', role: 'cash' },
      { name: 'Savings', amount: '' },
      { name: '', amount: '5' },
      { name: 'Brokerage', amount: '1200', role: 'investment' },
    ];
    const owe = [{ name: 'Card', amount: '230.10' }];
    expect(balancesOf(own, owe)).toEqual([
      { code: '1500', name: 'Checking', type: 'asset', amount: '10000.50', asset_role: 'cash' },
      { code: '1510', name: 'Brokerage', type: 'asset', amount: '1200', asset_role: 'investment' },
      { code: '2500', name: 'Card', type: 'liability', amount: '230.10' },
    ]);
  });

  it('asks the kind of everything owned before it is sent', () => {
    expect(rolesGiven([{ name: 'Checking', amount: '10' }])).toBe(false);
    expect(rolesGiven([{ name: 'Checking', amount: '10', role: 'cash' }, { name: 'Unfinished', amount: '' }])).toBe(true);
  });

  it('names income sources, with no amount, paid into the first cash account owned', () => {
    const incomes = [{ name: 'Salary', amount: '' }, { name: '', amount: '' }];
    const own: Line[] = [{ name: 'Funds', amount: '900', role: 'investment' }, { name: 'Checking', amount: '10', role: 'cash' }];
    expect(incomesOf(incomes, own)).toEqual([{ code: '4700', name: 'Salary', deposit_account_code: '1510', deposit_account_name: 'Checking' }]);
    expect(incomesOf(incomes, [])).toEqual([{ code: '4700', name: 'Salary' }]);
  });

  it('keeps goals by name, with an amount and a year when given', () => {
    expect(goalsOf([{ name: 'House', amount: '40000', date: '2029' }, { name: 'Trip', amount: 'soon', date: '' }, { name: '', amount: '1', date: '' }])).toEqual([
      { name: 'House', target_amount: '40000', target_date: '2029-12-31' },
      { name: 'Trip' },
    ]);
  });
});
