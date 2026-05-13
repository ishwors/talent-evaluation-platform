import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 responses — redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ── Auth API ─────────────────────────────────────────────────────

export const authAPI = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  register: (name, email, password) => api.post('/auth/register', { name, email, password }),
  getMe: () => api.get('/auth/me'),
};

// ── Candidates API ───────────────────────────────────────────────

export const candidatesAPI = {
  list: (params = {}) => api.get('/candidates', { params }),
  getById: (id) => api.get(`/candidates/${id}`),
  submitScore: (id, data) => api.post(`/candidates/${id}/scores`, data),
  generateSummary: (id) => api.post(`/candidates/${id}/summary`),
  updateNotes: (id, internal_notes) => api.put(`/candidates/${id}/notes`, { internal_notes }),
  delete: (id) => api.delete(`/candidates/${id}`),
};

export default api;
