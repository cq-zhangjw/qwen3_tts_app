import { createI18n, type I18nOptions } from 'vue-i18n';

type LocaleMessages = Record<string, any>;

const loadLocaleMessages = async (): Promise<LocaleMessages> => {
  const locales = await Promise.all([
    import('../public/locales/en.json'),
    import('../public/locales/zh.json'),
    import('../public/locales/ja.json')
  ]);
  const messages: LocaleMessages = {};
  const langCodes = ['en', 'zh', 'ja'];
  locales.forEach((locale, index) => {
    const lang = langCodes[index];
    messages[lang] = locale.default;
  });
  return messages;
};
const getBrowserLocale = () => {
  const navigatorLocale = navigator.language || (navigator as any).userLanguage;
  return navigatorLocale.split('-')[0];
};

const browserLocale = getBrowserLocale();
const availableLocales = ['en', 'zh', 'ja'];
const defaultLocale = availableLocales.includes(browserLocale) ? browserLocale : 'en';

const i18nOptions: I18nOptions = {
  legacy: false,
  locale: defaultLocale,
  fallbackLocale: 'en',
  messages: await loadLocaleMessages()
};

const i18n = createI18n(i18nOptions);

export default i18n;
    