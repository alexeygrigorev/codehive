import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import type { ReactNode } from "react";
import {
  loginUser,
  registerUser,
  refreshToken as refreshTokenApi,
  getMe,
} from "@/api/auth";
import type { UserRead } from "@/api/auth";

const ACCESS_TOKEN_KEY = "codehive_access_token";
const REFRESH_TOKEN_KEY = "codehive_refresh_token";

interface AuthContextValue {
  user: UserRead | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    username: string,
    password: string,
  ) => Promise<void>;
  logout: () => void;
  refreshAccessToken: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<UserRead | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshTokenValue, setRefreshTokenValue] = useState<string | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const storedAccess = localStorage.getItem(ACCESS_TOKEN_KEY);
    const storedRefresh = localStorage.getItem(REFRESH_TOKEN_KEY);

    if (storedAccess && storedRefresh) {
      setAccessToken(storedAccess);
      setRefreshTokenValue(storedRefresh);
      getMe(storedAccess)
        .then((userData) => {
          setUser(userData);
          setIsLoading(false);
        })
        .catch(() => {
          // Token might be expired, try refresh
          refreshTokenApi(storedRefresh)
            .then((tokens) => {
              localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
              localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
              setAccessToken(tokens.access_token);
              setRefreshTokenValue(tokens.refresh_token);
              return getMe(tokens.access_token);
            })
            .then((userData) => {
              setUser(userData);
              setIsLoading(false);
            })
            .catch(() => {
              // Refresh also failed, clear everything
              localStorage.removeItem(ACCESS_TOKEN_KEY);
              localStorage.removeItem(REFRESH_TOKEN_KEY);
              setAccessToken(null);
              setRefreshTokenValue(null);
              setUser(null);
              setIsLoading(false);
            });
        });
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await loginUser(email, password);
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
    setAccessToken(tokens.access_token);
    setRefreshTokenValue(tokens.refresh_token);
    const userData = await getMe(tokens.access_token);
    setUser(userData);
  }, []);

  const register = useCallback(
    async (email: string, username: string, password: string) => {
      const tokens = await registerUser(email, username, password);
      localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
      localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
      setAccessToken(tokens.access_token);
      setRefreshTokenValue(tokens.refresh_token);
      const userData = await getMe(tokens.access_token);
      setUser(userData);
    },
    [],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setAccessToken(null);
    setRefreshTokenValue(null);
    setUser(null);
  }, []);

  const refreshAccessToken = useCallback(async () => {
    const storedRefresh = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!storedRefresh) {
      throw new Error("No refresh token available");
    }
    const tokens = await refreshTokenApi(storedRefresh);
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
    setAccessToken(tokens.access_token);
    setRefreshTokenValue(tokens.refresh_token);
  }, []);

  const value: AuthContextValue = {
    user,
    accessToken,
    refreshToken: refreshTokenValue,
    isAuthenticated: user !== null,
    isLoading,
    login,
    register,
    logout,
    refreshAccessToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
