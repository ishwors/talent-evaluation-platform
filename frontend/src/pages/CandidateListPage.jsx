import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { candidatesAPI } from '../api/client';

export default function CandidateListPage() {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState({
    status: '',
    role_applied: '',
    skill: '',
    keyword: '',
  });
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const navigate = useNavigate();

  const user = JSON.parse(localStorage.getItem('user') || '{}');

  const fetchCandidates = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = { page, page_size: pageSize };
      if (filters.status) params.status = filters.status;
      if (filters.role_applied) params.role_applied = filters.role_applied;
      if (filters.skill) params.skill = filters.skill;
      if (filters.keyword) params.keyword = filters.keyword;

      const response = await candidatesAPI.list(params);
      setCandidates(response.data.candidates);
      setTotalPages(response.data.total_pages);
      setTotal(response.data.total);
    } catch (err) {
      setError('Failed to fetch candidates.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filters]);

  useEffect(() => {
    fetchCandidates();
  }, [fetchCandidates]);

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const clearFilters = () => {
    setFilters({ status: '', role_applied: '', skill: '', keyword: '' });
    setPage(1);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  const getStatusColor = (status) => {
    const colors = {
      new: 'status-new',
      reviewed: 'status-reviewed',
      hired: 'status-hired',
      rejected: 'status-rejected',
      archived: 'status-archived',
    };
    return colors[status] || '';
  };

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-left">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
          <h1>TalentScan Dashboard</h1>
        </div>
        <div className="header-right">
          <span className="user-badge">
            <span className={`role-tag ${user.role}`}>{user.role}</span>
            {user.name}
          </span>
          <button className="btn btn-ghost" onClick={handleLogout}>Sign Out</button>
        </div>
      </header>

      {/* Filters */}
      <section className="filters-section">
        <div className="filters-bar">
          <div className="filter-group">
            <label>Status</label>
            <select
              id="filter-status"
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="new">New</option>
              <option value="reviewed">Reviewed</option>
              <option value="hired">Hired</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>

          <div className="filter-group">
            <label>Role</label>
            <input
              id="filter-role"
              type="text"
              placeholder="e.g. Full-Stack Engineer"
              value={filters.role_applied}
              onChange={(e) => handleFilterChange('role_applied', e.target.value)}
            />
          </div>

          <div className="filter-group">
            <label>Skill</label>
            <input
              id="filter-skill"
              type="text"
              placeholder="e.g. Python"
              value={filters.skill}
              onChange={(e) => handleFilterChange('skill', e.target.value)}
            />
          </div>

          <div className="filter-group">
            <label>Keyword</label>
            <input
              id="filter-keyword"
              type="text"
              placeholder="Search name, email..."
              value={filters.keyword}
              onChange={(e) => handleFilterChange('keyword', e.target.value)}
            />
          </div>

          <button className="btn btn-ghost" onClick={clearFilters}>Clear</button>
        </div>
        <div className="results-count">
          {total} candidate{total !== 1 ? 's' : ''} found
        </div>
      </section>

      {/* Content */}
      <main className="candidates-grid">
        {loading && (
          <div className="loading-state">
            <div className="spinner large"></div>
            <p>Loading candidates...</p>
          </div>
        )}

        {error && <div className="error-message">{error}</div>}

        {!loading && !error && candidates.length === 0 && (
          <div className="empty-state">
            <p>No candidates match your filters.</p>
            <button className="btn btn-primary" onClick={clearFilters}>Clear Filters</button>
          </div>
        )}

        {!loading && candidates.map((candidate) => (
          <div
            key={candidate.id}
            className="candidate-card"
            onClick={() => navigate(`/candidates/${candidate.id}`)}
          >
            <div className="candidate-card-header">
              <div className="candidate-avatar">
                {candidate.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
              </div>
              <div className="candidate-info">
                <h3>{candidate.name}</h3>
                <p className="candidate-email">{candidate.email}</p>
              </div>
              <span className={`status-badge ${getStatusColor(candidate.status)}`}>
                {candidate.status}
              </span>
            </div>
            <div className="candidate-card-body">
              <p className="candidate-role">{candidate.role_applied}</p>
              <div className="skills-list">
                {candidate.skills.slice(0, 4).map((skill) => (
                  <span key={skill} className="skill-tag">{skill}</span>
                ))}
                {candidate.skills.length > 4 && (
                  <span className="skill-tag more">+{candidate.skills.length - 4}</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </main>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="pagination">
          <button
            className="btn btn-ghost"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            ← Previous
          </button>
          <span className="page-info">
            Page {page} of {totalPages}
          </span>
          <button
            className="btn btn-ghost"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
