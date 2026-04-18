import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

const supportedLanguages = ["zh", "en"] as const;
type SupportedLanguage = (typeof supportedLanguages)[number];

function normalizeLanguage(language: string | readonly string[] | undefined | null): SupportedLanguage {
  const value = Array.isArray(language) ? language[0] : language;
  if (typeof value !== "string") {
    return "zh";
  }
  return value.toLowerCase().startsWith("en") ? "en" : "zh";
}

async function loadTranslations(language: SupportedLanguage) {
  if (language === "en") {
    return (await import("./locales/en.json")).default;
  }
  return (await import("./locales/zh.json")).default;
}

export async function ensureLanguageResources(language: string) {
  const normalized = normalizeLanguage(language);
  if (!i18n.hasResourceBundle(normalized, "translation")) {
    const messages = await loadTranslations(normalized);
    i18n.addResourceBundle(normalized, "translation", messages, true, true);
  }
  return normalized;
}

export async function changeAppLanguage(language: string) {
  const normalized = await ensureLanguageResources(language);
  await i18n.changeLanguage(normalized);
}

export async function initializeI18n() {
  if (i18n.isInitialized) {
    return i18n;
  }

  const detector = new LanguageDetector();
  detector.init();
  const initialLanguage = normalizeLanguage(detector.detect());
  const initialMessages = await loadTranslations(initialLanguage);

  await i18n
    .use(LanguageDetector)
    .use(initReactI18next)
    .init({
      lng: initialLanguage,
      resources: {
        [initialLanguage]: {
          translation: initialMessages,
        },
      },
      supportedLngs: [...supportedLanguages],
      fallbackLng: "zh",
      interpolation: {
        escapeValue: false,
      },
    });

  return i18n;
}

export default i18n;
