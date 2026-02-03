'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { authApi, User, AuthResponse } from './api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string, company?: string) => Promise<void>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      if (token) {
        const userData = await authApi.me();
        setUser(userData);
      }
    } catch (error) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user');
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const response: AuthResponse = await authApi.login(email, password);
    localStorage.setItem('auth_token', response.access_token);
    localStorage.setItem('user', JSON.stringify(response.user));
    setUser({
      id: response.user.id,
      email: response.user.email,
      name: response.user.name,
      company: response.user.company,
      tenant_id: response.user.tenant_id || null,
      is_verified: false,
      created_at: new Date().toISOString(),
    });
  };

  const register = async (email: string, password: string, name: string, company?: string) => {
    const response: AuthResponse = await authApi.register(email, password, name, company);
    localStorage.setItem('auth_token', response.access_token);
    localStorage.setItem('user', JSON.stringify(response.user));
    setUser({
      id: response.user.id,
      email: response.user.email,
      name: response.user.name,
      company: response.user.company,
      tenant_id: response.user.tenant_id || null,
      is_verified: false,
      created_at: new Date().toISOString(),
    });
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      // Ignore errors on logout
    }
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
