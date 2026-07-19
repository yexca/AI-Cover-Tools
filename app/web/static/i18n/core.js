(() => {
  'use strict';

  const STORAGE_KEY = 'audioflow:locale';
  const SYSTEM = 'system';
  const DEFAULT_LOCALE = 'en';
  const SUPPORTED_LOCALES = Object.freeze(['zh-CN', 'ja', 'en']);
  const SUPPORTED_PREFERENCES = new Set([SYSTEM, ...SUPPORTED_LOCALES]);
  const locales = window.AudioFlowLocales || (window.AudioFlowLocales = {});

  function normalizeLanguage(value) {
    const language = String(value || '').trim().replace(/_/g, '-').toLowerCase();
    if (language === 'zh' || language.startsWith('zh-')) return 'zh-CN';
    if (language === 'ja' || language.startsWith('ja-')) return 'ja';
    if (language === 'en' || language.startsWith('en-')) return 'en';
    return null;
  }

  function browserLanguages() {
    const values = Array.isArray(navigator.languages) && navigator.languages.length
      ? navigator.languages
      : [navigator.language];
    return values.filter(Boolean);
  }

  function resolveLocale(values = browserLanguages()) {
    const languages = Array.isArray(values) ? values : [values];
    for (const language of languages) {
      const resolved = normalizeLanguage(language);
      if (resolved) return resolved;
    }
    return DEFAULT_LOCALE;
  }

  function readPreference() {
    try {
      const value = localStorage.getItem(STORAGE_KEY);
      return SUPPORTED_PREFERENCES.has(value) ? value : SYSTEM;
    } catch {
      return SYSTEM;
    }
  }

  function writePreference(value) {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Storage can be unavailable in private or locked-down browser contexts.
    }
  }

  let preference = readPreference();
  let locale = preference === SYSTEM ? resolveLocale() : preference;
  let numberFormatter = null;
  let timeFormatter = null;
  let dateTimeFormatter = null;
  let pluralRules = null;

  function resetFormatters() {
    numberFormatter = null;
    timeFormatter = null;
    dateTimeFormatter = null;
    pluralRules = null;
  }

  function interpolate(template, params) {
    return String(template).replace(/\{([a-zA-Z0-9_]+)\}/g, (match, name) => (
      Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match
    ));
  }

  function t(key, params = {}) {
    const active = locales[locale] || locales[DEFAULT_LOCALE] || {};
    const fallback = locales[DEFAULT_LOCALE] || {};
    const template = active[key] ?? fallback[key] ?? key;
    return interpolate(template, params);
  }

  function formatNumber(value, options = {}) {
    if (Object.keys(options).length) return new Intl.NumberFormat(locale, options).format(value);
    numberFormatter ||= new Intl.NumberFormat(locale);
    return numberFormatter.format(value);
  }

  function formatTime(value = new Date(), options = {}) {
    const date = value instanceof Date ? value : new Date(value);
    const defaults = { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
    if (Object.keys(options).length) return new Intl.DateTimeFormat(locale, options).format(date);
    timeFormatter ||= new Intl.DateTimeFormat(locale, defaults);
    return timeFormatter.format(date);
  }

  function formatDateTime(value, options = {}) {
    const date = value instanceof Date ? value : new Date(value);
    const defaults = { dateStyle: 'medium', timeStyle: 'medium' };
    if (Object.keys(options).length) return new Intl.DateTimeFormat(locale, options).format(date);
    dateTimeFormatter ||= new Intl.DateTimeFormat(locale, defaults);
    return dateTimeFormatter.format(date);
  }

  function plural(key, count, params = {}) {
    pluralRules ||= new Intl.PluralRules(locale);
    const category = pluralRules.select(Number(count));
    const active = locales[locale] || {};
    const fallback = locales[DEFAULT_LOCALE] || {};
    const selectedKey = active[`${key}.${category}`] !== undefined || fallback[`${key}.${category}`] !== undefined
      ? `${key}.${category}`
      : `${key}.other`;
    return t(selectedKey, { ...params, count: formatNumber(count) });
  }

  function elementsFor(root, attribute) {
    const values = [];
    if (root instanceof Element && root.hasAttribute(attribute)) values.push(root);
    if (root?.querySelectorAll) values.push(...root.querySelectorAll(`[${attribute}]`));
    return values;
  }

  function applyDocumentTranslations(root = document) {
    elementsFor(root, 'data-i18n').forEach(element => {
      element.textContent = t(element.dataset.i18n);
    });
    elementsFor(root, 'data-i18n-placeholder').forEach(element => {
      element.setAttribute('placeholder', t(element.dataset.i18nPlaceholder));
    });
    elementsFor(root, 'data-i18n-title').forEach(element => {
      element.setAttribute('title', t(element.dataset.i18nTitle));
    });
    elementsFor(root, 'data-i18n-aria-label').forEach(element => {
      element.setAttribute('aria-label', t(element.dataset.i18nAriaLabel));
    });
    document.documentElement.lang = locale;
  }

  function bindLocaleSelect(root = document) {
    elementsFor(root, 'data-i18n-locale-select').forEach(select => {
      select.value = preference;
      if (select.dataset.i18nLocaleBound === 'true') return;
      select.dataset.i18nLocaleBound = 'true';
      select.addEventListener('change', () => setLocale(select.value));
    });
  }

  function updateLocale(nextPreference, persist, emit) {
    const safePreference = SUPPORTED_PREFERENCES.has(nextPreference) ? nextPreference : SYSTEM;
    const nextLocale = safePreference === SYSTEM ? resolveLocale() : safePreference;
    const changed = preference !== safePreference || locale !== nextLocale;
    preference = safePreference;
    locale = nextLocale;
    if (persist) writePreference(preference);
    resetFormatters();
    applyDocumentTranslations();
    bindLocaleSelect();
    elementsFor(document, 'data-i18n-locale-select').forEach(select => { select.value = preference; });
    if (emit && changed) {
      window.dispatchEvent(new CustomEvent('audioflow:localechange', {
        detail: { locale, preference }
      }));
    }
    return locale;
  }

  function setLocale(nextPreference) {
    return updateLocale(nextPreference, true, true);
  }

  function initialize() {
    updateLocale(preference, false, false);
  }

  const api = Object.freeze({
    STORAGE_KEY,
    SYSTEM,
    SUPPORTED_LOCALES,
    resolveLocale,
    getLocale: () => locale,
    getPreference: () => preference,
    setLocale,
    t,
    plural,
    formatNumber,
    formatTime,
    formatDateTime,
    applyDocumentTranslations,
    bindLocaleSelect
  });

  window.AudioFlowI18n = api;
  window.addEventListener('languagechange', () => {
    if (preference === SYSTEM) updateLocale(SYSTEM, false, true);
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
})();
