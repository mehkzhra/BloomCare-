import { useEffect } from 'react';
import { setLanguage, useLanguage, t } from './i18n.js';
export function LanguageSelector() {
  const language = useLanguage();
  useEffect(() => { document.documentElement.lang = language; document.documentElement.dir = language === 'ur' ? 'rtl' : 'ltr'; }, [language]);
  return <label className="language-selector"><span>{t('Language')}</span><select value={language} onChange={e => setLanguage(e.target.value)} aria-label="Language">
    <option value="en">English</option><option value="ur">اردو</option>
  </select></label>;
}
