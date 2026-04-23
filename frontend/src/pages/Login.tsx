import { FormEvent, useEffect, useMemo, useState } from "react";
import { Languages, Loader2, Moon, ShieldCheck, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { getErrorMessage } from "@/api/client";
import { changeAppLanguage } from "@/i18n";
import { getPublicFeatures, login, register } from "@/api/user";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useTheme } from "@/hooks/use-theme";
import { useUserStore } from "@/store/useUserStore";

type AuthMode = "login" | "register";

export default function LoginPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();
  const setLogin = useUserStore((state) => state.login);

  const [mode, setMode] = useState<AuthMode>("login");
  const [allowRegistration, setAllowRegistration] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isFeatureLoading, setIsFeatureLoading] = useState(true);
  const [error, setError] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [inviteCode, setInviteCode] = useState("");

  useEffect(() => {
    async function loadFeatures() {
      setIsFeatureLoading(true);
      try {
        const features = await getPublicFeatures();
        setAllowRegistration(Boolean(features.allow_registration));
      } catch {
        setAllowRegistration(false);
      } finally {
        setIsFeatureLoading(false);
      }
    }

    void loadFeatures();
  }, []);

  useEffect(() => {
    if (!allowRegistration && mode === "register") {
      setMode("login");
    }
  }, [allowRegistration, mode]);

  const submitLabel = useMemo(() => {
    if (isLoading) {
      return mode === "login" ? t("login.submitting") : t("login.registerSubmitting");
    }
    return mode === "login" ? t("login.submit") : t("login.registerSubmit");
  }, [isLoading, mode, t]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const data =
        mode === "login"
          ? await login(username, password)
          : await register({
              username,
              password,
              email: email.trim() || null,
              invite_code: inviteCode.trim(),
            });
      setLogin(data);
      navigate("/cocoons", { replace: true });
    } catch (error) {
      const message = getErrorMessage(error);
      setError(message && !message.startsWith("Request failed with status") ? message : mode === "login" ? t("login.error") : t("login.registerError"));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-10 text-foreground transition-colors duration-300">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(14,116,144,0.15),_transparent_35%),radial-gradient(circle_at_bottom,_rgba(190,24,93,0.1),_transparent_30%)]" />

      <div className="fixed top-6 right-6 z-20 flex gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => void changeAppLanguage(i18n.resolvedLanguage === "zh" ? "en" : "zh")}
        >
          <Languages className="h-5 w-5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          <span className="inline-flex transition-transform duration-200 ease-out">
            {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </span>
        </Button>
      </div>

      <div className="relative z-10">
        <Card className="w-full min-w-0 max-w-2xl border-border/60 bg-card/85 shadow-2xl backdrop-blur-sm md:min-w-[42rem]">
          <CardHeader className="space-y-3 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-primary/20 bg-primary/10">
              <ShieldCheck className="h-6 w-6 text-primary" />
            </div>
            <div>
              <CardTitle className="text-2xl font-bold tracking-tight">
                {mode === "login" ? t("login.title") : t("login.registerTitle")}
              </CardTitle>
              <CardDescription className="mt-2">
                {mode === "login" ? t("login.description") : t("login.registerDescription")}
              </CardDescription>
            </div>
          </CardHeader>

          <form onSubmit={onSubmit}>
            <CardContent className="grid gap-5">
              {allowRegistration && !isFeatureLoading ? (
                <div className="flex rounded-xl border border-border/70 bg-background/60 p-1">
                  <Button type="button" variant={mode === "login" ? "default" : "ghost"} className="flex-1" onClick={() => setMode("login")}>
                    {t("login.modeLogin")}
                  </Button>
                  <Button type="button" variant={mode === "register" ? "default" : "ghost"} className="flex-1" onClick={() => setMode("register")}>
                    {t("login.modeRegister")}
                  </Button>
                </div>
              ) : null}

              <div className="grid gap-2">
                <Label htmlFor="username" className="text-muted-foreground">
                  {t("login.placeholderUser")}
                </Label>
                <Input
                  id="username"
                  type="text"
                  required
                  className="h-11 bg-background"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                />
              </div>

              {mode === "register" ? (
                <>
                  <div className="grid gap-2">
                    <Label htmlFor="email">{t("common.email")}</Label>
                    <Input
                      id="email"
                      type="email"
                      className="h-11 bg-background"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="invite-code">{t("login.inviteCode")}</Label>
                    <Input
                      id="invite-code"
                      type="text"
                      required
                      className="h-11 bg-background"
                      value={inviteCode}
                      onChange={(event) => setInviteCode(event.target.value)}
                    />
                  </div>
                </>
              ) : null}

              <div className="grid gap-2">
                <Label htmlFor="password">{t("login.placeholderPass")}</Label>
                <Input
                  id="password"
                  type="password"
                  required
                  minLength={mode === "register" ? 8 : undefined}
                  className="h-11 bg-background"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </div>

              {mode === "register" ? (
                <div className="rounded-xl border border-dashed border-border/70 bg-muted/40 px-4 py-3 text-left text-sm text-muted-foreground">
                  <div>{t("login.registerHint")}</div>
                  <div>{t("login.registerInviteHint")}</div>
                </div>
              ) : null}

              {error ? <Label className="text-red-500">{error}</Label> : null}
            </CardContent>

            <CardFooter className="flex flex-col gap-4">
              <Button className="h-11 w-full text-base font-semibold transition-all active:scale-[0.98]" type="submit" disabled={isLoading || isFeatureLoading}>
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {submitLabel}
                  </>
                ) : (
                  submitLabel
                )}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}
