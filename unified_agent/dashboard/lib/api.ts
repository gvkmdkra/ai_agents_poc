import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export interface User {
  id: number;
  email: string;
  name: string | null;
  company: string | null;
  tenant_id: string | null;
  is_verified: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id: number;
    email: string;
    name: string | null;
    company: string | null;
    tenant_id?: string;
  };
}

export interface Call {
  id: string;
  call_sid: string;
  status: string;
  direction: string;
  from_number: string;
  to_number: string;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
}

// Auth API
export const authApi = {
  register: async (email: string, password: string, name: string, company?: string): Promise<AuthResponse> => {
    const response = await api.post('/api/v1/auth/register', { email, password, name, company });
    return response.data;
  },

  login: async (email: string, password: string): Promise<AuthResponse> => {
    const response = await api.post('/api/v1/auth/login', { email, password });
    return response.data;
  },

  me: async (): Promise<User> => {
    const response = await api.get('/api/v1/auth/me');
    return response.data;
  },

  logout: async (): Promise<void> => {
    await api.post('/api/v1/auth/logout');
  },
};

// Calls API
export const callsApi = {
  initiate: async (phoneNumber: string, systemPrompt?: string): Promise<any> => {
    const response = await api.post('/api/v1/calls/initiate', {
      phone_number: phoneNumber,
      system_prompt: systemPrompt,
    });
    return response.data;
  },

  list: async (limit: number = 20): Promise<Call[]> => {
    const response = await api.get(`/api/v1/calls/list?limit=${limit}`);
    return response.data.calls || [];
  },

  getStatus: async (callId: string): Promise<any> => {
    const response = await api.get(`/api/v1/calls/status/${callId}`);
    return response.data;
  },

  hangup: async (callId: string): Promise<void> => {
    await api.post(`/api/v1/calls/hangup/${callId}`);
  },
};

// Chat API
export const chatApi = {
  send: async (message: string, conversationId?: string): Promise<any> => {
    const response = await api.post('/api/v1/chat/send', {
      message,
      conversation_id: conversationId,
    });
    return response.data;
  },

  history: async (conversationId: string): Promise<any> => {
    const response = await api.get(`/api/v1/chat/history/${conversationId}`);
    return response.data;
  },
};

// Health API
export const healthApi = {
  check: async (): Promise<any> => {
    const response = await api.get('/health');
    return response.data;
  },
};

export default api;
