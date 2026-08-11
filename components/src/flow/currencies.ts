// Currency definitions for airtime transfers
// Based on the original React implementation

export interface Currency {
  code: string;
  name: string;
}

export const CURRENCIES: Record<string, Currency> = {
  ARS: { code: 'ARS', name: 'Argentine Peso' },
  AUD: { code: 'AUD', name: 'Australian Dollar' },
  BIF: { code: 'BIF', name: 'Burundi Franc' },
  BRL: { code: 'BRL', name: 'Brazilian Real' },
  CAD: { code: 'CAD', name: 'Canadian Dollar' },
  CDF: { code: 'CDF', name: 'Congolese Franc' },
  CLP: { code: 'CLP', name: 'Chilean Peso' },
  COP: { code: 'COP', name: 'Colombian Peso' },
  DJF: { code: 'DJF', name: 'Djibouti Franc' },
  DOP: { code: 'DOP', name: 'Dominican Peso' },
  DZD: { code: 'DZD', name: 'Algerian Dinar' },
  EUR: { code: 'EUR', name: 'Euro' },
  GBP: { code: 'GBP', name: 'Pound Sterling' },
  GHS: { code: 'GHS', name: 'Ghana Cedi' },
  GNF: { code: 'GNF', name: 'Guinean Franc' },
  KES: { code: 'KES', name: 'Kenyan Shilling' },
  LBP: { code: 'LBP', name: 'Lebanese Pound' },
  LKR: { code: 'LKR', name: 'Sri Lanka Rupee' },
  LRD: { code: 'LRD', name: 'Liberian Dollar' },
  MWK: { code: 'MWK', name: 'Malawian Kwacha' },
  MXN: { code: 'MXN', name: 'Mexican Peso' },
  MZN: { code: 'MZN', name: 'Mozambican Metical' },
  NAD: { code: 'NAD', name: 'Namibian Dollar' },
  NGN: { code: 'NGN', name: 'Nigerian Naira' },
  PEN: { code: 'PEN', name: 'Peruvian Sol' },
  PHP: { code: 'PHP', name: 'Philippine Peso' },
  RWF: { code: 'RWF', name: 'Rwandan Franc' },
  SZL: { code: 'SZL', name: 'Swazi Lilangeni' },
  TZS: { code: 'TZS', name: 'Tanzanian Shilling' },
  UGX: { code: 'UGX', name: 'Ugandan Shilling' },
  USD: { code: 'USD', name: 'US Dollar' },
  XAF: { code: 'XAF', name: 'Central African CFA Franc' },
  XOF: { code: 'XOF', name: 'West African CFA Franc' },
  ZAR: { code: 'ZAR', name: 'South African Rand' },
  ZMW: { code: 'ZMW', name: 'Zambian Kwacha' }
};

// Convert currencies to select options format
export const CURRENCY_OPTIONS = Object.values(CURRENCIES).map((currency) => ({
  value: currency.code,
  name: `${currency.name} (${currency.code})`
}));
