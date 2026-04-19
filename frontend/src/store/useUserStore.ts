import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { SessionUser } from "@/api/user";

type UserState = {
  userInfo: SessionUser | null;
  isLoggedIn: boolean;
  login: (data: SessionUser) => void;
  logout: () => void;
  updateInfo: (data: Partial<SessionUser>) => void;
  getToken: () => string | null;
};

export const useUserStore = create<UserState>()(
  persist(
    (set, get) => ({
      userInfo: null,
      isLoggedIn: false,
      login: (data) =>
        set({
          userInfo: data,
          isLoggedIn: true,
        }),
      logout: () =>
        set({
          userInfo: null,
          isLoggedIn: false,
        }),
      updateInfo: (data) =>
        set((state) => ({
          userInfo: state.userInfo ? { ...state.userInfo, ...data } : null,
        })),
      getToken: () => get().userInfo?.access_token ?? null,
    }),
    {
      name: "user-storage-v2",
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
