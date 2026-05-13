import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../api/client';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isRegister, setIsRegister] = useState(false);
  const [name, setName] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      let response;
      if (isRegister) {
        response = await authAPI.register(name, email, password);
      } else {
        response = await authAPI.login(email, password);
      }

      const { access_token, role, user_id, name: userName } = response.data;
      localStorage.setItem('token', access_token);
      localStorage.setItem('user', JSON.stringify({ id: user_id, role, name: userName, email }));
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Authentication failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">
            <svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <h1>TalentScan</h1>
          <p className="login-subtitle">Candidate Scoring Dashboard</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <h2>{isRegister ? 'Create Account' : 'Welcome Back'}</h2>
          
          {error && <div className="error-message">{error}</div>}

          {isRegister && (
            <div className="form-group">
              <label htmlFor="name">Full Name</label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter your full name"
                required
              />
            </div>
          )}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
              minLength={6}
            />
          </div>

          <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
            {loading ? (
              <span className="loading-spinner">
                <span className="spinner"></span>
                {isRegister ? 'Creating...' : 'Signing in...'}
              </span>
            ) : (
              isRegister ? 'Create Account' : 'Sign In'
            )}
          </button>

          <div className="login-toggle">
            <button type="button" className="btn-link" onClick={() => { setIsRegister(!isRegister); setError(''); }}>
              {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Register"}
            </button>
          </div>

          {!isRegister && (
            <div className="demo-credentials">
              <p><strong>Demo Accounts:</strong></p>
              <div className="demo-row">
                <button type="button" className="btn btn-ghost" onClick={() => { setEmail('admin@ishwors.com'); setPassword('admin123'); }}>
                  Admin
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => { setEmail('reviewer@ishwors.com'); setPassword('reviewer123'); }}>
                  Reviewer
                </button>
              </div>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
