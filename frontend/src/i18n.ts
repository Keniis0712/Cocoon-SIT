import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

const supportedLanguages = ["zh", "en"] as const;
const namespaces = [
  "common",
  "nav",
  "login",
  "me",
  "users",
  "characters",
  "groups",
  "invites",
  "merges",
  "settings",
  "tags",
  "prompts",
  "cocoons",
  "workspace",
  "audits",
  "insights",
  "chatGroups",
  "providers",
  "wakeups",
  "plugins",
] as const;
type SupportedLanguage = (typeof supportedLanguages)[number];
type Namespace = (typeof namespaces)[number];

const localeModules = import.meta.glob("./locales/*/*.json");

function normalizeLanguage(language: string | readonly string[] | undefined | null): SupportedLanguage {
  const value = Array.isArray(language) ? language[0] : language;
  if (typeof value !== "string") {
    return "zh";
  }
  return value.toLowerCase().startsWith("en") ? "en" : "zh";
}

async function loadNamespace(language: SupportedLanguage, namespace: Namespace) {
  const key = `./locales/${language}/${namespace}.json`;
  const loader = localeModules[key];
  if (!loader) {
    throw new Error(`Missing locale namespace: ${key}`);
  }
  const module = await loader();
  return (module as { default: Record<string, unknown> }).default;
}

async function loadTranslations(language: SupportedLanguage) {
  const entries = await Promise.all(
    namespaces.map(async (namespace) => [namespace, await loadNamespace(language, namespace)] as const),
  );
  const resources = Object.fromEntries(entries) as Record<Namespace, Record<string, unknown>>;
  const translation = Object.fromEntries(entries) as Record<string, Record<string, unknown>>;
  return {
    ...resources,
    translation,
  };
}

export async function ensureLanguageResources(language: string) {
  const normalized = normalizeLanguage(language);
  if (!i18n.hasResourceBundle(normalized, "translation")) {
    const bundles = await loadTranslations(normalized);
    for (const namespace of namespaces) {
      i18n.addResourceBundle(normalized, namespace, bundles[namespace], true, true);
    }
    i18n.addResourceBundle(normalized, "translation", bundles.translation, true, true);
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
        [initialLanguage]: initialMessages,
      },
      ns: ["translation", ...namespaces],
      defaultNS: "translation",
      supportedLngs: [...supportedLanguages],
      fallbackLng: "zh",
      interpolation: {
        escapeValue: false,
      },
    });

  return i18n;
}

export default i18n;
