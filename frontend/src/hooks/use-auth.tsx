import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, clearToken, fetchMe, getToken, setToken, type AuthUser } from "@/lib/api";

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  signIn: async () => {},
  signUp: async () => {},
  signOut: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    fetchMe()
      .then(setUser)
      .finally(() => setLoading(false));
  }, []);

  const signIn = async (email: string, password: string) => {
    const { access_token } = await api.signIn(email, password);
    setToken(access_token);
    setUser(await api.me());
  };

  const signUp = async (email: string, password: string) => {
    const { access_token } = await api.signUp(email, password);
    setToken(access_token);
    setUser(await api.me());
  };

  const signOut = async () => {
    clearToken();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
