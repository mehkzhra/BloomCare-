import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, expect, test } from 'vitest';
import { BloodPressureNotice, bloodPressureAction } from './blood-pressure-notice.jsx';
afterEach(cleanup);

test.each([
  [139, 89, null], [140, 80, 'SAME_DAY_MATERNITY_CONTACT'],
  [120, 90, 'SAME_DAY_MATERNITY_CONTACT'], [140, 100, 'SAME_DAY_MATERNITY_CONTACT'],
  [159, 109, 'SAME_DAY_MATERNITY_CONTACT'], [160, 80, 'IMMEDIATE_MATERNITY_REVIEW'],
  [150, 110, 'IMMEDIATE_MATERNITY_REVIEW'], [260, 180, 'IMMEDIATE_MATERNITY_REVIEW'],
  ['', 80, null], [undefined, 80, null], [true, 80, null], [90, 140, null]
])('BP %s/%s produces the appropriate independent action', (systolic, diastolic, expected) => {
  expect(bloodPressureAction({ systolic_mmhg: systolic, diastolic_mmhg: diastolic })).toBe(expected);
});

test('severe recorded readings require immediate care and are not labelled PE HIGH', () => {
  render(<BloodPressureNotice observations={{ systolic_mmhg: 170, diastolic_mmhg: 110, gestational_weeks: 12 }} saved />);
  expect(screen.getByRole('alert')).toHaveTextContent('Seek urgent maternity care now');
  expect(screen.getByRole('alert')).toHaveTextContent('Before 20 weeks');
  expect(screen.getByRole('alert')).toHaveTextContent('not a PE prediction or diagnosis');
  expect(screen.getByRole('alert')).toHaveTextContent('older reading already assessed');
  expect(screen.getByRole('alert')).not.toHaveTextContent('PE HIGH');
});
