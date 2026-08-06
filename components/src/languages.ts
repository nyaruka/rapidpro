const intlLanguageNames = new Intl.DisplayNames(['en'], {
  type: 'language',
  fallback: 'none'
});

const ADDITIONAL_LANGUAGE_NAMES: { [code: string]: string } = {
  aab: 'Alumu-Tesu',
  aac: 'Ari',
  aas: 'Aasáx',
  abp: 'Abellen Ayta',
  acf: 'Saint Lucian Creole French',
  aec: 'Saidi Arabic',
  afb: 'Gulf Arabic',
  apd: 'Sudanese Arabic',
  ayl: 'Libyan Arabic',
  blk: "Pa'o Karen",
  bog: 'Bamako Sign Language',
  bzs: 'Brazilian Sign Language',
  csn: 'Colombian Sign Language',
  dag: 'Dagbani',
  ecs: 'Ecuadorian Sign Language',
  frk: 'Frankish',
  fsl: 'French Sign Language',
  fuv: 'Nigerian Fulfulde',
  gcr: 'Guianese Creole French',
  gpe: 'Ghanaian Pidgin English',
  gux: 'Gourmanchéma',
  ise: 'Italian Sign Language',
  ksw: "S'gaw Karen",
  kun: 'Kunama',
  kyu: 'Western Kayah',
  laj: 'Lango',
  nyj: 'Nyanga',
  prd: 'Parsi-Dari',
  prl: 'Peruvian Sign Language',
  pst: 'Central Pashto',
  rop: 'Kriol',
  tdt: 'Tetun Dili',
  toi: 'Tonga',
  tuv: 'Turkana',
  vsl: 'Venezuelan Sign Language'
};

export function getLanguageName(code: string): string {
  if (!code) return '';
  if (code === 'und') return 'Unknown';

  try {
    const name = intlLanguageNames.of(code);
    if (name) return name;
  } catch {
    // fall through to additional lookup
  }

  return ADDITIONAL_LANGUAGE_NAMES[code] || code;
}
