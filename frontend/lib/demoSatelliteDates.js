/** Instant demo satellite dates (no API wait). Matches backend DEMO_AVAILABLE_DATES. */
export const DEMO_SATELLITE_DATES = [
  '2024-09-01',
  '2024-09-05',
  '2024-09-10',
  '2024-09-15',
  '2024-09-20',
  '2024-09-25',
  '2024-10-01',
  '2024-10-05',
  '2024-10-10',
  '2024-10-15',
  '2024-10-20',
  '2024-10-22',
  '2024-10-25',
  '2024-10-30',
  '2024-11-01',
  '2024-11-05',
  '2024-11-10',
  '2024-11-15',
  '2024-11-20',
  '2024-11-25',
];

export const DEMO_DATE_CLOUD_COVER = Object.fromEntries(
  DEMO_SATELLITE_DATES.map((date, i) => [date, 3 + (i % 5)]),
);